#!/usr/bin/env python3
"""Within-runtime fence A/B, and the same A/B on the stamped 0.32.1 baseline.

The Fedora box was upgraded Ollama 0.32.1 -> 0.32.4 on 2026-07-27 (PROVENANCE.md). Every
committed #36 number was measured on 0.32.1. The fenced arm re-run on 0.32.4 no longer
looked fenced, but that comparison crossed runtimes — the fourth amendment's exact error.
This scores control against fenced *within each runtime*, so the fence is only ever
compared to its own control.

Two things are reported that a bare metric table would hide:

* **Runtime provenance per file.** Records carry `runtime` and `model_digest` since
  `run.py` self-stamped (the 0.32.1 files predate that and are stamped by PROVENANCE.md,
  so an absent stamp is *expected* there and asserted to be absent, not silently allowed).
* **Payload hashes per (seed, replicate).** The fifth and sixth amendments: replicate
  *files* are not replicate *observations*, and which configurations happen to be
  bit-reproducible is not predictable from model, prompt or corpus. The number of
  *independent* observations per condition is a computed output, not the file count.

Usage:  python3 compare_runtime.py
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

# The two runtimes, each with its own control and fenced replicates. 0.32.1's lists are the
# ones FENCE-FINDINGS.md's 14b table was built from (compare_replicates.py's PLAN).
RUNTIMES = {
    "0.32.1 (stamped, pre-upgrade)": {
        "expect_stamp": None,       # predates run.py self-stamping; PROVENANCE.md covers it
        "control": ["raw.jsonl", "raw-control-replication.jsonl", "raw-control-r3.jsonl"],
        "fenced": ["raw-fenced.jsonl", "raw-fenced-r2.jsonl", "raw-fenced-r3.jsonl"],
    },
    "0.32.4 (post-upgrade)": {
        "expect_stamp": "ollama version is 0.32.4",
        "control": ["raw-control-ollama0324.jsonl", "raw-control-ollama0324-r2.jsonl"],
        "fenced": ["raw-fenced-ollama0324.jsonl", "raw-fenced-ollama0324-r2.jsonl",
                   "raw-fenced-ollama0324-r3.jsonl"],
    },
}

METRICS = [("Event→Fact", "ef"), ("real errors", "errors"), ("type accuracy %", "acc"),
           ("coverage %", "cov"), ("ent/subj", "eps"), ("degenerate draws", "degen")]


def records(path):
    p = HERE / path
    if not p.exists():
        return []
    return [r for r in (json.loads(l) for l in p.read_text().splitlines() if l.strip())
            if r["model"] == MODEL]


def payload_hash(rec):
    return hashlib.sha256((rec.get("response") or "").encode()).hexdigest()[:8]


def provenance(files, expect):
    """Report the runtime stamp and model digest on every file, and whether it is as expected."""
    rows, ok = [], True
    for f in files:
        recs = records(f)
        if not recs:
            rows.append((f, 0, "—", "—", "missing"))
            ok = False
            continue
        vers = sorted({r.get("runtime") or "(unstamped)" for r in recs})
        digs = sorted({r.get("model_digest") or "(unstamped)" for r in recs})
        want = expect or "(unstamped)"
        good = vers == [want] and len(recs) == 8
        ok &= good
        note = "ok" if good else ("**runtime MISMATCH**" if vers != [want]
                                  else f"**short — {len(recs)}/8 draws**")
        rows.append((f, len(recs), "; ".join(vers), "; ".join(d[:12] for d in digs), note))
    return rows, ok


def independence(files):
    """Distinct payloads per seed across replicate files -> independent observation count.

    Returns (per_seed_distinct, n_independent). `n_independent` is the number of distinct
    whole-replicate signatures: a file whose every draw duplicates another file's is not a
    second observation of anything.
    """
    per_file = {f: {r["seed"]: payload_hash(r) for r in records(f)} for f in files}
    per_file = {f: h for f, h in per_file.items() if h}
    seeds = sorted(set().union(*per_file.values())) if per_file else []
    per_seed = {s: len({h.get(s) for h in per_file.values() if s in h}) for s in seeds}
    sigs = {f: tuple(h.get(s, "") for s in seeds) for f, h in per_file.items()}
    return per_seed, len(set(sigs.values())), sigs


def summarise(label, cfg):
    print(f"\n## Ollama {label}\n")

    print("### Provenance\n")
    print("| file | draws | runtime stamp | model digest | |")
    print("|---|---|---|---|---|")
    all_ok = True
    for cond in ("control", "fenced"):
        rows, ok = provenance(cfg[cond], cfg["expect_stamp"])
        all_ok &= ok
        for f, n, v, d, st in rows:
            print(f"| `{f}` ({cond}) | {n} | {v} | {d} | {st} |")
    if not all_ok:
        print("\n⚠ **not all files are 8 draws on the expected runtime — read the rows above "
              "before reading any number below.**")

    print("\n### Independent observations (payload hashes, fifth/sixth amendments)\n")
    got_ind = {}
    print("| condition | replicate files | distinct whole-replicate payloads | per-seed distinct |")
    print("|---|---|---|---|")
    for cond in ("control", "fenced"):
        present = [f for f in cfg[cond] if records(f)]
        per_seed, n_ind, _sigs = independence(present)
        got_ind[cond] = n_ind
        spread = ", ".join(f"s{s}:{n}" for s, n in sorted(per_seed.items()))
        print(f"| {cond} | {len(present)} | **{n_ind} of {len(present)}** | {spread} |")

    print("\n### Per-replicate metrics (degenerate draws excluded from accuracy/coverage)\n")
    got = {}
    print("| condition | replicate | Event→Fact | real errors | type accuracy | coverage | "
          "ent/subj | degenerate |")
    print("|---|---|---|---|---|---|---|---|")
    for cond in ("control", "fenced"):
        reps = [r for r in (replicate(f, MODEL) for f in cfg[cond]) if r]
        got[cond] = reps
        for r in reps:
            print(f"| {cond} | `{r['file']}` | {r['ef']} | {r['errors']} | {r['acc']:.1f}% | "
                  f"{r['cov']:.1f}% | {r['eps']:.2f} | {r['degen']} |")
    if not (got["control"] and got["fenced"]):
        print("\n_(incomplete — cannot compare)_")
        return None

    print(f"\n### Control vs fenced, within {label.split()[0]}\n")
    print("| metric | control (range) | fenced (range) | ranges overlap? |")
    print("|---|---|---|---|")
    out = {}
    for lab, key in METRICS:
        c = [r[key] for r in got["control"]]
        f = [r[key] for r in got["fenced"]]
        overlap = not (max(f) < min(c) or min(f) > max(c))
        fmt = "{:.2f}" if key == "eps" else "{:.1f}"
        print(f"| {lab} | {fmt.format(mean(c))} [{fmt.format(min(c))}–{fmt.format(max(c))}] | "
              f"{fmt.format(mean(f))} [{fmt.format(min(f))}–{fmt.format(max(f))}] | "
              f"{'yes' if overlap else '**no**'} |")
        out[key] = {"c": c, "f": f, "overlap": overlap}

    ctl, fen = collections.Counter(), collections.Counter()
    for r in got["control"]:
        ctl.update(r["conf"])
    for r in got["fenced"]:
        fen.update(r["conf"])
    print(f"\n**Confusions, summed over replicates ({len(got['control'])} control, "
          f"{len(got['fenced'])} fenced — not per-draw comparable across conditions)**\n")
    print("| confusion | control | fenced |")
    print("|---|---|---|")
    for k in sorted(set(ctl) | set(fen), key=lambda k: -(ctl[k] + fen[k])):
        print(f"| {k[0]} → {k[1]} | {ctl[k]} | {fen[k]} |")
    out["_independence"] = got_ind
    return out


def main():
    print("# The fence, scored within each runtime\n")
    print("Generated by `compare_runtime.py`. Each runtime's fenced arm is compared **only "
          "to its own control**.\n")
    res = {}
    for label, cfg in RUNTIMES.items():
        res[label] = summarise(label, cfg)

    print("\n## Does the fence separate from its own control, on each runtime?\n")
    print("| runtime | Event→Fact control → fenced | non-overlapping? | accuracy control → fenced |"
          " non-overlapping? |")
    print("|---|---|---|---|---|")
    for label, r in res.items():
        if not r:
            print(f"| {label} | incomplete | — | incomplete | — |")
            continue
        ef, ac = r["ef"], r["acc"]
        print(f"| {label} | {mean(ef['c']):.1f} [{min(ef['c'])}–{max(ef['c'])}] → "
              f"{mean(ef['f']):.1f} [{min(ef['f'])}–{max(ef['f'])}] | "
              f"{'no — **overlaps**' if ef['overlap'] else '**yes**'} | "
              f"{mean(ac['c']):.1f}% → {mean(ac['f']):.1f}% | "
              f"{'no — **overlaps**' if ac['overlap'] else '**yes**'} |")


if __name__ == "__main__":
    main()
