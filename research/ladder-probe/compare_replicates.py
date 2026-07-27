#!/usr/bin/env python3
"""Score the #36 fence across replicates, per CRITERIA.md's fourth amendment.

The probe is not reproducible run to run, so a single paired A/B cannot support a claim
about a 3-6 count difference. This reads three replicates per condition and asks the only
question three replicates can answer honestly: **do the two conditions' ranges overlap?**

Degenerate draws (`done_reason: length`, or fewer than 10 entities from 40 subjects)
measure the decoder rather than the prompt. They are excluded from accuracy and coverage
and counted as an outcome in their own right.

Usage:  python3 compare_replicates.py
"""
import collections
import json
import sys
from pathlib import Path
from statistics import mean

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import score_record  # noqa: E402
from compare_fence import cell_types  # noqa: E402

DEGENERATE_MIN_ENTITIES = 10

PLAN = {
    "qwen3:14b": {
        "control": ["raw.jsonl", "raw-control-replication.jsonl", "raw-control-r3.jsonl"],
        "fenced": ["raw-fenced.jsonl", "raw-fenced-r2.jsonl", "raw-fenced-r3.jsonl"],
    },
    "qwen3:4b": {
        "control": ["raw.jsonl", "raw-control-4b-r2.jsonl", "raw-control-4b-r3.jsonl"],
        "fenced": ["raw-fenced.jsonl", "raw-fenced-4b-r2.jsonl", "raw-fenced-4b-r3.jsonl"],
    },
}


def replicate(path, model):
    """Score one 8-draw replicate. Returns None if the file is absent."""
    p = HERE / path
    if not p.exists():
        return None
    n = right = degen = 0
    conf = collections.Counter()
    cov, eps = [], []
    seen = 0
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["model"] != model:
            continue
        seen += 1
        sc = score_record(r)
        if r.get("done_reason") == "length" or sc["n_entities"] < DEGENERATE_MIN_ENTITIES:
            degen += 1
            continue
        cov.append(sc["covered"] / sc["n_subjects"])
        eps.append(sc["n_entities"] / sc["n_subjects"])
        cn, cr, cc = cell_types(r)
        n += cn
        right += cr
        conf.update(cc)
    if not seen:
        return None
    return {"file": path, "draws": seen, "degen": degen, "n": n, "right": right,
            "acc": right / n * 100 if n else 0.0, "errors": n - right,
            "ef": conf[("Event", "Fact")], "conf": conf,
            "cov": mean(cov) * 100 if cov else 0.0,
            "eps": mean(eps) if eps else 0.0}


def main():
    for model, conds in PLAN.items():
        print(f"\n# `{model}`\n")
        got = {}
        print("| condition | replicate | Event→Fact | real errors | type accuracy | coverage | ent/subj | degenerate draws |")
        print("|---|---|---|---|---|---|---|---|")
        for cond, files in conds.items():
            reps = [r for r in (replicate(f, model) for f in files) if r]
            got[cond] = reps
            for r in reps:
                print(f"| {cond} | `{r['file']}` | {r['ef']} | {r['errors']} | {r['acc']:.1f}% | "
                      f"{r['cov']:.1f}% | {r['eps']:.2f} | {r['degen']} |")
        if not all(got.values()):
            print("\n_(incomplete — some replicates missing)_")
            continue

        print(f"\n**Condition summary — {model}**\n")
        print("| metric | control (range) | fenced (range) | ranges overlap? |")
        print("|---|---|---|---|")
        for label, key, fmt in [("Event→Fact", "ef", "{:.1f}"), ("real errors", "errors", "{:.1f}"),
                                ("type accuracy %", "acc", "{:.1f}"), ("coverage %", "cov", "{:.1f}"),
                                ("degenerate draws", "degen", "{:.1f}")]:
            c = [r[key] for r in got["control"]]
            f = [r[key] for r in got["fenced"]]
            overlap = not (max(f) < min(c) or min(f) > max(c))
            print(f"| {label} | {fmt.format(mean(c))} [{min(c)}–{max(c)}] | "
                  f"{fmt.format(mean(f))} [{min(f)}–{max(f)}] | {'yes' if overlap else '**no**'} |")

        ctl_conf, fen_conf = collections.Counter(), collections.Counter()
        for r in got["control"]:
            ctl_conf.update(r["conf"])
        for r in got["fenced"]:
            fen_conf.update(r["conf"])
        print(f"\n**Confusions, summed over 3 replicates each — {model}**\n")
        print("| confusion | control | fenced | Δ |")
        print("|---|---|---|---|")
        for k in sorted(set(ctl_conf) | set(fen_conf), key=lambda k: -(ctl_conf[k] + fen_conf[k])):
            print(f"| {k[0]} → {k[1]} | {ctl_conf[k]} | {fen_conf[k]} | {fen_conf[k]-ctl_conf[k]:+d} |")
        worst = max(((fen_conf[k] - ctl_conf[k]), k) for k in set(ctl_conf) | set(fen_conf))
        print(f"\nLargest increase in any single confusion: **{worst[0]:+d}** ({worst[1][0]} → {worst[1][1]})")


if __name__ == "__main__":
    main()
