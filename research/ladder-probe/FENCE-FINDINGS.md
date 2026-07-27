# The `_Avoid_` fence — findings

**Run 2026-07-26/27 on the Fedora box (RX 6900 XT, Ollama), grammar-constrained.** Resolves
the measurement half of issue [#36](https://github.com/markdlabrecque/tome/issues/36).
Criteria pre-registered in `CRITERIA.md`, third amendment, with the fourth and fifth
amendments recorded before the result was scored.

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
