"""Deliberately ambiguous synthetic subject corpus for the enrichment probe (issue #35).

80 blocks in three strata: 40 genuinely ambiguous subjects, 24 unambiguous controls, and
16 quarantined subjects that sit on the two boundaries the #36 prompt fence touches.

WHY IT EXISTS. The ladder probe emitted 626 entities and not one scored `type_confidence`
below §13.4's 0.7 threshold (means 0.915 / 0.945 / 1.000 by model). `corpus.py` was written
as *unambiguous exemplars*, so that measurement cannot distinguish two explanations:
(a) the models are miscalibrated and report high confidence regardless of real ambiguity, so
the numeric route is unsalvageable; or (b) the corpus was too easy and the threshold is
merely mis-set. This corpus is the instrument that separates them. The measurement is the
*difference between strata within a draw* — not the absolute confidence on ambiguous items,
which on its own says nothing.

WHAT IT IS NOT FOR. It is not a recall corpus and not a replacement for `corpus.py`.
Ground-truth types here are contested by construction, so `analyze.py`'s coverage,
fabrication and Decision-recall numbers computed over this file are not comparable to the
ladder result and should not be reported next to it. Decision-shaped subjects are *not*
over-represented, because #24's Decision-count invariant is not what this measures.

AMBIGUITY, NOT VAGUENESS. Every subject is concrete, extractable, and names a specific
synthetic thing. A subject qualifies only if a competent reader of CONTEXT.md § "Entity
Types" would hesitate between two *named* types and could argue either. Vague text produces
bad extraction; ambiguous text produces a contested classification, and only the second is
being measured here. See AMBIGUOUS-CORPUS.md for the criterion and its failure modes.

ENTIRELY SYNTHETIC. No real person, project, company or event appears here, for the same
reason `corpus.py` says so. Committed for the same reason too: #24 built a corpus, never
committed it, and its probe became unrepeatable.

Types follow CONTEXT.md: Person, Project, Preference, Decision, Fact, Commitment, Event.
"""
import sys
from pathlib import Path
from typing import NamedTuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from corpus import SUBJECTS as _UNAMBIGUOUS  # noqa: E402  — marker-collision check only


class Subject(NamedTuple):
    """`corpus.py`'s (type, marker, text) in positions 0/1/2, plus the contested pair.

    Positional access is preserved deliberately: `SUBJECTS[i][2]` and `len(SUBJECTS)` work
    unchanged, so `run.py` needs only its import line swapped. Tuple *unpacking* does not
    survive the extra fields — see the scorer-change note below.

    gold     — the type to score as correct. For `sole` it is the only correct answer; for
               `leans` it is the better of two defensible readings; for `tossup` it is a
               nominated primary and `alt` is equally correct (see `verdict`).
    marker   — distinctive lowercase token, unique across this file AND `corpus.py`, and
               (unlike `corpus.py`) always literally present in `text`. Asserted below.
    text     — the subject as it would appear in a note. One sentence.
    alt      — the competing type a reader could defend. `None` only for the control stratum.
    verdict  — "sole"   : unambiguous; `alt` is None.
               "leans"  : `gold` is better, `alt` is defensible. Emitting `alt` is a soft
                          error, not a hard one.
               "tossup" : `gold` and `alt` are equally defensible. Either is correct.
                          In the `fence` stratum, `gold` additionally records the reading
                          `prompt-fenced.txt` endorses — under `prompt.txt` these are plain
                          toss-ups, and must be scored as such.
    stratum  — "control" | "ambiguous" | "fence".
    """
    gold: str
    marker: str
    text: str
    alt: Optional[str]
    verdict: str
    stratum: str


# ---------------------------------------------------------------------------------------
# WHAT THE SCORERS MUST CHANGE TO CONSUME THIS
#
#   run.py:11           `from corpus import SUBJECTS` -> `from corpus_ambiguous import ...`.
#                       Nothing else in run.py touches the tuple shape.
#   analyze.py:122      `for t, _, _ in subs` raises ValueError on a 6-field row.
#                       -> `for s in subs` / `s[0]`. (Decision recall is meaningless on this
#                       corpus anyway; the line only needs to stop crashing.)
#   analyze.py:153      `[toks(t) for _, _, t in subs]` -> `[toks(s[2]) for s in subs]`.
#   type_accuracy.py:36 same substitution.
#   type_accuracy.py:76 `truth = subs[si][0]` already works, but correctness must become
#                       three-valued: right if `got == gold`; also right if
#                       `verdict == "tossup"` and `got == alt`; soft-wrong if
#                       `verdict == "leans"` and `got == alt`; wrong otherwise.
#
# NEW OUTCOMES this corpus makes scorable, neither of which any committed scorer computes:
#   - confidence separation: mean/median `type_confidence` on `ambiguous` minus the same on
#     `control`, computed *within each draw* and then paired across the 8 seeds. This is the
#     #35 measurement. A separation indistinguishable from zero is evidence for (a).
#   - competitor naming (#35 item 2): for ambiguous rows, whether `considered_types`
#     contains `alt`. Three counts worth keeping apart — `considered_types` empty, non-empty
#     but missing `alt`, and containing `alt`. The last is the behavioural signal #35
#     proposes to use instead of the numeric one.
# Report the `fence` stratum separately from `ambiguous` in every table. It is not part of
# the confidence-separation statistic.
# ---------------------------------------------------------------------------------------

SUBJECTS = [
    # =====================================================================================
    # STRATUM: ambiguous (40) — 5 contested boundaries x 8
    # =====================================================================================

    # --- Decision / Preference (8) — a one-off choice vs. a recurring default. -----------
    # Device: a choice with exactly one origin that has since governed every later case,
    # or a stated rule with a single visible instance behind it.
    Subject("Decision", "kelvedon",
            "Two approvals on anything touching a migration became the rule after the Kelvedon rollback, and no migration has gone out with one since.",
            "Preference", "tossup", "ambiguous"),
    Subject("Decision", "marrowgate",
            "Marrowgate was written in Go, and every service started since has been Go as well.",
            "Preference", "tossup", "ambiguous"),
    Subject("Preference", "ashcombe",
            "Declines any meeting that arrives without an agenda, a line drawn the day the Ashcombe review ran two hours over.",
            "Decision", "leans", "ambiguous"),
    Subject("Decision", "pellingham",
            "Ruled that Pellingham dashboards belong in the reporting tool rather than bespoke code, and has pointed every request there since.",
            "Preference", "leans", "ambiguous"),
    Subject("Preference", "vartry",
            "Will not approve a schema change without a rollback script, ever since Vartry needed one and did not have it.",
            "Decision", "leans", "ambiguous"),
    Subject("Decision", "ferndown",
            "Took the smaller instance class for the Ferndown workers on cost grounds, and has taken the smaller class every time the question has come up.",
            "Preference", "tossup", "ambiguous"),
    Subject("Decision", "corvyn",
            "Standardised Corvyn on a single logging format and now turns back anything that emits a second.",
            "Preference", "leans", "ambiguous"),
    Subject("Preference", "brindlemere",
            "Support escalations come before feature work, a priority set during the Brindlemere backlog and never revisited.",
            "Decision", "leans", "ambiguous"),

    # --- Commitment / Event (8) — an obligation vs. a scheduled occurrence. --------------
    # Device: a date that carries someone's obligation, or an obligation whose only
    # concrete form is a date. CONTEXT.md's own _Avoid_ pair, pushed to where it strains.
    Subject("Event", "ambergate",
            "The Ambergate handover session is booked for the fourth, and the outgoing team stays responsible until it happens.",
            "Commitment", "tossup", "ambiguous"),
    Subject("Commitment", "riverkeep",
            "Told the Riverkeep group they would have the migration plan at the monthly on the ninth.",
            "Event", "leans", "ambiguous"),
    Subject("Commitment", "halvard",
            "Signed up to present the Halvard findings at the all-hands three weeks out.",
            "Event", "tossup", "ambiguous"),
    Subject("Event", "threnody",
            "The Threnody agreement renews on the last day of the quarter unless somebody cancels it before then.",
            "Commitment", "leans", "ambiguous"),
    Subject("Commitment", "quillfeather",
            "Is down to run the Quillfeather onboarding for the two starters next month.",
            "Event", "tossup", "ambiguous"),
    Subject("Event", "saltram",
            "The Saltram penetration test runs in the second week and the remediation window closes thirty days after it.",
            "Commitment", "leans", "ambiguous"),
    Subject("Commitment", "ostrander",
            "Agreed to a Thursday check-in with the Ostrander team for as long as the integration lasts.",
            "Event", "tossup", "ambiguous"),
    Subject("Commitment", "wexcombe",
            "Put a name against the Wexcombe compliance sign-off for the end of the month, and the slot is in the calendar either way.",
            "Event", "leans", "ambiguous"),

    # --- Person / Preference (8) — a person's habit vs. a standing convention. -----------
    # Device: CONTEXT.md scopes Preference to a convention *the author* applies. A named
    # colleague's habit is a Person fact; the same habit once it has spread and the author
    # follows it too is a Preference. Each subject sits somewhere on that transition.
    Subject("Person", "vandreth",
            "Thoren Vandreth opens every design review by reading the problem statement aloud, and every review now starts that way.",
            "Preference", "leans", "ambiguous"),
    Subject("Person", "karsavane",
            "Delphine Karsavane reviews on paper and will not comment on a diff until she has printed it.",
            "Preference", "leans", "ambiguous"),
    Subject("Person", "sixsmith",
            "Ronan Sixsmith keeps a local stack and refuses to test anything on shared staging.",
            "Preference", "leans", "ambiguous"),
    Subject("Person", "ythrane",
            "Nothing from Marisol Ythrane arrives after six in the evening, and the team plans around it as a fixed constraint.",
            "Preference", "tossup", "ambiguous"),
    Subject("Preference", "ottoline",
            "Bram Ottoline writes commit messages in full paragraphs, and the rest of the team has quietly started doing the same.",
            "Person", "tossup", "ambiguous"),
    Subject("Person", "nantwich",
            "Solveig Nantwich requires a written rollback plan before any release and has never waived it.",
            "Preference", "tossup", "ambiguous"),
    Subject("Preference", "alvenholm",
            "Meetings run by Kester Alvenholm end at twenty-five minutes so people can walk between them, which is now how all of them are scheduled.",
            "Person", "leans", "ambiguous"),
    Subject("Preference", "ravelston",
            "Imogen Ravelston starts every retro with what went well, and the format has spread to the other teams.",
            "Person", "leans", "ambiguous"),

    # --- Fact / Project (8) — a standing state vs. an ongoing effort with a state. -------
    # Device: a partial state that implies unfinished work without naming the work, or an
    # effort whose only visible property is where it has got to.
    Subject("Project", "wrenfield",
            "The Wrenfield index rebuild runs continuously and is about two-thirds through the historical backlog.",
            "Fact", "leans", "ambiguous"),
    Subject("Project", "calderstone",
            "Getting Calderstone data into the warehouse has been at ninety percent for months.",
            "Fact", "tossup", "ambiguous"),
    Subject("Project", "bellowes",
            "The Bellowes archive is being deduplicated a bucket at a time, with roughly thirty buckets left.",
            "Fact", "leans", "ambiguous"),
    Subject("Fact", "tarnwick",
            "Half the Tarnwick estate is still on the old certificate authority.",
            "Project", "leans", "ambiguous"),
    Subject("Fact", "pinemarsh",
            "The Pinemarsh style guide is maintained by whoever last needed a rule added to it.",
            "Project", "leans", "ambiguous"),
    Subject("Fact", "ilverstone",
            "Nobody has owned the Ilverstone cost dashboard since it was built, and it still updates every night.",
            "Project", "tossup", "ambiguous"),
    Subject("Fact", "ashgrove",
            "The Ashgrove test fixtures are regenerated by hand about once a quarter.",
            "Project", "tossup", "ambiguous"),
    Subject("Project", "dunmorrow",
            "Two of the four Dunmorrow regions have been drained and the other two are waiting on a date.",
            "Fact", "tossup", "ambiguous"),

    # --- Decision / Commitment (8) — a choice made vs. an obligation taken on. -----------
    # Device: agreeing to something both settles a question and creates an obligation. The
    # contest is over which half the note is actually about.
    Subject("Decision", "fennimore",
            "Agreed to move the Fennimore release out a week rather than cut scope.",
            "Commitment", "tossup", "ambiguous"),
    Subject("Commitment", "grimsdale",
            "Told the Grimsdale board the old platform would be off by year end, which also settles whether it gets extended.",
            "Decision", "leans", "ambiguous"),
    Subject("Decision", "vellacourt",
            "Undertook to keep the Vellacourt endpoint alive two more quarters instead of deprecating it now.",
            "Commitment", "tossup", "ambiguous"),
    Subject("Decision", "marchmont",
            "Took the Marchmont audit response on personally rather than splitting it, to keep the answers consistent.",
            "Commitment", "leans", "ambiguous"),
    Subject("Commitment", "selwyn",
            "Promised the Selwyn team a storage-layout answer by Friday and to use their numbers whichever way it lands.",
            "Decision", "leans", "ambiguous"),
    Subject("Commitment", "bragenwold",
            "Said yes to putting the Bragenwold integration inside the existing service, which now has to be built by month end.",
            "Decision", "tossup", "ambiguous"),
    Subject("Decision", "draymoor",
            "Accepted the Draymoor vendor timeline rather than negotiating it, and is bound to their milestones as a result.",
            "Commitment", "leans", "ambiguous"),
    Subject("Commitment", "harrowden",
            "Elected to answer the Harrowden questionnaire in full, which costs three days of somebody's week.",
            "Decision", "tossup", "ambiguous"),

    # =====================================================================================
    # STRATUM: control (24) — unambiguous, written fresh so no marker collides with
    # corpus.py. These are the within-draw baseline. Without them a model that reports 0.9
    # for everything is indistinguishable from one that genuinely discriminates.
    # =====================================================================================

    # --- Person (4) ---
    Subject("Person", "perrivale",
            "Nadia Perrivale leads the accessibility guild and reviews every new component before it ships.",
            None, "sole", "control"),
    Subject("Person", "trenneman",
            "Osgood Trenneman looks after the build farm and knows why every runner is named what it is.",
            None, "sole", "control"),
    Subject("Person", "vanterpool",
            "Priya Vanterpool joined from the games industry and thinks about frame budgets more than anyone else here.",
            None, "sole", "control"),
    Subject("Person", "drescoll",
            "Callum Drescoll is the one person allowed to rotate the production signing keys.",
            None, "sole", "control"),

    # --- Project (3) ---
    Subject("Project", "silverbark",
            "Silverbark is the effort to replace the batch scheduler and is about a third of the way through.",
            None, "sole", "control"),
    Subject("Project", "coppergate",
            "Coppergate is the internationalisation programme and currently covers four locales.",
            None, "sole", "control"),
    Subject("Project", "nightjar",
            "Nightjar is the effort to cut cold-start latency on the edge workers.",
            None, "sole", "control"),

    # --- Preference (3) ---
    Subject("Preference", "changelog",
            "Consistently prefers a written changelog entry to a release announcement, because the changelog outlives the announcement.",
            None, "sole", "control"),
    Subject("Preference", "pagination",
            "Generally prefers pagination to infinite scroll in anything an operator has to audit.",
            None, "sole", "control"),
    Subject("Preference", "utc",
            "Has a standing preference for UTC in every log line and refuses local timestamps anywhere.",
            None, "sole", "control"),

    # --- Decision (4) ---
    Subject("Decision", "verrick",
            "Chose the Verrick library for date handling after two days comparing three options.",
            None, "sole", "control"),
    Subject("Decision", "coldhaven",
            "Decided to delete the Coldhaven staging environment rather than pay to keep it warm.",
            None, "sole", "control"),
    Subject("Decision", "quintrell",
            "Chose to write the Quintrell importer as one file rather than three, because it will be thrown away.",
            None, "sole", "control"),
    Subject("Decision", "ridgemount",
            "Decided to cap Ridgemount retention at thirty days rather than build tiered storage.",
            None, "sole", "control"),

    # --- Fact (4) ---
    Subject("Fact", "ashenmoor",
            "The Ashenmoor cluster has sixty-four cores across eight nodes.",
            None, "sole", "control"),
    Subject("Fact", "corrindale",
            "There are three hundred and twelve tables in the Corrindale schema.",
            None, "sole", "control"),
    Subject("Fact", "bexhaven",
            "The Bexhaven licence covers up to fifty seats.",
            None, "sole", "control"),
    Subject("Fact", "ferrowbank",
            "Cold storage in the Ferrowbank tier costs about a fifth of what hot storage costs.",
            None, "sole", "control"),

    # --- Commitment (3) ---
    Subject("Commitment", "thurloe",
            "Committed to giving the Thurloe group a written specification of the API shape before they start.",
            None, "sole", "control"),
    Subject("Commitment", "kentmere",
            "Owes the Kentmere group a summary of the incident review and has not sent it.",
            None, "sole", "control"),
    Subject("Commitment", "padstowe",
            "Agreed to review the Padstowe proposal before it goes out.",
            None, "sole", "control"),

    # --- Event (3) ---
    Subject("Event", "wrayburn",
            "The Wrayburn summit ran for two days in May and produced nothing anyone acted on.",
            None, "sole", "control"),
    Subject("Event", "stannington",
            "The Stannington failover drill is scheduled for the first Monday of next month.",
            None, "sole", "control"),
    Subject("Event", "merribeck",
            "The Merribeck quarterly briefing happened on the ninth and overran badly.",
            None, "sole", "control"),

    # =====================================================================================
    # STRATUM: fence (16) — QUARANTINED. These straddle Event/Fact and Project/Event, the
    # two boundaries `prompt-fenced.txt` adds explicit `Avoid` lines to (CRITERIA.md, third
    # amendment). The fence may *resolve* them, so they cannot sit in the ambiguous stratum
    # without making the confidence-separation statistic prompt-dependent.
    #
    # `gold` here records the reading the FENCED prompt endorses. Under `prompt.txt` every
    # row in this stratum is a plain toss-up and `verdict` says so. Their value is the
    # second question: does the fence remove the ambiguity or relocate it?
    # =====================================================================================

    # --- Event / Fact (8) — 5 the fence pushes to Event, 3 to Fact. ---------------------
    Subject("Event", "ravensgill",
            "The Ravensgill cluster was resized in February and has been running at the larger size since.",
            "Fact", "tossup", "fence"),
    Subject("Event", "kilbraith",
            "The Kilbraith queue limit was raised to two hundred during the March backlog and left there.",
            "Fact", "tossup", "fence"),
    Subject("Event", "nettlebed",
            "The Nettlebed agreement was signed in the spring and runs for three years.",
            "Fact", "tossup", "fence"),
    Subject("Event", "brocklehurst",
            "The Brocklehurst rate limit was doubled for the launch and never put back.",
            "Fact", "tossup", "fence"),
    Subject("Event", "yarborough",
            "The Yarborough index was rebuilt over one weekend and has not needed rebuilding since.",
            "Fact", "tossup", "fence"),
    Subject("Fact", "halstow",
            "Halstow certificates renew themselves every ninety days with nobody in the loop.",
            "Event", "tossup", "fence"),
    Subject("Fact", "erriston",
            "Both Erriston API versions answer, and neither has a retirement date.",
            "Event", "tossup", "fence"),
    Subject("Fact", "quarrenden",
            "Quarrenden backups run nightly and the restore test runs weekly.",
            "Event", "tossup", "fence"),

    # --- Project / Event (8) — 5 the fence pushes to Event, 3 to Project. ---------------
    Subject("Event", "ellersby",
            "The Ellersby migration is one weekend and there is no phase two.",
            "Project", "tossup", "fence"),
    Subject("Event", "whitminster",
            "The Whitminster cut-over is a single change on the twentieth with a week of watching after it.",
            "Project", "tossup", "fence"),
    Subject("Event", "tregarran",
            "The Tregarran engagement is two weeks long and starts on the sixth.",
            "Project", "tossup", "fence"),
    Subject("Event", "ledbury",
            "The Ledbury hardening block is one fortnight, booked for August.",
            "Project", "tossup", "fence"),
    Subject("Event", "otterbourne",
            "The Otterbourne purge is a single scheduled run with a dry run the week before.",
            "Project", "tossup", "fence"),
    Subject("Project", "cadnam",
            "Cadnam is four rehearsal drills scheduled before December, one of which has already happened.",
            "Event", "tossup", "fence"),
    Subject("Project", "naseby",
            "The Naseby upgrade spans three consecutive Sunday windows, of which two are done.",
            "Event", "tossup", "fence"),
    Subject("Project", "fyfield",
            "Fyfield is a week of head-to-head vendor testing and is still being scoped.",
            "Event", "tossup", "fence"),
]

# Index lists the scorers need. Strata are contiguous above, but derive them anyway so a
# later insertion cannot silently break the split.
CONTROL_INDICES = [i for i, s in enumerate(SUBJECTS) if s.stratum == "control"]
AMBIGUOUS_INDICES = [i for i, s in enumerate(SUBJECTS) if s.stratum == "ambiguous"]
FENCE_INDICES = [i for i, s in enumerate(SUBJECTS) if s.stratum == "fence"]

# Unordered {gold, alt} boundary -> count. Used by AMBIGUOUS-CORPUS.md's coverage table.
PAIR_COUNTS = {}
for _s in SUBJECTS:
    if _s.alt:
        PAIR_COUNTS["/".join(sorted((_s.gold, _s.alt)))] = \
            PAIR_COUNTS.get("/".join(sorted((_s.gold, _s.alt))), 0) + 1

# Tokens from `prompt-fenced.txt`'s worked examples (a ticketing system, an office move).
# A subject built from either would be teaching to the test in reverse — see CRITERIA.md's
# third amendment, which imposed the same constraint in the other direction.
_PROMPT_EXAMPLE_TOKENS = frozenset(
    "foxglove ticketing switched saturday office dundas street building april forty".split()
)

TYPES = {"Person", "Project", "Preference", "Decision", "Fact", "Commitment", "Event"}
VERDICTS = {"sole", "leans", "tossup"}
STRATA = {"control", "ambiguous", "fence"}

assert len(SUBJECTS) == 80, len(SUBJECTS)
assert len(AMBIGUOUS_INDICES) == 40, len(AMBIGUOUS_INDICES)
assert len(CONTROL_INDICES) == 24, len(CONTROL_INDICES)
assert len(FENCE_INDICES) == 16, len(FENCE_INDICES)

_markers = {s.marker for s in SUBJECTS}
assert len(_markers) == 80, "markers must be unique within this file"
_collide = _markers & {m for _, m, _ in _UNAMBIGUOUS}
assert not _collide, f"markers collide with corpus.py: {sorted(_collide)}"

for _s in SUBJECTS:
    assert _s.gold in TYPES, _s
    assert _s.verdict in VERDICTS, _s
    assert _s.stratum in STRATA, _s
    assert _s.marker == _s.marker.lower() and _s.marker.isalpha(), _s
    # unlike corpus.py, every marker is a literal token of its own subject text
    assert _s.marker in _s.text.lower(), _s
    if _s.stratum == "control":
        assert _s.alt is None and _s.verdict == "sole", _s
    else:
        assert _s.alt in TYPES and _s.alt != _s.gold, _s
        assert _s.verdict in {"leans", "tossup"}, _s
    if _s.stratum == "fence":
        assert _s.verdict == "tossup", _s
        assert {_s.gold, _s.alt} in ({"Event", "Fact"}, {"Project", "Event"}), _s
    # no subject may be built out of the fenced prompt's worked examples
    _words = set(_s.text.lower().replace(",", " ").replace(".", " ").split())
    assert not (_words & _PROMPT_EXAMPLE_TOKENS), (_s.marker, _words & _PROMPT_EXAMPLE_TOKENS)

# Boundary coverage: five contested pairs at 8 each in the ambiguous stratum, two at 8 each
# under quarantine. Asserted so a later edit cannot quietly pile onto one boundary.
_amb_pairs = {}
for _i in AMBIGUOUS_INDICES:
    _k = "/".join(sorted((SUBJECTS[_i].gold, SUBJECTS[_i].alt)))
    _amb_pairs[_k] = _amb_pairs.get(_k, 0) + 1
assert sorted(_amb_pairs.values()) == [8, 8, 8, 8, 8], _amb_pairs
assert len(_amb_pairs) == 5, _amb_pairs

_fence_pairs = {}
for _i in FENCE_INDICES:
    _k = "/".join(sorted((SUBJECTS[_i].gold, SUBJECTS[_i].alt)))
    _fence_pairs[_k] = _fence_pairs.get(_k, 0) + 1
assert sorted(_fence_pairs.values()) == [8, 8], _fence_pairs

del _s, _i, _k, _markers, _collide, _words, _amb_pairs, _fence_pairs
