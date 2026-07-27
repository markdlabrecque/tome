#!/usr/bin/env python3
"""Before/after for the #36 prompt fence, scored against CRITERIA.md's third amendment.

Pairs on seed — every draw is identical between the two conditions — so the difference is
reported as a paired bootstrap CI, not two bare percentages.

Usage:  python3 compare_fence.py <baseline.jsonl> <fenced.jsonl> [model ...]
"""
import collections
import json
import random
import sys
from pathlib import Path
from statistics import mean

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analyze import boot, entities_in, extract_json, score_record, toks  # noqa: E402
from corpus import SUBJECTS  # noqa: E402

REAL = 0.6   # overlap at/above which a match is the *same* subject (third amendment)


def cell_types(rec):
    """(n_matched, n_correct, Counter(confusions)) for one draw, real matches only."""
    d = extract_json(rec.get("response"))
    ents = [e for e in (entities_in(d) or []) if isinstance(e, dict) and "entity_type" in e]
    subs = [SUBJECTS[i] for i in rec["indices"]]
    et = [toks(f"{e.get('natural_key','')} {e.get('summary','')}") for e in ents]
    n = right = 0
    conf = collections.Counter()
    for truth, _mk, text in subs:
        st = toks(text)
        if not st:
            continue
        best, bi = 0.0, None
        for i, t in enumerate(et):
            ov = len(st & t) / len(st)
            if ov > best:
                best, bi = ov, i
        if best >= REAL:
            n += 1
            got = str(ents[bi].get("entity_type", "")).strip()
            if got == truth:
                right += 1
            else:
                conf[(truth, got)] += 1
    return n, right, conf


def load(path, model):
    out = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["model"] == model:
            out[r["seed"]] = r
    return out


def condition(recs):
    seeds = sorted(recs)
    acc, conf, n_tot, r_tot = [], collections.Counter(), 0, 0
    cov, eps, fshare = [], [], []
    for s in seeds:
        n, right, c = cell_types(recs[s])
        acc.append(right / n if n else 0.0)
        conf.update(c)
        n_tot += n
        r_tot += right
        sc = score_record(recs[s])
        cov.append(sc["covered"] / sc["n_subjects"])
        eps.append(sc["n_entities"] / sc["n_subjects"])
        fshare.append(sc["fact_share"])
    return {"seeds": seeds, "acc": acc, "conf": conf, "n": n_tot, "right": r_tot,
            "cov": cov, "eps": eps, "fshare": fshare}


def main():
    base_p, fenced_p = sys.argv[1], sys.argv[2]
    models = sys.argv[3:] or ["qwen3:14b", "qwen3:4b"]
    print(f"# Prompt-fence A/B — `{Path(base_p).name}` → `{Path(fenced_p).name}`\n")

    for m in models:
        b_recs, f_recs = load(base_p, m), load(fenced_p, m)
        shared = sorted(set(b_recs) & set(f_recs))
        if not shared:
            continue
        b = condition({s: b_recs[s] for s in shared})
        f = condition({s: f_recs[s] for s in shared})
        print(f"## `{m}` — {len(shared)} paired draws\n")
        print("| metric | before | after | Δ |")
        print("|---|---|---|---|")
        ba, fa = b["right"] / max(b["n"], 1) * 100, f["right"] / max(f["n"], 1) * 100
        print(f"| type accuracy (real matches) | {ba:.1f}% | {fa:.1f}% | {fa-ba:+.1f} pp |")
        print(f"| real misclassifications | {b['n']-b['right']} | {f['n']-f['right']} | "
              f"{(f['n']-f['right'])-(b['n']-b['right']):+d} |")
        print(f"| **Event → Fact** | **{b['conf'][('Event','Fact')]}** | "
              f"**{f['conf'][('Event','Fact')]}** | "
              f"**{f['conf'][('Event','Fact')]-b['conf'][('Event','Fact')]:+d}** |")
        print(f"| subjects confidently matched | {b['n']} | {f['n']} | {f['n']-b['n']:+d} |")
        print(f"| coverage (recall guard) | {mean(b['cov'])*100:.1f}% | {mean(f['cov'])*100:.1f}% | "
              f"{(mean(f['cov'])-mean(b['cov']))*100:+.1f} pp |")
        print(f"| ent/subj (recall guard) | {mean(b['eps']):.2f} | {mean(f['eps']):.2f} | "
              f"{mean(f['eps'])-mean(b['eps']):+.3f} |")
        print(f"| Fact share | {mean(b['fshare'])*100:.1f}% | {mean(f['fshare'])*100:.1f}% | "
              f"{(mean(f['fshare'])-mean(b['fshare']))*100:+.1f} pp |")
        d = [(x - y) * 100 for x, y in zip(f["acc"], b["acc"])]
        lo, hi = boot(d)
        print(f"\nPaired bootstrap on per-draw accuracy, 10k resamples: "
              f"**{mean(d):+.1f} pp [{lo:+.1f}, {hi:+.1f}]**\n")

        allk = set(b["conf"]) | set(f["conf"])
        rows = sorted(allk, key=lambda k: -(b["conf"][k] + f["conf"][k]))
        print("| confusion | before | after |")
        print("|---|---|---|")
        for k in rows:
            if b["conf"][k] or f["conf"][k]:
                print(f"| {k[0]} → {k[1]} | {b['conf'][k]} | {f['conf'][k]} |")
        new = [k for k in rows if f["conf"][k] > b["conf"][k]]
        if new:
            worst = max(f["conf"][k] - b["conf"][k] for k in new)
            print(f"\nLargest *increase* in any single confusion: **+{worst}** "
                  f"({', '.join(f'{k[0]}→{k[1]}' for k in new if f['conf'][k]-b['conf'][k] == worst)})")
        print()


if __name__ == "__main__":
    main()
