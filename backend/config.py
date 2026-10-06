from __future__ import annotations

import os


YES_THRESHOLD = float(os.environ.get("YES_THRESHOLD", "0.65"))
NO_THRESHOLD = float(os.environ.get("NO_THRESHOLD", "0.35"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_TAGS = (
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "qwen2.5:7b",
)
LLM_TEMPERATURE = 0
# 1 = engines run one after another, so every measured latency is that engine alone on the CPU.
# Values above 1 run engines at the same time and make them compete for cores; latencies then include that contention.
ENGINE_WORKERS = max(1, int(os.environ.get("SYSTEM_ONE_ENGINE_WORKERS", "1")))
KEV_DEFAULT_TEMPERATURE = float(os.environ.get("KEV_TEMPERATURE", "2.35"))
