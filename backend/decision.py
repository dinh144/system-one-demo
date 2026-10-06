from __future__ import annotations

from typing import Any

from backend.config import NO_THRESHOLD, YES_THRESHOLD


QUESTIONS = {
    "should_store": "Does the latest conversation contain a durable fact about the user worth storing in long-term memory?",
    "redundant": "Is the new information already covered by one of the recent memories?",
    "obsolete": "Does the new information make any of the recent memories outdated or contradicted?",
}


def make_state(observation: str, recent_memories: list[str], candidate: str | None = None) -> str:
    lines = ["Conversation:", f"User: {observation}", "", "Recent memories:"]
    lines.extend(f"- {memory}" for memory in recent_memories)
    if candidate is not None:
        lines.extend(["", "Candidate memory:", candidate])
    return "\n".join(lines)


def classify(probability: float) -> str:
    if probability >= YES_THRESHOLD:
        return "yes"
    if probability <= NO_THRESHOLD:
        return "no"
    return "unsure"


def action_for(answers: dict[str, dict[str, Any]]) -> str:
    labels = {key: value["label"] for key, value in answers.items()}
    if any(label == "unsure" for label in labels.values()):
        return "ask"
    if labels["obsolete"] == "yes":
        return "replace"
    if labels["should_store"] == "yes" and labels["redundant"] == "no":
        return "add"
    return "skip"


def scored_answers(
    probabilities: dict[str, float],
    sources: dict[str, str],
    *,
    api_compatible: bool = True,
) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    for key in QUESTIONS:
        probability = float(probabilities[key])
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"{key} probability is outside [0, 1]")
        source = sources[key]
        # Section 5's response enum is model|hard_label. The internal logprob
        # value remains available to regression checks and is mapped to model
        # on the public API surface.
        public_source = "model" if source == "logprob" and api_compatible else source
        answers[key] = {
            "p": probability,
            "label": classify(probability),
            "probability_source": public_source,
        }
    return answers
