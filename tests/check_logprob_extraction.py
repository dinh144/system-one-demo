from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

from backend.config import LLM_TEMPERATURE, OLLAMA_TAGS, OLLAMA_URL
from backend.decision import QUESTIONS, make_state
from backend.engines import extract_logprob_probability
from backend.hardware import physical_core_count
from backend.benchmark import load_cases


def _request(tag: str, prompt: str) -> dict:
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
        return json.loads(response.read().decode("utf-8"))


def _prompt(observation: str, memories: list[str], candidate: str | None) -> str:
    state = make_state(observation, memories, candidate)
    return (
        f"{state}\n\n"
        "Answer three yes/no questions about the latest conversation:\n"
        f"1. should_store: {QUESTIONS['should_store']}\n"
        f"2. redundant: {QUESTIONS['redundant']}\n"
        f"3. obsolete: {QUESTIONS['obsolete']}\n"
        'Reply with JSON only: {"should_store": true|false, "redundant": true|false, "obsolete": true|false}'
    )


def main() -> int:
    cases = load_cases()[:5]
    failed = False
    for tag in OLLAMA_TAGS:
        try:
            # Load each Ollama model before collecting the five benchmark examples.
            _request(tag, _prompt("Warm-up request.", [], None))
            logprob_count = 0
            field_count = 0
            for case in cases:
                response = _request(
                    tag,
                    _prompt(case["observation"], case["recent_memories"], case["candidate"]),
                )
                message = response.get("message") or {}
                content = message.get("content", "")
                sampled = json.loads(content)
                entries = response.get("logprobs") or message.get("logprobs") or []
                for field in QUESTIONS:
                    value = sampled[field]
                    probability, source = extract_logprob_probability(
                        content,
                        entries,
                        field,
                        value,
                    )
                    field_count += 1
                    logprob_count += source == "logprob"
                    if not 0.0 <= probability <= 1.0:
                        raise AssertionError(f"{field}: probability outside [0, 1]")
                    if (probability >= 0.5) != value:
                        raise AssertionError(
                            f"{field}: p(true)={probability:.6f} disagrees with sampled {value}"
                        )
            status = "PASS" if logprob_count >= 14 and field_count == 15 else "FAIL"
            print(f"{tag}: {status} ({logprob_count}/{field_count} logprob; sampled labels agree)")
            failed |= status != "PASS"
        except Exception as exc:
            failed = True
            print(f"{tag}: FAIL ({str(exc).splitlines()[0]})")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
