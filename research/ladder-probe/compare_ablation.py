#!/usr/bin/env python3
"""Score the #35/#36 prompt ablation — four conditions, one runtime (Ollama 0.32.4).

Sibling to `compare_replicates.py` rather than an extension of it: that script is the
committed record of the pre-upgrade two-condition analysis and its summary table is
hardcoded to control-vs-fenced. This one takes four conditions and a reference.

Two things it does that the older script does not, both of them lessons paid for:

1. **It hashes payloads.** Replicate *files* are not replicate *observations* — the
   pre-upgrade 14b fenced arm had 5 of 8 draws bit-identical across all three replicates,
   and a published "ranges do not overlap" claim turned out to be comparing a real 3-run
   spread against a zero-variance point. Where a condition has no variance this script says
   so and **withholds the overlap verdict** instead of printing a misleading one.

2. **It refuses cross-runtime comparison.** Every record carries `runtime` since `512e487`;
   any condition mixing runtimes, or differing from the others, is reported as an error.

Usage:  python3 compare_ablation.py
"""
import collections
import hashlib
import json
import sys
from pathlib import Path
from statistics import mean

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from compare_replicates import replicate  # noqa: E402

MODEL = "qwen3:14b"
REFERENCE = "fenced"          # the arms are deltas against the shipped fenced prompt
CONDITIONS = {
    "control": ["raw-control-0324.jsonl", "raw-control-0324-r2.jsonl", "raw-control-0324-r3.jsonl"],
    "fenced": ["raw-fenced-0324.jsonl", "raw-fenced-0324-r2.jsonl", "raw-fenced-0324-r3.jsonl"],
    "arm1-nogate": ["raw-nogate-0324.jsonl", "raw-nogate-0324-r2.jsonl", "raw-nogate-0324-r3.jsonl"],
    "arm2-noconf": ["raw-noconf-0324.jsonl", "raw-noconf-0324-r2.jsonl", "raw-noconf-0324-r3.jsonl"],
}
METRICS = [("Event→Fact", "ef"), ("Commitment→Decision", "cd"), ("real errors", "errors"),
           ("type accuracy %", "acc"), ("coverage %", "cov"), ("degenerate draws", "degen")]


def payload_hashes(path):
    """Per-seed hash of the model's raw text, for the given model only."""
    p = HERE / path
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["model"] != MODEL:
            continue
        out[r["seed"]] = hashlib.sha256((r.get("response") or "").encode()).hexdigest()[:10]
    return out


def runtimes(path):
    p = HERE / path
    if not p.exists():
        return set()
    return {json.loads(l).get("runtime") for l in p.read_text().splitlines() if l.strip()}


def distinct_observations(files):
    """How many of the replicates are genuinely distinct, draw by draw.

    Returns (n_distinct_replicate_vectors, per_seed_variance) where per_seed_variance counts
    seeds whose payload differs across at least two replicates. A condition with
    per_seed_variance == 0 is deterministic: its three files are one observation.
    """
    hs = [payload_hashes(f) for f in files]
    hs = [h for h in hs if h]
    if not hs:
        return 0, 0
    vectors = {tuple(sorted(h.items())) for h in hs}
    seeds = set().union(*(set(h) for h in hs))
    varying = sum(1 for s in seeds if len({h.get(s) for h in hs}) > 1)
    return len(vectors), varying


def main():
    print("# Prompt ablation — `qwen3:14b`, Ollama 0.32.4, FORMAT=json, corpus.py\n")

    data, determinism, rt_all = {}, {}, {}
    for cond, files in CONDITIONS.items():
        reps = [r for r in (replicate(f, MODEL) for f in files) if r]
        if reps:
            data[cond] = reps
        determinism[cond] = distinct_observations(files)
        rt = set().union(*(runtimes(f) for f in files)) if files else set()
        rt_all[cond] = {x for x in rt if x}

    # --- runtime gate: refuse to compare across runtimes -------------------------------
    seen_rt = set().union(*rt_all.values()) if rt_all else set()
    print("## Runtime provenance\n")
    for cond in CONDITIONS:
        print(f"- **{cond}**: {sorted(rt_all[cond]) or '(no data)'}")
    if len(seen_rt) > 1:
        print(f"\n> ⚠ **STOP — {len(seen_rt)} distinct runtimes across conditions: "
              f"{sorted(seen_rt)}. These are not comparable.**")
    print()

    # --- per-replicate ---------------------------------------------------------------
    print("## Per replicate\n")
    print("| condition | file | draws | Event→Fact | Commit→Dec | real errors | type acc | coverage |"
          " ent/subj | degen |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for cond, reps in data.items():
        for r in reps:
            # A replicate is 8 draws. Fewer means the file is still being written — flag it,
            # because a 1-draw file scores like a result and is not one.
            draws = f"{r['draws']}" if r["draws"] == 8 else f"**{r['draws']}/8**"
            print(f"| {cond} | `{r['file']}` | {draws} | {r['ef']} | "
                  f"{r['conf'][('Commitment','Decision')]} | "
                  f"{r['errors']} | {r['acc']:.1f}% | {r['cov']:.1f}% | {r['eps']:.2f} | {r['degen']} |")
    if any(r["draws"] != 8 for reps in data.values() for r in reps):
        print("\n> ⚠ Bolded draw counts are incomplete files. Their metrics are not results.")

    # --- determinism ------------------------------------------------------------------
    print("\n## Determinism — are these replicate observations, or replicate files?\n")
    print("| condition | replicate files | distinct draw-vectors | seeds that vary | reads as |")
    print("|---|---|---|---|---|")
    for cond, files in CONDITIONS.items():
        n_files = len([f for f in files if (HERE / f).exists()])
        vecs, varying = determinism[cond]
        verdict = ("no data" if not n_files else
                   f"**deterministic — {n_files} files, 1 observation**" if varying == 0 else
                   f"{varying}/8 draws vary")
        print(f"| {cond} | {n_files} | {vecs} | {varying} | {verdict} |")

    missing = [c for c in CONDITIONS if c not in data or len(data[c]) < 3]
    if missing:
        print(f"\n_(incomplete — fewer than 3 replicates for: {', '.join(missing)}. "
              "Ranges below are provisional.)_")

    if REFERENCE not in data:
        print(f"\n_(no reference condition `{REFERENCE}` yet — nothing to compare against.)_")
        return

    # --- condition ranges vs the reference --------------------------------------------
    for cond in data:
        if cond == REFERENCE:
            continue
        print(f"\n## `{cond}` vs `{REFERENCE}`\n")
        print(f"| metric | {REFERENCE} (range) | {cond} (range) | ranges overlap? |")
        print("|---|---|---|---|")
        _, ref_var = determinism[REFERENCE]
        _, arm_var = determinism[cond]
        for label, key in METRICS:
            ref = [r["conf"][("Commitment", "Decision")] if key == "cd" else r[key]
                   for r in data[REFERENCE]]
            arm = [r["conf"][("Commitment", "Decision")] if key == "cd" else r[key]
                   for r in data[cond]]
            overlap = not (max(arm) < min(ref) or min(arm) > max(ref))
            if ref_var == 0 or arm_var == 0:
                verdict = "_withheld — a side has no variance_"
            else:
                verdict = "yes" if overlap else "**no**"
            print(f"| {label} | {mean(ref):.1f} [{min(ref):.1f}–{max(ref):.1f}] | "
                  f"{mean(arm):.1f} [{min(arm):.1f}–{max(arm):.1f}] | {verdict} |")

    # --- confusions -------------------------------------------------------------------
    print("\n## Confusions, summed over replicates\n")
    sums = {c: collections.Counter() for c in data}
    for c, reps in data.items():
        for r in reps:
            sums[c].update(r["conf"])
    keys = sorted(set().union(*(set(s) for s in sums.values())),
                  key=lambda k: -sum(s[k] for s in sums.values()))
    cols = list(data)
    print("| confusion | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 1) + "|")
    for k in keys:
        print(f"| {k[0]} → {k[1]} | " + " | ".join(str(sums[c][k]) for c in cols) + " |")


if __name__ == "__main__":
    main()
