import os, requests
from dotenv import load_dotenv

load_dotenv()
VK = os.getenv("BIFROST_VK", "")
H = {"x-bf-vk": VK} if VK else {}

MSG = [{"role": "user", "content": "Python ka latest version kya hai aur Claude Opus ka input price kitna hai?"}]

print("== TEST 1: seedha Bifrost ==")
r = requests.post("http://localhost:8080/v1/chat/completions", headers=H,
                  json={"model": "groq/openai/gpt-oss-120b", "messages": MSG}, timeout=120)
print(r.status_code)
print(r.text[:400])

print("\n== TEST 2: FreshCheck sidecar (Bifrost ke through) ==")
r = requests.post("http://127.0.0.1:8000/v1/chat/completions",
                  json={"model": "groq/openai/gpt-oss-120b", "messages": MSG}, timeout=180)
print(r.status_code, r.headers.get("x-freshcheck-status"), r.headers.get("x-freshcheck-score"))
print(r.text[:600])