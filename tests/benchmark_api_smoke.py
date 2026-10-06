from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8000"
ENGINES = [
    "laya",
    "kev-0.8b",
    "llm:qwen2.5:0.5b",
    "llm:qwen2.5:1.5b",
    "llm:qwen2.5:3b",
    "llm:qwen2.5:7b",
]


def main() -> int:
    with urlopen(f"{BASE}/api/cases", timeout=30) as response:
        case_id = json.loads(response.read())["cases"][0]["id"]
    request = Request(
        f"{BASE}/api/benchmark",
        data=json.dumps({"engines": ENGINES, "case_ids": [case_id], "warmup": 3}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    events = []
    with urlopen(request, timeout=1800) as response:
        assert response.headers.get_content_type() == "text/event-stream"
        event_name = None
        data_lines = []
        while True:
            line = response.readline()
            if not line:
                break
            line = line.decode("utf-8").rstrip("\r\n")
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])
            elif not line and event_name:
                events.append((event_name, json.loads("\n".join(data_lines))))
                event_name, data_lines = None, []
    results = [payload["results"] for name, payload in events if name == "result"]
    assert len(results) == 1
    assert set(results[0]) == set(ENGINES)
    assert all(results[0][engine].get("n") == 1 for engine in ENGINES)
    assert all(isinstance(results[0][engine].get("accuracy"), dict) for engine in ENGINES)
    warmups = sum(payload.get("phase") == "warmup" for _, payload in events)
    measurements = sum(payload.get("phase") == "measure" for _, payload in events)
    assert measurements == len(ENGINES), (measurements, events)
    print(f"PASS: case={case_id}; warmup_events={warmups}; measured_events={measurements}; engines={len(ENGINES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
