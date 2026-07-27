# The Gate B "2.43x overshoot" — dissolved, twice over

**Question:** #33's Gate B measured a warm capture-path embedding ratio of **2.43x** (Mac ÷ Fedora, `bge-m3`, 1,839 tokens, `num_batch: 8192`). `research/33-gate-b-macbook.md` says this "sits just above the 1.83–2.22x platform penalty band #32 measured on the enrichment path," while the cold (1.09x) and query (1.14x) ratios sit far below it. Explain the overshoot, or establish it needs no explaining.

**Machine:** MacBook Pro, Apple M4 Pro, **16 GPU cores** (`system_profiler SPDisplaysDataType`), 48 GB unified, macOS 27.0. Ollama **0.32.4**, Homebrew LaunchAgent `homebrew.mxcl.ollama`, `127.0.0.1:11434`. **Idle and mains-powered** (`pmset -g batt`: "AC Power, 100%, charged") for every number below.
**Date:** 2026-07-27. **Branch:** `main`. Nothing committed.

---

## Verdict

**Dissolved. There is no overshoot, and there was never a comparison to be made.** Two independent reasons, either of which is sufficient. Both are measured, not argued.

**1. The comparison was a category error.** The 1.83–2.22x band is a **blended per-entry ratio for a causal decoder** — `qwen3:{4b,8b,14b}` doing prefill *and* autoregressive decode. `research/macos-spike-inference.md` §19.3 decomposes it and states the two underlying platform constants outright:

| | Achieved prefill compute | Achieved decode bandwidth |
|---|---|---|
| Fedora, RX 6900 XT, Ollama/ROCm | 24.8 TFLOPS | 350 GB/s |
| Mac, M4 Pro **20**-core, Ollama/GGUF-Metal | 5.77 TFLOPS | 194 GB/s |
| **Ratio, Fedora ÷ Mac (GGUF)** | **4.30x** | **1.80x** |

The 1.83–2.22x band is what you get when you mix those two in the ~12–30% prefill / ~70–88% decode proportion that `qwen3:14b` extraction happens to have. **`bge-m3` is an encoder: one forward pass, no KV cache, no decode.** It is 100% prefill. Its correct comparator is the **4.30x prefill column**, not the blend. Against that, 2.43x is not an overshoot — it is a substantial *undershoot*.

The "FLAT ACROSS MODEL SIZE" claim compounds this. §19.1's flatness is across **model parameter count** (`qwen3:4b`→`14b`, 3.7x), holding the workload shape fixed. Input length was never varied, and the band's own derivation (`Mac ÷ Fedora = w_p·(C_fed/C_mac) + w_d·(B_fed/B_mac)`) makes it explicit that the ratio is a weighted mix whose weights depend on the workload. A different workload shape gives a different blend, by construction.

Worth stating because it points the other way from the puzzle as posed: the 4.30x figure was modelled for a **20-core** M4 Pro. This machine has **16**, and §2 of the same document records a ~21% prefill gap between the parts. The naive prediction for this machine is therefore **~5.2x**, and the measured encoder compute ratio (below) is **3.1–3.8x**. The encoder does *better* on Metal than the decoder-derived model predicts, not worse. Why is untested — plausible candidates are `bge-m3`'s f16 dense weights versus `qwen3`'s 4-bit quantisation (no dequant in the Metal matmul path) and different arithmetic intensity. **Inferred, not measured.**

**2. Even setting that aside, 2.43x is not a platform property.** It is one blend of a cheap fixed cost and an expensive per-token cost, evaluated at one arbitrary input length, and **it slides continuously with input length**. The length sweep below confirms this directly: on this machine the Mac÷Fedora ratio runs from **~1.0–1.3x at 128 tokens to ~2.4x at 1,839 to ~2.5x at 2,048.** Quoting "2.43x" as a number is quoting the x-axis, not the hardware.

---

## 1. The length sweep

**Instrument:** `research/gate-b/embed_length_sweep.py` (new, committed-shaped, re-runnable). It imports `embed()` and `server_env()` from the existing `research/gate-b/embed_latency.py` verbatim — same call path, same PRD §6.4 obligations (`truncate: false`, `options.num_batch: 8192`, no prefix on either side) — and the same committed corpus (`research/ladder-probe/corpus.py`, 80 synthetic subjects). Every input size was built by binary-searching word count against the server's own `prompt_eval_count`, so sizes are in **measured bge-m3 tokens**, not estimated from characters. Every timed call asserts the returned `prompt_eval_count` and a 1024-dim vector, so a short read cannot be counted as a fast run.

**Protocol:** 12 sizes × 15 reps. Rounds are **interleaved and shuffled** — every size measured once per round in random order — so any thermal drift spreads across sizes instead of loading onto the largest one. Three unrecorded warm-ups per size first. Raw artefact: `research/gate-b/embed-length-sweep-Marks-MacBook-Pro-2.json` (all 180 observations, each tagged with its round).

| bge-m3 tokens | n | median (ms) | min–max | sd |
|---|---|---|---|---|
| 16 | 15 | 97.0 | 89.1 – 102.7 | 5.07 |
| 33 | 15 | 99.3 | 92.6 – 105.5 | 4.25 |
| 64 | 15 | 95.6 | 92.2 – 107.2 | 5.07 |
| 128 | 15 | 110.2 | 99.7 – 113.2 | 5.44 |
| 257 | 15 | 130.8 | 122.5 – 136.9 | 4.75 |
| 384 | 15 | 145.4 | 136.5 – 151.5 | 4.84 |
| 512 | 15 | 168.5 | 157.3 – 171.2 | 3.84 |
| 768 | 15 | 210.7 | 200.6 – 217.2 | 4.61 |
| 1024 | 15 | 258.0 | 245.7 – 263.3 | 5.34 |
| 1537 | 15 | 376.2 | 363.1 – 381.5 | 5.37 |
| **1839** | 15 | **445.2** | 434.9 – 466.1 | 6.61 |
| 2048 | 15 | 491.8 | 480.6 – 498.4 | 5.25 |

**445.2 ms at 1,839 tokens reproduces Gate B's 447.3 ms to within 0.5%**, on a different day, in a different harness, with shuffled ordering. The Gate B measurement is sound; only its interpretation was not.

### The fit

| Fit | Intercept | Slope | R² |
|---|---|---|---|
| Linear, all 12 sizes (medians) | 79.8 ms | 0.1941 ms/tok | 0.9927 |
| Linear, all 180 raw observations | 78.9 ms | 0.1942 ms/tok | 0.9914 |
| **Linear, 128–2048 (medians)** | **69.8 ms** | **0.2011 ms/tok** | **0.9942** |
| Linear, 512–2048 | 48.9 ms | 0.2144 ms/tok | 0.9973 |

**The hypothesis holds, with one correction and one refinement.**

**Correction: the intercept is not 99 ms.** The brief's arithmetic used the 15-token query latency as the intercept, giving 99 ms and a slope of 0.189 ms/tok. That is close, but the query point sits on a **floor**, not on the line. The three smallest sizes (16, 33, 64 tokens) are statistically indistinguishable from each other at ~96 ms, while the fitted line predicts 73–83 ms there. So the true structure is `max(floor, intercept + slope·n)` with a floor of **~96 ms** and a linear intercept of **~70 ms**; the floor binds below roughly 100 tokens. The residual pattern makes this visible: +23.9, +22.8, +13.0 ms at 16/33/64 tokens against the 128–2048 fit, then it drops away.

**Refinement: it is not linear, it is quadratic** — as an attention-bearing encoder must be. Within 0–2,048 the quadratic term is small enough that the linear fit reads as excellent, but pushing past the capture cap exposes it immediately (medians of 7 reps each, 2 warm-ups, same harness path):

| tokens | measured median | linear model `69.8 + 0.2011·n` | measured ÷ linear |
|---|---|---|---|
| 2048 | 486.4 ms | 481.6 ms | 1.01x |
| 3073 | 796.8 ms | 687.7 ms | **1.16x** |
| 4095 | 1,168.8 ms | 893.2 ms | **1.31x** |
| 6144 | 2,095.6 ms | 1,305.1 ms | **1.61x** |
| 7999 | 3,225.6 ms | 1,678.1 ms | **1.92x** |

Fitting a quadratic over the whole 128–7,999 range:

> **`latency_ms = 96.7 + 0.1247·n + 3.317e-5·n²`   (R² = 0.99993)**

Residuals: −3.0, −0.1, −4.0, −0.7, −1.3, −1.2, +9.5, +7.0, −4.8, +3.7, +5.3, −19.3, +9.1 ms across the thirteen sizes. That is a near-perfect fit over a 62x range in input length, and its intercept (96.7 ms) lands on the observed floor rather than needing one bolted on. **This is the honest functional form.** The `0.1247·n` term is the layer-stack cost (linear in tokens); the `3.317e-5·n²` term is self-attention.

**No steps, no knees, no batching artefacts.** This was the specific thing to look for and it is absent. The reason is visible in Ollama's own launch line: with `options.num_batch: 8192` it starts `llama-server` with `-b 8192 -ub 8192`, so every input up to 8,192 tokens goes through as a **single micro-batch**. There is nothing to step on.

**No thermal drift.** Comparing the first 5 rounds against the last 5, per size: +6.4, +1.0, +4.2, +0.2, −2.0, +1.9, −3.0, +1.4, −2.2, −4.3, +0.5, −4.4 ms. Non-monotone, both signs, all inside the per-size standard deviation. Overall early median 156.0 ms vs late 158.3 ms. Across a ~9-minute run on an idle mains-powered machine there is no derate to report. This does **not** speak to sustained load or battery — see §4.

### The decomposition, and the Fedora caveat

| | Overhead / floor | Per-token slope (128–2048) |
|---|---|---|
| **Mac (measured, 12 sizes × 15 reps)** | **~96 ms floor; 69.8 ms linear intercept** | **0.2011 ms/tok** |
| Fedora (**two points only**, from #33) | 87 ms (the 15-token query) | 0.0528 ms/tok |

**The Fedora slope is a two-point estimate and cannot be checked for linearity, for a floor, or for curvature.** It is `(184 − 87)/1839`. Two readings of it bracket the answer:

- **Taking the query point at face value as the intercept:** Fedora slope 0.0528 ms/tok → **compute ratio 3.81x**, overhead ratio 96/87 = **1.10x**.
- **Assuming Fedora has the same floor shape as the Mac** (Mac's linear intercept is 0.72x its floor; applying that gives a Fedora intercept of ~63 ms): slope 0.0658 ms/tok → **compute ratio 3.06x**. **This is an inference, not a measurement** — nobody has swept input length on the Fedora box.

Either way the picture is the same, and it is the one the hypothesis predicted: **an overhead ratio of ~1.1x and a compute ratio of ~3.1–3.8x, which the 1,839-token measurement blends into 2.43x.** How that blend moves:

| tokens | Mac (fitted) | Fedora, intercept 87 | ratio | Fedora, intercept 63 | ratio |
|---|---|---|---|---|---|
| 128 | 95.6 ms | 93.8 ms | 1.02x | 71.4 ms | 1.34x |
| 512 | 172.8 ms | 114.0 ms | 1.52x | 96.7 ms | 1.79x |
| 1024 | 275.7 ms | 141.0 ms | 1.96x | 130.4 ms | 2.11x |
| **1839** | 439.6 ms | 184.0 ms | **2.39x** | 184.0 ms | **2.39x** |
| 2048 | 481.6 ms | 195.0 ms | 2.47x | 197.8 ms | 2.44x |

The two Fedora treatments necessarily agree at 1,839 (both are anchored on the measured 184 ms) and diverge below it. **2.43x is a property of choosing 1,839 tokens.** Note also that the compute ratio 3.06–3.81x is itself only the ratio *within the capture range* — since both machines carry a quadratic term of unknown relative size, it is not a constant either, merely a much better-behaved one than 2.43x.

---

## 2. GPU and backend: both settled

**`bge-m3` runs entirely on the GPU, via llama.cpp / GGML-Metal — not MLX.** This is measured and corroborated three ways, none of which depends on `ollama ps` alone.

**a. `ollama ps` during a real embed** (sampled at 20 Hz from a thread while a loop of 1,839-token embeds ran, not at idle):
```
bge-m3:latest    790764642607    940 MB    100% GPU     8192    4 minutes from now
```

**b. Ollama's own server log, on a fresh load** (`/opt/homebrew/var/log/ollama.log`, watched from a known offset after `keep_alive: 0` eviction confirmed by `ollama ps`):
```
starting llama-server  cmd=".../libexec/lib/ollama/llama-server --model ...
   -c 8192 -np 1 --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on
   --embedding -b 8192 -ub 8192 --context-shift --keep 4"
gpu memory  id=0 library=Metal  available="36.9 GiB"
load_tensors: offloading output layer to GPU
load_tensors: offloading 23 repeating layers to GPU
load_tensors: offloaded 25/25 layers to GPU
load_tensors:   CPU_Mapped model buffer size =   520.29 MiB
load_tensors:  MTL0_Mapped model buffer size =   577.23 MiB
ggml_metal_init: found device: Apple M4 Pro
```
`25/25 layers offloaded`, `library=Metal`, `ggml_metal_init`. The 520 MiB `CPU_Mapped` buffer is the token-embedding table — 250,002 vocab × 1024 × 2 bytes = 512 MiB, matching almost exactly. That is a gather, not compute; it is not a partial-CPU offload of the transformer stack.

**c. This closes §6.4's open question.** The runtime request logs are llama.cpp's server format throughout (`srv update_slots`, `slot launch_slot_`, `n_ctx_slot`, `memory_seq_rm`). The Ollama binary **does** contain `github.com/ollama/ollama/x/mlxrunner` (confirmed by `strings`), so the MLX runner exists in this build — **it is simply not what serves `bge-m3`.** §6.4's recorded ambiguity — "MLX reproduces llama.cpp batching exactly" versus "`bge-m3` is not served through MLX here" — resolves to **the second**. The batching behaviour matches Fedora's because **it is the same llama.cpp code path on both machines**, not because two implementations agree. That is a stronger and simpler statement than the one on record, and it means §6.4's `num_batch` findings port across the two machines by construction.

**d. Corroboration independent of Ollama's reporting, from scaling.** `bge-m3` is XLM-RoBERTa-large shaped: 24 layers, d=1024, ~302M non-embedding parameters, f16. At 1,839 tokens the forward pass is ~1.11 TFLOP dense plus ~0.33 TFLOP attention ≈ **1.45 TFLOP**, executed in the 375 ms above the intercept — **~3.9 TFLOPS achieved**. A 16-core M4 Pro GPU is ~5.7 TFLOPS fp32 vector peak (higher through simdgroup matrix ops), so this is ~68% of peak: entirely consistent with a GPU-resident model and well above what GGML's CPU backend delivers in practice. **The FLOP counts are derived from the published architecture, not measured**; the timing is measured.

**What I could not do:** `powermetrics` GPU residency requires sudo, which I do not have. I did not run it and make no claim from it. Items (a)–(d) are the substitutes, and (b) — Ollama's own load-time log of the Metal backend and layer offload — is the load-bearing one.

---

## 3. The `OLLAMA_FLASH_ATTENTION` A/B — the predicted no-op is **wrong**, and there is a config hazard

The expectation on record (`33-gate-b-macbook.md`) was that both options "should not touch the Gate B numbers" because `bge-m3` "allocates no KV cache." **Half of that is right and half is measurably wrong.** Method: rewrite `EnvironmentVariables` in the LaunchAgent plist, `launchctl bootout` + `bootstrap`, poll until the server answers, reload and warm the model, 9 reps per size. The `llama-server` argv was read back from the log each time to confirm the flag actually landed.

| config | resulting `llama-server` flags | 33 tok | 1,839 tok | 6,144 tok |
|---|---|---|---|---|
| **baseline** `FA=1 KV=q8_0` | `--flash-attn on --cache-type-k q8_0` | 102.7 ms | 446.4 ms | 2,118.2 ms |
| `FA=1 KV=f16` | `--flash-attn on --cache-type-k f16` | 102.3 ms (0.996x) | 439.7 ms (**0.985x**) | 2,113.4 ms (0.998x) |
| **`FA=0` KV unset** | `--flash-attn off` | 105.2 ms (1.025x) | **532.4 ms (1.193x)** | **2,725.5 ms (1.287x)** |
| neither set | `--flash-attn` default | 103.7 ms (1.010x) | 444.8 ms (0.996x) | 2,112.0 ms (0.997x) |

**`OLLAMA_KV_CACHE_TYPE` is a genuine no-op** for this model (≤1.5%, within run-to-run noise) — as predicted, and now measured rather than inferred.

**`OLLAMA_FLASH_ATTENTION` is not.** Turning it off costs **+19.3% at 1,839 tokens and +28.7% at 6,144**, and the effect grows with input length — the signature of a term acting on attention, which scales as n². The stated mechanism ("no KV cache, therefore no effect") was wrong: flash attention is a **fused attention kernel**, not only a KV-cache optimisation, and a non-causal encoder's self-attention benefits from the fusion exactly as a decoder's does. The effect is invisible at 33 tokens (+2.5%) because the attention term is negligible there — consistent with the quadratic fit.

**This does not reopen the env-var theory as an explanation of the 2.43x, and does not resurrect it.** The theory is still dead, and now for a *measured* reason rather than an assumed one: `OLLAMA_FLASH_ATTENTION=1` is set on **both** machines (Fedora since 2026-07-22, per the brief), so both benefit identically. The "neither set" row shows why it would not have mattered anyway — **Ollama's default already enables flash attention** (444.8 ms, indistinguishable from the explicit `FA=1`), so even an unconfigured Fedora would have had it. What changes is only the status of the claim in `33-gate-b-macbook.md`: it should now read "measured to have no cross-machine effect because both are on and on is the default," not "inferred to be a no-op because encoders have no KV cache."

### A config hazard worth recording

The first attempt at this A/B, using `FA=0` with `KV=q8_0` left in place, **failed outright**:

```
llama_init_from_model: V cache quantization requires flash_attn
srv llama_server: exiting due to model loading error
[GIN] 500 | 895.685958ms | POST "/api/embed"
```

**`bge-m3` does not load at all if `OLLAMA_KV_CACHE_TYPE=q8_0` is set while `OLLAMA_FLASH_ATTENTION` is off.** The two Homebrew LaunchAgent variables are **coupled**, and the failure mode is a hard 500 on `/api/embed` — capture breaks completely, not gracefully. Anyone tuning flash attention off (to chase a `qwen3` quality question, say) silently breaks the capture path unless `OLLAMA_KV_CACHE_TYPE` is cleared in the same edit. This applies to the Fedora drop-in identically. It is not related to the 2.43x; it is a live operational trap found on the way past.

### Restoration, verified

The original plist was hashed before any change (`9d2ed9af…d53d76`) and restored in the script's `finally` block. Verified after the run **two ways**: `plutil -p` diff against the backup reports the files identical, and `launchctl print gui/$(id -u)/homebrew.mxcl.ollama` shows the **running service** carrying `OLLAMA_FLASH_ATTENTION => 1` and `OLLAMA_KV_CACHE_TYPE => q8_0`. `curl /api/version` returns `0.32.4`; `ollama ps` is clean. The service is as it was found.

---

## 4. What I measured, what I inferred, what I could not test

**Measured on this machine, this session:**
- The 12-point length sweep, 180 observations, and its fits (§1).
- The extension to 7,999 tokens and the quadratic form (§1).
- Absence of thermal drift across the sweep, idle and mains-powered (§1).
- `bge-m3` at 100% GPU during real embeds; `library=Metal`; 25/25 layers offloaded; `ggml_metal_init`; the `llama-server` argv (§2).
- Presence of `x/mlxrunner` in the binary and its non-use for this model (§2).
- The four-config flash-attention / KV-cache A/B, and the `FA=0 + q8_0` load failure (§3).
- Plist restoration, in the file and in the running service (§3).

**Inferred, stated as such:**
- That Fedora has a floor like the Mac's, giving the 3.06x compute-ratio bracket. Only the 3.81x figure follows from Fedora's two measured points alone.
- Why the encoder beats the 4.30x (or 16-core-adjusted ~5.2x) prefill prediction. Quantisation and arithmetic-intensity differences are candidates; none tested.
- The ~3.9 TFLOPS achieved figure (§2d) — timing measured, FLOP count derived from published architecture.

**Could not test:**
- **`powermetrics` GPU residency** — requires sudo, which I do not have. Substituted with §2 (a)–(d).
- **Anything on the Fedora box** — no access. Its slope remains a two-point estimate and cannot be checked for linearity, floor, or curvature. **A 12-point sweep on Fedora would settle the compute ratio to a single number and costs about ten minutes of that machine's time.** It is the one cheap measurement that would close what remains open here.
- **Battery, thermal derate under sustained load, and contention with `qwen3:14b` on the same GPU.** All three remain exactly as unmeasured as `33-gate-b-macbook.md` left them. The absence of drift in §1 covers a ~9-minute idle mains-powered run and nothing more.

---

## 5. What the PRD should quote instead

**Do not quote 2.43x, or any single Mac÷Fedora ratio, for the capture-path embed.** It is not a platform constant. It is the value of a length-dependent blend at one input size, and it is being compared against a band derived from a different workload shape.

Quote these instead. All are measured on this machine (M4 Pro 16-core GPU, Ollama 0.32.4, `bge-m3`, `num_batch: 8192`, idle, mains):

1. **The cost model, in preference to any ratio:**
   > `capture_embed_ms ≈ 97 + 0.125·n + 3.32e-5·n²`, for n in bge-m3 tokens, R² = 0.99993 over 128–7,999 tokens.

   Within the §6.4 capture range the simpler `≈ 70 + 0.20·n` (R² = 0.994, 128–2,048) is adequate and easier to reason with, with a **floor of ~96 ms** below ~100 tokens.

2. **The headline number, at the cap rather than at 1,839:** the capture ceiling is **2,048** tokens, and at 2,048 the measured warm median is **486–492 ms** (two independent runs: 491.8 ms, n=15; 486.4 ms, n=7). Against §4.5's **5,000 ms** inline budget that is **~10.2x headroom**. Gate B's 1,839-token figure is not the ceiling; the cap is.

3. **If a platform comparison is wanted, quote the two components, not the blend:** per-request overhead ratio **~1.1x**, per-token compute ratio **~3.1–3.8x** (the range being the two treatments of Fedora's two-point estimate). And note that for an encoder the comparable #32 constant is the **prefill** column — **4.30x** for the Ollama/GGUF path — not the 1.83–2.22x blended band, which prices decode.

4. **Gate B's PASS is unaffected and if anything strengthened.** The worst case in the operating range is 2,048 tokens at ~492 ms warm; the cold path adds ~870 ms of model load. Nothing observed in this investigation approaches §4.5's budget.

5. **Two corrections to `research/33-gate-b-macbook.md`:** its sentence "the warm ratio (2.43x) sits just above the 1.83–2.22x platform penalty band" should be withdrawn — the band is not a valid comparator for an encoder. And its inference that flash attention is a no-op on `bge-m3` is **wrong by 19–29%**; the correct statement is that it has no *cross-machine* effect because it is enabled on both and is Ollama's default anyway.
