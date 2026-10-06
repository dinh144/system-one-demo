from __future__ import annotations

import os

import torch
from laya import Router

from backend.hardware import physical_core_count


EXAMPLES = [
    (
        "User: I just moved to Berlin last month, still getting used to it.\nAssistant: Nice, how are you finding it?\nUser: Good. Also my new landlord requires rent on the 1st.",
        ["User lives in Paris.", "User prefers dark mode.", "User works as a nurse."],
    ),
    (
        "User: Thanks, that's all for now.\nAssistant: You're welcome!",
        ["User is learning Rust.", "User lives in Hanoi.", "User has a cat named Miso."],
    ),
    (
        "User: I'm vegetarian, by the way.\nAssistant: Noted, I'll suggest vegetarian recipes.",
        ["User is vegetarian.", "User likes spicy food.", "User cooks on weekends."],
    ),
    (
        "User: I switched from Python to Go for my backend work.\nAssistant: Interesting, why?\nUser: Concurrency and deployment simplicity.",
        ["User writes backend code in Python.", "User uses PostgreSQL.", "User deploys on AWS."],
    ),
    (
        "User: What's the weather like today?\nAssistant: I can't check live weather, sorry.",
        ["User's birthday is June 3.", "User drinks green tea.", "User's name is Linh."],
    ),
]

QUESTIONS = {
    "should_store": {
        "type": "noul",
        "instructions": "Does the latest conversation contain a durable fact about the user worth storing in long-term memory?",
    },
    "redundant": {
        "type": "noul",
        "instructions": "Is the new information already covered by one of the recent memories?",
    },
    "obsolete": {
        "type": "noul",
        "instructions": "Does the new information make any of the recent memories outdated or contradicted?",
    },
}

EXPECTED = [
    {"should_store": 0.05, "redundant": 0.15, "obsolete": 0.75},
    {"should_store": 0.75, "redundant": 0.47, "obsolete": 0.04},
    {"should_store": 0.52, "redundant": 0.06, "obsolete": 0.03},
    {"should_store": 0.54, "redundant": 0.22, "obsolete": 0.19},
    {"should_store": 0.10, "redundant": 0.13, "obsolete": 0.09},
]


def run_regression() -> list[dict[str, float]]:
    os.environ.pop("LAYA_CPU_AMP", None)
    torch.set_num_threads(physical_core_count()[0])
    router = Router(preload=True, device="cpu")
    observed = []
    for conversation, memories in EXAMPLES:
        state = "Conversation:\n" + conversation + "\n\nRecent memories:\n" + "\n".join(
            f"- {memory}" for memory in memories
        )
        result = router.predict(state, QUESTIONS, model="english")
        observed.append({key: float(result["answers"][key]["noul"]) for key in QUESTIONS})
    for index, values in enumerate(observed):
        for key, expected in EXPECTED[index].items():
            if abs(values[key] - expected) > 0.01:
                raise AssertionError(f"example {index} {key}: expected {expected}, got {values[key]}")
    return observed


if __name__ == "__main__":
    for index, values in enumerate(run_regression()):
        print(f"ex{index}", "/".join(f"{values[key]:.4f}" for key in QUESTIONS))
