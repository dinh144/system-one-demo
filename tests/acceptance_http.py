from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8000"
ENGINES = ["laya", "kev-0.8b", "llm:qwen2.5:0.5b"]


def _get(path: str):
    with urlopen(f"{BASE}{path}", timeout=30) as response:
        assert response.status == 200, (path, response.status)
        return json.loads(response.read())


def _post(path: str, payload: dict):
    request = Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return urlopen(request, timeout=900)


def _read_events(response) -> list[tuple[str, dict, float]]:
    started = time.perf_counter()
    events = []
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
            events.append((event_name, json.loads("\n".join(data_lines)), time.perf_counter() - started))
            event_name, data_lines = None, []
    return events


def main() -> int:
    health = _get("/api/health")
    assert health == {"schema": 1, "ok": True, "mock": False}
    hardware = _get("/api/hardware")
    assert {"schema", "os", "cpu", "ram_gb", "gpu", "python", "torch", "ollama"} <= hardware.keys()
    models = _get("/api/models")
    assert isinstance(models, list)
    assert all({"id", "label", "params", "kind", "device", "status", "reason"} <= row.keys() for row in models)
    scenario = _get("/api/scenario")
    assert scenario["schema"] == 1 and len(scenario["turns"]) == 10
    cases = _get("/api/cases")
    assert cases["schema"] == 1 and cases["n"] == len(cases["cases"]) == 30
    print("API contract PASS: health, hardware, models, scenario (10 turns), cases (30)")

    session = _post("/api/session", {"engines": ENGINES})
    with session:
        session_id = json.loads(session.read())["session_id"]
    response = _post(
        f"/api/session/{session_id}/turn",
        {"text": "I moved to Berlin and now prefer quiet cafes."},
    )
    with response:
        assert response.headers.get_content_type() == "text/event-stream"
        events = _read_events(response)
    names = [payload.get("engine") for name, payload, _ in events if name == "decision"]
    errors = [payload for name, payload, _ in events if name == "engine_error"]
    assert not errors, errors
    assert len(names) == len(ENGINES) and set(names) == set(ENGINES), names
    decisions = {payload["engine"]: payload for name, payload, _ in events if name == "decision"}
    assert events[0][0] == "turn" and events[-1][0] == "done"
    assert all(decision["source"] == "live" and decision["latency_ms"] >= 0 for decision in decisions.values())
    # Default execution mode is sequential (SYSTEM_ONE_ENGINE_WORKERS=1): engines run in session order and each
    # engine_start follows the previous decision. With SYSTEM_ONE_ENGINE_WORKERS>1 a faster engine can finish first.
    workers = int(os.environ.get("SYSTEM_ONE_ENGINE_WORKERS", "1"))
    sequence = [(name, payload.get("engine")) for name, payload, _ in events if name in ("engine_start", "decision")]
    starts = [engine for name, engine in sequence if name == "engine_start"]
    assert set(starts) == set(ENGINES) and len(starts) == len(ENGINES), starts
    if workers == 1:
        assert names == ENGINES, (names, ENGINES)
        expected = []
        for engine in ENGINES:
            expected += [("engine_start", engine), ("decision", engine)]
        assert sequence == expected, sequence
    else:
        fastest = min(ENGINES, key=lambda engine: decisions[engine]["latency_ms"])
        slowest = max(ENGINES, key=lambda engine: decisions[engine]["latency_ms"])
        assert names.index(fastest) < names.index(slowest), (names, fastest, slowest)
    print("SSE PASS: engine_start and one measured decision per engine; order=" + ",".join(names) + f" (workers={workers})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
