# Local test of FreshCheck's MCP endpoint (before adding it to Bifrost).
# Run:  py test_mcp.py      (FreshCheck must be running on port 8000)
import json
import requests

URL = "http://127.0.0.1:8000/mcp"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def rpc(method, params=None, mid=1, notify=False):
    msg = {"jsonrpc": "2.0", "method": method}
    if not notify:
        msg["id"] = mid
    if params is not None:
        msg["params"] = params
    return requests.post(URL, headers=H, data=json.dumps(msg), timeout=180)


print("1) initialize")
r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}})
print("  ", r.status_code, r.json()["result"]["serverInfo"], r.json()["result"]["protocolVersion"])

print("2) initialized notification")
r = rpc("notifications/initialized", notify=True)
print("  ", r.status_code, "(202 chahiye)")

print("3) tools/list")
r = rpc("tools/list", mid=2)
print("  ", r.status_code, [t["name"] for t in r.json()["result"]["tools"]])

print("4) tools/call (pehli baar 20-40 sec lag sakte hain)")
text = "Python 3.12 is the latest version of Python. Node.js 18 is the current LTS release."
r = rpc("tools/call", {"name": "check_freshness", "arguments": {"text": text}}, mid=3)
res = r.json()["result"]
print("  ", r.status_code, "isError =", res["isError"])
print(res["content"][0]["text"])
