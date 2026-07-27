# Confidence scoring — how to run `confidence.py` and how to read it

The scorer for [#35](https://github.com/markdlabrecque/tome/issues/35), against
`corpus_ambiguous.py`. `analyze.py` reports recall and composition; `type_accuracy.py`
reports classification; neither says anything about `type_confidence` beyond a mean and a
count below 0.7. This one exists because that mean is the whole of #35's problem: **0 of 626
entities scored below 0.7**, and a single unstratified corpus cannot say whether the models
are miscalibrated or the corpus was too easy.

**The measurement is the separation between strata.** Not the level on any one of them. Every
table splits by stratum for that reason, and a number pooled across the four is meaningless —
40 of the corpus's 100 subjects are contested by construction, which is a design parameter
and not an estimate of anything.

## The `run.py` change this needs

`run.py` currently hard-codes `from corpus import SUBJECTS`, so it cannot produce a draw over
`corpus_ambiguous.py`. **This is the only change required**; `note_from` uses `SUBJECTS[i][2]`
and `draw` uses `len(SUBJECTS)`, both of which the six-field `Subject` NamedTuple supports
unchanged.

```diff
--- a/research/ladder-probe/run.py
+++ b/research/ladder-probe/run.py
@@ -4,11 +4,13 @@
 Criteria are fixed in CRITERIA.md, committed before this ran. This script counts nothing
 and judges nothing — it only calls models and records what came back.
 """
-import json, os, random, sys, time, urllib.request
+import importlib, json, os, random, sys, time, urllib.request
 from pathlib import Path
 
 sys.path.insert(0, str(Path(__file__).parent))
-from corpus import SUBJECTS
+# Corpus is switchable so the #35 ambiguous probe reuses this runner unchanged.
+# The default reproduces every committed run exactly.
+SUBJECTS = importlib.import_module(os.environ.get("CORPUS", "corpus")).SUBJECTS
```

Applied to a scratch copy and executed: with `CORPUS` unset, `len(SUBJECTS)` is 80 and
`draw(3)` is identical to the committed runs; with `CORPUS=corpus_ambiguous`, `len(SUBJECTS)`
is 100 and one draw renders a 40-line, 3,701-character note against 3,692 for `corpus.py` —
the 2% growth `AMBIGUOUS-CORPUS.md` predicted. Nothing else in `run.py` is touched.

`confidence.py` warns if a JSONL file contains no subject index ≥ 80, because that is what a
run against `corpus.py` looks like and every stratum label would otherwise be silently wrong.

## Running it

```bash
cd research/ladder-probe

# collect — one file per replicate, same eight seeds inside each
CORPUS=corpus_ambiguous OUT=raw-amb-14b-r1.jsonl ARMS=qwen3:14b python3 run.py
CORPUS=corpus_ambiguous OUT=raw-amb-14b-r2.jsonl ARMS=qwen3:14b python3 run.py
CORPUS=corpus_ambiguous OUT=raw-amb-14b-r3.jsonl ARMS=qwen3:14b python3 run.py

# score
python3 confidence.py amb=raw-amb-14b-r1.jsonl,raw-amb-14b-r2.jsonl,raw-amb-14b-r3.jsonl
```

A bare filename becomes a condition named after its stem; several comma-separated files in
one condition are replicates of it. `--model M` restricts the arms, otherwise every model
present in the files is reported separately. Two conditions can be compared side by side —
`plain=…` against `fenced=…` — which is how the `fence` stratum's second question (does the
#36 fence *remove* the ambiguity or *relocate* it?) gets asked.

**At least two replicates per condition.** One replicate still produces every table, and the
scorer says so in §2, but the across-replicate range is undefined and CRITERIA.md's fourth
amendment asks for repeated measures before a small difference is quoted.

## What each section means

**§0 Draw accounting.** Draws, degenerate draws, entities, paired entities, unmatched
entities, and entities that carried no numeric `type_confidence` — per replicate.

- A **degenerate draw** is `done_reason: length` or fewer than 10 entities from 40 subjects.
  It is excluded from every other table and reported here as an outcome in its own right,
  exactly as CRITERIA.md's fourth amendment requires. A condition that raises this count is
  penalised on that axis directly and the penalty is not offset elsewhere.
- An **unmatched entity** paired with no drawn subject under `type_accuracy.pair` — the same
  greedy one-to-one content-word pairing at `COVER_T = 0.25` that `type_accuracy.py` uses.
  It therefore has no stratum and no ground truth, so it is counted and scored nowhere.
  Only paired entities appear below.

**§1 Distribution by stratum.** n, mean, median, p10/p25/p75, min, and the fraction below
0.7 / 0.8 / 0.9 / 0.95 / 1.0, for `ambiguous`, `control-matched`, `control` and `fence`
separately. Read the `<0.7` column against the ladder's 0 of 626: if it is still zero on the
`ambiguous` row, the numeric route is in trouble on data built to break it.

The `pairing` column is the share of drawn subjects an entity could be matched to. Watch it:
if `ambiguous` pairs at a markedly lower rate than `control-matched`, the confidence
distributions are conditioned on different selection and the separation below is partly a
selection effect.

**§2 Separation.** Every contrast is computed **within a draw** and then averaged over draws,
so a draw that runs globally high or low cancels out of the difference. Four contrasts:

| contrast | what it is |
|---|---|
| `ambiguous − control-matched` | **the headline.** Length, clause count and register are held fixed, so what is left is the type contest |
| `ambiguous − control` | the same against the short controls. If this gap is much the larger, the surplus is length sensitivity |
| `control-matched − control` | length sensitivity measured directly, on subjects whose type nobody disputes |
| `fence − control-matched` | reported, never part of the headline — `prompt-fenced.txt` may resolve those subjects by prompt rather than by model |

**§3 `considered_types`.** #35 item 2's alternative trigger, and the ticket's most promising
line. Per stratum: how often it is non-empty, how many types it names, and — for `ambiguous`
and `fence`, which carry a known competing pair — how often it contains `alt`.

- **`contains alt`** is the design note's statistic: the model named the specific competitor
  the corpus says exists.
- **`names the unchosen pair member`** is the stricter reading. When the model emits `alt` as
  its `entity_type`, naming `alt` again is self-reference, not hesitation; this column asks
  whether it named the member of `{gold, alt}` it did *not* choose. Entries restating the
  entity's own `entity_type` are dropped before any counting, on all strata equally.
- On `control-matched`, a non-empty `considered_types` is a **false positive** — same length,
  same clause count, no contested type. That is the specificity half, and it is why the
  matched stratum earns its place beyond answering the length confound.
- `alt` is ground truth and unavailable at runtime. The `alt` columns diagnose the signal's
  *quality*; only **non-empty** is a deployable trigger.

**§4 Trigger sweep.** For each candidate threshold and each `considered_types` rule: what it
fires on in `ambiguous` (true positives), in `control-matched` and `control` (false
positives), and in `fence` (information only). This is the direct answer to #35 item 1 — read
down the `type_confidence` rows and see whether *any* threshold buys sensitivity without
buying the controls with it. If every row is either 0/0 or 100/100, no numeric threshold
separates the strata and the numeric route is unsalvageable rather than mis-set.

Denominators differ by row and are printed: `type_confidence` rows count only entities that
carried a numeric one; `considered_types` rows count every paired entity.

## Reading separation against a noise floor

A separation means nothing until it is read against what this instrument returns when there
is nothing to find. CRITERIA.md's fourth amendment established why: a control replication of
an *unchanged* prompt moved `Event → Fact` by 3 with nothing changed but the wall clock.

Two floors are computed, and both should clear before a separation is quoted.

**The placebo split-half** is the primary one, and it is available from a single run. Each
control stratum is cut deterministically into interleaved halves and contrasted with itself,
within-draw, using the identical arithmetic. Its true value is **zero**, so whatever it
returns is this instrument's own noise on this statistic — sampling noise from ~4–5
observations a side per draw (40 of 100 subjects are drawn, so a 20-subject stratum yields
about 8, and a half of it about 4), averaged over the draws, plus whatever the decoder
contributes. A draw where either half came up empty is dropped from that contrast and the
usable draw count is printed. §2 prints the band spanned by all
placebo contrasts and marks each real contrast **outside the floor** or not.

**The across-replicate range** is the second. Every contrast is printed per replicate with
its `[min–max]`, and the per-replicate stratum means are printed separately so the run-to-run
drift in the *levels* can be told apart from drift in the *differences* — the within-draw
difference should cancel most of the former, and that table is how you check it did.

A contrast is readable when its across-replicate range sits wholly outside the placebo band.
That is the same weak, honest test `compare_replicates.py` applies, and it is stated as weak:
non-overlap over three replicates shows an effect clears the noise floor. It does not put an
interval on the effect size, and no interval derived from it should be quoted as though it
were.

If `ambiguous − control-matched` is inside the floor, that is evidence for #35's explanation
**(a)** — high confidence regardless of genuine ambiguity — and the numeric route is
unsalvageable, not mis-set. If it clears the floor, explanation **(b)** survives and the
threshold is merely wrong. Either way, see the next section for what the number still cannot
do.

## What this cannot answer

In the register of `CRITERIA.md`'s section of the same name, and additional to
`AMBIGUOUS-CORPUS.md`'s, which all still apply to anything scored here.

- **It cannot set §13.4's threshold.** If separation is observed, its size is a property of
  this corpus's deliberately concentrated ambiguity — 40 contested subjects in 100 is a design
  parameter, not a prevalence estimate. §4's sweep says which thresholds separate *these*
  strata. It does not say what number belongs in the PRD, and the sweep's best row is
  arithmetic over the draws in front of it, not a recommendation. The scorer labels it so.
- **It cannot show the low confidence lands on the right items.** Each subject appears in
  about 3.2 of 8 draws, so per-item confidence rests on roughly three observations per model.
  A separation is consistent with a model uncertain about something else correlated with
  ambiguity — and `AMBIGUOUS-CORPUS.md` names the specific residual confound: the ambiguity
  devices favour certain constructions, and the matched controls do not reproduce them,
  because reproducing them is what creates ambiguity.
- **It cannot settle #35 item 3.** Whether a near-constant `type_confidence` column earns its
  place in §5.7's histogram depends on the shape of that histogram under *real* notes.
  Nothing here observes real notes.
- **It cannot touch #35 item 4 at all.** §3.3's stickiness margin (`incumbent + 0.20`) governs
  re-typing an entity on a *later* extraction. Single-pass draws produce no second extraction
  of the same entity, so type stickiness stays inert-by-argument. That may be the more
  consequential of the two knobs and it needs a different probe.
- **The `considered_types` result is a measurement of a prompt, not of a capability.** Both
  prompts ask for the field, and `prompt.txt` ties it explicitly to "below 0.7" — so a model
  that never goes below 0.7 has been told, in the same breath, not to populate it. A low fire
  rate on `ambiguous` is therefore ambiguous itself between the model and the instruction, and
  distinguishing them needs a prompt variant that asks for alternatives unconditionally. That
  variant does not exist yet.
- **Ground truth is unadjudicated.** `gold`, `alt` and `verdict` are one author's judgments.
  The `contains alt` columns inherit that error bar in full.
- **It prints no verdict.** The scorer reports distributions, differences and floors. Deciding
  #35 — recalibrate, switch trigger, or retire the field — is a human reading of those
  numbers, and CRITERIA.md's habit is that the reading gets written down before the run, not
  after.

## Verification

The scorer was checked against a synthetic JSONL fixture with constructed confidences and
`considered_types`, built outside the repo — including a constant-1.000 arm standing in for
`qwen3:8b`, two degenerate draws, unmatched entities, entities missing `type_confidence`, and
self-referential `considered_types` entries. Every count, distribution, contrast and placebo
value it reported matched the values the fixture was built to contain. No model has been run
against `corpus_ambiguous.py` yet, and no number in this document comes from one.
