# The ambiguous corpus — design note

`corpus_ambiguous.py`, written for issue [#35](https://github.com/markdlabrecque/tome/issues/35). **No model has been run against it.** This note
is the pre-registration of what it is and what it can be asked; it was written before the
first arm, for the same reason `CRITERIA.md` was.

## The discrimination it exists to make

The ladder probe emitted 626 entities and **none** scored `type_confidence` below §13.4's
0.7 (means 0.915 / 0.945 / 1.000 by model). `corpus.py`'s subjects were deliberately
unambiguous exemplars, so that result is consistent with two opposite explanations:

- **(a)** the models report high confidence regardless of real ambiguity — the numeric route
  is unsalvageable and #35 should take the `considered_types` path;
- **(b)** the corpus was too easy — genuine ambiguity would produce genuine low confidence,
  and 0.7 is merely mis-set.

Every design choice below serves that one discrimination. **The measurement is the
difference in `type_confidence` between the ambiguous and control strata, within a draw,
paired across the eight seeds.** The absolute level on ambiguous items is not the finding;
a model that emits 0.95 everywhere and a model that emits 0.95 on hard items because they
*are* 0.95-hard look identical without the control.

## The ambiguity criterion

A subject qualifies only if:

1. a competent reader of `CONTEXT.md` § "Entity Types" would **hesitate between two named
   types**, and
2. could **write a defensible sentence for either**, citing the glossary rather than taste,
   and
3. the hesitation survives knowing everything the text says — it is not resolved by more
   detail, because the text is not short of detail.

**How it was kept from sliding into vagueness.** Vagueness and ambiguity produce the same
symptom (a model that hedges) from different causes, and only one of them is being measured.
Three rules enforce the distinction:

- **Every subject names a specific synthetic thing** and states a concrete property of it.
  There are no "some work is happening on the thing" subjects.
- **The contest is over the *type*, never over the *referent*.** In every ambiguous subject,
  a reader can say exactly what entity should be created and what its summary should say —
  and still not know which of two boxes it goes in.
- **The ambiguity is constructed, not stumbled into.** Each of the five boundaries has a
  named *device* recorded in the source, and every subject on that boundary instantiates it.
  A Decision/Preference subject, for example, is a choice with exactly one origin that has
  since governed every later case: both glossary definitions apply in full, which is the
  point. If a subject could not be traced to its device it was cut.

The failure mode this does not fully escape is stated under "What this cannot answer".

## Strata

| stratum | n | what it is |
|---|---|---|
| `ambiguous` | 40 | five contested boundaries, 8 each |
| `control` | 24 | unambiguous, freshly written; the within-draw baseline |
| `fence` | 16 | quarantined; two boundaries `prompt-fenced.txt` may resolve |
| **total** | **80** | |

**Why 80.** `run.py` draws 40 of 80 with `random.Random(seed).sample`, seeds 0–7. Keeping
the total at 80 leaves the paired-draw machinery byte-identical to the ladder run, so seeds,
draw sizes and the bootstrap all carry over unchanged.

**Why 24 controls.** Enough that every draw carries a usable baseline and not so many that
the treatment stratum thins. Simulating `run.py`'s eight draws gives per-draw
control/ambiguous/fence counts of **(13,20,7) (14,21,5) (9,20,11) (10,18,12) (10,24,6)
(16,18,6) (12,21,7) (13,20,7)** — totals **97 / 162 / 61** across the eight. The thinnest
draw carries 9 controls; that is the number to keep in mind when reading a single seed's
separation, and the reason the statistic is pooled and paired rather than read per-draw.

**Why the controls are new subjects.** Re-using `corpus.py`'s would collide markers across
the two files and make a mixed run unreadable. All 24 are written fresh, spread over all
seven types (Person 4, Decision 4, Fact 4, Project 3, Preference 3, Commitment 3, Event 3).

## Ground-truth shape

`corpus.py`'s `(type, marker, text)` becomes a six-field `NamedTuple` that keeps those three
in **positions 0, 1, 2**:

```
Subject(gold, marker, text, alt, verdict, stratum)
```

- `gold` — the type to score as correct.
- `alt` — the competing type. `None` only for controls.
- `verdict` — `sole` (unambiguous), `leans` (`gold` is better, `alt` is defensible), or
  `tossup` (`gold` and `alt` are equally correct).
- `stratum` — `control` | `ambiguous` | `fence`.

In the `fence` stratum `gold` records the reading the **fenced** prompt endorses, not a human
lean; under `prompt.txt` those rows are plain toss-ups and `verdict` says `tossup`.

Positional access survives, so `SUBJECTS[i][2]` and `len(SUBJECTS)` are unchanged. Tuple
*unpacking* does not. **What the scorers must change** (also recorded in the source):

| site | change |
|---|---|
| `run.py:11` | import `corpus_ambiguous` instead of `corpus`; nothing else in `run.py` touches the shape |
| `analyze.py:122` | `for t, _, _ in subs` raises `ValueError`; use `s[0]`. Decision recall is meaningless on this corpus — the line only needs to stop crashing |
| `analyze.py:153` | `[toks(t) for _, _, t in subs]` → `[toks(s[2]) for s in subs]` |
| `type_accuracy.py:36` | same substitution |
| `type_accuracy.py:76` | correctness becomes three-valued: right if `got == gold`; also right if `verdict == "tossup"` and `got == alt`; **soft-wrong** if `verdict == "leans"` and `got == alt`; wrong otherwise |

Two outcomes no committed scorer computes, and which this corpus exists to make scorable:

- **Confidence separation** — mean and median `type_confidence` on `ambiguous` minus the
  same on `control`, computed within each draw and paired across the eight seeds. A
  separation indistinguishable from zero is evidence for **(a)**.

  **Read `CRITERIA.md`'s fourth amendment before quoting a number from this.** The probe is
  not bit-reproducible: a control replication of an unchanged prompt moved `Event → Fact` by
  3 and coverage by 1.2 pp with nothing changed but the wall clock. The separation statistic
  is a within-draw *difference*, so it cancels more of that noise than a raw count does — but
  by how much is unmeasured, and the honest way to find out is the same one the fourth
  amendment adopted: **run the control condition twice and take control-vs-control separation
  as the noise floor** before reading control-vs-ambiguous against it. Degenerate draws
  (`done_reason: length`, or fewer than 10 entities from 40 subjects) are excluded and
  counted, per the same amendment.
- **Competitor naming** (#35 item 2) — for ambiguous rows, whether `considered_types`
  contains `alt`. Keep three counts apart: empty, non-empty but missing `alt`, and containing
  `alt`. Only the third is the behavioural signal #35 proposes to promote.

Report the `fence` stratum in its own rows everywhere. It is not part of the separation
statistic.

## Boundary coverage

Derived from the file, not from intent:

| boundary | stratum | n | `leans` | `tossup` | device |
|---|---|---|---|---|---|
| Decision / Preference | ambiguous | 8 | 5 | 3 | a choice with one origin that has governed every case since |
| Commitment / Event | ambiguous | 8 | 4 | 4 | a date that carries an obligation, or an obligation whose only concrete form is a date |
| Person / Preference | ambiguous | 8 | 5 | 3 | a named colleague's habit that has spread far enough to be a convention the author also follows |
| Fact / Project | ambiguous | 8 | 4 | 4 | a partial state implying unfinished work without naming the work |
| Commitment / Decision | ambiguous | 8 | 4 | 4 | agreeing to something both settles a question and creates an obligation |
| Event / Fact | **fence** | 8 | 0 | 8 | a completed occurrence that has become the standing state |
| Project / Event | **fence** | 8 | 0 | 8 | a bounded effort that is also a single scheduled occurrence |

Ambiguous stratum: **22 `leans`, 18 `tossup`**. Two of the five ambiguous boundaries
(Decision/Preference, Commitment/Event) are `CONTEXT.md`'s own `_Avoid_` pairs, pushed to
where the fence stops helping; the other three are unfenced and untested.

Person/Preference deserves a note. `CONTEXT.md` scopes Preference to a convention **the
author** applies repeatedly, so a third party's habit is a Person fact — until it has spread
and the author follows it too. All eight subjects sit somewhere along that transition, which
is why the pair is contestable at all rather than merely a model error. This also gives the
instrument something `CRITERIA.md`'s third amendment explicitly wanted and did not have:
Person had **zero** real misclassification arrivals in the ladder run, which is why #36's
proposed Person fence was refused as unfalsifiable. If Person arrivals appear here, that
refusal gets revisited on evidence.

## The fence quarantine

`CRITERIA.md`'s third amendment adds `Avoid: Event` to both `Fact` and `Project`, plus
*"A completed occurrence remains an Event; it does not become a Fact once it is over."* That
change is **under measurement right now**. Subjects straddling Event/Fact or Project/Event
may therefore be *resolved* by the prompt rather than by the model, which would make the
confidence-separation statistic depend on which prompt was used — the one thing it must not
depend on. So they are a separate stratum, flagged in the data, and excluded from the
headline number.

They keep their value as a second question: **does the fence remove the ambiguity or
relocate it?** Run under both prompts, this stratum distinguishes a fence that raises
confidence and gets the type right from one that raises confidence and merely picks
consistently. To make over-correction visible, the fence-endorsed reading is not uniform:
of the 16, **10 resolve to Event, 3 to Fact, 3 to Project**. A model that answers Event to
all 16 has been pushed, not taught.

## Mechanical checks

Run against the file as written, not against the intention:

- **Marker uniqueness and cross-file disjointness** — 80 unique markers, asserted at import
  against `corpus.py`'s 80 by importing them. A collision is an `AssertionError`, not a
  review finding.
- **Markers are literal tokens of their own text** — asserted. `corpus.py` does not
  guarantee this (its Decision markers are slugs); this file does, so a future marker-based
  coverage scorer will work without re-editing the corpus.
- **No leakage from the prompts.** `prompt-fenced.txt`'s worked examples use a ticketing
  system and an office move. Diffing the two prompts and tokenising only the added lines
  (55 content words, `analyze.py`'s tokeniser and stoplist): **the maximum any subject shares
  with the added text is 2 content words** (`utc`, on "every" and "standing") — the same bar
  the third amendment set for the prompt's own examples. Against the *whole* fenced prompt
  the maximum is 5, all generic ("all", "between", "people", "scheduled", "them").
  `foxglove`, `ticketing`, `switched`, `saturday`, `office`, `dundas`, `street`, `building`,
  `april` appear **nowhere** in the corpus; an assert enforces it.
- **Within-file lexical separation.** `type_accuracy.py` pairs greedily on content-word
  overlap at `COVER_T = 0.25`, so near-duplicate subjects would mis-pair. Maximum pairwise
  overlap coefficient is **0.33**, with **12 of 3,160 pairs** at or above 0.25 — slightly
  better than `corpus.py`'s own 0.43 and 13. Three subjects were reworded to get there.
- **Every assert runs on import.** `python3 -c "import corpus_ambiguous"` is the whole
  self-check.

## What this corpus cannot answer

In the register of `CRITERIA.md`'s section of the same name.

- **It cannot prove the low confidence, if any, lands on the right items.** A separation
  between strata is consistent with a model that is uncertain about *something else*
  correlated with ambiguity. Each subject appears in about half the draws, so per-item
  confidence rests on roughly four observations per model — enough to eyeball, not enough to
  infer.
- **It cannot rule out that the models are reacting to surface form.** The ambiguity device
  usually produces a second coordinated clause, so ambiguous subjects are longer than
  controls: **mean 101 characters against 83** (fence stratum 78). Nothing here separates
  "sensitive to type ambiguity" from "sensitive to sentence complexity". A length-matched
  control stratum would fix it and does not exist; if a separation is observed, this is the
  first alternative explanation to attack, and the cheapest attack is a rerun with the
  controls padded to matching length. *(The whole-corpus budget is unaffected: 7,290
  characters against `corpus.py`'s 7,279, so a 40-subject draw costs the same prompt tokens
  and carries the same degeneration risk as the ladder run — no more, no less.)*
- **The ground truth is unadjudicated.** `gold`, `alt` and `verdict` are one author's
  judgments; no second reader has scored them. Human disagreement on these 40 is the
  instrument's own error bar and is currently unmeasured. A `leans` that two readers split on
  is really a `tossup`, and the `leans`/`tossup` counts above should be read as provisional.
- **It cannot set a threshold.** If separation is observed, its size is a property of *this*
  corpus's ambiguity, which is deliberately concentrated. §13.4's number cannot be read off
  it. The finding would be directional — "the signal exists" — and no more.
- **It says nothing about the prevalence of ambiguity in real notes.** 40 of 80 is a design
  parameter, not an estimate. §5.7's histogram shape under real usage stays unknown, and
  #35's item 3 — whether a near-constant `type_confidence` column earns its place — is not
  settled by anything measured here.
- **It cannot touch #35 item 4.** The §3.3 stickiness margin (`incumbent + 0.20`) is about
  re-typing an entity on a *later* extraction. Single-pass draws produce no second
  extraction of the same entity, so type stickiness remains inert-by-argument, not by
  measurement. That may be the more consequential of the two knobs and it needs a different
  probe.
- **The control baseline is not prompt-invariant.** The fenced prompt edits the `Fact`,
  `Project` and `Event` definitions, and 10 of the 24 controls are of those types. Comparing
  *separation* across the two prompt arms therefore carries a confound the quarantine does
  not remove; comparing separation *within* one arm does not.
- **It is still synthetic, and still not a judged set.** Same caveat as the ladder probe:
  §13.1's open question needs 90 days of real usage. A separation here licenses keeping the
  numeric route alive, not shipping a threshold.
