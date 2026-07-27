#!/usr/bin/env python3
"""Score the `format: "json"` hazard probe. Reads json-hazard-<host>.jsonl.

Degeneration criteria, fixed from the Fedora observation before this was run against the
Mac data (the Fedora failures were "newline streams" and "runaway to the token cap with
duplicated keys"):

  D1 runaway   done_reason == "length" — hit the 4096 num_predict cap
  D2 newline   >30% of response characters are newlines, or a whitespace run > 100 chars
  D3 dup keys  distinct natural_keys / entities < 0.7
  D4 schema    no entity list recoverable from the response
  D5 inflation entities > 2.5x the subjects actually drawn

Envelope shape is NOT a criterion: three shapes were observed from one model family on
Fedora and all carried valid content. `entities_in()` is imported from the ladder probe's
analyze.py rather than reimplemented.

Usage: uv run --no-project --python 3.12 research/gate-b/json_hazard_score.py
"""
import json, platform, re, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "ladder-probe"))
from analyze import entities_in, extract_json  # noqa: E402


def degeneration(rec):
    """Return the list of criteria this draw trips. Empty list == clean."""
    hits = []
    if rec.get("error"):
        return ["D0 transport error: " + rec["error"]]
    txt = rec.get("response")
    if txt is None:
        return ["D4 schema (no response body)"]
    if rec.get("done_reason") == "length":
        hits.append("D1 runaway")
    if txt:
        nl = txt.count("\n") / len(txt)
        longest_ws = max((len(m) for m in re.findall(r"\s+", txt)), default=0)
        if nl > 0.30 or longest_ws > 100:
            hits.append(f"D2 newline (nl={nl:.2f} run={longest_ws})")
    ents = entities_in(extract_json(txt))
    if not ents:
        hits.append("D4 schema")
    else:
        keys = [str(e.get("natural_key", "")).lower() for e in ents if isinstance(e, dict)]
        if keys and len(set(keys)) / len(keys) < 0.7:
            hits.append(f"D3 dup keys ({len(set(keys))}/{len(keys)})")
        if len(ents) > 2.5 * rec["n_subjects"]:
            hits.append(f"D5 inflation ({len(ents)} from {rec['n_subjects']})")
    return hits


def main():
    host = platform.node().split(".")[0]
    src = HERE / f"json-hazard-{host}.jsonl"
    recs = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]

    cells = {}
    for r in recs:
        hits = degeneration(r)
        cells.setdefault((r["n_subjects"], r["condition"]), []).append((r, hits))

    sizes = sorted({n for n, _ in cells})
    print(f"# format:\"json\" hazard — {recs[0]['model']} on {host}\n")
    print("| subjects | cond | draws | degenerate | in tok | out tok (mean) | "
          "max out | hit detail |")
    print("|---|---|---|---|---|---|---|---|")
    totals = {"json": [0, 0], "unconstrained": [0, 0]}
    for n in sizes:
        for cond in ("json", "unconstrained"):
            v = cells.get((n, cond), [])
            if not v:
                continue
            bad = [(r, h) for r, h in v if h]
            outs = [r.get("eval_count") or 0 for r, _ in v]
            ins = [r.get("prompt_eval_count") or 0 for r, _ in v]
            totals[cond][0] += len(v)
            totals[cond][1] += len(bad)
            detail = "; ".join(f"seed {r['seed']}: {', '.join(h)}" for r, h in bad) or "—"
            print(f"| {n} | `{cond}` | {len(v)} | **{len(bad)}** | {sum(ins)//len(ins)} | "
                  f"{sum(outs)//len(outs)} | {max(outs)} | {detail} |")
    print()
    for cond, (nn, bb) in totals.items():
        rule3 = 3.0 / nn * 100 if nn and bb == 0 else None
        extra = (f" — 0 events in {nn} draws bounds the per-draw rate at "
                 f"<{rule3:.0f}% (95%, rule of three)") if rule3 else ""
        print(f"{cond}: {bb}/{nn} degenerate{extra}")


if __name__ == "__main__":
    main()
