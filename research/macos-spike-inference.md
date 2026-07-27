# Inference on Metal, and the cost model — macOS spike (Agent 1)

Research date: **2026-07-26**. Spike ticket: **#32**. Branch: `spike/macos-target`.
Owned PRD sections: **§1.4**, **§7.7**, **§6.4**, §4's per-entry cost model (**§1.5**, **§4.1**, **§4.2**, **§4.4**, **§4.5**, **§4.10**), and the inference/VRAM/latency/Ollama rows of **§13.3**.

Hypothetical target: **MacBook Pro, Apple M4 Pro, 48 GB unified memory, macOS, Metal, no network.**
Specified baseline: **Fedora 44 desktop, AMD RX 6900 XT (gfx1030), 16 GB VRAM, ROCm, Ollama, 64 GB system RAM.**

This document produces findings only. It does not change `PRD.md` and does not reopen any closed decision on its merits.

---

## Evidence grades used throughout

The PRD's own standard is measured / documented / assumed, and §13.3 exists because that standard was not always met. This document uses five grades, and every load-bearing number carries one:

| Grade | Meaning |
|---|---|
| **M-Tome** | A number `PRD.md` records as **measured on the Fedora box**. |
| **M-3P** | A number **someone else measured** and published, source named, hardware named. |
| **D** | **Documented** — stated in a vendor's own documentation, or read directly out of source code that I fetched. |
| **X** | **Derived** — arithmetic on M-Tome / M-3P / D inputs. The arithmetic is always shown so it can be checked or rejected. |
| **A** | **Assumed** — a judgement with no measurement behind it. Called out as such. |

Nothing in this document is a measurement taken on an M4 Pro. **I have not run anything on the target machine.** Every M4 Pro number here is either third-party-measured on an M4-family chip or derived. The measure-on-the-machine checklist in §14 exists because several of these questions are settled in minutes by running `llama-bench` or `omlx` on the actual laptop and cannot be settled at all by reading.

---

## 1. Summary — the answer in one page

**The capacity ceiling dissolves. The throughput ceiling replaces it, and it is worse.** That is the headline and it survived the MLX widening of the brief.

Per-entry extraction cost, for the PRD's own 18 s baseline entry (6,661 qwen3 prefill tokens, ~320 output tokens — the accounting is reconstructed and cross-checked in §7):

| Path | Prefill | Decode | Per entry | vs. PRD | 10k full run |
|---|---|---|---|---|---|
| **Fedora + ROCm + Ollama** (baseline; the model reproduces the PRD's 18 s) | 7.4 s | 10.7 s | **18.1 s** | 1.00× | **50 h** (§1.5) |
| **Mac + Metal + Ollama/GGUF**, M4 Pro 20-core GPU | 30.3 s | 15.8 s | **46.1 s** | **2.55×** | **128 h** |
| **Mac + MLX**, M4 Pro 20-core GPU | 30.3 s | 13.3 s | **43.6 s** | **2.41×** | **121 h** |
| **Mac + Metal + Ollama/GGUF**, M4 Pro **16**-core GPU | 37.0 s | 15.8 s | **52.8 s** | **2.92×** | **147 h** |

**A full re-derivation goes from ~2 days to ~5–6 days, on a machine that sleeps, moves, and runs on battery.** That is the single most consequential number in this area, and it is not rescued by MLX.

**MLX does not overturn the finding.** The reported 3× MLX-over-llama.cpp advantage is real but is a **Mixture-of-Experts** result. For a **dense 14 B at 4-bit** — which is exactly `qwen3:14b` — three independent routes (Apple's own mlx-lm benchmark scaled by parameters and GPU cores; Apple's own M4-vs-M5 research post; the llama.cpp Metal benchmark thread) converge on **~200–250 tok/s prefill** and **~20–24 tok/s decode** on an M4 Pro, regardless of runtime. MLX's edge on this model class is roughly **0 % on prefill and ~15–20 % on decode**, and part of even that is because the MLX 4-bit quant is a *smaller* artifact than GGUF Q4_K_M, not because the kernels are faster. Details and the honest uncertainty band are in §8.

**The four things that come back the other way** — all genuine, none of which offsets the throughput loss on its own:

1. **Capacity genuinely stops binding.** Metal reports ~36 GiB usable of 48 GiB by default; Tome's resident set is ~11–13 GB. `OLLAMA_GPU_OVERHEAD`, the `q8_0` KV requirement, `NUM_PARALLEL=1`, the 13.12/15.98 GB co-residency measurement and the entire iGPU rejection all **dissolve** (§6). No sysctl tuning is needed.
2. **Reproducibility may become reachable.** The PRD calls it *"unreachable, not merely expensive"* on a fact that is an **Ollama-registry artifact**, not a law of nature. An MLX/HuggingFace path pins by commit SHA, stores weights as ordinary content-addressed files, and never garbage-collects them. This is the most consequential *non-performance* finding in this document, and it outlives the Mac question (§11).
3. **The embedding path survives comfortably** on both runtimes, and `bge-m3` has a first-class MLX conversion. §6.4's single highest-value line ports as a native substitute with the same shape (§9).
4. **The `q8_0` KV constraint and the serialisation it forced can both be relaxed**, which removes a real capture-vs-enrichment contention (§6.4).

**And two that make it worse than the raw multiplier suggests:**

5. **The cost model changes shape, not just magnitude.** On the Fedora box the 18 s splits ~41 % prefill / ~59 % decode. On the M4 Pro it becomes **~66–70 % prefill**. Everything the PRD reasons about as "costs only prefill" — §4.9's name-precedence rule says exactly that — was priced when prefill was the cheap half. It is now the expensive half (§7.4).
6. **Bandwidth is now shared with everything the user does.** On the desktop, a browser touches system RAM and inference touches VRAM; they do not contend. On unified memory they contend for the *same* 273 GB/s that decode is bound by, and they contend for the same thermal envelope. §7.7's *"the machine is assumed not in use during enrichment"* is false on a laptop **and** the consequence is no longer merely social (§6.3, §12).

**Runtime recommendation:** if this target is ever pursued, **oMLX** (`github.com/jundot/omlx`) is the only serving stack found that can carry Tome's whole surface — generation *and* embeddings *and* reranking, with model pinning, per-model TTL and a memory ceiling — but it is **five months old with 741 open issues**, and staking a memory-keeper's durability on it is a different risk class than staking it on Ollama. Ollama-on-Mac is now MLX-backed anyway (§4), which collapses most of the performance argument for switching. **The reproducibility argument, not the performance argument, is the reason to look at an MLX/HF path** — and that argument applies on Fedora too. Full reasoning and what would change my mind: §13.

**Per-section verdicts:** §15. **Measure-on-the-machine checklist:** §14.

---

## 2. What the M4 Pro actually is — §1.4's facts, restated

`PRD.md` §1.4 is a list of *measured facts that decided things*. Here is the same list for the hypothetical target, with grades. Facts I cannot establish without the machine are marked and appear again in §14.

| §1.4 fact (Fedora) | M4 Pro equivalent | Grade |
|---|---|---|
| AMD RX 6900 XT, gfx1030, **80 CUs** | Apple M4 Pro GPU, **16 or 20 cores** — both exist, and **48 GB is offered on both** | **D** — Apple lists "16-core GPU, 20-core GPU" for M4 Pro and offers 48 GB as a configure-to-order option ([MacBook Pro 14-inch M4 Pro tech specs](https://support.apple.com/en-us/121553)) |
| **16 GB VRAM (15.98 GiB usable)** | **48 GiB unified**, of which Metal reports ~**36 GiB** by default | **D + X** — see §5 |
| GDDR6 at **~512 GB/s** | LPDDR5X at **273 GB/s** | **D** — Apple states "273GB/s memory bandwidth" for M4 Pro on both the 14-inch and 16-inch spec pages |
| 64 GB system RAM, **separate** from VRAM | 48 GiB, **shared** — one pool, one bandwidth budget | **D** |
| **1.16 GiB VRAM held with no model loaded** | No direct analogue. macOS idle working set is far larger, but it comes out of the same pool Metal draws on, and Metal's own `currentAllocatedSize` only counts the *calling process* | **D** (ggml source, §5) |
| Raphael iGPU (`gfx1036`), 2 CUs, no rocblas — **ruled out** | **No second GPU exists.** The whole analysis dissolves | **D** |
| Ollama **v0.32.1**, hand-installed at `/usr/local/bin`, owned by no package | Ollama on macOS ships as an `.app` / Homebrew formula; **and on Apple silicon it is now MLX-backed** (§4). oMLX ships as `.dmg` or `brew` | **D** |
| firewalld `FedoraWorkstation` zone opens 1025–65535 on `eno1` | Not applicable — Agent 2 owns this | — |
| Dual-boot, **sometimes off for stretches** | **Sleeps constantly rather than powering off** — Agent 3 owns the consequences; §12 owns the thermal/power half | — |
| 72.4 Wh battery (14-inch) / 100 Wh (16-inch); 70 W or 96 W adapter (14-inch), 140 W (16-inch) | new fact with no Fedora counterpart | **D** ([121553](https://support.apple.com/en-us/121553), [121554](https://support.apple.com/en-us/121554)) |

**Two facts in that table would decide things and are not yet known:**

- **Which M4 Pro.** 48 GB is available on the 12-core-CPU/**16-core-GPU** part and the 14-core-CPU/**20-core-GPU** part. Prefill is compute-bound, so the difference is real: llama.cpp's Apple-silicon benchmark thread measures the same 7B Q4_0 at **pp512 364.06 t/s (16-core)** versus **439.78 t/s (20-core)** — a **21 % prefill gap** — while text generation is essentially identical (**49.64 vs 50.74 t/s**), exactly as bandwidth-bound decode predicts, since both parts have the same 273 GB/s ([ggml-org/llama.cpp discussion #4167](https://github.com/ggml-org/llama.cpp/discussions/4167), **M-3P**). Since the M4 Pro's cost is now prefill-dominated, this alone is a ~20 % swing on the full-run estimate.
- **14-inch or 16-inch.** Same silicon, different battery (72.4 vs 100 Wh), different adapter (70/96 W vs 140 W), and different sustained thermal headroom. §12.

**One fact that changed under the project's feet.** Apple's M5 introduced per-GPU-core **Neural Accelerators** providing dedicated matrix-multiply, which Apple measures at **4.06× faster time-to-first-token** on **exactly `Qwen3-14B-4bit`** versus an M4 ([Apple ML Research, *Exploring LLMs with MLX and the Neural Accelerators in the M5 GPU*, 2025-11-19](https://machinelearning.apple.com/research/exploring-llms-mlx-m5), **D/M-3P**). The M4 Pro sits on the wrong side of that jump. This is a hardware-selection finding, not a portability finding, but it is the kind of thing that should be said out loud before anyone buys a machine to run this on: **an M5 Pro would erase most of the prefill penalty this document is about.**

---

## 3. The three-way runtime question, named precisely and dated

The owner's note referred to "omlx" without certainty about what that names. Here is what actually exists on 2026-07-26, established from repository metadata and source rather than from write-ups.

| Option | What it actually is | Status on 2026-07-26 | Serves embeddings? |
|---|---|---|---|
| **MLX** (`ml-explore/mlx`) | Apple's array framework. Not a server. MIT. 27.7k stars, pushed 2026-07-25 | Foundation layer | n/a |
| **mlx-lm** (`ml-explore/mlx-lm`) | Apple's LLM package on top of MLX. Ships `mlx_lm.server` | MIT, 6.4k stars, pushed 2026-07-26 | **No.** Its HTTP server routes are `/v1/completions`, `/v1/chat/completions`, `/v1/models`, `/health` — read directly from [`mlx_lm/server.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py) (**D**). There is no `/v1/embeddings`. |
| **mlx-embeddings** (`Blaizzy/mlx-embeddings`) | A *library* for running embedding models under MLX. 423 stars, last pushed 2026-05-13 | Library, not a server | Yes, but you write the server |
| **oMLX** (`jundot/omlx`) | Full OpenAI- **and** Anthropic-compatible inference server, Apple-silicon only. Apache-2.0, Python 3.11–3.13, macOS 15.0+ | **18.2k stars, created 2026-02-13, v0.5.3 released 2026-07-22, 741 open issues** | **Yes** — `POST /v1/embeddings` and `POST /v1/rerank`, with **BGE-M3 named explicitly** in its supported-embedding list (**D**, README) |
| **Ollama on Apple silicon** | **Is now MLX-backed.** Ollama announced "Ollama is now powered by MLX on Apple silicon in preview" on **2026-03-30** ([ollama.com/blog/mlx](https://ollama.com/blog/mlx)), and the repository contains an `x/mlxrunner/` package with continuous batching, prefix caching and speculative decoding (**D**) | Preview | Yes — Ollama's `/api/embed` is unchanged |
| **LM Studio MLX engine** | GUI-first, closed-source app with an MLX engine | Not evaluated in depth — a GUI app is a poor fit for a launchd-managed background service, and Tome's whole design is headless | — |

**Three consequences of that table.**

- **"MLX instead of Ollama" is now partly a false dichotomy.** Ollama on Apple silicon *is* MLX. Choosing "Ollama on Mac" in mid-2026 already buys the MLX engine, without changing Tome's client code, without changing the epoch's `ollama --version` field, and without adopting a five-month-old project. The performance argument for switching runtimes has largely evaporated; what remains is the *reproducibility* argument (§11), which is about artifact management, not kernels.
- **mlx-lm alone is not a viable path.** It cannot serve embeddings, and Tome embeds on the **capture hot path** (§4.5). An mlx-lm path means a second model server for embeddings — two launchd jobs, two ports, two model-residency stories, two failure modes on a path §7.3 deliberately made *soft*. That is a real cost and it is why oMLX, not mlx-lm, is the only serious MLX-native candidate.
- **oMLX's maturity is the risk, not its capability.** Capability-wise it is a startlingly good fit for §7.7 (see §6.4). But 741 open issues against a project that did not exist six months ago, holding the only write path into a memory-keeper, is a different risk class from Ollama — whose version-pinning §12.1 already records as "satisfied structurally". The PRD's judgement in §7.7 was explicitly *"declined on proportion"*; the same discipline applies here.

*Dating note: every status figure in this table was read from the GitHub API on 2026-07-26 and will drift.*

---

## 4. Ollama on Apple silicon, as it stands

Established from primary sources (Ollama's own blog and repository):

- **Ollama is MLX-backed on Apple silicon**, announced 2026-03-30, described as **preview** ([ollama.com/blog/mlx](https://ollama.com/blog/mlx), **D**). A follow-up post claims the MLX engine is "up to 20 % faster" from kernel fusion and reworked GPU-backed sampling ([ollama.com/blog/mlx-performance](https://ollama.com/blog/mlx-performance), **D** — the post gives no reproducible per-chip numbers, so treat the 20 % as vendor-stated rather than measured).
- The benchmark numbers Ollama publishes alongside the announcement are for **Qwen3.5-35B-A3B**, an **MoE** model, at NVFP4: prefill 1810 t/s and decode 112 t/s, against 1154/58 on the previous engine. **These are MoE numbers and must not be read across to a dense 14 B.** This is the single most common error in the secondary literature on this question.
- The announcement notes the preview path requires "a Mac with more than 32 GB of unified memory" — a 48 GB machine clears that (**D**).
- **Flash attention is supported on Metal** in Ollama: `ml/device.go`'s `FlashAttentionSupported` returns true for `gpu.Name == "Metal" || gpu.Library == "Metal"` (**D**, read from source). This matters because `OLLAMA_KV_CACHE_TYPE=q8_0` requires flash attention — so §7.7's `q8_0` KV cache setting *would* still work on Metal, even though §6 shows it is no longer needed.
- **Version numbering is inconsistent between the blog and §1.4.** The blog names releases in the 0.18/0.19 range; §1.4 records "Ollama v0.32.1" measured on the Fedora box. I could not reconcile these and did not try further — nothing in this analysis depends on it, but **anyone acting on this document should re-check the version story rather than inherit it**, because §3.7's epoch records `ollama --version` as an identity field.

---

## 5. What macOS actually lets the GPU use — killing hypothesis 3

**Hypothesis 3 as stated ("macOS caps GPU-usable unified memory at roughly 75 %; establish the real ceiling and whether raising it is safe") is confirmed on the mechanism and killed on the consequence: the cap is real, it is not binding, and raising it is unnecessary.**

### 5.1 The mechanism, from source

The chain is short and every link is readable:

1. **ggml's Metal backend reports device memory as `recommendedMaxWorkingSetSize`.** From `ggml/src/ggml-metal/ggml-metal-device.m` (**D**, fetched 2026-07-26):

   ```c
   void ggml_metal_device_get_memory(ggml_metal_device_t dev, size_t * free, size_t * total) {
       if (@available(macOS 10.12, iOS 16.0, *)) {
           *total = dev->mtl_device.recommendedMaxWorkingSetSize;
           *free  = *total - dev->mtl_device.currentAllocatedSize;
       } else {
           *free = 0;
           *total = 0;
       }
   }
   ```

   This is wired to the backend device interface as `.get_memory` in `ggml-metal.cpp`, so it is what any ggml consumer sees when it asks how much GPU memory exists.

2. **Ollama consumes that number and subtracts its own reserves.** `server/sched.go` (**D**):

   ```go
   available := gpu.FreeMemory - envconfig.GpuOverhead() - gpu.MinimumMemory()
   ```

   and `ml/device.go` sets `MinimumMemory()` to **512 MiB for Metal** (versus 457 MiB elsewhere).

3. **`recommendedMaxWorkingSetSize` is what `iogpu.wired_limit_mb` moves.** Apple documents the property as "an approximation of how much memory, in bytes, this GPU device can allocate without affecting its runtime performance" ([Apple Developer](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize), **D**). The sysctl is undocumented by Apple; the reserve fractions come from a disassembly posted in [ggml-org/llama.cpp discussion #2182](https://github.com/ggml-org/llama.cpp/discussions/2182) showing `reservePercent = 33.333f`, dropping to `25.0f` above `0x800000000` bytes (32 GiB) — **weak evidence, reverse-engineered, cite as such.**

4. **Curiosity worth recording:** Ollama's `discover/gpu_info_darwin.m` still defines `getRecommendedMaxVRAM()`, but a GitHub code search finds no Go caller — only the `.m` and `.h`. Ollama's own darwin memory discovery (`discover/gpu_darwin.go`) reports **`NSProcessInfo.physicalMemory`** and a Mach-derived free figure as *system* memory, and lets ggml's backend registry supply the *device* figure. So there are two different memory views in play. Not load-bearing at Tome's sizes, but it is exactly the kind of undocumented seam §6.4 warns about, and it is why §14 asks for the startup log rather than for arithmetic.

### 5.2 The number

On a 48 GB machine (`physicalMemory` = 48 GiB = 51,539,607,552 bytes), at a 25 % reserve:

- `recommendedMaxWorkingSetSize` ≈ **36 GiB** (**X**, from the reverse-engineered fraction — verify by reading one log line, §14)
- minus Ollama's Metal `MinimumMemory()` of 512 MiB → **~35.5 GiB available** (**X**)

Against Tome's resident set:

| Item | Fedora (M-Tome) | Mac, Ollama/GGUF | Mac, MLX |
|---|---|---|---|
| `qwen3:14b` Q4_K_M at `num_ctx` 16384 | **10 GB** (§7.7, M-Tome) | ~10 GB | **9.16 GB** peak for `Qwen3-14B-MLX-4bit` at a 4096 prompt (Apple, **M-3P**) |
| `bge-m3` weights | ~940 MB (§6.4) | ~940 MB | ~1.2 GB fp16 (`mlx-community/bge-m3-mlx-fp16`) |
| `num_batch: 8192` buffer | **276 MB** (§6.4, M-Tome) | 276 MB | no equivalent (§9) |
| Both models co-resident, total | **13.12 GB of 15.98 GiB = 76.4 %** (M-Tome) | **~11–13 GB of ~35.5 GiB ≈ 32–37 %** (**X**) | similar |

**KV cache arithmetic, from `Qwen/Qwen3-14B/config.json`** (**D**: 40 layers, 8 KV heads, `head_dim` 128):

```
bytes/token = 2 (K and V) × 40 layers × 8 kv_heads × 128 head_dim × bytes_per_element
f16   : 2×40×8×128×2 = 163,840 B/token = 160 KiB/token → 2.50 GiB at 16,384 tokens
q8_0  : ≈ 8.5 bits/element        ≈  85 KiB/token → 1.33 GiB at 16,384 tokens
```

The **f16-versus-`q8_0` delta at 16k is ~1.17 GiB.** On a 15.98 GiB card that was the difference between fitting comfortably and not; against ~35.5 GiB it is noise. As a cross-check on the arithmetic, at `NUM_PARALLEL=4` f16 KV comes to **10.0 GiB**, which corroborates §7.7's *"at 4, KV alone would be ~10.9 GiB and nothing fits"* — and on 48 GB, 10 GiB of KV plus ~13 GB of weights is ~23 GiB of ~35.5 GiB. **`NUM_PARALLEL=4` now fits.**

### 5.3 Verdict on hypothesis 3

- **Confirmed:** the cap exists, is real, gates Ollama and any ggml/MLX consumer, defaults to ~75 %, and is moved by `sudo sysctl iogpu.wired_limit_mb=N`, which **resets on reboot** and is unsupported by Apple.
- **Killed:** *"establish whether raising it is safe"* is the wrong question, because **there is no reason to raise it.** Tome needs ~13 GB of ~35.5 GiB. Recommending a sysctl tweak here would be spending an unsupported, reboot-volatile, system-wide setting to buy headroom that is already unused — and on a machine that is "simultaneously doing everything else the user does", eroding the OS's reserve is exactly the wrong trade.
- The only scenario that revives the question is hypothesis 4 (a larger enrichment model), and §10 concludes that trade is bad for a different reason.
- **Note the changed failure mode.** On the desktop, over-committing VRAM makes Ollama spill layers to CPU — slow, but bounded, and *reported* (`100% GPU` becomes something less). On unified memory, exceeding the wired limit does not error either; it pushes the system into compression and swap, which degrades **everything on the machine at once**, not just the run. The guardrail `OLLAMA_GPU_OVERHEAD` existed to stop the first failure. There is no equivalent guardrail against the second, and the default reserve *is* the guardrail. Another reason not to touch it.

---

## 6. §7.7 audited, setting by setting, on both runtime paths

§7.7 is the densest section in the PRD and the most 16-GB-shaped. Here is every line of it, with a verdict for each runtime path. **"Dissolves" means the problem does not exist on this target** — it is a stronger and more useful result than "survives".

| §7.7 item | Fedora rationale | Mac + Ollama/GGUF | Mac + MLX (oMLX) |
|---|---|---|---|
| **Both models co-resident, no swap** (`OLLAMA_MAX_LOADED_MODELS` auto = 3 × GPU count) | Superseded a sequential hot-swap design | **Survives unchanged.** One Metal device → auto = 3. Trivially satisfied at ~13 GB of ~35.5 GiB | **Survives with a native substitute.** oMLX has an `EnginePool` with LRU eviction, **manual load/unload, model pinning and per-model TTL** (**D**, README). Strictly more expressive than Ollama's |
| **Measured 13.12 GB of 15.98 GiB (76.4 %)** | The load-bearing capacity measurement | **Dissolves.** ~32–37 % of ~35.5 GiB. The measurement is not wrong, it is no longer a constraint | Same |
| **The `q8_0` KV cache requirement** — *"an f16 cache would not fit as comfortably"* | 16 GB ceiling | **Dissolves.** f16 KV costs 1.17 GiB more at 16k against ~22 GiB of headroom. Ollama on Metal *supports* `q8_0` (flash attention is enabled for Metal — **D**, `ml/device.go`), so this is a free choice rather than a forced one — and f16 is the better choice, since it removes a quantisation that was accepted under duress | **Dissolves**, differently: oMLX's cache stack is a block-based paged cache with prefix sharing and Copy-on-Write, plus a hot/cold RAM+SSD tier. The `q8_0` knob has **no equivalent**; the concept it belonged to is gone |
| **Pin the embedding model** (`keep_alive=-1` at MCP server start) | *"So it is never the model that has to be loaded"* — because Ollama evicts only idle models and a 275 MB embedder can evict a 10 GiB `qwen3` | **Survives unchanged, and the failure mode it prevents becomes unreachable anyway.** The eviction spiral §7.7 describes requires memory pressure. At 37 % utilisation there is none. Keep the pin: it costs nothing and the reasoning is about *Ollama's* LRU, not about capacity | **Survives with a native substitute** — oMLX's **model pinning** is the same concept, named the same thing. Its `ProcessMemoryEnforcer` defaults to "system RAM − 8 GB", i.e. ~40 GB here, which is above Metal's own ~36 GiB ceiling and therefore inert |
| **Shorten the global keep-alive** (crash behaviour: *"a run that dies before unloading pins ~10 GiB for minutes, not a day"*) | 16 GB ceiling | **Survives, but the argument weakens to near-zero.** Pinning 10 GiB of 36 GiB for a day is not a problem. Keep it for hygiene, not for capacity | **Survives with a native substitute** — oMLX's **per-model TTL** is exactly `keep_alive` |
| **Unload `qwen3:14b` at end of run** | Same | Same as above | Same |
| **`OLLAMA_GPU_OVERHEAD` → ~1.5 GiB** — *"This, not cgroup limits, is the real guardrail"* | At 0, Ollama sizes as though all 15.98 GiB were free when ~1.16 GiB is not | **Dissolves.** The env var still exists and is still applied (`server/sched.go`, **D**), but Metal already reports `free = recommendedMaxWorkingSetSize − currentAllocatedSize`, and the remaining margin is ~22 GiB. Setting it would be cargo-culting. **But note the honest gap:** `currentAllocatedSize` is the *calling process's* allocation, so other apps' GPU use is invisible to it — the desktop's 1.16 GiB problem is structurally still there, just made irrelevant by scale | **Dissolves** — no equivalent knob, no need for one |
| **Drop global `OLLAMA_CONTEXT_LENGTH` for a per-request `num_ctx` ~16k** | The global override was 8× Ollama's VRAM-derived choice for this card | **Survives unchanged.** Per-request `num_ctx` is a request field, not a device property. §4.4's whole pre-flight assertion depends on it, and none of that reasoning touches the GPU | **Breaks as written, survives in substance.** There is no `num_ctx`; oMLX's paged cache grows as needed under a memory ceiling. §4.4's assertion `P + entry×0.906 + 500 + 1500 ≤ num_ctx` still needs a right-hand side, so a **configured** limit has to be invented rather than inherited from the runtime. **This is not cosmetic** — see §7.5 |
| **`OLLAMA_NUM_PARALLEL` stays 1** — *"At 4, KV alone would be ~10.9 GiB and nothing fits"* | Pure capacity | **Dissolves as a constraint; becomes a live decision.** 4 slots of f16 KV = 10.0 GiB (**X**, §5.2) fits. Raising it for **`bge-m3` only** would remove the §6.6/§4.5 contention where a capture embed queues behind an entity embed — the exact reason §4.5's deferred path had to be re-justified. Cheap: an encoder's per-slot cost is small. **Reported as a finding, not proposed** | **Dissolves.** oMLX does continuous batching through mlx-lm's `BatchGenerator`, default **`--max-concurrent-requests 8`**. The serialisation §6.5 and §6.6 reason from **is not the default behaviour of this runtime** |
| **Bind loopback only** (`OLLAMA_HOST=127.0.0.1:11434`) | firewalld opens 1025–65535 on `eno1` | Agent 2 owns the network verdict. Mechanically the knob exists on both | oMLX binds `localhost:8000` by default and additionally offers `--api-key` |
| **`ollama.service` deliberately left unsealed**; `IPAddressDeny=` measured and declined | systemd cgroup BPF filter | **Restated, not ported.** macOS has no `IPAddressDeny=` equivalent — this is #28's ruling and Agent 2 owns it. §11.3 adds the MLX-specific twist | The fetching process changes identity entirely — §11.3 |
| **No CPU/memory/IO limits; no idle-gating** — *"the machine is assumed not in use during enrichment"* | Desktop duty cycle | **Breaks.** The premise is false on a laptop, and on unified memory the contention is no longer merely social — it is for the same bandwidth and the same thermal envelope (§6.3, §12). Agent 3 owns the gating decision; this section owns the reason it is now load-bearing | Same |
| **The iGPU is ruled out on hard data** (2 CUs vs 80; no rocblas for `gfx1036`; DDR5 ~96 GB/s vs GDDR6 ~512 GB/s; *"a larger context makes prefill dominant and prefill is compute-bound"*; no per-model device selection) | Whole-section analysis | **Dissolves entirely.** There is one GPU. No `gfx` targets, no rocblas, no `HSA_OVERRIDE_GFX_VERSION`, no two-services-two-ports mechanics | Same |

### 6.1 The one piece of §7.7's reasoning that survives and turns around to bite

§7.7's iGPU paragraph contains the sentence that matters most for this whole spike:

> *"Decisively, **a larger context makes prefill dominant and prefill is compute-bound**, so the iGPU is at its worst precisely at the operation the extra capacity was for."*

That reasoning is **correct**, is **corroborated by Apple's own primary documentation** — *"generating the first token is compute-bound... Generating subsequent tokens is bounded by memory bandwidth, rather than by compute ability"* ([Apple ML Research](https://machinelearning.apple.com/research/exploring-llms-mlx-m5), **D**) — and it is **exactly the argument that indicts the M4 Pro**. The M4 Pro is not a 2-CU iGPU; the ratios are 4× on prefill, not 40×. But the argument's *shape* transfers intact, and §8 quantifies it.

### 6.2 What replaces the ceiling — the direct answer to hypothesis 1

**Hypothesis 1 is confirmed: capacity stops being the binding constraint.** Three things replace it, in order of how much they matter:

1. **Sustained prefill throughput.** ~220 tok/s versus ~900. This is the binding constraint and it is a *rate*, not a *ceiling*. That is a qualitatively different kind of constraint to design against: a ceiling either fits or it doesn't and you find out at load time; a rate degrades everything continuously and shows up as wall-clock in §1.5's table.
2. **Bandwidth contention with the rest of the machine.** On the desktop, VRAM traffic and system-RAM traffic are physically separate. On unified memory they are the same 273 GB/s. Decode is bandwidth-bound; therefore **anything the user does during a run directly slows the run, and the run directly slows everything the user does.** There is no equivalent on the Fedora box, and no configuration knob for it — this is architecture, not policy. §7.7 explicitly declined CPU/memory/IO limits on the grounds that *"the knobs are not connected to the contended resource"*. On the Mac, the knobs are still not connected to the contended resource, but now the contended resource is one the user is also using.
3. **The sustained power and thermal envelope.** §12.

**Notably absent from that list: swap.** The natural guess is that a unified-memory machine's new ceiling is "macOS decides to swap". At Tome's sizes it will not — ~13 GB resident on a 48 GB machine leaves room for a normal working set. The swap cliff is real (§5.3) but is not reachable without deliberately raising `iogpu.wired_limit_mb` or loading a much larger model.

### 6.3 One thing §7.7 gets that it would lose

§7.7 spends most of its length reasoning about **eviction, residency and thrash** — the failure mode where *"a trickle of saves thrashes the run."* On the Mac that whole class of failure becomes unreachable through abundance. That is a genuine simplification and it should be counted on the credit side: **a section that is ~40 % eviction-avoidance reasoning would shrink to a handful of lines.** It is just not worth 2.5× the per-entry cost.

### 6.4 oMLX's fit to §7.7, stated plainly

This deserves saying because it is surprising. §7.7's requirements are: co-residency without swap, a pinned small model, an idle timeout on the large one, an explicit unload, a memory ceiling that accounts for what the device is already using, and no priority inversion. **oMLX ships every one of those as a named feature** — `EnginePool` with LRU eviction, **model pinning**, **per-model TTL**, **manual load/unload**, and a **`ProcessMemoryEnforcer`** with a configurable ceiling (`--memory-guard-gb`). It is a closer match to §7.7's intent than Ollama is, because Ollama's §6.6 finding — *"Ollama has no priority, pinning or reservation concept"* — is precisely the gap oMLX was built to fill.

**That does not make it the recommendation.** §13.

---

## 7. The cost model, reconstructed and checked before it is re-costed

Before re-costing the ~18 s and ~50 h figures it is necessary to know what they are made of. The PRD does not decompose them, and §13.3 already flags the whole thing as resting on an unverified claim (*"a merging extraction may be two `qwen3` calls, not one... **This is the cost model that the ~18 s/entry and ~50 h figures rest on**"*). So the first task is to derive a decomposition and check it against the PRD's own measurements. It checks out to within a few percent on four independent data points, which is a stronger foundation than I expected to find.

### 7.1 Where the numbers are stated

- **§1.5:** *"One extraction call is **~18 s**, so a full re-derivation is **~5 h at 1k entries, ~25 h at 5k, ~50 h at 10k**."*
- **§4.1:** the `full` mode row repeats **~5 h / 1k, ~25 h / 5k, ~50 h / 10k**; `reembed` is **~6 min / 10k**.
- **§3.7:** the extraction axis's remedy is *"full run — ~50 h / 10k"*, against the embedding axis's *"`--reembed` — ~6 min / 10k"*. The **500:1 ratio between those two remedies is a load-bearing design fact** — it is why the epoch is itemised rather than one opaque hash.
- **§4.4:** the runaway case *"burned **602 s — 33× the 18 s baseline** — producing nothing."*

**The 50 h figure is literally 18 s × 10,000 = 180,000 s = 50.0 h** (**X**). There is no other content in it. So re-costing the full run reduces exactly to re-costing one entry, and every downstream figure moves by the same multiplier.

### 7.2 Extracting a decode rate from the PRD's own numbers

§4.4's runaway measurement is unusually informative:

> *"At 6,046 tokens... The worst run emitted **17,957 output tokens for a total of 24,618** against a 16,384 window... it burned **602 s — 33× the 18 s baseline**."*

Two things fall straight out (**X** on **M-Tome** inputs):

```
prompt tokens  = 24,618 − 17,957 = 6,661 qwen3 tokens
cross-check    : 6,046 bge tokens × 0.906 (§4.4 ratio) = 5,478
               + 1,215 (measured prompt P)            = 6,693     ✓ within 0.5 %
decode rate    ≥ 17,957 / 602 s = 29.8 tok/s   (equality iff prefill were free)
               = 30.2 tok/s if prefill took 7.4 s
```

**So `qwen3:14b` Q4_K_M decodes at ~30 tok/s on the RX 6900 XT (M-Tome-derived).** That is a real number the PRD contains but never states, and it is almost insensitive to any prefill assumption. Sanity check against physics: 30 tok/s × ~9.0 GB of weights ≈ 270 GB/s effective, i.e. **53 % of the card's 512 GB/s** — a normal llama.cpp-on-ROCm efficiency, and consistent with the third-party RX 6900 XT measurement below.

### 7.3 Extracting a prefill rate, and checking the whole model

Prefill is not directly measurable from the PRD. Anchor: llama.cpp's ROCm benchmark thread measures an **RX 6900 XT** on **llama 7B Q4_0** at **pp512 = 1889.84 ± 31.21 t/s, tg128 = 88.49 t/s** ([ggml-org/llama.cpp discussion #15021](https://github.com/ggml-org/llama.cpp/discussions/15021), **M-3P** — the exact card, not an extrapolation from a 6800). Prefill compute scales roughly inversely with parameter count, so a 14.8 B model at 4-bit should land near `1889.84 × 7/14.8 ≈ 894 t/s`, a little lower for Q4_K_M's costlier dequantisation than Q4_0. **Take ~900 tok/s (X), range 800–1000.**

Now test the two-parameter model `wall = prefill_tokens/900 + output_tokens/30` against §4.10's four measured rows, which vary entry size and entity yield together — the only place in the PRD where per-entry wall time is measured at several sizes:

| §4.10 row (M-Tome) | Entities | Wall | Prefill tok (entry + 1,215) | Prefill s @900 | Residual = decode s | Output tok @30 t/s | **Output tok per entity** |
|---|---|---|---|---|---|---|---|
| 40 entries × ~113 tok | 46 / 40 = 1.15 | 133/40 = 3.33 s | 1,328 | 1.48 | 1.85 | 55 | **48** |
| 10 entries × ~450 tok | 3.60 | 93/10 = 9.30 s | 1,665 | 1.85 | 7.45 | 224 | **62** |
| 4 entries × ~1,130 tok | 10.25 | 92/4 = 23.0 s | 2,345 | 2.61 | 20.4 | 612 | **60** |
| 1 entry × 4,525 tok | 18.00 | 42.0 s | 5,740 | 6.38 | 35.6 | 1,068 | **59** |

**The last column is the test, and it passes.** A two-parameter model with no free fitting recovers a per-entity output cost that is constant at **~59 output tokens per extracted Entity** across a 40× range of entry sizes and a 16× range of entity yields. (The 48 on the smallest row is the expected artifact of per-call fixed overhead being amortised over 1.15 entities.) A JSON object carrying a natural key, a type, a summary and a confidence is about that size. **The model is sound.**

Applying it to the §4.4 baseline entry:

```
18.0 s = 6,661 / 900  +  X / 30
       = 7.4 s prefill  +  10.6 s decode
                        ⇒ X ≈ 318 output tokens ≈ 5.4 Entities
```

**Which is the decomposition this whole section exists to produce:**

> **18 s ≈ 7.4 s prefill (41 %) + 10.6 s decode (59 %).** (**X**, on M-Tome and M-3P inputs.)

### 7.4 A structural point that falls out for free, and it is not small

§7.7's iGPU paragraph asserts that *"a larger context makes prefill dominant."* At Tome's actual sizes on the Fedora box, **it is not dominant — it is the minority term, 41 %.** The dominant cost is generating the extracted JSON, and that is bandwidth-bound.

This matters because it means the PRD's cost model is, on the current hardware, **mostly a decode cost**, i.e. mostly proportional to *how many Entities an entry yields*, not to how long the entry is. That reframes several things in the PRD's own terms:

- **§4.10's granularity result gets a cost explanation the PRD does not give it.** The 40-entries-of-113-tokens run costs 133 s and yields 46 Entities; the 1-entry-of-4,525-tokens run costs 42 s and yields 18. The finer split is *3.2× more expensive in wall time* and it is expensive **because it succeeds** — it emits 2.6× the Entities and the emitting is the cost. That is a much better-behaved trade-off than "fine-grained capture is slow", and it is worth knowing before anyone optimises the wrong term.
- **On the M4 Pro this inverts.** Prefill goes from 41 % to **66–70 %** of the per-entry cost (§8.2). The pipeline changes from decode-dominated to prefill-dominated, which means the *sensitivities* change:
  - **§4.9's name-precedence rule says its price is *"Costs only prefill; **owes no full run**"*.** That sentence prices a change in the cheap half. On the M4 Pro, "costs only prefill" is the expensive half. The conclusion (no full run owed) is unaffected; the cost framing is now wrong.
  - **§4.4's 3,000-token prompt budget** is 2.5× the measured 1,215. Spending that headroom costs 1,785 extra prefill tokens per entry — 2.0 s on the Fedora box, **8.1 s on the M4 Pro** (**X**). Across a 10k full run that is **22 hours** of difference from prompt growth alone.
  - **§4.4's flat 500-token `context` allowance**, chosen because *"a constant that is always high cannot be wrong"*, is charged against the expensive term now. The reasoning still holds — a cliff is still worse than a slope — but the constant is no longer free.
  - **§4.4's runaway-generation failure gets relatively *better*.** The unbounded case (17,957 output tokens) would cost ~889 s of decode on the M4 Pro versus 602 s on the desktop — a 1.5× worsening against a 2.5× worsening for the ordinary case. Bounding `num_predict` at 1,500 remains correct and remains cheap.
  - **§4.10's mitigation — holding capture at ~2048 tokens — becomes worth more**, because it caps the term that got expensive. §12.2's "the number survived, the reason changed" would gain a third reason.

---

## 8. The re-cost — hypothesis 2, the consequential one

**Hypothesis 2 as stated: "throughput gets worse even though capacity improves; the M4 Pro is believed roughly half the bandwidth, with less raw compute; re-cost the 18 s and 50 h figures." Confirmed on bandwidth, confirmed and then some on compute, and MLX does not rescue it.**

### 8.1 Establishing the M4 Pro's rates for a dense 14 B at 4-bit

Four independent routes. They are set out separately because the fact that they **converge** is the argument; any one of them alone would be weak.

**Route A — llama.cpp Metal, measured, scaled by parameters.**
[Discussion #4167](https://github.com/ggml-org/llama.cpp/discussions/4167) (**M-3P**), M4 Pro 20-core GPU, llama 7B Q4_0: **pp512 439.78 t/s, tg128 50.74 t/s.**
- Prefill for 14.8 B: `439.78 × 7/14.8 = 208 t/s`
- Decode: `50.74 t/s × 3.83 GB = 194 GB/s effective` = **71 % of 273 GB/s peak**. For 9.0 GB of Q4_K_M weights plus ~0.55 GiB of `q8_0` KV at a ~6.7k context: `194 / 9.6 = ` **20.2 t/s**

**Route B — MLX, Apple's own benchmark, scaled by parameters and GPU cores.**
`mlx-lm`'s `BENCHMARKS.md` (**D/M-3P**, Apple's repository), 64 GB M4 Max, `Qwen3-4B-Instruct-2507` q4: **prompt(2048) 1622.27 t/s, generation(128) 134.52 t/s, memory 3.35 GB.**
- Which M4 Max? `134.52 × 3.35 = 451 GB/s effective`, which **exceeds** the 410 GB/s 32-core part, so it must be the **546 GB/s 40-core** part (**X**, by elimination) — at 82.5 % of peak.
- Prefill for 14.8 B on that chip: `1622.27 × 4.0/14.8 = 438 t/s`; scaled to the M4 Pro's 20 of 40 GPU cores: **219 t/s**
- Decode on the M4 Pro: `0.825 × 273 = 225 GB/s effective`; for `Qwen3-14B-MLX-4bit` (~8.3 GB weights + ~1.0 GiB f16 KV at ~6.7k): `225 / 9.4 = ` **24.0 t/s**

**Route C — Apple's M4-vs-M5 research post, on exactly this model.**
Apple benchmarked `Qwen3-14B-MLX-4bit` at a **4096-token prompt** on a base M4 and a base M5 (10-core GPUs, 120 and 153 GB/s), reporting **TTFT speedup 4.06×** and **"the M5 pushes the time-to-first-token generation under 10 seconds for a dense 14B architecture"** (**D/M-3P**). Working backwards: if M5 TTFT is 6–9.5 s, base-M4 TTFT is 24.4–38.6 s, i.e. **106–168 t/s prefill on a 10-core M4**. Doubling for the M4 Pro's 20 cores: **212–336 t/s.**

**Route D — the reported MLX advantage, correctly scoped.**
The widely-cited 3× MLX-over-llama.cpp figures — 130 vs 43 tok/s on an M4 Pro; 130 vs 43.5 on an M4 Max — are all **MoE models** (`Qwen3-Coder-30B-A3B`, `Qwen3.5-35B-A3B`), where llama.cpp's expert-routing kernels are the known weak point. Ollama's own MLX announcement benchmarks the same class. The same secondary write-up that reports those numbers also records a case where **GGUF beat MLX** (M1 Max, ~650-token prompt: 20 vs 13 effective tok/s) and estimates the raw engine gap at "1.4–1.8×" once Ollama's Go wrapper overhead is separated out ([yage.ai, 2026-03-31](https://yage.ai/share/mlx-apple-silicon-en-20260331.html) — **weak evidence, a blog aggregating Reddit and GitHub threads; cited because it is the only place that scopes the claim rather than repeating it**).

**Convergence.** Routes A, B and C put prefill for a dense 14 B 4-bit on a 20-core M4 Pro at **208, 219 and 212–336 tok/s** respectively — from three different runtimes, three different base measurements, and three different scaling arguments. Take **~220 tok/s (range 190–280)**. Decode: **20.2 (GGUF) to 24.0 (MLX) tok/s.**

**And the MLX-versus-GGUF gap on this workload:**

| | GGUF/Metal | MLX | Gap |
|---|---|---|---|
| Prefill, dense 14 B 4-bit, M4 Pro 20-core | ~208 t/s | ~219 t/s | **~5 %, i.e. indistinguishable within the error bars of both derivations** |
| Decode | ~20.2 t/s | ~24.0 t/s | **~19 %** |

**Two honesty notes on that 19 %.** First, part of it is not kernel quality at all: MLX's q4 is a *smaller artifact* than GGUF's Q4_K_M (~8.3 GB vs ~9.0 GB weights for the same model). On a bandwidth-bound operation a smaller model is a faster model, and it is also a slightly *worse* model — `mlx-lm`'s own benchmark table shows MMLU-Pro dropping monotonically with bit-width, and Tome's whole extraction-quality argument (§4.10, §13.1) is quality-sensitive. Second, this gap is **already available inside Ollama**, because Ollama on Apple silicon is MLX-backed (§4). So it is not a reason to change runtimes.

### 8.2 The re-cost

Applying §7.3's decomposition (6,661 prefill tokens, ~318 output tokens) at each rate:

| Path | Prefill rate | Prefill s | Decode rate | Decode s | **Per entry** | **× PRD** | Prefill share |
|---|---|---|---|---|---|---|---|
| **Fedora + ROCm + Ollama** | ~900 t/s (**X**) | 7.4 | 30 t/s (**M-Tome-derived**) | 10.6 | **18.0 s** | 1.00× | 41 % |
| **Mac, MLX, 20-core** | ~220 t/s | 30.3 | 24.0 t/s | 13.3 | **43.6 s** | **2.41×** | 69 % |
| **Mac, Ollama/GGUF, 20-core** | ~208 t/s | 32.0 | 20.2 t/s | 15.8 | **47.8 s** | **2.65×** | 67 % |
| **Mac, Ollama/GGUF, 16-core** | ~172 t/s | 38.7 | 20.2 t/s | 15.8 | **54.5 s** | **3.02×** | 71 % |

**Central estimate: 2.4–3.0×, call it 2.6×.**

Propagated to every figure the PRD states:

| PRD figure | § | Fedora | **M4 Pro (range)** | **M4 Pro (central)** |
|---|---|---|---|---|
| One extraction call | 1.5 | 18 s | 44–55 s | **~47 s** |
| Full run, 1k entries | 1.5, 4.1 | ~5 h | 12–15 h | **~13 h** |
| Full run, 5k entries | 1.5, 4.1 | ~25 h | 60–76 h | **~65 h** |
| Full run, 10k entries | 1.5, 4.1, 3.7 | **~50 h** | **121–151 h** | **~131 h ≈ 5.5 days** |
| Full run "reaching ~36 h within a year" | 1.5 | ~36 h | 87–109 h | **~94 h ≈ 3.9 days** |
| Bounded worst case per entry (`num_predict` 1500) | 4.4 | ~54 s | 90–98 s | **~94 s** |
| `--reembed`, 10k | 4.1, 3.7 | ~6 min | 15–30 min | **~24 min** |
| Daily incremental at 20 entries/day | 1.5, 4.8 | ~6 min | 15–18 min | **~16 min** |

Three of these deserve separate comment.

**The 10k full run.** ~50 h is already the number §1.5 flags as *"easy to forget"* and §4.1 uses to justify refusing reads during a rebuild. At **~5.5 days** it stops being "an expensive weekend operation" and becomes an operation with no natural window on a laptop at all. The user cannot close the lid, cannot unplug, cannot take the machine anywhere, for the better part of a week. Agent 3 owns the mechanism; the *magnitude* is this section's finding.

**The 500:1 remedy ratio survives.** §3.7's itemised-epoch design rests on the asymmetry between a full run (~50 h) and a `--reembed` (~6 min). At ~131 h versus ~24 min the ratio is ~330:1 — narrower, still overwhelming. **The argument survives unchanged.** Good: the epoch design does not need re-deciding on cost grounds.

**The daily incremental is fine, and that is the trap.** ~16 minutes a day spread across 96 timer firings is invisible in aggregate, which means the M4 Pro will *feel* fine in normal operation and will only reveal the problem the first time a full run is triggered — after a prompt edit, a model swap, or a type change, all of which §4.1 says happen "manually and rarely". **The cost is concentrated in exactly the operation nobody rehearses.**

### 8.3 What is not in these numbers

Stated so nobody reads the table as a prediction of wall-clock:

- **No thermal derating.** §12. Sustained multi-day GPU load in a laptop chassis will not hold peak rates, and the derate is not knowable from documentation.
- **No contention.** These assume an idle machine, which §7.7's *"the machine is assumed not in use during enrichment"* assumes and a laptop violates.
- **No sleep, no lid closes, no unplugging.** Agent 3.
- **Prompt-prefix caching is not credited.** Tome's extraction prompt is a **fixed 1,215-token prefix on every call** (§4.9: identity is the hash of the rendered text). Both llama.cpp/Ollama and oMLX reuse a cached common prefix across requests, so in practice ~1,215 of the 6,661 prefill tokens should be free after the first entry — worth ~5.5 s per entry on the Mac, ~12 % of the per-entry cost. It applies on **both** platforms, so the *ratio* is unchanged; it improves the absolute figure on both sides. oMLX's differentiator here is that its cold tier persists prefixes to SSD across restarts, which is worth little for a sequential batch job. **Not credited above because I have not verified either runtime actually retains the prefix across the runner's request pattern — that is a §14 item, and if it works it is the cheapest available win.**
- **`num_predict` bounding is assumed in effect** (§4.4).

### 8.4 The embedding path, separately — it survives

Everything above is about generation. The embed path behaves differently and comes out fine:

- **§4.2's phase-1 batching:** measured at **105 ms/entry singly, 37 ms at batch 50** (**M-Tome**). Embedding is a single encoder forward — prefill-shaped, therefore compute-bound, therefore hit by the ~4× prefill ratio. **Estimate ~150 ms/entry at batch 50 on the M4 Pro** (**X**). Phase 1 over 10k rows goes from ~6 min to ~25 min. Irrelevant against a 131 h full run.
- **§4.5's 5-second inline capture budget.** A maximum-size entry is 2,048 bge-m3 tokens through a 568 M-parameter encoder: `2 × 0.568e9 × 2048 ≈ 2.3 TFLOP` of dense matmul (**X**). At a plausible 4–5 achieved TFLOPS on a 20-core M4 Pro that is **~0.5–0.8 s**, plus attention and tokenisation. **Comfortably inside 5 s — but the margin falls from roughly 25× to roughly 5×.** §13.3 already lists *"`bge-m3` embed latency against the 5 s capture budget"* as never measured. **On this target that row gets more urgent, not less**, and it moves from "should measure eventually" to "measure before committing".

---

## 9. §6.4 audited — the embedding model and call configuration

§6.4 carries three obligations on every `/api/embed` call. This is where an MLX path is most likely to break, so it was checked hardest.

| §6.4 obligation | Why it exists | Mac + Ollama/GGUF | Mac + MLX (oMLX) |
|---|---|---|---|
| **`truncate: false`** — *"the single highest-value line in the whole configuration"*; the default silently returns a valid-looking 1024-dim vector for the opening ~8 % of a 135,000-character input | Silent, undetectable corruption | **Survives unchanged.** Same daemon, same API field | **Survives with a native substitute, and with the identical trap.** oMLX's `/v1/embeddings` request model declares `truncation: bool = True` and `max_length: Optional[int] = None` (**D**, `omlx/api/embedding_models.py`), threaded down to `EmbeddingEngine.embed(..., truncation: bool = True)` (**D**, `omlx/engine/embedding.py`). So the line becomes `"truncation": false` — **and the dangerous default is dangerous in exactly the same way.** §6.4's warning ports verbatim; only the spelling changes |
| **`options.num_batch: 8192`** — because Ollama's embed path is gated by `min(num_ctx, GGUF context_length, num_batch)` and *"the default 2048 batch is what binds"*; costs 276 MB | An Ollama engine artifact sitting beside a `TODO` in its source | **Survives unchanged** — same engine, same gate. §6.4's instruction to *"re-run the ceiling probe after any Ollama upgrade"* is now **more** important, because the MLX-backed engine on Apple silicon is a different code path from the one the probe was run against | **Dissolves — and is replaced by a different, subtler hazard.** There is no batch gate. But oMLX resolves the sequence limit from model metadata, with `_DEFAULT_EMBEDDING_MAX_LENGTH = 512` as the **fallback when it cannot find one** (**D**, `omlx/models/embedding.py`). For `bge-m3` it should read `model_max_length: 8192` from `tokenizer_config.json` or `max_position_embeddings: 8194` from `config.json` (**D**, both fetched from `BAAI/bge-m3`) — **note those two disagree, and 8194 is XLM-RoBERTa's padding-offset artifact, not a usable sequence length.** If oMLX resolves 8194 and passes it as `max_length`, tokenisation at the limit overruns the position table. If it finds neither, the window silently becomes **512** — a *worse* silent truncation than the 2048 §6.4 was written against. **The class of failure §6.4 exists to prevent is present on both runtimes, in a different place.** §14 |
| **Prepend nothing** — *"an explicit rule, not an omission"*; a generic instruction costs `bge-m3` 5.95 nDCG@10 | Model-card fact | **Survives unchanged** on both | **Survives unchanged** — a property of the model, not the runtime |

**Model availability — the weak point, checked hardest, and it holds.** Querying the HuggingFace API on 2026-07-26 (**D**):

| Model | MLX conversions available | Downloads |
|---|---|---|
| `bge-m3` (the incumbent) | `mlx-community/bge-m3-mlx-fp16`, `-8bit`, `-6bit`, `-4bit` | 8,306 / 1,215 / 156 / 562 |
| `qwen3:14b` | `mlx-community/Qwen3-14B-4bit`, `-8bit`, `-6bit`, `-3bit`, `-bf16`, `-4bit-AWQ`, `-4bit-DWQ-053125` | 7,656 for the 4-bit |

**Both specified models have credible, actively-downloaded MLX conversions, and oMLX names BGE-M3 in its supported-embedding list explicitly.** The feared outcome — a split runtime, MLX for generation and something else for embeddings — **does not materialise on the oMLX path.** It does materialise on an mlx-lm path, which is one of the reasons mlx-lm is not a serious option (§3).

**Three residual risks on the MLX embedding path, all real:**

1. **Pooling.** §13.3 already lists *"Ollama's per-model pooling in GGUF conversion — unverified; `bge-m3` declares CLS, matching its card."* On MLX the pooling comes from a different conversion pipeline. oMLX's wrapper prefers `text_embeds`, then `pooler_output`, then mean-pools `last_hidden_state` (**D**, `omlx/models/embedding.py`). **`bge-m3` is CLS-pooled.** If the MLX conversion does not carry a pooler and oMLX mean-pools instead, the vectors are *valid* and *wrong* — cosine-comparable to nothing the PRD measured. This is the same shape of failure as the truncation trap: silent, plausible output. **A one-command check settles it (§14).**
2. **Re-embedding is mandatory, not optional.** Any move from `bge-m3` GGUF to `bge-m3` MLX-fp16 is a different artifact producing different vectors. §3.7 is explicit that the embedding axis makes vectors **incoherent** rather than stale, because *"cosine across model versions is meaningless and exact search leaves no fuzz to hide it."* The remedy exists and is cheap (`--reembed`, ~24 min at 10k on the M4 Pro), but **it is not free and it must be done deliberately.**
3. **§6.4's whole comparison would have to be re-run to hold its own standard.** The six-way model comparison (`embeddinggemma`'s +0.069 nDCG@10, `qwen3-embedding:0.6b`'s elimination at matched fp16, the +0.0202 truncation control) was measured against **Ollama GGUF artifacts**. Under MLX conversions at different precisions the numbers are not automatically transferable. This does not invalidate the *choice* — `bge-m3` was retained on being the only candidate that can serve both layers, an architectural fact — but the margins are no longer measured facts on the new runtime.

---

## 10. Hypothesis 4 — does a larger enrichment model now fit?

**Confirmed on capacity, killed on economics. Reported as a finding; no proposal is made, and §4's extraction-quality reasoning is not reopened here.**

**Capacity, first — it does fit.** With ~35.5 GiB usable:

| Candidate | 4-bit weights | Decode on M4 Pro (**X**, at 225 GB/s effective) | Prefill (**X**) | Per entry (**X**) | 10k full run |
|---|---|---|---|---|---|
| `qwen3:14b` (incumbent) | ~8.3–9.0 GB | 20–24 t/s | ~220 t/s | ~44–55 s | **121–151 h** |
| Qwen3-32B class | ~18–20 GB | ~11 t/s | ~100 t/s | ~96 s | **~267 h ≈ 11 days** |
| Qwen3-30B-A3B (MoE) | ~18.2 GB | ~60–110 t/s | ~800 t/s | ~14 s | ~39 h |

Note the third row: `mlx-lm`'s own benchmark measures `Qwen3-30B-A3B-Instruct-2507` q4 at **1753.90 t/s prompt / 113.33 t/s generation on an M4 Max**, versus `Qwen3-4B` q4's 1622/134 (**M-3P**, Apple's repository). A 3 B-active MoE is *cheaper per token than a 4 B dense model* while holding 30 B of parameters. **If a larger model were ever pursued on this hardware, the MoE direction is the only one where the arithmetic is not absurd** — a 30 B-A3B would be roughly break-even with the incumbent on speed at ~18 GB resident, which fits comfortably.

**Why this is still a finding and not a proposal:**

1. **A dense 32 B is unambiguously a bad trade here.** ~11 days for a full run on a laptop. Not close.
2. **The quality problem a bigger model would be bought to fix may not be a model-size problem.** §4.10's measured finding is that **Decisions do not scale at all** — 7 decision-shaped subjects across six entry sizes yielded `1, 1, 1, 1, 1, 1`, *"including the run that extracted 42 Entities"*. That is a **behavioural** failure of one-pass extraction over a long input, not a capability ceiling. §13.1 already names the suspected fix as *"a per-type or two-stage pass"*. **Nothing establishes that a larger model changes the `1,1,1,1,1,1` row**, and it is the row that matters most — §4.10 says plainly that *"the analytical content a memory-keeper exists for is exactly what is lost."*
3. **And that suspected fix gets *more* expensive on this target, not less.** A per-type pass over seven Entity Types, or a two-stage extract-then-merge pass, multiplies the call count — and each call now costs 2.6×. A seven-way per-type pass at ~47 s a call is ~5.5 minutes per entry and a **thousand-hour** full run. **This is the finding with the longest reach in this document:** the M4 Pro target does not merely slow Tome down, it **prices the fix to §13.1's one open question out of reach**, and §13.1 is explicitly the question the project intends to answer with real data after 90 days. A per-type pass on the Fedora box is expensive; on the M4 Pro it is not a thing that can be run.
4. **The other direction is now the interesting one.** If throughput is the binding constraint, the live question a Mac target raises is not *"can we afford a bigger model"* but *"is a smaller model good enough"* — which is a quality question §4.10 and §13.1 already own and which this spike is explicitly not allowed to decide.

**This does reopen §4's extraction-quality reasoning, exactly as the brief predicted — but from the opposite side.** Not "capacity is free, take a bigger model", but "throughput is scarce, and the roadmapped quality fix is what it makes unaffordable."

---

## 11. Two findings that reach beyond this section

### 11.1 Reproducibility may become reachable — and the argument is about runtime, not hardware

§3.7 states the position in the strongest available terms:

> *"**Reproducibility is unreachable, not merely expensive, and this is the fact that settles it.** Ollama refuses digest-addressed models — `{"model":"bge-m3@sha256:…"}` returns `invalid model name`, measured on this machine. `latest` is a mutable pointer, and Ollama prunes unreferenced blobs at server start, so once upstream republishes, the artifact that embedded the first 500 entries is gone from both the registry and the disk."*

**The pruning half is corroborated in Ollama's own source** (**D**): `server/routes.go` calls `PruneLayers()` on the server-start path, guarded only by a manifest-corruption check. So the PRD's measurement is not an artifact of its environment.

**But every clause in that sentence is a property of Ollama's registry and blob store, not of local inference.** On a HuggingFace-sourced MLX path, each clause fails to hold:

| §3.7's clause | On an MLX/HF path | Grade |
|---|---|---|
| *"Ollama refuses digest-addressed models"* | `hf_hub_download` and `snapshot_download` both take **`revision` — "An optional Git revision id which can be a branch name, a tag, or a **commit hash**"** | **D**, [huggingface_hub file_download reference](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download) |
| *"`latest` is a mutable pointer"* | A commit hash is not. And `HfFileMetadata` returns `commit_hash` for any URL, so the exact revision in use is always recoverable | **D** |
| *"Ollama prunes unreferenced blobs at server start"* | The HF cache is `blobs/` (content-addressed by git-sha1 or sha256) + `snapshots/<commit_hash>/` of symlinks + `refs/`. **Nothing in the documented cache behaviour prunes anything automatically** — deletion is an explicit operator action via the separate cache-management CLI | **D** |
| *"gone from both the registry and the disk"* | oMLX serves from a plain `--model-dir` of ordinary directories and **does not garbage-collect them**. Its downloader calls `snapshot_download` into `model_dir/<org>/<repo>` — and, notably, **passes no `revision`** (**D**, no `revision` occurrence in `omlx/admin/hf_downloader.py`), so the *convenience* path takes the branch tip. Tome would bypass it: `snapshot_download(repo_id, revision="<sha>", local_dir=...)` and point `--model-dir` at the result | **D** |

**What this would buy, concretely, in §3.7's own vocabulary.** §3.7's epoch records *"Enrichment model tag + digest"* and says *"Recording the digest buys **detection and honest labelling**, at any budget."* On a pinned-HF path the epoch could instead record the **commit hash of a revision that still exists and can be re-downloaded**, or — better, and available with no network at all — **a hash of the actual `safetensors` files on disk**, which are ordinary files the operator owns. The epoch would then move from *attribution* to *attribution plus a re-derivation path*, which is the thing §3.7 says is out of reach.

**Four cautions, because this is the finding most likely to be overstated:**

1. **It does not make derivation deterministic.** §3.7's *"the non-determinism is the feature: a better model should produce better Entities, not identical ones"* is untouched, and so is `temperature: 0` not implying bitwise reproducibility across kernels or runtime versions. What becomes reachable is **the same weights**, not the same output.
2. **HuggingFace repositories can be deleted, gated or rewritten upstream.** Pinning a SHA guarantees the *local copy* survives and is identifiable; it does not guarantee it is re-fetchable in five years. The durable half is "the artifact is an ordinary file you own and can back up" — which is genuinely different from a blob store that prunes.
3. **It costs the convenience path.** `ollama pull` becomes a scripted `snapshot_download` with an explicit revision, and the operator has to know the SHA. §3.7's *"the `ollama pull` row is the one a human fires **without meaning to**"* becomes harder to fire accidentally, which is the point, at the cost of an ergonomic regression.
4. **This is an argument about runtime choice, not about hardware.** Nothing in it requires a Mac. **The same argument applies to the Fedora box today**, where a llama.cpp-plus-pinned-GGUF path, or an Ollama-with-locally-imported-Modelfile path, could reach much of the same place. **If the spike produces one finding worth keeping regardless of the macOS verdict, this is it** — and it should be sized as its own ticket rather than being folded into a host decision.

### 11.2 The Ollama version field in the epoch

§3.7 records **"Ollama version — `ollama --version`"** as an epoch field, and §12.1 records version pinning as *"already satisfied structurally"* because Ollama is hand-installed with no unattended upgrade path. On macOS:

- Ollama's `.app` ships **in-app auto-update**; oMLX's ships **Sparkle-driven auto-update** and Homebrew's `brew upgrade` (**D**, both READMEs). **The structural pin is gone.** An epoch field whose value can change without a deliberate operator act is a different thing from one that cannot.
- And on the Ollama path the *engine* now changes underneath the version string: an Ollama release can move Apple-silicon inference from llama.cpp to MLX, which is a derivation-relevant change that `ollama --version` records only incidentally. §3.7's table says *"Ollama upgrade → **Yes**"* creates a new epoch, so the mechanism is right; but the **frequency and the accidental-ness** both go up.
- On an oMLX path the field has no meaning at all and would need replacing with something like `omlx --version` plus `mlx.__version__` plus `mlx_lm.__version__` — three moving parts where there was one.

**Verdict: §3.7's epoch survives structurally; two of its six fields need re-specifying on either Mac path.** That is Agent 3 / synthesis territory for the deployment half, but the *reason* is inference-side and belongs here.

### 11.3 The `ollama pull` egress exception, on an MLX path

Agent 2 owns §1.3. The inference-side facts it needs:

- §1.3's exception 4 and §7.7's unsealed-daemon ruling both hang on a **measured** fact: *"a bare `POST /api/pull` with no CLI in the picture returns `pulling manifest` followed by a registry error, so the fetch happens **inside `ollama.service`**"* — i.e. the daemon that receives every raw entry text is also the process with standing outbound access.
- **On an oMLX path that specific coupling persists in the same shape**: the model downloader is `omlx/admin/hf_downloader.py`, in-process, reachable from the admin HTTP surface (**D**). Same property, different hostname (`huggingface.co` instead of `registry.ollama.ai`).
- **On a Tome-driven pinned-download path it does not.** `snapshot_download(revision=sha)` runs in whatever process the operator invokes — a `make pull` target, outside the serving daemon — which is the bar §1.3 item 3 (`uv sync` reaching PyPI) clears and item 4 does not. **So a pinned-HF path would move the fourth egress exception from item-4 shape to item-3 shape**, which is a genuine improvement on #28's ruling rather than a restatement of it.
- **What does not improve:** macOS has no `IPAddressDeny=` equivalent, so the *capability* argument #28 rests on cannot be sealed on either Mac path even if someone wanted to. That is Agent 2's to state.
- **One new fact worth handing over:** oMLX's admin surface is an **HTTP web UI on port 8000 with model search and one-click download**, and API-key verification is skippable for localhost. That is a broader inbound and outbound surface than `ollama.service`, and it is a *feature* of the product rather than an accident.

---

## 12. Hypothesis 5 — thermals and battery

**Partially confirmed, and one of my starting beliefs was wrong.** This is the weakest-evidence section in the document and it is labelled accordingly: **almost nothing here is measurable from documentation, and almost all of it is cheaply measurable on the machine.**

### 12.1 What Apple documents

From [*About Power Modes on your Mac*](https://support.apple.com/en-us/101613) (published 2026-06-05, **D**):

- **High Power Mode** — *"allows the fans to run at higher speeds. The additional cooling capacity may allow the system to deliver higher performance in very intensive workloads."* Supported models include **"MacBook Pro (14-inch, 2024) with M4 Pro or Max"** and **"MacBook Pro (16-inch, 2024)"**.
  **This kills a belief I held going in** — High Power Mode is *not* 16-inch-Max-only; it is available on the 14-inch M4 Pro. Apple adds: *"For 14-inch MacBook Pro with M4 Pro and M5 Pro chip, the 96W USB-C Power Adapter is recommended for using high power mode while charging."*
- **Low Power Mode** — *"reduces energy use to increase battery life... also helps reduce fan noise... and allows reduced power consumption if your Mac is always left on."* Supported on MacBook Pro (14-inch and 16-inch, 2024).
- **Per-source modes** — *"You can set different energy modes for when your Mac is on battery or connected to the power adapter."* Default is **Automatic**.

**That last line is the operationally important one.** macOS already has a first-class, user-visible, per-power-source performance policy. **An enrichment run's performance profile is therefore partly a *user setting* on this target, not a property of the software** — which has no counterpart on the Fedora box, and which means §7.7's *"the settings above stand independently of that"* acquires an exception it cannot control.

### 12.2 What the specs imply about a multi-day run

| Fact | 14-inch | 16-inch | Source |
|---|---|---|---|
| Battery | **72.4 Wh** | **100 Wh** | **D** ([121553](https://support.apple.com/en-us/121553), [121554](https://support.apple.com/en-us/121554)) |
| Adapter (M4 Pro) | **70 W** included with 12-core CPU; **96 W** with 14-core CPU | **140 W** | **D** |
| Apple's note | 96 W *recommended* for High Power Mode while charging | — | **D** |

Sustained package power for an M4 Pro under continuous GPU inference is **not documented by Apple** and I found no primary measurement. Third-party reviews put M4 Pro sustained loads in the 40–60 W range, and report that the 14-inch supplements from the battery under heavy load even while plugged in (notebookcheck, MacRumors forums — **weak evidence, explicitly flagged**). Taking that at face value purely to size the problem (**A**):

- A **131-hour full run** at ~45 W of *additional* draw is **~5.9 kWh** of work, and is flatly impossible on battery: `72.4 Wh / 45 W ≈ 1.6 hours` before the machine is empty, and that ignores everything else running.
- On the **14-inch with the 70 W adapter**, sustained inference plus display plus the rest of the system plausibly exceeds the adapter, meaning the machine slowly drains **while plugged in**. Apple's own recommendation of the 96 W adapter for High Power Mode is a hint in that direction.
- **A full run is an AC-only, lid-open, don't-move-the-laptop, multi-day operation.** On the desktop it was "leave it overnight, twice."

### 12.3 What cannot be established from reading

- **The actual sustained-versus-peak derate for a multi-hour GPU load on an M4 Pro.** The llama-bench figures underpinning §8 are `pp512`/`tg128` runs lasting seconds. They are *peak* numbers. **The real full-run figure is the sustained figure, and the sustained figure is not in any source I found.** If the derate is 15 %, the 131 h becomes 154 h.
- **Whether Automatic mode throttles the GPU on battery** for a sustained compute load. Apple documents that separate modes exist; it does not document what Automatic does under sustained GPU load on battery.
- **Whether Low Power Mode is actually *better* for this workload.** There is a plausible case — a bandwidth-bound decode phase may lose little to a lower clock while gaining a lot in sustainability and fan noise — and it is a two-hour experiment, not a research question.
- **Whether the 14-inch throttles where the 16-inch does not** on this specific workload. Reviews say the M4 Pro fits the 14-inch chassis comfortably (unlike M4/M5 Max), but that is a reviewer's judgement about bursty benchmarks, not a measurement of a five-day run.

**Verdict on hypothesis 5: confirmed that this is a real and new problem class, unresolved on magnitude.** Every question in §12.3 is a §14 item.

---

## 13. The runtime recommendation

**Recommendation: if the macOS target is pursued, use Ollama, and pursue a pinned-artifact path as a separate question on its own merits.**

The reasoning, in order:

1. **The performance case for switching has largely evaporated.** Ollama on Apple silicon is MLX-backed as of 2026-03-30 (**D**). The MLX advantage on a dense 14 B at 4-bit is ~0 % prefill and ~19 % decode (§8.1), and Ollama already captures it. Switching runtimes to chase that is spending a large amount of design surface for a fraction of a factor that does not change any conclusion in §8.2.
2. **Keeping Ollama preserves a large amount of measured work.** §6.4's six-way embedder comparison, §4.4's five measured budget quantities, §4.10's granularity table, the `num_batch` ceiling probe, the tokenizer ratio — all measured against Ollama artifacts. Switching runtime does not invalidate the *decisions*, but it does invalidate the *margins*, and re-measuring them is real work the spike has not costed.
3. **oMLX is a better fit to §7.7's intent and a worse fit to Tome's risk posture.** It is genuinely impressive — model pinning, per-model TTL, a memory enforcer, continuous batching, embeddings *and* reranking, and BGE-M3 named explicitly. But it is **five months old, at v0.5.3, with 741 open issues**, and it would be the sole process standing between a memory-keeper and its only write path. The PRD's own §7.7 declined a *two-line* change on proportionality grounds; adopting a six-month-old server is a much larger bet than that.
4. **The reproducibility argument is real and should be separated from the Mac question.** §11.1 is the finding worth keeping. It is an argument about **how model artifacts are managed**, and it applies to the Fedora box unchanged. Bundling it into a host decision would be a category error, and would make a good idea contingent on a bad one.
5. **mlx-lm alone is not viable** — no embeddings endpoint (**D**), and Tome embeds on the capture hot path.

**What would change my mind, stated precisely so it is falsifiable:**

- **A measured `llama-bench` versus `mlx_lm.benchmark` head-to-head on the actual machine, on `Qwen3-14B` at 4-bit, at a ~6,700-token prompt, showing MLX more than ~40 % faster on prefill.** My derivation says ~5 %, from three converging routes, and it is the single number I would most like to be wrong about. Above 40 % the full-run figure moves enough to be worth re-arguing.
- **Evidence that Ollama's MLX path leaves "preview" and its Apple-silicon prefill lands materially below oMLX's** — in which case the choice becomes "wait" rather than "switch".
- **A finding that Ollama's Apple-silicon MLX engine cannot honour `truncate: false` or the `num_batch` ceiling** the way the llama.cpp path does. §6.4's highest-value line depends on it, and it is a different code path from the one it was measured against. This would move Ollama-on-Mac from "survives unchanged" to "breaks", and would force the oMLX path on correctness grounds.
- **oMLX reaching a 1.0 with a materially lower open-issue count**, at which point point 3 weakens considerably.

---

## 14. Cheaply measurable on the actual MacBook

Ordered by value per minute. Several of these are single commands, and collectively they would settle more of this document than another day of reading.

**Tier 1 — settles the headline (30 minutes)**

1. **`llama-bench` on `qwen3:14b` Q4_K_M**, at `-p 6656 -n 320` to match §7.3's decomposition, not the default `pp512/tg128`. This directly measures the two rates §8 derives, on the real model, at the real shape. **Everything in §8.2 is downstream of this one command.**
2. **`mlx_lm.benchmark --model mlx-community/Qwen3-14B-4bit -p 6656 -g 320`.** The same measurement on the MLX path. The pair of them settles §13's falsifiable condition.
3. **`system_profiler SPHardwareDataType` / `sysctl hw.model`** — establish **16-core or 20-core GPU**, and 14-inch or 16-inch. A ~20 % swing on the full-run estimate and the whole of §12.2.

**Tier 2 — settles the capacity story (10 minutes)**

4. **Read the startup log line** — `ggml_metal_init: recommendedMaxWorkingSetSize = ... MB`, or Ollama's `gpu memory ... available=/free=/minimum=/overhead=` line from `server/sched.go`. Confirms or refutes the ~36 GiB figure and the 25 %-reserve reverse-engineering in one line, with no arithmetic.
5. **`sysctl iogpu.wired_limit_mb`** — confirm the key exists on this macOS version and reads 0.
6. **Load both models at `num_ctx: 16384` with an f16 KV cache and read peak footprint.** Confirms §5.2's arithmetic and confirms the `q8_0` requirement really has dissolved.

**Tier 3 — settles §6.4, the correctness-critical section (30 minutes)**

7. **The truncation probe, re-run.** §6.4's finding came from a 135,000-character input returning a valid 1024-dim vector with `prompt_eval_count: 2048`. Re-run it against (a) Ollama's Apple-silicon MLX engine and (b) oMLX with `truncation: false`. **This is the highest-value line in the configuration and it is being carried onto a code path it was never measured against.**
8. **The `num_batch` ceiling probe**, per §6.4's own standing instruction to re-run it after any Ollama upgrade. The engine change is a much bigger event than an upgrade.
9. **oMLX's resolved `max_length` for `bge-m3`.** Embed a known 4,000-token input and read `total_tokens` back. Distinguishes 512 (the fallback disaster), 8192 (correct), and 8194 (the XLM-RoBERTa off-by-two).
10. **Pooling check.** Embed one short string through Ollama's `bge-m3` and through `mlx-community/bge-m3-mlx-fp16`, and compute the cosine between the two vectors. **Near 1.0 means the same pooling; anything else means the MLX conversion is a different model in the only sense that matters.** Also settles §13.3's long-standing "per-model pooling in GGUF conversion — unverified" row for the incumbent.
11. **`bge-m3` inline embed latency for a full 2,048-token entry**, single, not batched. §13.3 lists this as never measured on either machine; §8.4 estimates 0.5–0.8 s against a 5 s budget. It is a `curl` and a stopwatch.

**Tier 4 — settles §12, which reading cannot (a few hours, mostly unattended)**

12. **Sustained-throughput derate.** Run `llama-bench` in a loop for 60–90 minutes with `powermetrics` sampling, and compare minute 1 to minute 60. **This is the number missing from §8.3** and there is no substitute for measuring it.
13. **The same, on battery, in Automatic mode.** Then in Low Power Mode. Then in High Power Mode on AC. Four runs, one afternoon, and it produces the table §12 could not.
14. **Package power under sustained inference** (`powermetrics --samplers cpu_power,gpu_power`) — turns §12.2's battery and adapter arithmetic from assumption into measurement.

**Tier 5 — worth knowing, cheap**

15. **Whether the 1,215-token prompt prefix is actually cached across sequential requests** on each runtime — visible as a drop in `prompt_eval_count` or `prompt_eval_duration` on the second and subsequent calls. §8.3 declines to credit ~12 % of the per-entry cost for want of this.
16. **A real end-to-end run of 20 synthetic entries through the actual extraction prompt**, timed. This measures the thing §8 models, including the merge-call question §13.3 flags as unverified — *"a merging extraction may be two `qwen3` calls, not one"*. **If it is two calls, every figure in §8.2 is up to 2× low, on both platforms equally.** That row is unresolved by this document and is the largest single uncertainty in the cost model.

---

## 15. Verdicts

Per the spike's four-way scheme. Where the verdict differs by runtime path, both are given.

| PRD § | Subject | Mac + Ollama/GGUF-MLX | Mac + oMLX | Note |
|---|---|---|---|---|
| **§1.4** | The machine — measured facts | **Survives with a native substitute** | same | Every fact is replaced by a different fact. The GPU/VRAM/iGPU/firewalld rows are wholly rewritten; two new facts appear with no counterpart (battery, adapter). The *section* survives as a section |
| **§1.5** | Scale assumptions — 20 entries/day, ~18 s, ~5/25/50 h | **Survives with the numbers changed** — 2.4–3.0× on every wall-clock figure | same | Structure intact, magnitudes not. **The 50 h → ~131 h change is the spike's most consequential single finding** |
| **§6.4** | `truncate: false` | **Survives unchanged** — but re-probe on the MLX engine (§14.7) | **Survives with a native substitute** — `truncation: false`, same default trap | The obligation is runtime-independent; only the spelling and the code path change |
| **§6.4** | `options.num_batch: 8192` | **Survives unchanged** | **Dissolves** — replaced by a `max_length` resolution hazard with a 512 fallback | The gate is an Ollama artifact |
| **§6.4** | Prepend nothing | **Survives unchanged** | **Survives unchanged** | Property of the model |
| **§6.4** | The six-way model comparison | **Survives** | **Survives with margins unverified** | MLX conversions are different artifacts |
| **§6.5** | One embedder per layer — deferred | **Survives unchanged** | **Survives, with one of four grounds weakened** | *"two pinned models serialise on `NUM_PARALLEL=1`"* is no longer true under continuous batching. The architectural objection — the permanent doubling of the re-embed design — is untouched and remains the real reason |
| **§6.6** | Nothing is prioritised | **Survives, weakened** | **Dissolves** | Ollama still has no priority concept; oMLX has pinning, TTL and manual load/unload |
| **§7.7** | Co-residency, no swap | **Survives unchanged** | **Survives with a native substitute** | |
| **§7.7** | 13.12/15.98 GB measurement | **Dissolves** | **Dissolves** | ~32–37 % of ~35.5 GiB |
| **§7.7** | `q8_0` KV requirement | **Dissolves** (still available, no longer needed) | **Dissolves** (no equivalent knob) | |
| **§7.7** | Pinned embedder at `keep_alive=-1` | **Survives unchanged** | **Survives with a native substitute** | The eviction spiral becomes unreachable, but the pin still costs nothing |
| **§7.7** | Shortened keep-alive, explicit unload | **Survives, argument weakened** | **Survives with a native substitute** (per-model TTL) | |
| **§7.7** | `OLLAMA_GPU_OVERHEAD` ~1.5 GiB | **Dissolves** | **Dissolves** | |
| **§7.7** | Per-request `num_ctx` ~16k | **Survives unchanged** | **Breaks as written** — no `num_ctx`; §4.4's assertion needs an invented right-hand side | |
| **§7.7** | `OLLAMA_NUM_PARALLEL=1` | **Dissolves as a constraint, becomes a live choice** | **Dissolves** — continuous batching, default 8 | |
| **§7.7** | Loopback bind | Agent 2 | Agent 2 | Mechanically available on both |
| **§7.7** | Unsealed daemon / `IPAddressDeny=` | **Restated, not ported** (Agent 2) | **Restated, and the fetching process changes identity** (§11.3) | |
| **§7.7** | *"the machine is assumed not in use during enrichment"* | **Breaks** | **Breaks** | False on a laptop, and on unified memory the contention is for the same bandwidth and the same thermals |
| **§7.7** | No CPU/memory/IO limits, no idle-gating | **Breaks** — the premise it rests on is gone (Agent 3 owns the remedy) | same | |
| **§7.7** | iGPU ruled out on hard data | **Dissolves entirely** | **Dissolves entirely** | One GPU |
| **§4.1** | Three run modes, and their costs | **Survives with the numbers changed** | same | The 500:1 full-vs-reembed ratio survives at ~330:1 — §3.7's itemised epoch needs no re-deciding |
| **§4.2** | Two phases, batched embed | **Survives unchanged** | same | ~37 → ~150 ms/entry at batch 50; irrelevant at this scale |
| **§4.4** | Budgets and the pre-flight assertion | **Survives unchanged** | **Survives with a substitute right-hand side** | The arithmetic is tokenizer-side, not device-side. But the *price* of the 3,000-token budget and the 500-token allowance rises ~4× (§7.4) |
| **§4.5** | 5 s inline embed budget | **Survives** — margin falls from ~25× to ~5× | same | §13.3's unmeasured row gets more urgent |
| **§4.10** | Extraction recall limitation | **Survives unchanged, and its remedy becomes unaffordable** | same | The suspected per-type / two-stage fix costs 2.6× per call on a target where a single-pass full run already takes 5.5 days (§10) |
| **§13.3** | Rows relating to inference/VRAM/latency/Ollama | see §16 | see §16 | |

---

## 16. The §13.3 rows this section owns

| §13.3 row | Effect of the host change |
|---|---|
| ***"A merging extraction may be two `qwen3` calls, not one."* Recorded as unverified. **"This is the cost model that the ~18 s/entry and ~50 h figures rest on."*** | **Unchanged and now more expensive to be wrong about.** If it is two calls, every figure in §8.2 is up to 2× low — on both platforms, so the *ratio* holds, but ~131 h becomes ~260 h. §14.16 |
| **`bge-m3` embed latency against the 5 s capture budget — never measured** | **Escalates.** Margin falls from ~25× to ~5× (§8.4). Should move from "measure eventually" to "measure before committing" |
| **Ollama's per-model runner queues — reasoned from architecture, not measured** | **Partly dissolves.** On oMLX, continuous batching with 8 concurrent slots is the documented default, so the premise is replaced rather than verified. On Ollama-on-Mac the row stands, unchanged |
| **Ollama's per-model pooling in GGUF conversion — unverified; `bge-m3` declares CLS** | **Escalates and becomes cheaply checkable.** On any MLX path a *second* conversion pipeline enters, and oMLX's wrapper falls back to mean-pooling when it finds no pooler (**D**). §14.10 settles both the old row and the new one with one cosine |
| **The `num_batch` behaviour is undocumented and sits beside a `TODO` in Ollama's source — re-probe after any upgrade** | **Escalates on Ollama-on-Mac** (the Apple-silicon engine change is far larger than an upgrade); **dissolves on oMLX**, replaced by the `max_length`-resolution hazard in §9 |
| **Exact-vs-HNSW recall; the ANN tripwire's 150 ms p95** | **Unaffected by inference, but the tripwire's calibration is not.** §13.4 sets it at ~10× the assumed ~10–20 ms exact-scan cost. Exact scan is Postgres-side, not GPU-side, and Agent 5 owns Postgres — but note that the M4 Pro's CPU is *faster* than the Fedora box's for this, so the tripwire is likely to be conservative in the safe direction |
| **Claude Desktop's lack of native remote-MCP support — re-check before building** | Agent 2 |
| **`granite-embedding-english-r2` not in the Ollama library — worth re-checking** | **Changes character entirely.** *"Not in the Ollama library"* is not a constraint on a HuggingFace-sourced path. The near-miss §6.4 calls *"the strongest"* becomes available. **Reported as a finding; no proposal, and §6.4's decision is not reopened** |
| — *new row this spike would add* — | **The M4 Pro's sustained-versus-peak inference derate is unmeasured**, and every figure in §8.2 is a peak figure (§12.3) |
| — *new row this spike would add* — | **Whether prompt-prefix caching retains the 1,215-token extraction prompt across sequential runner requests** on either runtime is unverified, and it is worth ~12 % of the per-entry cost (§8.3) |

---

## 17. What I could not establish

Recorded so that nothing here is mistaken for a finding.

- **No number in this document was measured on an M4 Pro.** Every M4 Pro figure is third-party-measured on M4-family hardware and scaled, or derived. §14 exists to fix this.
- **The exact absolute TTFT figures behind Apple's 4.06× speedup** are in a figure image, not the page text. §8.1 route C therefore yields a range (106–168 t/s on a base M4), not a point.
- **The prefill rate for `qwen3:14b` Q4_K_M on the RX 6900 XT** is not measured by the PRD. §7.3 derives ~900 t/s from a third-party 7B measurement on the exact card and validates the resulting model against four independent PRD measurements — but it is a derivation, and if it is materially wrong the 41/59 prefill/decode split moves. The **decode** rate (~30 t/s) is much more solid, being nearly independent of the prefill assumption.
- **Sustained thermal derate, package power, and battery-mode throttling** for this workload: not documented, not measured, only bounded by weak third-party reviews (§12).
- **Whether the extraction is one `qwen3` call or two.** §13.3 already flags it. It is the largest single uncertainty in the cost model and it is settled by one timed run (§14.16).
- **The Ollama version discrepancy** between §1.4's "v0.32.1" and Ollama's blog numbering (§4). Nothing here depends on it; it should not be inherited unchecked, because §3.7 records it as an epoch field.
- **oMLX's real-world reliability.** 741 open issues is a number, not an assessment. I read its source and its README; I did not run it, and I did not read its issue tracker.
- **Whether Ollama's Apple-silicon MLX engine preserves `truncate: false` and the `num_batch` ceiling.** §6.4's two measured obligations are being carried onto a code path they were never measured against. §14.7 and §14.8.

---

## 18. Sources

**Primary — vendor documentation and source code**

- Apple, [MacBook Pro (14-inch, M4 Pro or M4 Max, 2024) — Tech Specs](https://support.apple.com/en-us/121553) — M4 Pro GPU core counts, 273 GB/s, 48 GB configurability, 72.4 Wh, 70/96 W adapters
- Apple, [MacBook Pro (16-inch, 2024) — Tech Specs](https://support.apple.com/en-us/121554) — 100 Wh, 140 W adapter
- Apple, [About Power Modes on your Mac](https://support.apple.com/en-us/101613) (published 2026-06-05) — Low/High Power Mode model lists, per-power-source Energy Mode
- Apple Machine Learning Research, [Exploring LLMs with MLX and the Neural Accelerators in the M5 GPU](https://machinelearning.apple.com/research/exploring-llms-mlx-m5) (2025-11-19) — `Qwen3-14B-MLX-4bit` at 9.16 GB, TTFT 4.06× / generation 1.19× M5-over-M4, and the compute-bound-prefill / bandwidth-bound-decode statement
- Apple, [`ml-explore/mlx-lm` `BENCHMARKS.md`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/BENCHMARKS.md) — Qwen3-4B and Qwen3-30B-A3B on 64 GB M4 Max, with MMLU-Pro alongside throughput
- Apple, [`ml-explore/mlx-lm` `mlx_lm/server.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/server.py) — the endpoint list, establishing no `/v1/embeddings`
- Apple Developer, [`recommendedMaxWorkingSetSize`](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize)
- ggml-org/llama.cpp, `ggml/src/ggml-metal/ggml-metal-device.m` and `ggml-metal.cpp` — `free`/`total` derived from `recommendedMaxWorkingSetSize` and `currentAllocatedSize`
- ollama/ollama, `server/sched.go`, `ml/device.go`, `envconfig/config.go`, `discover/gpu_darwin.go`, `discover/gpu_info_darwin.m`, `server/routes.go` — `GpuOverhead` application, Metal `MinimumMemory()` of 512 MiB, Metal flash-attention support, darwin memory discovery, `PruneLayers()` on the server-start path
- Ollama, [Ollama is now powered by MLX on Apple Silicon in preview](https://ollama.com/blog/mlx) (2026-03-30) and [Ollama's highest performance on Apple Silicon yet with MLX](https://ollama.com/blog/mlx-performance)
- jundot/omlx — `README.md`, `omlx/api/embedding_models.py`, `omlx/engine/embedding.py`, `omlx/models/embedding.py`, `omlx/admin/hf_downloader.py`; repository metadata read from the GitHub API on 2026-07-26
- HuggingFace, [`huggingface_hub` file-download reference](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download) — `revision` accepting a commit hash; the `blobs`/`refs`/`snapshots` cache layout
- HuggingFace model configs: `Qwen/Qwen3-14B/config.json` (40 layers, 8 KV heads, head_dim 128), `BAAI/bge-m3/config.json` (`max_position_embeddings: 8194`) and `tokenizer_config.json` (`model_max_length: 8192`)
- HuggingFace model listings for `mlx-community` (queried 2026-07-26): `bge-m3-mlx-fp16/8bit/6bit/4bit`, `Qwen3-14B-4bit` and variants

**Community measurements — named hardware, named builds, treated as M-3P**

- ggml-org/llama.cpp, [Discussion #4167 — Performance of llama.cpp on Apple Silicon M-series](https://github.com/ggml-org/llama.cpp/discussions/4167) — M4 Pro 16-core and 20-core, M4 base, M4 Max, M1 Max
- ggml-org/llama.cpp, [Discussion #15021 — Performance of llama.cpp on AMD ROCm (HIP)](https://github.com/ggml-org/llama.cpp/discussions/15021) — **RX 6900 XT, llama 7B Q4_0, pp512 1889.84, tg128 88.49**
- ggml-org/llama.cpp, [Discussion #2182 — Adjust VRAM/RAM split on Apple Silicon](https://github.com/ggml-org/llama.cpp/discussions/2182) — `iogpu.wired_limit_mb`; the 33.3 %/25 % reserve fractions are **reverse-engineered from a disassembly posted in-thread, not Apple documentation**

**Weak evidence, used only where nothing better exists and flagged at each use**

- [yage.ai, *MLX vs llama.cpp on Apple Silicon*](https://yage.ai/share/mlx-apple-silicon-en-20260331.html) (2026-03-31) — a blog aggregating Reddit and GitHub threads. Cited only because it is the one source that *scopes* the 3× MLX claim to MoE models and records a counter-case, rather than repeating the headline
- notebookcheck and MacRumors forum threads on M4 Pro sustained thermals — used only to bound §12, and identified as forum/review material at the point of use
- Several "Apple Silicon LLM benchmark" aggregator sites were consulted and **discarded**: one asserts 35–55 tok/s for a 14 B model on an M4 Pro, which is physically impossible at 273 GB/s for a ~9 GB model (the ceiling is ~30 tok/s). They are recorded here as a caution, not as evidence.

**Tome's own measurements**

- `PRD.md` §1.4, §1.5, §3.7, §4.1, §4.2, §4.4, §4.5, §4.10, §6.4, §6.5, §6.6, §7.7, §12.1, §12.2, §13.3, §13.4
