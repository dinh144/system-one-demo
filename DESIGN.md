# DESIGN: System-One memory-control demo

A measuring instrument, not a landing page. Calm, exact, readable from the back of a room on a projector. No marketing tone, no winner styling.

## Principles

1. Numbers are the content. A probability or a millisecond value is always the largest, highest-contrast thing in its card.
2. Provenance is always visible: `live` vs `replay`, device, model version. Replay is loud (full-width banner), live is quiet.
3. No ranking. Never colour a model "best", never medal, crown, or green-vs-red an engine as a whole. Colour carries meaning only for `yes / no / unsure` and for "decisions differ".
4. Three states, not two: `yes`, `no`, `unsure`. `unsure` is a first-class state with its own colour and label.
5. Honest empty and failure states: an unavailable engine says why, in plain Vietnamese, in the column.
6. Motion shows work happening (latency clock counting up, bar filling) and nothing else. Respect `prefers-reduced-motion`: show the final value, no animation.

## Language

UI copy is Vietnamese. Identifiers (`should_store`, `redundant`, `obsolete`, model names) stay in English, set in the mono font, with a short Vietnamese gloss on first use ("should_store: có nên lưu không").

Fixed strings (do not reword):

- Labels note: `nhãn tham chiếu (n = 30), chưa kiểm định độc lập`
- Replay banner: `Phát lại: đo trên {recorded_on}, không phải máy này`
- Unsure action: `không chắc, nên hỏi lại`
- Accuracy caveat: `Với redundant (3 ca) và obsolete (3 ca), độ chính xác chưa có ý nghĩa thống kê.`
- Forbidden words anywhere in UI or data: `gán tay`, `nhóm tự gán`, `ground truth`, `đáp án đúng`, `winner`, `tốt nhất`, `nhanh nhất`.

## Tokens

Light theme only (projectors wash out dark UIs). Define as CSS variables on `:root`; shadcn tokens map onto these.

Colour (OKLCH; verify contrast ≥ 7:1 for body text, ≥ 4.5:1 for everything else with `better-colors`):

| token | value | use |
|---|---|---|
| `--bg` | `oklch(0.985 0.003 95)` | page |
| `--surface` | `oklch(1 0 0)` | cards |
| `--ink` | `oklch(0.2 0.01 260)` | text |
| `--ink-2` | `oklch(0.42 0.01 260)` | secondary text |
| `--line` | `oklch(0.9 0.005 260)` | borders |
| `--yes` | `oklch(0.45 0.12 150)` | label yes |
| `--no` | `oklch(0.45 0.01 260)` | label no (neutral grey, not red) |
| `--unsure` | `oklch(0.5 0.14 70)` | label unsure (amber) |
| `--differ` | `oklch(0.45 0.16 285)` | "decisions differ" marker (violet, outline only) |
| `--replay` | `oklch(0.35 0.1 40)` bg tint `oklch(0.95 0.04 70)` | replay banner |
| `--focus` | `oklch(0.45 0.18 255)` | focus ring, 3px |

`yes/no/unsure` are never conveyed by colour alone: always a text label and an icon shape (check, dash, question mark).

Type (self-hosted or system, no CDN needed offline): UI `Inter` fallback `system-ui`; numbers and identifiers `JetBrains Mono` fallback `ui-monospace`; `font-variant-numeric: tabular-nums` on every number so clocks do not jitter.

| role | size / line | weight |
|---|---|---|
| body | 18 / 28 px | 400 |
| card number (probability, ms) | 32 / 36 px, mono | 600 |
| label chip | 16 / 20 px, uppercase tracking 0.04em | 600 |
| column header | 22 / 28 px | 600 |
| footer, captions | 16 / 24 px | 400 |

Nothing under 16 px. Body 18 px minimum on content.

Spacing: 4 px base, steps 4 8 12 16 24 32 48. Radius 8 px cards, 999 px chips, 4 px bars. Borders 1 px `--line`; no shadows except focus ring.

## Layout

Page max width 1840 px, side gutter 24 px (16 px under 640 px). Works at 1920x1080 and 1280x720; below 1000 px the three engine columns stack.

```
┌ header: title · hardware line (device, cuda yes/no, python) ───────────┐
├ replay banner (only when source = replay) ─────────────────────────────┤
├ tabs: Trực tiếp | Bảng đo | Phát lại ─────────────────────────────────┤
│ chat (≈ 28%)            │ engine column ×3 (each ≈ 24%)                │
│  messages               │  header: name · params · device · status      │
│  [Chạy kịch bản 10 lượt]│  memory store (list)                          │
│  [ô gõ tự do]           │  decision cards, newest on top                │
└ footer: candidate rule · label note ───────────────────────────────────┘
```

## Components

- **Engine column header**: model name (22 px), `params · device` in `--ink-2`, status chip (`ready`, `loading`, `unavailable`). LLM column has a dropdown of installed tags.
- **Decision card** (one per turn per engine): turn index; three rows `should_store / redundant / obsolete`, each with the label chip (icon + text), a probability bar (0 to 1 with ticks at 0.35 and 0.65 marking the unsure band) and the number; action chip (`add`, `replace`, `skip`, `ask`); latency clock bottom right.
- **Latency clock**: mono, counts up in 10 ms steps while pending, freezes at the server value, then shows `ms` in `--ink-2`. Pending state also shows a text "đang chạy" (not only motion).
- **Probability source badge**: when `probability_source` is `hard_label` show `nhãn cứng` badge on that row; `logprob` and `model` show nothing.
- **Differ marker**: a 2 px `--differ` outline on the decision cards of one turn when their actions or any label differ, with the text `khác nhau`.
- **Memory item**: text, status `active` or `replaced` (struck through, `--ink-2`, with "thay bằng …").
- **Replay banner**: full width, `--replay`, always on top of every tab while source is replay.
- **Benchmark table**: engines as rows, p50, p95, n; accuracy per question with `n` positives; static GPT-4o-mini reference line with the Jev-Mem citation; the accuracy caveat sentence; button `Chạy đo trên máy này`.

## States to design

Loading models; engine unavailable (reason shown); engine error mid-turn (card shows message, other columns unaffected); no ollama (LLM column unavailable with install hint); backend unreachable (full-page message with the command to start it); empty store ("chưa có ký ức nào"); replay present vs absent; reduced motion.

## Accessibility

Keyboard reachable everywhere, visible 3 px focus ring, tab order chat → columns. Cards are `article` with an accessible name; the latency clock has `aria-live="off"` while counting and announces once on freeze. Contrast and target size verified with `better-accessibility`; targets ≥ 44 px.

## Do / Don't

Do: show the raw value next to every bar; keep three columns the same width; keep cards the same height per turn so differences line up across columns.
Don't: gradient hero, illustrations, emoji, confetti, success-green for an engine, sorting engines by speed or accuracy, any sentence that says one model is better.
