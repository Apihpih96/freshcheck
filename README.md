# FreshCheck: Experimental Stale-Answer Review

FreshCheck is a local web prototype that uses an LLM to find potentially time-sensitive claims in an answer, searches Tavily for related web results, and asks a configured LLM to suggest a verdict. Treat its labels, explanations, corrected values, and scores as suggestions—not verified facts. Check the original sources yourself before relying on them.

The repository includes a FastAPI web app, an optional OpenAI-compatible sidecar endpoint, and an MCP endpoint. The LLM can use Groq directly (the code default) or a Bifrost instance configured in `.env`.

## Hackathon scope

The relevant Tavily problem statement is **“Build a Stale-Answer Detector for AI Applications.”** This repository explores that workflow, but its model-generated verdicts and score are not a reliable freshness or truth guarantee.

The event’s separate Bifrost problem statement is **“Open-Source Bifrost Gateway.”** FreshCheck can be configured alongside Bifrost through a sidecar and MCP server, but it does not modify Bifrost or implement an upstream gateway extension. Do not describe it as satisfying the separate Bifrost problem statement, or use unverified numbered track names, without organizer confirmation.

## What the prototype does

1. Accepts pasted text at `/check`, or generates an answer and checks it at `/ask`.
2. Uses an LLM prompt to extract up to eight candidate time-sensitive claims.
3. Searches Tavily for each candidate; an optional second query adds update/replacement terms.
4. Asks the configured LLM to label each claim `fresh`, `stale`, or `unclear` from the returned search-result text.
5. Checks the proposed evidence quote against the returned result text using normalized matching with a tolerant word-overlap fallback. A failed match downgrades the verdict to `unclear`.
6. Displays the proposed verdict, explanation, source link, quote, and a heuristic score. Other endpoints offer an answer rewrite, a search-based timeline, model comparison, and aggregate counters.

FreshCheck does not fetch or authenticate the original source page, independently establish that a result supports a claim, or guarantee the model’s interpretation. A quote match only shows that similar text occurs in the Tavily result content; it is not proof of claim truth. The model may return an incorrect label, explanation, or “correct” value.

## Labels and scores

- `fresh`, `stale`, and `unclear` are LLM-generated assessments based on search results, not ground-truth findings.
- The 0–100 `freshness_score` is a hand-written formula using the proposed label, a broad source category, quote-match result, and reported conflict flag. It is not a calibrated probability, confidence score, or measure of truth.
- `best_before` is a fixed review interval by claim type, not a source publication date or a validated expiry prediction.
- Review the original source, date, context, and claim manually before using any conclusion or rewritten answer.

## Features in the repository

- Candidate-claim extraction and Tavily Search queries, with an optional recency-oriented second query.
- Proposed per-claim labels, source excerpts/links, explanations, a heuristic score, and a fixed review-date cue.
- Optional answer rewrite, search-result timeline, multi-model comparison, recent-check history, and aggregate dashboard.
- OpenAI-compatible `/v1/chat/completions` sidecar that adds FreshCheck metadata and response headers; streaming is not supported.
- JSON-RPC MCP endpoint exposing `check_freshness`.
- Browser voice input/output where supported, English/Hindi/Marathi/Hinglish UI text, and report sharing/export.

These features are experimental; their presence in the code does not establish reliability or suitability for production use.

## Bifrost configuration

Bifrost is optional. Without overrides, `config.py` defaults to Groq directly (`https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b`). Copying `.env.example` configures the app to use Bifrost at `http://localhost:8080/v1`; fill in the required provider key and Bifrost virtual key first.

When configured, the sidecar forwards requests to the selected LLM endpoint and adds FreshCheck metadata. The `/mcp` endpoint can be registered as an MCP server in the Bifrost dashboard. These are integrations around Bifrost, not a new feature in Bifrost’s core.

## Setup

### Requirements

- Git
- Python 3
- Node.js and npm, only if using `run.bat` to start Bifrost
- Tavily API key
- Groq API key, or an LLM provider configured in Bifrost
- Recent Chrome or Edge for the browser UI and voice features

### Install

```sh
git clone https://github.com/yogeshx21/freshcheck.git
cd freshcheck
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and replace the placeholder values. Do not commit `.env` or API keys. The example configures Bifrost; if using Groq directly, set `GROQ_API_KEY` and either leave out the Bifrost overrides or configure the desired provider explicitly.

Run `run.bat` on Windows to start Bifrost and FreshCheck, or start them separately:

```sh
# Optional Bifrost terminal
npx -y @maximhq/bifrost

# FreshCheck terminal, with the virtual environment active
python -m uvicorn server:app --reload
```

Open `http://127.0.0.1:8000`. Bifrost is used only when the `.env` endpoint/model settings point to it and its keys are configured. The app otherwise uses the direct Groq defaults.

### Register the MCP endpoint

With FreshCheck running, add an HTTP MCP server in Bifrost at `http://127.0.0.1:8000/mcp`. The server exposes `check_freshness`. Its output is still model-generated and should be reviewed against original sources.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/check` | Extract and assess candidate claims from supplied text |
| POST | `/ask` | Ask the configured LLM, then assess its answer |
| POST | `/fix` | Ask the configured LLM to rewrite an answer from supplied claim results |
| POST | `/history` | Ask the LLM to build a timeline from Tavily search results |
| POST | `/compare` | Generate and assess answers from configured models |
| GET | `/stats` | Read local aggregate counters |
| POST | `/v1/chat/completions` | OpenAI-compatible sidecar; adds FreshCheck metadata when applicable |
| POST | `/mcp` | JSON-RPC MCP endpoint (`check_freshness`) |

Example sidecar request (for a Bifrost-configured `.env`):

```python
import requests

r = requests.post(
    "http://127.0.0.1:8000/v1/chat/completions",
    json={
        "model": "groq/openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "What is the latest Python?"}]
    },
    timeout=180,
)
print(r.headers.get("x-freshcheck-status"))
print(r.json().get("freshcheck", {}).get("claims", []))
```

The model name must be available through the configured LLM endpoint. The sidecar removes streaming options and does not provide streaming responses.

## Evaluation record

The checked-in [`eval_report.md`](eval_report.md) records one internal 12-case run dated November 5, 2026, with all 12 labels matching that test’s expected labels for `groq/openai/gpt-oss-120b`. The cases are a small, hand-picked set of single-sentence examples; this is not an independent benchmark and does not establish general accuracy or calibration.

A separate small-model experiment in the project work matched 2 of 5 expected labels. That experiment used a different model and test setup, so it is not directly comparable to the checked-in run. Together these results do not support a broad reliability claim; treat FreshCheck’s assessments as experimental.

Run the repository’s checks with configured credentials as needed:

```sh
python eval.py
python test_gateway.py
python test_tavily.py
python test_mcp.py
python test_bifrost_mcp.py
```

## Limitations

- Search results are snippets/content returned by Tavily; the app does not independently open or authenticate the linked pages.
- LLM extraction, verdicts, reasons, values, timelines, comparisons, and rewrites can be wrong.
- Quote checking is normalized and may use tolerant word overlap; it does not prove relevance or entailment.
- The score and `best_before` date are simple heuristics, not calibrated measures or validated predictions.
- Caches and counters are local files; the project runs locally by default and has no public deployment URL in this repository.
- Live checks require working provider credentials, network access, and available API quotas.

## Project structure

```
freshcheck/
+-- server.py         web app, API, sidecar and MCP endpoints
+-- extractor.py      LLM-prompted claim extraction
+-- verifier.py       Tavily search, LLM assessments and heuristic score
+-- config.py         provider settings, clients, cache and tracing
+-- mcp_server.py     JSON-RPC MCP tool
+-- index.html        browser interface
+-- eval.py           12-case internal evaluation
+-- eval_report.md    recorded evaluation output
+-- warm_demo.py      optional cache warm-up
+-- run.bat           Windows launcher
+-- requirements.txt  Python dependencies
+-- .env.example      configuration template
+-- test_*.py         gateway, Tavily and MCP checks
```

## Team

Team Visionaries:

- Yogesh Mondhe — Team Leader
- Khushi Wanjari — Team Member
- Ayush Kakulte — Team Member

Built for the Global AI Hackathon. This README describes the repository code and its limitations; it does not claim that the entry was submitted or accepted.
