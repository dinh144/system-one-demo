from __future__ import annotations

import json
import threading
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import OLLAMA_TAGS
from backend.engines import engine_temperature, model_availability
from backend.hardware import hardware_report
from backend.sessions import SESSIONS, VALID_ENGINE_IDS, build_turn_stream
from backend.benchmark import benchmark_stream, load_cases


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LABEL_NOTE = "nhãn tham chiếu (n = 30), chưa kiểm định độc lập"

class SessionRequest(BaseModel):
    engines: list[str] = Field(min_length=1, max_length=3)


class TurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class BenchmarkRequest(BaseModel):
    engines: list[str] = Field(min_length=1, max_length=8)
    case_ids: list[str] | None = Field(default=None, max_length=30)
    warmup: int = Field(default=3, ge=0, le=5)


def _json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_rows() -> list[dict[str, Any]]:
    availability = model_availability()
    kev_temperature = engine_temperature("kev-0.8b")
    rows: list[dict[str, Any]] = []
    descriptions = [
        ("laya", "Laya", "421M", "system-one"),
        ("kev-0.8b", "Kev-0.8B", f"0.8B; T={kev_temperature:g}", "system-one"),
    ]
    for engine_id, label, params, kind in descriptions:
        status, detail = availability[engine_id]
        rows.append({
            "id": engine_id,
            "label": label,
            "params": params,
            "kind": kind,
            "device": detail if status == "ready" else "unavailable",
            "status": status,
            "reason": None if status == "ready" else detail,
        })

    for tag in OLLAMA_TAGS:
        engine_id = f"llm:{tag}"
        status, detail = availability[engine_id]
        rows.append({
            "id": engine_id,
            "label": tag,
            "params": tag.rsplit(":", 1)[-1],
            "kind": "llm",
            "device": "ollama" if status == "ready" else "unavailable",
            "status": status,
            "reason": None if status == "ready" else detail,
        })
    return rows


# The demo listens on the loopback interface only. A web page open in the same browser can still send requests to it,
# either directly (cross-site POST) or through DNS rebinding (a hostname that later resolves to 127.0.0.1). So every
# request must carry a loopback Host header, and a state-changing request that carries an Origin header must come from
# this very server. Extra hosts can be allowed on purpose with SYSTEM_ONE_ALLOWED_HOSTS="name1,name2".
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"} | {
    host.strip().lower() for host in os.environ.get("SYSTEM_ONE_ALLOWED_HOSTS", "").split(",") if host.strip()
}
_BENCHMARK_LOCK = threading.Lock()


def _hostname(netloc: str) -> str:
    netloc = netloc.strip().lower()
    if netloc.startswith("["):
        return netloc[1:].split("]", 1)[0]
    return netloc.rsplit(":", 1)[0] if netloc.count(":") == 1 else netloc


def _blocked(code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"schema": 1, "error": {"code": error, "message": message}})


def create_app() -> FastAPI:
    app = FastAPI(title="System-One memory-control demo", version="1")

    @app.middleware("http")
    async def local_only_guard(request: Request, call_next):
        host_header = request.headers.get("host", "")
        if _hostname(host_header) not in _ALLOWED_HOSTS:
            return _blocked(400, "host_not_allowed", "This server only answers requests addressed to localhost.")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin is not None:
                origin_netloc = origin.split("://", 1)[-1].rstrip("/").lower()
                if origin_netloc != host_header.strip().lower():
                    return _blocked(403, "origin_not_allowed", "Cross-origin requests are not accepted.")
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"schema": 1, "error": {"code": "internal_error", "message": str(exc)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = exc.errors()[0].get("msg", "Invalid request") if exc.errors() else "Invalid request"
        return JSONResponse(
            status_code=422,
            content={"schema": 1, "error": {"code": "invalid_request", "message": detail}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = str(exc.detail) if isinstance(exc.detail, (str, int, float)) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"schema": 1, "error": {"code": "http_error", "message": message}},
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"schema": 1, "ok": True, "mock": False}

    @app.get("/api/hardware")
    async def hardware() -> dict[str, Any]:
        return {"schema": 1, **hardware_report()}

    @app.get("/api/models")
    async def models() -> list[dict[str, Any]]:
        # Section 5 specifies this response as an array; it has no top-level place for schema.
        return _model_rows()

    @app.get("/api/scenario")
    async def scenario() -> dict[str, Any]:
        source = _json_file(DATA / "scenario.json")
        return {
            "schema": 1,
            "id": source["id"],
            "title": source["title"],
            "turns": [
                {"i": turn["i"], "speaker": "user", "text": turn["text"]}
                for turn in source["turns"]
            ],
        }

    @app.get("/api/cases")
    async def cases() -> dict[str, Any]:
        source = _json_file(DATA / "cases.json")
        return {
            "schema": 1,
            "n": source["n"],
            "label_note": source.get("label_note", LABEL_NOTE),
            "positives": source["positives"],
            "cases": [
                {
                    "id": case["id"],
                    "observation": case["observation"],
                    "recent_memories": case["recent_memories"],
                    "candidate": case["candidate"],
                    "reference": case["reference"],
                }
                for case in source["cases"]
            ],
        }

    @app.get("/api/replay")
    async def replay() -> JSONResponse:
        path = DATA / "replay.json"
        if not path.exists():
            return JSONResponse(
                status_code=404,
                content={"schema": 1, "error": {"code": "not_found", "message": "No replay recording is available."}},
            )
        data = _json_file(path)
        return JSONResponse({"schema": 1, **data})

    @app.post("/api/session")
    async def create_session(body: SessionRequest) -> JSONResponse:
        if any(engine not in VALID_ENGINE_IDS for engine in body.engines):
            return JSONResponse(
                status_code=400,
                content={"schema": 1, "error": {"code": "invalid_engine", "message": "One or more engine ids are not supported."}},
            )
        if len(set(body.engines)) != len(body.engines):
            return JSONResponse(
                status_code=400,
                content={"schema": 1, "error": {"code": "duplicate_engine", "message": "Engine ids must be unique."}},
            )
        session = SESSIONS.create(body.engines)
        return JSONResponse({"schema": 1, "session_id": session.session_id})

    @app.post("/api/session/{session_id}/turn")
    async def session_turn(session_id: str, body: TurnRequest) -> Any:
        session = SESSIONS.get(session_id)
        if session is None:
            return JSONResponse(
                status_code=404,
                content={"schema": 1, "error": {"code": "not_found", "message": "Session not found."}},
            )
        return StreamingResponse(
            build_turn_stream(session, body.text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/session/{session_id}/reset")
    async def reset_session(session_id: str) -> JSONResponse:
        session = SESSIONS.get(session_id)
        if session is None:
            return JSONResponse(
                status_code=404,
                content={"schema": 1, "error": {"code": "not_found", "message": "Session not found."}},
            )
        SESSIONS.reset(session)
        return JSONResponse({"schema": 1, "ok": True})

    @app.post("/api/benchmark")
    async def benchmark(body: BenchmarkRequest) -> Any:
        if any(engine not in VALID_ENGINE_IDS for engine in body.engines):
            return JSONResponse(
                status_code=400,
                content={"schema": 1, "error": {"code": "invalid_engine", "message": "One or more engine ids are not supported."}},
            )
        if len(set(body.engines)) != len(body.engines):
            return JSONResponse(
                status_code=400,
                content={"schema": 1, "error": {"code": "duplicate_engine", "message": "Engine ids must be unique."}},
            )
        if body.case_ids is not None:
            known = {case["id"] for case in load_cases()}
            unknown = set(body.case_ids) - known
            if unknown:
                return JSONResponse(
                    status_code=400,
                    content={"schema": 1, "error": {"code": "invalid_case", "message": "One or more case ids are not supported."}},
                )
        if not _BENCHMARK_LOCK.acquire(blocking=False):
            return _blocked(429, "benchmark_busy", "A benchmark is already running on this machine.")

        async def guarded():
            try:
                async for chunk in benchmark_stream(body.engines, body.case_ids, body.warmup):
                    yield chunk
            finally:
                _BENCHMARK_LOCK.release()

        return StreamingResponse(
            guarded(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.mount("/", StaticFiles(directory=ROOT / "web" / "out", html=True), name="ui")
    return app


app = create_app()
