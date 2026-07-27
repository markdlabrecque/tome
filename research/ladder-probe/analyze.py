#!/usr/bin/env python3
"""Score the ladder probe against CRITERIA.md. Reads raw.jsonl, writes results.md.

Coverage note: the corpus `marker` is a label, not always a literal token in the subject
text (it is for Person/Project proper nouns, not for Decisions). So coverage is measured by
content-word overlap between each drawn subject and each emitted entity, greedily matched —
applied identically to every arm, which is what matters for a relative comparison.
"""
import json, random, re, sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent))
from corpus import SUBJECTS

HERE = Path(__file__).parent
CONTROL = "qwen3:14b"
STOP = set("the a an and or but of to in on at for with by from is are was were be been it "
           "its this that these those as not no than then so if into over under after "
           "before about which who whom whose has have had do does did will would can could "
           "should may might must one two three end most only still nobody everyone".split())
COVER_T = 0.25   # overlap coefficient against the subject's content words


def extract_json(text):
    """First balanced {...} in the response. Tolerates reasoning preamble and md fences.

    Unconstrained decoding is what #24 measured and what CRITERIA.md's amendment was
    reverted to; a model that wraps good JSON in prose is not a schema failure.
    """
    if not text:
        return None
    a = text.find("[")
    b = text.find("{")
    if a != -1 and (b == -1 or a < b):
        depth, instr, esc = 0, False, False
        for i in range(a, len(text)):
            ch = text[i]
            if instr:
                if esc:            esc = False
                elif ch == "\\":   esc = True
                elif ch == '"':    instr = False
                continue
            if ch == '"':   instr = True
            elif ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[a:i + 1])
                    except Exception:
                        break
    s = text.find("{")
    while s != -1:
        depth, instr, esc = 0, False, False
        for i in range(s, len(text)):
            ch = text[i]
            if instr:
                if esc:      esc = False
                elif ch == "\\": esc = True
                elif ch == '"':  instr = False
                continue
            if ch == '"':   instr = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        import json as _j
                        return _j.loads(text[s:i + 1])
                    except Exception:
                        break
        s = text.find("{", s + 1)
    return None



def entities_in(node, depth=0):
    """Find the entity list regardless of envelope shape.

    Three shapes were observed across the ladder, all carrying valid content:
      {"entities": [...]}      qwen3:14b, qwen3:4b
      [ {...}, {...} ]         qwen3:8b, 5 of 8 draws
      [ {"entities": [...]} ]  qwen3:8b, 3 of 8 draws
    Treating envelope variation as a content failure was a scoring bug, not a model result.
    """
    if depth > 4 or node is None:
        return None
    if isinstance(node, list):
        if node and all(isinstance(x, dict) and "natural_key" in x for x in node):
            return node
        for x in node:
            got = entities_in(x, depth + 1)
            if got:
                return got
        return None
    if isinstance(node, dict):
        if "natural_key" in node:
            return [node]
        for k in ("entities", "data", "result", "items"):
            if k in node:
                got = entities_in(node[k], depth + 1)
                if got:
                    return got
        for v in node.values():
            got = entities_in(v, depth + 1)
            if got:
                return got
    return None


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP and len(w) > 2}


def score_record(rec):
    """Return per-draw metrics for one (model, seed) cell."""
    out = {"schema_fail": 0, "n_entities": 0, "distinct_keys": 0, "covered": 0,
           "fabricated": 0, "decisions_emitted": 0, "decisions_drawn": 0,
           "fact_share": 0.0, "confidences": [], "n_subjects": len(rec["indices"])}
    subs = [SUBJECTS[i] for i in rec["indices"]]
    out["decisions_drawn"] = sum(1 for t, _, _ in subs if t == "Decision")

    if rec.get("error") or not rec.get("response"):
        out["schema_fail"] = 1
        return out
    d = extract_json(rec["response"])
    ents = entities_in(d)
    if not isinstance(ents, list) or not ents:
        out["schema_fail"] = 1
        return out

    clean = []
    for e in ents:
        if not isinstance(e, dict) or "natural_key" not in e or "entity_type" not in e:
            out["schema_fail"] = 1
            continue
        clean.append(e)
    if not clean:
        out["schema_fail"] = 1
        return out

    out["n_entities"] = len(clean)
    out["distinct_keys"] = len({str(e.get("natural_key", "")).lower() for e in clean})
    out["decisions_emitted"] = sum(1 for e in clean if str(e.get("entity_type")) == "Decision")
    out["fact_share"] = sum(1 for e in clean if str(e.get("entity_type")) == "Fact") / len(clean)
    for e in clean:
        c = e.get("type_confidence")
        if isinstance(c, (int, float)):
            out["confidences"].append(float(c))

    ent_toks = [toks(f"{e.get('natural_key','')} {e.get('summary','')}") for e in clean]
    sub_toks = [toks(t) for _, _, t in subs]
    matched_ents = set()
    for st in sub_toks:
        best, bi = 0.0, None
        for i, et in enumerate(ent_toks):
            if not st:
                continue
            ov = len(st & et) / len(st)
            if ov > best:
                best, bi = ov, i
        if best >= COVER_T:
            out["covered"] += 1
            matched_ents.add(bi)
    # an entity supported by no drawn subject
    for i, et in enumerate(ent_toks):
        if i in matched_ents:
            continue
        if max((len(st & et) / len(st) if st else 0) for st in sub_toks) < COVER_T:
            out["fabricated"] += 1
    return out


def boot(diffs, n=10000):
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(7)
    ms = sorted(mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return (ms[int(0.025 * n)], ms[int(0.975 * n)])


def main():
    recs = [json.loads(l) for l in (HERE / __import__("os").environ.get("RAW","raw.jsonl")).read_text().splitlines() if l.strip()]
    by = {}
    for r in recs:
        by.setdefault(r["model"], {})[r["seed"]] = (r, score_record(r))

    per = {}
    for m, cells in by.items():
        seeds = sorted(cells)
        g = lambda f: [f(cells[s][1]) for s in seeds]                       # noqa: E731
        tim = [cells[s][0] for s in seeds]
        per[m] = {
            "seeds": seeds,
            "ent_per_subj": [c["n_entities"] / c["n_subjects"] for c in (cells[s][1] for s in seeds)],
            "coverage": [c["covered"] / c["n_subjects"] for c in (cells[s][1] for s in seeds)],
            "fabrication": [c["fabricated"] / max(c["n_entities"], 1) for c in (cells[s][1] for s in seeds)],
            "dec_recall": [c["decisions_emitted"] / max(c["decisions_drawn"], 1) for c in (cells[s][1] for s in seeds)],
            "fact_share": g(lambda c: c["fact_share"]),
            "distinct": g(lambda c: c["distinct_keys"]),
            "schema_fail": sum(g(lambda c: c["schema_fail"])),
            "conf": [x for s in seeds for x in cells[s][1]["confidences"]],
            "wall": [t.get("wall_s") or 0 for t in tim],
            "in_tok": [t.get("prompt_eval_count") or 0 for t in tim],
            "out_tok": [t.get("eval_count") or 0 for t in tim],
            "pe_s": [(t.get("prompt_eval_duration") or 0) / 1e9 for t in tim],
            "ev_s": [(t.get("eval_duration") or 0) / 1e9 for t in tim],
            "trunc": sum(1 for t in tim if t.get("done_reason") == "length"),
        }

    ctl = per[CONTROL]
    lines = ["# Ladder probe results", "",
             f"Arms: {', '.join(per)} · control: `{CONTROL}` · {len(ctl['seeds'])} paired draws of 40.",
             "", "## Quality", "",
             "| model | ent/subj | coverage | fabric. | Decision recall | Fact share | distinct keys | schema fails |",
             "|---|---|---|---|---|---|---|---|"]
    for m, p in per.items():
        lines.append(f"| `{m}` | {mean(p['ent_per_subj']):.2f} | {mean(p['coverage'])*100:.1f}% | "
                     f"{mean(p['fabrication'])*100:.1f}% | {mean(p['dec_recall'])*100:.0f}% | "
                     f"{mean(p['fact_share'])*100:.1f}% | {mean(p['distinct']):.1f} | {p['schema_fail']} |")

    lines += ["", "## Paired difference from control (95% bootstrap CI, 10k resamples)", "",
              "| model | Δ ent/subj | Δ coverage (pp) | verdict inputs |", "|---|---|---|---|"]
    for m, p in per.items():
        if m == CONTROL:
            continue
        de = [a - b for a, b in zip(p["ent_per_subj"], ctl["ent_per_subj"])]
        dc = [(a - b) * 100 for a, b in zip(p["coverage"], ctl["coverage"])]
        le, he = boot(de)
        lc, hc = boot(dc)
        rel_e = mean(p["ent_per_subj"]) / mean(ctl["ent_per_subj"]) * 100
        rel_c = mean(p["coverage"]) / mean(ctl["coverage"]) * 100
        lines.append(f"| `{m}` | {mean(de):+.3f} [{le:+.3f}, {he:+.3f}] | {mean(dc):+.1f} [{lc:+.1f}, {hc:+.1f}] | "
                     f"ent/subj {rel_e:.0f}% of control · coverage {rel_c:.0f}% |")

    lines += ["", "## Cost (measured on the Fedora box, RX 6900 XT)", "",
              "| model | wall/entry | prefill s | decode s | in tok | out tok | prefill share | truncated |",
              "|---|---|---|---|---|---|---|---|"]
    for m, p in per.items():
        pe, ev = mean(p["pe_s"]), mean(p["ev_s"])
        lines.append(f"| `{m}` | {mean(p['wall']):.1f}s | {pe:.2f} | {ev:.2f} | {mean(p['in_tok']):.0f} | "
                     f"{mean(p['out_tok']):.0f} | {pe/(pe+ev)*100:.0f}% | {p['trunc']} |")

    lines += ["", "## type_confidence against §13.4's 0.7 starting value", "",
              "| model | n | mean | below 0.7 |", "|---|---|---|---|"]
    for m, p in per.items():
        c = p["conf"]
        lines.append(f"| `{m}` | {len(c)} | {mean(c):.3f} | {sum(1 for x in c if x < 0.7)/max(len(c),1)*100:.1f}% |"
                     if c else f"| `{m}` | 0 | — | — |")

    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
