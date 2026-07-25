# Local LLM Serving Runtime & Models for Tome on ROCm (RX 6900 XT)

Research date: 2026-07-25. Target hardware: AMD Radeon RX 6900 XT (16GB VRAM, RDNA2, GPU target **gfx1030**), 64GB system RAM, Fedora Linux.

---

## Summary / Recommendation

- **Runtime: Ollama** (built on the llama.cpp/GGML engine). gfx1030 appears directly in Ollama's own supported-LLVM-target table ([docs.ollama.com/gpu](https://docs.ollama.com/gpu); [github.com/ollama/ollama docs/gpu.mdx](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx)), it gives a simple model-swapping API (`keep_alive`) that is a natural fit for a periodic batch job, and it needs no custom build step. **llama.cpp** directly is the fallback if finer control over HIP build flags is ever needed — it is the engine Ollama itself vendors, and gfx1030 is llama.cpp's own worked example for `-DGPU_TARGETS=` in its build docs ([docs/build.md](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/build.md)). **vLLM is not viable on this GPU** — neither vLLM's own docs nor AMD's ROCm docs list any RDNA2/gfx1030 device as a supported ROCm target for vLLM (see below); it targets Instinct (MI2xx/MI3xx) and newer Radeon/RDNA3-4 (RX 7000/9000) hardware only.
- **Embedding model:** `nomic-embed-text` (v1.5), 137M params, Apache-2.0, 768-dim (Matryoshka-truncatable), long-context (up to 8192 tokens per its own model card) — available directly from the Ollama library at ~274MB ([ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text), [huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)). `bge-m3` (BAAI, 567M params, MIT license, 1024-dim, 8192-token context, dense+sparse+multi-vector) is a strong alternative if multilingual/hybrid retrieval matters more than footprint ([ollama.com/library/bge-m3](https://ollama.com/library/bge-m3), [huggingface.co/BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)).
- **Enrichment/classification model:** `qwen3:14b` (Qwen3-14B dense, Apache-2.0, 14.8B params, 40 layers, 32K native / 128K YaRN context), Q4_K_M quantization ≈ 9.3GB download on Ollama ([ollama.com/library/qwen3:14b](https://ollama.com/library/qwen3:14b), [Qwen3 blog](https://qwenlm.github.io/blog/qwen3/)). It fits comfortably in 16GB, is Apache-2.0 licensed, and Qwen's own blog claims strong structured-output/tool-calling and instruction-following behavior appropriate for JSON entity extraction. **Important operational note:** disable "thinking mode" for this workload (see Risks) so the model emits clean JSON rather than a reasoning preamble.
- These two models never need to be resident at the same instant for a periodic batch enrichment job — see VRAM analysis below — so sequential (hot-swap) loading under Ollama is the right operating model, not a design compromise.

---

## Runtime comparison: Ollama vs llama.cpp vs vLLM on ROCm / gfx1030

### Ollama

- Ollama's official GPU docs state plainly: **"Ollama requires the AMD ROCm v7 driver on Linux"** and, for Windows, "Ollama requires an AMD ROCm v7 / HIP7-capable driver stack" ([docs.ollama.com/gpu](https://docs.ollama.com/gpu); mirrored in [github.com/ollama/ollama/blob/main/docs/gpu.mdx](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx)).
- Ollama's own LLVM-target support table (from `docs/gpu.mdx`) is:

  | LLVM Target | Example GPU |
  |---|---|
  | gfx908 | Radeon Instinct MI100 |
  | gfx90a | Radeon Instinct MI210/MI250 |
  | gfx942 | Radeon Instinct MI300X/MI300A |
  | gfx950 | Radeon Instinct MI350X |
  | **gfx1030** | **Radeon PRO V620** |
  | gfx1100 | Radeon PRO W7900 |
  | gfx1101 | Radeon PRO W7700 |
  | gfx1102 | Radeon RX 7600 |
  | gfx1150 | Ryzen AI 9 HX 375 |
  | gfx1151 | Ryzen AI Max+ 395 |
  | gfx1200 | Radeon RX 9070 |
  | gfx1201 | Radeon RX 9070 XT |

  (verbatim table from [github.com/ollama/ollama docs/gpu.mdx](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx))
- **gfx1030 is directly in this table.** The Radeon PRO V620 is a datacenter card, but it uses the exact same Navi 21 / gfx1030 silicon and ISA as the consumer RX 6800/6800 XT/6900 XT/6950 XT — Ollama (like llama.cpp under it) compiles/dispatches kernels by LLVM/gfx target string, not by marketing SKU, so a compiled `gfx1030` kernel runs on any gfx1030 device.
- Ollama also documents the escape hatch for GPUs whose *own* gfx string has no compiled kernel: **"you can force the system to try to use a similar LLVM target that is close"** via `HSA_OVERRIDE_GFX_VERSION` (x.y.z syntax), with per-device overrides like `HSA_OVERRIDE_GFX_VERSION_0=10.3.0` ([docs.ollama.com/gpu](https://docs.ollama.com/gpu)). This override is what's needed for chips like gfx1031/gfx1032/gfx1034 (RX 6700 XT / RX 6600 / RX 5xxx-adjacent parts) that lack their own compiled kernel and must masquerade as `10.3.0` (gfx1030). **The RX 6900 XT does not need this override** — its native gfx string already is gfx1030, which is directly in Ollama's supported table.

### llama.cpp

- llama.cpp's official build docs give the HIP/ROCm build command with `gfx1030` as the **worked example**, not merely a footnote:

  ```
  HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
      cmake -S . -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1030 -DCMAKE_BUILD_TYPE=Release \
      && cmake --build build --config Release -- -j 16
  ```
  ([docs/build.md, ggml-org/llama.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/build.md))
- The doc notes `GPU_TARGETS` is optional — omitting it builds for all GPUs detected on the system — and documents `HSA_OVERRIDE_GFX_VERSION` the same way as Ollama, giving "10.3.0 on RDNA2" and "11.0.0 on RDNA3" as the canonical override values for GPUs that need to borrow a neighboring target ([docs/build.md](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/build.md)).
- llama.cpp requires a self-managed build (install ROCm from the distro or AMD's ROCm Quick Start page, then `cmake`/`make`) whereas Ollama ships prebuilt ROCm binaries — this is the main practical tradeoff between the two for a Fedora desktop setup.
- AMD itself also publishes install/build docs for llama.cpp on ROCm directly ([rocm.docs.amd.com/projects/llama-cpp](https://rocm.docs.amd.com/projects/llama-cpp/en/docs-26.02/install/llama-cpp-install.html)), corroborating that llama.cpp is a first-class, AMD-documented ROCm workload.

### vLLM

- vLLM's own installation docs (`docs.vllm.ai`) state ROCm support requires **ROCm 6.2+** in general, with **prebuilt wheels only for ROCm 7.0 (`rocm700`) and ROCm 7.2.1 (`rocm721`)** ([docs.vllm.ai/en/latest/getting_started/installation/gpu/](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)).
- The **supported AMD GPU list vLLM documents is**: MI200s (gfx90a), MI300 (gfx942), and Radeon RX 7900 series (gfx1100) for the ROCm 6.2+ era, expanding in newer releases to MI350/MI355, RX 9000-series Radeon (gfx1200/1201) and Ryzen AI Max/300 APUs (gfx1150/1151) ([docs.vllm.ai/en/v0.6.5/getting_started/amd-installation.html](https://docs.vllm.ai/en/v0.6.5/getting_started/amd-installation.html); [docs.vllm.ai/en/latest/getting_started/installation/gpu/](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)).
- AMD's own ROCm documentation for vLLM inference (ROCm 7.13.0 technology preview) lists supported Instinct GPUs (MI355X, MI350X/P, MI325X, MI300X/A) and supported Radeon GPUs (Radeon AI PRO R9700/R9600D, RX 9070 XT/9070 GRE/9070/9060 XT/9060, Radeon PRO W7900/W7800, RX 7900 XTX/XT/GRE, RX 7800 XT, RX 7700 XT/7700, PRO V710, RX 7600) — **no gfx1030, RDNA2, or RX 6900 XT/6800 device appears anywhere in this list** ([rocm.docs.amd.com/en/7.13.0-preview/ai-inference/vllm.html](https://rocm.docs.amd.com/en/7.13.0-preview/ai-inference/vllm.html)).
- **Conclusion: vLLM has no official or documented ROCm path for gfx1030/RDNA2 at all** (not even via an override — vLLM ships/compiles kernels per exact target rather than allowing an ISA-compatible override the way llama.cpp/Ollama do). Getting vLLM running on an RX 6900 XT would mean building from source against unsupported targets with no upstream guarantee of correctness or continued support — not a reasonable choice for a personal project.

---

## gfx1030 / RX 6900 XT support status specifics

| Runtime | gfx1030 in official supported list? | Override needed for RX 6900 XT specifically? | ROCm version targeted |
|---|---|---|---|
| Ollama | Yes — explicit row in the LLVM target table ([gpu.mdx](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx)) | No — RX 6900 XT's native gfx string is already gfx1030 | ROCm v7 driver required ([docs.ollama.com/gpu](https://docs.ollama.com/gpu)) |
| llama.cpp | Yes — used as the literal example target in the build docs ([docs/build.md](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/build.md)) | No | Whatever ROCm/HIP toolchain the user builds against (no version pin in the doc itself; AMD separately documents ROCm builds of llama.cpp at [rocm.docs.amd.com/projects/llama-cpp](https://rocm.docs.amd.com/projects/llama-cpp/en/docs-26.02/install/llama-cpp-install.html)) |
| vLLM | No — absent from every supported-GPU list found in vLLM's and AMD's own docs | N/A (not supported at all) | ROCm 6.2+ generally, prebuilt wheels for 7.0/7.2.1 ([docs.vllm.ai](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)) |

AMD's own top-level ROCm compatibility matrix (ROCm 7.14.0, current as of this research) does list gfx1030 as a supported target, via **"AMD Radeon PRO W6800 (gfx1030)"** and **"AMD Radeon PRO V620 (gfx1030)"** ([rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)). Note the nuance: **AMD's own official compatibility matrix only names professional/datacenter SKUs for gfx1030** (W6800, V620), not the consumer RX 6800/6900 XT directly — the matrix also shows minimal OS/driver-version detail for this older architecture compared to current-gen entries, suggesting it's a legacy-tier listing rather than a fully first-class one. However, since the consumer RX 6900 XT uses the identical Navi 21 die and gfx1030 ISA, and both Ollama's and llama.cpp's own docs compile/dispatch by gfx-target string (not by AMD's per-SKU support tier), gfx1030 kernels built by either runtime run on the RX 6900 XT without modification. This matches widespread real-world usage of RX 6800/6900-series cards with Ollama and llama.cpp.

**Bottom line: no `HSA_OVERRIDE_GFX_VERSION` workaround is needed for an RX 6900 XT on Ollama or llama.cpp** — that override exists for *other* RDNA2 chips (gfx1031/1032/1034 — RX 6700 XT/6600-series/6500-series) that lack their own compiled kernel and must masquerade as gfx1030 (`HSA_OVERRIDE_GFX_VERSION=10.3.0`). The RX 6900 XT already *is* gfx1030 natively.

---

## VRAM budget / concurrency analysis (16GB card)

Rough resident-memory budget for the two candidate models:

- `nomic-embed-text` (v1.5): tiny — 274MB package on Ollama, plus a modest KV/activation footprint for its 768-dim, ~2K-8K token context ([ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text); [huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)). Even `bge-m3` at ~1.2GB ([ollama.com/library/bge-m3](https://ollama.com/library/bge-m3)) is negligible next to a 16GB budget.
- `qwen3:14b` at Q4_K_M: 9.3GB weights ([ollama.com/library/qwen3:14b](https://ollama.com/library/qwen3:14b)), plus KV-cache overhead that scales with context length and batch size (roughly 1-3GB for a few-thousand-token context at this size), plus ROCm/driver overhead (typically 0.5-1.5GB reserved by the HIP runtime).

Adding these up (274MB–1.2GB + 9.3GB + ~2GB overhead ≈ 11.5–12.5GB), **both models could in principle fit resident simultaneously within 16GB**, with headroom to spare. So this is not strictly a VRAM-scarcity problem.

That said, for Tome's actual workload — a **periodic batch enrichment job**, not an interactive chat session — simultaneous residency buys nothing:

- The embedding pass (raw entry → vector) and the enrichment pass (raw entry → structured JSON) are logically separate stages that don't need to run at the exact same instant. A batch run can embed everything queued, release the embedding model, then load the chat model and classify everything queued.
- Ollama already does this automatically: it loads a model on first request and unloads it after an idle `keep_alive` window (default ~5 minutes) unless told to keep it warm. For a scheduled/periodic job this default behavior is exactly "hot-swap," with no special configuration required.
- Model *load* time is the only real cost of hot-swapping, and it's small relative to a periodic (e.g. hourly/nightly) batch cadence: a ~9.3GB file loading from a local NVMe/SSD at hundreds of MB/s to a few GB/s takes on the order of single-digit seconds to a couple dozen seconds — trivial next to the minutes a periodic job already runs on, and irrelevant to a background job with no human waiting synchronously.

**Recommendation: don't bother engineering for concurrent residency.** Sequential (hot-swap) loading is simpler, avoids any risk of VRAM fragmentation/OOM from two models fighting over the card, and matches how Ollama already behaves by default for a batch-style access pattern. Concurrent residency should only be revisited if Tome later wants an *interactive* chat/RAG feature where a user is asking questions live (embedding a query + generating an answer within the same request) — that's a different latency profile than a periodic background enrichment sweep.

---

## Recommended models

### Embedding: `nomic-embed-text` (v1.5)

- 137M parameters, Apache-2.0 license, produces 768-dimensional embeddings that are Matryoshka-truncatable down to 64 dims with minimal quality loss ([huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)).
- Nomic's own model card describes it as a long-context text encoder; Ollama's packaged version defaults to a 2K context window in its Modelfile, while the underlying model supports up to 8192 tokens per its native card — worth explicitly raising `num_ctx` if any raw note entries run long ([ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text), [huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)).
- Ships as a 274MB Ollama package, trivially cheap to keep loaded or reload on demand ([ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text)).
- Alternative: `bge-m3` (BAAI, 567M params, MIT license, 1024-dim, native 8192-token context, dense+sparse+multi-vector retrieval, ~1.2GB Ollama package) if multilingual notes or hybrid dense/sparse retrieval quality matter more than minimal footprint ([ollama.com/library/bge-m3](https://ollama.com/library/bge-m3), [huggingface.co/BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)).

### Enrichment/classification: `qwen3:14b`

- Qwen3-14B dense model: 14.8B total parameters (13.2B non-embedding), 40 layers, Apache-2.0 license, 32K native context (128K with YaRN) ([Qwen3 blog](https://qwenlm.github.io/blog/qwen3/); [huggingface.co/Qwen/Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B)).
- Ollama distributes it at Q4_K_M quantization, 9.3GB download ([ollama.com/library/qwen3:14b](https://ollama.com/library/qwen3:14b)) — comfortably inside 16GB with room for KV cache and ROCm overhead, and well clear of needing to drop to a smaller/more-quantized variant.
- Qwen3's own release material emphasizes strong tool-calling/agentic capability and claims the 4B variant "can rival the performance of Qwen2.5-72B-Instruct," implying the 14B dense model has ample headroom for a comparatively simpler task like structured entity extraction from short personal notes ([Qwen3 blog](https://qwenlm.github.io/blog/qwen3/)).
- Chosen over Qwen2.5:7b-instruct for extra headroom on extraction quality (people/date/topic disambiguation benefits from a larger model, and 16GB VRAM comfortably fits 14B at Q4_K_M) and over 32B-class models to leave load-time and future-headroom margin.

---

## Open questions / risks

- **Qwen3's thinking mode is a real risk for this task.** Qwen3 supports switching between "thinking" and "non-thinking" modes ([Qwen3 blog](https://qwenlm.github.io/blog/qwen3/)); if the enrichment job asks it to emit structured JSON, a thinking-mode reasoning preamble in the output would break naive JSON parsing. Confirm the exact non-thinking invocation for the Ollama-packaged `qwen3:14b` (e.g. an `enable_thinking`-style template flag or a `/no_think` convention) before wiring it into a parser, and prefer whatever mechanism the model's own chat template exposes rather than assuming.
- **AMD's own compatibility matrix names gfx1030 only through professional-tier SKUs** (Radeon PRO W6800/V620), not the consumer RX 6900 XT by name ([rocm.docs.amd.com compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)). The reasoning that this still covers the RX 6900 XT rests on shared silicon/ISA (both are Navi 21 / gfx1030) and on Ollama's/llama.cpp's own gfx-target-based dispatch — this is sound but is an inference from the primary sources rather than a sentence in any of them that names the RX 6900 XT directly. Worth a smoke test on the actual machine before relying on it in production.
- **ROCm's support lifecycle moves fast and drops old architectures over time.** Given RDNA2 (gfx1030) is now two generations behind AMD's current RDNA4 (gfx120x) lineup, watch Ollama/llama.cpp release notes for any future deprecation of gfx1030 kernels — pin a known-good Ollama version if this becomes a concern.
- **vLLM was ruled out entirely for this hardware** — if Tome's needs ever grow toward high-throughput multi-request serving (many concurrent users, not a personal single-user batch job), that would be the point to revisit vLLM, but it would require different (newer, RDNA3/4 or Instinct) hardware, not this card.
- Exact KV-cache VRAM consumption at the specific context lengths Tome will actually use (e.g. how long a "batch of raw entries" prompt gets) wasn't measured here — only estimated by convention. Worth a quick empirical check (`rocm-smi`/`nvtop`-equivalent monitoring during a real batch run) once the pipeline exists.
