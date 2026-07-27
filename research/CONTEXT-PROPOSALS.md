# `CONTEXT.md` changes — both applied 2026-07-27

`CONTEXT.md` is the source the extraction prompt is built from and the project's domain
vocabulary, so wording here is a domain call rather than a spec call. Two tickets wanted
changes to it. Both are written in the glossary's own register, and **both are now applied** —
see the status table below, the per-section banners, and *Ratification* at the end for exactly
what landed and what the "ratified" stamps do and do not mean.

| # | change | status |
|---|---|---|
| [#36](https://github.com/markdlabrecque/tome/issues/36) | `_Avoid_` fences on `Fact` and `Project`, one clause on `Event` | ✅ **APPLIED** — ablation run, rewritten `Fact` wording ratified 2026-07-27 |
| [#35](https://github.com/markdlabrecque/tome/issues/35) | the `Type Suggestion` entry, whose referent no longer exists | ✅ **APPLIED** — Option A ratified 2026-07-27 |

---

## 1. #36 — the `_Avoid_` fence ✅ APPLIED

> **Applied 2026-07-27 with the MEASURED `Fact` wording. The rewrite proposed below is
> withdrawn** — the coverage cost it existed to fix was a scoring artifact. See "the rewrite is
> withdrawn" at the end of this block.
>
> Kept as the record of what was decided. Three amendments the ablation forced:
>
> 1. **The numbers in the paragraph below are pre-upgrade and not directly comparable to
>    anything measured after 2026-07-27.** Re-measured same-runtime on Ollama 0.32.4:
>    `Event → Fact` **7 → 3** per replicate (control → fenced), same direction as the
>    4.7 → 1.0 below, both endpoints shifted up. The fence stands.
> 2. **"Ranges non-overlapping throughout" cannot be claimed on the new runtime.** All four
>    conditions are bit-identical across three replicates, so there are no ranges. And
>    deduplicated by subject — each is drawn ~4× per replicate — the fence fixes **two subjects
>    of eighty** and reduces distinct-subject errors 8 → 5.
> 3. **The `Commitment → Decision` worry below largely dissolves.** It counted re-draws:
>    deduplicated, the fenced condition mistypes *fewer* distinct `Commitment` subjects than the
>    control (2 vs 3) while routing more of a smaller error set to `Decision`.
>
> ### The rewrite is withdrawn — it was solving a scoring artifact
>
> **Neither half of the prediction held, and the reason is that there was nothing to fix.**
>
> `analyze.py`'s coverage counter is **many-to-one** — it credits each subject with its best
> entity and never stops one entity covering several subjects. `type_accuracy.pair()` is
> one-to-one. Re-scoring the pre-upgrade fence study both ways:
>
> | pre-upgrade, 14b, 3 reps | one-to-one | many-to-one |
> |---|---|---|
> | control | 96.98% | 98.44% |
> | fenced | 96.88% | 97.50% |
> | **the fence's coverage cost** | **0.10 pp** (1 subject / 960) | 0.94 pp |
>
> **The 0.9 pp recall cost that made the measured `Fact` sentence a suspect was 0.1 pp.** Nine
> tenths of it was one entity being credited several times — the same defect the traps list
> already blames for "the entire Person finding in #36", claiming a second finding on this ticket.
>
> And the ablation gives the rewrite no advantage. Paired per-draw bootstrap, n=8, against the
> fenced arm: coverage **+0.00 pp [0.00, 0.00]** and `Commitment → Decision` **+0.00 [0.00, 0.00]**
> — byte-for-byte identical on every draw. Type accuracy +0.34 pp [−0.64, +1.34], not resolved.
>
> So the pre-registered fallback applies: **the measured wording ships**, and the recall trade it
> was accused of costing is 1 subject in 960 rather than something to accept. Full result:
> [`ladder-probe/ABLATION-FINDINGS.md`](./ladder-probe/ABLATION-FINDINGS.md) §5.

Measured at `qwen3:14b` over three independent replicates per condition: `Event → Fact`
**4.7 [3–6] → 1.0**, real misclassifications **10.0 → 7.0**, type accuracy **96.8% → 97.7%**,
ranges non-overlapping throughout. Full result in
[`ladder-probe/FENCE-FINDINGS.md`](./ladder-probe/FENCE-FINDINGS.md).

**`Person` gains nothing**, against #36's own item 1 — nothing ever lands *in* Person, and the
two subjects that leak *out* of it are one contestable corpus label and one coin-flip (§4.9).

```diff
 **Project**:
 An ongoing effort (e.g. Tome itself) and its state or goals.
+_Avoid_: Event (a Project is an ongoing effort with a state; an Event is a single
+occurrence — "the effort to consolidate three authentication paths" is a Project, "the
+cutover happened over a weekend" is an Event)

 **Fact**:
 A standalone piece of knowledge that doesn't fit another Entity Type. Deliberately kept
-small and generic — a catch-all, not a default.
+small and generic — a catch-all, not a default. When a subject fits Fact and also fits
+another Entity Type, choose the other type.
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

### ⚠ The `Fact` sentence above is *not* the measured one

The measured wording was **"Choose Fact only after every other type has been ruled out."**
It is replaced here by **"When a subject fits Fact and also fits another Entity Type, choose
the other type"** because the measured phrasing is a *procedural gate* on the act of choosing,
and it is the prime suspect for both uncomfortable results in the fence run:

- **coverage 98.4% [97.8–99.1] → 97.5%** — 3 more missed subjects per 320 against the control
  mean, 1 against the control's worst run;
- **`Commitment → Decision` 3 → 9** summed over replicates, the largest single increase
  anywhere, on a boundary neither fence touches.

The rewrite keeps the operational force and removes the sentence a model can read as raising
the bar for emitting anything at all. It makes a falsifiable prediction — coverage recovers
*and* `Commitment → Decision` falls back toward 3 — and that ablation is queued.

**If the ablation holds, ratify the diff above. If coverage stays at 97.5%, the gate clause
was not the mechanism**, the recall cost is real, and the choice reverts to the measured
wording with the trade accepted explicitly.

---

## 2. #35 — the `Type Suggestion` entry ✅ APPLIED

> **Ratified as Option A and applied.** Kept below as the record of what was decided and why, plus two further references the ratification turned up: `Type Override`'s discriminator (which cited the deleted threshold) and `Derivation Epoch`'s input list (which named it as a recorded input). Both were corrected in the same pass.

Enrichment no longer writes Type Suggestions. Both kinds failed, for different reasons, and
the reasoning is in PRD §3.9: `Ambiguous`'s two candidate triggers both failed, though not in
the same way — the confidence half is unreachable (0 of ~2,350 entities below the 0.7
threshold) while `considered_types` is reachable and uninformative (13.9% fire rate under the
shipped fenced prompt, 4.7% precision against a 2.3% base error rate; the earlier "empty on
~2,950 entities" is withdrawn — see `ladder-probe/CONFIDENCE-FINDINGS.md` §2). `No fit` is
unreachable **by construction** — it fires when a subject fits no
type, while `Fact` is *defined* as the type for whatever fits no other type. A designed
catch-all and a missing-type detector cannot coexist.

The glossary entry therefore describes something that does not exist. Two options.

### Option A — replace the entry (recommended)

Keeps the vocabulary honest and names what actually feeds governance, so the `_Avoid_` line
still has work to do.

```diff
-**Type Suggestion**:
-A note logged by Enrichment when classification strains, in one of two kinds. **No fit**: the
-Raw Entry is a poor/low-confidence fit for every existing Entity Type — records why it
-strained, plus a guessed name for a possible new type. **Ambiguous**: several Entity Types fit
-plausibly and confidence fell below threshold — records the competing types. Governance
-metadata, not itself an Entity Type: both kinds exist only to feed the periodic manual review
-of the entity-type schema, where a recurring Ambiguous pair is evidence that a type *boundary*
-is wrong rather than that a guess was.
-_Avoid_: New entity, candidate type
+**Schema Evidence**:
+What the periodic manual review of the entity-type schema reads. Two kinds, neither of them a
+model self-report. **A recurring confusion pair** in the ground-truth corpus probe is evidence
+that a type *boundary* is wrong rather than that one guess was. **A recurring theme inside
+Fact** is evidence that a type is *missing* — Fact is the designed catch-all, so what
+accumulates there is the homeless-subject signal. Governance metadata, not itself an Entity
+Type.
+_Avoid_: Type Suggestion (the model-emitted version; it was specified, measured, and removed —
+see PRD §3.9), new entity, candidate type
```

### Option B — delete the entry outright

Cheaper. The cost is that "Type Suggestion" was a term of art across five PRD sections and two
closed tickets, so a reader meeting it in the archive gets no pointer saying it is gone. The
`_Avoid_` line in Option A is doing exactly that job, which is why I prefer A.

---

## Ratification

**#35: closed** — Option A, applied 2026-07-27.

**#36: closed.** The ablation resolved it *against* the rewrite: the 0.9 pp coverage cost that
made the measured `Fact` sentence a suspect was a scoring artifact worth 0.10 pp (§1), so the
pre-registered fallback applied and **the measured wording shipped** rather than the diff above.

**What actually landed in `CONTEXT.md`:** `_Avoid_: Event` on **`Project`** and on **`Fact`**;
the *"A completed occurrence remains an Event; it does not become a Fact once it is over"*
clause on **`Event`**; `Fact` keeping its **measured** sentence (*"Choose Fact only after every
other Entity Type has been ruled out"*), not the withdrawn rewrite in §1's diff; and
`Type Suggestion` replaced by **`Schema Evidence`** (#35, Option A), with an `_Avoid_` line so
the retired term still resolves. **`Person` was deliberately declined** — nothing ever lands
*in* it, and the two subjects that leak *out* are one contestable corpus label and one
coin-flip.

**Status of the ratification itself, stated plainly.** These changes were applied and
**self-stamped by the implementing session** — the "ratified 2026-07-27" stamps in this file and
in the status table above are that session's own marks, not a countersignature. **Owner
ratification is not recorded as a separate artifact**; there is no independent sign-off to point
to. What is true is that the wording is in `CONTEXT.md` and shipping. Whether the domain owner
has endorsed it is simply not evidenced here, and should not be read out of the stamps.
