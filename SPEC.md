# SPEC: System-One memory-control demo

Status: draft 1, 2026-10-06. Owner of this file: Claude (spec and verification). Codex builds `backend/`, agy builds `web/`. Neither edits this file; ask if something here is wrong.

## 1. Purpose and thesis

Demo for a supervisor (2026-10-07) of the student research proposal "fast non-generative decision model with controlled reliability evaluation for AI-agent memory control".

The demo shows the **problem** (an agent must decide what to do with memory on every chat turn) and a **fair measurement tool** (the same turn is sent to several models, each decision is shown with its probability and its measured latency). It does **not** claim any model is better.

Measured on the dev laptop (ThinkPad, CPU only, 3 noul questions, p50): qwen2.5:0.5b 294 ms, 1.5b 784 ms, 3b 1429 ms, Laya torch 1-2.2 s, Laya ONNX fp32 ~1.1 s, Kev-0.8B 1.2-1.3 s. A small LLM is faster than Laya/Kev on CPU. Do not write copy that implies System-One is faster.

## 2. Honesty rules (hard requirements, tested)

1. Every latency on screen is measured at runtime on the machine running the backend. No hard-coded latency in the UI or the repo, except inside a recording (rule 3).
2. Every number is tagged `live` or `replay`. A replay never looks live: a persistent banner reads "Phát lại: đo trên ThinkPad, không phải máy này".
3. Replay data and the video are labelled with the machine they came from (`recorded_on`).
4. Labels for the 30 cases are shown as **"nhãn tham chiếu (n = 30), chưa kiểm định độc lập"**. Never write "gán tay", "nhóm tự gán" or "ground truth". Do not mention who proposed them.
5. Accuracy is a secondary number, shown only with `n` and rule 4's wording. Never rank models with a "winner" badge.
6. Text claiming LLMs "have no probability" or "only return hard labels" is forbidden. Verified 2026-10-06: ollama 0.35.1 returns per-token logprobs (with top_logprobs) on `/api/generate` and `/api/chat`. The LLM engines therefore get a `logprob` probability variant (section 4); the demo never claims probabilities are unique to System-One.
7. Jev is not in the demo. GPT-4o-mini appears only as a static reference line citing the Jev-Mem paper (arXiv 2609.23986), never as a live column.
8. The repo does not contain the LoCoMo file (CC BY-NC 4.0). It contains only the 30 case turns and 10 scenario turns as short excerpts with attribution (`data/cases.json`, `data/scenario.json`, `NOTICE`), built by `scripts/build_cases.py` from the file that `scripts/fetch_data.py` downloads at setup. No API keys, no names from the proposal document. The repo is non-commercial research use.
9. The UI shows the number of positive reference cases per question next to every accuracy figure (`data/cases.json` → `positives`: should_store 20, redundant 3, obsolete 3 of 30) and says that accuracy on `redundant` and `obsolete` is not statistically meaningful.

## 3. Architecture

- `backend/`: Python 3.11+, FastAPI. Runs models. Serves JSON and Server-Sent Events on `127.0.0.1:8000`.
- `web/`: Next.js + shadcn, talks to the backend only through the API in section 5. For development it runs as a dev server against the mock or the backend. For the demo it is built once as a **static export** (`output: 'export'`, `web/out/`, committed to the repo) and **served by the backend itself**, so the presenter's machine runs one process on one port and needs no Node. In the exported build the API base is same-origin (empty string); `NEXT_PUBLIC_API_BASE` only overrides it for development.
- One launcher: `python -m demo run` starts the backend on `127.0.0.1:8000`; if that port is busy it picks the next free port and prints the URL it chose, never fails because of a busy port and never stops another process. It serves `web/out/` at `/` and opens the browser. If `web/out/` is missing it says so and tells the presenter how to build it. Cross-platform Python, no `.sh`/`.bat` logic beyond a 3-line wrapper (`run.bat`, `run.sh`). The target machine is **Windows + NVIDIA RTX 30xx**; the dev machine is Linux without GPU. Windows is untested by us.
- Everything works offline after `python -m demo setup` has downloaded weights.

Model adapters (one class each, same interface `decide(state, candidate) -> Decision`):

| id | what | device |
|---|---|---|
| `laya` | `convaiinnovations/laya` via `laya` package, `Router.predict(model="english")` | cuda if available else cpu |
| `kev-0.8b` | `jaredpalmer/kev-0.8b` (LoRA on Qwen3.5-0.8B-Base + head), call `Checkpoint.load` then `probs_batch`; no HTTP server | cuda if available else cpu |
| `llm:<tag>` | ollama `/api/chat`, `stream:false`, `format:json`, temperature 0 | ollama decides |

LLM tags offered: `qwen2.5:0.5b`, `qwen2.5:1.5b`, `qwen2.5:3b`, `qwen2.5:7b` (only those present in `ollama list`).

A missing or failing model never breaks the page: its column shows `status: unavailable` with a one-line reason.

## 4. The decision

For each chat turn the backend builds:

- `observation`: the user turn text.
- `recent_memories`: up to 3 most recent memory items from that engine's own store.
- `candidate`: in a live chat, the single recent memory with the highest overlap of lowercase 4-letter word prefixes with the turn (so "hike" matches "hiking"), empty if the overlap is zero. Simple rule on purpose; documented in the UI footer. In benchmark mode the candidate comes from `data/cases.json`.

Three yes/no questions (`noul`), wording after Jev-Mem `memory/jev_questions.py`:

- `should_store`: should this observation be stored as a memory?
- `redundant`: does the candidate already say the same thing?
- `obsolete`: does this observation make the candidate outdated or wrong?

Policy (same for every engine, thresholds in `backend/config.py`, default 0.5):

- p ≥ 0.65 → `yes`, p ≤ 0.35 → `no`, between → `unsure` (UI: "không chắc, nên hỏi lại").
- Memory action: `unsure` on any question → `ask` (store nothing). Else if `obsolete`=yes → `replace` candidate. Else if `should_store`=yes and `redundant`=no → `add`. Else `skip`.

LLM engines are called with `logprobs: true, top_logprobs: 5`. For each of the three JSON boolean fields, find the token position of the value (`true`/`false`) in the response and compute p(true) = exp(lp_true) / (exp(lp_true) + exp(lp_false)) from that position's top_logprobs, falling back to the sampled token's logprob if the other token is absent from the top 5. `probability_source: "logprob"`. If a position cannot be located, report `probability_source: "hard_label"` with p = 1.0 or 0.0 and the UI shows the badge. This extraction is unverified on the JSON output format: Claude verifies it on all four LLM tags (acceptance item 16) before the UI relies on it. Same policy thresholds apply to all engines, so the comparison of probabilities is like for like.

Each engine keeps its **own** memory store; the stores diverge visibly.

## 5. API (backend, JSON)

All responses carry `schema: 1`. Errors: `{"error": {"code": str, "message": str}}` with a proper HTTP status.

- `GET /api/health` → `{"ok": true, "mock": false}`. The UI mock server (`web/mock/`, development only, never packaged in the handoff run path) returns `"mock": true`; then the UI shows a full-width banner "MÁY CHỦ GIẢ LẬP, số liệu không thật" on every tab, styled like the replay banner. `web/mock/` is the only place in `web/` allowed to contain latency constants.
- `GET /api/hardware` → `{ "os": str, "cpu": str, "ram_gb": float, "gpu": {"name": str, "vram_gb": float, "cuda": bool} | null, "python": str, "torch": str, "ollama": {"reachable": bool, "models": [str]} }`
- `GET /api/models` → `[{ "id": str, "label": str, "params": str, "kind": "system-one"|"llm", "device": str, "status": "ready"|"loading"|"unavailable", "reason": str|null }]`
- `GET /api/scenario` → `{ "id": str, "title": str, "turns": [{ "i": int, "speaker": "user", "text": str }] }` (10 turns, from real LoCoMo dialogue, fetched at setup)
- `GET /api/cases` → `{ "n": int, "label_note": "nhãn tham chiếu (n = 30), chưa kiểm định độc lập", "cases": [{ "id": str, "observation": str, "recent_memories": [str], "candidate": str|null, "reference": {"should_store": bool, "redundant": bool, "obsolete": bool} }] }`
- `POST /api/session` → `{ "session_id": str }`. Creates empty memory stores for the chosen engines. Body: `{ "engines": [str] }` (max 3).
- `POST /api/session/{id}/turn` body `{ "text": str }` → `text/event-stream`. Events, in order:
  - `turn`: `{ "i": int, "text": str }`
  - one `decision` per engine **as soon as that engine finishes** (not in lockstep): `{ "engine": str, "source": "live", "latency_ms": float, "device": str, "answers": { "should_store": {"p": float, "label": "yes|no|unsure", "probability_source": "model|hard_label"}, "redundant": {...}, "obsolete": {...} }, "action": "add|replace|skip|ask", "memory": [ {"id": str, "text": str, "status": "active|replaced"} ], "gen_tokens": int|null }`
  - `engine_start`: `{ "engine": str }`, sent when that engine actually begins running (see "Execution mode" below); the UI starts the engine's latency clock here and shows "đang chờ đến lượt" before it. A UI that never receives it treats every engine as running from the start of the turn.
  - `engine_error`: `{ "engine": str, "message": str }`
  - `done`: `{}`
- `POST /api/session/{id}/reset` → `{ "ok": true }`
- `POST /api/benchmark` body `{ "engines": [str], "case_ids": [str]|null, "warmup": 3 }` → SSE `progress` events then `result`: per engine `{ "p50_ms": float, "p95_ms": float, "n": int, "accuracy": {"value": float, "n": int, "note": str} }`. Accuracy uses rule 4's `note`. Runs on this machine only.
- `GET /api/replay` → `{ "source": "replay", "recorded_on": str, "recorded_at": str, "turns": [...same shape as live decision events...] }`. Present only if `data/replay.json` exists.

**Execution mode.** Default is sequential (`SYSTEM_ONE_ENGINE_WORKERS=1`): engines run one after another, in the order listed in the session, so every reported latency is that engine alone on the machine. Measured on the dev laptop (CPU only, 4 physical cores), running three engines at the same time inflated each engine's latency roughly tenfold (for example Laya 1.3 s alone versus 13 s concurrent), because they compete for the same cores. `SYSTEM_ONE_ENGINE_WORKERS=N` (N>1) runs N engines at once; then every latency includes contention and the UI footer must say so. The benchmark endpoint uses the same setting. First call of each engine is a warm-up that is not reported as a latency.

## 6. UI (web)

Read `DESIGN.md` first; if it does not exist, stop and ask Claude to write it (UI agent does not invent a design system).

Main screen, fixed layout:

- Left: chat. Starter button "Chạy kịch bản 10 lượt" (default, prominent). Free text box present but secondary.
- Right: **three engine columns**: Laya, Kev-0.8B, and one LLM chosen from a dropdown. Each column shows the engine's own memory store and, per turn, a decision card with: three answers with probability bars and label (`yes/no/unsure`), the action chip, and a **latency clock** that counts up live while the engine is running and freezes at the measured value.
- A decision that differs between columns is highlighted. `unsure` is a visible third state, not hidden.
- Footer line: device and model versions from `/api/hardware`, plus the `candidate` rule.
- Tab 2: "Bảng đo": full table of all ready engines from `/api/benchmark` (p50, p95, accuracy with n and note), the GPT-4o-mini reference line, and the honesty note. A "Chạy đo trên máy này" button.
- Tab 3: "Phát lại": only when `/api/replay` exists; banner per rule 2.

States that must be designed: loading models, engine unavailable, engine error mid-turn, no ollama, backend unreachable, empty store.

Must work on a 1920x1080 projector and a 1280x720 laptop; text readable from the back of a room (body ≥ 18px).

## 7. Repo layout

```
system-one-demo/
  README.md          human, 10 lines
  HANDOFF.md         for the friend's coding agent (section 9)
  SPEC.md            this file
  DESIGN.md          UI design system (Claude writes before UI work)
  backend/  web/  scripts/  data/(cases.json, scenario.json, replay.json, video/)
  demo/__main__.py   setup | doctor | run | selftest
```

## 8. Acceptance criteria (Claude verifies independently, on the dev laptop)

Backend:
1. `python -m demo doctor` prints a hardware report and exits 0 even with no GPU, no ollama, or missing models; it lists exactly what is missing.
2. `/api/models` marks missing engines `unavailable` with a reason; the server still starts.
3. A turn on 3 engines streams one `engine_start` and one `decision` event per engine, each with its own `latency_ms`; in the default sequential mode events arrive in session order and each engine_start follows the previous decision, and with `SYSTEM_ONE_ENGINE_WORKERS=3` a faster engine's decision arrives before a slower one's.
4. Probabilities for Laya on the 5 benchmark examples in the dev scratchpad match the recorded fp32 values within 0.01 (regression check, torch CPU).
5. `selftest` runs 3 cases through every ready engine and reports pass/fail per engine; one failing engine does not abort the others.
6. No latency constant appears in `backend/` or `web/` source (grep test). `data/replay.json` is the only file with recorded latencies and has `recorded_on`.
7. Repo contains no `locomo10.json`, no key-like strings, no proposal-document names (grep test).
8. All engines' stores diverge correctly: `replace` marks the candidate `replaced`, `ask` stores nothing.

UI:
9. All states listed in section 6 render without console errors.
10. Latency clock counts up while pending and freezes at the server value.
11. Replay mode shows the banner on every screen; live mode never does.
12. No forbidden wording from section 2 anywhere (grep test over `web/` and `data/`).
13. Lighthouse accessibility ≥ 95 and no text under 18px for body content at 1920 and 1280 widths; `better-accessibility` and `design-review` skills clean.

Handoff:
14. A fresh copy of the repo (git clone once a commit exists) on the dev laptop reaches a working demo by following only `HANDOFF.md`, with no step relying on this conversation, with another process already holding port 3000 and port 8000 free or busy (test both), and without Node installed on the PATH.
17. UI content checks the agents' own reports missed: the chat panel lists every turn of the 10-turn scenario; the page for a full scenario is no taller than 2 viewport heights at 1920x1080 (cards compact, or the engine columns scroll on their own with the newest turn pinned at the top); engine parameter counts come from `/api/models` (`params`), never typed in the UI; the mock replay is labelled `recorded_on: "mock"`, never a real machine name.
16. For each of the four LLM tags, 5 benchmark examples: the extracted p(true) for every field is in [0,1], matches the sampled token's decision (p ≥ 0.5 iff the model wrote `true`), and `probability_source` is `logprob` for at least 14 of 15 fields; otherwise the fallback badge shows.
15. A 60-90 s screen recording of a real run exists in `data/video/`, labelled with `recorded_on`.

## 9. HANDOFF.md requirements (for the friend's agent, Windows)

Written for an agent, per `writing-for-agents`: numbered steps, each with a command and an exact pass/fail check; no prose that needs interpretation. It must say plainly: "Not tested on Windows by the authors." It must include: install Python, uv, Node, Ollama; `ollama pull` for the four LLM tags; `python -m demo setup`; `python -m demo doctor`; `python -m demo run`; what to do if CUDA torch fails (fall back to CPU, still works); what to send back (the `doctor` output and any error text). It ends with a 5-line "what the presenter says about the labels if asked" note stating the truth: reference labels, 30 cases, proposed by the author and not independently verified.

## 10. Out of scope

Jev, GPT-4o-mini live, training, calibration plots (ECE/Brier/AUROC), Docker, deployment, auth, multi-user.

## 11. Open items (measurements pending, owner Claude)

Resolved 2026-10-06 (dev laptop, CPU only, i7-1185G7, noisy by 20-40%):
1. Kev-0.8B: best config is fp32 with threads = physical cores (4 here), p50 ~0.83-1.08 s. 8 threads and 2 threads are slower, bf16 is 2-3x slower (no avx512_bf16/amx), `flash-linear-attention` needs triton and gives no gain on CPU, `causal_conv1d` needs nvcc. Backend therefore: threads default = physical core count (not a constant 4), fp32 on CPU, on CUDA let the library pick. Do not install the acceleration packages on Windows CPU fallback; on CUDA they may help but are untested by us, so `doctor` reports whether they import and the demo never requires them. Prefix cache gave no gain inside one request on CPU.
2. qwen2.5:7b: p50 3.29 s, p95 7.1 s (load ~3), ~7 tok/s.
3. ollama logprobs: available (see rule 6). JSON-position extraction still to verify.

Still open:
4. Kev default calibration temperature (2.35) vs `KEV_TEMPERATURE=1.0`: decide which the demo shows by default; show the setting in the UI.
5. All numbers above are from the ThinkPad. The Legion 5 (RTX 30xx) will differ; nothing here is shown on screen as a measured result.

## 12. Work split

- Claude: this spec, DESIGN.md, `data/cases.json` (30 cases) and `scenario.json`, measurements, acceptance, independent verification, video.
- Codex: `backend/`, `demo/`, `scripts/`, `HANDOFF.md` draft.
- agy: `web/` against the API in section 5 using a mock server first.
- Each agent reports what it ran and the output; Claude re-runs the acceptance checks itself and does not accept "done" without them.
