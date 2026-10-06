from __future__ import annotations

import concurrent.futures
from pathlib import Path

from backend.benchmark import load_cases
from backend.engines import model_availability, run_engine, warm_engine


def _test_engine(engine: str, cases: list[dict]) -> tuple[str, int, list[str]]:
    errors: list[str] = []
    completed = 0
    try:
        first = cases[0]
        warm_engine(engine, first["observation"], first["recent_memories"], first["candidate"])
    except Exception as exc:
        errors.append(str(exc).splitlines()[0])
        return engine, completed, errors
    for case in cases:
        try:
            result, _ = run_engine(engine, case["observation"], case["recent_memories"], case["candidate"])
            if set(result.probabilities) != {"should_store", "redundant", "obsolete"}:
                raise ValueError("missing question probabilities")
            if any(not 0 <= probability <= 1 for probability in result.probabilities.values()):
                raise ValueError("probability outside [0, 1]")
            completed += 1
        except Exception as exc:
            errors.append(str(exc).splitlines()[0])
    return engine, completed, errors


def run_selftest() -> int:
    cases = load_cases()[:3]
    availability = model_availability()
    ready = [engine for engine, (status, _) in availability.items() if status == "ready"]
    if not ready:
        print("SELFTEST FAIL: no ready engines")
        for engine, (status, reason) in availability.items():
            print(f"{engine}: {status}: {reason or 'unavailable'}")
        return 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ready)) as executor:
        futures = [executor.submit(_test_engine, engine, cases) for engine in ready]
        results = [future.result() for future in futures]
    failed = False
    for engine, completed, errors in sorted(results):
        status = "PASS" if completed == len(cases) and not errors else "FAIL"
        failed |= status != "PASS"
        print(f"{engine}: {status} ({completed}/{len(cases)} cases)")
        for error in errors:
            print(f"  {error}")
    for engine, (status, reason) in availability.items():
        if status != "ready":
            print(f"{engine}: NOT RUN ({reason or status})")
    return 1 if failed else 0
