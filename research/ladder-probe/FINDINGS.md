# Enrichment model-ladder probe — findings

**Run 2026-07-26 on the Fedora box (RX 6900 XT, Ollama).** Follow-up to issue [#32](https://github.com/markdlabrecque/tome/issues/32).
Criteria pre-registered in `CRITERIA.md` with both amendments recorded before scoring.
Raw data: `raw.jsonl` (grammar-constrained), `raw-unconstrained.jsonl`, and
`raw-contended.jsonl.bak` (first run, VRAM-contended, retained not deleted).

## The question

#8 chose `qwen3:14b` because it *"fits comfortably within 16GB VRAM"* — a ceiling-fit, never
an argument that 14b is the **minimum** for extraction quality. Is a smaller model good enough?

## Headline

**No clean pass. `qwen3:4b` is the best small candidate and lands a SOFT FAIL; `qwen3:8b` is
worse than `4b` in every configuration tested.** The ladder is **non-monotonic**, which
matches LLMStructBench's independent finding that 4B ≈ 8B and that 14B beats 32B.

**The sharper result is not the scores — it is that only `qwen3:14b` was robust across
decoding configurations.** Each smaller model works in exactly one and fails in the other.

| model | grammar-constrained (`format: "json"`) | unconstrained |
|---|---|---|
| `qwen3:14b` | ✅ 1.01 ent/subj, 99.1% coverage | ✅ 0.97 ent/subj, 98.4% coverage |
| `qwen3:8b` | ❌ degenerates on 3/8 draws | ⚠️ 5/8 clean, 3/8 malformed → 1 entity recovered |
| `qwen3:4b` | ✅ 0.95 ent/subj, 92.5% coverage | ❌ 0/8 — reasoning preamble, hits the cap |

## Scored result, best configuration per model

| model | config | ent/subj | coverage | fabrication | Decision recall | Fact share | schema fails |
|---|---|---|---|---|---|---|---|
| `qwen3:14b` (control) | either | 1.01 | 99.1% | 0.0% | 101% | 12.8% | 0 |
| `qwen3:4b` | constrained | 0.95 | 92.5% | 0.0% | 89% | 13.6% | 0 |
| `qwen3:8b` | unconstrained | 0.62 | 62.5% | 0.0% | 62% | 22.1% | 0* |

\* 0 hard schema failures only because a tolerant parser recovers *something*; 3 of 8 draws
yield a single entity out of 40.

Paired bootstrap, `qwen3:4b` vs control (10k resamples): **Δ ent/subj −0.056 [−0.162, +0.025]**
(CI crosses zero — not distinguishable), **Δ coverage −6.6 pp [−11.2, −2.5]** (real).

**Verdict against pre-registered thresholds: `qwen3:4b` = SOFT FAIL.** Coverage is 93% of
control against a 95% bar, and Decision recall is below control. Interpretation, fixed in
advance: viable, but wants a judged set before adoption.

## Cost, measured

| model | wall/entry | prefill | decode | out tok | decode rate | prefill share |
|---|---|---|---|---|---|---|
| `qwen3:14b` | 60.4 s | 0.96 s | 59.1 s | 2420 | **41 tok/s** | 2% |
| `qwen3:8b` | 41.3 s | 0.86 s | 39.1 s | 2507 | 64 tok/s | 2% |
| `qwen3:4b` | 28.3 s | 0.31 s | 27.8 s | 2648 | 95 tok/s | 1% |

**Prefill is 1–2% of wall time, not the 41% originally derived or the 12–30% corrected to.**
At this entry size the model emits ~2,500 tokens against a ~1,260-token prompt, so decode
dominates completely. This is a *regime* difference, not a contradiction: these are
40-subject entries, far larger than a typical capture.

**These absolute times are not comparable to §1.5's ~18 s/entry** — different entry size,
different output volume. What they do corroborate is the decode-bandwidth figure: 41 tok/s ×
9.3 GB ≈ 381 GB/s against the ~350 GB/s the rebuilt cost model assumed.

## Four findings beyond the ladder

1. **`format: "json"` is a measured hazard, not a free safety net.** Under grammar-constrained
   decoding `qwen3:8b` failed 3 of 8 draws — one degenerating into a newline stream, two
   running away to the token cap emitting duplicate keys (`...-clarified-clarified`). Re-running
   those exact seeds with only `format` removed: all three completed normally. Constrained
   decoding pushing a model into a repetitive state is a known effect; here it hit exactly one
   rung. **Anything shipped must either avoid it or verify per-model that it does not induce
   degeneration** — including `qwen3:14b`, which survived these eight draws and is not thereby
   proven immune at other entry sizes.

2. **#24's Decision-collapse did not reproduce.** The control emitted ~7 Decisions from ~7
   decision-shaped subjects — **100–101% recall**, not the documented "7 subjects yield exactly
   1 Decision at every size." Either #24's corpus differed materially, or the collapse was a
   property of its prompt rather than of the model — and #24 flagged its own prompt as an
   unvalidated placeholder that also fabricated entities from its example keys. **This matters
   because the argument that "the 14b is already at the floor on Decisions, so a smaller model
   costs little there" rests on the collapse being real.** It did not survive contact with a
   different prompt.

3. **§13.4's 0.7 confidence threshold is inert.** Across 626 emitted entities, **not one** scored
   below 0.7; mean 0.92 on the control, and `qwen3:8b` returned exactly 1.000 on every entity it
   emitted. As specified, the `ambiguous` Type Suggestion channel would never fire and
   `review_schema`'s histogram would be a single bar. The threshold I set this morning as a
   labelled starting point is measurably wrong — which is the §13.4 mechanism working as intended,
   on its first contact with data.

4. **Output-envelope instability is a real integration cost.** Three distinct shapes appeared
   across the ladder, all carrying valid content: `{"entities": [...]}` (14b, 4b), a bare
   `[{...}]` (8b, 5 draws), and `[{"entities": [...]}]` (8b, 3 draws — and malformed past a
   point, recovering 1 entity of 40). The scoring harness needed three revisions to handle
   this, and **a production runner would face exactly the same problem.** "Swap the enrichment
   model" is not a configuration change; it is a per-model integration task with its own
   parsing and decoding tuning.

## What this does and does not answer

**Does:** on synthetic text, at a ceiling-sized entry, `qwen3:4b` recovers ~94% of the control's
entities and ~93% of its subject coverage with zero fabrication — at **2.1× the speed**. That is
a real option, and it makes the ladder worth pursuing on the Fedora box independent of #32.

**Does not:** this is not a judged set. It measures extraction recall and composition on
synthetic subjects with a reconstructed prompt, not retrieval quality on real memory. §13.1's
open question stands. A SOFT FAIL licenses further work, not adoption.

**Methodological caveat, stated plainly:** the harness produced three wrong answers before this
one — a VRAM-contention artifact, a grammar-induced degeneration misread as model instability,
and two envelope-shape misparses. Each was caught by inspecting raw output rather than trusting
a summary statistic. The pre-registered criteria did their job; the instrument needed three
revisions to be worth applying them to.
