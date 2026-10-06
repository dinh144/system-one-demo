from __future__ import annotations

import asyncio
import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from backend.config import ENGINE_WORKERS
from backend.decision import action_for, scored_answers
from backend.engines import model_availability, run_engine, warm_engine


ENGINE_EXECUTOR = ThreadPoolExecutor(max_workers=ENGINE_WORKERS, thread_name_prefix="model-engine")
VALID_ENGINE_IDS = {
    "laya",
    "kev-0.8b",
    "llm:qwen2.5:0.5b",
    "llm:qwen2.5:1.5b",
    "llm:qwen2.5:3b",
    "llm:qwen2.5:7b",
}
_WORD = re.compile(r"[A-Za-z]{4,}")


@dataclass
class MemoryItem:
    id: str
    text: str
    status: str = "active"

    def response(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text, "status": self.status}


@dataclass
class Session:
    session_id: str
    engines: list[str]
    stores: dict[str, list[MemoryItem]] = field(default_factory=dict)
    turn_index: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)


MAX_SESSIONS = 20


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()

    def create(self, engines: list[str]) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            engines=engines,
            stores={engine: [] for engine in engines},
        )
        with self.lock:
            self.sessions[session.session_id] = session
            while len(self.sessions) > MAX_SESSIONS:
                self.sessions.pop(next(iter(self.sessions)))  # drop the oldest session
        return session

    def get(self, session_id: str) -> Session | None:
        with self.lock:
            return self.sessions.get(session_id)

    def reset(self, session: Session) -> None:
        with session.lock:
            session.stores = {engine: [] for engine in session.engines}
            session.turn_index = 0


SESSIONS = SessionStore()


def _prefixes(text: str) -> set[str]:
    return {match.group(0).lower()[:4] for match in _WORD.finditer(text)}


def _candidate(text: str, store: list[MemoryItem]) -> MemoryItem | None:
    observation_words = _prefixes(text)
    if not observation_words:
        return None
    selected: MemoryItem | None = None
    best_score = 0
    for memory in reversed(store):
        if memory.status != "active":
            continue
        score = len(observation_words & _prefixes(memory.text))
        if score > best_score:
            selected, best_score = memory, score
    return selected


def _apply_memory_action(session: Session, engine: str, action: str, observation: str, candidate: MemoryItem | None) -> None:
    store = session.stores[engine]
    if action == "add":
        store.append(MemoryItem(str(uuid.uuid4()), observation))
    elif action == "replace":
        if candidate is not None:
            candidate.status = "replaced"
        store.append(MemoryItem(str(uuid.uuid4()), observation))


def _event(name: str, body: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(body, ensure_ascii=False, separators=(',', ':'))}\n\n"


def build_turn_stream(session: Session, text: str):
    with session.lock:
        session.turn_index += 1
        turn_index = session.turn_index
        snapshots: dict[str, tuple[list[str], MemoryItem | None]] = {}
        for engine in session.engines:
            store = session.stores[engine]
            recent = [item for item in store if item.status == "active"][-3:]
            candidate = _candidate(text, recent)
            snapshots[engine] = ([item.text for item in recent], candidate)

    async def stream():
        yield _event("turn", {"i": turn_index, "text": text})
        loop = asyncio.get_running_loop()
        warm_futures = {
            loop.run_in_executor(
                ENGINE_EXECUTOR,
                warm_engine,
                engine,
                text,
                *snapshots[engine],
            ): engine
            for engine in session.engines
        }
        warm_pending = set(warm_futures)
        warm_errors: dict[str, str] = {}
        while warm_pending:
            completed, warm_pending = await asyncio.wait(warm_pending, return_when=asyncio.FIRST_COMPLETED)
            for future in completed:
                engine = warm_futures[future]
                try:
                    future.result()
                except Exception as exc:
                    message = str(exc).splitlines()[0]
                    warm_errors[engine] = message
                    yield _event("engine_error", {"engine": engine, "message": message})

        futures = {
            loop.run_in_executor(
                ENGINE_EXECUTOR,
                _run_for_session,
                session,
                engine,
                turn_index,
                text,
                *snapshots[engine],
            ): engine
            for engine in session.engines
            if engine not in warm_errors
        }
        pending = set(futures)
        order = [futures[future] for future in futures]
        started = 0
        if ENGINE_WORKERS == 1:
            # One engine at a time: tell the UI when each one actually starts, so its clock excludes the wait.
            if order:
                yield _event("engine_start", {"engine": order[0]})
                started = 1
        else:
            for engine in order:
                yield _event("engine_start", {"engine": engine})
            started = len(order)
        while pending:
            completed, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for future in completed:
                engine = futures[future]
                try:
                    event_name, payload = future.result()
                    yield _event(event_name, payload)
                except Exception as exc:
                    yield _event("engine_error", {"engine": engine, "message": str(exc).splitlines()[0]})
                if started < len(order):
                    yield _event("engine_start", {"engine": order[started]})
                    started += 1
        yield _event("done", {})

    return stream()


def _run_for_session(
    session: Session,
    engine: str,
    turn_index: int,
    observation: str,
    memories: list[str],
    candidate: MemoryItem | None,
) -> tuple[str, dict[str, Any]]:
    if model_availability().get(engine, ("unavailable", "Unknown engine"))[0] != "ready":
        status, reason = model_availability().get(engine, ("unavailable", "Unknown engine"))
        raise RuntimeError(reason or status)
    result, latency = run_engine(engine, observation, memories, candidate.text if candidate else None)
    answers = scored_answers(result.probabilities, result.probability_sources)
    action = action_for(answers)
    with session.lock:
        _apply_memory_action(session, engine, action, observation, candidate)
        memory = [item.response() for item in session.stores[engine]]
    return "decision", {
        "engine": engine,
        "source": "live",
        "latency_ms": latency,
        "device": result.device,
        "answers": answers,
        "action": action,
        "memory": memory,
        "gen_tokens": result.gen_tokens,
    }
