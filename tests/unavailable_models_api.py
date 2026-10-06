from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


def main() -> int:
    with TestClient(app, base_url="http://localhost") as client:
        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        health = health_response.json()
        assert health["ok"] is True and health["mock"] is False
        models_response = client.get("/api/models")
        assert models_response.status_code == 200
        rows = models_response.json()
        assert isinstance(rows, list)
    by_id = {row["id"]: row for row in rows}
    for engine in ("llm:qwen2.5:0.5b", "llm:qwen2.5:1.5b", "llm:qwen2.5:3b", "llm:qwen2.5:7b"):
        assert by_id[engine]["status"] == "unavailable", by_id[engine]
        assert by_id[engine]["reason"] == "Ollama is not reachable", by_id[engine]
    assert by_id["laya"]["status"] == "ready"
    assert by_id["kev-0.8b"]["status"] == "ready"
    print("PASS: backend served health and model status; four Ollama engines unavailable with exact reason")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
