import re, json, datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from config import (
    chat, parse_json, search, Trace, LOCK, load_json, save_json, MODEL, COMPARE_MODELS,
    RECENCY_PROBE, explain_error,
)
from extractor import extract_claims

SHELF_DAYS = {"pricing": 30, "version": 90, "leadership": 365, "law": 180, "stat": 90, "other": 60}
ANSWER_SYSTEM = "Answer the user's question clearly and concisely in under 150 words."


# ---------- helpers ----------
def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def quote_ok(quote, text):
    """True only if the quote really appears in the source text."""
    q, t = norm(quote), norm(text)
    if len(q) < 8:
        return False
    if q in t:
        return True
    qt, ts = q.split(), set(t.split())
    return len(qt) >= 6 and sum(w in ts for w in qt) / len(qt) >= 0.9


OFFICIAL_HOSTS = (
    "python.org", "anthropic.com", "claude.com", "openai.com", "github.com", "mozilla.org",
    "microsoft.com", "google.com", "apple.com", "nodejs.org", "reactjs.org", "react.dev",
)
NEWS_HOSTS = (
    "reuters", "apnews", "bbc", "nytimes", "forbes", "bloomberg", "techcrunch", "theverge",
    "cnbc", "wsj", "economictimes", "ndtv", "thehindu", "hindustantimes", "livemint", "wired",
)


def classify(url):
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return "blog"
    if host.endswith(".gov") or ".gov." in host or host.endswith(".edu") or ".nic.in" in host \
            or host.startswith("docs.") or ".docs." in host or host.startswith("developer.") \
            or host.startswith("platform.") or any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
        return "official"
    if "wikipedia.org" in host or "britannica.com" in host:
        return "reference"
    if any(n in host for n in NEWS_HOSTS):
        return "news"
    return "blog"


def find_span(answer, exact, claim):
    """Return [start, end] of the claim inside the answer, or None."""
    if exact:
        i = answer.lower().find(exact.lower())
        if i >= 0:
            return [i, i + len(exact)]
    words = {w for w in norm(claim).split() if len(w) >= 3}
    if not words:
        return None
    best, best_score = None, 0.0
    for m in re.finditer(r"[^.!?\n\u0964]+[.!?\u0964]?", answer):
        seg = m.group(0)
        sw = set(norm(seg).split())
        score = len(words & sw) / len(words)
        if score > best_score:
            lead = len(seg) - len(seg.lstrip())
            best, best_score = [m.start() + lead, m.end()], score
    return best if best_score >= 0.4 else None


# ---------- verification ----------
VERIFY = """Today's date is <<TODAY>>.
You are a strict fact-checker. Decide if the CLAIM is still true today using ONLY the numbered search results below.

Rules:
- If results disagree, trust official documentation and the newest sources.
- "evidence_quote" MUST be copied EXACTLY (word for word, max 30 words) from ONE result. Never invent or edit a quote.
- "evidence_source" is the number of the result that the quote came from.
- Never state a number, version or name in correct_value that does not appear in the results.
- If the results do not clearly settle it, verdict is "unclear".
- verdict: "fresh" (still true), "stale" (outdated or no longer true), or "unclear".
- freshness_score: 0-100 (100 = fully true and current).
- conflict: true if credible results contradict each other about this fact.
Write correct_value, reason and conflict_note in the same language as the claim.

Return ONLY JSON:
{"verdict":"","freshness_score":0,"correct_value":"","reason":"","evidence_quote":"","evidence_source":1,"conflict":false,"conflict_note":""}

CLAIM: <<CLAIM>>

SEARCH RESULTS:
<<RESULTS>>
"""


def gather_results(query, trace=None):
    """Main search + a 'recency probe' (a 2nd search aimed at updates and replacements).
    Old pages often outrank new ones, so the probe makes sure the NEW fact is in the results."""
    results = list(search(query, trace))
    if RECENCY_PROBE:
        try:
            probe = search(f"{query} latest update replaced {datetime.date.today().year}", trace)
        except Exception:
            probe = []
        seen = {r.get("url") for r in results}
        for r in probe:
            if r.get("url") not in seen:
                results.append(r)
                seen.add(r.get("url"))
    return results[:8]


SOURCE_POINTS_FRESH = {"official": 15, "reference": 8, "news": 8, "blog": 0}
SOURCE_POINTS_STALE = {"official": -12, "reference": -6, "news": -6, "blog": 0}


def compute_score(verdict, source_type, verified, conflict):
    """Explainable 0-100 freshness score. 100 = fully true and current.
    Returns (score, parts) where parts lists every +/- that made the number."""
    parts = []

    def add(key, pts):
        parts.append({"key": key, "points": pts})
        return pts

    if verdict == "fresh":
        s = add("fresh_base", 70)
        s += add("source_" + source_type, SOURCE_POINTS_FRESH.get(source_type, 0)) if SOURCE_POINTS_FRESH.get(source_type, 0) else 0
        s += add("proof_verified", 10) if verified else 0
        s += add("sources_conflict", -25) if conflict else 0
    elif verdict == "stale":
        s = add("stale_base", 20)
        s += add("source_" + source_type, SOURCE_POINTS_STALE.get(source_type, 0)) if SOURCE_POINTS_STALE.get(source_type, 0) else 0
        s += add("proof_verified", -5) if verified else 0
        s += add("sources_conflict", 15) if conflict else 0
    else:
        s = add("unclear_base", 35)
        s += add("sources_conflict", -5) if conflict else 0
    return max(0, min(100, s)), parts


def verify_claim(c, answer, trace=None):
    today = datetime.date.today()
    out = {
        "claim": c["claim"], "exact_text": c.get("exact_text", ""), "type": c.get("type", "other"),
        "search_query": c["search_query"], "verdict": "unclear", "freshness_score": 30,
        "correct_value": "", "reason": "", "evidence_quote": "", "evidence_verified": False,
        "source_url": "", "source_type": "blog", "conflict": False, "conflict_note": "",
        "span": find_span(answer, c.get("exact_text", ""), c["claim"]),
        "shelf_days": SHELF_DAYS.get(c.get("type", "other"), 60), "best_before": None,
        "score_parts": [], "llm_score": None,
    }
    try:
        results = gather_results(c["search_query"], trace)
        block = "\n\n".join(
            f"[{i + 1}] URL: {r.get('url')}\n{(r.get('content') or '')[:900]}"
            for i, r in enumerate(results)
        )
        prompt = (
            VERIFY.replace("<<TODAY>>", today.isoformat())
            .replace("<<CLAIM>>", c["claim"])
            .replace("<<RESULTS>>", block)
        )
        d = parse_json(chat([{"role": "user", "content": prompt}], trace=trace,
                            label="Verify: " + c["claim"][:42]))
    except Exception as e:
        out["reason"] = "Verification failed: " + explain_error(e)
        return out

    verdict = d.get("verdict") if d.get("verdict") in ("fresh", "stale", "unclear") else "unclear"
    try:
        llm_score = max(0, min(100, int(d.get("freshness_score", 30))))
    except Exception:
        llm_score = None
    quote = d.get("evidence_quote") or ""
    try:
        idx = max(1, min(len(results), int(d.get("evidence_source") or 1)))
    except Exception:
        idx = 1
    src = results[idx - 1] if results else {}
    verified = bool(results) and quote_ok(quote, src.get("content", ""))
    if not verified:  # the quote may come from another result
        for r in results:
            if quote_ok(quote, r.get("content", "")):
                verified, src = True, r
                break
    if not verified:  # a verdict without proof is never trusted
        verdict = "unclear"
        quote = ""
    out.update(
        verdict=verdict, correct_value=d.get("correct_value", ""),
        reason=d.get("reason", ""), evidence_quote=quote, evidence_verified=verified,
        source_url=src.get("url") or (results[0].get("url") if results else ""),
        conflict=bool(d.get("conflict")), conflict_note=d.get("conflict_note", ""),
        llm_score=llm_score,
    )
    out["source_type"] = classify(out["source_url"])
    out["freshness_score"], out["score_parts"] = compute_score(
        verdict, out["source_type"], verified, out["conflict"])
    if verdict == "fresh":
        out["best_before"] = (today + datetime.timedelta(days=out["shelf_days"])).isoformat()
    return out


def summarize(claims):
    n = len(claims)
    f = sum(c["verdict"] == "fresh" for c in claims)
    s = sum(c["verdict"] == "stale" for c in claims)
    avg = round(sum(c["freshness_score"] for c in claims) / n) if n else 0
    return {"avg": avg, "fresh": f, "stale": s, "unclear": n - f - s, "n": n}


# ---------- stats for the dashboard ----------
STATS_FILE = "stats.json"


def load_stats():
    return load_json(STATS_FILE, {
        "checks": 0, "claims": 0, "types": {}, "live_searches": 0,
        "cache_hits": 0, "tokens": 0, "llm_calls": 0,
    })


def record_stats(claims, trace):
    with LOCK:
        s = load_stats()
        s["checks"] += 1
        s["claims"] += len(claims)
        for c in claims:
            t = s["types"].setdefault(c["type"], {"fresh": 0, "stale": 0, "unclear": 0})
            t[c["verdict"]] += 1
        if trace is not None:
            s["live_searches"] += trace.live_searches
            s["cache_hits"] += trace.cache_hits
            s["tokens"] += trace.tokens
            s["llm_calls"] += trace.llm_calls
        save_json(STATS_FILE, s)


def check_answer(answer, trace=None):
    trace = trace if trace is not None else Trace()
    claims = extract_claims(answer, trace)
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda c: verify_claim(c, answer, trace), claims))
    record_stats(results, trace)
    return results


# ---------- feature: fix my answer ----------
FIX = """Rewrite the AI ANSWER below so that every outdated or unverified fact is corrected,
using ONLY the VERIFIED FACTS list. Keep the same language, tone and roughly the same length.
Wrap every corrected or changed fact in double asterisks, like **this**.
Do not add any fact that is not in the list. If a fact is marked "unverified", soften it
(for example "may have changed"). Return only the rewritten answer.

ANSWER:
<<ANSWER>>

VERIFIED FACTS:
<<FACTS>>
"""


def fix_answer(answer, claims, trace=None):
    items, sources = [], []
    for c in claims:
        if c.get("verdict") == "stale":
            items.append({"outdated_claim": c["claim"], "correct_value": c.get("correct_value", "")})
            if c.get("source_url"):
                sources.append(c["source_url"])
        elif c.get("verdict") == "unclear":
            items.append({"claim": c["claim"], "status": "unverified"})
    if not items:
        return {"fixed": answer, "sources": [], "changed": False}
    prompt = FIX.replace("<<ANSWER>>", answer).replace(
        "<<FACTS>>", json.dumps(items, ensure_ascii=False))
    fixed = chat([{"role": "user", "content": prompt}], trace=trace, label="Fix answer")
    return {"fixed": fixed, "sources": sources, "changed": True}


# ---------- feature: time machine ----------
HISTORY = """Today's date is <<TODAY>>.
Using ONLY the numbered search results, build a short timeline of how this fact changed over time.
Fact: <<CLAIM>>

Rules:
- Oldest first, newest last (the last item must be the current state). 3 to 7 items.
- Only include entries clearly supported by the results. Never invent dates or values.
- "when" is a year or date text, "value" is what was true then, "note" is a few words of context.
- "source" is the number of the result that supports the entry (or 0).
- If the results do not contain enough history, return an empty timeline.
Write in the same language as the fact.

Return ONLY JSON: {"timeline":[{"when":"","value":"","note":"","source":0}]}

SEARCH RESULTS:
<<RESULTS>>
"""


def fact_history(claim, query, trace=None):
    results = search(query + " history timeline over time previous changes", trace)
    block = "\n\n".join(
        f"[{i + 1}] URL: {r.get('url')}\n{(r.get('content') or '')[:900]}"
        for i, r in enumerate(results)
    )
    prompt = (
        HISTORY.replace("<<TODAY>>", datetime.date.today().isoformat())
        .replace("<<CLAIM>>", claim)
        .replace("<<RESULTS>>", block)
    )
    d = parse_json(chat([{"role": "user", "content": prompt}], trace=trace, label="Time machine"))
    out = []
    for e in d.get("timeline", []) if isinstance(d, dict) else []:
        if not isinstance(e, dict) or not e.get("when") or not e.get("value"):
            continue
        try:
            n = int(e.get("source") or 0)
        except Exception:
            n = 0
        url = results[n - 1].get("url") if 1 <= n <= len(results) else ""
        out.append({"when": str(e["when"]), "value": str(e["value"]),
                    "note": str(e.get("note", "")), "source_url": url})
    return {"timeline": out[:7]}


# ---------- feature: compare models ----------
def compare_models(question, models=None):
    models = models or COMPARE_MODELS

    def run(model):
        tr = Trace()
        try:
            ans = chat(
                [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": question}],
                model=model, trace=tr, label=f"Answer ({model})", temperature=0.2,
            )
            claims = check_answer(ans, tr)
            return {"model": model, "answer": ans, "claims": claims,
                    "summary": summarize(claims), "trace": tr.summary(), "error": ""}
        except Exception as e:
            return {"model": model, "answer": "", "claims": [],
                    "summary": summarize([]), "trace": tr.summary(), "error": str(e)[:200]}

    with ThreadPoolExecutor(max_workers=len(models)) as ex:
        return list(ex.map(run, models))
