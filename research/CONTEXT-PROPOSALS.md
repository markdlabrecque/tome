# Proposed `CONTEXT.md` changes — for ratification, deliberately not applied

`CONTEXT.md` is the source the extraction prompt is built from and the project's domain
vocabulary, so wording here is a domain call rather than a spec call. Two open tickets want
changes to it. Both are written in the glossary's own register and **neither is applied.**

| # | change | status |
|---|---|---|
| [#36](https://github.com/markdlabrecque/tome/issues/36) | `_Avoid_` fences on `Fact` and `Project`, one clause on `Event` | measured; **exact `Fact` wording pending one ablation** |
| [#35](https://github.com/markdlabrecque/tome/issues/35) | the `Type Suggestion` entry, whose referent no longer exists | ✅ **APPLIED** — Option A ratified 2026-07-27 |

---

## 1. #36 — the `_Avoid_` fence

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
the reasoning is in PRD §3.9: `Ambiguous` had no reachable trigger (0 of ~2,350 entities below
the 0.7 threshold; `considered_types` empty on ~2,950 entities across three wordings and two
models), and `No fit` is unreachable **by construction** — it fires when a subject fits no
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

**#35: done** — Option A, applied 2026-07-27.

**#36: open, and blocked on the ablation rather than on a judgement.** The diff in §1 goes in as
written *if* the rewritten `Fact` clause holds coverage; if it does not, the choice reverts to
the measured phrasing with the recall cost accepted explicitly.
