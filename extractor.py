from config import chat, parse_json

TYPES = {"pricing", "version", "leadership", "law", "stat", "other"}

PROMPT = """You are a fact-extraction engine. Below is an AI's answer.
Extract ONLY facts that can change with time: prices, version numbers, "latest/current" claims,
who holds a role (CEO, minister, etc.), laws and rules, release dates, statistics, rankings.

For every such fact return:
- "claim": the fact in one short line, in the same language as the answer
- "exact_text": the shortest EXACT substring copied character-for-character from the answer that states this fact
- "type": one of pricing | version | leadership | law | stat | other
- "search_query": a short English web-search query (3-8 words) that would find the CURRENT truth.
  Do NOT put the claimed value in the query.
  For laws, rules, "main", "latest" or "currently" claims, end the query with: current status replaced 2026
Return ONLY JSON: {"claims":[{"claim":"","exact_text":"","type":"","search_query":""}]}
Maximum 8 claims. If there are none, return {"claims":[]}.

ANSWER:
"""


def extract_claims(answer, trace=None):
    raw = chat(
        [{"role": "user", "content": PROMPT + answer}],
        trace=trace,
        label="Extract claims",
        json_mode=True,
    )
    data = parse_json(raw)
    claims = data.get("claims", []) if isinstance(data, dict) else []
    clean = []
    for c in claims:
        if isinstance(c, dict) and c.get("claim") and c.get("search_query"):
            c["type"] = c.get("type") if c.get("type") in TYPES else "other"
            c["exact_text"] = c.get("exact_text") or ""
            clean.append(c)
    return clean[:8]


if __name__ == "__main__":
    sample = (
        "Claude Opus 4.8 costs $5 per million input tokens. "
        "Anthropic ka CEO Dario Amodei hai. Python 3.12 latest version hai."
    )
    for c in extract_claims(sample):
        print(c)
