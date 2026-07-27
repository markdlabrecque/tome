# The two prompt ablations — result

Run 2026-07-27, `qwen3:14b`, `FORMAT=json`, `corpus.py` (80 subjects), 8 draws of 40 per
replicate, **three replicates per condition, four conditions, all on Ollama 0.32.4**.
Reproduce: `run-ablation-0324.sh`, score with `compare_ablation.py`.

Control and fenced were **re-measured rather than reused**. The committed 14b replicates predate
the 0.32.4 upgrade, and the upgrade moves the numbers, so every comparison here is same-runtime.

## 0. The headline finding is methodological: three replicates bought nothing

**All four conditions are bit-identical across their three replicates.** Zero seeds vary in any
condition — 12 files, four observations.

| condition | replicate files | seeds that vary | effective observations |
|---|---|---|---|
| control | 3 | 0 | 1 |
| fenced | 3 | 0 | 1 |
| arm1-nogate | 3 | 0 | 1 |
| arm2-noconf | 3 | 0 | 1 |

This is a **change from the pre-upgrade runtime**, where 14b varied run-to-run on the control
prompt and was deterministic only on the fenced ones (`CRITERIA.md`, fifth and sixth amendments).
Determinism is a property of the whole configuration *including the runtime*, and it is not
predictable from any part.

**Consequence: the ranges-overlap test cannot be run on any metric here.** `compare_ablation.py`
withholds every verdict rather than printing a comparison between two zero-variance points —
which is precisely the error that produced the pre-upgrade "ranges do not overlap" claim. Every
number below is a **single observation with no variance estimate.**

## 1. Sample size is 80 subjects, not 320 slots

Each replicate draws 8 × 40 from 80 subjects, so **every subject is drawn ~4 times** and the
error counts are inflated ~4× by re-draws of the same subject. Deduplicated:

| condition | paired | raw errors | **distinct subjects wrong** | type acc | coverage | ent/subj |
|---|---|---|---|---|---|---|
| control | 314 | 12 | **8** / 80 | 96.5% | 99.1% | 1.01 |
| fenced | 315 | 10 | **5** / 80 | 96.8% | 98.8% | 0.99 |
| arm1-nogate | 315 | 9 | **7** / 80 | 97.1% | 99.1% | 0.99 |
| arm2-noconf | 304 | 7 | **6** / 80 | 97.7% | 95.9% | 0.96 |

**Every difference in this table is one to three distinct subjects out of eighty, with no
variance estimate. Nothing here is separable.** The conditions are reported because the
directions are consistent with the prior work, not because these margins are resolvable.

Note also that errors are **not consistent within a condition**: subject 3 is mistyped on 2 of
the 3 draws it appears in under the control. The draw's surrounding note context changes the
answer, so even a deterministic run is not a per-subject verdict.

## 2. #36's fence survives the runtime change — and an earlier doubt is withdrawn

On a single 0.32.4 fenced replicate read alone, `Event → Fact` was 3 against the *pre-upgrade*
control's [3–6], which looked as though the fence had stopped working. **With the same-runtime
control measured, it has not:**

| | control | fenced |
|---|---|---|
| `Event → Fact` (summed / 3 reps) | 21 | 9 |
| per replicate | 7 | 3 |
| **distinct Event subjects mistyped** | **4** (51, 54, 55, 59) | **2** (55, 59) |
| distinct subjects wrong, all types | 8 | 5 |
| type accuracy | 96.5% | 96.8% |
| coverage | 99.1% | 98.8% |

Same direction as the pre-upgrade 4.7 → 1.0, with both endpoints shifted up. **Deduplicated,
the fence fixes two subjects of eighty** (51 and 54) and reduces distinct-subject errors 8 → 5.

**The coverage cost shrank**: 0.3 pp here (99.1 → 98.8) against the 0.9 pp measured pre-upgrade.

**`Commitment → Decision` 1 → 3 per replicate is a re-routing, not a new failure class.** Deduped,
the control mistypes 3 distinct Commitment subjects and the fenced condition 2 — the fenced
condition is *better* on Commitment subjects while sending more of its errors specifically to
`Decision`. The pre-upgrade framing of this as "the largest single increase anywhere" counted
re-draws.

## 3. Arm 1 — the gate clause: prediction **fails on its conjunction**

`prompt-fenced-nogate.txt` replaces *"Choose Fact only after every other type has been ruled
out"* with *"When a subject fits Fact and also fits another type, choose the other type."*
`CONTEXT-PROPOSALS.md` §1 pre-registered a conjunctive prediction: coverage recovers **and**
`Commitment → Decision` falls back toward its control value.

| metric | fenced | arm1 | prediction | held? |
|---|---|---|---|---|
| coverage | 98.8% | **99.1%** | recovers | ✅ recovers exactly to the control's 99.1% |
| `Commitment → Decision` /rep | 3 | **3** | falls toward 1 | ❌ unchanged |
| `Event → Fact` /rep | 3 | 4 | stays low | ~ one more error |
| type accuracy | 96.8% | **97.1%** | — | no worse |
| distinct subjects wrong | 5 | 7 | — | worse, by 2 |

**Reading:** the gate clause **was** the mechanism behind the fence's coverage cost — removing it
restores coverage to the control's level exactly — and **was not** the mechanism behind the
`Commitment → Decision` increase, which is unchanged without it. That increase therefore has an
unidentified cause, and §2 above suggests it is a re-routing of a smaller set of errors rather
than something needing a mechanism at all.

## 4. Arm 2 — dropping `type_confidence` and `considered_types` from the prompt

`prompt-fenced-nogate-noconf.txt` is arm 1 with both fields removed from the `OUTPUT` schema and
the sentence gating them on 0.7 deleted. **The clean contrast is arm 2 against arm 1**, since
those are the only two things that differ.

| metric | arm1 | arm2 | Δ |
|---|---|---|---|
| type accuracy | 97.1% | **97.7%** | **+0.6 pp** |
| raw errors | 9 | 7 | −2 |
| distinct subjects wrong | 7 | 6 | −1 |
| `Event → Fact` /rep | 4 | 1 | −3 |
| **coverage** | 99.1% | **95.9%** | **−3.2 pp** |
| entities per subject | 0.99 | 0.96 | −0.03 |

**The measurement answers #35's question and raises a new one.** The question was whether
*asking* for a confidence is a mild reasoning step that helps classification. It is not — removing
the ask **improves** classification on every error metric.

But it **costs recall**: arm 2 emits fewer entities per subject and pairs 11 fewer of 320 slots.
No subject is lost entirely and there are no degenerate draws, so this is intermittent
under-emission rather than a decode failure. The mechanism is unidentified; a plausible reading is
that asking for more per-entity fields makes the model more thorough overall, in which case the
confidence fields are doing useful work for a reason unrelated to confidence.

**This trade was not anticipated.** The pre-registered rule was *"type accuracy holds vs arm 1 →
drop both columns"*, and accuracy did better than hold. The rule never contemplated coverage
moving, and the coverage movement is **five times the size** of the accuracy gain.

Two things bound how much the recall cost matters:

- **Enrichment is fully re-runnable from immutable raw**, so a missed subject is recoverable by a
  later run with a better prompt. It is not the unbackfillable class of loss.
- But while it stands, ~3% of subjects have no entity, so they are reachable only through
  `search_raw` — the fallback — and not through the primary surface.

**Recommendation: do not adopt arm 2's prompt.** Keep asking for `type_confidence` in the prompt
and still never store it. The storage decision is untouched either way — nothing reads the columns
— and the ask costs a few tokens against a 3.2 pp recall difference that is larger than anything
else measured in this study. This is the branch `CONTEXT-PROPOSALS.md` §1 reserved for "accuracy
drops"; accuracy rose instead, but the branch's logic applies to the metric that actually moved.

## 5. What none of this can support

- **No claim of the form "X and Y do not overlap."** Zero variance in all four conditions.
- **No claim that a 1–3 subject difference is real.** n = 80 subjects, one observation each.
- **Nothing about `qwen3:4b`**, which was not run here.
- **Nothing across runtimes.** The pre-upgrade files are a different instrument; see
  `PROVENANCE.md`.
