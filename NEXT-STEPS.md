# Next steps — handoff, updated 2026-07-27 (overnight session)

Written to survive a context clear. Read this first; it should make re-deriving anything unnecessary.

## Where things stand

The v1 PRD is **complete and closed** ([`PRD.md`](./PRD.md), 14 sections; wayfinding map #1 and assembly #27 both closed). On top of it, spike #32 decided to **move Tome to the on-device MacBook** (M4 Pro, 48 GB) — settled, not open, reasoning in #32's closing comment. Keep `qwen3:14b`; storage ~11.7 GB against ~15 GB available.

Since the previous handoff, the three Fedora-side obligations have been worked. **Two are measured and waiting on you; one is mid-run.** The MacBook items (#33) are being run concurrently on that machine.

## Repo state

- Branch **`spike/macos-target`**, pushed, **not merged to main**. Merging remains an open item.
- `research/macos-spike-*.md` — five area documents plus `macos-spike-synthesis.md` (read its correction block first; the original verdict there is withdrawn).
- `research/34-adversarial-verification.md` — #34's three claims checked against primary sources.
- `research/ladder-probe/` — the instrument, now substantially larger than the previous handoff described. See "The instrument" below.

## Open issues

| # | What | State |
|---|---|---|
| **#33** | MacBook on-machine confirmations | **Running on the Mac, concurrently** |
| **#34** | `source` provenance may arrive `None` | **Verified.** Decisions open; one has a deadline |
| **#35** | §13.4's 0.7 confidence threshold measures as inert | **Instrument built, probe running.** Decision open |
| **#36** | The unfenced entity types are the confusion sinks | **Measured, PASS.** Wording ratification open |

## What's waiting for you, in the order I'd spend it

### 1. The `mcp` version bound — closed on the Mac, but ⚠ **not pushed**

**Stable `mcp` 2.0 and the final 2026-07-28 protocol both land 2026-07-28.** The SDK's own README tells dependants to add `<2` *before* it lands, because on 2.x `mcp.server.fastmcp` **does not exist** and `client_params is None` is a served outcome no server-side setting can prevent.

The concurrent MacBook session reports having created **`pyproject.toml` with `mcp>=1.28,<2`** and closed this item (#34 comment, 2026-07-27).

**⚠ As of this writing that file is on no remote branch.** Checked every branch on `origin`: `pyproject.toml` does not exist on any of them. It is presumably an unpushed local commit on the Mac. **Push it** — this is the single most time-boxed artifact in the project and it currently exists on one machine.

Note the bound carries its own clock in the other direction: `mcp` 1.x caps at protocol 2025-11-25, so a 1.x Tome will refuse a client that opens with a modern envelope.

### 2. #36's wording — ratify, don't grill

The fence is measured and passes every pre-registered threshold. The proposed `CONTEXT.md` diff is in [`research/ladder-probe/FENCE-FINDINGS.md`](./research/ladder-probe/FENCE-FINDINGS.md), written in the glossary's register and **deliberately not applied**.

One judgement rides with it: **the fence costs ~0.9 pp coverage at 14b, consistently** — the fenced condition sits below the control's worst run. The pre-registered bound accepted that in advance; you may not. You now have the number rather than an opinion.

Note I **declined #36's Person `_Avoid_` line** on evidence: Person is not a confusion sink, and its arrivals in the ticket were omissions misscored as misclassifications.

### 3. #35 — evidence landing overnight

The probe is running. Whatever it returns, one finding is already fixed and it reshapes the ticket: **`considered_types` is gated on the very threshold that never fires** (`prompt.txt`: *"if your confidence is below 0.7 … record the alternatives"*). #35 item 2 proposes `considered_types` as the *alternative* to the numeric threshold, and as specified the two are coupled by construction — the alternative could not be observed while the thing it replaces gates it. Hence the gated/unconditional prompt axis in the run.

### 4. #34's remaining decisions — alongside #33

What `source` records when client info is absent, whether the column earns its place on a single-device install, and the consequence for §7.5's stateful-sessions argument. Unchanged by tonight except that the **provenance risk is low**: no client examined can omit `clientInfo`. **M4** — whether Claude Desktop omits it — is the one open input, and Gate A on the Mac answers it for free.

## Measured facts — do not re-derive these

**Capture path, Fedora, `bge-m3`, `num_batch: 8192`, against §4.5's 5,000 ms budget:** ceiling-size entry (1,839 tok) warm **184 ms**; cold incl. load **1,261 ms**; query embed **87 ms**. ~27× headroom.

**Ladder probe (8 paired draws of 40):** `qwen3:14b` 1.01 ent/subj, 99.1% coverage, 41 tok/s. `qwen3:4b` 0.95, 92.5%, 95 tok/s, **7.5% of subjects produce no entity**. `qwen3:8b` worst rung, unusable in both decoding configs.

**The fence (#36), `qwen3:14b`, three independent runs per condition:** `Event → Fact` **4.7 [3–6] → 1.0**, ranges non-overlapping; type accuracy **96.8% → 97.7%**; coverage **98.4% → 97.5%**. At `qwen3:4b` (directional only — see traps): `Event → Fact` 9.3 → 2.0, accuracy 91.1% → 92.6%.

**#36's real error structure, corrected:** 36 real misclassifications, not the ticket's 31 — **Fact 17, Project 11, Preference 3, Decision 2, Event 2, Commitment 1, Person 0.** Plus 10 omissions that the original scheme miscounted as misclassifications, 8 of them landing on Person.

**#34, verified against primary sources 2026-07-26:** v1.28.1 matches §7.5 exactly (confirmed in source *and* by running it). Spec PR #3002 merged 2026-07-16, `clientInfo` optional, still draft-only, released revision still 2025-11-25. The "on main (2.0.0b2)" attribution is **wrong** — the behaviour post-dates the published beta, which *rejects* a `clientInfo`-less request with `-32602`. And the prior research's "structurally unreachable on stdio" is **false**: `serve_dual_era_loop` builds a fresh `Connection` per request for a modern client, reproduced over real pipes.

## Traps that cost time — the list grew tonight

- **The probe is not reproducible.** An unchanged prompt moved `Event → Fact` by 3 with nothing changed but the wall clock. `temperature: 0` and a fixed `seed` fix sampling, not kernel scheduling, and `keep_alive: 0` reloads the model every call. **Never read a single run as a measurement.**
- **Determinism is model-dependent.** `qwen3:4b` reproduces **bit-exactly** within a session; `qwen3:14b` does not. Replicate *files* are not replicate *observations* — **hash the payloads** before treating replicate count as sample size. This silently turned three 4b runs into one.
- **`considered_types` is gated on the 0.7 threshold** in the prompt, so it could never have been observed populated. A field's absence may be an instruction rather than a behaviour.
- **`format: "json"` induces degeneration** — previously `qwen3:8b`, now also `4b` under a ~150-token-longer prompt (cap hit, 1 entity from 40). Per-model hazard, not a free safety net.
- **Scoring schemes conflate omission with misclassification.** Letting one emitted entity match several subjects lets a *missing* entity score as a *wrong* one. Cost: the entire Person finding in #36.
- **Worked examples in a prompt must not quote the corpus** — that is teaching to the test, the defect #24's prompt had. Check it mechanically.
- **`OLLAMA_KEEP_ALIVE=24h`** is set in the drop-in; pass `keep_alive: 0` per request rather than editing the unit (which would need sudo).
- **Three JSON envelope shapes** across one model family; `analyze.py`'s `entities_in()` handles all three.
- **Agents anchor to numbers without checking provenance.** Three instances now: two in #32, and #36's confusion table, which did not reproduce.
- **`sudo` can't prompt from inside the harness** — no TTY. **None of the remaining Fedora work needs it.**
- **Concurrent GPU jobs corrupt runs** — `raw-contended.jsonl.bak` is the retained evidence. Serialize everything on this box.

## The instrument (`research/ladder-probe/`)

| file | what it is |
|---|---|
| `corpus.py` | 80 unambiguous subjects with ground-truth types |
| `corpus_ambiguous.py` | **new** — 100 subjects, 4 strata: 40 ambiguous, 20 length-matched controls, 24 short controls, 16 quarantined on the fence boundaries |
| `prompt.txt` / `prompt-fenced.txt` | control and fenced extraction prompts |
| `prompt-unconditional.txt` / `prompt-fenced-unconditional.txt` | **new** — `considered_types` ungated |
| `run.py` | the runner. `PROMPT`, `OUT`, `ARMS`, `FORMAT`, `CORPUS` env switches; defaults reproduce the original run exactly |
| `analyze.py` | recall and composition |
| `type_accuracy.py` | **new** — classification against ground truth. The instrument never had this |
| `compare_fence.py` / `compare_replicates.py` | **new** — paired A/B, and repeated-measures with degenerate-draw handling |
| `confidence.py` | **new** — #35: per-stratum confidence, split-half placebo band, `considered_types` specificity, trigger sweep |
| `CRITERIA.md` | pre-registration, **five amendments** — read 4 and 5 before trusting any replicate count |
| `CONFIDENCE-CRITERIA.md` | **new** — #35 pre-registered |
| `FENCE-FINDINGS.md` | **new** — #36's result |
| `AMBIGUOUS-CORPUS.md` / `CONFIDENCE-SCORING.md` | **new** — corpus design and scorer reading guide |

## Things deliberately not done

- **`PRD.md` is untouched.** Revising it for the on-device deployment follows #33.
- **`CONTEXT.md` is untouched.** The #36 wording is a domain call and is yours to ratify.
- **No ticket has been closed.** #34, #35 and #36 all still carry open decisions, and the plan says to spend them in one pass rather than three.
- **No `pyproject.toml`.** See item 1 — the pin is right, but creating it starts the build.
- The remaining #32 harvest items stay unticketed until relevant: the Tome-owned-logfiles change (revises #26), awake-time staleness measurement, `initdb --locale-provider=builtin`, the reproducibility-is-a-runtime-question finding, and the `chattr +C`/compression correction.
