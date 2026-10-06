"""Build data/cases.json and data/scenario.json from LoCoMo (conversation index 5: Audrey and Andrew).

Turn text is copied verbatim from the LoCoMo file by dia_id. Memories are short paraphrases written for this demo.
Labels are reference labels proposed for the demo and not independently verified; the UI wording is fixed in SPEC.md section 2.

Usage: python scripts/build_cases.py path/to/locomo10.json
LoCoMo: Maharana et al., "Evaluating Very Long-Term Conversational Memory of LLM Agents", CC BY-NC 4.0.
"""
import json
import sys
from pathlib import Path

CONV = 5

MEM = {
    "A1": "Audrey has three dogs, Pepper, Precious and Panda, for 3 years.",
    "A2": "Audrey's dogs are city dogs that explore parks and trails.",
    "A3": "Audrey adopted a puppy named Pixie; she took a few days to get used to the other dogs.",
    "A4": "Audrey has not yet checked out the hiking spot Andrew recommended.",
    "A5": "Audrey went on a hike and saw a hummingbird.",
    "A6": "Audrey moved to a new place with a bigger backyard.",
    "A7": "Audrey plays fetch with her dogs and goes to doggie playdates.",
    "N1": "Andrew started a new job as a Financial Analyst.",
    "N2": "Andrew has no pets right now and loves animals.",
    "N3": "Andrew wants a dog but finds it hard to find a dog-friendly apartment in the city.",
    "N5": "Andrew hikes on weekends on the Fox Hollow trail.",
}

# (dia_id, recent memory keys, candidate key or None, should_store, redundant, obsolete)
T, F = True, False
CASES = [
    ("D1:1", [], None, F, F, F),
    ("D1:7", [], None, T, F, F),
    ("D1:9", ["A1"], "A1", T, F, F),
    ("D1:11", ["A1", "A2"], "A2", F, F, F),
    ("D1:21", ["A1", "A2"], "A2", F, F, F),
    ("D2:1", ["A1", "A2"], "A1", T, F, F),
    ("D2:3", ["A1", "A2", "A3"], "A3", T, F, F),
    ("D2:5", ["A1", "A2"], "A1", T, F, F),
    ("D2:7", ["A1", "A3"], "A3", T, T, F),
    ("D2:9", ["A1", "A3"], "A3", T, F, F),
    ("D2:11", ["A1", "A3", "A4"], "A4", F, F, F),
    ("D4:1", ["A3", "A4"], "A4", T, F, T),
    ("D4:3", ["A3", "A5"], "A5", F, F, F),
    ("D4:15", ["A1", "A3", "A5"], "A1", F, T, F),
    ("D4:17", ["A2", "A5"], "A5", T, F, F),
    ("D4:21", ["A2", "A5"], "A2", T, F, F),
    ("D4:29", ["A5", "A7"], "A7", F, F, F),
    ("D9:1", ["A2", "A5", "A7"], "A2", T, F, F),
    ("D9:5", ["A2", "A7", "A6"], "A6", T, F, F),
    ("D9:17", ["A6", "A7"], "A6", T, T, F),
    ("D9:15", ["A6", "A7"], "A7", F, F, F),
    ("D9:23", ["A5", "A6"], "A5", T, F, F),
    ("D9:27", ["A5", "A6"], "A6", F, F, F),
    ("D1:2", [], None, T, F, F),
    ("D1:12", ["N1"], "N1", T, F, F),
    ("D1:20", ["N1", "N2"], "N2", T, F, F),
    ("D2:8", ["N1", "N2"], "N2", T, F, F),
    ("D2:10", ["N2", "N3"], "N3", F, F, F),
    ("D12:1", ["N2", "N3"], "N2", T, F, T),
    ("D21:5", ["N1", "N5"], "N5", T, F, T),
]

# 10 user turns of Audrey, in conversation order; engines build their own memory from these turns.
SCENARIO = ["D1:7", "D2:1", "D2:3", "D2:5", "D2:7", "D4:1", "D4:15", "D4:21", "D9:1", "D9:17"]


def main(path):
    data = json.loads(Path(path).read_text())
    conv = data[CONV]["conversation"]
    turns = {}
    for key, val in conv.items():
        if key.startswith("session_") and not key.endswith("date_time"):
            for t in val:
                turns[t["dia_id"]] = t

    def text(dia):
        return turns[dia]["text"].strip()

    cases = []
    for i, (dia, recent, cand, s, r, o) in enumerate(CASES, 1):
        cases.append({
            "id": f"c{i:02d}",
            "source": f"LoCoMo conv {CONV} {dia} ({turns[dia]['speaker']})",
            "observation": text(dia),
            "recent_memories": [MEM[k] for k in recent],
            "candidate": MEM[cand] if cand else None,
            "reference": {"should_store": s, "redundant": r, "obsolete": o},
        })
    positives = {q: sum(c["reference"][q] for c in cases) for q in ("should_store", "redundant", "obsolete")}
    out = Path(__file__).resolve().parent.parent / "data"
    out.mkdir(exist_ok=True)
    (out / "cases.json").write_text(json.dumps({
        "n": len(cases),
        "label_note": f"nhãn tham chiếu (n = {len(cases)}), chưa kiểm định độc lập",
        "positives": positives,
        "attribution": "Turn text from LoCoMo (Maharana et al.), CC BY-NC 4.0; memories and labels are demo-authored.",
        "cases": cases,
    }, ensure_ascii=False, indent=2))
    (out / "scenario.json").write_text(json.dumps({
        "id": "audrey-1",
        "title": "Audrey và các chú chó (10 lượt từ LoCoMo)",
        "attribution": "Turn text from LoCoMo (Maharana et al.), CC BY-NC 4.0.",
        "turns": [{"i": i, "speaker": "user", "text": text(d), "source": f"LoCoMo conv {CONV} {d}"} for i, d in enumerate(SCENARIO, 1)],
    }, ensure_ascii=False, indent=2))
    print("cases", len(cases), "positives", positives)


if __name__ == "__main__":
    main(sys.argv[1])
