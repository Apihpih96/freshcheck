"""FreshCheck accuracy test: ~12 jawab-pata-wale claims par check karta hai ki
system sahi verdict deta hai ya nahi. Result `eval_report.md` mein save hota hai
(README mein "tested on N claims, X% correct" likhne ke kaam aata hai).

Chalao:   py eval.py          (server + Bifrost chalu hone chahiye)
Credits:  lagbhag 2-3 Tavily credits per case (total ~30-40).

DHYAN: expected verdicts duniya ki 2026 ki sthiti ke hisaab se hain.
Agar koi fact badal gaya ho to us line ka `expect` khud badal do.
  stale = purana hona chahiye | fresh = sahi hona chahiye | none = koi stale nahi aana chahiye
"""
import sys, time, datetime
import requests

BASE = "http://127.0.0.1:8000"

CASES = [
    # (label, text, expect)
    ("Python version",   "Python 3.12 is the latest version of Python.", "stale"),
    ("Twitter CEO",      "The CEO of Twitter is Parag Agrawal.", "stale"),
    ("India: IPC",       "The Indian Penal Code (IPC) is the main criminal law of India.", "stale"),
    ("India: CrPC",      "The Code of Criminal Procedure (CrPC) governs criminal procedure in India.", "stale"),
    ("India: GST slabs", "India's GST has four main slabs: 5%, 12%, 18% and 28%.", "stale"),
    ("iPhone",           "The latest iPhone is the iPhone 14.", "stale"),
    ("ChatGPT model",    "ChatGPT runs on GPT-3.5.", "stale"),
    ("Node.js LTS",      "Node.js 18 is the current LTS release.", "stale"),
    ("Windows",          "Windows 10 is the latest version of Windows.", "stale"),
    ("Anthropic CEO",    "Anthropic's CEO is Dario Amodei.", "fresh"),
    ("Microsoft CEO",    "Satya Nadella is the CEO of Microsoft.", "fresh"),
    ("Timeless fact",    "The Eiffel Tower is in Paris, France.", "none"),
]


def verdicts(d):
    return [c["verdict"] for c in d["claims"]]


def passed(expect, v):
    if expect == "stale":
        return "stale" in v
    if expect == "fresh":
        return "stale" not in v and "fresh" in v
    return "stale" not in v  # none


def main():
    try:
        h = requests.get(BASE + "/health", timeout=10).json()
    except Exception:
        print("FreshCheck server nahi mila. Pehle: py -m uvicorn server:app --reload")
        sys.exit(1)
    if not h["gateway_ok"]:
        print("Gateway offline hai. Bifrost chalao.")
        sys.exit(1)

    rows, ok = [], 0
    print(f"{'Case':<18} {'Expect':<7} {'Got':<28} Result")
    print("-" * 66)
    for label, text, expect in CASES:
        try:
            r = requests.post(BASE + "/check", json={"text": text}, timeout=300)
            if r.status_code != 200:
                raise RuntimeError(r.json().get("detail", r.text)[:80])
            v = verdicts(r.json())
            good = passed(expect, v)
            got = ",".join(v) or "(no claims)"
        except Exception as e:
            good, got = False, "ERROR " + str(e)[:40]
        ok += good
        rows.append((label, expect, got, good, text))
        print(f"{label:<18} {expect:<7} {got:<28} {'PASS' if good else 'FAIL'}")
        time.sleep(0.5)

    pct = round(100 * ok / len(CASES))
    print("-" * 66)
    print(f"Accuracy: {ok}/{len(CASES)} = {pct}%")

    with open("eval_report.md", "w", encoding="utf-8") as f:
        f.write(f"# FreshCheck evaluation\n\nDate: {datetime.date.today()}  |  Gateway: {h['gateway']}  |  Model: {h['model']}\n\n")
        f.write(f"**{ok}/{len(CASES)} cases correct ({pct}%)**\n\n")
        f.write("| Case | Expected | Got | Result |\n|---|---|---|---|\n")
        for label, expect, got, good, text in rows:
            f.write(f"| {label} | {expect} | {got} | {'PASS' if good else 'FAIL'} |\n")
        f.write("\nCases are single-sentence claims with known answers. `stale` = must be flagged outdated, "
                "`fresh` = must be confirmed current, `none` = must not be flagged.\n")
    print("Report saved: eval_report.md")
    print("FAIL aaye to us sentence ko website par chalake dekho, aur mujhe bhejo.")


if __name__ == "__main__":
    main()
