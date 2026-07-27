#!/usr/bin/env python3
"""Re-run PRD.md section 6.4's truncation / `num_batch` ceiling probe against `bge-m3`.

Section 6.4 calls `truncate: false` "the single highest-value line in the whole
configuration". It records, on the Fedora box:

  * default `truncate` (true) silently truncates: a 135,000-character input returned a
    valid 1024-dim vector with `prompt_eval_count: 2048` — an embedding of the opening
    ~8% of the text, indistinguishable from a real one;
  * the embed window is `min(num_ctx, GGUF context_length, num_batch)` and the default
    2048 `num_batch` is what binds, so without `options.num_batch: 8192` the usable
    window is 2048, not 8192;
  * with `num_batch: 8192` the vector is *correct*, not merely accepted: a distinctive
    fact buried past the 2048 default in a 6,689-token document lifted query cosine by
    +0.0202 against a truncated control.

DESIGN RULE FOR THIS FILE
-------------------------
This is a probe for *silent* failure, so it must not be able to fail silently itself.
`call()` raises unless the caller explicitly says a failure is an expected outcome
(`expect_fail=True`), and every numeric comparison operates on a vector that was
proven present. There is no path on which a missing embedding degrades to an empty
one and yields a clean "no truncation detected".

It also carries its own POSITIVE CONTROLS: checks 4 and 6 feed inputs that are known
to exceed the window, and the run FAILS unless truncation is actually detected there.
A run that reports "clean" without tripping its own controls is a bug, not a pass.

Usage:  uv run --no-project --python 3.12 research/gate-b/truncation_probe.py
Writes: research/gate-b/truncation-<host>.json
"""
import json, math, platform, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "ladder-probe"))
from corpus import SUBJECTS  # noqa: E402

API = "http://127.0.0.1:11434/api/embed"
MODEL = "bge-m3"
DEFAULT = object()   # "omit the option entirely", distinct from an explicit value

FILLER = " ".join(s[2] for s in SUBJECTS)


class ProbeError(RuntimeError):
    """Raised whenever the probe cannot produce a trustworthy reading."""


def call(text, truncate=DEFAULT, num_batch=DEFAULT, num_ctx=DEFAULT, expect_fail=False):
    """One /api/embed call.

    Returns a dict that ALWAYS contains a usable 1024-dim `vec`, or raises. The only
    exception is `expect_fail=True`, which permits an HTTP error and returns a record
    with `ok: False` and no `vec` — callers of that form must not do vector maths.
    """
    body = {"model": MODEL, "input": text, "keep_alive": "5m"}
    if truncate is not DEFAULT:
        body["truncate"] = truncate
    opts = {}
    if num_batch is not DEFAULT:
        opts["num_batch"] = num_batch
    if num_ctx is not DEFAULT:
        opts["num_ctx"] = num_ctx
    if opts:
        body["options"] = opts
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            p = json.load(r)
    except urllib.error.HTTPError as e:
        rec = {"ok": False, "status": e.code, "error": e.read().decode()[:400],
               "wall_s": round(time.perf_counter() - t0, 3)}
        if expect_fail:
            return rec
        raise ProbeError(f"unexpected HTTP {e.code} from /api/embed: {rec['error']}") from e
    except Exception as e:                                        # noqa: BLE001
        rec = {"ok": False, "status": None, "error": f"{type(e).__name__}: {e}",
               "wall_s": round(time.perf_counter() - t0, 3)}
        if expect_fail:
            return rec
        raise ProbeError(f"transport failure calling /api/embed: {rec['error']}") from e

    embs = p.get("embeddings")
    if not isinstance(embs, list) or not embs or not isinstance(embs[0], list):
        raise ProbeError(f"no embedding in a 200 response: {str(p)[:300]}")
    vec = embs[0]
    if len(vec) != 1024 or not all(isinstance(x, (int, float)) for x in vec[:8]):
        raise ProbeError(f"malformed embedding, dim={len(vec)}")
    n = p.get("prompt_eval_count")
    if not isinstance(n, int) or n <= 0:
        raise ProbeError(f"missing/absurd prompt_eval_count: {n!r} — cannot judge truncation")
    return {"ok": True, "wall_s": round(time.perf_counter() - t0, 3),
            "dim": len(vec), "prompt_eval_count": n, "vec": vec}


def strip(r):
    return {k: v for k, v in r.items() if k != "vec"}


def cos(a, b):
    if not a or not b:
        raise ProbeError("cosine on an absent vector — the probe cannot report a result")
    n = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if n == 0:
        raise ProbeError("zero-norm embedding")
    return sum(x * y for x, y in zip(a, b)) / n


def words_for_tokens(target):
    """Deterministic filler of ~`target` bge-m3 tokens, measured against the server's own
    `prompt_eval_count` rather than estimated. Raises if it cannot land near the target."""
    pool = []
    while len(pool) < target * 3:
        pool.extend(FILLER.split())
    lo, hi, best = 1, len(pool), None
    while lo <= hi:
        mid = (lo + hi) // 2
        r = call(" ".join(pool[:mid]), truncate=False, num_batch=8192, expect_fail=True)
        if not r["ok"]:                      # over the hard ceiling; search downward
            hi = mid - 1
            continue
        n = r["prompt_eval_count"]
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (" ".join(pool[:mid]), n)
        if n == target:
            break
        lo, hi = (mid + 1, hi) if n < target else (lo, mid - 1)
    if best is None or abs(best[1] - target) > max(8, target * 0.01):
        raise ProbeError(f"could not build a ~{target}-token input (best={best[1] if best else None})")
    return best


def main():
    host = platform.node().split(".")[0]
    out = {"host": host, "model": MODEL, "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "corpus": str((HERE.parent / "ladder-probe" / "corpus.py").resolve()),
           "checks": {}, "controls": {}}
    C = out["checks"]

    # ---- 1. the section 6.4 headline: 135,000 chars ------------------------------------
    huge = (FILLER * 40)[:135_000]
    C["huge_default_truncate_default_num_batch"] = strip(call(huge, expect_fail=True))
    C["huge_default_truncate_num_batch_8192"] = strip(call(huge, num_batch=8192, expect_fail=True))
    C["huge_truncate_false_num_batch_8192"] = strip(
        call(huge, truncate=False, num_batch=8192, expect_fail=True))
    C["huge_truncate_false_num_batch_default"] = strip(
        call(huge, truncate=False, expect_fail=True))

    # ---- 2. where the window actually binds, truncate: false ---------------------------
    ladder = {}
    for target in (1839, 2048, 2100, 3000, 6689, 8192):
        text, n = words_for_tokens(target)
        ladder[f"target{target}_actual{n}"] = {
            "default_num_batch": strip(call(text, truncate=False, expect_fail=True)),
            "num_batch_8192": strip(call(text, truncate=False, num_batch=8192, expect_fail=True)),
        }
    C["ceiling_ladder_truncate_false"] = ladder

    # ---- 3. num_ctx cannot raise the ceiling ------------------------------------------
    t3000, _ = words_for_tokens(3000)
    C["num_ctx_8192_alone_truncate_false"] = strip(
        call(t3000, truncate=False, num_ctx=8192, expect_fail=True))

    # ---- 4. POSITIVE CONTROL: which end survives truncation ----------------------------
    # ~16k tokens against an 8192 window. Truncation MUST occur here; if it does not, the
    # probe is not measuring what it claims to and the run aborts.
    head = "The Ferrograve Accord was ratified in the humid Wexley annex."
    tail = "The Blindwater Ledger was sealed beneath the Kirrin obelisk."
    body, body_n = words_for_tokens(8192)
    doc = f"{head} {body} {body} {tail}"
    dt = call(doc, num_batch=8192)                     # default truncate = true
    qh = call(head, num_batch=8192)
    qt = call(tail, num_batch=8192)
    ch, ct = cos(dt["vec"], qh["vec"]), cos(dt["vec"], qt["vec"])
    C["truncation_direction"] = {
        "input_tokens_uncapped_estimate": body_n * 2 + 30,
        "doc": strip(dt),
        "cos_to_head_sentinel": round(ch, 4),
        "cos_to_tail_sentinel": round(ct, 4),
        "surviving_end": "head (tail discarded)" if ch > ct else "tail (head discarded)",
    }
    out["controls"]["over_length_input_was_truncated"] = (
        dt["prompt_eval_count"] < body_n * 2)
    out["controls"]["sentinels_are_distinguishable"] = abs(ch - ct) > 0.01

    # ---- 5. correctness at depth: the section 6.4 +0.0202 replication ------------------
    fact = ("The Ferrograve Accord fixes the retry budget at seventeen attempts "
            "before the ledger is sealed.")
    query = "how many retry attempts does the Ferrograve Accord allow"
    pre, _ = words_for_tokens(2600)      # buries the fact past the 2048 default
    post, _ = words_for_tokens(4000)
    deep_doc = f"{pre} {fact} {post}"
    full = call(deep_doc, truncate=False, num_batch=8192)
    control = call(deep_doc)                       # default truncate + default 2048 batch
    qv = call(query, num_batch=8192)
    cf, cc = cos(full["vec"], qv["vec"]), cos(control["vec"], qv["vec"])
    C["fact_at_depth"] = {
        "doc_tokens_full": full["prompt_eval_count"],
        "doc_tokens_control": control["prompt_eval_count"],
        "cos_full": round(cf, 4), "cos_truncated_control": round(cc, 4),
        "lift": round(cf - cc, 4),
    }
    out["controls"]["depth_control_was_truncated"] = (
        control["prompt_eval_count"] < full["prompt_eval_count"])

    # ---- 6. POSITIVE CONTROL: prefix identity under the default window -----------------
    # If truncation is silent and front-preserving, a 2048-token doc and a longer doc
    # sharing its first 2048 tokens must embed near-identically under the default batch.
    p2048, _ = words_for_tokens(2048)
    longer = p2048 + " " + post
    a = call(p2048)
    b = call(longer)
    C["prefix_identity_under_default"] = {
        "short": strip(a), "long": strip(b), "cos": round(cos(a["vec"], b["vec"]), 4)}
    out["controls"]["long_doc_capped_at_same_count_as_short"] = (
        a["prompt_eval_count"] == b["prompt_eval_count"])

    # ---- verdict ------------------------------------------------------------------------
    failed = [k for k, v in out["controls"].items() if not v]
    out["controls_all_passed"] = not failed
    dest = HERE / f"truncation-{host}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"\nwrote {dest}")
    if failed:
        raise SystemExit(
            "POSITIVE CONTROLS FAILED: " + ", ".join(failed) +
            "\nThe probe could not demonstrate that it detects truncation. "
            "Report section 6.4 as UNVERIFIED, not PASS.")
    print("\npositive controls: all passed — the probe demonstrably detects truncation")


if __name__ == "__main__":
    main()
