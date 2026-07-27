#!/usr/bin/env python3
"""Re-check the `format: "json"` degeneration hazard against `qwen3:14b` on the Mac (#33).

On the Fedora box, `format: "json"` induced degeneration in `qwen3:8b` on 3 of 8 draws
(newline streams; runaway to the token cap with duplicated keys) while `14b` and `4b`
were unaffected. Two things make that insufficient for the on-device deployment:

  * the Mac runtime differs (Ollama on Apple silicon has been MLX-backed since
    2026-03-30), and
  * every Fedora draw was 40 subjects. Entry size is the untested axis, and nothing
    shows the 14b is immune at other sizes.

So this varies ENTRY SIZE at fixed model, and runs a paired unconstrained control at
every cell with the same seed, so a difference is attributable to the flag alone.

Reuses the committed corpus and prompt from research/ladder-probe/, and that package's
`entities_in()` — three JSON envelope shapes were observed from one model family and a
fragile parser would score envelope variation as degeneration.

Usage:  uv run --no-project --python 3.12 research/gate-b/json_hazard.py [--seeds N]
Writes: research/gate-b/json-hazard-<host>.jsonl   (resumable; append-only)

This script records. Scoring lives in `json_hazard_score.py`.
"""
import argparse, json, platform, random, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
LADDER = HERE.parent / "ladder-probe"
sys.path.insert(0, str(LADDER))
from corpus import SUBJECTS  # noqa: E402

PROMPT = (LADDER / "prompt.txt").read_text()
API = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:14b"
SIZES = [5, 10, 20, 40, 60, 80]        # subjects per entry; 40 is the Fedora comparator
CONDITIONS = ["json", "unconstrained"]


def draw(seed, n):
    """Same seed + size -> same subjects in the same order, identically in both arms."""
    return random.Random(seed * 1000 + n).sample(range(len(SUBJECTS)), n)


def call(note, use_format):
    body = {
        "model": MODEL,
        "prompt": f"{PROMPT}\n\nNOTE:\n{note}\n",
        "stream": False,
        "think": False,
        "keep_alive": "10m",     # explicit: OLLAMA_KEEP_ALIVE may be set, and only one
                                 # model is in play here, so warm is the honest condition
        "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096, "seed": 42},
    }
    if use_format:
        body["format"] = "json"
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3600) as r:
        p = json.load(r)
    p["_wall_s"] = time.perf_counter() - t0
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    a = ap.parse_args()
    host = platform.node().split(".")[0]
    out = HERE / f"json-hazard-{host}.jsonl"

    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["condition"], r["n_subjects"], r["seed"]))

    total = len(SIZES) * a.seeds * len(CONDITIONS)
    i = 0
    with out.open("a") as fh:
        for n in SIZES:
            for seed in range(a.seeds):
                for cond in CONDITIONS:
                    i += 1
                    if (cond, n, seed) in done:
                        print(f"[{i}/{total}] skip {cond} n={n} seed={seed}", flush=True)
                        continue
                    idx = draw(seed, n)
                    note = "\n".join(SUBJECTS[j][2] for j in idx)
                    try:
                        p, err = call(note, cond == "json"), None
                    except Exception as e:                          # noqa: BLE001
                        p, err = {}, f"{type(e).__name__}: {e}"
                    rec = {
                        "model": MODEL, "condition": cond, "n_subjects": n, "seed": seed,
                        "indices": idx, "error": err,
                        "response": p.get("response"),
                        "wall_s": p.get("_wall_s"),
                        "prompt_eval_count": p.get("prompt_eval_count"),
                        "eval_count": p.get("eval_count"),
                        "eval_duration": p.get("eval_duration"),
                        "done_reason": p.get("done_reason"),
                    }
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"[{i}/{total}] {cond} n={n} seed={seed} "
                          f"wall={(rec['wall_s'] or 0):.1f}s in={rec['prompt_eval_count']} "
                          f"out={rec['eval_count']} reason={rec['done_reason']} err={err}",
                          flush=True)


if __name__ == "__main__":
    main()
