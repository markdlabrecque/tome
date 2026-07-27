#!/usr/bin/env python3
"""Score *classification* accuracy against the corpus's ground-truth types.

`analyze.py` scores recall and composition; it never scored type accuracy. Issue #36's
confusion table was produced ad hoc during the spike and never committed, so this exists
first to *reproduce* that table from the committed raw JSONL, and then to measure the
before/after of a prompt change against it.

Matching: an emitted entity is compared to a drawn subject only when the two can be paired.
Pairing is one-to-one and greedy by content-word overlap (the same tokenizer, stoplist and
0.25 threshold `analyze.py` uses for coverage), highest overlap first. Entities that pair
with no subject are `unmatched` and carry no ground truth, so they are excluded from
accuracy rather than counted as wrong.

Usage:  RAW=raw.jsonl python3 type_accuracy.py [model ...]
"""
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import entities_in, extract_json, toks, COVER_T  # noqa: E402
from corpus import SUBJECTS  # noqa: E402

TYPES = ["Person", "Project", "Preference", "Decision", "Fact", "Commitment", "Event"]


def pair(subs, ents):
    """One-to-one greedy pairing of drawn subjects to emitted entities.

    Returns (pairs, n_unmatched_entities) where pairs is [(subject_idx, entity, overlap)].
    """
    sub_toks = [toks(t) for _, _, t in subs]
    ent_toks = [toks(f"{e.get('natural_key','')} {e.get('summary','')}") for e in ents]
    cands = []
    for si, st in enumerate(sub_toks):
        if not st:
            continue
        for ei, et in enumerate(ent_toks):
            ov = len(st & et) / len(st)
            if ov >= COVER_T:
                cands.append((ov, si, ei))
    cands.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_s, used_e, pairs = set(), set(), []
    for ov, si, ei in cands:
        if si in used_s or ei in used_e:
            continue
        used_s.add(si)
        used_e.add(ei)
        pairs.append((si, ents[ei], ov))
    return pairs, len(ents) - len(used_e)


def score(raw_path, models=None):
    per = {}
    for line in Path(raw_path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        m = rec["model"]
        if models and m not in models:
            continue
        p = per.setdefault(m, {"n": 0, "right": 0, "unmatched": 0, "undrawn": 0,
                               "conf": collections.Counter(), "seeds": 0})
        p["seeds"] += 1
        d = extract_json(rec.get("response"))
        ents = entities_in(d) or []
        ents = [e for e in ents if isinstance(e, dict) and "entity_type" in e]
        subs = [SUBJECTS[i] for i in rec["indices"]]
        pairs, unmatched = pair(subs, ents)
        p["unmatched"] += unmatched
        for si, e, _ov in pairs:
            truth = subs[si][0]
            got = str(e.get("entity_type", "")).strip()
            p["n"] += 1
            if got == truth:
                p["right"] += 1
            else:
                p["conf"][(truth, got)] += 1
                if got not in TYPES:
                    p["undrawn"] += 1
    return per


def report(per):
    out = []
    out.append("| model | matched | type accuracy | wrong | unmatched entities |")
    out.append("|---|---|---|---|---|")
    for m, p in per.items():
        acc = p["right"] / max(p["n"], 1) * 100
        out.append(f"| `{m}` | {p['n']} | {acc:.1f}% | {p['n'] - p['right']} | {p['unmatched']} |")

    total = collections.Counter()
    for p in per.values():
        total.update(p["conf"])

    out.append("")
    out.append("**Wrong arrivals by destination type (summed across the models scored):**")
    out.append("")
    out.append("| destination | wrong arrivals |")
    out.append("|---|---|")
    dest = collections.Counter()
    for (_truth, got), n in total.items():
        dest[got] += n
    for t, n in dest.most_common():
        out.append(f"| {t} | {n} |")

    out.append("")
    out.append("**Largest confusions (truth → emitted):**")
    out.append("")
    out.append("| confusion | " + " | ".join(f"`{m}`" for m in per) + " | total |")
    out.append("|---|" + "---|" * (len(per) + 1))
    for (truth, got), n in total.most_common(12):
        cells = [str(per[m]["conf"].get((truth, got), 0)) for m in per]
        out.append(f"| {truth} → {got} | " + " | ".join(cells) + f" | {n} |")
    return "\n".join(out)


if __name__ == "__main__":
    raw = HERE / os.environ.get("RAW", "raw.jsonl")
    wanted = sys.argv[1:] or None
    per = score(raw, wanted)
    print(f"# Type accuracy — `{Path(raw).name}`\n")
    print(report(per))
