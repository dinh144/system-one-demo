from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from backend.config import KEV_DEFAULT_TEMPERATURE, LLM_TEMPERATURE, OLLAMA_TAGS, OLLAMA_URL
from backend.decision import QUESTIONS, make_state
from backend.hardware import engine_availability, physical_core_count, torch_info


_ENGINE_LOCK = threading.RLock()
_INITIALIZE_LOCK = threading.RLock()
_ENGINE_STATES: dict[str, dict[str, Any]] = {}
_ENGINES: dict[str, "Engine"] = {}


@dataclass
class EngineResult:
    probabilities: dict[str, float]
    probability_sources: dict[str, str]
    gen_tokens: int | None
    device: str


class Engine:
    def __init__(self, engine_id: str) -> None:
        self.engine_id = engine_id
        self.device = "ollama" if engine_id.startswith("llm:") else _compute_device()
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.RLock()
        self._warmed = False

    def _load(self) -> None:
        with _INITIALIZE_LOCK:
            if self._model is not None:
                return
            core_count, _ = physical_core_count()
            import torch

            torch.set_num_threads(core_count)
            if self.engine_id == "laya":
                from laya import Router

                if self.device == "cpu":
                    os.environ.pop("LAYA_CPU_AMP", None)
                self._model = Router(preload=True, device=self.device)
                return
            if self.engine_id == "kev-0.8b":
                from kev.checkpoint import Checkpoint, LoadOptions

                checkpoint = Checkpoint("jaredpalmer/kev-0.8b")
                options = LoadOptions(dtype=torch.float32 if self.device == "cpu" else None)
                tokenizer, model = checkpoint.load(self.device, options)
                requested_temperature = os.environ.get("KEV_TEMPERATURE")
                if requested_temperature:
                    model.head.temperature = float(requested_temperature)
                self._tokenizer = tokenizer
                self._model = model
                _ENGINE_STATES[self.engine_id]["temperature"] = model.head.temperature
                return
            raise RuntimeError(f"Unsupported engine id: {self.engine_id}")

    def _call(self, observation: str, memories: list[str], candidate: str | None) -> EngineResult:
        if self.engine_id.startswith("llm:"):
            return self._call_ollama(observation, memories, candidate)
        self._load()
        state = make_state(observation, memories, candidate)
        if self.engine_id == "laya":
            output = self._model.predict(state, _laya_questions(), model="english")
            answers = output["answers"]
            probabilities = {key: float(answers[key]["noul"]) for key in QUESTIONS}
            return EngineResult(
                probabilities,
                {key: "model" for key in QUESTIONS},
                None,
                self.device,
            )
        from kev.api import SystemOneRequest, to_answers, to_record
        from kev.model import admit

        request = SystemOneRequest(state=state, questions=_kev_questions())
        record, metadata = to_record(request)
        encoded = admit(self._model, self._tokenizer, record)
        probabilities_batch, _ = self._model.probs_batch([encoded], [None], [False])
        output = to_answers(probabilities_batch[0], metadata)
        probabilities = {key: float(output[key]["noul"]) for key in QUESTIONS}
        return EngineResult(
            probabilities,
            {key: "model" for key in QUESTIONS},
            None,
            self.device,
        )

    def decide(self, observation: str, memories: list[str], candidate: str | None) -> tuple[EngineResult, float]:
        with self._lock:
            self._load_or_warm(observation, memories, candidate)
            start = time.perf_counter()
            result = self._call(observation, memories, candidate)
            elapsed = (time.perf_counter() - start) * 1000.0
            _ENGINE_STATES[self.engine_id]["last_latency_ms"] = elapsed
            return result, elapsed

    def _load_or_warm(self, observation: str, memories: list[str], candidate: str | None) -> None:
        if self._warmed:
            return
        try:
            self._call(observation, memories, candidate)
            self._warmed = True
        except Exception:
            raise

    def _call_ollama(self, observation: str, memories: list[str], candidate: str | None) -> EngineResult:
        state = make_state(observation, memories, candidate)
        prompt = (
            f"{state}\n\n"
            "Answer three yes/no questions about the latest conversation:\n"
            f"1. should_store: {QUESTIONS['should_store']}\n"
            f"2. redundant: {QUESTIONS['redundant']}\n"
            f"3. obsolete: {QUESTIONS['obsolete']}\n"
            'Reply with JSON only: {"should_store": true|false, "redundant": true|false, "obsolete": true|false}'
        )
        tag = self.engine_id.removeprefix("llm:")
        payload = {
            "model": tag,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": LLM_TEMPERATURE,
                "num_thread": physical_core_count()[0],
            },
            "logprobs": True,
            "top_logprobs": 5,
        }
        request = Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
        message = result.get("message") or {}
        content = message.get("content", "")
        parsed = json.loads(content)
        if not isinstance(parsed, dict) or any(type(parsed.get(key)) is not bool for key in QUESTIONS):
            raise ValueError("Ollama response must contain three JSON boolean fields")
        token_entries = result.get("logprobs") or message.get("logprobs") or []
        probabilities: dict[str, float] = {}
        sources: dict[str, str] = {}
        for key in QUESTIONS:
            value = parsed[key]
            probability, source = extract_logprob_probability(content, token_entries, key, value)
            probabilities[key] = probability
            sources[key] = source
        count = result.get("eval_count")
        return EngineResult(
            probabilities,
            sources,
            int(count) if count is not None else None,
            "ollama",
        )


def _laya_questions() -> dict[str, dict[str, str]]:
    return {key: {"type": "noul", "instructions": question} for key, question in QUESTIONS.items()}


def _kev_questions() -> dict[str, dict[str, Any]]:
    return _laya_questions()


def _compute_device() -> str:
    _, gpu = torch_info()
    return "cuda" if gpu and gpu.get("cuda") else "cpu"


def _byte_span(content: str, value: str) -> tuple[int, int] | None:
    match = re.search(rf'"{re.escape(value)}"\s*:\s*(true|false)\b', content)
    if match is None:
        return None
    start, end = match.span(1)
    return len(content[:start].encode("utf-8")), len(content[:end].encode("utf-8"))


def _token_at(entries: list[dict[str, Any]], byte_index: int) -> dict[str, Any] | None:
    cursor = 0
    for entry in entries:
        raw = entry.get("bytes")
        token_bytes = bytes(raw) if isinstance(raw, list) else str(entry.get("token", "")).encode("utf-8")
        next_cursor = cursor + len(token_bytes)
        if cursor <= byte_index < next_cursor:
            return entry
        cursor = next_cursor
    return None


def _top_boolean_logprobs(entry: dict[str, Any]) -> tuple[float | None, float | None]:
    candidates: dict[str, list[tuple[tuple[str, str], float]]] = {"true": [], "false": []}
    sampled_match = re.fullmatch(r"(\s*)(true|false)(\s*)", str(entry.get("token", "")))
    sampled_style = (sampled_match.group(1), sampled_match.group(3)) if sampled_match else None
    for candidate in entry.get("top_logprobs") or []:
        match = re.fullmatch(r"(\s*)(true|false)(\s*)", str(candidate.get("token", "")))
        if match is not None:
            style = (match.group(1), match.group(3))
            candidates[match.group(2)].append((style, float(candidate["logprob"])))

    def select(value: str) -> float | None:
        choices = candidates[value]
        matching_style = [logprob for style, logprob in choices if style == sampled_style]
        if matching_style:
            return max(matching_style)
        if choices:
            return max(logprob for _, logprob in choices)
        return None

    return select("true"), select("false")


def extract_logprob_probability(
    content: str,
    entries: list[dict[str, Any]],
    field: str,
    sampled_value: bool,
) -> tuple[float, str]:
    """Read binary probability from the token spanning a JSON boolean, with a hard-label fallback."""
    span = _byte_span(content, field)
    entry = _token_at(entries, span[0]) if span and entries else None
    if entry is not None:
        lp_true, lp_false = _top_boolean_logprobs(entry)
        if lp_true is not None and lp_false is not None:
            maximum = max(lp_true, lp_false)
            e_true = math.exp(lp_true - maximum)
            e_false = math.exp(lp_false - maximum)
            return e_true / (e_true + e_false), "logprob"

        sampled = str(entry.get("token", "")).strip()
        if sampled in {"true", "false"} and "logprob" in entry:
            sampled_probability = min(1.0, max(0.0, math.exp(float(entry["logprob"]))))
            return (sampled_probability if sampled == "true" else 1.0 - sampled_probability), "logprob"

    return (1.0 if sampled_value else 0.0), "hard_label"


_AVAILABILITY_TTL_SECONDS = 15.0
_AVAILABILITY_LOCK = threading.Lock()
_AVAILABILITY_CACHE: dict[str, Any] = {"at": 0.0, "value": None}


def _base_availability() -> dict[str, tuple[str, str | None]]:
    # The check talks to Ollama and the model caches (0.3 to 1 s). It ran several times per engine per turn, which
    # added about 2 s of wall time per engine outside the measured latency, so keep the answer for a few seconds.
    now = time.monotonic()
    with _AVAILABILITY_LOCK:
        cached = _AVAILABILITY_CACHE["value"]
        if cached is not None and now - _AVAILABILITY_CACHE["at"] < _AVAILABILITY_TTL_SECONDS:
            return dict(cached)
    try:
        value = engine_availability()
    except Exception as exc:
        return {engine: ("unavailable", str(exc)) for engine in ["laya", "kev-0.8b", *(f"llm:{t}" for t in OLLAMA_TAGS)]}
    with _AVAILABILITY_LOCK:
        _AVAILABILITY_CACHE["value"] = dict(value)
        _AVAILABILITY_CACHE["at"] = now
    return dict(value)


def model_availability() -> dict[str, tuple[str, str | None]]:
    base = _base_availability()
    with _ENGINE_LOCK:
        for engine, state in _ENGINE_STATES.items():
            if state.get("status") == "unavailable":
                base[engine] = ("unavailable", state.get("reason") or "Engine failed")
            elif state.get("status") == "loading":
                base[engine] = ("loading", None)
    return base


def run_engine(engine_id: str, observation: str, memories: list[str], candidate: str | None) -> tuple[EngineResult, float]:
    current = _base_availability()
    with _ENGINE_LOCK:
        runtime_state = _ENGINE_STATES.get(engine_id, {})
    if runtime_state.get("status") == "unavailable":
        status, reason = "unavailable", runtime_state.get("reason")
    else:
        status, reason = current.get(engine_id, ("unavailable", "Unknown engine"))
    if status != "ready":
        raise RuntimeError(reason or "Engine is unavailable")
    with _ENGINE_LOCK:
        engine = _ENGINES.get(engine_id)
        if engine is None:
            engine = Engine(engine_id)
            _ENGINES[engine_id] = engine
        _ENGINE_STATES[engine_id] = {"status": "loading"}
    try:
        result, elapsed = engine.decide(observation, memories, candidate)
        with _ENGINE_LOCK:
            _ENGINE_STATES[engine_id] = {"status": "ready", "last_latency_ms": elapsed}
        return result, elapsed
    except Exception as exc:
        with _ENGINE_LOCK:
            _ENGINE_STATES[engine_id] = {"status": "unavailable", "reason": str(exc).splitlines()[0]}
        raise


def warm_engine(engine_id: str, observation: str, memories: list[str], candidate: str | None) -> bool:
    status, reason = _base_availability().get(engine_id, ("unavailable", "Unknown engine"))
    with _ENGINE_LOCK:
        runtime_state = _ENGINE_STATES.get(engine_id, {})
    if runtime_state.get("status") == "unavailable":
        status, reason = "unavailable", runtime_state.get("reason")
    if status != "ready":
        raise RuntimeError(reason or "Engine is unavailable")
    with _ENGINE_LOCK:
        engine = _ENGINES.get(engine_id)
        if engine is None:
            engine = Engine(engine_id)
            _ENGINES[engine_id] = engine
        if engine._warmed:
            return False
        _ENGINE_STATES[engine_id] = {"status": "loading"}
    try:
        performed = False
        with engine._lock:
            if not engine._warmed:
                engine._call(observation, memories, candidate)
                engine._warmed = True
                performed = True
        with _ENGINE_LOCK:
            _ENGINE_STATES[engine_id] = {"status": "ready"}
        return performed
    except Exception as exc:
        with _ENGINE_LOCK:
            _ENGINE_STATES[engine_id] = {"status": "unavailable", "reason": str(exc).splitlines()[0]}
        raise


def initialize_unreported_warmup(engine_id: str, observation: str, memories: list[str], candidate: str | None) -> None:
    """Compatibility entry point for callers that need an unreported first call."""
    engine = _ENGINES.get(engine_id)
    if engine is None:
        run_engine(engine_id, observation, memories, candidate)
        return
    if not engine._warmed:
        engine.decide(observation, memories, candidate)


def engine_temperature(engine_id: str) -> float | None:
    state = _ENGINE_STATES.get(engine_id, {})
    if engine_id == "kev-0.8b":
        return float(state.get("temperature", KEV_DEFAULT_TEMPERATURE))
    return state.get("temperature")
