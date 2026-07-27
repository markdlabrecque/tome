#!/usr/bin/env python3
"""Gate B (#33): capture-path embedding latency for `bge-m3` with `num_batch: 8192`.

Reproduces the three numbers measured on the Fedora box (RX 6900 XT, 2026-07-26):
  ceiling-size entry (1,839 bge-m3 tokens), warm ......  184 ms
  same, cold including model load ....................  1,261 ms
  query embed, warm, median of 5 .....................     87 ms

against PRD.md section 4.5's 5,000 ms inline capture budget.

Every call carries section 6.4's three obligations: `truncate: false`,
`options.num_batch: 8192`, and no prefix on either side.

This script measures and records. It renders no verdict.

Usage:  uv run --python 3.12 research/gate-b/embed_latency.py [--warm N] [--cold N] [--query N]
Writes: research/gate-b/embed-latency-<host>.json
"""
import argparse, json, os, platform, statistics, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "ladder-probe"))
from corpus import SUBJECTS  # noqa: E402

API = "http://127.0.0.1:11434/api/embed"
MODEL = "bge-m3"
TARGET_TOKENS = 1839          # the Fedora comparator's ceiling-size entry
QUERY = "what did we decide about the ingest pipeline retry budget"


def embed(text, keep_alive="5m", timeout=600):
    """One /api/embed call under section 6.4's configuration. Returns (wall_s, payload)."""
    body = json.dumps({
        "model": MODEL,
        "input": text,
        "truncate": False,                      # section 6.4, obligation 1
        "options": {"num_batch": 8192},         # section 6.4, obligation 2
        "keep_alive": keep_alive,
    }).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.load(r)
    return time.perf_counter() - t0, payload


def unload():
    """Evict the model and confirm eviction. OLLAMA_KEEP_ALIVE may be set, so this is
    explicit rather than trusting a timeout."""
    body = json.dumps({"model": MODEL, "input": "", "keep_alive": 0}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception:                                           # noqa: BLE001
        pass
    for _ in range(60):
        ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
        if MODEL.split(":")[0] not in ps:
            return True
        time.sleep(0.5)
    return False


def build_ceiling_text(target=TARGET_TOKENS):
    """A genuinely `target`-token input, built deterministically from the committed corpus.

    Binary-searches on word count against the server's own `prompt_eval_count`, so the
    size is measured in bge-m3 tokens rather than estimated from characters.
    """
    pool = []
    while len(" ".join(pool).split()) < target * 3:
        pool.extend(" ".join(s[2] for s in SUBJECTS).split())
    lo, hi, best = 1, len(pool), None
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
    if best is None:
        raise SystemExit("could not build a ceiling-size input — refusing to measure")
    return best


def server_env():
    """Ollama's own environment, as the LaunchAgent (macOS) or drop-in (Linux) sets it.

    The Linux branch was missing: this returned `{"vars": {}}` on Fedora, which reads as
    "no variables set" and is indistinguishable from "not checked". That silence is what
    made `OLLAMA_FLASH_ATTENTION`/`OLLAMA_KV_CACHE_TYPE` look Mac-only when Fedora has had
    both since 2026-07-22, and the Gate B doc cites this field as its evidence. Absence is
    now reported as `"unavailable"` rather than as an empty result.
    """
    import glob, plistlib
    for p in glob.glob(str(Path.home() / "Library/LaunchAgents/*ollama*.plist")):
        with open(p, "rb") as fh:
            return {"source": p, "vars": plistlib.load(fh).get("EnvironmentVariables", {})}
    if platform.system() == "Linux":
        r = subprocess.run(["systemctl", "show", "ollama", "-p", "Environment"],
                           capture_output=True, text=True)
        if r.returncode == 0 and "=" in r.stdout:
            body = r.stdout.strip().split("=", 1)[1]
            got = dict(kv.split("=", 1) for kv in body.split() if "=" in kv)
            return {"source": "systemctl show ollama -p Environment", "vars": got}
        return {"source": "systemctl unavailable", "vars": "unavailable"}
    return {"source": "unavailable on this platform", "vars": "unavailable"}


def spread(xs):
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4) if len(xs) >= 4 else [xs[0], statistics.median(xs), xs[-1]]
    return {
        "n": len(xs), "min_ms": xs[0] * 1000, "p25_ms": q[0] * 1000,
        "median_ms": statistics.median(xs) * 1000, "p75_ms": q[2] * 1000,
        "max_ms": xs[-1] * 1000,
        "mean_ms": statistics.mean(xs) * 1000,
        "stdev_ms": (statistics.stdev(xs) * 1000) if len(xs) > 1 else 0.0,
        "all_ms": [round(x * 1000, 1) for x in xs],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warm", type=int, default=25)
    ap.add_argument("--cold", type=int, default=7)
    ap.add_argument("--query", type=int, default=25)
    a = ap.parse_args()

    host = platform.node().split(".")[0]
    out = {
        "host": host, "platform": platform.platform(), "model": MODEL,
        "ollama_version": subprocess.run(["ollama", "--version"], capture_output=True,
                                         text=True).stdout.strip(),
        "env_keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE"),
        # The *server's* environment is what matters, and on macOS it comes from the
        # Homebrew LaunchAgent plist, not from this process. Recorded because Homebrew
        # sets OLLAMA_FLASH_ATTENTION=1 / OLLAMA_KV_CACHE_TYPE=q8_0 and the Fedora
        # comparator did not — a reader must not attribute the ratio to hardware alone.
        "server_env": server_env(),
        "corpus": str((HERE.parent / "ladder-probe" / "corpus.py").resolve()),
        "corpus_subjects": len(SUBJECTS),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    print("building ceiling-size input ...", flush=True)
    text, n_tok = build_ceiling_text()
    out["ceiling_tokens"] = n_tok
    out["ceiling_chars"] = len(text)
    print(f"  {n_tok} bge-m3 tokens, {len(text)} chars", flush=True)

    # --- warm, ceiling-size -------------------------------------------------
    for _ in range(3):                                   # warm-up, not recorded
        embed(text)
    warm = []
    for i in range(a.warm):
        w, p = embed(text)
        assert p["prompt_eval_count"] == n_tok, p["prompt_eval_count"]
        warm.append(w)
        print(f"  warm {i+1}/{a.warm}: {w*1000:.0f} ms", flush=True)
    out["warm_ceiling"] = spread(warm)

    # --- cold, ceiling-size, including model load ---------------------------
    cold, loads = [], []
    for i in range(a.cold):
        if not unload():
            raise SystemExit("model would not unload; refusing to report a warm number as cold")
        w, p = embed(text)
        if p.get("prompt_eval_count") != n_tok:
            raise SystemExit(f"cold run embedded {p.get('prompt_eval_count')} tokens, not {n_tok}")
        cold.append(w)
        loads.append(p.get("load_duration", 0) / 1e9)
        print(f"  cold {i+1}/{a.cold}: {w*1000:.0f} ms "
              f"(load {loads[-1]*1000:.0f} ms)", flush=True)
    out["cold_ceiling"] = spread(cold)
    out["cold_load_duration"] = spread(loads)

    # --- query embed, warm --------------------------------------------------
    for _ in range(3):
        embed(QUERY)
    if a.query < 1:
        raise SystemExit("--query must be >= 1")
    q, qp = [], None
    for i in range(a.query):
        w, qp = embed(QUERY)
        if qp.get("prompt_eval_count") is None or len(qp["embeddings"][0]) != 1024:
            raise SystemExit(f"bad query embed response: {qp}")
        q.append(w)
    assert qp is not None
    out["query_tokens"] = qp["prompt_eval_count"]
    out["query_warm"] = spread(q)
    print(f"  query embed ({out['query_tokens']} tok) median "
          f"{out['query_warm']['median_ms']:.0f} ms", flush=True)

    dest = HERE / f"embed-latency-{host}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {dest}")
    for k in ("warm_ceiling", "cold_ceiling", "query_warm"):
        s = out[k]
        print(f"{k:15s} n={s['n']:3d} median={s['median_ms']:8.1f} ms  "
              f"[{s['min_ms']:.0f}–{s['max_ms']:.0f}]  IQR {s['p25_ms']:.0f}–{s['p75_ms']:.0f}")


if __name__ == "__main__":
    main()
