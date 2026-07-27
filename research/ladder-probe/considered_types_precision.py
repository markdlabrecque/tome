#!/usr/bin/env python3
"""Does a non-empty `considered_types` predict a misclassification?

#35 concluded `considered_types` is not adoptable, on the stated ground that it is **never
populated** — "empty on ~2,950 entities across three wordings and two models". That ground is
wrong twice over:

1. `CONFIDENCE-FINDINGS.md` §2's own table reports 15 non-empty values (12 in 14b fenced/gated,
   3 in 4b control/gated) while its prose says the field is empty on all of them.
2. §2 only ever examined `corpus_ambiguous`. On **`corpus.py` with the shipped fenced prompt**
   the field fires on **13.9%** of paired entities — three times the highest rate that section
   found, and on the corpus production would actually resemble.

So the field *is* populated, and the real question — never asked — is whether firing carries
information. This script asks it: pair emitted entities to drawn subjects exactly as
`type_accuracy.py` does, then cross the fire against the ground truth.

The number that matters is **precision against the base rate of error**. A trigger that fires
on 13.9% of entities to find errors that occur in 2.3% of them must beat 2.3% by enough to be
worth reading, and it must beat it on *distinct subjects* rather than on replicate copies of
the same subject — this corpus is deterministic on the fenced prompt, so three replicates of
one hit are one hit.

Usage:  python3 considered_types_precision.py [file ...]        (default: the 3 fenced 14b replicates)
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import entities_in, extract_json  # noqa: E402
from corpus import SUBJECTS  # noqa: E402
from type_accuracy import pair  # noqa: E402

MODEL = "qwen3:14b"
DEFAULT = ["raw-fenced.jsonl", "raw-fenced-r2.jsonl", "raw-fenced-r3.jsonl"]


def analyse(files, model=MODEL):
    cells = collections.Counter()
    fired_wrong, fired_right, missed = [], [], []
    for f in files:
        p = HERE / f
        if not p.exists():
            print(f"_(missing: {f})_")
            continue
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["model"] != model:
                continue
            d = extract_json(rec.get("response"))
            ents = [e for e in (entities_in(d) or [])
                    if isinstance(e, dict) and "entity_type" in e]
            subs = [SUBJECTS[i] for i in rec["indices"]]
            pairs, _ = pair(subs, ents)
            for si, e, _ov in pairs:
                truth = subs[si][0]
                key = subs[si][1]
                got = str(e.get("entity_type", "")).strip()
                v = e.get("considered_types")
                fired = isinstance(v, list) and len(v) > 0
                wrong = got != truth
                cells[(fired, wrong)] += 1
                if fired and wrong:
                    fired_wrong.append((key, truth, got, tuple(v)))
                elif fired and not wrong:
                    fired_right.append((key, truth, tuple(v)))
                elif wrong:
                    missed.append((key, truth, got))
    return cells, fired_wrong, fired_right, missed


def main():
    files = sys.argv[1:] or DEFAULT
    cells, fw, fr, missed = analyse(files)
    tp, fp = cells[(True, True)], cells[(True, False)]
    fn, tn = cells[(False, True)], cells[(False, False)]
    n = tp + fp + fn + tn
    if not n:
        print("no paired entities — nothing to score")
        return

    print(f"# `considered_types` as an error trigger — `{MODEL}`\n")
    print(f"Files: {', '.join(f'`{f}`' for f in files)}\n")
    print("| | misclassified | correct | total |")
    print("|---|---|---|---|")
    print(f"| **fired** (non-empty) | {tp} | {fp} | {tp+fp} |")
    print(f"| **empty** | {fn} | {tn} | {fn+tn} |")
    print(f"| total | {tp+fn} | {fp+tn} | {n} |")

    base = (tp + fn) / n * 100
    prec = tp / (tp + fp) * 100 if tp + fp else 0.0
    rec = tp / (tp + fn) * 100 if tp + fn else 0.0
    print(f"\n- fire rate: **{(tp+fp)/n*100:.1f}%** ({tp+fp}/{n})")
    print(f"- base rate of error: **{base:.1f}%** ({tp+fn}/{n}) — precision must beat this")
    print(f"- precision (fired → actually wrong): **{prec:.1f}%**"
          f"  → lift **{prec/base:.2f}×**" if base else "")
    print(f"- recall (wrong → fired): **{rec:.1f}%** — it misses {fn} of {tp+fn} errors")

    # Determinism correction: replicate copies of one subject are not independent hits.
    d_fw = {k for k, *_ in fw}
    d_missed = {k for k, *_ in missed}
    print(f"\n**Deduplicated by subject** — this corpus is deterministic on the fenced prompt, "
          f"so replicate copies of one hit are one hit:\n")
    print(f"- distinct subjects the fire caught: **{len(d_fw)}** ({sorted(d_fw)})")
    print(f"- distinct misclassified subjects it missed: **{len(d_missed)}**")
    named = sum(1 for _k, truth, _got, v in fw if truth in v)
    print(f"- of the caught ones, times the named alternative *was* the correct type: "
          f"**{named}/{len(fw)}** raw")

    if fw:
        print("\n**The fires that were errors:**\n")
        print("| subject | truth | emitted | considered | named the truth? |")
        print("|---|---|---|---|---|")
        for k, truth, got, v in sorted(set(fw)):
            print(f"| `{k}` | {truth} | {got} | {list(v)} | "
                  f"{'yes' if truth in v else '**no**'} |")


if __name__ == "__main__":
    main()
