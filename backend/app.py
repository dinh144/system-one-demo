from __future__ import annotations

import json
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
    text: str = Field(min_length=1)


class BenchmarkRequest(BaseModel):
    engines: list[str] = Field(min_length=1)
    case_ids: list[str] | None = None
    warmup: int = Field(default=3, ge=0)


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


def create_app() -> FastAPI:
    app = FastAPI(title="System-One memory-control demo", version="1")

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
        return StreamingResponse(
            benchmark_stream(body.engines, body.case_ids, body.warmup),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.mount("/", StaticFiles(directory=ROOT / "web" / "out", html=True), name="ui")
    return app


app = create_app()
