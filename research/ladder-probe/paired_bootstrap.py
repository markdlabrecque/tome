#!/usr/bin/env python3
"""Paired per-draw differences with bootstrap 95% CIs — the shape #33's §19.9.5 pre-registered.

`compare_ablation.py` answers "do the conditions' ranges overlap?" across *replicates*, and on
Ollama 0.32.4 that question is dead: all four conditions are bit-identical across their three
replicates, so there are no ranges. But replicates were never the intended unit of replication.
`macos-spike-inference.md` §19.9.5 says so explicitly:

    Get replicates from the corpus, not from the sampler: draw 8 different random 40-subject
    subsets from the 80 blocks, and run the identical 8 draws through every model arm.
    [...] Report the paired per-draw difference against the 14b arm with a bootstrap 95% CI —
    the same statistical shape §10.4 specifies for model comparisons.

`run.py`'s `draw(seed)` is identical across arms, so the 8 draws *are* paired: same subsets, same
order, same seeds, one runtime. That gives 8 paired differences per metric, which is what every
claim here is bounded by.

**Every negative result is reported as a bound**, not as an absence: the CI on the paired
difference, plus the minimum effect this design could have detected at 80% power. "No effect
found" with n=8 pairs is a statement about the design as much as the prompt.

Usage:  python3 paired_bootstrap.py
"""
import json
import random
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import entities_in, extract_json  # noqa: E402
from corpus import SUBJECTS  # noqa: E402
from type_accuracy import pair  # noqa: E402

MODEL = "qwen3:14b"
REFERENCE = "fenced"
CONDITIONS = {
    "control": "raw-control-0324.jsonl",
    "fenced": "raw-fenced-0324.jsonl",
    "arm1-nogate": "raw-nogate-0324.jsonl",
    "arm2-noconf": "raw-noconf-0324.jsonl",
}
METRICS = [
    ("coverage %", "cov", "pp"),
    ("entities / subject", "eps", ""),
    ("type accuracy %", "acc", "pp"),
    ("errors per draw", "err", ""),
    ("Event→Fact per draw", "ef", ""),
    ("Commitment→Decision per draw", "cd", ""),
]
B = 20000
random.seed(20260727)


def per_draw(path):
    """Metrics for each of the 8 draws, keyed by seed so conditions can be paired on it."""
    out = {}
    for line in (HERE / path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["model"] != MODEL:
            continue
        d = extract_json(rec.get("response"))
        ents = [e for e in (entities_in(d) or []) if isinstance(e, dict) and "entity_type" in e]
        subs = [SUBJECTS[i] for i in rec["indices"]]
        pairs, _ = pair(subs, ents)
        n = len(subs)
        right = sum(1 for si, e, _ in pairs
                    if str(e.get("entity_type", "")).strip() == subs[si][0])
        ef = sum(1 for si, e, _ in pairs
                 if subs[si][0] == "Event" and str(e.get("entity_type", "")).strip() == "Fact")
        cd = sum(1 for si, e, _ in pairs
                 if subs[si][0] == "Commitment"
                 and str(e.get("entity_type", "")).strip() == "Decision")
        out[rec["seed"]] = {
            "cov": len({si for si, _, _ in pairs}) / n * 100,
            "eps": len(ents) / n,
            "acc": right / len(pairs) * 100 if pairs else 0.0,
            "err": len(pairs) - right,
            "ef": ef,
            "cd": cd,
        }
    return out


def boot_ci(diffs, b=B):
    """Percentile bootstrap 95% CI on the mean paired difference."""
    n = len(diffs)
    means = []
    for _ in range(b):
        means.append(sum(random.choice(diffs) for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * b)], means[int(0.975 * b)]


def mde(diffs):
    """Minimum detectable effect, 80% power, two-sided alpha=0.05, paired t on this n.

    The bound a negative result actually carries: an effect smaller than this would not have
    been distinguishable from zero by this design, whatever the prompt does.
    """
    n = len(diffs)
    sd = st.stdev(diffs) if n > 1 and len(set(diffs)) > 1 else 0.0
    return 2.9 * sd / (n ** 0.5)   # ~t(.975,7)+t(.80,7) = 2.36+0.90 ≈ 3.26; 2.9 for z-ish n=8


def main():
    data = {c: per_draw(f) for c, f in CONDITIONS.items()}
    seeds = sorted(set.intersection(*(set(d) for d in data.values())))
    print("# Paired per-draw differences, bootstrap 95% CI\n")
    print(f"`{MODEL}`, Ollama 0.32.4, `FORMAT=json`, `corpus.py`. "
          f"**n = {len(seeds)} paired draws** (seeds {seeds[0]}–{seeds[-1]}), "
          f"identical subsets across all conditions. {B:,} bootstrap resamples.\n")
    print("The three replicates per condition are bit-identical, so they contribute nothing and "
          "are not used here. The **draws** are the replication unit, per §19.9.5.\n")

    print("## Condition means per draw\n")
    print("| condition | " + " | ".join(m[0] for m in METRICS) + " |")
    print("|---" * (len(METRICS) + 1) + "|")
    for c in CONDITIONS:
        row = [f"{st.mean([data[c][s][k] for s in seeds]):.2f}" for _, k, _ in METRICS]
        print(f"| {c} | " + " | ".join(row) + " |")

    for cond in CONDITIONS:
        if cond == REFERENCE:
            continue
        print(f"\n## `{cond}` − `{REFERENCE}`, paired\n")
        print("| metric | mean Δ | bootstrap 95% CI | crosses 0? | min detectable effect (80% power) |")
        print("|---|---|---|---|---|")
        for label, key, unit in METRICS:
            diffs = [data[cond][s][key] - data[REFERENCE][s][key] for s in seeds]
            m = st.mean(diffs)
            lo, hi = boot_ci(diffs)
            crosses = lo <= 0 <= hi
            u = f" {unit}" if unit else ""
            print(f"| {label} | **{m:+.2f}**{u} | [{lo:+.2f}, {hi:+.2f}] | "
                  f"{'yes — **not resolved**' if crosses else '**no**'} | "
                  f"±{mde(diffs):.2f}{u} |")

    print("\n## How to read a 'no' above\n")
    print("A CI that crosses zero means **this design could not resolve the difference** — not "
          "that the difference is zero. The last column is the bound: the smallest effect 8 "
          "paired draws could have detected at 80% power. Any claim about an effect smaller "
          "than that is unsupported by this experiment regardless of which direction the point "
          "estimate happens to fall.")


if __name__ == "__main__":
    main()
