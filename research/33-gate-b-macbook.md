# #33 Gate B and the two carried hazards — measured on the MacBook

> **CORRECTION, 2026-07-27 — read before §0.** Two claims in this document are withdrawn,
> and the Fedora comparator has been re-measured.
>
> 1. **The env-var caveat below is false.** This document states the Fedora box did not set
>    `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` (§0 and *Carried forward* item 1).
>    **Fedora has had both since 2026-07-22**, in
>    `/etc/systemd/system/ollama.service.d/90-pi-local-rocm.conf`, predating all benchmarking
>    on either machine. The configurations match on this axis and **the cross-machine ratios
>    need no such qualification.** Withdrawn on the ticket too (#33, 2026-07-27).
> 2. **`server_env` could not have shown this, which is how the error survived.** This
>    document cites `server_env` as the record — but `embed_latency.py:server_env()` had no
>    Linux branch. It returned `{"vars": {}}` on Fedora, which reads as *"nothing set"* and is
>    indistinguishable from *"not checked"*. Fixed in `b869633`; absence now reports
>    `"unavailable"`, and both machines' artifacts carry the two flags.
> 3. **The Fedora comparator is now measured with this document's own instrument.** It
>    previously existed only as prose in `NEXT-STEPS.md` — no n, no protocol, no raw data.
>    `research/gate-b/embed-latency-odin.json`, n=25: **warm ceiling median 189.9 ms**
>    (IQR 189–191), **cold 1,281 ms**, **query 87.5 ms**. The original 184 ms holds up.
>
> **Net effect on the numbers: none of the Mac measurements change.** The ratios become
> **2.36× warm / 1.07× cold / 1.13× query**, like-for-like on one instrument. Gate B still
> passes with 11.2× headroom.
>
> **What this makes worse, not better:** the env-var difference was the candidate explanation
> for the warm ratio overshooting #32's projected 1.83–2.22× band. It does not exist, and the
> overshoot survives re-measurement, so **it is an open question.** Two residual differences
> are recorded but not tested as causes: Ollama **0.32.4** (Mac) vs **0.32.1** (Fedora), and
> Metal-vs-ROCm backends, which this project has never separated from hardware.
> `OLLAMA_KEEP_ALIVE` also differs (unset on the Mac, `24h` on Fedora) but every measurement
> passes `keep_alive` explicitly.

**Machine:** MacBook Pro, Apple M4 Pro, **16 GPU cores** (confirmed via `system_profiler SPDisplaysDataType`), 48 GB unified memory, macOS 27.0 (`macOS-27.0-arm64-arm-64bit`).
**Runtime:** Ollama **0.32.4**, Homebrew CLI formula, running as the LaunchAgent `homebrew.mxcl.ollama` on `127.0.0.1:11434`.
**Models:** `bge-m3:latest` (1.2 GB), `qwen3:14b` (9.3 GB).
**Date:** 2026-07-26.
**Comparator:** the Fedora box (RX 6900 XT), measured 2026-07-26, as recorded in issue #33 and `NEXT-STEPS.md`.

## Instruments

All three are committed under `research/gate-b/` and are re-runnable:

| File | What it does |
|---|---|
| `embed_latency.py` | Gate B proper. Builds a genuinely 1,839-bge-m3-token input from the committed corpus and times warm / cold / query embeds. |
| `truncation_probe.py` | Re-runs PRD §6.4's truncation and `num_batch` ceiling probe, with its own positive controls. |
| `json_hazard.py` + `json_hazard_score.py` | Re-checks the `format: "json"` hazard against `qwen3:14b`, varying entry size, with a paired unconstrained control at every cell. |

Raw output is written beside them as `embed-latency-<host>.json`, `truncation-<host>.json`, `json-hazard-<host>.jsonl`.

All three import `research/ladder-probe/corpus.py` (80 committed synthetic subjects) and, where relevant, `prompt.txt` and `analyze.py`'s `entities_in()`. There is no inline fallback corpus in any of them — a failed import is a hard error, and the loaded path is recorded in each JSON artefact.

### A configuration difference that is not hardware

**⚠ WITHDRAWN — see the correction block at the top of this file. Fedora has both, set 2026-07-22.** The original claim read: *"Homebrew's Ollama LaunchAgent sets `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`; the Fedora box did not."* This is recorded in every artefact (`server_env`). Both options act on the attention/KV-cache path of a *causal decoder*; `bge-m3` is a non-causal encoder invoked through `/api/embed`, which allocates no KV cache, so they should not touch the Gate B numbers — but that is an inference from what the options do, **not** something measured here. Do not read the Mac÷Fedora ratios below as pure hardware difference without noting this. `OLLAMA_KEEP_ALIVE` is **not** set on this machine (Ollama's 5-minute default applies); every measurement nevertheless passes `keep_alive` explicitly.

---

# 1. Gate B proper — capture-path embedding latency

**Method.** `bge-m3`, every call carrying §6.4's three obligations: `truncate: false`, `options.num_batch: 8192`, and no prefix on either side. The ceiling-size input was built by binary-searching word count against the server's own `prompt_eval_count` until it read **exactly 1,839 bge-m3 tokens** (8,185 characters) — measured, not estimated from a character ratio. Warm runs are preceded by three unrecorded warm-ups. Cold runs evict the model via `keep_alive: 0` and **poll `ollama ps` until it is gone** before the timed call, so the load cost is genuinely inside the measurement; the run aborts rather than reporting a warm number as cold. Every timed call asserts that the response carried a 1024-dim vector and the expected token count, so a failed or short-read request cannot be silently counted as a fast one.

## Measured

| Measurement | n | median | min–max | IQR | mean ± sd |
|---|---|---|---|---|---|
| **Ceiling-size entry (1,839 tok), warm** | 25 | **447.3 ms** | 432.6 – 456.6 | 443.3 – 450.2 | 446.3 ± 5.7 |
| **Same, cold incl. model load** | 7 | **1,376.2 ms** | 1,357.9 – 1,587.2 | 1,373.2 – 1,458.1 | 1,416.0 ± 82.3 |
| *of which model load* | 7 | 870.9 ms | 858.9 – 1,111.8 | 868.3 – 883.9 | 905.2 ± 91.4 |
| **Query embed (15 tok), warm** | 25 | **99.2 ms** | 90.6 – 105.1 | 96.5 – 102.5 | 99.3 ± 4.0 |

The warm distribution is extraordinarily tight — a 24 ms total range across 25 runs, 1.3% relative standard deviation. The cold distribution has one outlier (1,587 ms, carrying a 1,112 ms load against a ~870 ms median); the other six sit inside a 28 ms band.

## Mac vs Fedora

| | Fedora (RX 6900 XT) | Mac (M4 Pro, 16 GPU cores) | Mac ÷ Fedora |
|---|---|---|---|
| Ceiling-size entry (1,839 tok), warm | 184 ms | **447 ms** | **2.43×** |
| Same, cold incl. model load | 1,261 ms | **1,376 ms** | **1.09×** |
| Query embed, warm | 87 ms | **99 ms** | **1.14×** |

The warm ratio (2.43×) sits just above the 1.83–2.22× platform penalty band #32 measured on the enrichment path. The cold and query ratios are far *below* it, because both are dominated by costs that are not compute: model load off an NVMe SSD (~870 ms of the 1,376 ms cold figure) and per-request overhead (a 15-token query cannot express a GPU throughput difference).

## Verdict

**GATE B: PASS.**

- Warm ceiling-size embed is **447 ms**, against the pass condition "comfortably under 1 s" — it is under half of it, and the *slowest of 25 runs* (457 ms) is still under half.
- Against §4.5's **5,000 ms** inline capture budget that is **11.2× headroom warm**, and **3.6× headroom even on a cold first capture that pays the full model load**.
- Nothing is remotely near the abort-and-rethink threshold. The worst single observation across all 32 ceiling-size runs, cold or warm, was 1,587 ms — 3.2× inside the budget.

The reliability premise in #33 survives the move. The ~27× Fedora headroom becomes ~11× here, which is a real reduction and worth recording, but §4.5's deferred-embedding fallback exists precisely for the tail, and the measured tail is 457 ms.

**One thing this does not measure:** every run here was on an idle, mains-powered machine. Capture on a thermally-derated or battery-saver laptop, or with the enrichment model mid-generation on the same GPU, will be slower. §4.5's `NUM_PARALLEL=1` contention case is called out in the PRD itself and is not covered by these numbers. Even a 5× degradation on top of the warm figure still lands inside the budget, so this does not change the verdict — but it is inference, not measurement.

---

# 2. PRD §6.4's truncation probe, re-run

**What §6.4 records** (Fedora): default `truncate` silently truncates — a 135,000-character input returned a valid 1024-dim vector with `prompt_eval_count: 2048`, "an embedding of the opening ~8% of the text, indistinguishable from a real one"; the embed window is `min(num_ctx, GGUF context_length, num_batch)` and the **default 2048 `num_batch` is what binds**; and with `num_batch: 8192` the vector is *correct*, not merely accepted — a fact buried past 2048 in a 6,689-token document lifted query cosine by **+0.0202** against a truncated control.

**Probe integrity.** This is a probe for *silent* failure, so it was written not to be able to fail silently itself: `call()` raises unless the caller has declared a failure an expected outcome, every cosine operates on a vector proven present and 1024-dim, and a missing `prompt_eval_count` is a hard error rather than a `None` that scores as clean. The script additionally carries **four positive controls** and exits non-zero unless all four trip. **All four tripped on this run** (`controls_all_passed: true`) — the probe demonstrably detects truncation on this machine, so the results below are a PASS and not an untested silence.

## Check 1 — the §6.4 headline, reproduced exactly

135,000 characters of corpus text:

| Call | Result |
|---|---|
| default `truncate`, default `num_batch` | **200 OK, 1024-dim vector, `prompt_eval_count: 2048`** |
| default `truncate`, `num_batch: 8192` | 200 OK, 1024-dim vector, `prompt_eval_count: 8192` |
| `truncate: false`, `num_batch: 8192` | **400** `the input length exceeds the context length` |
| `truncate: false`, default `num_batch` | **400** `the input length exceeds the context length` |

The first row is §6.4's exact finding, digit for digit: a valid-looking embedding of the opening ~1.5% of the input, with no error and nothing in the response distinguishing it from a real one.

## Check 2 — where the window binds, with `truncate: false`

| Input (bge-m3 tokens) | default `num_batch` | `num_batch: 8192` |
|---|---|---|
| 1,839 | 200, 1,839 | 200, 1,839 |
| 2,048 | 200, 2,048 | 200, 2,048 |
| 2,100 | **400** exceeds context | 200, 2,100 |
| 3,000 | **400** | 200, 3,000 |
| 6,689 | **400** | 200, 6,689 |
| 8,192 | **400** | 200, 8,192 |

The cliff is at exactly 2,048 without `num_batch`, and the full 8,192 is reachable with it. Unchanged from §6.4.

## Check 3 — `num_ctx` cannot raise the ceiling

A 3,000-token input with `truncate: false` and `options.num_ctx: 8192` but **no** `num_batch`: **400, exceeds context length.** `num_ctx` can only lower the window, never raise it — so the global `OLLAMA_CONTEXT_LENGTH` remains inert here, exactly as §6.4 states. This also confirms that no Ollama-0.32.4-era change has made `num_ctx` sufficient on its own.

## Check 4 — which end survives (new; §6.4 did not measure this directly)

A ~16,400-token document with a distinctive sentinel sentence at the very start and a different one at the very end, embedded with default `truncate` and `num_batch: 8192`:

| | |
|---|---|
| `prompt_eval_count` | 8,192 (positive control: input was truncated) |
| cosine to the **head** sentinel | **0.4443** |
| cosine to the **tail** sentinel | 0.3881 |

**The head survives; the tail is discarded.** Truncation keeps the opening of the input, which is consistent with §6.4's "an embedding of the opening ~8% of the text". Naming note: the hazard is often written as "front-truncation", meaning *truncation down to the front portion* — the text that is silently thrown away is the **end**, not the beginning.

## Check 5 — the vector is correct at depth, not merely accepted

A fact planted at ~2,600 tokens (past the 2,048 default) inside a 6,624-token document, against a query naming it:

| | Fedora (§6.4) | Mac |
|---|---|---|
| doc tokens, full (`num_batch: 8192`) | 6,689 | 6,624 |
| doc tokens, truncated control | — | 2,048 |
| cosine, full | — | **0.4024** |
| cosine, truncated control | — | 0.3544 |
| **lift** | **+0.0202** | **+0.0481** |

Same sign, and larger here. The corpus and query text are not identical to §6.4's, so the magnitudes are not directly comparable — what replicates is the direction and the fact that content past 2,048 measurably reaches the vector when `num_batch: 8192` is set and measurably does not when it is not.

## Check 6 — the smoking gun for silence

A 2,048-token document, and a much longer document whose first 2,048 tokens are byte-identical to it, both embedded under the **default** configuration:

| | `prompt_eval_count` | |
|---|---|---|
| short (2,048 tok) | 2,048 | |
| long (2,048 tok prefix + ~4,000 more) | **2,048** | |
| **cosine between the two vectors** | **1.0000** | |

The two embeddings are *identical to four decimal places*. Everything after the 2,048th token contributed nothing, and the response carried no indication of it — no error, no flag, no differing token count to notice.

## Verdict

**§6.4's truncation behaviour is UNCHANGED on this machine.** It does not differ from what §6.4 records: default `truncate` silently front-preserving-truncates at the binding window, the default `num_batch: 2048` is what binds, `num_ctx` cannot raise it, `truncate: false` converts the silent corruption into a loud 400, and `num_batch: 8192` produces vectors that demonstrably carry content from past 2,048 tokens.

**Consequence for the deployment:** §6.4's three obligations port to the Mac *verbatim* and must be carried on every `/api/embed` call. #33's abort condition ("§6.4's truncation behaviour differs on the MLX-backed runtime → stop and re-measure the ceiling") **does not fire**. The standing PRD instruction to re-run this probe after any Ollama upgrade remains correct and now has a committed instrument: `research/gate-b/truncation_probe.py`.

**Caveat on the "MLX-backed" premise.** These readings are behaviourally identical to the Fedora GGUF/ROCm ones at every check, including the exact 2,048 cliff and the exact 135,000-char headline. This report did not independently verify *which* backend served `bge-m3` on this machine. Either the MLX path reproduces the llama.cpp batching semantics exactly, or `bge-m3` is not being served through it. Both are consistent with the data; the probe cannot distinguish them, and for §6.4's purposes it does not need to.

---

# 3. The `format: "json"` hazard, re-checked against `qwen3:14b`

**What Fedora recorded.** `format: "json"` induced degeneration in `qwen3:8b` on **3 of 8 draws** — newline streams, and runaway to the token cap with duplicated keys — while `14b` and `4b` were unaffected. Every Fedora draw was **40 subjects**. Entry size was therefore never varied, and #33 names that as the untested axis.

**Method.** `qwen3:14b` only. Committed corpus (`research/ladder-probe/corpus.py`) and committed prompt (`prompt.txt`). Six entry sizes — **5, 10, 20, 40, 60, 80 subjects** — with **5 seeds each**, and at every single cell a **paired unconstrained control on the same seed and the same subjects**, so any difference is attributable to the flag and nothing else. Decoding matched the Fedora ladder: `temperature: 0`, `num_ctx: 16384`, `num_predict: 4096`, `seed: 42`, `think: false`. `keep_alive` passed explicitly. **60 draws total.**

Degeneration criteria were fixed from the Fedora observation before scoring: **D1** runaway (`done_reason == "length"`), **D2** newline stream (>30% newline characters, or a whitespace run > 100 chars), **D3** duplicated keys (distinct/total < 0.7), **D4** no recoverable entity list, **D5** entity inflation (> 2.5x subjects drawn). Envelope shape is deliberately **not** a criterion, and parsing uses `analyze.py`'s `entities_in()` rather than a new parser.

## Measured

| subjects | condition | draws | degenerate | strict-parse OK | entities recovered (mean) | out tok (mean) | max out |
|---|---|---|---|---|---|---|---|
| 5 | `format: "json"` | 5 | **0** | 5/5 | 5.2 | 329 | 383 |
| 5 | unconstrained | 5 | **0** | 5/5 | 5.2 | 329 | 381 |
| 10 | `format: "json"` | 5 | **0** | 5/5 | 10.0 | 619 | 651 |
| 10 | unconstrained | 5 | **0** | 5/5 | 10.0 | 623 | 651 |
| 20 | `format: "json"` | 5 | **0** | 5/5 | 19.8 | 1,228 | 1,259 |
| 20 | unconstrained | 5 | **0** | 5/5 | 19.8 | 1,228 | 1,260 |
| 40 *(Fedora's size)* | `format: "json"` | 5 | **0** | 5/5 | 39.6 | 2,363 | 2,528 |
| 40 *(Fedora's size)* | unconstrained | 5 | **0** | 5/5 | 39.6 | 2,363 | 2,528 |
| 60 | `format: "json"` | 5 | **0** | **5/5** | 59.8 | 3,748 | 4,071 |
| 60 | unconstrained | 5 | **1** (D1) | 4/5 | 46.2 | 3,753 | 4,096 |
| 80 | `format: "json"` | 5 | **4** (D1) | 1/5 | 12.2 | 3,923 | 4,096 |
| 80 | unconstrained | 5 | **4** (D1) | 1/5 | 12.2 | 3,923 | 4,096 |

**Totals: `format: "json"` 4/30 degenerate; unconstrained 5/30.**

**Envelope shapes across all 60 draws:** 51 x `{"entities": [...]}`, 9 x a bare object (every one of those a fragment recovered from a cap-truncated response). **No bare `[...]` and no `[{"entities": [...]}]`** — the two shapes the 8b produced on Fedora did not appear from the 14b at any entry size, in either arm.

## What the failures actually are

**Every single degenerate draw is D1 — the `num_predict: 4096` cap — and it fires in both arms at the same sizes, on the same seeds.** It is not the `format: "json"` signature:

- **None of the 8b signatures appeared, at any size, in either arm.** Zero D2 newline streams. Zero D3 duplicated keys. Zero D5 inflation.
- **The two arms are near-identical throughout.** Output token counts match within 0.6% at every size, and entity recovery is identical to one decimal place at five of six sizes.
- **The cap is arithmetically inevitable at these sizes.** `research/oversize-enrichment-budget.md` measures output at ~96 tokens per entity; 80 subjects therefore needs ~7,700 output tokens against a 4,096 budget. Hitting the cap at 80 subjects is the instrument's configuration, not model degeneration.
- **Where the arms do differ, `format: "json"` is the more robust one.** At 60 subjects the constrained arm produced 5/5 strictly parseable responses and recovered 59.8 of 60 subjects; the unconstrained arm produced 4/5 and recovered 46.2.

## Verdict

**The hazard did not reproduce against `qwen3:14b` on this machine, at any entry size tested.** Varying entry size — the specific untested axis — did not surface it. The flag is neither a hazard nor a benefit here; it is measurably inert on this model, on this runtime.

**Honest statement of power.** 5 draws per cell is thin. Restricting to the 25 `format: "json"` draws that ran below the output cap (sizes 5 through 60), **0 of 25 degenerated**, which by the rule of three bounds the per-draw degeneration rate at **under 12% (95%)**. That is enough to exclude a hazard of the magnitude Fedora saw in the 8b (**3/8 = 37.5%**), and not enough to exclude a rarer one. If `format: "json"` is ever adopted for the shipping path, this deserves a larger run; as long as it stays unused, the 14b's unconstrained behaviour is what matters and it was clean at every size below the cap.

## The finding that is not about `format: "json"`

**`num_predict: 4096` is a hard ceiling at large entry sizes, in both decoding configurations.** At 80 subjects, 4 of 5 seeds hit it in *both* arms; the response is a truncated JSON array with no closing bracket, and a downstream parser recovers roughly 12 of 80 subjects from the fragment before giving up — silently, with `done_reason: "length"` as the only signal.

This is a *known* consequence of the enrichment budget already documented in `research/oversize-enrichment-budget.md` (a cliff, not a slope), reproduced here on the Mac. It is enrichment-axis, and #33 lists enrichment throughput as an explicit non-goal, so it does not gate this deployment. It is worth carrying forward as **a runner obligation, not a model problem**: the enrichment runner must treat `done_reason == "length"` as a failure and not persist entities parsed out of a truncated response. The measured entry sizes here also sit far above §4.5's ~2,048-token capture ceiling — the 40-subject draw is ~1,248 prompt tokens — so nothing capture-path is affected.

---

# Summary against #33's abort conditions

| #33 abort/reshape condition | Status |
|---|---|
| Gate B lands anywhere near the 5 s budget → the reliability premise is wrong | **Does not fire.** 447 ms warm, 1,376 ms cold, 11.2x headroom warm. |
| §6.4's truncation behaviour differs on the MLX-backed runtime → embeddings silently at risk | **Does not fire.** Behaviour is identical at every check, including the exact 2,048 cliff. |
| `format: "json"` hazard present in the shipping model | **Does not fire.** 0 of 25 sub-cap draws degenerate; the flag is inert on the 14b here. |

**Nothing measured in this pass should abort or reshape the deployment.** Gate A (transport) was not in scope for this pass and remains the blocking item.

## Carried forward

1. **Record the LaunchAgent's `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` as part of the deployment's pinned configuration.** They arrived from Homebrew rather than from a decision, which is reason enough. ~~and the Fedora comparator did not have them~~ — **withdrawn, Fedora has both** (see the correction block); they are not a confound.
2. **The enrichment runner must reject `done_reason == "length"`** rather than persisting entities parsed from a truncated response. Measured here at 60-80 subjects per entry; not capture-path.
3. **Re-run `research/gate-b/truncation_probe.py` after any Ollama upgrade** — this now discharges the PRD's standing instruction with a committed, self-checking instrument rather than a manual procedure.
4. **Gate B was measured idle and mains-powered.** Thermal derate, battery-saver, and `NUM_PARALLEL=1` contention with the enrichment model are unmeasured. The headroom is large enough that this is a note, not a risk.
