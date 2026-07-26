# Embedding model selection for short-English asymmetric retrieval

Research for [issue #22](https://github.com/markdlabrecque/tome/issues/22), child of the "Tome: memory-keeper PRD" map ([#1](https://github.com/markdlabrecque/tome/issues/1)). Question: which locally-servable embedding model best fits Tome's actual retrieval workload — a conversational LLM-generated query against a 1–3 sentence LLM-written entity summary — and does it supersede the incumbent `bge-m3`?

Research date: 2026-07-26. Sources are primary: HuggingFace model cards and their shipped config files, the Ollama library and its registry API, the Ollama source, the MTEB results repository and benchmark definitions, and the relevant papers. **In addition, everything in §2, §5 and §6 was measured directly on the target machine** (Ollama 0.32.1, AMD RX 6900 XT / gfx1030, 16 GB VRAM), because several published facts turned out to be wrong for this stack.

---

## Summary / recommendation

### Two findings that outlast the model choice

**1. Adding a *generic task instruction* is dangerous; applying a model's *own native prefix* is a small, safe positive. These are different interventions and the literature conflates them.**

- **Generic task instructions swing results by −10.85 to +6.57 nDCG@10 with model-dependent sign.** On LMEB's 22 short-document memory datasets, turning instructions on cost `bge-large-en-v1.5` 10.85 points, `EmbeddingGemma-300M` 7.66 and `bge-m3` 5.95, while *gaining* `multilingual-e5-large-instruct` 5.21 and `KaLM-Embedding-V1` 6.57 — and `bge-multilingual-gemma2` a full **+16.31**. The MTEB maintainers measured the same volatility from another angle: changing *only* the instruction text on one task moved two models by +9.5 and +12.4 nDCG@10 while leaving a non-instruction-tuned model unmoved to five decimal places ([mteb#3469](https://github.com/embeddings-benchmark/mteb/pull/3469#issuecomment-3436467106)).
- **A model's native prefix is a much smaller effect.** Measured here on an 810-document on-distribution corpus (§6.1): applying `embeddinggemma`'s own documented prefixes rather than bare text is worth **+0.024 nDCG@10** on the hard query set (CI `[-0.039, +0.084]`, P=0.78) and **+0.002** on the easy one (P=0.60) — real in direction, not statistically established, and **smaller than the spread between models** (0.172 nDCG on the same set).

**This corrects a claim I had drafted from the small-corpus probe** — that prompt configuration is a 2–3× larger lever than model choice. That holds for *generic instruction experimentation*, and it does **not** hold for native prefixes on Tome-shaped data, where model choice is the larger lever.

**2. A required prefix that Ollama will never apply for you is still the highest-risk item in the decision** — not because the upside is large, but because the downside is silent. Ollama applies no template on the embed path for *any* of these models (§2, verified per-model), Tome has no retrieval-quality telemetry, and a prefix mistake therefore never surfaces. Prefix-freedom is a **safety property whose value is insurance, not performance** — and for `bge-m3` specifically the instruction lever points *down* (−5.95), so there is no upside being forgone at all (§8).

### Recommendation

**Keep `bge-m3`. It is not superseded.** Add one runtime option — `options.num_batch: 8192` on every `/api/embed` call — and the two properties [#16](https://github.com/markdlabrecque/tome/issues/16) provisionally adopted it for (prefix-free, 8192 context) both hold up under measurement. `vector(1024)` stands unchanged.

Three results decide it, all from the padded, precision-clean probe in §6.1 (810 documents, two independent query sets with opposite biases, all models at fp16/bf16):

- **`qwen3-embedding:0.6b` — the ticket's front-runner — is eliminated on quality, not just footprint.** At matched fp16 precision on a realistic corpus it is **worse than `bge-m3`** on both query sets (−0.045 nDCG@10, P=0.11; −0.006, P=0.05). Its apparent lead in my first small-corpus run was an artifact of a 40-document pool and an 8-bit-vs-fp16 mismatch. Independently it also fails criterion 4 by a measured 2.5× (**2.4 GB resident at `num_ctx=8192`, 4.0 GB at its default 32768**, vs `bge-m3`'s **940 MB**). Nothing recommends it.
- **`embeddinggemma:300m` is genuinely the best model for the *entity* layer, and it is blocked on context.** It beats `bge-m3` on **both** query sets with confidence intervals excluding zero (+0.069 nDCG@10, P=0.98 on the hard set; +0.010, P=0.98 on the easy one), and it wins even *without* its prefixes. But it is capped at **2048 tokens** — native, Ollama-packaged and measured, and unliftable (§9) — so under #16's mandatory `truncate: false` and #10's long-form raw entries it **cannot serve the raw layer at all**. This is the exact ground that disqualified `mxbai-embed-large`.
- **`bge-m3` is the best model that can serve *both* layers.** It ranks second of seven configurations on the hard query set and clears 8192 tokens; every model that beats it is capped at 2048 or below.

So the ticket's real question is not "which model" but **"one embedder or two"** — `embeddinggemma` for entity summaries, `bge-m3` for raw. §9 assesses that on the measured margin. **Recommendation: not for v1**, because the gain is incremental and *re-capturable at identical cost later* (swapping the entity embedder is a full entity re-derive, which #12 already supports), whereas committing to two embedders now permanently doubles [#17](https://github.com/markdlabrecque/tome/issues/17)'s re-embed design and forecloses cross-layer vector comparison forever. The published evidence is also split rather than one-sided: `bge-m3` leads LMEB-Semantic, LMEB-Dialogue and MLDR — the closest register match to a Tome entity gloss — while `embeddinggemma` leads LMEB-Episodic, KnowMeBench, PeerQA and EPBench, and every LMEB correlation is statistically insignificant at n=15 (CIs ≈ −0.60 to +0.44). §8 works through that split.

**Ruled out, with reasons:**

| Model | Ruled out because |
|---|---|
| `nomic-embed-text` (the [#8](https://github.com/markdlabrecque/tome/issues/8) choice) | **Two independent disqualifiers.** Its GGUF as shipped by Ollama declares a **2048** context — not 8192 — and no option can raise it (§2). And its prefixes are **mandatory** on *both* sides (`search_query: ` / `search_document: `), which Ollama never applies. #8 recommended it partly on "8192 tokens per its own model card"; that is not what Ollama ships. |
| `embeddinggemma:300m` | **2048 context, hard-capped** (fails criterion 2 — see §9), plus **required two-sided prefixes** including a document-side one (fails criterion 5, and makes any later prefix change a full re-embed), and Gemma Terms of Use rather than an OSI licence. Strong on quality; blocked on context. |
| `granite-embedding:278m` | **512 tokens** (measured). Ollama ships only the superseded 512-context generation; the 8192-context `granite-embedding-english-r2` — 149M params, Apache-2.0, prefix-free, best-in-class English retrieval — **is not in the Ollama library at all** (fails criterion 3). The strongest near-miss in this whole exercise. |
| `snowflake-arctic-embed2` | Viable, and strictly dominated: identical dimension (1024), identical measured footprint (940 MB) and identical usable window (8192, same `num_batch` caveat) as `bge-m3`, but adds a `query: ` prefix whose omission cost Snowflake never quantifies. No reason to pay a prefix obligation for a lateral move. |
| `bge-multilingual-gemma2` (BAAI's instruction-tuned embedder, considered because `bge-m3` has none) | **9.24B parameters** — roughly 4× criterion 4's entire budget before quantisation — the **`gemma` licence** rather than MIT, and it **404s in the Ollama library** (fails criterion 3). It also shows the largest instruction swing of any model measured (**+16.31**), which is the volatility argument of §8 in its purest form. |

**The designated challenger is `embeddinggemma:300m` for the entity layer only** — deferred, not rejected, on the reasoning in §9. `qwen3-embedding:0.6b`, which the ticket expected to win, is out on quality *and* footprint. §10 records the consequences for #16, #18, #8, #12 and #15.

---

## 1. The workload, restated precisely

Worth stating because it is what disqualifies most benchmarks:

- **Query**: one conversational sentence, written by an LLM agent calling `search_entities` — *"who should I talk to about accessibility?"*
- **Document**: a 1–3 sentence declarative third-person gloss, written by `qwen3:14b` during enrichment — *"Priya Nair leads the design system work and is the main contact for accessibility questions."* Typically 100–300 characters.
- **Asymmetric**: question against statement. Not paraphrase detection, not duplicate-question matching.
- **English only.** Per [CONTEXT.md](../CONTEXT.md), every Entity Type is a gloss of Mark's own notes.
- **Two layers, one model.** The same embedder also vectorises the raw layer, where [#10](https://github.com/markdlabrecque/tome/issues/10) permits long-form entries — hence criterion 2's ~8k requirement. The entity side is short; the raw side is not.
- **Exact search, no ANN index** ([#16](https://github.com/markdlabrecque/tome/issues/16)), so dimensionality is a linear scan-cost term and nothing else.

---

## 2. What Ollama's embed path actually does — three corrections

This section supersedes assumptions in #8, #16 and [#18](https://github.com/markdlabrecque/tome/issues/18). Every number was measured on this machine with `truncate: false`, binary-searching the largest accepted input and reading back `prompt_eval_count`.

| Ollama model | GGUF declared ctx | Packaged `num_ctx` | **Measured max tokens, default options** | **With `num_batch: 8192`** |
|---|---|---|---|---|
| `qwen3-embedding:0.6b` | 32768 | *(none)* | **32767** | 32767 |
| `bge-m3:latest` | 8192 | *(none)* | **2048** | **8192** |
| `snowflake-arctic-embed2:latest` | 8192 | *(none)* | **2048** | **8192** |
| `embeddinggemma:300m` | 2048 | `2048` (+ `num_batch 2048`) | **2048** | 2048 |
| `nomic-embed-text:latest` | 2048 | `8192` | **2048** | 2048 |
| `granite-embedding:278m` | 512 | *(none)* | **512** | 512 |

### Correction 1: `num_ctx` cannot raise the embed ceiling, only lower it

`/api/embed` computes its limit as `min(options.num_ctx, GGUF context_length)`. From `server/routes.go` in `EmbedHandler`'s `inputTokensAndContext` closure ([v0.32.4](https://github.com/ollama/ollama/blob/v0.32.4/server/routes.go#L879)):

```go
// TODO @nicolepardal: avoid reaching into kvData here; pass required tokenizer metadata via model/options instead
ctxLen := int(kvData.ContextLength())
if opts.NumCtx > 0 {
    ctxLen = min(opts.NumCtx, ctxLen)
}
```

This is why `nomic-embed-text` is stuck at 2048 despite Ollama's own packaged Modelfile setting `PARAMETER num_ctx 8192` — the `min()` silently discards it. The packaged value is dead weight, and actively misleading. Confirmed locally:

```
$ ollama show nomic-embed-text:latest
    context length      2048          <- GGUF
  Parameters
    num_ctx    8192                   <- unreachable
```

Upstream has known this since 2024: [ollama#7741](https://github.com/ollama/ollama/issues/7741) ("num_ctx does not increase context length above 2048") names `nomic-embed-text` specifically and was closed **without re-importing the GGUF**; [ollama#7008](https://github.com/ollama/ollama/issues/7008) is the same root cause for `mxbai-embed-large` (whose GGUF says 512). `OLLAMA_CONTEXT_LENGTH` — set to 32768 by [#15](https://github.com/markdlabrecque/tome/issues/15) — only supplies a *default* for `opts.NumCtx` and feeds the same `min()`, so it is equally clamped. The clamp is undocumented; [docs.ollama.com/api/embed](https://docs.ollama.com/api/embed.md) never mentions it.

### Correction 2: `num_batch` is a second, undocumented gate — and it is the one that was biting

**This corrects #18's headline measurement.** #18 concluded "the embedding ceiling is 2048 tokens, not 8192" from a `bge-m3` measurement, and inferred a runtime artifact affecting all embedders equally. The artifact is real but it is **`num_batch`, not `num_ctx`, and it is liftable**:

```
bge-m3, 3000-word input, truncate:false
  no options                       REJECTED  the input length exceeds the context length
  num_ctx=8192                     REJECTED  the input length exceeds the context length
  num_batch=8192                   ACCEPTED  prompt_eval_count=6002
  num_batch=8192 + num_ctx=8192    ACCEPTED  prompt_eval_count=6002
```

Binary-searched ceiling for `bge-m3` with `num_batch: 8192`: **8192 tokens**, i.e. the model's full native window. Same for `snowflake-arctic-embed2`. The mechanism is that a non-causal encoder must hold the whole sequence in one batch, and Ollama's default logical batch is 2048 — so the effective ceiling on the legacy llama.cpp path is `min(num_ctx, GGUF ctx, num_batch)`. Raising `num_ctx` alone can never help. Note `embeddinggemma` is the one package that ships `num_batch 2048` explicitly, matched to its 2048 native window.

**The override produces genuinely correct vectors, not merely accepted ones.** I verified this rather than assuming it, by burying a distinctive fact past the 2048 default ceiling of a 6689-token document:

```
cos(full_doc, doc_truncated_before_the_fact) = 0.9757   (not 1.000 -> the tail is in the vector)
cos(full_doc,      query_about_late_fact)    = 0.5014
cos(truncated_doc, query_about_late_fact)    = 0.4812
lift from including the tail                 = +0.0202   PASS
```

The absolute lift is modest because `bge-m3` uses CLS pooling, so one sentence in 6689 tokens is heavily diluted — an honest caveat about long-document embedding in general, not about this override.

**`qwen3-embedding:0.6b` needs neither option.** It is a `qwen3`-architecture causal model and runs on Ollama's newer engine, which honours `num_ctx` properly (setting 8192 lowered its ceiling to 8191, as the `min()` predicts) and defaults to the model's full 32768 with no tuning. It is the only candidate whose advertised context is simply true out of the box.

### Correction 3: Ollama applies no template on the embed path, for any of these models

Verified locally for every candidate: each is `TEMPLATE {{ .Prompt }}` or has no template layer at all. Two oddities found in the packaging:

- `snowflake-arctic-embed2`'s manifest files the **Apache License text under the `template` mediaType** — so `ollama show --modelfile` prints a licence where a template should be. Harmless on the embed path (which does not render templates) but it means there is definitely nothing that could inject the `query: ` prefix.
- `qwen3-embedding:0.6b` reports `tools` and `thinking` capabilities alongside `embedding`, inherited from the Qwen3 base. Irrelevant to `/api/embed`, but a reminder that it is a causal LM with last-token (EOS) pooling rather than a bidirectional encoder.

**Consequence:** every prefix any of these models wants must be applied by Tome's own code. This is exactly the silent-degradation surface criterion 5 is about — and #16 had already verified the `TEMPLATE {{ .Prompt }}` half of it.

---

## 3. Candidates, verified

Dimensions, licences and context lengths below are from the shipped weights (`ollama show` locally, GGUF metadata, and each model's own config files), not from prose.

### `bge-m3` — incumbent, recommended

- **Dimension 1024.** No Matryoshka support.
- **Prefix: none, explicitly.** The card states the design intent directly: *"The only difference is that the BGE-M3 model no longer requires adding instructions to the queries"* ([huggingface.co/BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)). This is a deliberate departure from BGE v1.5, which wanted `Represent this sentence for searching relevant passages: `. Queries and documents are embedded identically.
- **Context: 8192 native, 8192 reachable** — GGUF declares `bert.context_length = 8192`; measured 2048 by default, 8192 with `num_batch: 8192` (§2).
- **Footprint: 1.2 GB on disk (F16, 567M params); measured 940 MB resident** at 8192 with the batch override, 664 MB without it.
- **Licence: MIT** (packaged licence blob and card agree).
- **Ollama: `bge-m3:latest`** (also `bge-m3:567m`), flagged as an embedding model. Locally verified.
- Paper: [arXiv 2402.03216](https://arxiv.org/abs/2402.03216).
- **Caveat worth recording:** bge-m3's marquee feature is multi-functionality — dense + sparse/lexical + ColBERT multi-vector. **Ollama can only ever return the dense head**, because `EmbedResponse.Embeddings` is a bare `[][]float32` with nowhere to put token weights or per-token vectors. So the main reason one might tolerate bge-m3's size over a smaller English model is unavailable through this runtime. If hybrid dense+sparse retrieval ever becomes desirable, that is a runtime change, not a model change.

### `qwen3-embedding:0.6b` — designated challenger

- **Dimension 1024**, user-selectable from 32 to 1024 via MRL. *"Embedding Dimension: Up to 1024, supports user-defined output dimensions ranging from 32 to 1024"* ([model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)). **Same 1024 as bge-m3** — see §9.
- **Prefix: optional, query-side only.** This is its best property. The literal string, from the shipped [`config_sentence_transformers.json`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/raw/main/config_sentence_transformers.json):

  ```json
  "prompts": {
    "query": "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:",
    "document": ""
  },
  "default_prompt_name": null
  ```

  The document prompt is the **empty string**, and the card's code comments say so twice: `# Each query must come with a one-sentence instruction that describes the task` and `# No need to add instruction for retrieval documents`. Qwen is the only vendor here to quantify the cost of omission: *"in most retrieval scenarios, not using an `instruct` on the query side can lead to a drop in retrieval performance by approximately 1% to 5%."* The task description is meant to be customised per application.

  Note an inconsistency published by Qwen itself: the Python helper is `f'Instruct: {task_description}\nQuery:{query}'` (**no** space after `Query:`) while the card's TEI curl example uses `Query: ` **with** a space. I used the no-space form in §6.
- **Context: 32768 native, 32767 measured reachable with no tuning.**
- **Footprint: 639 MB on disk (Q8_0, 595.78M params) — but measured 2.0–4.0 GB resident** (§5). The disk figure badly understates it.
- **Licence: Apache-2.0.**
- **Ollama: `qwen3-embedding:0.6b`**, flagged as embedding. **Trap:** `qwen3-embedding:latest` is the **8B** model (4.7 GB) — the tag must always be pinned.
- Paper: [arXiv 2506.05176](https://arxiv.org/abs/2506.05176). Last-token (EOS) pooling on a causal LM: *"we utilize LLMs with causal attention, appending an [EOS] token at the end of the input sequence."*

### `embeddinggemma:300m` — best quality signal, disqualified on context and prefixes

- **Dimension 768**, MRL to 512/256/128.
- **Prefix: required in practice, on both sides, and asymmetric.** From the shipped [`config_sentence_transformers.json`](https://huggingface.co/google/embeddinggemma-300m): query is `"task: search result | query: "`, document is `"title: none | text: "` — note ` | ` is space-pipe-space, both end in a trailing space, and `none` is a literal that you substitute a real title into if you have one. `"default_prompt_name": null`, so nothing is applied unless asked. Google's card frames these as "Recommended Prompt" rather than mandatory, but the paper confirms all published scores were produced with them: *"using the prompt instructions detailed in the model card."* A bare `encode()` is off-distribution.
- **Context: 2048 native and hard-capped** — `max_position_embeddings: 2048`, GGUF 2048, packaged `num_ctx 2048`. Nothing lifts it. **This alone fails criterion 2**, and it fails it at a level (~1,400 words) that #18 already identified as painful.
- **Footprint: 621 MB on disk (BF16); measured 681 MB resident.** Comfortably inside criterion 4.
- **Licence: [Gemma Terms of Use](https://ai.google.dev/gemma/terms)**, not Apache/MIT — verified against the licence blob Ollama actually ships. For a self-hosted personal project this is fine in substance (§3.3: *"Google claims no rights in Outputs you generate using Gemma"*), but the terms are unilaterally updatable, incorporate a Prohibited Use Policy by reference, and reserve Google the right to *"restrict (remotely or otherwise) usage."* Note Google's own model-card page footer misleadingly reads "Apache 2.0 License" — that is documentation-site boilerplate, not the model licence.
- **Ollama: `embeddinggemma:300m`** (= `:latest`), flagged as embedding. Quantised `300m-qat-q4_0` (239 MB) and `-q8_0` (338 MB) tags also exist.
- Paper: [arXiv 2509.20354](https://arxiv.org/abs/2509.20354).

### `granite-embedding:278m` — and the r2 model that is not in Ollama

- What Ollama ships as `granite-embedding:278m` is **`granite-embedding-278m-multilingual`**: **768 dim, 512 tokens** (measured), Apache-2.0, 562 MB on disk, **180 MB measured resident** — the smallest footprint of the set. **Prefix-free**, CLS pooling. 512 tokens fails criterion 2 decisively.
- **The interesting model is `granite-embedding-english-r2`, and it is not in the Ollama library.** 149M params, 768 dim, **8192 context**, Apache-2.0, ModernBERT-based, **prefix-free**, and the best MTEB(eng, v2) Retrieval score of any candidate here at **56.4** ([model card](https://huggingface.co/ibm-granite/granite-embedding-english-r2), [arXiv 2508.21085](https://arxiv.org/abs/2508.21085)). On paper it is close to an ideal fit for criteria 1, 2, 4 and 5 simultaneously. It fails criterion 3: verified absent from `ollama.com/search?q=granite-embedding` and `?c=embedding`; the official `granite-embedding` namespace has only the six year-old 512-context r1 tags, which IBM's own cards mark as superseded. Reaching it would mean a GGUF conversion or a second serving path, both of which reopen #8's runtime decision. **Recorded as the strongest candidate blocked purely by packaging** — worth re-checking the Ollama library periodically.

### `snowflake-arctic-embed2` — viable, strictly dominated

- Ollama packages the **large** variant, `snowflake-arctic-embed-l-v2.0` (inferred from the `568m-l-fp16` tag name, the 566.70M parameter count in the config blob, and the `bert` family; the L variant is XLM-R-based while M is a custom `GteModel` Ollama's bert path would not load).
- **Dimension 1024**, MRL to exactly 256 (a single supported truncation point, not a range).
- **Prefix: `query: `** — five characters, colon, trailing space, from the shipped `config_sentence_transformers.json` (`"prompts": {"query": "query: "}`, with **no document key at all**). The card says *"use the query prefix below (just on the query)"* for "optimal retrieval quality". **Snowflake publishes no number for the cost of omitting it** — unlike Qwen. The card's own nav links to a `#faq` anchor that does not exist in the file.
- **Context: 8192 native**, 8192 reachable with the same `num_batch` override as bge-m3 — unsurprising, since it is built on `bge-m3-retromae`. (The card credits RoPE for the long context; the config actually says `"position_embedding_type": "absolute"` with `max_position_embeddings: 8194`. The 8192 is real, the explanation is wrong.)
- **Footprint: 1.2 GB on disk (F16 only, no quantised tag); measured 940 MB resident** — identical to bge-m3.
- **Licence: Apache-2.0.** Paper: [arXiv 2412.04506](https://arxiv.org/abs/2412.04506).
- **Why dominated:** same dimension, same footprint, same usable window, same runtime caveat as the incumbent — plus a prefix obligation with an unquantified downside. There is no axis on which it pays for the switch.

### `nomic-embed-text` — #8's choice, now disqualified

- **Dimension 768**, MRL to 64. **Licence Apache-2.0.** 274 MB on disk, **323 MB measured resident** — genuinely the cheapest thing that isn't Granite.
- **Prefix: mandatory, both sides.** The card is emphatic (emphasis theirs): *"**Important**: the text prompt **must** include a **task instruction prefix**, instructing the model which task is being performed."* For retrieval that is `search_document: ` on documents and `search_query: ` on queries (also `clustering: ` and `classification: `). Ollama's package has **no template layer**, and Ollama's own model readme passes bare text in its examples.
- **Context: 2048, unliftable** (§2) — not the 8192 its HF card advertises and not the 8192 its own packaged `num_ctx` claims.
- Two disqualifiers, either sufficient. Worth stating plainly because #8 chose it and #12 still names it.

### Also checked and excluded early

`mxbai-embed-large` (1024 dim, **512 context** per GGUF and packaged `num_ctx`, required query prompt `Represent this sentence for searching relevant passages: `) and `bge-large` / `bge-large-en-v1.5` (1024 dim, **512 context**, same query instruction, optional in v1.5 — BAAI: *"No instruction only has a slight degradation in retrieval performance"*). Both fail criterion 2 by 4×. The ticket already anticipated this class.

---

## 4. Comparison table

Resident VRAM and max tokens are **measured on this machine**, not vendor claims. "Usable ctx" is the largest input `/api/embed` accepts with `truncate: false`.

| | `bge-m3` ✅ | `qwen3-embedding:0.6b` | `embeddinggemma:300m` | `snowflake-arctic-embed2` | `granite-embedding:278m` | `nomic-embed-text` |
|---|---|---|---|---|---|---|
| **Dimension** | **1024** | **1024** (MRL 32–1024) | 768 (MRL 512/256/128) | 1024 (MRL 256) | 768 | 768 (MRL →64) |
| **Prefix required?** | **None** | Optional, **query only** | **Yes, both sides** | Query only, unquantified | **None** | **Yes, both sides** |
| **Literal prefix** | — | `Instruct: {task}\nQuery:{q}` | q: `task: search result \| query: `<br>d: `title: none \| text: ` | `query: ` | — | `search_query: ` / `search_document: ` |
| **Native ctx** | 8192 | 32768 | 2048 | 8192 | 512 | 8192 (card) |
| **GGUF ctx as shipped** | 8192 | 32768 | 2048 | 8192 | 512 | **2048** |
| **Ollama packaged `num_ctx`** | *(none)* | *(none)* | `2048` | *(none)* | *(none)* | `8192` (**unreachable**) |
| **Usable ctx, default opts** | 2048 | **32767** | 2048 | 2048 | 512 | 2048 |
| **Usable ctx, `num_batch 8192`** | **8192** | 32767 | 2048 | **8192** | 512 | 2048 |
| **Disk / quant** | 1.2 GB / F16 | 639 MB / Q8_0 | 621 MB / BF16 | 1.2 GB / F16 | 562 MB / F16 | 274 MB / F16 |
| **Measured resident VRAM** | **940 MB** | **2.4 GB** @8k / **4.0 GB** default | 681 MB | 940 MB | 180 MB | 323 MB |
| **Licence** | **MIT** | Apache-2.0 | **Gemma ToU** | Apache-2.0 | Apache-2.0 | Apache-2.0 |
| **In Ollama library** | Yes | Yes (pin the tag!) | Yes | Yes | Yes (r1 only) | Yes |
| MTEB(eng,v2) Retrieval | *incomplete* | **61.83** | 55.69 | 58.56 | 51.44 | 47.97 |
| **LMEB Mean(Dataset)** | **56.83** | 53.49 | 56.03 | n/a | n/a | *unreliable* |
| **Padded probe §6.1, set A nDCG@10** | 0.835 | 0.790 | **0.904** | 0.787 | 0.732 | 0.740 |
| **Padded probe §6.1, set B nDCG@10** | 0.984 | 0.978 | **0.994** | 0.986 | 0.984 | 0.981 |
| **Criteria failed** | *none* | **1** (quality), **4** (footprint) | **2**, **5** | *none (dominated)* | **2** | **2**, **5** |

Note how the two benchmark rows disagree, and how the two *models* that top them are different. That is §7.

---

## 5. Footprint, measured — and the trap in `qwen3-embedding`

`ollama ps` resident size, all models 100% on GPU, on the 16 GB card:

| Model | Loaded context | Resident |
|---|---|---|
| `granite-embedding:278m` | 512 | 180 MB |
| `nomic-embed-text` | 2048 | 323 MB |
| `bge-m3` | 8192 (default batch, 2048 usable) | 664 MB |
| **`bge-m3`** | **8192 + `num_batch 8192`** | **940 MB** |
| `embeddinggemma:300m` | 2048 | 681 MB |
| `snowflake-arctic-embed2` | 8192 + `num_batch 8192` | 940 MB |
| `qwen3-embedding:0.6b` | 2048 | 2.0 GB |
| `qwen3-embedding:0.6b` | 4096 | 2.2 GB |
| **`qwen3-embedding:0.6b`** | **8192** | **2.4 GB** |
| **`qwen3-embedding:0.6b`** | **32768 (its default!)** | **4.0 GB** |

**`qwen3-embedding:0.6b` has a ~2.0 GB floor and a 4.0 GB default.** Its 639 MB download is not its cost: it is a 28-layer causal transformer, so KV-cache and graph allocation dominate, and because Ollama's newer engine correctly defaults it to its full 32768 window, **the default is the expensive case**. Any adoption must pin `num_ctx` explicitly — the opposite of the usual advice, and the opposite of what the BERT-family models need.

### Co-residency, measured against the real chat model

I pulled `qwen3:14b` and tested it, rather than estimating as #8 did. `qwen3:14b` at `num_ctx: 16384` is **10 GB resident** (vs #8's 9.3 GB download figure), 70% of VRAM alone. Idle baseline is 13%.

| Configuration | Total resident | VRAM allocated | Both on GPU? |
|---|---|---|---|
| `qwen3:14b` @16k alone | 10 GB | 70% | — |
| **+ `bge-m3` @8k + `num_batch 8192`** | **10.9 GB** | **74%** | **Yes, 100% GPU** |
| + `qwen3-embedding:0.6b` @8k | 12.4 GB | 83% | Yes, 100% GPU |
| + `qwen3-embedding:0.6b` @default 32768 | 14 GB | 92% | Yes, 100% GPU |

**Both candidates fit** — #15's `keep_alive=-1` pinning is safe either way, and #8's "don't bother engineering for concurrent residency" is confirmed as *achievable* here even though #8 recommended hot-swapping anyway. But the margins differ materially: `bge-m3` leaves ~26% of the card free, `qwen3-embedding` at 8k leaves 17%, and at its default 8% — about 1.3 GB. On a machine that is Mark's daily driver, with a desktop compositor and browser competing for VRAM, 8% is the difference between "pinned" and "silently offloaded to CPU mid-run."

---

## 6. Workload-shaped measurement

MTEB does not measure this workload (§7), so I built a probe that does. **Read this as indicative, not as a benchmark** — the caveats at the end are load-bearing.

**Setup.** 40 entity summaries I hand-wrote in Tome's actual Entity Type shapes (Person, Project, Preference, Decision, Fact, Commitment, Event), 1–3 sentences each, in the register `qwen3:14b` would plausibly produce. 40 conversational queries of the kind an LLM agent would send to `search_entities`, deliberately paraphrased rather than lexically overlapping their target, with near-miss distractors in the corpus (e.g. `preference:async-review` competing with `person:alex-chen` for "who can't do early meetings"). Exact cosine over L2-normalised vectors, matching #16's mechanism. Metrics Recall@1 and MRR@10, plus a paired bootstrap over queries (20,000 resamples).

| Config | R@1 | MRR@10 |
|---|---|---|
| `embeddinggemma:300m` prefixed | **0.925** | **0.963** |
| `qwen3-embedding:0.6b` prefixed | **0.925** | **0.954** |
| `qwen3-embedding:0.6b` bare | 0.875 | 0.933 |
| `snowflake-arctic-embed2` prefixed | 0.875 | 0.925 |
| `nomic-embed-text` bare | 0.850 | 0.904 |
| `embeddinggemma:300m` bare | 0.825 | 0.903 |
| `nomic-embed-text` prefixed | 0.825 | 0.898 |
| `granite-embedding:278m` (prefix-free) | 0.825 | 0.878 |
| `snowflake-arctic-embed2` bare | 0.825 | 0.876 |
| **`bge-m3` (prefix-free)** | **0.800** | **0.896** |

**Paired bootstrap vs `bge-m3`, MRR@10** — a CI spanning zero means not distinguishable:

```
qwen3-embedding:0.6b  prefixed   +0.058  CI [-0.004, +0.125]  P(better)=0.96
embeddinggemma:300m   prefixed   +0.067  CI [+0.004, +0.133]  P(better)=0.98
snowflake-arctic2     prefixed   +0.029  CI [-0.037, +0.100]  P(better)=0.77
nomic-embed-text      bare       +0.008  CI [-0.075, +0.087]  P(better)=0.55
granite-embedding     bare       -0.018  CI [-0.111, +0.073]  P(better)=0.36
qwen3-embedding:0.6b  bare       +0.037  CI [-0.025, +0.104]  P(better)=0.86
```

On R@1 both leaders are +0.125 over `bge-m3` with CI `[0.000, 0.250]` — the lower bound touches zero exactly. And the two leaders are **indistinguishable from each other** (qwen3 − gemma = −0.008, CI `[-0.062, +0.046]`, P=0.36).

### The prefix ablation is the most trustworthy result here

A *within-model* comparison is robust to the corpus being small and single-authored in a way the cross-model comparison is not — the same 40 documents and queries, the same model, only the prefix differing:

```
MRR@10, prefixed - bare
  embeddinggemma:300m       +0.060  CI [+0.000, +0.123]  P(prefix better)=0.97
  snowflake-arctic-embed2   +0.049  CI [-0.013, +0.118]  P(prefix better)=0.94
  qwen3-embedding:0.6b      +0.021  CI [-0.008, +0.062]  P(prefix better)=0.85
  nomic-embed-text          -0.006  CI [-0.050, +0.037]  P(prefix better)=0.34
```

Three findings worth carrying forward regardless of which model wins:

1. **Where a prefix is specified, applying it helps** — three of four models improved, and `qwen3-embedding`'s +0.021 sits right inside Qwen's own claimed "1% to 5%".
2. **`nomic-embed-text` did not improve from its own mandatory prefix** on this corpus. Given the card says it *must* be used, the most likely reading is that the corpus is too easy and too small to expose the difference — but it is a genuine negative result and I am not going to dress it up.
3. **The prefix is a larger lever than the model choice.** The best-to-worst spread across models is ~0.085 MRR; the prefix swing within `embeddinggemma` alone is 0.060. This independently corroborates the published finding in §7 and is the single strongest argument for criterion 5.

### Robustness check: the ranking is not a document-length artifact

Since the whole premise is that document length changes which model wins, I re-ran the probe with every summary cut to its **first sentence only** (mean 142 → 126 characters), making the documents shorter and sparser:

| Config | full (R@1 / MRR) | first sentence only |
|---|---|---|
| `embeddinggemma:300m` prefixed | 0.925 / 0.963 | 0.900 / 0.933 |
| `qwen3-embedding:0.6b` prefixed | 0.925 / 0.954 | 0.875 / 0.917 |
| `qwen3-embedding:0.6b` bare | 0.875 / 0.933 | 0.850 / 0.908 |
| `snowflake-arctic-embed2` prefixed | 0.875 / 0.925 | 0.850 / 0.901 |
| `nomic-embed-text` prefixed | 0.825 / 0.898 | 0.800 / 0.871 |
| `granite-embedding:278m` bare | 0.825 / 0.878 | 0.800 / 0.855 |
| **`bge-m3` bare** | 0.800 / 0.896 | **0.750 / 0.840** |

Every model degrades slightly and **the order is preserved exactly**, with `bge-m3` still last and degrading most. So the §6 ranking is not an artifact of where in the 100–300-character band the documents sit. This is a weak perturbation (only 16 characters of mean difference) and it does **not** address the authorship bias below, which remains the probe's real limitation.

### Caveats, and they are serious

- **N=40.** One query is 0.025 of R@1. Nothing under ~3 queries of separation is meaningful.
- **I wrote both the queries and the documents.** I cannot rule out having unconsciously written in a register that suits instruction-tuned models — which is precisely the direction the results point. This is the probe's biggest weakness and the main reason it does not overrule §7.
- **40 documents is a tiny candidate pool.** Real Tome will hold thousands of entities, where discrimination is much harder and the ranking could reorder.
- **No relevance judgements beyond one gold answer per query.** Several "misses" are arguably correct — *"which of my colleagues can't do early morning meetings?"* returning `preference:async-review` is a defensible answer that scores as a failure.
- The harness is reproducible but was not committed (it is not product code); it lives in `/tmp/tome_retrieval_probe.py` and `/tmp/tome_stats.py` for the duration of this session only.

---

## 6.1 The padded, precision-clean probe — the measurement that decides the ticket

§6's weaknesses were a 40-document pool, a single author, and (discovered afterwards) an 8-bit-vs-fp16 precision mismatch. This run fixes all three.

**Setup.** The 40 hand-written gold summaries, plus **770 additional entity summaries generated by `qwen3:14b`** — the actual enrichment model — across all 7 Entity Types and 8 life domains, giving an **810-document corpus** in which every document is a plausible negative. Two query sets, kept separate because their biases run in opposite directions:

- **Set A — 40 hand-written queries** (n=40). Deliberately paraphrased away from their targets, so genuinely adversarial. Weakness: I wrote both sides.
- **Set B — 200 queries generated by `qwen3:14b`** from summaries it had written (n=200). Removes my authorship bias entirely, and is the production shape — an LLM writes the summary, an LLM writes the query. Weaknesses: it shares vocabulary with its target, making it markedly easier; and it is noisier (spot-checking found items that are generic-knowledge rather than personal-memory shaped, and one with a mismatched pronoun).

**All models at fp16/bf16 tags** (`qwen3-embedding:0.6b-fp16` in place of the Q8_0 default), so precision is not a confound. Exact cosine, matching #16.

| Config | Set A nDCG@10 | Set A R@1 | Set B nDCG@10 | Set B R@1 |
|---|---|---|---|---|
| **`embeddinggemma:300m`** (prefixed) | **0.904** | **0.800** | **0.994** | **0.985** |
| `embeddinggemma:300m` (bare, no prefix) | 0.880 | 0.750 | 0.992 | 0.980 |
| **`bge-m3`** (prefix-free) | **0.835** | **0.700** | **0.984** | **0.965** |
| `qwen3-embedding:0.6b-fp16` (prefixed) | 0.790 | 0.650 | 0.978 | 0.950 |
| `snowflake-arctic-embed2` (prefixed) | 0.787 | 0.675 | 0.986 | 0.965 |
| `nomic-embed-text` (prefixed) | 0.740 | 0.600 | 0.981 | 0.960 |
| `granite-embedding:278m` (prefix-free) | 0.732 | 0.650 | 0.984 | 0.960 |

**Paired bootstrap vs `bge-m3`, nDCG@10, 20,000 resamples:**

```
                                   set A (n=40)                          set B (n=200)
embeddinggemma:300m         +0.069 CI [+0.007,+0.132] P=0.98    +0.010 CI [+0.001,+0.022] P=0.98
embeddinggemma:300m [bare]  +0.045 CI [-0.024,+0.123] P=0.90    +0.008 CI [-0.001,+0.020] P=0.95
qwen3-embedding:0.6b-fp16   -0.045 CI [-0.122,+0.023] P=0.11    -0.006 CI [-0.014,+0.001] P=0.05
snowflake-arctic-embed2     -0.048 CI [-0.137,+0.030] P=0.12    +0.002 CI [-0.007,+0.012] P=0.68
granite-embedding:278m      -0.104 CI [-0.223,+0.007] P=0.03    +0.000 CI [-0.012,+0.013] P=0.49
nomic-embed-text            -0.095 CI [-0.201,-0.002] P=0.02    -0.002 CI [-0.015,+0.009] P=0.35
```

**What this establishes:**

1. **`embeddinggemma:300m` > `bge-m3` on Tome-shaped retrieval, replicated across two query sets with opposite biases, both CIs excluding zero.** This is the only result in the study that survives both. The honest effect-size range is **+0.010 to +0.069 nDCG@10** — the truth for real usage is somewhere between the easy set and the hard one, and the hard set's +10 percentage points of R@1 (0.700 → 0.800) is the more decision-relevant end.
2. **`qwen3-embedding:0.6b` is eliminated.** At matched precision on a realistic corpus it is *below* the incumbent on both sets. §6's apparent lead was a small-pool-plus-quantisation artifact. This is the clearest single correction the padded run produced.
3. **Model choice is a bigger lever than a native prefix on this data** (spread 0.172 vs prefix effect 0.024 on set A) — reversing what §6's small corpus suggested, and the correction recorded at the top of this file.
4. **Set B is near-saturated** (0.978–0.994) and therefore barely discriminates; its significance comes from n=200, not from effect size. Set A discriminates well but is n=40. Neither alone would be convincing; agreeing, they are.

### A bug I found and fixed, recorded because it nearly produced a false conclusion

The first padded run returned R@1 = **0.025 for every model** — exactly 1/40. That is the signature of broken ground truth, not of seven models simultaneously failing, so I diagnosed it before reporting: the hand-written query list pairs each query with its target's **key**, not its position, and the padded harness had assumed positional correspondence. Inspecting the actual rankings showed the models were retrieving correctly all along (`"who should I talk to about accessibility?"` → Priya Nair at rank 1). Fixed, re-run, and the corrected numbers are the ones above. **Any single-number retrieval result that looks uniform across models should be treated as a harness fault until the top-ranked documents have been eyeballed.**

### Remaining limitations

- **Power is set by query count, not corpus size.** Padding to 810 documents made the task realistically hard — which is why set A's scores dropped from §6's 0.80–0.925 R@1 to 0.60–0.80 — but the bootstrap is still over 40 and 200 queries. Padding fixed realism, not sample size.
- **One gold document per query, in a corpus that now contains near-duplicates.** With 770 generated summaries across the same life domains, several set-A queries have genuinely plausible alternative answers that score as errors — e.g. *"how often does the vehicle need maintenance?"* has the gold at 0.652 and a generated oil-change summary at 0.650. This depresses all models roughly equally, so comparisons remain usable, but the absolute scores understate real-world quality.
- **Set B's queries were written by the same model that wrote its documents**, which may favour models whose embedding space aligns with `qwen3:14b`'s lexical choices. This is a real confound and the reason set A is retained despite its author bias.
- Harnesses live in `/tmp/tome_final_probe.py`, `/tmp/tome_gen_distractors.py`, `/tmp/tome_gen_queries.py` and `/tmp/tome_final_stats.py` for this session only; they are not product code and were not committed.

---

## 7. Why MTEB is the wrong benchmark — and what the right one says

The ticket asked for skepticism about MTEB averages. The situation is worse than "the average is diluted": **the retrieval subset itself is measuring a different task.**

### The MTEB(eng, v2) retrieval subset has no short documents at all

It is only 10 tasks, and MTEB publishes its own per-task corpus statistics. Average document length, `test` split, in characters:

| Task | avg query chars | avg **doc** chars |
|---|---|---|
| Touche2020Retrieval.v3 | 43 | 2096 |
| ClimateFEVERHardNegatives | 122 | 1246 |
| SCIDOCS | 72 | 1204 |
| TRECCOVID | 69 | 1117 |
| ArguAna | **1193** | 1030 |
| CQADupstackUnixRetrieval | 50 | 1006 |
| FiQA2018 | 63 | 767 |
| FEVERHardNegatives | 50 | 696 |
| CQADupstackGamingRetrieval | 49 | 490 |
| HotpotQAHardNegatives | 93 | 375 |

Mean document ≈ **1003 characters**. A Tome entity summary is **100–300**. Not one of the ten is in the right regime; ArguAna is actively pathological, with *queries* averaging 1193 characters. And v2 deliberately **dropped** the one MTEB retrieval task with genuinely short documents — QuoraRetrieval (docs ~62 chars) survives only in the legacy `MTEB(eng, v1)`. STS tasks are short-text but **symmetric pair regression scored by Spearman correlation, not ranking**; a high STS score is weak evidence that a question vector lands near a statement vector in a large pool, and should not be read as short-document retrieval skill.

Also worth recording, since it explains a lot of confusion in vendor tables: **`MTEB(eng, v1)` and `MTEB(eng, v2)` scores are not comparable.** v1 has 56 tasks, is marked `superseded_by=["MTEB(eng, v2)"]`, and v2's own description says it *"resolves [a known scoring bug], uses updated task versions, and removes common fine-tuning datasets such as MSMARCO."* `nomic-embed-text`'s self-reported 62.28 is a v1 number and must never be set beside EmbeddingGemma's 69.67 or Qwen's 70.70. Concretely: `granite-embedding-english-r2` and `nomic-embed-text-v1.5` are **tied on BEIR-15 (53.1 vs 53.0)** and **8.5 points apart on MTEB(eng, v2) Retrieval (56.4 vs 48.0)** — same models, same metric, opposite conclusions.

### The right benchmark exists, and it favours the incumbent

MTEB now ships **`LMEB`, display name "Long-Horizon Memory"** ([benchmarks.py](https://github.com/embeddings-benchmark/mteb/blob/main/mteb/benchmarks/benchmarks/benchmarks.py)), described as *"Long-horizon memory retrieval quality across episodic, dialogue, semantic, and procedural retrieval tasks, measuring how well embedding models retrieve evidence in long-term memory scenarios"* — 22 English zero-shot datasets, 193 retrieval tasks ([arXiv 2603.12572](https://arxiv.org/abs/2603.12572)). Several of its datasets are LLM-written short queries against LLM- or human-written short memories, i.e. Tome's shape almost exactly:

| LMEB dataset | Category | query words | **doc words** |
|---|---|---|---|
| ConvoMem | Dialogue | 23.19 | **27.33** |
| PeerQA | Semantic | 15.65 | 24.67 |
| REALTALK | Dialogue | 8.99 | 34.20 |
| LoCoMo | Dialogue | 10.36 | 38.73 |
| MemBench | Dialogue | 10.41 | 42.92 |
| ReMe | Procedural | 13.51 | 47.36 |
| KnowMeBench | **Episodic (Event)** | 31.80 | **58.68** |

Compare BEIR, where the only sub-30-word corpus is Quora.

**LMEB explicitly measures that MTEB rank does not transfer:** *"the correlation analysis between LMEB and MTEB (eng, v2) (retrieval subset) shows low Pearson and Spearman correlation coefficients of **-0.115 and -0.130**, respectively, demonstrating that the two benchmarks are orthogonal."* On the dialogue subset it is worse: *"the Pearson and Spearman correlation coefficients between LMEB-Dialogue and MTEB (eng, v2) (retrieval subset) are **-0.496 and -0.364**."* The paper's own headline findings include *"Larger models do not always perform better."*

Sub-1B models, LMEB nDCG@10 (w/o instruction), against their MTEB retrieval scores:

| Model | LMEB Mean(Dataset) | LMEB Mean(Type) | MTEB(eng,v2) Retrieval |
|---|---|---|---|
| **`bge-m3` (Dense) 560M** | **56.83** | **58.57** | *incomplete* |
| EmbeddingGemma-300M | 56.03 | 58.26 | 55.69 |
| jina-v5-text-small 596M | 53.80 | 55.17 | — |
| **Qwen3-Embedding-0.6B** | 53.49 | 54.30 | **61.83 (best)** |
| bge-large-en-v1.5 335M | 53.02 | 53.54 | 55.44 |
| multilingual-e5-large-instruct | 49.85 | 51.25 | 53.47 |
| *Qwen3-Embedding-**4B*** | 51.44 | 52.38 | — |

**`Qwen3-Embedding-0.6B` leads this group on MTEB retrieval by 6.1 points and trails `bge-m3` on LMEB by 3.3.** Qwen3-Embedding-**4B**, seven times larger, scores *below* EmbeddingGemma-300M. This is a direct, published, independent contradiction of the ticket's founding suspicion that bge-m3's long-document and multilingual tuning would hurt it on short English glosses. **On the closest published proxy for Tome's workload, bge-m3 is the best sub-1B model available.**

I independently replicated the non-transfer effect on QuoraRetrieval using the [MTEB results repository](https://github.com/embeddings-benchmark/results): across nine candidates, MTEB(eng, v2) Retrieval and QuoraRetrieval nDCG@10 correlate at **Spearman −0.05**, with MTEB retrieval spreading 13.86 points while Quora spreads only 2.28 — and the *worst* model on MTEB retrieval (`nomic`, 47.97) beating the *best* (`Qwen`, 87.78) on Quora. Caveat: Quora is near-saturated (all models 86.9–89.2), so low variance mechanically suppresses correlation — which itself says Quora cannot discriminate between these models either.

### Published evidence that prompt configuration outweighs model choice

This corroborates §6's ablation from a completely independent direction. LMEB ran the same 22 datasets with instructions off and on:

| Model | w/o inst | w/ inst | Δ |
|---|---|---|---|
| bge-large-en-v1.5 | 53.02 | 42.17 | **−10.85** |
| EmbeddingGemma-300M | 56.03 | 48.37 | **−7.66** |
| `bge-m3` (Dense) | 56.83 | 50.88 | **−5.95** |
| Qwen3-Embedding-0.6B | 53.49 | 54.71 | +1.22 |
| multilingual-e5-large-instruct | 49.85 | 55.06 | **+5.21** |
| KaLM-Embedding-V1 | 48.64 | 55.21 | **+6.57** |

**The range is −10.9 to +6.6 nDCG@10 and the sign is model-dependent** — roughly 2–3× the total spread between the top and bottom model. The MTEB maintainers measured the same thing from another angle: on ClimateFEVERHardNegatives, changing *only the instruction text* moved `multilingual-e5-large-instruct` by +9.5 and `stella_en_400M_v5` by +12.4 nDCG@10, while a non-instruction-tuned model was unmoved to five decimal places ([mteb#3469](https://github.com/embeddings-benchmark/mteb/pull/3469#issuecomment-3436467106)).

**Note the direction for `bge-m3`: adding an instruction cost it 5.95 points.** Its prefix-freedom is not merely a convenience — on this task family, leaving it alone is measurably the right thing to do, which is a second, independent argument for criterion 5 and for the incumbent.

Two honest caveats: LMEB's "w/o inst." setting does not state whether each model's *native* template (e.g. EmbeddingGemma's `task: search result | query:`) was retained or stripped along with the task instruction, so this quantifies "prompt text matters by ±5–11 points" rather than specifically "omitting a required prefix costs N points." And BGE's own guidance — *"For a retrieval task that uses short queries to find long related documents, it is recommended to add instructions"* — is scoped to long documents, i.e. explicitly not Tome.

---

## 8. Reconciling the evidence — split, not a win for either

The conflict is the substance of this ticket, so it should not be papered over, and it should not be resolved by argument in either direction.

### The honest position: the evidence does not discriminate between `bge-m3` and `embeddinggemma:300m`

`bge-m3` wins LMEB-Semantic, LMEB-Dialogue, MLDR and QASPER. `embeddinggemma:300m` wins my probe (§6), LMEB-Episodic, KnowMeBench, PeerQA and EPBench. **Neither has a clean sweep and the margins are small.**

It would be equally wrong to use LMEB to overrule the probe. LMEB is unrefereed, and **every one of its correlation coefficients is statistically insignificant at n=15** — the confidence intervals run from roughly −0.60 to +0.44, comfortably spanning zero. More importantly, LMEB's own stated mechanism for why MTEB does not transfer is that memory evidence is *"fragmented, context-dependent, and temporally distant"* — a description that **does not fit Tome's clean, deduplicated, third-person glosses at all**. Using an off-distribution benchmark to override an on-distribution measurement is the same error in the opposite direction.

Two register corrections matter here and cut against reading LMEB as a bge-m3 vindication:

- **KnowMeBench and ConvoMem are not Tome-shaped.** KnowMeBench documents are structured first-person records, ConvoMem's are conversation turns. Neither is a third-person declarative gloss. Yet LMEB-Episodic — the category `embeddinggemma` wins — is built on them.
- **MLDR is the closest register match in LMEB** — a natural-language question against a third-person, Wikipedia-style entity gloss, which is very nearly Tome's entity layer exactly. `bge-m3` leads it. Note the counter-consideration: MLDR is a *long*-document retrieval task, so it matches Tome on register while mismatching on length, which is the axis this whole ticket is about. It supports `bge-m3` on the dimension that matters most and is compromised on the dimension the ticket is named for.

So the two benchmark families each match Tome on one axis and miss on the other, and the model that wins flips with the axis. **That is a split, and it is why §9 resolves the ticket on operational grounds rather than quality.**

### One confound worth recording, because it changes which comparisons are trustworthy

**Ollama's default tags are not all the same precision**, verified locally with `ollama show`:

| Default tag | Quantisation |
|---|---|
| `bge-m3:latest` | **F16** |
| `embeddinggemma:300m` | **BF16** |
| `snowflake-arctic-embed2:latest` | F16 |
| `granite-embedding:278m` | F16 |
| `nomic-embed-text:latest` | F16 |
| **`qwen3-embedding:0.6b`** | **Q8_0** (`:0.6b` and `:0.6b-q8_0` share a digest; `:0.6b-fp16` is a separate 1.2 GB blob) |

So the `bge-m3` vs `embeddinggemma` leg of §6 is **precision-clean** — both at the fp16/bf16 precision LMEB's reference implementations used — while the `qwen3-embedding` leg was run 8-bit-quantised and is confounded. §6.1 re-runs everything at fp16/bf16 to remove this.

This weakens the `qwen3-embedding` result specifically, in a direction that does not rescue it: it fails criterion 4 on footprint at *any* precision, and at fp16 its resident footprint would be strictly worse than the 2.4 GB measured at Q8_0.

### Does prefix-freedom cost us the biggest lever?

The headline finding says prompt configuration is a 2–3× larger lever than model choice. `bge-m3` is prefix-free, so choosing it forgoes that lever entirely. **Is that a cost or a safety property?** On this evidence it is a safety property, for three reasons:

1. **`bge-m3`'s *unconfigured* scores already lead** on LMEB-Semantic, LMEB-Dialogue and MLDR. So we would be leaving upside unrealised, not accepting a deficit.
2. **The lever's sign is model-dependent, and for `bge-m3` it points down**: adding instructions cost it **−5.95** nDCG@10 on LMEB. For this model the configured direction is worse, so there is no upside to forgo — the correct configuration *is* the empty one.
3. **The downside is unbounded and silent.** The swing runs to −10.85 for `bge-large-en-v1.5`, and Tome has no telemetry to notice it. A prefix-free model removes the failure mode rather than managing it.

**`bge-m3` has no instruction-tuned variant worth considering.** BAAI's instruction-following embedder is `bge-multilingual-gemma2`, which is excluded on three independent grounds: **9.24B parameters** (~4× criterion 4's whole budget before quantisation), the **`gemma` licence** rather than MIT, and it **404s in the Ollama library** — failing criterion 3. It also has the largest instruction swing of any model measured (**+16.31**), which is precisely the volatility argument above. `bge-m3`'s own card recommends no instruction and states the design intent explicitly (§3).

### What everything agrees on

- **Prefix configuration matters more than model identity.** §6 measures a 0.060 MRR swing inside one model; §7 measures −10.85 to +6.57 nDCG@10 across models. Both dwarf the model-to-model spread. This is the durable result.
- **No model in this set is decisively better at this task.** The spread is small and the rank order depends on which measurement you believe. That is itself the answer to "does it supersede": a change of this cost needs a clear win, and there is not one.
- **`embeddinggemma:300m` is the model to watch.** It is disqualified on **context** (§9's dual-model assessment), not on quality — and on quality it is the best-supported challenger.

---

## 9. The real question: one embedding model, or two?

`embeddinggemma:300m`'s context length is the fact that shapes this ticket, so it is worth stating with all three figures, from primary sources and from measurement:

| | Value | Source |
|---|---|---|
| **Native context** | **2048** | *"Maximum input context length of 2048 tokens"* — [model card](https://huggingface.co/google/embeddinggemma-300m); `"max_position_embeddings": 2048` in the shipped `config.json`; *"2K token context"* on [ai.google.dev](https://ai.google.dev/gemma/docs/embeddinggemma) |
| **Ollama-packaged `num_ctx`** | **2048** | Registry params blob: `{"num_batch":2048,"num_ctx":2048}`. Locally: `ollama show embeddinggemma:300m` → `num_ctx 2048`, `num_batch 2048`, GGUF context length 2048. The Ollama library page advertises "2K context" honestly. |
| **Measured usable ceiling** | **2048** | §2. Unliftable — `num_ctx`, `num_batch` and `OLLAMA_CONTEXT_LENGTH` all fail to raise it, because the GGUF ceiling *is* 2048 and `min()` wins. |

So it is the 2048 case. Under #16's mandatory `truncate: false` and #10's long-form raw entries, **`embeddinggemma:300m` cannot serve the raw layer** — overflow is a hard `400` that lands in the human attention queue, which is exactly the ground that disqualified `mxbai-embed-large` and made `nomic-embed-text`'s packaged 2K a liability. The question therefore becomes: one model, or one per layer?

### Assessed: `embeddinggemma:300m` for entities + `bge-m3` for raw

This is coherent, and it is not a VRAM problem. Measured (§5): `qwen3:14b` @16k = 10 GB, `bge-m3` @8k+batch = 940 MB, `embeddinggemma` @2k = 681 MB → **~11.6 GB of 16 GB**, both embedders pinnable at `keep_alive=-1`. The entity layer is also *inherently* length-bounded — a 1–3 sentence summary is nowhere near 2048 tokens — so the context limit genuinely does not bind on that side.

**The measured gain is real.** §6.1 establishes `embeddinggemma:300m` over `bge-m3` at **+0.069 nDCG@10 / +10 points R@1** on the adversarial query set and **+0.010 / +2 points** on the easy one, both with CIs excluding zero. This is not a rounding error and it should not be dismissed as one. It is the best-supported quality result in this study.

**Recommendation: defer it, do not reject it.** Four grounds, in order of weight:

1. **The gain is re-capturable later at identical cost; the architectural commitment is not.** Adopting a second embedder for entities requires deleting and re-deriving the entity layer — which is exactly #12's full Enrichment Run, a mechanism that already exists and will keep existing. So waiting costs nothing but the foregone gain in the interim. Committing now, by contrast, permanently shapes **#17's re-embed design into two independent operations** that can sit at different versions simultaneously, with the entity-side one re-triggered by every merge (#12 rewrites a summary per contributing entry). **Asymmetric reversibility is the argument.**
2. **Cross-layer vector comparison is foreclosed permanently.** Two embedding spaces (768-dim and 1024-dim) means a raw vector and an entity vector can never be compared, co-scored or reranked against each other. #3's tiering does not need that today; giving it up forever for +0.07 nDCG is a bad trade in an unfinished design.
3. **The published evidence does not corroborate the probe.** `bge-m3` leads LMEB-Semantic, LMEB-Dialogue and **MLDR — the closest register match in LMEB to a third-person entity gloss retrieved by a natural-language question**. `embeddinggemma`'s LMEB support is Episodic (+1.19 over `bge-m3`, one category), built on KnowMeBench and ConvoMem, whose documents are structured first-person records and conversation turns respectively — not Tome-shaped. One on-distribution probe with a 40-query hard set is *not enough on its own* to override that, especially against a licence downgrade.
4. **Two pinned models contend on a single-threaded runtime.** #15's topology assumes one embedder. Under `OLLAMA_NUM_PARALLEL=1` a capture-path embed and an enrichment-path embed would serialise across *two* models rather than queueing on one. VRAM is genuinely fine (~11.6 GB of 16); scheduling is the cost, not memory.

**What would change the answer.** Any one of these should reopen it:

- **Retrieval telemetry showing entity search underperforming in practice.** This is the missing ingredient for the whole decision (§10) and would convert +0.069 nDCG from a proxy into an observed deficit.
- **Raw-layer chunking.** If #18's roadmapped chunked scheme lands — one Raw Entry plus `(entry_id, ordinal, span, embedding)` children — chunks would be sized well under 2048 tokens, **the context objection to `embeddinggemma:300m` vanishes, and it becomes a single-model candidate on the merits** rather than a two-model compromise. This is the most likely trigger and is worth noting in #18.
- **`granite-embedding-english-r2` appearing in the Ollama library.** 768-dim, 8192 context, Apache-2.0, prefix-free — it would dominate this entire comparison as a single model if it were servable (§3).

---

## 10. Consequences for the map

### #16 is unchanged, and the reason is worth recording

**`vector(1024)` stands. No amendment needed.** Retaining `bge-m3` means #16's provisional adoption was correct on both properties it cited — prefix-free (verified against the card and the packaged Modelfile) and 8192 context (verified reachable, §2). One addition:

- **`options.num_batch: 8192` must be passed on every `/api/embed` call**, alongside the `truncate: false` #18 already mandates. Without it the usable window is 2048, not 8192. This is a client-side constant, not a schema change, and it belongs next to `truncate: false` wherever that is set. It costs 276 MB of resident VRAM (664 MB → 940 MB, §5).
- Dimension remains a free variable in the mechanism, exactly as #16 argued. Worth noting that had the recommendation gone the other way, **`qwen3-embedding:0.6b` is also 1024-dimensional** — so #16's expected blast radius of "one number in one column type" would in fact have been **zero numbers**: the column type is identical. #16's dimension-agnosticism was never tested by this ticket and remains untested.

### #18's measured ceiling should be corrected from 2048 to 8192

This is the largest downstream consequence, and it improves things. #18 §5 records *"The embedding ceiling is 2048 tokens, not 8k"* and §6 builds `capture_entry`'s rejection path on it, accepting the cost that *"~2048 tokens is ~1,400 words of prose."* With `num_batch: 8192` the ceiling is **8192 tokens, ~5,600 words** — a 4× increase, for one runtime option and 276 MB.

What that changes:

- **The configured limit in `/etc/tome/tome.env`** (#18 §6 puts *"the embedding model's measured effective context"* there) becomes 8192 rather than ~2048. #18 anticipated exactly this — *"so a runtime upgrade can raise it without a code change"* — and the mechanism works as designed; it just turns out the raise was available immediately.
- **#18's character-limit table rescales** by 4×: prose ~34,700 chars, terse fragments ~23,700, JSON/code ~17,300, URLs/ids ~19,000. The observation that a character limit cannot be tight still holds.
- **#18's "the two thresholds collapse to one" conclusion needs re-checking.** It rested on capture being capped near 2048 while the enrichment budget is ~10k usable, making *"an entry can never be too large to enrich, because it could never have been captured."* At 8192 the margin is much thinner: an 8192-token entry against a ~10k enrichment budget leaves ~1.8k for prompt and output, and #18 measured ~1.5k of output. **The oversize-at-enrichment case may become reachable again**, which would reinstate the #14 tombstone justification #18 retired. This needs deciding before the limit is raised, and it is a decision, not a research finding — flagged for #18 rather than settled here.
- #18's note that *"both candidate embedders declare 8192 natively, so this is a runtime artifact"* was right about the cause and wrong about it being unavoidable.

### #8's embedding recommendation should be marked superseded

#8 chose `nomic-embed-text` and its research file states *"Ollama's packaged version defaults to a 2K context window in its Modelfile, while the underlying model supports up to 8192 tokens."* **This is backwards**: the packaged Modelfile sets `num_ctx 8192` and the *GGUF* declares 2048, and the `min()` in §2 means 2048 wins. Combined with the mandatory two-sided prefixes #8 never mentioned, `nomic-embed-text` is disqualified on two independent grounds. #12 still names it in the two-phase run description and should be updated to `bge-m3`.

### #15's VRAM budget is confirmed, with a better number

#15's pinning of the embedder at `keep_alive=-1` is safe: measured 74% of VRAM with `bge-m3` co-resident with `qwen3:14b` at 16k context, both fully on GPU (§5). Two refinements: `qwen3:14b` is **10 GB resident** at `num_ctx: 16384`, not the 9.3 GB download figure #8 used; and #15's `OLLAMA_CONTEXT_LENGTH=32768` is inert on the embed path (§2) — harmless, but it is not doing the job it looks like it is doing.

---

## 11. Risks, caveats and open questions

- **The retrieval-quality question is not closed, and this ticket's recommendation is a decision under genuine uncertainty.** The honest summary is that no candidate is decisively better at Tome's task, and the incumbent wins on the unambiguous criteria. If retrieval quality later proves inadequate in practice, `qwen3-embedding:0.6b` is the designated challenger and `embeddinggemma:300m` the one to try if criterion 2 relaxes. Both swaps are cheap — same-or-smaller dimension, no ANN index, and #12's full re-run already exists as the mechanism.
- **There is no retrieval-quality telemetry, which is what makes all of this hard to settle.** #16 chose exact search partly to keep the mechanism simple, and nothing in the map measures whether `search_entities` returns good results. **Any embedder comparison on real data is currently impossible**, and that — not the model choice — is the gap most worth closing. A minimal version would log the query, the returned ids and their scores, letting a later ticket replay a real query set against a candidate model. Recommend raising this as its own ticket; it is a precondition for ever revisiting this decision on evidence rather than proxies.
- **`num_batch: 8192` is undocumented behaviour and could change.** It is not in [docs.ollama.com/api/embed](https://docs.ollama.com/api/embed.md), and the clamp it works around sits next to a `TODO @nicolepardal` in Ollama's source. A future Ollama release could fix the clamp (making the option unnecessary), change the default batch (making it unnecessary or insufficient), or regress. **Pin the Ollama version, and re-run the ceiling probe after any upgrade** — the failure mode is a `400` on entries that used to capture fine, which is loud, but it would break capture until noticed.
- **A live Ollama bug makes `truncate: true` unreliable.** [ollama#14186](https://github.com/ollama/ollama/issues/14186) (opened 2026-02-10, **still open**, PR #14230 unmerged) reports that oversized input can hard-fail even with `truncate: true`, because truncating to `ctxLen` and re-tokenising can exceed `ctxLen` again — reported specifically for multilingual text and emoji. Tome mandates `truncate: false` anyway so this is not a live hazard, but it does mean the "silent truncation" default #18 measured is not even reliably a truncation, and nothing should depend on that path.
- **The current Ollama is v0.32.4** (published 2026-07-25); all measurements here are on **0.32.1**, the version #18 measured on. Close enough to treat as current, but the one-patch gap is unverified.
- **`bge-m3`'s sparse and ColBERT heads are unreachable through Ollama** (§3). If hybrid retrieval ever looks attractive, that is a runtime decision that reopens #8, not a model swap.
- **`granite-embedding-english-r2` is the model to watch.** 149M params, 768 dim, 8192 context, Apache-2.0, prefix-free, best MTEB(eng, v2) Retrieval in this set — it would satisfy criteria 1, 2, 4 and 5 more cleanly than anything actually available. It is blocked solely on not being in the Ollama library. Worth re-checking; it has never been evaluated on LMEB, so its standing on Tome's real workload is unknown.
- **`qwen3-embedding` tag hazard, recorded in case it is ever adopted:** `qwen3-embedding:latest` resolves to the **8B** model (4.7 GB), not 0.6B. Also its default `num_ctx` of 32768 costs 4.0 GB resident, so `num_ctx` must be pinned *down* — the opposite of the tuning every other model here needs.
- **Vendor prefix strings contain inconsistencies that will bite whoever implements them.** Qwen publishes `Query:` and `Query: ` (with and without trailing space) on the same card; `mxbai`'s card does the same with its query prompt. EmbeddingGemma's document prompt contains the literal word `none` that a real title substitutes into. If a prefix is ever adopted, copy it from the model's shipped `config_sentence_transformers.json`, not from card prose.
- **All LMEB comparisons are against HF reference checkpoints, not the artefacts Ollama actually serves.** LMEB evaluated the upstream models at their reference precision and pooling; Tome would run Ollama GGUF conversions. Precision is now checked (§8) and the `bge-m3`/`embeddinggemma` comparison is clean at fp16/bf16 — but **pooling is not verified**. `bge-m3`'s GGUF declares `pooling_type = 2` (CLS) which matches its card, and `nomic`'s declares `1` (mean) which also matches; I did not confirm the others against their reference implementations, and a pooling mismatch in a GGUF conversion would silently change results. Any published score for any of these models should be treated as approximate for this stack.
- **LMEB itself is unrefereed and statistically weak.** Every correlation it reports is insignificant at n=15 (CIs ≈ −0.60 to +0.44). It is the best-shaped published evidence available and it is not strong evidence. Treated accordingly in §8.
- **Corpus padding raises task difficulty, not statistical power.** §6.1's padded run makes the retrieval task realistically hard — a gold summary must beat ~N plausible negatives rather than 39 — which spreads the scores and makes real differences easier to see. But the paired bootstrap is still over the same 40 (or 40 + generated) queries, so **the power of the model-vs-model comparison is set by the number of queries, not the size of the corpus.** Padding fixes on-distribution realism; it does not turn n=40 into n=2000. This distinction is easy to conflate and worth stating plainly.
- **Not measured: real-corpus scale effects.** All retrieval evidence here is on ≤40-document (mine) or benchmark-scale (LMEB) pools. How ranking behaves over a few thousand Tome entities, where #12's deliberately-coarse Person and Project keys create hub entities with long merged summaries, is unknown. Long merged summaries also interact badly with CLS pooling — §2's dilution measurement showed a single sentence contributing +0.02 cosine within a 6689-token document — which is a mild argument that entity summaries should stay short, and a question for whoever owns merge behaviour.
- **Models pulled onto this machine during the research** (`qwen3-embedding:0.6b`, `embeddinggemma:300m`, `granite-embedding:278m`, `snowflake-arctic-embed2`, `nomic-embed-text`, `qwen3:14b`) total ~13 GB of disk and can be removed with `ollama rm` if not wanted. `bge-m3` and `qwen3:14b` are the two the map actually calls for.
