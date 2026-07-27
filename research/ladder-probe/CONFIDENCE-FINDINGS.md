# `type_confidence` and `considered_types` — findings

**Run 2026-07-27 on the Fedora box (RX 6900 XT, Ollama), grammar-constrained.** Resolves the
measurement half of issue [#35](https://github.com/markdlabrecque/tome/issues/35). Criteria
pre-registered in `CONFIDENCE-CRITERIA.md` before the first arm ran; `CRITERIA.md`'s fourth,
fifth and sixth amendments govern how many independent observations each arm carries.

Design: **2 × 2 × 2**, plus a third `considered_types` wording added after the first result — `{control, fenced}` prompt × `{gated, unconditional}`
`considered_types` × `{qwen3:14b, qwen3:4b}`, eight draws each, against
`corpus_ambiguous.py` (40 ambiguous / 20 length-matched controls / 24 short controls / 16
fence-quarantined). The four `qwen3:14b` conditions were replicated.

## Verdict

**ABANDON THE NUMERIC ROUTE, and `considered_types` is not adoptable as measured either.**
Both of #35's candidate mechanisms fail, for different reasons, and one of #35's own
sub-questions is answered decisively in the process.

## 1. The numeric threshold is not salvageable

`qwen3:14b`, control (shipped) prompt, two independent replicates:

| | ambiguous | length-matched control | separation | ambiguous < 0.9 | ambiguous < 0.7 |
|---|---|---|---|---|---|
| r1 | 0.889 | 0.904 | **−0.0148** | 14.9% | **0.0%** |
| r2 | 0.896 | 0.909 | **−0.0134** | 13.4% | **0.0%** |

**Ambiguity is weakly detectable.** The separation replicates at −0.013 to −0.015 and sits
outside the split-half placebo floor (≈ ±0.01), and it points the right way: genuinely
contested subjects score lower than unambiguous subjects *matched on length and clause
count*, so this is not the sentence-complexity confound.

**But it is not thresholdable.** Across all eight arms the best any cut achieves is **21.7%**
of ambiguous rows caught, against a pre-registered bar of 50%. At 14b the best is `< 0.9`,
catching 13–15% of ambiguous while also firing on 5.1% of length-matched and **12.7% of short
controls**. A rule that fires on one in eight unambiguous entities to catch one in seven
ambiguous ones is not a threshold; it is a direction with noise around it.

**§13.4's 0.7 specifically is dead.** Zero of ~2,350 paired entities fell below 0.7 in seven
of eight arms. The single exception is `qwen3:4b` on the *fenced* prompt, at 7.3% — the only
sub-0.7 observations in the entire study, and on an arm that cannot be replicated (fifth
amendment).

### The number is an artifact of the prompt that asks for it

This is the sharpest result here. Removing the clause that names 0.7:

| `qwen3:14b` | ambiguous | matched | separation |
|---|---|---|---|
| gated (*"if your confidence is below 0.7…"*) | 0.889 / 0.896 | 0.904 / 0.909 | −0.014 |
| unconditional (no number named) | **1.000** | **1.000** | **+0.0000** |

**With 0.7 mentioned, values spread over {0.8, 0.9}. With it removed, the model returns
exactly 1.000 on every entity in every stratum** — 317 and 279 entities across two
replicates, no exceptions.

The third wording makes the point cleanly, because now there are three prompts over one
corpus. `qwen3:14b`, `ambiguous` stratum mean `type_confidence`:

| prompt | ambiguous mean | separation vs matched |
|---|---|---|
| gated — names 0.7 | 0.889 / 0.896 | −0.014 |
| unconditional — names no number | **1.000** | +0.000 |
| forced — names no number, different tail | **0.958** | −0.008 |

**Same corpus, same model, same subjects. The confidence level is a function of the sentence
asking for it.** A self-report that moves 0.11 on rewording, while the separation it is
supposed to express stays within ±0.014, is not carrying information about the input.

## 2. `considered_types` is never populated, across three wordings

| arm | paired entities | non-empty `considered_types` |
|---|---|---|
| 14b control, gated | 280 / 318 | 0 / 0 |
| 14b control, unconditional | 317 / 279 | **0 / 0** |
| 14b fenced, gated | 277 | 12 (4.3%) |
| 14b fenced, unconditional | 276 | **0** |
| 4b control, gated | 294 | 3 (1.0%) |
| 4b control / fenced, unconditional | 302 / 299 | **0 / 0** |
| 4b fenced, gated | 308 | 0 |

**Verified at the raw level, not inferred from the scorer:** the model emits the
`considered_types` key on *every* entity and the value is `[]` — 287/287, 358/358, 316/316,
293/293 in the four arms checked by hand. The field is not absent; it is present and empty.

Overall fire rate across all arms: **15 of ~2,350 entities (0.6%)**, with **0 of those on the
`ambiguous` stratum** in the arms where it fired at all. Sensitivity 0.0%, and therefore no
trigger.

**The unconditional variant was not validated on its own**, so a third wording was run rather
than resting the verdict on it. It had produced *fewer* fires than the gated prompt — zero, in
all four arms — where `CONFIDENCE-CRITERIA.md` had pre-registered the opposite failure mode
("fires on nearly everything is a FAILURE of the variant"). The suspect was my own second
sentence, *"If only one type was ever in play, leave considered_types empty"*, which may have
licensed emptiness as the default.

**Third wording (`prompt-forced.txt`): also 0.0%.** The opt-out sentence was removed, the
schema hint changed from *"other types you weighed, **if any**"* to *"the types you rejected
for this subject"*, and the instruction rewritten to state that the unchosen type belongs
there whenever the model hesitated.

| `prompt-forced.txt` | paired | non-empty `considered_types` |
|---|---|---|
| `qwen3:14b` ambiguous | 126 | **0 (0.0%)** |
| `qwen3:14b` all strata | 315 | **0 (0.0%)** |
| `qwen3:4b` ambiguous | 115 | **0 (0.0%)** |
| `qwen3:4b` all strata | 293 | **0 (0.0%)** |

**Three wordings, two models, ~2,950 entities, and the field is empty on all of them.** #35
item 2 is answered: `considered_types` is not a usable ambiguity trigger for these models on
this task, and the failure is not an artifact of how it was asked for.

## 3. Item 4 — type stickiness is absolute, confirmed by measurement

#35 flagged this as possibly mattering more than the threshold, and it now has a measurement
rather than an inference.

§3.3's override margin is *incumbent + 0.20, and ≥ the global threshold*. Under the shipped
gated prompt, observed confidences occupy **{0.8, 0.9}** and never reach 1.0. So an incumbent
at 0.9 needs a challenger at 1.1 — impossible — and an incumbent at 0.8 needs exactly 1.0,
which **never occurred in any gated arm**.

**An Entity can therefore never be re-typed by a later extraction. Type stickiness is not a
tunable margin, it is an absolute rule with a number decorating it.** That is a second inert
knob from the same measurement, and unlike the first it changes a behaviour the PRD believes
it has.

## 4. An unexpected interaction with #36's fence

The fenced prompt raises confidence overall *and* widens the separation slightly:

| `qwen3:14b`, gated | ambiguous | matched | separation |
|---|---|---|---|
| control prompt | 0.889 / 0.896 | 0.904 / 0.909 | −0.014 |
| fenced prompt | 0.908 | 0.925 | **−0.0175** |

And the only sub-0.7 confidences anywhere in the study come from `qwen3:4b` on the fenced
prompt (7.3%), where the same arm on the control prompt produced none.

**Weak, and only one independent observation per fenced arm** (sixth amendment: the fenced
prompts reproduce bit-exactly here). It does not change the verdict — 10.6% caught at `< 0.9`
is still nowhere near usable — but if the fence is adopted for #36's reasons, the confidence
channel becomes marginally less useless rather than more, which is worth knowing before
deciding whether the column survives at all.

## What this means for the PRD, as recommendations not decisions

- **§13.4's 0.7 threshold** cannot be recalibrated into usefulness. The mechanism it gates —
  §4.9's `ambiguous` Type Suggestion — needs a different trigger or needs to stop being
  automatic.
- **§3.3's +0.20 margin** should either be removed and stickiness stated as absolute, or the
  rule rebuilt on something that isn't self-reported confidence.
- **§5.7's histogram** would show one or two bars. Whether `type_confidence` earns its
  storage is a judgement, but it has no gating role left to justify it.
- **§13.2** gains an entry: the ambiguity channel is unverifiable by the telemetry the PRD
  specifies.
- **The schema-review loop needs a new input.** `CONTEXT.md`'s rationale — *"a recurring
  Ambiguous pair is evidence that a type boundary is wrong"* — is sound and currently has no
  source. The most promising replacement is not a model self-report at all: #36 demonstrated
  that **scoring classifications against a ground-truth corpus finds real boundary defects**
  (`Event → Fact`, 6 of 10 errors at the shipping model). A periodically re-run corpus probe
  is evidence the model cannot decline to provide.

## What this cannot answer

- **Synthetic corpus, one author's judgement** of what is ambiguous, no second reader. The
  `leans`/`tossup` split is provisional.
- **The residual construction confound** (`AMBIGUOUS-CORPUS.md`): the matched controls are
  length- and clause-matched but do not reproduce the ambiguity *constructions*, so a model
  keying on "contains a consequence clause" would still separate. The separation found here
  is small enough that this matters.
- **Only two `considered_types` wordings** were tried. See above — this is the live loose end.
- **Nothing about real captures.** Whether real memory content produces genuine low-confidence
  cases is untested, and §13.1's judged-set question stands regardless.
