from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from backend.engines import EngineResult
from backend.sessions import MemoryItem, SessionStore, build_turn_stream


ENGINES = ["laya", "kev-0.8b", "llm:qwen2.5:0.5b"]


class SessionStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_replace_ask_and_add_only_change_their_engine_store(self) -> None:
        sessions = SessionStore()
        session = sessions.create(ENGINES)
        session.stores["laya"].append(MemoryItem("old", "User lives in Berlin."))

        probabilities = {
            "laya": {"should_store": 0.9, "redundant": 0.1, "obsolete": 0.9},
            "kev-0.8b": {"should_store": 0.5, "redundant": 0.1, "obsolete": 0.1},
            "llm:qwen2.5:0.5b": {"should_store": 0.9, "redundant": 0.1, "obsolete": 0.1},
        }

        def fake_run_engine(engine: str, *_args: object) -> tuple[EngineResult, float]:
            values = probabilities[engine]
            result = EngineResult(
                probabilities=values,
                probability_sources={key: "model" for key in values},
                gen_tokens=None,
                device="test",
            )
            return result, 1.25

        ready = {engine: ("ready", "test") for engine in ENGINES}
        with (
            patch("backend.sessions.model_availability", return_value=ready),
            patch("backend.sessions.warm_engine", return_value=True),
            patch("backend.sessions.run_engine", side_effect=fake_run_engine),
        ):
            raw_events = [
                event
                async for event in build_turn_stream(
                    session,
                    "I moved away from Berlin last week.",
                )
            ]

        parsed_events: list[tuple[str, dict[str, object]]] = []
        for raw in raw_events:
            event_name, data_line = raw.strip().split("\n", 1)
            parsed_events.append((event_name.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))

        decisions = {payload["engine"]: payload for name, payload in parsed_events if name == "decision"}
        self.assertEqual(set(decisions), set(ENGINES))
        self.assertEqual(decisions["laya"]["action"], "replace")
        self.assertEqual(decisions["kev-0.8b"]["action"], "ask")
        self.assertEqual(decisions["llm:qwen2.5:0.5b"]["action"], "add")

        laya_memory = decisions["laya"]["memory"]
        self.assertEqual(laya_memory[0]["id"], "old")
        self.assertEqual(laya_memory[0]["status"], "replaced")
        self.assertEqual(laya_memory[1]["text"], "I moved away from Berlin last week.")
        self.assertEqual(decisions["kev-0.8b"]["memory"], [])
        self.assertEqual(len(decisions["llm:qwen2.5:0.5b"]["memory"]), 1)
        self.assertEqual(session.stores["kev-0.8b"], [])
        self.assertEqual(session.stores["llm:qwen2.5:0.5b"][0].text, "I moved away from Berlin last week.")


if __name__ == "__main__":
    unittest.main()
