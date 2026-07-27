# Pass/fail criteria — fixed before any model was run

**Written and committed before the first arm executed.** This exists so the ladder result
cannot be rationalised after the fact. Issue [#32](https://github.com/markdlabrecque/tome/issues/32) follow-up; method from the design in
`research/macos-spike-inference.md` §19.9.

## The question

`qwen3:14b` was chosen in #8 because it *"fits comfortably within 16GB VRAM"* — a
ceiling-fit, never an argument that 14b is the **minimum** for extraction quality. Is a
smaller model good enough?

## Design

- **Corpus:** 80 synthetic subjects (`corpus.py`), committed. 14 are Decision-shaped, so a
  40-subject draw carries ~7 — the regime in which #24 measured its Decision invariant.
- **Paired draws:** 8 draws of 40 subjects, `random.Random(seed)` with fixed seeds 0–7.
  **Identical draws across every arm.** Pairing removes between-draw composition variance,
  which is why 8 draws suffice where unpaired would need ~12.
- **Arms:** `qwen3:14b` (control), `qwen3:8b`, `qwen3:4b`, and `gpt-oss:20b`.
- **Held fixed across arms:** prompt bytes, draw contents and order, `temperature: 0`,
  `num_ctx: 16384`, `num_predict: 1500`, thinking disabled, one runtime (Ollama, Q4_K_M
  where applicable). Anything that differs between arms other than the model is a bug.
- **`gpt-oss:20b` is a control, not a candidate.** It tests harvest item 8 — the claim that
  §1.5's ~18 s/entry was measured on it rather than on `qwen3:14b`. If it reproduces ~18 s
  while `qwen3:14b` does not, that correction stops being token arithmetic and becomes a
  measurement.

## Amendment, made before any scored arm ran

A single smoke call (`qwen3:4b`, seed 0) exposed two defects in the design above. Both are
fixed here rather than silently in code.

1. **`num_predict: 1500` truncates.** The call returned `done_reason: length` at the cap.
   Forty subjects need roughly 3,000 output tokens. **Raised to 4,096.** The original number
   came from §19.9 and was simply too small for this regime.
2. **`think: false` alone does not yield clean JSON on the small model** — it emitted a
   reasoning preamble, the exact failure §4.9 records for `qwen3:14b`. **Added Ollama's
   `format: "json"`**, which constrains output syntax.

**Consequence for outcome 7, stated plainly:** `format: "json"` makes syntactic parse
failure impossible, so that metric is now near-vacuous. It is replaced by **schema
failures** — valid JSON of the wrong shape (missing `entities`, missing required fields,
wrong types). The change is deliberate and it *favours the smaller models*: without it, a
small model would be penalised for a formatting problem that any real implementation fixes
for free, which would answer a question nobody is asking. It also mildly departs from #24,
which measured 0/160 syntactic parse failures at 14b unconstrained.

**Disclosure:** that smoke call was `qwen3:4b` on seed 0 — one of the 32 cells — and it
returned 40 entities from 40 subjects. This is disclosed because it happened before the
thresholds were finalised. It does not compromise the pre-registration: **every threshold
is relative to the `qwen3:14b` control, and no control arm had been run at that point**, so
an absolute count from one non-control cell carries no information about pass or fail.

## Second amendment: `format: "json"` reverted — it was the confound

**Made after a first full run, before that run was scored as a result.** The first run is
retained as `raw-contended.jsonl.bak` / `raw.jsonl`; the scored result comes from
`raw-unconstrained.jsonl`.

The first amendment added `format: "json"` and argued it *favoured* the small models. **It
did the opposite, and specifically to one arm.** Under grammar-constrained decoding
`qwen3:8b` failed 3 of 8 draws in two ways: seed 1 degenerated into a stream of newline
tokens (`done_reason: None`, no `eval_count`), and seeds 5 and 7 ran away to the 4,096-token
cap while re-emitting duplicate entities with corrupted keys (`...-clarified-clarified`).
`qwen3:14b` and `qwen3:4b` were unaffected.

**Re-running those exact three seeds with `format` removed and everything else identical:
all three completed normally** — `done_reason: stop`, 2,286 / 2,656 / 2,303 tokens, no
degeneration, no runaway. So the failure was **induced by the JSON grammar mask**, not a
property of the model. Constrained decoding pushing a model into a repetitive state is a
known effect; this is an instance of it, and it landed on exactly one rung of the ladder.

Had this been scored as reported, `qwen3:8b` would have been recorded as a **HARD FAIL**
with 6/8 schema failures — a wrong conclusion, produced by the harness, about the single
most decision-relevant arm.

**Reverted to unconstrained decoding**, which is also what #24 used and therefore restores
comparability. Outcome 7 returns to its original meaning, with one change: extraction uses a
**lenient parser** (first balanced `{...}`, tolerating a reasoning preamble or a markdown
fence), because a model that wraps good JSON in prose has a formatting problem a real
implementation solves trivially — which is the thing the first amendment was right to want
and wrong about how to get.

**Generalisation worth keeping:** whichever way the ladder lands, `format: "json"` is now a
measured hazard on this task rather than a free safety net. Anything shipped should either
avoid it or verify per-model that it does not induce degeneration.

## Counted outcomes

1. **entities/subject** — primary recall proxy.
2. **distinct natural keys** — collapse detection (two subjects merged onto one key).
3. **marker coverage** — fraction of the 40 drawn subjects whose distinctive marker appears
   in some emitted key or summary. Recall, independent of how the model chose to split.
4. **fabrication rate** — emitted entities whose key matches no drawn subject's marker,
   plus any emission of the schema's placeholder strings.
5. **Decision recall** — Decisions emitted ÷ Decision-shaped subjects drawn. #24 measured
   this collapsing to ~1 regardless of input count.
6. **Fact share** — junk-drawer signal. §4.9 predicts a rising `Fact` share is the failure
   signature when `_Avoid_` discrimination degrades.
7. **parse failures** — responses that are not valid JSON of the required shape.
8. **`type_confidence` distribution** — against §13.4's *unmeasured* 0.7 starting value.
9. **timing** — `prompt_eval_count`/`_duration`, `eval_count`/`_duration` per call.

## Thresholds, relative to the `qwen3:14b` control

A smaller model **PASSES** if, across the 8 paired draws:

- **entities/subject ≥ 90%** of control, AND
- **marker coverage ≥ 95%** of control, AND
- **fabrication rate** no worse than control by more than **2 percentage points**, AND
- **parse failures ≤** control's, AND
- **Decision recall** not worse than control's, AND
- **Fact share** no more than **5 percentage points** above control.

**SOFT FAIL** — 80–90% on entities/subject, or 90–95% marker coverage, with every other
criterion met. Interpretation: viable but wants a judged set before adoption.

**HARD FAIL** — any of: entities/subject < 80% of control; marker coverage < 90%; any
parse failure where the control had none; fabrication worse by > 5pp; Decision recall
below control; Fact share > 10pp above control.

**A smaller model may score HIGHER.** This is explicitly allowed and would itself be a
finding — #24 observed that on Decisions the 14b is already at the floor (1 of 7 at every
size tested), so the large model may not be buying what under-extraction is about. A
smaller model beating the control is reported as such, not treated as an anomaly.

## Statistics

Report the **paired bootstrap 95% CI** on the per-draw difference from control (10,000
resamples), the same shape §10.4 specifies for the judged set. A single run carries roughly
±15% Poisson noise on entity counts; pairing plus 8 draws is what makes a ~10% difference
readable.

## What this probe cannot answer

It measures **extraction recall and composition on synthetic text**. It does not measure
retrieval quality, and it is not a judged set — §13.1's open question needs 90 days of real
usage and remains open regardless of the outcome here. A PASS licenses trying a smaller
model, not skipping the eventual judged set.
