import os, hashlib, urllib.request, urllib.error
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import (
    llm, chat, Trace, MODEL, COMPARE_MODELS, GATEWAY_NAME, LLM_BASE_URL, load_json, save_json,
    explain_error,
)
from verifier import (
    check_answer, fix_answer, fact_history, compare_models, summarize, load_stats, ANSWER_SYSTEM,
)

app = FastAPI(title="FreshCheck")

# Whole-result cache: the same input a second time returns instantly (great for demos).
RC_FILE = "results_cache.json"
RC = load_json(RC_FILE, {})
FC_MIN_CHARS = int(os.getenv("FC_MIN_CHARS", "40"))


def key_of(kind, text):
    return kind + ":" + hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()


def cached_trace():
    return {
        "gateway": GATEWAY_NAME, "base_url": LLM_BASE_URL, "model": MODEL,
        "steps": [{"name": "Result cache hit", "detail": "served instantly", "ms": 0}],
        "llm_calls": 0, "tokens": 0, "live_searches": 0, "cache_hits": 0, "total_ms": 0,
    }


class Q(BaseModel):
    text: str


class FixIn(BaseModel):
    answer: str
    claims: list[dict]


class HistIn(BaseModel):
    claim: str
    search_query: str


def fail(e):
    """Build an HTTP error with a clear, human sentence."""
    code = 503 if type(e).__name__ == "APIConnectionError" else 500
    return HTTPException(code, explain_error(e))


def reachable(url, timeout=3):
    """True if anything answers at this URL (even 401/404). False only if nobody is listening."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def need_text(q):
    t = q.text.strip()
    if not t:
        raise HTTPException(400, "empty text")
    return t


def run_pipeline(text, ask):
    tr = Trace()
    if ask:
        answer = chat(
            [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": text}],
            trace=tr, label="LLM answer", temperature=0.2,
        )
    else:
        answer = text
    claims = check_answer(answer, tr)
    return {"answer": answer, "claims": claims, "summary": summarize(claims),
            "trace": tr.summary(), "cached": False}


def serve(kind, text, ask):
    k = key_of(kind, text)
    if k in RC:
        d = dict(RC[k])
        d["cached"], d["trace"] = True, cached_trace()
        return d
    try:
        d = run_pipeline(text, ask)
    except Exception as e:
        raise fail(e)
    RC[k] = d
    save_json(RC_FILE, RC)
    return d


@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/logo")
def logo():
    for name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp"):
        if os.path.exists(name):
            return FileResponse(name)
    raise HTTPException(404, "logo not found")


@app.get("/health")
def health():
    root = LLM_BASE_URL.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    return {
        "server": "ok", "gateway": GATEWAY_NAME, "gateway_url": LLM_BASE_URL,
        "gateway_ok": reachable(root), "model": MODEL,
        "tavily_key": bool(os.getenv("TAVILY_API_KEY")),
        "virtual_key": bool(os.getenv("BIFROST_VK")),
    }


@app.get("/config")
def config():
    return {"gateway": GATEWAY_NAME, "base_url": LLM_BASE_URL, "model": MODEL,
            "compare_models": COMPARE_MODELS}


@app.post("/check")
def check(q: Q):
    return serve("check", need_text(q), ask=False)


@app.post("/ask")
def ask(q: Q):
    return serve("ask", need_text(q), ask=True)


@app.post("/fix")
def fix(body: FixIn):
    try:
        return fix_answer(body.answer, body.claims, Trace())
    except Exception as e:
        raise fail(e)


@app.post("/history")
def history(body: HistIn):
    try:
        return fact_history(body.claim, body.search_query, Trace())
    except Exception as e:
        raise fail(e)


@app.post("/compare")
def compare(q: Q):
    text = need_text(q)
    k = key_of("compare", text)
    if k in RC:
        return {**RC[k], "cached": True}
    try:
        models = compare_models(text)
    except Exception as e:
        raise fail(e)
    d = {"question": text, "models": models, "cached": False}
    if any(not m["error"] for m in models):
        RC[k] = d
        save_json(RC_FILE, RC)
    return d


@app.get("/stats")
def stats():
    return load_stats()


# ---------------------------------------------------------------------------
# FreshCheck SIDECAR (works on Windows, no Go needed).
# An OpenAI-compatible endpoint: apps call THIS instead of Bifrost directly.
# It forwards to Bifrost (LLM_BASE_URL), then adds freshness info to the reply.
# This is the fallback if the real Go plugin cannot be built.
# ---------------------------------------------------------------------------
def fc_payload(d):
    s = d["summary"]
    return {
        "score": s["avg"], "fresh": s["fresh"], "stale": s["stale"], "unclear": s["unclear"],
        "claims": [
            {"claim": c["claim"], "verdict": c["verdict"], "score": c["freshness_score"],
             "correct_value": c.get("correct_value", ""), "source_url": c.get("source_url", ""),
             "evidence": c.get("evidence_quote", "")}
            for c in d["claims"]
        ],
    }


@app.post("/v1/chat/completions")
def sidecar_chat(body: dict = Body(...)):
    body = dict(body)
    body.pop("stream", None)          # streaming is not supported by the sidecar
    body.pop("stream_options", None)
    body.setdefault("model", MODEL)
    try:
        data = llm.chat.completions.create(**body).model_dump(mode="json")
    except Exception as e:
        raise HTTPException(502, "Gateway error: " + explain_error(e))
    headers = {}
    try:
        text = data["choices"][0]["message"].get("content")
        if isinstance(text, str) and len(text) >= FC_MIN_CHARS:
            fc = fc_payload(serve("check", text, ask=False))
            data["freshcheck"] = fc
            headers = {
                "x-freshcheck-score": str(fc["score"]),
                "x-freshcheck-fresh": str(fc["fresh"]),
                "x-freshcheck-stale": str(fc["stale"]),
                "x-freshcheck-unclear": str(fc["unclear"]),
                "x-freshcheck-status": "stale-found" if fc["stale"] else "ok",
            }
    except Exception:
        headers = {"x-freshcheck-status": "error"}
    return JSONResponse(content=data, headers=headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
