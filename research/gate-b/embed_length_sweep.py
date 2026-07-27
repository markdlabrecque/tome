#!/usr/bin/env python3
"""Length sweep for `bge-m3` embedding latency: is 447 ms a platform constant or one
point on a line?

Motivation (#33 follow-up). Gate B reported a warm Mac/Fedora ratio of 2.43x at 1,839
tokens, against 1.09x cold and 1.14x on a 15-token query. If latency is
`overhead + slope * n`, a single ratio is not a platform property at all -- it is the
blend at one chosen input length. This sweeps n and fits the line.

Reuses `embed_latency.py`'s call path verbatim (same PRD section 6.4 obligations:
`truncate: false`, `options.num_batch: 8192`, no prefix) and the same committed corpus.

Rounds are interleaved -- every size is measured once per round, in shuffled order --
so thermal drift spreads across sizes instead of confounding the largest one. The
round index is recorded with every observation so drift can be tested for rather than
averaged away.

Usage:  uv run --python 3.12 research/gate-b/embed_length_sweep.py [--reps N]
Writes: research/gate-b/embed-length-sweep-<host>.json
"""
import argparse, json, platform, random, statistics, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from embed_latency import embed, server_env, MODEL  # noqa: E402
sys.path.insert(0, str(HERE.parent / "ladder-probe"))
from corpus import SUBJECTS  # noqa: E402

TARGETS = [16, 32, 64, 128, 256, 384, 512, 768, 1024, 1536, 1839, 2048]


def build_pool():
    pool = []
    while len(pool) < 20000:
        pool.extend(" ".join(s[2] for s in SUBJECTS).split())
    return pool


def build_at(pool, target):
    """Binary-search word count until the server's own prompt_eval_count hits target."""
    lo, hi, best = 1, min(len(pool), target * 4), None
    while lo <= hi:
        mid = (lo + hi) // 2
        text = " ".join(pool[:mid])
        _, p = embed(text)
        n = p["prompt_eval_count"]
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (text, n)
        if n == target:
            break
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def ols(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    icpt = my - slope * mx
    ss_res = sum((y - (icpt + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    # standard errors
    dof = n - 2
    s2 = ss_res / dof if dof > 0 else float("nan")
    return {
        "intercept_ms": icpt, "slope_ms_per_token": slope,
        "r_squared": 1 - ss_res / ss_tot if ss_tot else float("nan"),
        "slope_stderr": (s2 / sxx) ** 0.5 if sxx else float("nan"),
        "intercept_stderr": (s2 * (1 / n + mx ** 2 / sxx)) ** 0.5 if sxx else float("nan"),
        "n_points": n,
    }


def processor_during_embed(text):
    """`ollama ps` reports a PROCESSOR column. Sample it *during* a real embed, not idle."""
    seen = []
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            r = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
            for line in r.splitlines()[1:]:
                if line.strip():
                    seen.append(line.rstrip())
            time.sleep(0.05)

    t = threading.Thread(target=poll, daemon=True)
    t.start()
    for _ in range(12):          # keep the GPU busy long enough to sample
        embed(text)
    stop.set()
    t.join(timeout=2)
    return sorted(set(seen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=15)
    a = ap.parse_args()

    host = platform.node().split(".")[0]
    out = {
        "host": host, "platform": platform.platform(), "model": MODEL,
        "ollama_version": subprocess.run(["ollama", "--version"], capture_output=True,
                                         text=True).stdout.strip(),
        "server_env": server_env(),
        "power": subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                                text=True).stdout.strip(),
        "gpu_cores": subprocess.run(
            ["bash", "-c", "system_profiler SPDisplaysDataType | grep -m1 'Total Number of Cores'"],
            capture_output=True, text=True).stdout.strip(),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "targets": TARGETS, "reps": a.reps,
    }

    pool = build_pool()
    texts = {}
    print("building inputs ...", flush=True)
    for t in TARGETS:
        text, n = build_at(pool, t)
        texts[n] = text
        print(f"  target {t:5d} -> {n:5d} tokens, {len(text)} chars", flush=True)
    sizes = sorted(texts)
    out["actual_tokens"] = sizes

    # backend / processor check, during real work
    out["processor_during_embed"] = processor_during_embed(texts[sizes[-1]])
    print(f"  ollama ps during embed: {out['processor_during_embed']}", flush=True)

    for n in sizes:                                   # warm every size before timing
        for _ in range(3):
            embed(texts[n])

    obs = []                                          # (round, tokens, ms)
    rng = random.Random(20260727)
    for r in range(a.reps):
        order = sizes[:]
        rng.shuffle(order)
        for n in order:
            w, p = embed(texts[n])
            assert p["prompt_eval_count"] == n, (n, p["prompt_eval_count"])
            assert len(p["embeddings"][0]) == 1024
            obs.append({"round": r, "tokens": n, "ms": w * 1000})
        print(f"  round {r+1}/{a.reps} done", flush=True)
    out["observations"] = obs

    by = {n: sorted(o["ms"] for o in obs if o["tokens"] == n) for n in sizes}
    out["by_size"] = {
        str(n): {
            "n": len(v), "median_ms": statistics.median(v), "min_ms": v[0], "max_ms": v[-1],
            "mean_ms": statistics.mean(v), "stdev_ms": statistics.stdev(v) if len(v) > 1 else 0.0,
        } for n, v in by.items()
    }

    out["fit_on_medians"] = ols(sizes, [statistics.median(by[n]) for n in sizes])
    out["fit_on_all"] = ols([o["tokens"] for o in obs], [o["ms"] for o in obs])
    # drift: median of every size, first third of rounds vs last third
    third = max(1, a.reps // 3)
    early = [o["ms"] for o in obs if o["round"] < third]
    late = [o["ms"] for o in obs if o["round"] >= a.reps - third]
    out["drift"] = {
        "rounds_per_window": third,
        "early_median_ms": statistics.median(early), "late_median_ms": statistics.median(late),
        "per_size": {str(n): {
            "early": statistics.median([o["ms"] for o in obs if o["tokens"] == n and o["round"] < third]),
            "late": statistics.median([o["ms"] for o in obs if o["tokens"] == n and o["round"] >= a.reps - third]),
        } for n in sizes},
    }

    dest = HERE / f"embed-length-sweep-{host}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {dest}\n")
    print(f"{'tokens':>7} {'n':>3} {'median':>9} {'min':>8} {'max':>8} {'sd':>7}")
    for n in sizes:
        s = out["by_size"][str(n)]
        print(f"{n:7d} {s['n']:3d} {s['median_ms']:8.1f}  {s['min_ms']:7.1f} "
              f"{s['max_ms']:7.1f} {s['stdev_ms']:6.2f}")
    f = out["fit_on_medians"]
    print(f"\nfit(medians): {f['intercept_ms']:.1f} ms + {f['slope_ms_per_token']:.4f} ms/tok  "
          f"R2={f['r_squared']:.5f}")
    f = out["fit_on_all"]
    print(f"fit(all obs): {f['intercept_ms']:.1f} ms + {f['slope_ms_per_token']:.4f} ms/tok  "
          f"R2={f['r_squared']:.5f}")


if __name__ == "__main__":
    main()
