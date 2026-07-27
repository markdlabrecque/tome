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

One failure mode survives partially and is stated under "What this cannot answer". The
other — that ambiguous subjects are simply *longer* — is answered by design, below.

## Strata

| stratum | n | what it is |
|---|---|---|
| `ambiguous` | 40 | five contested boundaries, 8 each |
| `control-matched` | 20 | unambiguous, **length- and shape-matched** to `ambiguous`. The baseline for the headline statistic |
| `control` | 24 | unambiguous and short. Kept as the length-sensitivity contrast against `control-matched` |
| `fence` | 16 | quarantined; two boundaries `prompt-fenced.txt` may resolve |
| **total** | **100** | |

### Why the length match exists, and why it is a stratum rather than a rewrite

The ambiguity device *is* the second clause — an occurrence plus its lasting consequence, a
ruling plus its subsequent pattern. Shortening the ambiguous subjects would delete the thing
being measured. But that makes them structurally longer than short controls (measured:
**17.18 words against 13.50**), so a separation read against the short controls alone is
equally well explained by "the model hedges on long compound sentences". A reviewer would
attack that first, and would be right to.

`control-matched` removes the explanation by construction: 20 unambiguous subjects, two
clauses each, matched on the word-count *distribution*, written in the same register. Their
second clause is always a **further fact of the same kind** — never one of the five ambiguity
devices. No "and every case since" on a Decision, no date-as-obligation on a Commitment, no
lasting-state clause on an Event, no habit pinned to a named colleague on a Preference. A
Person with two clauses is still unmistakably a Person.

Measured from the file, all four strata:

| stratum | n | mean | median | range | quartiles |
|---|---|---|---|---|---|
| `ambiguous` | 40 | **17.18** | 17.0 | 11–25 | 15.0 / 17.0 / 20.0 |
| `control-matched` | 20 | **17.10** | 17.0 | 11–25 | 14.25 / 17.0 / 19.5 |
| `control` | 24 | 13.50 | 13.5 | 8–18 | 11.25 / 13.5 / 15.75 |
| `fence` | 16 | 13.19 | 13.0 | 10–17 | 12.0 / 13.0 / 14.75 |

Mean within 0.1 words, identical median, identical range. The match is **asserted at import**
(mean within 0.5, medians equal), as is the requirement that the short controls stay at least
3 words shorter — because if that contrast collapsed, the length-sensitivity readout would go
with it. Residual: the matched IQR is 5.25 against the ambiguous 5.0 but sits slightly lower
(14.25–19.5 vs 15.0–20.0), so the matched stratum is a fraction less top-heavy. That is
under a word at each quartile and is not the size of thing that explains a confidence gap.

**Type mix is matched too**, at half scale, so answering the length confound does not import
a type-mix confound in its place. `ambiguous` gold: Decision 9, Commitment 9, Preference 6,
Person 5, Project 4, Fact 4, Event 3. `control-matched`: Decision 5, Commitment 4,
Preference 3, Person 2, Project 2, Fact 2, Event 2 — every type within 0.5 of its half-scale
target.

### Why 100 rather than rebalancing to 80

Holding 80 would mean cutting 20 subjects to make room. Every candidate cut costs something
the probe needs: below 40, the ambiguous stratum loses its even 8-per-boundary coverage;
below 16, the fence stratum stops supporting the relocation question; and taking the short
controls down to single digits would delete the length contrast that justifies the matched
stratum in the first place. Growing is the cheaper trade.

What growing costs: a 40-subject draw now covers 40% of the corpus instead of 50%, so each
subject appears in about 3.2 of the 8 draws rather than 4. Per-item confidence readings get
thinner; the per-stratum statistic, which is what is being measured, does not.

What it does **not** cost: `run.py` is untouched. `DRAW_N` stays 40 and the seeds stay 0–7,
so the note handed to the model is the same size as the ladder run's — **3,760 characters per
draw on average against 3,687 for the same eight seeds over `corpus.py`, a 2.0% increase** —
and the 4,096-token output cap that produced the fourth amendment's degeneration is under no
more pressure than before.

Simulated per-draw composition (`random.Random(seed).sample(range(100), 40)`, seeds 0–7):

| seed | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | total |
|---|---|---|---|---|---|---|---|---|---|
| `ambiguous` | 13 | 18 | 14 | 14 | 22 | 15 | 14 | 18 | **128** |
| `control-matched` | 9 | 6 | 7 | 10 | 6 | 9 | 11 | 8 | **66** |
| `control` | 12 | 10 | 10 | 7 | 7 | 9 | 10 | 8 | **73** |
| `fence` | 6 | 6 | 9 | 9 | 5 | 7 | 5 | 6 | **53** |

The thinnest cell is 5 (`fence`, seeds 4 and 6) and the matched stratum bottoms out at 6.
Those are the numbers that make single-seed reading a mistake: the statistic is pooled across
the eight paired draws, never read per-draw.

**Why the controls are new subjects.** Re-using `corpus.py`'s would collide markers across
the two files and make a mixed run unreadable. All 44 control subjects are written fresh.

## Ground-truth shape

`corpus.py`'s `(type, marker, text)` becomes a six-field `NamedTuple` that keeps those three
in **positions 0, 1, 2**:

```
Subject(gold, marker, text, alt, verdict, stratum)
```

The field names are `gold`, `marker`, `text`, `alt`, `verdict`, `stratum` — note that the
first field is **`gold`, not `type`**; `type` appears nowhere in the tuple.

- `gold` — the type to score as correct.
- `alt` — the competing type. `None` only in a control stratum.
- `verdict` — `sole` (unambiguous), `leans` (`gold` is better, `alt` is defensible), or
  `tossup` (`gold` and `alt` are equally correct).
- `stratum` — `control-matched` | `control` | `ambiguous` | `fence`.

In the `fence` stratum `gold` records the reading the **fenced** prompt endorses, not a human
lean; under `prompt.txt` those rows are plain toss-ups and `verdict` says `tossup`.

Positional access survives, so `SUBJECTS[i][2]` and `len(SUBJECTS)` are unchanged. Tuple
*unpacking* does not. **What the scorers must change** (also recorded in the source):

| site | change |
|---|---|
| `run.py:11` | import `corpus_ambiguous` instead of `corpus`; nothing else in `run.py` touches the shape |
| `analyze.py:122` | `for t, _, _ in subs` raises `ValueError`; use `for s in subs … s.gold`. Decision recall is meaningless on this corpus — the line only needs to stop crashing |
| `analyze.py:153` | `[toks(t) for _, _, t in subs]` → `[toks(s.text) for s in subs]` |
| `type_accuracy.py:36` | same substitution |
| `type_accuracy.py:76` | `subs[si][0]` still works; prefer `subs[si].gold`. Correctness becomes three-valued: right if `got == s.gold`; also right if `s.verdict == "tossup"` and `got == s.alt`; **soft-wrong** if `s.verdict == "leans"` and `got == s.alt`; wrong otherwise |
| everywhere | every metric splits by `s.stratum`. A number pooled over this corpus is meaningless — the strata *are* the measurement |

Two outcomes no committed scorer computes, and which this corpus exists to make scorable:

- **Confidence separation** — mean and median `type_confidence` on `ambiguous` minus the
  same on **`control-matched`**, computed within each draw and paired across the eight seeds.
  A separation indistinguishable from zero is evidence for **(a)**. Report
  `ambiguous − control` beside it: if the gap against the short controls is much the larger,
  the surplus is length sensitivity rather than ambiguity sensitivity, and
  `control-matched − control` measures that surplus directly on subjects whose type nobody
  disputes.

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
  `alt`. Only the third is the behavioural signal #35 proposes to promote. On
  `control-matched` rows a non-empty `considered_types` is a **false positive** — same length,
  same clause count, no contested type — which is the specificity half of the same
  measurement, and the reason the matched stratum earns its place beyond answering the
  length confound.

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

Re-run in full after the matched stratum was added. Numbers are from the file as written, not
from the intention:

- **Marker uniqueness and cross-file disjointness** — **100 unique markers**, asserted at
  import against `corpus.py`'s 80 by importing them. Collisions: **none**. A collision is an
  `AssertionError`, not a review finding.
- **Markers are literal tokens of their own text** — asserted, true for all 100. `corpus.py`
  does not guarantee this (its Decision markers are slugs); this file does, so a future
  marker-based coverage scorer will work without re-editing the corpus.
- **No leakage from the prompts.** `prompt-fenced.txt`'s worked examples use a ticketing
  system and an office move. Diffing the two prompts and tokenising only the added lines
  (55 content words, `analyze.py`'s tokeniser and stoplist): **the maximum any subject shares
  with the added text is 2 content words** (`utc`, on "every" and "standing") — the same bar
  the third amendment set for the prompt's own examples, and unchanged by the 20 new
  subjects. Against the *whole* fenced prompt the maximum is 5, all generic. `foxglove`,
  `ticketing`, `switched`, `saturday`, `office`, `dundas`, `street`, `building`, `april`,
  `forty` appear **nowhere** in the corpus; an assert enforces it.
- **Within-file lexical separation.** `type_accuracy.py` pairs greedily on content-word
  overlap at `COVER_T = 0.25`, so near-duplicate subjects mis-pair. Maximum pairwise overlap
  coefficient is **0.33** (`corpus.py`: 0.43), with **24 of 4,950 pairs** at or above 0.25
  (`corpus.py`: 13 of 3,160). The raw count is not the comparable quantity, because only 40
  subjects are drawn together: the expected number of ≥0.25 pairs *co-drawn in one draw* is
  **3.8 here against 3.2 for `corpus.py`** — marginally worse, and the honest way to state
  it. Four subjects were reworded after the first measurement (27 pairs, 4.3 co-drawn) to
  get there; the residue is Decision subjects sharing "chose / rather / because", which is
  the vocabulary the type is made of.
- **Token budget.** 9,341 characters over 100 subjects. Because `DRAW_N` is still 40, the
  note the model sees averages **3,760 characters per draw against 3,687** for the same eight
  seeds over `corpus.py` — a 2.0% increase, well inside the margin the 4,096-token output cap
  already had.
- **Every assert runs on import**, including the length match and the type/stratum
  invariants. `python3 -c "import corpus_ambiguous"` is the whole self-check.

## What this corpus cannot answer

In the register of `CRITERIA.md`'s section of the same name.

- **It cannot prove the low confidence, if any, lands on the right items.** A separation
  between strata is consistent with a model that is uncertain about *something else*
  correlated with ambiguity. Each subject appears in about 3.2 of the 8 draws, so per-item
  confidence rests on roughly three observations per model — enough to eyeball, not enough to
  infer.
- **The length confound is answered, but not every surface confound is.** `control-matched`
  removes sentence length, clause count and register from the list of alternative
  explanations, and `control-matched − control` measures length sensitivity directly instead
  of assuming it away. What survives is narrower and worth naming: the ambiguity devices
  favour certain *constructions* — "and every X since", "and it is still", a temporal clause
  bolted to a state — and the matched controls, while two-clause, do not reproduce those
  constructions, because reproducing them is what creates ambiguity. So a model keying on
  "sentence contains a consequence clause" rather than on the type contest would still
  produce a separation. Distinguishing those two needs an adversarial stratum built the other
  way round — the ambiguity constructions attached to subjects whose type is nonetheless
  forced — and that stratum does not exist here.
- **The ground truth is unadjudicated.** `gold`, `alt` and `verdict` are one author's
  judgments; no second reader has scored them. Human disagreement on these 40 is the
  instrument's own error bar and is currently unmeasured. A `leans` that two readers split on
  is really a `tossup`, and the `leans`/`tossup` counts above should be read as provisional.
- **It cannot set a threshold.** If separation is observed, its size is a property of *this*
  corpus's ambiguity, which is deliberately concentrated. §13.4's number cannot be read off
  it. The finding would be directional — "the signal exists" — and no more.
- **It says nothing about the prevalence of ambiguity in real notes.** 40 of 100 is a design
  parameter, not an estimate. §5.7's histogram shape under real usage stays unknown, and
  #35's item 3 — whether a near-constant `type_confidence` column earns its place — is not
  settled by anything measured here.
- **It cannot touch #35 item 4.** The §3.3 stickiness margin (`incumbent + 0.20`) is about
  re-typing an entity on a *later* extraction. Single-pass draws produce no second
  extraction of the same entity, so type stickiness remains inert-by-argument, not by
  measurement. That may be the more consequential of the two knobs and it needs a different
  probe.
- **The control baseline is not prompt-invariant.** The fenced prompt edits the `Fact`,
  `Project` and `Event` definitions, and **16 of the 44 control subjects** are of those types
  (10 of 24 short, 6 of 20 matched). Comparing *separation* across the two prompt arms
  therefore carries a confound the quarantine does not remove; comparing separation *within*
  one arm does not.
- **It is still synthetic, and still not a judged set.** Same caveat as the ladder probe:
  §13.1's open question needs 90 days of real usage. A separation here licenses keeping the
  numeric route alive, not shipping a threshold.
