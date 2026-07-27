#!/usr/bin/env python3
"""Run the enrichment model-ladder probe. Writes raw JSONL; analysis is separate.

Criteria are fixed in CRITERIA.md, committed before this ran. This script counts nothing
and judges nothing — it only calls models and records what came back.
"""
import importlib, json, os, random, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# CORPUS=corpus_ambiguous switches to #35's stratified corpus. Default is unchanged.
SUBJECTS = importlib.import_module(os.environ.get("CORPUS", "corpus")).SUBJECTS

HERE = Path(__file__).parent
# Parameterised for the #36 A/B (third amendment). Defaults reproduce the original run
# exactly: same prompt, same arms, same output file, unconstrained decoding.
PROMPT = (HERE / os.environ.get("PROMPT", "prompt.txt")).read_text()
OUT = HERE / os.environ.get("OUT", "raw-unconstrained.jsonl")
ARMS = os.environ.get("ARMS", "qwen3:14b,qwen3:8b,qwen3:4b").split(",")
FORMAT = os.environ.get("FORMAT") or None   # "json" for grammar-constrained decoding
SEEDS = list(range(8))
DRAW_N = 40
API = "http://127.0.0.1:11434/api/generate"


def draw(seed):
    """Identical across arms: same seed -> same 40 subject indices, same order."""
    return random.Random(seed).sample(range(len(SUBJECTS)), DRAW_N)


def note_from(indices):
    return "\n".join(SUBJECTS[i][2] for i in indices)


def call(model, note):
    payload_in = {
        "model": model,
        "prompt": f"{PROMPT}\n\nNOTE:\n{note}\n",
        "stream": False,
        "think": False,
        "keep_alive": 0,   # one model resident at a time: 14b+8b overflows 16GB VRAM
        "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096, "seed": 42},
    }
    if FORMAT:
        payload_in["format"] = FORMAT
    body = json.dumps(payload_in).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        payload = json.load(r)
    payload["_wall_s"] = time.time() - t0
    return payload


def main():
    out = OUT
    done = set()
    if out.exists():  # resumable — a long run should not restart from zero
        for line in out.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                done.add((rec["model"], rec["seed"]))

    with out.open("a") as fh:
        for model in ARMS:
            for seed in SEEDS:
                if (model, seed) in done:
                    print(f"skip {model} seed={seed}", flush=True)
                    continue
                idx = draw(seed)
                note = note_from(idx)
                try:
                    p = call(model, note)
                    err = None
                except Exception as e:                      # noqa: BLE001
                    p, err = {}, f"{type(e).__name__}: {e}"
                rec = {
                    "model": model,
                    "seed": seed,
                    "indices": idx,
                    "error": err,
                    "response": p.get("response"),
                    "wall_s": p.get("_wall_s"),
                    "prompt_eval_count": p.get("prompt_eval_count"),
                    "prompt_eval_duration": p.get("prompt_eval_duration"),
                    "eval_count": p.get("eval_count"),
                    "eval_duration": p.get("eval_duration"),
                    "done_reason": p.get("done_reason"),
                }
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                print(f"{model} seed={seed} wall={rec['wall_s']:.1f}s "
                      f"in={rec['prompt_eval_count']} out={rec['eval_count']} "
                      f"reason={rec['done_reason']} err={err}", flush=True)


if __name__ == "__main__":
    main()
