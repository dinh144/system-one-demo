from __future__ import annotations

import asyncio
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.config import ENGINE_WORKERS
from typing import Any

from backend.decision import classify
from backend.engines import model_availability, run_engine, warm_engine


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LABEL_NOTE = "nhãn tham chiếu (n = 30), chưa kiểm định độc lập"
ACCURACY_CAVEAT = "Độ chính xác của redundant và obsolete không có ý nghĩa thống kê do số nhãn dương quá nhỏ."
BENCH_EXECUTOR = ThreadPoolExecutor(max_workers=ENGINE_WORKERS, thread_name_prefix="benchmark-engine")


def load_cases() -> list[dict[str, Any]]:
    return json.loads((DATA / "cases.json").read_text(encoding="utf-8"))["cases"]


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    location = (len(ordered) - 1) * quantile
    lower = int(location)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = location - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _warm_one(engine: str, case: dict[str, Any]) -> bool:
    return warm_engine(engine, case["observation"], case["recent_memories"], case["candidate"])


def _warm_additional(engine: str, case: dict[str, Any]) -> None:
    run_engine(engine, case["observation"], case["recent_memories"], case["candidate"])


def _timed_case(engine: str, case: dict[str, Any]) -> tuple[float, dict[str, float], dict[str, bool]]:
    result, latency = run_engine(engine, case["observation"], case["recent_memories"], case["candidate"])
    return latency, result.probabilities, case["reference"]


def _event(name: str, body: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(body, ensure_ascii=False, separators=(',', ':'))}\n\n"


def benchmark_stream(engines: list[str], case_ids: list[str] | None, warmup: int):
    all_cases = load_cases()
    selected = all_cases if case_ids is None else [case for case in all_cases if case["id"] in set(case_ids)]

    async def stream():
        if not selected:
            yield _event("result", {"schema": 1, "results": []})
            return
        states = model_availability()
        active = [engine for engine in engines if states.get(engine, ("unavailable", "Unknown engine"))[0] == "ready"]
        errors = {
            engine: states.get(engine, ("unavailable", "Unknown engine"))[1] or "Engine is unavailable"
            for engine in engines
            if engine not in active
        }
        loop = asyncio.get_running_loop()
        total = len(engines) * len(selected)
        completed = 0

        warm_futures = {
            loop.run_in_executor(BENCH_EXECUTOR, _warm_one, engine, selected[0]): engine
            for engine in active
        }
        warm_pending = set(warm_futures)
        initial_warmup: dict[str, bool] = {}
        while warm_pending:
            finished, warm_pending = await asyncio.wait(warm_pending, return_when=asyncio.FIRST_COMPLETED)
            for future in finished:
                engine = warm_futures[future]
                try:
                    initial_warmup[engine] = future.result()
                    yield _event("progress", {
                        "phase": "warmup",
                        "engine": engine,
                        "completed": 0,
                        "total": total,
                    })
                except Exception as exc:
                    errors[engine] = str(exc).splitlines()[0]
                    active.remove(engine)

        additional_counts = {
            engine: max(0, warmup - int(initial_warmup.get(engine, False)))
            for engine in active
        }
        for warm_round in range(max(additional_counts.values(), default=0)):
            extra_warm = {
                loop.run_in_executor(BENCH_EXECUTOR, _warm_additional, engine, selected[0]): engine
                for engine in active
                if additional_counts[engine] > warm_round
            }
            pending_warm = set(extra_warm)
            while pending_warm:
                finished, pending_warm = await asyncio.wait(pending_warm, return_when=asyncio.FIRST_COMPLETED)
                for future in finished:
                    engine = extra_warm[future]
                    try:
                        future.result()
                        yield _event("progress", {
                            "phase": "warmup",
                            "engine": engine,
                            "completed": 0,
                            "total": total,
                        })
                    except Exception as exc:
                        errors[engine] = str(exc).splitlines()[0]
                        if engine in active:
                            active.remove(engine)

        results: dict[str, list[tuple[float, dict[str, float], dict[str, bool]]]] = {engine: [] for engine in active}
        timed_futures = {
            loop.run_in_executor(BENCH_EXECUTOR, _timed_case, engine, case): (engine, case)
            for engine in active
            for case in selected
        }
        pending_timed = set(timed_futures)
        while pending_timed:
            finished, pending_timed = await asyncio.wait(pending_timed, return_when=asyncio.FIRST_COMPLETED)
            for future in finished:
                engine, case = timed_futures[future]
                completed += 1
                try:
                    results[engine].append(future.result())
                    progress_status = "complete"
                except Exception as exc:
                    errors[engine] = str(exc).splitlines()[0]
                    progress_status = "unavailable"
                yield _event("progress", {
                    "phase": "measure",
                    "engine": engine,
                    "case_id": case["id"],
                    "status": progress_status,
                    "completed": completed,
                    "total": total,
                })

        output: dict[str, Any] = {}
        for engine in engines:
            samples = results.get(engine, [])
            if errors.get(engine) or not samples:
                output[engine] = {"status": "unavailable", "reason": errors.get(engine, "No measurements completed")}
                continue
            latency_values = [sample[0] for sample in samples]
            comparisons = [
                (probabilities, references)
                for _, probabilities, references in samples
            ]
            all_correct = 0
            all_count = 0
            by_question: dict[str, dict[str, Any]] = {}
            for question in ("should_store", "redundant", "obsolete"):
                correct = 0
                positives = sum(bool(case["reference"][question]) for case in selected)
                for probabilities, references in comparisons:
                    predicted = classify(probabilities[question])
                    expected = "yes" if references[question] else "no"
                    correct += predicted == expected
                all_correct += correct
                all_count += len(comparisons)
                note = LABEL_NOTE
                if question in {"redundant", "obsolete"}:
                    note = f"{LABEL_NOTE}; {ACCURACY_CAVEAT}"
                by_question[question] = {
                    "value": correct / len(comparisons),
                    "n": len(comparisons),
                    "positives": positives,
                    "note": note,
                }
            output[engine] = {
                "p50_ms": round(statistics.median(latency_values), 3),
                "p95_ms": round(_percentile(latency_values, 0.95), 3),
                "n": len(latency_values),
                "accuracy": {
                    "value": all_correct / all_count,
                    "n": all_count,
                    "note": LABEL_NOTE,
                },
                "accuracy_by_question": by_question,
            }
        yield _event("result", {"schema": 1, "results": output})

    return stream()
