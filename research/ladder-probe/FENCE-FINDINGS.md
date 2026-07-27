# The `_Avoid_` fence — findings

**Run 2026-07-26/27 on the Fedora box (RX 6900 XT, Ollama), grammar-constrained.** Resolves
the measurement half of issue [#36](https://github.com/markdlabrecque/tome/issues/36).
Criteria pre-registered in `CRITERIA.md`, third amendment, with the fourth and fifth
amendments recorded before the result was scored.

> ### ⚠ Re-measured on Ollama 0.32.4 — read *"The fence on Ollama 0.32.4"* at the foot of this file
>
> Every number in the body of this document was measured on **Ollama 0.32.1**
> (`PROVENANCE.md`). The box was upgraded to **0.32.4** on 2026-07-27 and the A/B was re-run
> whole. **The fence survives: `Event → Fact` 7 → 3 against its own control, all five
> pre-registered thresholds still pass.** But the baseline moved, the net accuracy gain
> shrank from +0.96 pp to +0.34 pp, and the runtime became bit-deterministic — so the
> supporting evidence is thinner than the body of this file describes. The closing section
> gives the numbers and what they do and do not license.

## Verdict

**PASS at `qwen3:14b`, measured. PASS at `qwen3:4b`, directional.** The distinction is not
politeness: at 14b there are three independently generated runs per condition; at 4b the
model reproduces bit-exactly within a session, so the fenced condition rests on one
observation (fifth amendment).

## What #36 claimed, and what the baseline actually says

#36's accuracies reproduce exactly — 95.6% / 89.2% — which pins the matching scheme it used.
**Its confusion table does not.** Under that same scheme the wrong arrivals total **46, not
31**, and its "Decision 0, Commitment 0" are 2 and 1.

The scheme also lets a subject the model **omitted** match a *different* subject's entity,
scoring an omission as a misclassification. Splitting by overlap:

| | count | what it is |
|---|---|---|
| overlap ≥ 0.6 | **36** | the model typed *this* subject wrongly — a real misclassification |
| overlap < 0.6 | **10** | the subject's best match is another subject's entity — an omission |

**Eight of those ten omissions land on Person.** Restricted to real misclassifications the
destinations are **Fact 17, Project 11, Preference 3, Decision 2, Event 2, Commitment 1 —
Person 0.**

So #36's central claim is **two-thirds right**. Fact and Project are sinks and absorb 28 of
36; the four fenced types absorb 8; **Person is not a sink and never was.** Its six arrivals
were recall failures wearing a classification failure's clothes. The Person `_Avoid_` line
#36 asks for was therefore **not written** — a fence against a confusion this instrument has
never observed is unfalsifiable, and it would dilute the lines that carry weight.

Two splits the summing hid: **Project is a 4b phenomenon** (all 12 arrivals are 4b's), and at
**14b — the shipping model — `Event → Fact` is 6 of only 10 real errors.** One confusion is
essentially the entire error budget of the model that ships.

## The change

Three edits to the extraction prompt, no others (`prompt.txt` → `prompt-fenced.txt`):

1. `Fact` gains `Avoid: Event`, plus *"Choose Fact only after every other type has been ruled
   out"* — operationalising "a catch-all, not a default", which the prose has always meant
   and never said in a form a model can act on.
2. `Project` gains `Avoid: Event`.
3. `Event` gains one clause: *"A completed occurrence remains an Event; it does not become a
   Fact once it is over."*

Worked examples use scenarios absent from the corpus, checked mechanically — quoting a
corpus subject would teach to the test, the defect #24's prompt had.

## Result

### `qwen3:14b` — three independent runs per condition

| metric | control (range) | fenced (range) | ranges overlap? |
|---|---|---|---|
| **`Event → Fact`** | **4.7 [3–6]** | **1.0 [1–1]** | **no** |
| real misclassifications | 10.0 [9–11] | 7.0 [7–7] | **no** |
| type accuracy | 96.8% [96.5–97.1] | 97.7% | **no** |
| coverage | 98.4% [97.8–99.1] | 97.5% | **no** (lower) |
| ent/subj | 0.98 [0.97–1.01] | 0.97 | — |
| degenerate draws | 0 | 0 | — |

### `qwen3:4b` — directional (see fifth amendment)

| metric | control | fenced |
|---|---|---|
| **`Event → Fact`** | **9.3 [8–10]** | **2.0** |
| real misclassifications | 24.0 [23–26] | 19.0 |
| type accuracy | 91.1% | 92.6% |
| coverage | 93.7% [92.5–94.3] | 93.9% |
| degenerate draws | 0.7 [0–1] | 1.0 |

### Against the pre-registered thresholds

| criterion | result |
|---|---|
| `Event → Fact` falls at both arms, ranges non-overlapping | ✅ 14b 3–6 → 1; 4b 8–10 → 2 |
| type accuracy rises at both arms | ✅ +0.9 pp and +1.5 pp, non-overlapping |
| errors removed, not relocated — no new confusion exceeding the `Event → Fact` reduction | ✅ largest increase +6 against reductions of 11 and 22 |
| coverage within 2 pp, ent/subj within 0.05 | ✅ −0.9 pp / −0.01 at 14b; improved at 4b |
| degenerate draws not raised | ✅ 0 → 0 at 14b; overlapping at 4b |

## Three things to carry forward, none of them comfortable

**1. The fence costs a little recall at 14b, consistently.** Coverage 98.4% → 97.5%, and the
ranges do not overlap — the fenced condition sits below the control's *worst* run. It is
inside the pre-registered 2 pp bound and it is real: roughly three subjects per eight draws.
The likely mechanism is the "rule out every other type" clause making the model decline
marginal extractions. **Buying classification accuracy with recall is a trade this project
has not consciously made**, and §4.9's junk-drawer reasoning assumed the opposite direction.

**2. `Commitment → Decision` tripled at 14b** — 1 per run to 3. Neither fence touches that
boundary. At these counts it may be noise, but the mechanism is guessable: "rule out every
other type" pushes a borderline Commitment toward the nearest confidently-fenced neighbour.
**Watch it on the next run** rather than treating the relocation check as passed and closed.

**3. `Fact` share barely moved** (12.8% → 11.5% at 14b) while classification accuracy rose.
§4.9 treats rising Fact share as the junk-drawer signature. This measurement says the
signature is **weakly coupled to the error it is supposed to indicate** — the fence removed
11 of 14 `Event → Fact` errors and moved Fact share by 1.3 pp. §4.9's diagnostic should not
be relied on as a primary signal.

## Proposed `CONTEXT.md` change — for ratification, not applied

`CONTEXT.md` is the source the extraction prompt is built from, and the wording is a domain
call. The measured wording, translated into the glossary's register:

```diff
 **Project**:
 An ongoing effort (e.g. Tome itself) and its state or goals.
+_Avoid_: Event (a Project is an ongoing effort with a state; an Event is a single
+occurrence — "the effort to consolidate three authentication paths" is a Project, "the
+cutover happened over a weekend" is an Event)

 **Fact**:
 A standalone piece of knowledge that doesn't fit another Entity Type. Deliberately kept
-small and generic — a catch-all, not a default.
+small and generic — a catch-all, not a default. Choose Fact only after every other Entity
+Type has been ruled out.
+_Avoid_: Event (an Event happened or will happen at a point in time; a Fact is a standing
+state with no occurrence)

 **Event**:
 Something that happened, or is scheduled to happen, at a point in time — a record of
-occurrence, past or future, with no obligation-tracking.
+occurrence, past or future, with no obligation-tracking. A completed occurrence remains an
+Event; it does not become a Fact once it is over.
 _Avoid_: Commitment ("meeting with Alex Friday" is an Event; "promised to send Alex the
 report by Friday" is a Commitment)
```

**`Person` gains nothing**, against #36's item 1, for the reason given above.

## What this cannot answer

- **Synthetic corpus, reconstructed prompt.** No committed extraction prompt exists yet
  (#17). The `_Avoid_` lines were taken verbatim from `CONTEXT.md`, so the correlation is
  against the real governing vocabulary, but the surrounding prompt is not the shipped one.
- **It measures classification, not recall.** `qwen3:4b`'s SOFT FAIL was driven by
  **coverage**, and no fence addresses omission. The fence narrows the 14b/4b accuracy gap
  from 5.7 to 5.1 points; it does not touch the metric that failed 4b, so it is **not** an
  argument for descending the ladder.
- **Grammar-constrained decoding only.** `format: "json"` remains a measured hazard: one 4b
  draw degenerated at the token cap under the fenced prompt, and 4b control draws degenerate
  too, so it is not fence-specific — but a ~150-token-longer prompt under a grammar mask is
  a combination that warrants per-model checking before shipping.

---

# The fence on Ollama 0.32.4

**Run 2026-07-27 on the same Fedora box after the 0.32.1 → 0.32.4 upgrade**, same corpus,
same two prompts, same eight seeds, same options, `qwen3:14b`, grammar-constrained. Two
control replicates and three fenced. Scored by `compare_runtime.py`, which reproduces this
document's 0.32.1 table exactly from the original files before scoring the new ones.

**Why it was run.** The fenced arm alone was re-run first and looked unfenced, because it
was compared against the *0.32.1* control — runtime confounded with condition, the fourth
amendment's exact error. This compares each runtime's fence only to its own control.

## Result: the fence separates on 0.32.4

| metric | control ×2 | fenced ×3 | Δ |
|---|---|---|---|
| **`Event → Fact`** | **7.0 [7–7]** | **3.0 [3–3]** | **−4.0** |
| real misclassifications | 11.0 | 10.0 | −1.0 |
| type accuracy | 96.49% | 96.83% | +0.34 pp |
| coverage | 99.1% | 98.8% | −0.3 pp |
| ent/subj | 1.01 | 0.99 | −0.02 |
| degenerate draws | 0 | 0 | — |

All five pre-registered thresholds pass, as written: `Event → Fact` falls with
non-overlapping ranges, accuracy rises, no *single* new confusion exceeds the reduction,
coverage is inside 2 pp and ent/subj inside 0.05, and degeneracy is not raised.

## What moved, and what it costs the argument

**1. The runtime shifted the baseline, and that is the whole explanation of the scare.**
The 0.32.4 *control* is worse on the target confusion than the 0.32.1 control:

| | 0.32.1 control | 0.32.4 control |
|---|---|---|
| `Event → Fact` | 4.7 [3–6] | **7.0** |
| type accuracy | 96.78% | 96.49% |
| coverage | 98.4% | **99.1%** |
| ent/subj | 0.98 | **1.01** |

0.32.4 extracts *more* and types it slightly *worse*. So the fenced arm's `Event → Fact` 3
— which sat inside the 0.32.1 control's 3–6 band and looked like a null result — is a
4-count reduction from where the control now actually sits.

**2. Determinism inverted, and it hollows out the non-overlap test.** On 0.32.1 this model
was the reason the design became repeated-measures. On 0.32.4 the fenced prompt reproduces
**byte-identically across all three replicates**, and the control across 7 of 8 seeds — the
one differing draw scored identically on every metric. **Both conditions therefore carry one
independent observation, and the zero-width ranges above are produced by determinism, not by
stability.** The seventh amendment records this. Read the non-overlap verdict as satisfying
the pre-registered form while carrying much less weight than the same words carried on
0.32.1.

The honest positive statement that survives: **the −4.0 effect exceeds the entire run-to-run
spread of the only noise floor this project has ever measured** (0.32.1's control, which
spanned 3 counts). That is a borrowed floor, and it is borrowed from a runtime this box no
longer runs.

**3. Most of the gain is now given back by relocation.** Per run:

| confusion | control | fenced | Δ |
|---|---|---|---|
| `Event → Fact` | 7.0 | 3.0 | **−4.0** |
| `Commitment → Decision` | 1.0 | 3.0 | **+2.0** |
| `Commitment → Fact` | 1.0 | 2.0 | +1.0 |
| `Person → Preference` | 2.0 | 2.0 | 0 |

Reduction 4.0, summed increases 3.0, **net 1.0 real error per eight draws**. On 0.32.1 the
net was 3.0. The pre-registered check compares the *largest single* increase (2.0) against
the reduction (4.0) and passes; on the sum it would be marginal. That is a defect in the
criterion, recorded in the seventh amendment, not a defect discovered in the fence.

**4. `Commitment → Decision` is no longer "may be noise" — it replicated exactly.** Cost #2
above said to watch it. Per run it is **+2.0 on both runtimes**, unchanged across an upgrade
that moved every other quantity in the table. Neither fence touches that boundary. It is an
established side effect of the "rule out every other type" clause, and it should be treated
as one.

**5. The recall cost — the open judgement call — got smaller.** Coverage −0.9 pp on 0.32.1,
**−0.3 pp on 0.32.4**, and ent/subj −0.02. The trade this document flagged as *"buying
classification accuracy with recall, which this project has not consciously made"* is on
current evidence about a third as expensive as when it was flagged. It is also now buying
less.

## What this does and does not settle for the `CONTEXT.md` wording

**Settles:** the proposed wording is not an artifact of Ollama 0.32.1. Its target confusion
is the dominant 14b error on both runtimes, and the fence more than halves it on both.
Nothing in the corrected error structure, the declined `Person` fence, or the Fact-share
finding is runtime-dependent, and none of them moved.

**Does not settle:** whether a **net 1 error per 8 draws** — +0.34 pp accuracy, against a
known +2.0 `Commitment → Decision` side effect and −0.3 pp coverage — is worth a permanent
change to the governing glossary. On 0.32.1 that trade was 3 errors for 0.9 pp of recall and
the answer looked easy. It is a closer call now, and it is a domain call, not a measurement
one. **Unratified and left open deliberately.**

**A standing consequence regardless of the decision:** this whole re-measurement happened
because an unrelated `dnf` upgrade silently changed a Derivation Epoch input, and nothing in
the project would have noticed. `run.py` now self-stamps and `PROVENANCE.md` covers the
back-catalogue, but there is still no mechanism that *fails* when the epoch moves under a
committed result.

---

# Reconciliation: the ablation session, and two numbers above that do not survive it

**Written 2026-07-27 by the `decisions-34-35-36` session, which measured the same thing
independently and then went further.** It ran a **four**-condition A/B on 0.32.4 — control,
fenced, and two prompt ablations — with 3 replicates each, and re-derived the control and fenced
arms from scratch rather than reusing these files. Full result: `ABLATION-FINDINGS.md`.

## Where the two sessions agree exactly

Independent runs, same box, same runtime, same seeds. Every headline number matches:

| 0.32.4, `qwen3:14b` | this document | ablation session |
|---|---|---|
| `Event → Fact`, control | 7.0 | 7.0 |
| `Event → Fact`, fenced | 3.0 | 3.0 |
| real errors, control → fenced | 11.0 → 10.0 | 11.0 → 10.0 |
| type accuracy, control → fenced | 96.49% → 96.83% | 96.5% → 96.8% |
| determinism | fenced 3/3 byte-identical | **all four conditions** byte-identical |

That is a genuine replication of the central result, and it also confirms the seventh amendment
on a wider base: with three replicates of four conditions, **zero seeds vary anywhere.**

## ⚠ 1. The −0.3 pp recall cost is not real, and neither was the −0.9 pp

Both figures come from `analyze.py`'s `covered`, which is **many-to-one** — it credits each subject
with its best entity and never excludes an entity already used. Scored one-to-one with
`type_accuracy.pair()`:

| pre-upgrade (0.32.1), 3 reps | one-to-one | many-to-one |
|---|---|---|
| control | 96.98% | 98.44% |
| fenced | 96.88% | 97.50% |
| **the fence's coverage cost** | **0.10 pp** — 1 subject in 960 | 0.94 pp |

And on 0.32.4, per-draw one-to-one coverage is control **98.12%** against fenced **98.44%** — the
fenced arm is *higher*. **So the fence has no measured recall cost on either runtime.** The
"closer call" framing above — *"3 errors for 0.9 pp of recall"* versus *"1 error for 0.3 pp"* —
loses its denominator entirely. See `../MEASUREMENT-TRAPS.md`; this matcher has cost three findings.

## ⚠ 2. `Commitment → Decision +2.0` is a re-routing, not a new failure class

It is recorded above as *"no longer 'may be noise'; an established side effect"* on the strength of
replicating on both runtimes. Replication does not fix the inflation: **each subject is drawn ~4×
per replicate, so raw counts are ~4× subject counts.** Deduplicated by subject, the fenced condition
mistypes **fewer** distinct `Commitment` subjects than the control — **2 against 3**. There is no
excess of wrong `Commitment` subjects to explain; the fence sends a *smaller* error set more
specifically at `Decision`.

## 3. The "obvious untested variant" was tested, and it changes nothing

This document proposes trimming the *"rule out every other type"* clause as the obvious next A/B,
since both side effects were attributed to it. The ablation ran that as **arm 1**
(`prompt-fenced-nogate.txt`, the clause rewritten as a typing rule rather than a procedural gate).
Paired against the fenced arm over 8 draws:

- coverage **+0.00 pp [0.00, 0.00]**
- `Commitment → Decision` **+0.00 [0.00, 0.00]**

Byte-for-byte identical on both, on every draw. **The clause's procedural form is not the mechanism
for either side effect.** Deleting the clause outright rather than rewriting it remains untested,
but the hypothesis that motivated the test is not supported.

## 4. The bound, which replaces borrowing 0.32.1's noise floor

The seventh amendment concludes that a 0.32.4 effect must be judged against 0.32.1's noise floor,
with the borrowing stated. **It does not have to be.** The 8 draws are paired — `run.py`'s
`draw(seed)` is arm-independent — so a paired per-draw bootstrap gives a within-runtime bound, which
is the shape `macos-spike-inference.md` §19.9.5 pre-registered for exactly this comparison:

| control − fenced | mean Δ | bootstrap 95% CI | resolved? | MDE (80%) |
|---|---|---|---|---|
| `Event → Fact` / draw | +0.50 | [−0.12, +1.12] | **no** | ±0.95 |
| type accuracy | −0.61 pp | [−1.63, +0.66] | **no** | ±1.85 pp |
| coverage | −0.31 pp | [−1.25, +0.62] | **no** | ±1.64 pp |

**So the fence's benefit is not resolved at this sample size**, and "all five pre-registered
thresholds still pass" should be read alongside that. The design is underpowered ~2× on the target
confusion. **This was not fixed by re-measuring**, deliberately: the effect lives in 2 of the
corpus's 12 `Event` subjects, so more draws resample the same 12 and buy a tighter interval around a
2-subject phenomenon. The binding constraint is the corpus.

## What was decided anyway, and on what basis

**The fence is applied to `CONTEXT.md`** (2026-07-27) — with the **measured** `Fact` wording,
*"Choose Fact only after every other Entity Type has been ruled out"*, not the rewrite this
document proposes. The rewrite existed to fix the 0.9 pp recall cost, and that cost was 0.10 pp.

The basis is deliberately modest and should not be overstated later: **directional consistency
across two runtimes, a measured cost of approximately zero, and no resolved benefit.** Not
"measured, ranges non-overlapping" — that phrasing is withdrawn.
