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

---

# Third amendment: the #36 prompt-fence A/B

**Written and committed before the fenced arm ran.** Issue
[#36](https://github.com/markdlabrecque/tome/issues/36) proposes adding `_Avoid_` lines to
the entity types that lack them, and predicts a measurable gain in classification accuracy.
This section fixes how that gain is measured, and records what the baseline actually says —
which is not what #36 says it says.

## The instrument had no type-accuracy scorer

`analyze.py` scores recall and composition. **It never scored classification against
ground truth.** #36's confusion table was produced ad hoc during the spike and was never
committed, so it could not be re-run. `type_accuracy.py` is added here to close that gap,
and its first job was to reproduce the published table from the committed raw JSONL.

## What reproduces, and what does not

Scoring `raw.jsonl` (grammar-constrained; the configuration in which both `qwen3:14b` and
`qwen3:4b` ran clean):

- **The accuracies reproduce exactly** — 95.6% / 89.2% — under one specific matching
  scheme: `analyze.py`'s coverage loop, where each drawn subject takes its best-overlapping
  emitted entity and reuse is allowed. That pins the scheme #36 used.
- **The confusion table does not reproduce.** Under that same scheme the wrong arrivals
  total **46**, not 31: Fact 17, Project 12, Person 8, Preference 3, Event 3, Decision 2,
  Commitment 1. #36's "Decision 0, Commitment 0 — the two types with the sharpest `_Avoid_`
  wording absorb none at all" is false; they absorb 2 and 1.

## The matching scheme inflates the error count, and it does so unevenly

Allowing reuse lets a subject the model **omitted entirely** match some *other* subject's
entity, which is then scored as a misclassification. Splitting the errors by overlap
separates the two failures:

- **Overlap ≥ 0.6** — the model emitted an entity for *this* subject and gave it the wrong
  type. A real misclassification. **36 of the 46.**
- **Overlap < 0.6** — the subject's best match is a different subject's entity. An
  **omission**, wearing a misclassification's clothes. **10 of the 46**, and *8 of those 10
  land on Person* (`team-restructure` matching `sora-nakagawa` at 0.29, `api-clients`
  matching `rafe-quillon` at 0.29).

**Consequence for #36's central claim.** Restricted to real misclassifications, the
destinations are **Fact 17, Project 11, Preference 3, Decision 2, Event 2, Commitment 1 —
and Person 0.** Person is not a confusion sink; its six arrivals in #36 were omissions.
The claim that the three unfenced types are *exactly* the three sinks is **two-thirds
right**: Fact and Project absorb 28 of 36 (78%), the four fenced types absorb 8, and Person
absorbs none.

Two further splits #36's summing hides:

- **Project is a `qwen3:4b` phenomenon.** All 12 Project arrivals are 4b's; the control has
  none in the constrained run and two in the unconstrained one.
- **At `qwen3:14b` — the model actually being shipped — there are 10 real
  misclassifications, and `Event → Fact` is 6 of them.** Essentially the whole error budget
  of the shipping model is one confusion.

`Event → Fact` is the one finding that survives every cut: top error at both model sizes
(6 at 14b, 8 at 4b), and it **replicates across decoding configurations** — 5 at 14b in
`raw-unconstrained.jsonl`, scored independently. That is what the fence is aimed at.

## The change under test

`prompt-fenced.txt`, diffed against `prompt.txt`. Three edits, no others:

1. **`Fact` gains an `Avoid: Event` line** plus one operational clause — *"Choose Fact only
   after every other type has been ruled out"* — which is what "a catch-all, not a default"
   has always meant and never said in a form a model can act on.
2. **`Project` gains an `Avoid: Event` line.**
3. **`Event`'s definition gains one clause:** *"A completed occurrence remains an Event; it
   does not become a Fact once it is over."* Aimed directly at the measured failures, which
   are past occurrences read as settled state.

**`Person` deliberately gains nothing**, against #36's item 1. It has zero real arrivals at
either model size, so a fence there would be written against a confusion that has never been
observed — unfalsifiable by this instrument, and it would dilute the lines that do carry
weight. If the corpus is later extended and Person arrivals appear, this is revisited.

**Worked examples use scenarios absent from the corpus** (a ticketing system, an office
move). Quoting a corpus subject in the prompt would teach to the test — the defect #24's
prompt had, where example keys were fabricated back out as entities. Checked
mechanically: no corpus subject shares more than two content words with the added text.

## Held fixed

Corpus, the eight seeds and their draw contents and order, `temperature: 0`,
`num_ctx: 16384`, `num_predict: 4096`, `seed: 42`, `think: false`, `keep_alive: 0`, Ollama
on the same box. **The prompt bytes are the only thing that differs.** The fenced prompt is
~90 tokens longer, which is a confound only for cost, and cost is not what is being claimed.

Both arms run **grammar-constrained**, matching `raw.jsonl`, because that is the only
configuration in which both models produced scorable output. `qwen3:14b` additionally runs
**unconstrained**, matching `raw-unconstrained.jsonl`, so the headline claim has a
replication rather than a single cell. `format: "json"` remains a measured hazard
(second amendment) and its output is checked for degeneration rather than assumed clean.

## Pre-registered thresholds

The change **PASSES** if, against the same-arm baseline:

- **`Event → Fact` falls at both arms**, and falls in the 14b unconstrained replication; AND
- **type accuracy on confidently-matched subjects (overlap ≥ 0.6) rises at both arms**; AND
- **the errors are removed, not relocated** — no single new confusion appears at a count
  greater than the reduction in `Event → Fact`; AND
- **recall does not pay for it**: `analyze.py` coverage falls by no more than 2 pp and
  ent/subj by no more than 0.05 at either arm.

**PARTIAL** — `Event → Fact` falls and accuracy rises at 14b but not at 4b, or accuracy
rises while recall degrades within the bounds above. Interpretation: keep the Fact fence,
re-examine the others.

**FAIL** — `Event → Fact` does not fall at 14b, or total real misclassifications rise at
either arm, or recall breaches the bounds. Interpretation: the fence is not the mechanism,
and #36's premise is wrong rather than merely overstated.

**A result where accuracy rises but `Fact` share does not fall is explicitly interesting**
rather than contradictory: §4.9 treats rising Fact share as the junk-drawer signature, and
this probe can now say whether that signature tracks classification error or is independent
of it.

---

# Fourth amendment: the run is not deterministic, so the A/B becomes repeated-measures

**Written after the first fenced run, before it was scored as a result.** The third
amendment assumed what the original probe assumed: that `temperature: 0` plus a fixed
`seed` makes a cell reproducible, so one run per condition is a measurement. **A control
replication falsified that**, and it has to be recorded before any fenced number is quoted.

## What the replication showed

`raw-control-replication.jsonl` re-runs the **unchanged** `prompt.txt` at `qwen3:14b`,
same eight seeds, same options, same box, minutes later. Against `raw.jsonl`:

| metric | first run | replication | Δ |
|---|---|---|---|
| `Event → Fact` | 6 | 3 | **−3** |
| real misclassifications | 10 | 9 | −1 |
| coverage | 99.1% | 97.8% | −1.2 pp |
| `Fact → Project` | 0 | 2 | +2 |

**Nothing changed but the wall clock.** So run-to-run noise on `Event → Fact` is at least
±3 — the same magnitude as the effect the fence is meant to produce — and the −1.6 pp
coverage change the fenced run showed is inside the noise the control produces on its own.
Ollama on this stack is not bit-reproducible across model loads (`keep_alive: 0` reloads
every call, and reduction order on the GPU is not pinned); `seed` fixes sampling, not
kernel scheduling. **A single paired run cannot support a claim about a 3–6 count
difference**, which is exactly what the third amendment's thresholds asked it to do.

## The second hazard, resurfaced

`qwen3:4b`, fenced, **seed 3 degenerated**: `done_reason: length` at the 4,096-token cap,
**1 usable entity from 40 subjects**. Seed 5 over-split into 60 entities at 3,915 tokens.
This is the `format: "json"` degeneration the second amendment measured on `qwen3:8b` —
now on `4b`, under a prompt ~150 tokens longer. That one draw *is* the entire −10 pp
coverage collapse in 4b's fenced column; the other seven draws improve on baseline.

**It is a decoding hazard, not a fence effect** — but it is a real cost of a longer prompt
under constrained decoding and it must be reported as an outcome, not filtered away.

## Revised design

**Three independent replicates of each condition**, same eight seeds within each, all
constrained, all on this box back to back:

| condition | replicates |
|---|---|
| `qwen3:14b` control | `raw.jsonl`, `raw-control-replication.jsonl`, + 1 more |
| `qwen3:14b` fenced | `raw-fenced.jsonl` + 2 more |
| `qwen3:4b` control | `raw.jsonl` + 2 more |
| `qwen3:4b` fenced | `raw-fenced.jsonl` + 2 more |

**Revised thresholds, replacing the third amendment's:**

- The effect is read as **the difference between condition means across replicates**, and it
  counts only if **the fenced range and the control range do not overlap** on
  `Event → Fact`. Non-overlap across three replicates is a weak test, and it is stated as
  weak — but it is honest about the noise floor, which a single paired run was not.
- **Recall guard is now judged on non-degenerate draws, with degeneracy reported
  separately**: a draw with `done_reason: length` or yielding < 10 entities from 40 subjects
  is counted as a **degenerate draw** and excluded from coverage and accuracy, and the
  **count of degenerate draws per condition is itself a reported outcome**. Rationale: a
  degenerate draw measures the decoder, not the prompt's discrimination, and pooling the
  two produced a −10 pp "recall collapse" that dissolves on inspection. Excluding it
  without reporting it would be the opposite error.
- **A prompt that raises the degenerate-draw count is penalised on that axis directly**,
  and that penalty is not offset by better classification. Under constrained decoding the
  fenced prompt is ~150 tokens longer and this is the axis where that could cost something.

**What this cannot become:** three replicates is enough to see whether an effect clears the
noise floor. It is not enough to put a confidence interval on the effect size, and no
interval derived from it should be quoted as though it were.

---

# Fifth amendment: determinism is model-dependent, so the replicate counts differ per arm

**Written before the fence result was reported.** The fourth amendment said the probe is not
reproducible. That is true of `qwen3:14b` and **false of `qwen3:4b`**, and the difference
changes how many independent observations each arm actually has.

Hashing the response payloads of every replicate:

| arm | condition | distinct payloads across 3 replicate files |
|---|---|---|
| `qwen3:14b` | control | **3 of 3** |
| `qwen3:14b` | fenced | **3 of 3** |
| `qwen3:4b` | control | **2 of 3** (`raw-control-4b-r2` and `-r3` are byte-identical) |
| `qwen3:4b` | fenced | **1 of 3** (all three byte-identical) |

`qwen3:4b` reproduces bit-exactly within a session; `qwen3:14b` does not, on the same box,
same options, minutes apart. Plausibly the larger model's layer split or reduction order
varies across loads in a way the smaller one's does not — but the cause is not measured here
and should not be asserted.

**Consequences, stated rather than buried:**

1. **At `qwen3:14b` the design works as intended.** Three independently generated runs per
   condition. Their aggregate metrics happen to coincide exactly in the fenced condition,
   which looks like duplication and is not: the per-seed `(entity_type, natural_key)`
   signatures differ on 3 of 8 seeds. Independent draws landing on the same totals.
2. **At `qwen3:4b` replication within a session is uninformative.** Re-running cannot
   produce a new observation, so the fenced condition rests on **one** independent
   observation and the control on **two** — `raw.jsonl` from the earlier session
   (`Event → Fact` 8) and tonight's (10). Those two are the only available estimate of that
   arm's run-to-run spread, and two counts is not a noise floor.
3. **More 4b replicates would be theatre.** Genuine independence there needs the server
   restarted between runs, which requires privileges this harness does not have, or a config
   change, which breaks comparability. Neither is worth it: the 4b arm is not the shipping
   model, and its effect size is far larger than its observed spread.

**So the 4b result is reported as directional and the 14b result as measured.** Any future
run of this probe should hash payloads before treating replicate count as sample size.

---

# Sixth amendment: determinism varies by *prompt*, not only by model

The fifth amendment concluded determinism is model-dependent — `qwen3:4b` bit-exact,
`qwen3:14b` not. The #35 replicates show that was still too narrow.

Hashing `qwen3:14b`'s response payloads across two replicates of each #35 condition:

| condition (all `qwen3:14b`) | r1 vs r2 |
|---|---|
| control prompt, gated | **different** (`1ef2d322` / `9ace68cf`) |
| control prompt, unconditional | **different** (`1330411d` / `3a7ece2a`) |
| fenced prompt, gated | **identical** (`b51e79d1`) |
| fenced prompt, unconditional | **identical** (`a92b1d0b`) |

Same model, same box, same options, same corpus — and the **fenced** prompts reproduce
bit-exactly while the control prompts do not. Note this is the *opposite* of what the same
model did on `corpus.py`, where three fenced replicates produced three distinct payloads.

**So determinism is a property of the whole configuration — model × prompt × corpus — and it
is not predictable from any one of them.** The practical rule stands and generalises:

> **Hash the payloads. Replicate *files* are not replicate *observations*, and which
> conditions happen to be reproducible cannot be guessed in advance.**

Consequence for #35's numbers: the control-prompt arms carry two independent observations
each and the fenced arms carry one. Reported that way.
