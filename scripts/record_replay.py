"""Record a real run of the 10-turn scenario into data/replay.json.

Needs a running backend (python -m demo run). Every latency in the output is measured by the backend during this
run, on the machine that runs the backend. Pass --recorded-on with an honest machine description; the UI shows it
in the replay banner.

Usage:
  python scripts/record_replay.py --recorded-on "ThinkPad X1 Carbon Gen 9 (i7-1185G7, CPU only)"
  python scripts/record_replay.py --base http://127.0.0.1:8001 --engines laya,kev-0.8b,llm:qwen2.5:0.5b --recorded-on "..."
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=600)


def read_events(resp):
    event, data = None, []
    for raw in resp:
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif line == "":
            if event is not None:
                yield event, json.loads("\n".join(data)) if data else {}
            event, data = None, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--engines", default="laya,kev-0.8b,llm:qwen2.5:0.5b")
    ap.add_argument("--recorded-on", required=True)
    args = ap.parse_args()
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    scenario = json.loads((ROOT / "data" / "scenario.json").read_text(encoding="utf-8"))
    session = json.load(post(f"{args.base}/api/session", {"engines": engines}))["session_id"]
    turns = []
    for sc in scenario["turns"]:
        decisions, errors = [], []
        started = time.time()
        for event, payload in read_events(post(f"{args.base}/api/session/{session}/turn", {"text": sc["text"]})):
            if event == "decision":
                payload["source"] = "replay"
                decisions.append(payload)
            elif event == "engine_error":
                errors.append(payload)
        print(f"turn {sc['i']}: {len(decisions)} decisions, {len(errors)} errors, {time.time() - started:.1f}s", flush=True)
        if errors:
            print("engine errors:", errors, file=sys.stderr)
        turns.append({"turn": {"i": sc["i"], "text": sc["text"]}, "decisions": decisions, "errors": errors})

    out = {
        "schema": 1,
        "source": "replay",
        "recorded_on": args.recorded_on,
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engines": engines,
        "turns": turns,
    }
    (ROOT / "data" / "replay.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote data/replay.json")


if __name__ == "__main__":
    main()
