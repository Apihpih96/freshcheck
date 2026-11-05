"""
Minimal MCP (Model Context Protocol) server for FreshCheck.

It speaks the "Streamable HTTP" transport in its simplest form: the client POSTs JSON-RPC
messages to /mcp and we answer with plain JSON. This lets the Bifrost MCP Gateway
register FreshCheck as an MCP server, so any model behind Bifrost can call the
`check_freshness` tool to verify its own facts against the live web.

No extra libraries needed. `handle_rpc` is a pure function so it is easy to test.
"""

SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

TOOL = {
    "name": "check_freshness",
    "description": (
        "Checks an answer or a statement for facts that may have gone out of date "
        "(prices, versions, office-holders, laws, releases). Each fact is re-verified "
        "against live web sources. Returns a freshness score (0-100) and, for every "
        "claim, a verdict (fresh / stale / unclear), the correct current value and a source link. "
        "Call it before stating time-sensitive facts, and correct any claim marked STALE."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The answer or statement to verify (a few sentences).",
            }
        },
        "required": ["text"],
    },
}

SERVER_INFO = {"name": "freshcheck", "version": "1.0.0"}
INSTRUCTIONS = (
    "FreshCheck verifies time-sensitive facts against live web sources. "
    "Use check_freshness on any answer that contains prices, versions, leaders or laws."
)


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def format_result(fc):
    """Turn FreshCheck's payload into a short text the model can read."""
    claims = fc.get("claims", [])
    if not claims:
        return "No time-sensitive facts were found in this text, so there is nothing to verify."
    lines = [
        "Freshness score: %s/100 (%s fresh, %s stale, %s unclear)"
        % (fc.get("score"), fc.get("fresh"), fc.get("stale"), fc.get("unclear"))
    ]
    for c in claims:
        verdict = str(c.get("verdict", "")).upper()
        line = "- %s: %s" % (verdict, c.get("claim", ""))
        if verdict != "FRESH" and c.get("correct_value"):
            line += " -> Correct: %s" % c["correct_value"]
        if c.get("source_url"):
            line += " (source: %s)" % c["source_url"]
        lines.append(line)
    if fc.get("stale"):
        lines.append("Rewrite the answer using the corrected values above.")
    return "\n".join(lines)


def handle_rpc(msg, check_fn):
    """
    Handle ONE JSON-RPC message.
    check_fn(text) -> FreshCheck payload dict (score, fresh, stale, unclear, claims).
    Returns a response dict, or None when no response is needed (notifications).
    """
    if not isinstance(msg, dict):
        return _err(None, -32600, "Invalid Request")

    method = msg.get("method")
    mid = msg.get("id")

    # Messages without a method are responses from the client; notifications have no id.
    if method is None or "id" not in msg:
        return None

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _ok(mid, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        })

    if method == "ping":
        return _ok(mid, {})

    if method == "tools/list":
        return _ok(mid, {"tools": [TOOL]})

    if method == "tools/call":
        params = msg.get("params") or {}
        if params.get("name") != TOOL["name"]:
            return _err(mid, -32602, "Unknown tool: %s" % params.get("name"))
        text = ((params.get("arguments") or {}).get("text") or "").strip()
        if not text:
            return _ok(mid, {
                "content": [{"type": "text", "text": "Error: 'text' is required."}],
                "isError": True,
            })
        try:
            out = format_result(check_fn(text))
            return _ok(mid, {"content": [{"type": "text", "text": out}], "isError": False})
        except Exception as e:  # tool errors are reported inside the result, not as protocol errors
            return _ok(mid, {
                "content": [{"type": "text", "text": "FreshCheck could not verify this text: %s" % e}],
                "isError": True,
            })

    return _err(mid, -32601, "Method not found: %s" % method)
