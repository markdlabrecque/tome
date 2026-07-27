# Pass/fail criteria for the #35 confidence probe — fixed before any arm was run

**Written and committed before the first ambiguous-corpus arm executed.** Same discipline as
`CRITERIA.md`, and a separate file because this is a different question sharing the same
harness: `CRITERIA.md` asks whether a smaller model extracts well enough, this asks whether
`type_confidence` can gate anything.

Issue [#35](https://github.com/markdlabrecque/tome/issues/35). Corpus: `corpus_ambiguous.py`
(100 subjects, four strata). Scorer: `confidence.py`. Both committed before this ran.

## The question

The ladder probe emitted **626 entities and not one scored `type_confidence` below 0.7**
(means 0.915 / 0.945 / 1.000 by model). §13.4's threshold never fires, so §4.9's `ambiguous`
Type Suggestion is unreachable, §5.7's histogram is a single bar, and the schema-review loop
has no input. But that corpus was written as unambiguous exemplars, so it cannot separate:

- **(a)** the models are badly calibrated and report high confidence regardless of genuine
  ambiguity — the numeric route is unsalvageable; from
- **(b)** the corpus was too easy — the threshold is merely mis-set.

**The measurement is the separation between strata, never the absolute level.**

## A confound found while building the scorer, which reshapes the design

`prompt.txt` says:

> *If several types fit plausibly and your confidence is below 0.7, still pick the best
> type, but record the alternatives in considered_types.*

**`considered_types` is gated on the very threshold that never fires.** So the ladder probe
could not have observed a populated `considered_types` no matter how ambiguous the input —
the field was instructed to stay empty. #35's item 2 proposes `considered_types` as the
*alternative* to the numeric threshold, and as specified the two are **coupled by
construction**: the alternative cannot be evaluated while the thing it replaces gates it.

This is a defect in the prompt, not in the model, and it means the prompt axis #35 needs is
**gated vs unconditional**, not control vs fenced. `prompt-unconditional.txt` and
`prompt-fenced-unconditional.txt` replace the clause with one that asks for every type
weighed, whatever the confidence, and asks for an empty field when only one type was in play
— which is what makes a false-positive rate measurable.

## Design

**2 × 2 × 2**, eight draws each, all constrained, all on the Fedora box back to back:

| axis | levels |
|---|---|
| fence | `prompt.txt` / `prompt-fenced.txt` |
| `considered_types` | gated / unconditional |
| model | `qwen3:14b`, `qwen3:4b` |

The fence axis is included rather than deferred because `corpus_ambiguous.py` quarantines 16
subjects on exactly the Event/Fact and Project/Event boundaries the fence targets. Those
rows answer a question the fence A/B cannot: **whether the fence resolves ambiguity or
merely relocates it.** That is the payoff the quarantine was built for.

`type_confidence` is reported for all four prompt conditions, since the gating clause names
0.7 explicitly and may itself anchor the number — a possibility that only a gated/unconditional
contrast can see.

## The noise floor is measured, not assumed

`CRITERIA.md`'s fourth amendment established this harness is **not reproducible run to run**:
an unchanged prompt moved a count by 3. So no separation is read as real on its face.

`confidence.py` splits each control stratum into deterministic interleaved halves and
contrasts it with itself using identical arithmetic. **The true value of that contrast is
zero**, so whatever it returns is the instrument's own noise. Every real contrast is reported
against that band. A separation inside the band is not a finding.

## Pre-registered outcomes

**A trigger is USABLE** if it catches **≥ 50%** of `ambiguous` rows while firing on **≤ 10%**
of `control-matched` rows, and the gap sits outside the placebo band.

*Why these numbers, since both are judgement:* the channel feeds a **periodic human schema
review** (§5.7), not an automated gate, so missing half the ambiguous cases still leaves a
usable signal — a recurring pair shows up across many entries even at 50% recall. The false
positive bar is tighter than the recall bar on purpose: a channel that fires on more than one
in ten unambiguous entities floods the review it exists to inform, and an alarm-fatigued
review is worse than none, which is the same reasoning §5.10 applies to warnings.

Then:

- **RECALIBRATE (numeric survives)** — some threshold `t` is USABLE on `type_confidence`.
  Report the `t`, and note it will need re-deriving per model, since `qwen3:8b` returned
  exactly 1.000 on every entity it ever emitted.
- **ABANDON THE NUMERIC ROUTE** — no `t` is USABLE at either model, *or* the
  ambiguous-vs-matched separation falls inside the placebo band. §13.4's threshold, §3.3's
  +0.20 stickiness margin and possibly the column itself then need rewriting rather than
  retuning.
- **ADOPT `considered_types`** — the unconditional variant makes non-empty
  `considered_types` USABLE where no numeric `t` is. This is the outcome #35 item 2 predicts
  and the one the gating defect has been hiding.
- **BOTH USABLE** — report both, and prefer `considered_types` on the ticket's own grounds:
  it is a behavioural signal rather than a self-report, and self-reported confidence is
  known to be poorly calibrated. Say so as a recommendation, not a decision.
- **NEITHER USABLE, separation outside the band** — the models discriminate but no clean cut
  exists. The honest report is that ambiguity is detectable and not thresholdable, which
  points at §4.9's `no_fit`/`ambiguous` split needing a different mechanism entirely.

**An unconditional variant that fires on nearly everything is a FAILURE of the variant, not
a finding about the model** — it would mean the rewritten clause licensed enumeration rather
than requesting discrimination. The `control-matched` false-positive rate is what detects
this, and it is why that stratum exists.

## Explicitly not answered here

- **#35 item 4, the §3.3 `+0.20` stickiness margin.** It needs the *same* entity extracted
  twice across two runs and compared, which this single-pass probe never does. It needs its
  own probe and does not get resolved by this one, however the rest lands.
- **Whether `type_confidence` keeps its column** (#35 item 3). That is a decision about
  §5.7's histogram earning its storage, informed by this measurement but not settled by it.
- **Calibration on real captures.** The corpus is synthetic and one author's judgement of
  what is ambiguous, with no second reader. `AMBIGUOUS-CORPUS.md` records the residual
  confound: the matched controls are length-matched but do not reproduce the ambiguity
  *constructions*, so a model keying on "contains a consequence clause" would still separate.
