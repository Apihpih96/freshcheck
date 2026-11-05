# FreshCheck: Catch Stale AI Answers Before They Mislead You

**Global AI Hackathon** | Tavily Track: Problem Statement 01, Stale-answer detector | Bifrost Priority Track: Problem Statement 04, A feature the open-source gateway is missing

> AI often states old facts with full confidence. FreshCheck re-verifies every time-sensitive claim on the live web, shows the proof and fixes the answer. It works as a website, as an OpenAI-compatible layer in front of the Bifrost gateway, and as a tool inside Bifrost's MCP Gateway.

## Project links

| What | Link |
|---|---|
| Source code | https://github.com/yogeshx21/freshcheck |
| Presentation (PDF) | [FreshCheck_Visionaries_Global_AI_Hackathon.pdf](FreshCheck_Visionaries_Global_AI_Hackathon.pdf) |


## Team Visionaries (Dream . Innovate . Build)

All three members contributed equally.

| Name | Role |
|---|---|
| Yogesh Mondhe | Team leader |
| Khushi Wanjari | Team Member |
| Ayush Kakulte | Team Member |

## Problem statement

**Tavily Track, 01: Stale-answer detector**
LLM apps confidently cite facts that changed (pricing, API versions, laws, leadership). Build a layer that takes any LLM answer, flags claims likely to have gone stale, and re-verifies them against live sources with a freshness score per claim.

**Bifrost Priority Track, 04: A feature the open-source gateway is missing**
Extend the open-source Bifrost gateway with something its operators would miss if you took it away: a plugin, an integration, a UI, a routing or caching strategy, or a developer tool.

FreshCheck answers both: it is the stale-answer detector (Tavily #1) and it plugs into Bifrost as a freshness layer and an MCP tool (Bifrost #4).

## The problem

AI answers go stale and still sound sure. Facts that change are the facts that hurt, and a user cannot tell which part of a confident answer is out of date.

| Type | Example of a stale claim |
|---|---|
| Prices | "The latest iPhone is the iPhone 14." |
| Versions | "Python 3.12 is the latest version." |
| AI models | "ChatGPT runs on GPT-3.5." |
| Laws | "The IPC is India's main criminal law." |

## Our solution

FreshCheck takes any AI answer, finds only the facts that can change, searches the live web for the current truth, and gives a verdict for every claim.

| Verdict | Meaning |
|---|---|
| STALE (red) | Outdated. Shows the correct current value and a source link. |
| FRESH (green) | Confirmed current by a live source, with the proof quote. |
| UNCLEAR (amber) | Not enough evidence, so it is flagged instead of guessed. |

**For every claim you get:**
- A verdict: stale, fresh or unclear
- A freshness score from 0 to 100
- The correct, current value
- An evidence quote and source link
- A best-before date
- A fixed version of the answer

### How it works

1. **Input:** paste any AI answer, or ask a question.
2. **Extract:** finds only facts that can change: prices, versions, leaders, laws.
3. **Search:** Tavily live search plus a recency probe that looks for updates.
4. **Verify:** the proof quote is checked inside the source. Score from 0 to 100.
5. **Fix:** highlights, correct value, source link and a one-click fix.

> **A verdict without proof is never trusted.** The evidence quote must really appear inside the source page.

### Why FreshCheck is different

| Plain AI answer | Normal web search | FreshCheck |
|---|---|---|
| Sounds sure, shows no proof | Gives links, you do the reading | Finds only facts that can change |
| Knowledge stops at its training date | Old pages often rank above new ones | Recency probe looks for the update |
| Cannot tell which facts have changed | No verdict and no score | Verdict, score, proof quote and a fix |

## Key features

- **Source proof:** evidence quote and source link, checked inside the page
- **Explainable score:** 0 to 100 with a "Why this score?" breakdown
- **Time machine:** see how a fact changed over the years
- **Best-before date:** each fact gets a shelf life (prices 30 days, versions 90, statistics 90, laws 180, leadership 365, other 60)
- **Fix my answer:** rewrites the answer using the current facts
- **Compare models:** ask several AI models at once and see which one is the most outdated
- **Voice and languages:** voice chat and read aloud in English, Hindi, Marathi and Hinglish
- **Share and export:** share link, PDF, copy or .txt, plus one-click demo traps
- **Dashboard:** which kinds of facts go stale most often
- **OpenAI-compatible gateway layer:** every reply carries `x-freshcheck-status`, `x-freshcheck-score` and `x-freshcheck-stale` headers
- **Bifrost MCP tool:** `check_freshness`, so models behind Bifrost can verify their own facts
- **Result and search cache:** saves Tavily credits

## Tavily #1: Stale-answer detector

| What the problem statement asks | What FreshCheck does |
|---|---|
| Takes any LLM answer | Paste text on the website, or call `/v1/chat/completions` with any model |
| Flags claims likely to have gone stale | Extracts prices, versions, leaders and laws, and marks each STALE, FRESH or UNCLEAR |
| Re-verifies against live sources | Tavily live search plus a recency probe. The proof quote is checked inside the source |
| Freshness score per claim | A 0 to 100 score on every claim, with a "Why this score?" breakdown |

## Bifrost #4: a feature for the gateway

- **MCP tool server:** FreshCheck is registered in Bifrost's MCP Gateway as `check_freshness`, so models behind Bifrost can verify their own facts.
- **Freshness layer:** an OpenAI-compatible endpoint in front of Bifrost. Every reply carries x-freshcheck score and status headers.
- **Compare via gateway:** one question to several models, all through Bifrost, to show which AI is the most outdated.

Proof from the Bifrost dashboard: the MCP Catalog shows `freshcheck` as Healthy with 1/1 tools enabled and 1/1 auto-execute, and the MCP Logs show a model calling `check_freshness` through the gateway successfully. Screenshots are in the presentation PDF.

## System architecture

**Flow 1: Freshness layer in front of Bifrost**

```
Any app or website --> FreshCheck (FastAPI: extract, verify, score) --> Bifrost gateway --> Groq models
                              |                                        (OpenAI-compatible,   (gpt-oss-120b,
                              v                                         virtual key)         gpt-oss-20b)
                      Tavily live web search
```

**Flow 2: Freshness tool inside Bifrost (MCP)**

```
Model behind Bifrost --> Bifrost MCP Gateway --> FreshCheck /mcp --> Tavily live web
 (asks to verify its     (tool: check_freshness)  (MCP server         (sources and proof quotes)
  own facts)                                       over HTTP)
```

Every LLM call in both flows goes through Bifrost, so the gateway keeps control of keys, models and logs.

## Drop-in for any app

Send a normal chat request to FreshCheck and get the answer plus freshness info:

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
print(r.headers["x-freshcheck-status"])
print(r.json()["freshcheck"]["claims"])
```

Example response headers: `x-freshcheck-status: stale-found`, `x-freshcheck-score: 42`, `x-freshcheck-stale: 1`.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/check` | Check an AI answer and return claims with verdicts |
| POST | `/ask` | Ask a question and check the answer |
| POST | `/fix` | Rewrite the answer using the current facts |
| POST | `/history` | Time machine: how a fact changed over the years |
| POST | `/compare` | Ask several models and compare freshness |
| GET | `/stats` | Dashboard statistics |
| POST | `/v1/chat/completions` | OpenAI-compatible gateway layer |
| POST | `/mcp` | Bifrost MCP tool (`check_freshness`) |

## How the freshness score works

Every claim gets an explainable score from 0 to 100 (100 means fully true and current). The "Why this score?" breakdown lists every plus and minus point.

| Verdict | Base score | Adjustments |
|---|---|---|
| FRESH | 70 | plus points for the source type (official, reference, news, blog), plus 10 if the proof quote is verified, minus 25 if sources conflict |
| STALE | 20 | source type points, minus 5 if the proof quote is verified, plus 15 if sources conflict |
| UNCLEAR | 35 | minus 5 if sources conflict |

## Results

**Internal evaluation: 12/12 cases correct (100%)** with `groq/openai/gpt-oss-120b` through Bifrost (9 stale, 2 fresh, 1 timeless).

| Case | Expected | Got | Result |
|---|---|---|---|
| Python version | stale | stale | PASS |
| Twitter CEO | stale | stale | PASS |
| India: IPC | stale | stale | PASS |
| India: CrPC | stale | stale | PASS |
| India: GST slabs | stale | stale | PASS |
| iPhone | stale | stale | PASS |
| ChatGPT model | stale | stale | PASS |
| Node.js LTS | stale | stale | PASS |
| Windows | stale | stale | PASS |
| Anthropic CEO | fresh | fresh | PASS |
| Microsoft CEO | fresh | fresh | PASS |
| Timeless fact | none | (no claims) | PASS |

Cases are single-sentence claims with known answers. `stale` must be flagged outdated, `fresh` must be confirmed current, `none` must not be flagged. Details are in [eval_report.md](eval_report.md).

**Real example:** the claim "Indian Penal Code (IPC) is the main criminal law in India" was marked **STALE, 15/100**. The current value: the Bharatiya Nyaya Sanhita, 2023 (effective July 1, 2024) replaced the IPC.

**Compare models:** for the question about the latest Python, `gpt-oss-120b` scored 30 and `gpt-oss-20b` scored 22. FreshCheck flagged the 20b answer, which named Python 3.13.0.

**Dashboard:** in our test checks, pricing and versions were the most often outdated fact types.

## Challenges we faced, and how we solved them

| Challenge | How we solved it |
|---|---|
| Old pages outrank new ones | A recency probe: a second search aimed at updates and replacements, so the new fact appears in the results |
| AI can invent proof | The evidence quote must really appear inside the source page, or the verdict is not trusted |
| Live search credits are limited | Search results and full checks are cached in files, so a repeated claim costs no new credits |
| Some claims cannot be proven | Those claims are marked UNCLEAR instead of guessed, and every score shows its plus and minus points |

## Who can use it

| User | Use |
|---|---|
| AI app builders | Add a freshness check to any chatbot through the gateway |
| Students and researchers | Check AI answers before using them in work |
| Businesses and support teams | Avoid wrong prices, rules and versions |
| Fact-checkers and everyday users | Voice and Hindi, Marathi, Hinglish support |

## Tech stack

| Category | Tools |
|---|---|
| Languages | Python 3, JavaScript, HTML, CSS, Batch script (one-click start), JSON (file cache and stats) |
| Backend | FastAPI, Uvicorn, Pydantic |
| LLM access | OpenAI Python SDK (talks to Bifrost), Groq models `gpt-oss-120b` and `gpt-oss-20b` |
| Live search | Tavily Search API (`tavily-python`) |
| Gateway | Bifrost AI gateway, Model Context Protocol (MCP) |
| Other | python-dotenv, requests, browser Web Speech API (voice and read aloud) |

## Project structure

```
freshcheck/
+-- server.py         web server, all endpoints
+-- extractor.py      finds facts that can go stale
+-- verifier.py       live search, verdict, score
+-- config.py         Bifrost client, Tavily, cache
+-- mcp_server.py     MCP tool: check_freshness
+-- index.html        website, 4 languages, voice
+-- eval.py           12-case accuracy test
+-- eval_report.md    latest evaluation result
+-- warm_demo.py      warms the cache for the demo
+-- run.bat           starts Bifrost + FreshCheck
+-- requirements.txt  Python dependencies
+-- .env.example      template for API keys
+-- test_*.py         gateway, Tavily and MCP tests
```

## Prerequisites

| Tool | Why |
|---|---|
| Git | to clone the code |
| Python 3 (tested on 3.14) | backend |
| Node.js and npm | `run.bat` starts Bifrost with `npx` |
| Tavily API key | live web search, from https://app.tavily.com |
| Groq API key | LLM models, from https://console.groq.com |
| A recent Chrome or Edge | website, voice and read aloud |

## Setup

**1. Get the code**

```
git clone https://github.com/yogeshx21/freshcheck.git
cd freshcheck
```

**2. Install Python packages**

Windows:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Add your API keys**

Copy `.env.example` to `.env` and fill in your keys. Never upload `.env` to GitHub.

| Setting | Meaning |
|---|---|
| `TAVILY_API_KEY` | Tavily live search key |
| `GROQ_API_KEY` | Groq key (the same key is also added inside Bifrost) |
| `BIFROST_VK` | Bifrost virtual key (Bifrost dashboard at http://localhost:8080, Governance, Virtual Keys) |
| `LLM_BASE_URL` | Bifrost URL, default `http://localhost:8080/v1` |
| `MODEL` | Default model, `groq/openai/gpt-oss-120b` |
| `COMPARE_MODELS` | Models used by Compare, `groq/openai/gpt-oss-120b,groq/openai/gpt-oss-20b` |
| `RECENCY_PROBE=0` | Optional: turns off the second recency search (saves credits, less accurate) |
| `FC_MIN_CHARS` | Optional: answers shorter than this are not checked in the gateway layer |

## Run the project

**Windows (one click):** double-click `run.bat`. It opens two windows (Bifrost and FreshCheck), then opens the website. Keep both windows open while you use the app.

**Or manually, in two terminals:**

```
# Terminal 1: Bifrost gateway
npx -y @maximhq/bifrost

# Terminal 2: FreshCheck (virtual environment active)
python -m uvicorn server:app --reload
```

Open http://127.0.0.1:8000 for the website and http://localhost:8080 for the Bifrost dashboard. On the top right of the website you should see "Bifrost - Gateway online".

## Register FreshCheck as a Bifrost MCP tool

1. Keep FreshCheck running.
2. In the Bifrost dashboard, open the MCP section and add a new MCP server named `freshcheck` with connection type HTTP and the URL `http://127.0.0.1:8000/mcp`.
3. FreshCheck should show as Healthy with the tool `check_freshness`. Models behind Bifrost can now call it to verify their own facts.

## Check that it works

- Open http://127.0.0.1:8000, click one of the demo traps and see STALE / FRESH flags with proof links.
- Run the accuracy test: `python eval.py` (writes `eval_report.md`).
- Gateway test: `python test_gateway.py`
- Tavily test: `python test_tavily.py`
- MCP tests: `python test_mcp.py`, `python test_bifrost_mcp.py`

## Limitations

- Needs internet and API keys (Tavily and Groq) for live search and the gateway.
- Only 12 internal test cases so far, so a bigger benchmark is needed.
- The verdict depends on what the search finds. If no source proves a claim, it is marked UNCLEAR.
- Runs locally for now (127.0.0.1:8000).

## What we build next

- Host it online with a public link
- A browser extension that checks an AI answer right where you read it
- A bigger benchmark with hundreds of claims, more languages and fact types
- Auto re-check of a fact when its best-before date passes

## Acknowledgements

- Tavily (live web search) and Bifrost (open-source AI gateway)
- Groq (`gpt-oss` models)
- Open-source libraries: FastAPI, Uvicorn, Pydantic, OpenAI Python SDK

Built by Team Visionaries for the Global AI Hackathon.
