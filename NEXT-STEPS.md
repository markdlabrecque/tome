# Next steps — handoff, updated 2026-07-27 (overnight session)

> ## ⚠ READ FIRST — one thing is in flight and it blocks a ratification
>
> **The Fedora box was upgraded Ollama 0.32.1 → 0.32.4** (2026-07-27, to settle a #33
> question — it settled it: the version is not the explanation for the 2.34x warm ratio).
> **The fenced arm re-run on 0.32.4 no longer looks fenced:** `Event -> Fact` **1,1,1 -> 3**,
> errors 7 -> 10, accuracy 97.7% -> 96.8%. Every one of those falls inside the **0.32.1
> control's** range (`Event -> Fact` 3-6, errors 9-11, accuracy 96.5-97.1%).
>
> **This is not yet a conclusion** — it compares 0.32.4-fenced against 0.32.1-control, which
> confounds runtime with condition (the fourth amendment's exact error), and it is n=1.
>
> **A within-runtime A/B was launched:** 2 control + 2 more fenced arms on 0.32.4. It writes
> into **this worktree, not the main checkout**:
> `.claude/worktrees/gate-b-doc-correction/research/ladder-probe/raw-{control,fenced}-ollama0324*.jsonl`.
> `run.py` is resumable — re-run the same command and it skips completed `(model, seed)` pairs.
> From `research/ladder-probe/`:
>
> ```
> PROMPT=prompt.txt        OUT=raw-control-ollama0324.jsonl    ARMS=qwen3:14b FORMAT=json python3 run.py
> PROMPT=prompt.txt        OUT=raw-control-ollama0324-r2.jsonl  ARMS=qwen3:14b FORMAT=json python3 run.py
> PROMPT=prompt-fenced.txt OUT=raw-fenced-ollama0324-r2.jsonl   ARMS=qwen3:14b FORMAT=json python3 run.py
> PROMPT=prompt-fenced.txt OUT=raw-fenced-ollama0324-r3.jsonl   ARMS=qwen3:14b FORMAT=json python3 run.py
> ```
>
> **Consequence: hold #36's `CONTEXT.md` wording ratification** until this lands. Posted to #36.
> If the 0.32.4 control also lands near 3, #36's PASS was a property of Ollama 0.32.1. Nothing
> else in #36 is affected — the corrected error structure, the declined Person fence, and the
> Fact-share finding all stand independently of runtime.
>
> **The lesson worth keeping either way:** a runtime upgrade *is* a Derivation Epoch change,
> and this project had no mechanism that would have noticed. Same class as #17's
> embedding-digest argument, now with a worked example.
> `research/ladder-probe/PROVENANCE.md` stamps every pre-upgrade result as 0.32.1 with model
> digests; `run.py` now self-stamps every record.

Written to survive a context clear. Read this first; it should make re-deriving anything unnecessary.

## Where things stand

The v1 PRD is **complete and closed** ([`PRD.md`](./PRD.md), 14 sections; wayfinding map #1 and assembly #27 both closed). On top of it, spike #32 decided to **move Tome to the on-device MacBook** (M4 Pro, 48 GB) — settled, not open, reasoning in #32's closing comment. Keep `qwen3:14b`; storage ~11.7 GB against ~15 GB available.

Since the previous handoff, **all three Fedora-side obligations have been worked and are measured.** Every remaining step on them is a decision, not a measurement. The MacBook items (#33) are being run concurrently on that machine.

## Repo state

- Branch **`spike/macos-target`**, pushed, **not merged to main**. Merging remains an open item.
- `research/macos-spike-*.md` — five area documents plus `macos-spike-synthesis.md` (read its correction block first; the original verdict there is withdrawn).
- `research/34-adversarial-verification.md` — #34's three claims checked against primary sources.
- `research/ladder-probe/` — the instrument, now substantially larger than the previous handoff described. See "The instrument" below.

## Open issues

| # | What | State |
|---|---|---|
| **#33** | MacBook on-machine confirmations | **Both gates PASS.** ⚠ Evidence unpushed; some items uncovered |
| **#34** | `source` provenance may arrive `None` | **Verified.** Decisions open; one has a deadline |
| **#35** | §13.4's 0.7 confidence threshold measures as inert | **Measured.** Both mechanisms fail. Decision open |
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

### 3. #35 — measured. Both candidate mechanisms fail

⚠ **The same runtime caveat applies in principle** — every #35 arm was measured on Ollama 0.32.1. Its headline results are far more robust to it than #36's, because they are *floors* rather than small differences: `considered_types` empty across ~2,950 entities and three wordings, and no threshold within 30 points of the 50% bar. A runtime shift would have to be enormous to move those. Not re-measured; noted.

Full result in [`research/ladder-probe/CONFIDENCE-FINDINGS.md`](./research/ladder-probe/CONFIDENCE-FINDINGS.md). **Verdict: abandon the numeric route; `considered_types` is not adoptable as measured.**

- **Ambiguity is weakly detectable but not thresholdable.** Separation −0.013 to −0.015, replicated, outside the placebo floor, and measured against *length-matched* controls so it is not the sentence-complexity confound. But the best cut anywhere across eight arms catches **21.7%** against a pre-registered 50% bar, and `< 0.9` at 14b fires on 12.7% of unambiguous short controls to catch 14% of ambiguous ones.
- **§13.4's 0.7 is dead:** zero of ~2,350 entities below it in seven of eight arms.
- **The number is an artifact of the prompt asking for it.** Remove the clause naming 0.7 and 14b returns **exactly 1.000 on every entity in every stratum**. A self-report whose range collapses when you reword the request is not measuring the input.
- **`considered_types` is emitted on every entity and is always `[]`** — verified in the raw payloads, not inferred. Overall fire rate 15 of ~2,350 (0.6%), none on the ambiguous stratum.
- **Item 4 is answered decisively, and it changes a behaviour the PRD believes it has.** Confidences occupy `{0.8, 0.9}` under the shipped prompt, so §3.3's *incumbent + 0.20* override is unreachable: **type stickiness is absolute, not a tunable margin.** An Entity can never be re-typed by a later extraction.
- **Interaction with #36:** the fence raises separation slightly (−0.0175) and produced the only sub-0.7 confidences in the study (4b, 7.3%). Weak, one observation, but it means adopting the fence makes this channel marginally *less* useless — worth knowing before deciding whether the column survives.

**Loose end closed rather than left open:** my unconditional rewrite produced *fewer* fires than the gated prompt (zero), which the pre-registration did not anticipate and which pointed at my own wording rather than the model. A third wording — `prompt-forced.txt`, opt-out removed, schema hint changed off *"…if any"* — was run to settle it. **Also 0.0%, both models, 608 paired entities.** Three wordings, ~2,950 entities, empty on all of them: the failure is not an artifact of how it was asked for.

### 4. #34's remaining decisions — M4 is now answered

What `source` records when client info is absent, whether the column earns its place on a single-device install, and the consequence for §7.5's stateful-sessions argument.

**M4 is closed.** Claude Desktop sends `{"name": "claude-ai", "version": "0.1.0"}` over stdio. So no client omits client info and the provenance risk stays **low** — confirming the Fedora assessment. But two properties make `source` weaker than its name suggests:

- **`version` is a placeholder.** The app is 1.24012.9 and announces `0.1.0` — which is also python-sdk's fallback string, so it is doubly uninformative. Nothing can be gated on it.
- **`name` is `claude-ai`, not `claude-desktop`.** It separates Desktop from `claude-code` and from nothing else. `source` carries a real but **coarser** bit than #13 assumed.

**Correction to my own earlier claim.** The #34 verification said a server-minted process-lifetime UUID still works as a replacement for the absent `session_id`. Gate A shows that UUID has **three different grains depending on entry point**: per-app-launch (Desktop stdio), per-session (Claude Code stdio, fresh PID each `claude -p`), and **per-server-lifetime on the loopback HTTP path — one PID served 8 sessions over 944 s.** Since HTTP is the chosen path for Claude Code, a process UUID collapses to a single value across every session there, so §3.8's fallback-judgement signal gets **no session grain on that path either**. The proposed fix is weaker than I stated and §3.8 needs a different mechanism or needs to lose the claim.

### 5. New decisions the MacBook surfaced

- **No off-device backup exists.** `tmutil destinationinfo` reports **no destinations configured**. This contradicts a PRD *assumption* rather than a number — §8.2's backup set and #33's "backups off-device, so the seven-dump rotation does not land here" are both currently unsupported. Needs hardware or an explicit decision.
- **Pin `OLLAMA_FLASH_ATTENTION` and `OLLAMA_KV_CACHE_TYPE` explicitly.** On the Mac they arrived from Homebrew's LaunchAgent rather than from a decision.
- **Claude Desktop never restarts a dead stdio server.** `kill -9` → `Server disconnected` in the log and nothing else; 90 s at zero processes, a new chat window did not respawn, only an app relaunch recovered. Combined with per-app-launch lifetime, **one crash silently costs the rest of that launch.** The stdio entry point must be effectively unkillable — no exception escaping to top level, no fatal path on a Postgres connection failure. That is a design constraint, not a checklist item.

## Measured facts — do not re-derive these

**Capture path, `bge-m3`, `num_batch: 8192`, against §4.5's 5,000 ms budget** — Fedora, then MacBook (M4 Pro, 16 GPU cores):

| | Fedora | Mac | ratio |
|---|---|---|---|
| ceiling-size entry (1,839 tok), warm | 184 ms | **447 ms** (n=25, sd 5.7) | 2.43× |
| same, cold incl. load | 1,261 ms | **1,376 ms** | 1.09× |
| query embed, warm | 87 ms | **99 ms** | 1.14× |

**Gate B PASS: 11.2× headroom warm, 3.6× on a cold first capture**, worst single observation 1,587 ms.

⚠ **One caveat in the Mac report is wrong, and it matters.** It states Fedora lacked `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`, and concludes every Mac-vs-Fedora ratio in the project is therefore not a pure hardware comparison. **Verified on this box: Fedora has both**, in `/etc/systemd/system/ollama.service.d/90-pi-local-rocm.conf`, mtime **2026-07-22** — before any benchmarking in this project. The flags are common to both machines and the comparison stands. The warm ratio does overshoot #32's projected 1.83–2.22× band at 2.43×, but that needs a different explanation.

**Ladder probe (8 paired draws of 40):** `qwen3:14b` 1.01 ent/subj, 99.1% coverage, 41 tok/s. `qwen3:4b` 0.95, 92.5%, 95 tok/s, **7.5% of subjects produce no entity**. `qwen3:8b` worst rung, unusable in both decoding configs.

**The fence (#36), `qwen3:14b`, three independent runs per condition:** `Event → Fact` **4.7 [3–6] → 1.0**, ranges non-overlapping; type accuracy **96.8% → 97.7%**; coverage **98.4% → 97.5%**. At `qwen3:4b` (directional only — see traps): `Event → Fact` 9.3 → 2.0, accuracy 91.1% → 92.6%.

**#36's real error structure, corrected:** 36 real misclassifications, not the ticket's 31 — **Fact 17, Project 11, Preference 3, Decision 2, Event 2, Commitment 1, Person 0.** Plus 10 omissions that the original scheme miscounted as misclassifications, 8 of them landing on Person.

**#34, verified against primary sources 2026-07-26:** v1.28.1 matches §7.5 exactly (confirmed in source *and* by running it). Spec PR #3002 merged 2026-07-16, `clientInfo` optional, still draft-only, released revision still 2025-11-25. The "on main (2.0.0b2)" attribution is **wrong** — the behaviour post-dates the published beta, which *rejects* a `clientInfo`-less request with `-32602`. And the prior research's "structurally unreachable on stdio" is **false**: `serve_dual_era_loop` builds a fresh `Connection` per request for a modern client, reproduced over real pipes.

## Traps that cost time — the list grew tonight

- **The probe is not reproducible.** An unchanged prompt moved `Event → Fact` by 3 with nothing changed but the wall clock. `temperature: 0` and a fixed `seed` fix sampling, not kernel scheduling, and `keep_alive: 0` reloads the model every call. **Never read a single run as a measurement.**
- **Determinism varies by the whole configuration — model × prompt × corpus — and is not predictable from any part of it.** `qwen3:4b` reproduces bit-exactly; `qwen3:14b` does not on the control prompts but *does* on the fenced ones, which is the opposite of what it did on `corpus.py`. Replicate *files* are not replicate *observations* — **hash the payloads** before treating replicate count as sample size. This silently turned three 4b runs into one. (`CRITERIA.md`, fifth and sixth amendments.)
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
| `prompt-forced.txt` | **new** — third `considered_types` wording; also 0.0% |
| `confidence.py` | **new** — #35: per-stratum confidence, split-half placebo band, `considered_types` specificity, trigger sweep |
| `CRITERIA.md` | pre-registration, **five amendments** — read 4 and 5 before trusting any replicate count |
| `CONFIDENCE-CRITERIA.md` | **new** — #35 pre-registered |
| `FENCE-FINDINGS.md` | **new** — #36's result |
| `CONFIDENCE-FINDINGS.md` | **new** — #35's result |
| `AMBIGUOUS-CORPUS.md` / `CONFIDENCE-SCORING.md` | **new** — corpus design and scorer reading guide |

## Things deliberately not done

- **`PRD.md` is untouched.** Revising it for the on-device deployment follows #33.
- **`CONTEXT.md` is untouched.** The #36 wording is a domain call and is yours to ratify.
- **No ticket has been closed.** #34, #35 and #36 all still carry open decisions, and the plan says to spend them in one pass rather than three.
- **No `pyproject.toml`.** See item 1 — the pin is right, but creating it starts the build.
- The remaining #32 harvest items stay unticketed until relevant: the Tome-owned-logfiles change (revises #26), awake-time staleness measurement, `initdb --locale-provider=builtin`, the reproducibility-is-a-runtime-question finding, and the `chattr +C`/compression correction.
