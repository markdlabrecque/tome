#!/usr/bin/env python3
"""Score `type_confidence` and `considered_types` by stratum, for issue #35.

WHAT IT MEASURES. The ladder probe emitted 626 entities and not one scored `type_confidence`
below §13.4's 0.7 (means 0.915 / 0.945 / 1.000 by model), so the threshold never fires. That
run cannot say whether the models are miscalibrated or the corpus was simply too easy.
`corpus_ambiguous.py` is the instrument that separates those; this is its scorer. It reports,
for each stratum: the `type_confidence` distribution, the *within-draw separation* between
strata, the behaviour of `considered_types` as an alternative trigger (#35 item 2), and a
sweep of what any candidate threshold would catch and cost (#35 item 1).

WHAT THE STRATIFICATION IS FOR. **The measurement is the separation between strata, not the
absolute level on any one of them.** A pooled number over this corpus is meaningless: 40 of
the 100 subjects are contested by construction, which is a design parameter and not an
estimate of anything. The headline contrast is `ambiguous` vs `control-matched`, because the
matched controls hold sentence length, clause count and register fixed; `ambiguous − control`
and `control-matched − control` are reported beside it so length sensitivity is visible
rather than absorbed. The `fence` stratum is reported in its own rows and is never part of
the headline, because `prompt-fenced.txt` may resolve those subjects by prompt rather than by
model.

HOW THE NOISE FLOOR IS BUILT. Per CRITERIA.md's fourth amendment this box is not
bit-reproducible, so a separation is only readable against a floor. Two floors are computed:

  - **Placebo split-half** — each control stratum is split deterministically into interleaved
    halves and contrasted with itself, within-draw, exactly as the real contrasts are. Its
    true value is zero, so whatever it returns is this instrument's own noise. Available from
    a single run.
  - **Across-replicate range** — pass several files per condition and every statistic is
    reported as a range over them, in the register `compare_replicates.py` established.

Degenerate draws (`done_reason: length`, or fewer than `DEGENERATE_MIN_ENTITIES` entities from
40 subjects) are excluded from every metric and counted as an outcome in their own right, per
the same amendment. Only entities that pair with a drawn subject are scored, using
`type_accuracy.pair` unchanged — an unpaired entity carries no ground truth, so it has no
stratum; the unmatched count is reported rather than dropped.

WHAT THIS DELIBERATELY DOES NOT CONCLUDE. It prints no verdict, sets no threshold, and does
not decide #35. A separation here is a property of *this* corpus's deliberately concentrated
ambiguity; §13.4's number cannot be read off it. It cannot show that low confidence lands on
the right items (~3 observations per subject per model), cannot distinguish sensitivity to
ambiguity from sensitivity to the constructions that create it, and cannot touch #35 item 4 —
type stickiness needs a second extraction of the same entity, which single-pass draws never
produce. See CONFIDENCE-SCORING.md's "what this cannot answer".

Usage:
    python3 confidence.py raw-amb-r1.jsonl
    python3 confidence.py amb=raw-amb-r1.jsonl,raw-amb-r2.jsonl,raw-amb-r3.jsonl
    python3 confidence.py plain=a.jsonl,b.jsonl fenced=c.jsonl,d.jsonl --model qwen3:14b

A bare filename becomes a condition named after its stem. Several files in one condition are
replicates of it. Without `--model`, every model present in the files is scored separately.
"""
import collections
import json
import sys
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import COVER_T, entities_in, extract_json  # noqa: E402
from compare_replicates import DEGENERATE_MIN_ENTITIES  # noqa: E402
from type_accuracy import pair  # noqa: E402
from corpus import SUBJECTS as _PLAIN  # noqa: E402  — wrong-corpus guard only
import corpus_ambiguous as CA  # noqa: E402

# Order is the reading order of every table: treatment, its matched baseline, the length
# contrast, then the quarantined stratum.
STRATA = ["ambiguous", "control-matched", "control", "fence"]
CONTROL_STRATA = ["control-matched", "control"]

# §13.4's 0.7 first, then the recalibration #35 item 1 asks about, then "anything short of
# perfect certainty" — which is the only threshold that can fire at all on a model that
# returns a constant 1.000.
THRESHOLDS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]

Row = collections.namedtuple(
    "Row", "cond model rep seed gidx stratum gold alt verdict etype conf cons")


# --------------------------------------------------------------------------------------
# The placebo split. Each control stratum is cut into interleaved halves by position in the
# corpus, so the two halves are matched on everything the corpus varies along its own order
# (the strata are written contiguous, and within them the boundaries rotate). Contrasting a
# half against its sibling is the same arithmetic as the real contrast with a true value of
# zero, which is what makes it a floor.
# --------------------------------------------------------------------------------------
def _halves(indices):
    idx = sorted(indices)
    return {g: (i % 2) for i, g in enumerate(idx)}


PLACEBO = {
    "control-matched A|B": _halves(CA.MATCHED_INDICES),
    "control A|B": _halves(CA.CONTROL_INDICES),
    "all-controls A|B": _halves(CA.ALL_CONTROL_INDICES),
}

CONTRASTS = [
    ("ambiguous − control-matched", "ambiguous", "control-matched"),   # headline
    ("ambiguous − control", "ambiguous", "control"),
    ("control-matched − control", "control-matched", "control"),       # length sensitivity
    ("fence − control-matched", "fence", "control-matched"),           # reported, not headline
]


def pctl(vals, q):
    """Linear-interpolated percentile. Small n here, so no library dependency is earned."""
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def as_conf(v):
    """`type_confidence` as a float, or None. Numeric only, matching `analyze.py`."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def as_considered(e):
    """`considered_types` normalised to the alternatives actually named.

    A string is treated as a one-element list. Entries equal to the entity's own
    `entity_type` are dropped: restating the chosen type is not an alternative weighed, and
    counting it would inflate the trigger's fire rate on every stratum equally. Entries that
    are not one of CONTEXT.md's seven types are kept — they are still evidence the model
    hesitated — but are visible as the gap between "named" and the seven.
    """
    raw = e.get("considered_types")
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ()
    own = str(e.get("entity_type", "")).strip().lower()
    out = []
    for x in raw:
        if not isinstance(x, str):
            continue
        x = x.strip()
        if not x or x.lower() == own or x.lower() in {y.lower() for y in out}:
            continue
        out.append(x)
    return tuple(out)


def names(cons, t):
    return bool(t) and any(c.lower() == t.lower() for c in cons)


def load(cond, model, paths):
    """Score every draw of one condition. Returns (rows, accounting)."""
    rows, acct = [], []
    for p in paths:
        path = HERE / p if not Path(p).is_absolute() else Path(p)
        if not path.exists():
            acct.append({"rep": p, "missing": True})
            continue
        a = {"rep": p, "missing": False, "draws": 0, "degen": 0, "ents": 0,
             "paired": 0, "unmatched": 0, "no_conf": 0, "max_idx": -1,
             "drawn": collections.Counter(), "paired_by": collections.Counter()}
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["model"] != model:
                continue
            a["draws"] += 1
            a["max_idx"] = max([a["max_idx"]] + list(rec["indices"]))
            ents = entities_in(extract_json(rec.get("response"))) or []
            clean = [e for e in ents
                     if isinstance(e, dict) and "natural_key" in e and "entity_type" in e]
            if rec.get("done_reason") == "length" or len(clean) < DEGENERATE_MIN_ENTITIES:
                a["degen"] += 1
                continue
            a["ents"] += len(clean)
            subs = [CA.SUBJECTS[i] for i in rec["indices"]]
            for s in subs:
                a["drawn"][s.stratum] += 1
            # `pair` unpacks a 3-field row, so hand it corpus.py's shape. Indices are
            # positional, so the returned subject index still points into `subs`.
            pairs, unmatched = pair([(s.gold, s.marker, s.text) for s in subs], clean)
            a["unmatched"] += unmatched
            a["paired"] += len(pairs)
            for si, e, _ov in pairs:
                s = subs[si]
                a["paired_by"][s.stratum] += 1
                conf = as_conf(e.get("type_confidence"))
                if conf is None:
                    a["no_conf"] += 1
                rows.append(Row(cond, model, p, rec["seed"], rec["indices"][si], s.stratum,
                                s.gold, s.alt, s.verdict,
                                str(e.get("entity_type", "")).strip(), conf,
                                as_considered(e)))
        acct.append(a)
    return rows, acct


# --------------------------------------------------------------------------------------
# Contrasts are computed *within a draw* and then averaged over draws, so a draw that is
# globally high or low cancels out of the difference. A draw contributes only if both sides
# have at least one scored entity.
# --------------------------------------------------------------------------------------
def by_draw(rows):
    d = collections.defaultdict(list)
    for r in rows:
        d[(r.rep, r.seed)].append(r)
    return d


def contrast(rows, pick_a, pick_b):
    """(mean of within-draw Δmean, mean of within-draw Δmedian, draws used)."""
    dm, dmed = [], []
    for _k, rs in sorted(by_draw(rows).items()):
        a = [r.conf for r in rs if r.conf is not None and pick_a(r)]
        b = [r.conf for r in rs if r.conf is not None and pick_b(r)]
        if not a or not b:
            continue
        dm.append(mean(a) - mean(b))
        dmed.append(median(a) - median(b))
    if not dm:
        return None, None, 0
    return mean(dm), mean(dmed), len(dm)


def stratum_pick(s):
    return lambda r: r.stratum == s


def half_pick(table, want):
    return lambda r: table.get(r.gidx) == want


def fmt(x, spec=".3f"):
    return "—" if x is None else format(x, spec)


def report(cond, model, rows, acct):
    out = []
    reps = [a["rep"] for a in acct if not a.get("missing")]
    short = {r: Path(r).name for r in reps}
    miss = [a["rep"] for a in acct if a.get("missing")]
    out.append(f"## `{model}` — condition `{cond}`\n")
    if miss:
        out.append("_Missing replicate files, skipped: "
                   + ", ".join('`' + Path(m).name + '`' for m in miss) + "._\n")
    if not rows:
        out.append("_No scorable draws._\n")
        return "\n".join(out)

    # ---- 0. draw accounting -----------------------------------------------------------
    out.append("### 0. Draw accounting\n")
    out.append("| replicate | draws | degenerate | entities | paired | unmatched | no `type_confidence` |")
    out.append("|---|---|---|---|---|---|---|")
    for a in acct:
        if a.get("missing"):
            continue
        out.append(f"| `{Path(a['rep']).name}` | {a['draws']} | **{a['degen']}** | {a['ents']} | "
                   f"{a['paired']} | {a['unmatched']} | {a['no_conf']} |")
    tot = {k: sum(a.get(k, 0) for a in acct if not a.get("missing"))
           for k in ("draws", "degen", "ents", "paired", "unmatched", "no_conf")}
    out.append(f"| **all {len(reps)}** | **{tot['draws']}** | **{tot['degen']}** | "
               f"**{tot['ents']}** | **{tot['paired']}** | **{tot['unmatched']}** | "
               f"**{tot['no_conf']}** |")
    # A file produced against `corpus.py` would index 0–79 and every stratum label below
    # would be silently wrong. 8 draws of 40 from 100 leave indices ≥ 80 unseen with
    # probability ~0, so this is a reliable tell and cheap insurance.
    suspect = [Path(a["rep"]).name for a in acct
               if not a.get("missing") and a["draws"] and a["max_idx"] < len(_PLAIN)]
    if suspect:
        out.append(f"\n> **Warning — wrong corpus?** No subject index ≥ {len(_PLAIN)} appears "
                   f"in {', '.join('`'+s+'`' for s in suspect)}, which is what a run against "
                   f"`corpus.py`'s {len(_PLAIN)} subjects looks like. Every stratum label "
                   f"below would then be meaningless. Check `run.py`'s corpus switch.")
    out.append("\nDegenerate draws are excluded from every table below and are an outcome in "
               "their own right (CRITERIA.md, fourth amendment). Unmatched entities pair with "
               "no drawn subject, so they carry no stratum and no ground truth; they are "
               "counted here and scored nowhere.\n")

    # ---- 1. distribution by stratum ---------------------------------------------------
    drawn = collections.Counter()
    pby = collections.Counter()
    for a in acct:
        if not a.get("missing"):
            drawn.update(a["drawn"])
            pby.update(a["paired_by"])
    out.append("### 1. `type_confidence` distribution by stratum\n")
    out.append("| stratum | drawn | paired | pairing | n conf | mean | median | p10 | p25 | p75 | min | "
               + " | ".join(f"<{t:g}" for t in (0.7, 0.8, 0.9, 0.95, 1.0)) + " |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|" + "---|" * 5)
    for s in STRATA:
        c = [r.conf for r in rows if r.stratum == s and r.conf is not None]
        pr = f"{pby[s]/drawn[s]*100:.0f}%" if drawn[s] else "—"
        if not c:
            out.append(f"| `{s}` | {drawn[s]} | {pby[s]} | {pr} | 0 |" + " — |" * 11)
            continue
        below = " | ".join(f"{sum(1 for x in c if x < t)/len(c)*100:.1f}%"
                           for t in (0.7, 0.8, 0.9, 0.95, 1.0))
        out.append(f"| `{s}` | {drawn[s]} | {pby[s]} | {pr} | {len(c)} | {mean(c):.3f} | "
                   f"{median(c):.3f} | {fmt(pctl(c, 0.10))} | {fmt(pctl(c, 0.25))} | "
                   f"{fmt(pctl(c, 0.75))} | {min(c):.3f} | {below} |")
    out.append("\nA number pooled across these rows would be meaningless — 40 of the corpus's "
               "100 subjects are contested by construction. `pairing` is the share of drawn "
               "subjects an entity could be matched to; if it differs sharply by stratum, the "
               "confidence distributions are conditioned on different selection.\n")

    # ---- 2. separation ----------------------------------------------------------------
    out.append("### 2. Separation between strata (within-draw, then across replicates)\n")
    out.append("Each contrast is computed inside a draw and averaged over draws, so a draw "
               "that runs globally high or low cancels. `A|B` rows are placebo splits of a "
               "control stratum against itself: their true value is zero, so they are this "
               "instrument's noise floor.\n")
    out.append("| contrast | " + " | ".join(f"`{short[r]}`" for r in reps) +
               " | Δ mean [min–max] | Δ median | draws |")
    out.append("|---|" + "---|" * (len(reps) + 3))

    def row_for(label, pa, pb):
        per = []
        for rp in reps:
            rr = [r for r in rows if r.rep == rp]
            m, _md, _n = contrast(rr, pa, pb)
            per.append(m)
        m_all, md_all, n_all = contrast(rows, pa, pb)
        got = [x for x in per if x is not None]
        rng = f"{mean(got):+.4f} [{min(got):+.4f}–{max(got):+.4f}]" if got else "—"
        cells = " | ".join(fmt(x, "+.4f") for x in per)
        out.append(f"| {label} | {cells} | {rng} | {fmt(md_all, '+.4f')} | {n_all} |")
        return got

    ranges = {}
    for label, a, b in CONTRASTS:
        ranges[label] = row_for(label, stratum_pick(a), stratum_pick(b))
    floor = []
    for label, table in PLACEBO.items():
        floor += row_for(f"_placebo_ {label}", half_pick(table, 0), half_pick(table, 1))

    if floor:
        lo, hi = min(floor), max(floor)
        out.append(f"\nPlacebo floor over {len(floor)} split-half contrast(s): "
                   f"**[{lo:+.4f}, {hi:+.4f}]**. A real contrast is readable only if it sits "
                   f"outside that band.\n")
        out.append("| contrast | range | outside the placebo floor? |")
        out.append("|---|---|---|")
        for label, got in ranges.items():
            if not got:
                out.append(f"| {label} | — | — |")
                continue
            out.append(f"| {label} | [{min(got):+.4f}, {max(got):+.4f}] | "
                       f"{'**yes**' if (min(got) > hi or max(got) < lo) else 'no'} |")
    if len(reps) < 2:
        out.append("\n_One replicate only. The across-replicate range is undefined and the "
                   "placebo floor is doing all the work; CRITERIA.md's fourth amendment asks "
                   "for repeated measures before a small difference is quoted._")

    out.append("\n**Per-replicate stratum means** (the run-to-run floor on the levels "
               "themselves, as distinct from the differences):\n")
    out.append("| stratum | " + " | ".join(f"`{short[r]}`" for r in reps) + " | range |")
    out.append("|---|" + "---|" * (len(reps) + 1))
    for s in STRATA:
        per = []
        for rp in reps:
            c = [r.conf for r in rows if r.rep == rp and r.stratum == s and r.conf is not None]
            per.append(mean(c) if c else None)
        got = [x for x in per if x is not None]
        rng = f"{max(got)-min(got):.4f}" if got else "—"
        out.append(f"| `{s}` | " + " | ".join(fmt(x) for x in per) + f" | {rng} |")

    # ---- 3. considered_types ----------------------------------------------------------
    out.append("\n### 3. `considered_types` as the trigger (#35 item 2)\n")
    out.append("| stratum | rows | non-empty | mean types named | contains `alt` | "
               "names the unchosen pair member | non-empty but misses `alt` |")
    out.append("|---|---|---|---|---|---|---|")
    for s in STRATA:
        rs = [r for r in rows if r.stratum == s]
        if not rs:
            out.append(f"| `{s}` | 0 |" + " — |" * 6)
            continue
        ne = [r for r in rs if r.cons]
        named = f"{mean(len(r.cons) for r in ne):.2f}" if ne else "—"
        if s in CONTROL_STRATA:
            hit = other = missing = "—"
        else:
            n_alt = sum(1 for r in rs if names(r.cons, r.alt))
            n_oth = sum(1 for r in rs if names(r.cons, r.alt if r.etype == r.gold else r.gold)
                        or (r.etype not in (r.gold, r.alt)
                            and (names(r.cons, r.alt) or names(r.cons, r.gold))))
            hit = f"{n_alt} ({n_alt/len(rs)*100:.1f}%)"
            other = f"{n_oth} ({n_oth/len(rs)*100:.1f}%)"
            n_miss = len(ne) - n_alt
            missing = f"{n_miss} ({n_miss/len(rs)*100:.1f}%)"
        label = f"`{s}`" + (" **(false positives)**" if s in CONTROL_STRATA else "")
        out.append(f"| {label} | {len(rs)} | {len(ne)} ({len(ne)/len(rs)*100:.1f}%) | "
                   f"{named} | {hit} | {other} | {missing} |")

    amb = [r for r in rows if r.stratum == "ambiguous"]
    mat = [r for r in rows if r.stratum == "control-matched"]
    if amb and mat:
        tp = sum(1 for r in amb if r.cons) / len(amb) * 100
        fp = sum(1 for r in mat if r.cons) / len(mat) * 100
        out.append(f"\nSensitivity {tp:.1f}% on `ambiguous`, false-positive rate {fp:.1f}% on "
                   f"`control-matched` — same length, same clause count, no contested type. "
                   f"Separation **{tp-fp:+.1f} pp**.")
    out.append("\n`alt` is ground truth and unavailable at runtime, so the `alt` columns "
               "diagnose the signal's *quality*; only `non-empty` is a deployable trigger. "
               "Entries restating the entity's own `entity_type` are dropped before counting.\n")

    # ---- 4. threshold / trigger sweep -------------------------------------------------
    out.append("### 4. What each candidate trigger would catch and cost\n")
    out.append("| trigger | `ambiguous` (TP) | `control-matched` (FP) | `control` (FP) | "
               "`fence` | TP − FP(matched) |")
    out.append("|---|---|---|---|---|---|")

    def sweep(label, fires, elig):
        cells, vals = [], {}
        for s in STRATA:
            rs = [r for r in rows if r.stratum == s and elig(r)]
            if not rs:
                cells.append("—")
                vals[s] = None
                continue
            k = sum(1 for r in rs if fires(r))
            vals[s] = k / len(rs) * 100
            cells.append(f"{k}/{len(rs)} ({vals[s]:.1f}%)")
        sep = ("—" if vals["ambiguous"] is None or vals["control-matched"] is None
               else f"{vals['ambiguous']-vals['control-matched']:+.1f} pp")
        out.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {sep} |")
        if vals["ambiguous"] is not None and vals["control-matched"] is not None:
            return (vals["ambiguous"] - vals["control-matched"], label)
        return None

    has_conf = lambda r: r.conf is not None            # noqa: E731
    always = lambda r: True                            # noqa: E731
    scored = []
    for t in THRESHOLDS:
        got = sweep(f"`type_confidence` < {t:g}", lambda r, t=t: r.conf < t, has_conf)
        if got:
            scored.append(got)
    for label, f in [("`considered_types` non-empty", lambda r: bool(r.cons)),
                     ("`considered_types` names ≥2", lambda r: len(r.cons) >= 2),
                     ("conf < 0.9 **or** `considered_types` non-empty",
                      lambda r: bool(r.cons) or (r.conf is not None and r.conf < 0.9)),
                     ("conf < 1.0 **and** `considered_types` non-empty",
                      lambda r: bool(r.cons) and r.conf is not None and r.conf < 1.0)]:
        got = sweep(label, f, always)
        if got:
            scored.append(got)
    out.append("\nDenominators differ by row: `type_confidence` rows count only entities that "
               "carried a numeric one, `considered_types` rows count every paired entity. "
               "`fence` is shown for information and is not part of the headline.")
    if scored:
        best = max(scored, key=lambda x: x[0])   # ties keep the earlier, simpler trigger
        out.append(f"\nLargest sensitivity-minus-false-positive gap on this run: "
                   f"**{best[0]:+.1f} pp** ({best[1]}). That is arithmetic over these draws, "
                   f"not a recommended threshold — read it against §2's placebo floor.")
    return "\n".join(out) + "\n"


def parse_args(argv):
    conds, models = collections.OrderedDict(), []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--model", "-m"):
            models.append(argv[i + 1])
            i += 2
            continue
        name, files = a.split("=", 1) if "=" in a else (Path(a).stem, a)
        conds.setdefault(name, []).extend(f for f in files.split(",") if f)
        i += 1
    return conds, models


def main():
    conds, models = parse_args(sys.argv[1:])
    if not conds:
        print("Usage:\n    " + __doc__.split("Usage:")[1].strip())
        return 2
    if not models:
        seen = set()
        for paths in conds.values():
            for p in paths:
                path = HERE / p if not Path(p).is_absolute() else Path(p)
                if not path.exists():
                    continue
                for line in path.read_text().splitlines():
                    if line.strip():
                        seen.add(json.loads(line)["model"])
        models = sorted(seen)

    print("# Confidence separation — `corpus_ambiguous.py`\n")
    print(f"Conditions: {', '.join(f'`{c}` ({len(p)} replicate(s))' for c, p in conds.items())} "
          f"· models: {', '.join('`'+m+'`' for m in models)}")
    print(f"Pairing: `type_accuracy.pair`, greedy one-to-one at `COVER_T = {COVER_T}`. "
          f"Degenerate draw: `done_reason: length` or < {DEGENERATE_MIN_ENTITIES} entities "
          f"from 40 subjects.")
    print(f"Strata drawn from: ambiguous {len(CA.AMBIGUOUS_INDICES)}, control-matched "
          f"{len(CA.MATCHED_INDICES)}, control {len(CA.CONTROL_INDICES)}, fence "
          f"{len(CA.FENCE_INDICES)} — 40 sampled per draw, so per-draw stratum sizes vary.\n")
    for cond, paths in conds.items():
        for m in models:
            rows, acct = load(cond, m, paths)
            print(report(cond, m, rows, acct))
    return 0


if __name__ == "__main__":
    sys.exit(main())
