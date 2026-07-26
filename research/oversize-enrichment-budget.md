# Issue #24 — Step 0 findings (measured 2026-07-26, this machine)

Ollama 0.32.1, `qwen3:14b` Q4_K_M, `bge-m3`, RX 6900 XT / 15.98 GiB, `num_ctx: 16384`
per request, thinking disabled, `temperature: 0`. KV cache is `q8_0`-quantised
(`--cache-type-k/v q8_0 --flash-attn on`), which the VRAM figures below depend on.

## What #17 actually delivered against #24's two asks

#24 asked #17 for (1) the committed prompt's token count and (2) a bound on prompt size.
**Neither exists.** #17 settled the prompt's *home* — in the `tome` package, identity =
hash of the rendered text, resolved once at run start (so per-run, not per-entity) — and
said nothing about size. So the prompt budget is #24's to set.

## The prompt: P = 1215 tokens

A faithful prompt built from CONTEXT.md's 8 entity types + `_Avoid_` lines verbatim (#12's
requirement) plus #12's output contract (`entity_type` / `natural_key` / `summary` /
`type_confidence` / `considered_types`) and the Type-Suggestion rules:

- **1215 qwen3 tokens** including chat template (5091 chars, 768 words).
- 1412 bge-m3 tokens for the same text — tokenizers differ, see ratio below.

**#15's assumption of ~3–6k was 2.5–5× too high.**

## Tokenizer ratio: qwen3 = 0.906 x bge-m3

Measured across five entry sizes (`prompt_eval_count` minus P, against `count_tokens`):

| entry (bge-m3) | qwen3 contribution | ratio |
|---|---|---|
| 620 | 547 | 0.882 |
| 1119 | 1009 | 0.902 |
| 2071 | 1878 | 0.907 |
| 4036 | 3640 | 0.902 |
| 8009 | 7257 | 0.906 |

This matters structurally: **the capture gate measures in bge-m3 tokens (#18's embed
oracle) but the enrichment budget is spent in qwen3 tokens**, and the gate is ~10%
conservative. An 8192-bge-token entry is ~7420 qwen3 tokens.

## Item 4 — the generate path truncates SILENTLY, and drops the front

The most important measurement. Prompt deliberately over `num_ctx`, canary planted at the
front, question at the back:

| num_ctx | sent (tok) | `prompt_eval_count` | ratio | canary survived |
|---|---|---|---|---|
| 2048 | 741 | 756 | — | yes |
| 2048 | 1461 | 1476 | — | yes |
| 2048 | 2421 | **1026** | 0.501 | **no** |
| 2048 | 4821 | **1026** | 0.501 | **no** |
| 4096 | 4824 | **2050** | 0.500 | **no** |
| 4096 | 9627 | **2050** | 0.500 | **no** |
| 8192 | 24040 | **4098** | 0.500 | **no** |
| 16384 | 24040 | **8194** | 0.500 | **no** |
| 16384 | 48055 | **8194** | 0.500 | **no** |

**Retention is exactly `num_ctx/2 + 2` regardless of how much was sent**, and it is the
*tail* that survives. `done_reason` is `"stop"`, there is no `truncated` field, no error,
no warning. This is llama.cpp context-shift (`--context-shift --keep 4`, which Ollama
passes unconditionally; there is no `OLLAMA_*` env var to disable it — checked
`ollama serve --help` and the binary's strings).

Consequences:

1. It is a **cliff, not a slope**: one token over the budget does not cost one token, it
   costs everything but the last ~50% of `num_ctx`.
2. Because Tome's prompt puts instructions first and the entry last, what gets discarded
   is **the entire instruction block** — type definitions, `_Avoid_` rules, output
   contract — while the entry tail survives. The model is then asked to extract with no
   instructions.
3. It would be recorded as success: `enrichment_state` = `enriched`.
4. **But it is detectable.** `prompt_eval_count` is returned, so the runner can compare it
   against an expected count. The `== num_ctx/2 + 2` signature is exact.

The right guard is nevertheless **pre-flight arithmetic**, not post-hoc detection: the
entry's token count is known at capture (#18's oracle) and P is known at run start, so
`P + entry*0.906 + reserve <= num_ctx` is checkable with no model call.

## Item 3 — VRAM and placement at num_ctx 16384

| state | VRAM used | of 15.98 GiB |
|---|---|---|
| no models (desktop only) | 0.90 GB | 5.6% |
| `qwen3:14b` @16384 + `bge-m3` @8192, both resident | **13.12 GB** | **76.4%** |

Both **100% GPU, no spill**. Confirms #22's 74% figure and #15's pinning design. Note this
is with the `q8_0` KV cache; an f16 cache would not fit as comfortably.

## Item 1 — f: output tokens as a function of entry length

Two passes. **Pass 1's top end was invalid** and is discarded: the corpus was only ~3.3k
tokens, so 4k/8k targets cycled and repeated subjects, which the model merges rather than
re-extracts — understating f exactly where it decides the ticket. Pass 2 uses 80 distinct
subject blocks, no repeats.

Pass 2 (2 reps each, `num_predict: -1`):

| subjects in | entry (bge-m3) | `prompt_eval` | output tok | entities | ent/subject |
|---|---|---|---|---|---|
| 4 | 620 | 1762 | 363 / 363 | 4 / 4 | 1.00 |
| 8 | 1119 | 2224 | 946 / 947 | 11 / 11 | 1.38 |
| 16 | 2071 | 3093 | 721 / 1000 | 9 / 14 | 0.56 / 0.88 |
| 34 | 4036 | 4855 | 1467 / 1502 | 17 / 16 | 0.50 / 0.47 |

**f increases, but sublinearly** — roughly `output ~= 350 + 0.28 * entry_tokens`. #18's
~1.5k constant was not wrong by mechanism at small sizes, but it does not hold as a
constant.

Every response parsed as valid JSON. No parse failures at any size.

## The finding that reframes the ticket: recall degrades well below the ceiling

Entities per subject: **1.00 -> 1.38 -> 0.56 -> 0.50**. The fall is between 8 and 16
subjects, i.e. between ~1100 and ~2100 bge-m3 tokens — **far below both 2048 and 8192**.

Qualitatively, at 16 subjects the 9 entities extracted all come from the first ~10 blocks;
Kirsten, the clock-drift fix, the audit-trail preference, Marcus Bell and the `num_batch`
discovery are simply absent. At 34 subjects, 17 entities.

So the budget is safe partly *because* the model stops extracting. The margin is bought
with recall.

## Prompt-example contamination — fabricated entities

Surfaced incidentally while building the prompt. Concrete example `natural_key`s in the
prompt are re-emitted as **entities that the entry does not support**, with confabulated
summaries. Reproducible in 8 of 12 pass-1/pass-2 responses across both passes and all
reps:

- `2026-08-01-send-alex-the-retrieval-report` — summary: *"Promised to send Alex the
  retrieval report by August 1st, as he is expecting his second child and will be off for
  part of the autumn."* The entry says the **opposite** (Alex offered to send *Mark* an
  evaluation harness). The strings "retrieval report" and "August 1st" appear nowhere in
  the entry — both are verbatim from the prompt's example key. The model then welded on a
  real detail (the second child) as justification.
- `2026-07-24-standup-with-alex` — the entry has a standup on the **22nd with Priya** and a
  separate call with Alex. "24" appears nowhere. Verbatim from the prompt's example key.
  It co-exists with the correctly-extracted `standup-on-the-twenty-second`.

**Scope caveat, stated honestly:** this is a placeholder prompt, because no committed
prompt exists. So it is not a defect in shipped work — it is a design constraint on the
prompt #17 chose to ship *unbounded and unvalidated*. A fabricated Commitment in a
memory-keeper does not read as an error; it reads as a memory.

Two lesser prompt defects also observed: `captured_at` used in place of the event's own
date (`2026-07-26-standup-on-22nd`), and "ROCm" mangled to `roc-m` by the
lowercase-hyphenate rule.

## Item 2 — the entry-size ceiling as a curve against P

Using `entry_bge_max = (num_ctx - P - reserve) / 0.906` at `num_ctx: 16384`, with a 1500-
token output reserve (generous against the 1502 max measured at 4k, and see the note
below):

| P (qwen3 tok) | largest entry (bge-m3 tok) |
|---|---|
| 1215 (measured) | ~15,090 |
| 2000 | ~14,220 |
| 3000 | ~13,110 |
| 6000 | ~9,800 |
| **~7,400** | **8192 — the embedder cap finally binds** |

At the projected `f(8192) ~= 2650`, the worst realistic case is
`1215 + 7420 + 2650 = 11,285` of 16,384 — **about 5.1k spare**.

**So oversize-at-enrichment is NOT reachable**, and #18's collapsed threshold survives with
a ~6x margin on today's prompt. The ticket's premise ("the margin goes from ~5x to roughly
nothing") was wrong, because it treated output as a constant 1.5k *and* assumed f rises
fast enough to matter. f rises, but slowly.

## CORRECTION to the f model above, and the real top-end numbers

The `output ~= 350 + 0.28 * entry_tokens` fit was drawn from the <=4k points and does NOT
hold. Full pass-2 data (2 reps, `temperature: 0`):

| subjects | entry (bge-m3) | prompt_eval | output tok | entities | ent/subject | JSON |
|---|---|---|---|---|---|---|
| 4 | 620 | 1762 | 363 / 363 | 4 / 4 | 1.00 | ok |
| 8 | 1119 | 2224 | 946 / 947 | 11 / 11 | 1.38 | ok |
| 16 | 2071 | 3093 | 721 / 1000 | 9 / 14 | 0.56 / 0.88 | ok |
| 34 | 4036 | 4855 | 1467 / 1502 | 17 / 16 | 0.50 / 0.47 | ok |
| 58 | 6046 | 6661 | **4027 / 7628** | 42 / **FAIL** | 0.72 / — | ok / **FAIL** |
| 80 | 7620 | 8110 | 1661 | 20 | **0.25** | ok |

Output tracks **entity count** at ~96 tokens/entity, and entity count is erratic, so f is
not a usable function of entry length. Worst observed total was **14,289 of 16,384** at a
6046-token entry — 2.1k spare, on an entry 26% below the 8192 cap.

### The reachable failure is generation degeneration, not context exhaustion

At 6046 tokens, rep 1 emitted 7628 output tokens and unparseable JSON. The tail:

```
"considered_types": ["Commitment", "Decision", "Preference",意图
```

A stray Chinese token (意图, "intent") mid-array, structure unterminated,
`done_reason: "stop"`, and **total 14,289 < 16,384 so no truncation happened**. The model
degraded on its own under a long generation.

Same input, `temperature: 0`, one rep clean with 42 entities and one rep garbage — so this
is **stochastic**, and an entry in this range is a coin flip.

**This contradicts CONTEXT.md.** Resolution Required is defined as a failure "for a reason
retrying cannot fix — unparseable model output, ...". Unparseable output here is exactly
what a retry fixes. #12's transient/deterministic split therefore mis-buckets its most
likely real failure: it would route a recoverable failure to a human decision.

### Recall degrades, composition is unstable, Decisions do not scale

Entities per subject: **1.00 -> 1.38 -> 0.56/0.88 -> 0.50/0.47 -> 0.72 -> 0.25**.

Composition swings unpredictably rather than degrading monotonically (6046 gave 19 Person
+ 18 Event; 7620 gave 1 Person + 7 Preference + 7 Event). But one pattern is exact:

| entry | total entities | Decision | Project |
|---|---|---|---|
| 620 | 4 | 1 | 1 |
| 1119 | 11 | 1 | 1 |
| 2071 | 9 | 1 | 1 |
| 4036 | 17 | 1 | 1 |
| 6046 | 42 | 1 | 1 |
| 7620 | 20 | 1 | 1 |

The corpus holds **7 decision-shaped blocks**, so expected Decision counts are ~1, 1, 2, 4,
6, 7. Actual is 1 at every size, including the run that found 42 entities. `Project = 1` is
correct (one project, coarse key, merging intended); Decision keys are date-scoped and must
NOT merge. So Decision under-extraction scales with entry length.

Person/Event — name-and-date shaped — are what grow. The analytical content a
memory-keeper exists for is what is lost.

## Runaway generation — the reachable failure (measured after the tables above)

Four runs of the SAME 6046-token entry (58 distinct subjects), `temperature: 0`,
`num_predict: -1`, `num_ctx: 16384`:

| run | JSON | entities | output tok | total | wall |
|---|---|---|---|---|---|
| pass2 rep0 | ok | 42 | 4027 | 10688 | 121 s |
| pass2 rep1 | **FAIL** | — | 7628 | 14289 | 236 s |
| retry rep0 | ok | 43 | 4289 | 10950 | 135 s |
| retry rep1 | **FAIL** | — | **17957** | **24618** | **602 s** |

**2 clean / 2 unparseable, n = 4** — a coin flip on an entry 26% below the 8192 cap.

`retry rep1` is the important one: **total 24,618 against a 16,384 window**, so the
generation ran through the context limit and context-shift fired *mid-generation*, sliding
the window off the instructions and then off the entry. Ten minutes, 18k tokens, nothing
usable — 33x #18's ~18 s/entry baseline.

So the binding failure at large entry sizes is **runaway output**, not prompt-side context
exhaustion. `num_predict: -1` is what permits it.

## The split counterfactual — 2.6x recovery

40 subjects held constant (4525 tokens), varying only how many captures they arrive in:

| as… | entities | distinct keys | per subject | output tok | wall |
|---|---|---|---|---|---|
| 1 entry (4525 tok) | 18 | 18 | 0.45 | 1511 | 42 s |
| 4 entries (~1130 tok) | 41 | 41 | 1.02 | 3558 | 92 s |
| 10 entries (~450 tok) | 36 | 36 | 0.90 | 3631 | 93 s |
| **40 entries (~113 tok)** | **46** | **46** | **1.15** | 5205 | 133 s |

Zero parse failures at any granularity. No interior optimum — the 10-entry dip is inside
this model's run-to-run noise. **46 distinct keys from 40 separate captures, no
collisions**, which is #12's merge-on-natural-key working as designed and the measured
basis for #18's "split and retry" being the better path rather than a consolation.

## Method note

The test corpus was **synthetic** — 80 hand-written subject blocks in the shape of personal
memory entries, with invented names. Per #23 §9 no real memory content was used, and the
corpus itself is deliberately not committed; only the measurements are.
