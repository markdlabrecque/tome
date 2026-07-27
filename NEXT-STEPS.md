# Next steps — handoff, updated 2026-07-27 (overnight session)

> ## ⚠ READ FIRST — the runtime scare is resolved; the ratification is unblocked but harder
>
> **The Fedora box was upgraded Ollama 0.32.1 → 0.32.4** (2026-07-27, to settle a #33
> question — it settled it: the version is not the explanation for the 2.34x warm ratio).
> A fenced-only re-run then looked unfenced, which put #36's wording on hold. **The
> within-runtime A/B is now complete (32 draws, 2 control + 3 fenced replicates on 0.32.4)
> and the scare does not survive it.**
>
> **The fence still separates from its own control on 0.32.4:**
>
> | | 0.32.1 control | 0.32.1 fenced | 0.32.4 control | 0.32.4 fenced |
> |---|---|---|---|---|
> | `Event → Fact` | 4.7 [3–6] | 1.0 | **7.0** | **3.0** |
> | real errors | 10.0 | 7.0 | 11.0 | 10.0 |
> | type accuracy | 96.78% | 97.74% | 96.49% | 96.83% |
> | coverage | 98.4% | 97.5% | 99.1% | 98.8% |
>
> The earlier alarm was the fourth amendment's error in miniature: 0.32.4-fenced (3) was
> being read against the *0.32.1* control (3–6). **The whole distribution shifted** — 0.32.4
> extracts more and types it slightly worse — so 3 is a 4-count reduction from where the
> control now sits, not a null result. All five pre-registered thresholds still pass.
>
> **What genuinely got worse, and it bears on the decision:**
>
> - **Net benefit is now 1 real error per 8 draws** (+0.34 pp accuracy), down from 3
>   (+0.96 pp). The fence removes 4.0 `Event → Fact` and adds 2.0 `Commitment → Decision`
>   plus 1.0 `Commitment → Fact`. The pre-registered relocation check tests the *largest
>   single* increase, not the sum, and would be marginal on the sum — a criterion defect,
>   recorded in `CRITERIA.md`'s **seventh amendment**.
> - **`Commitment → Decision` +2.0 per run replicated exactly on both runtimes.** It is no
>   longer "may be noise"; it is an established side effect of the "rule out every other
>   type" clause.
> - **0.32.4 is bit-deterministic** where 0.32.1 was not: all three fenced replicates are
>   byte-identical, the control identical on 7 of 8 seeds. So each condition carries **one**
>   independent observation and the non-overlap test is formally passed but epistemically
>   empty. The only measured noise floor this project has is 0.32.1's; the −4.0 effect
>   exceeds it, but that floor is borrowed from a runtime this box no longer runs.
> - **The recall cost shrank** from −0.9 pp to −0.3 pp — the open judgement call is cheaper
>   than when it was flagged, and also buying less.
>
> **Consequence: #36's `CONTEXT.md` wording ratification is unblocked and still yours.** The
> wording is not an artifact of 0.32.1. Whether 1 net error per 8 draws, against a known
> +2.0 `Commitment → Decision` side effect, justifies a permanent glossary change is a domain
> call and was deliberately left open. Full write-up: the closing section of
> `research/ladder-probe/FENCE-FINDINGS.md`. Re-derive with
> `cd research/ladder-probe && python3 compare_runtime.py` — it re-scores the 0.32.1 files
> too, and reproduces this document's published baseline table before reporting anything new.
>
> **The lesson worth keeping:** a runtime upgrade *is* a Derivation Epoch change, and this
> project had no mechanism that would have noticed. Same class as #17's embedding-digest
> argument, now with a worked example. `research/ladder-probe/PROVENANCE.md` stamps every
> pre-upgrade result as 0.32.1 with model digests; `run.py` now self-stamps every record.
> **There is still nothing that *fails* when the epoch moves under a committed result.**

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
| **#36** | The unfenced entity types are the confusion sinks | **Measured, PASS on both runtimes.** Wording ratification open |

## What's waiting for you, in the order I'd spend it

### 1. The `mcp` version bound — closed on the Mac, but ⚠ **not pushed**

**Stable `mcp` 2.0 and the final 2026-07-28 protocol both land 2026-07-28.** The SDK's own README tells dependants to add `<2` *before* it lands, because on 2.x `mcp.server.fastmcp` **does not exist** and `client_params is None` is a served outcome no server-side setting can prevent.

The concurrent MacBook session reports having created **`pyproject.toml` with `mcp>=1.28,<2`** and closed this item (#34 comment, 2026-07-27).

**⚠ As of this writing that file is on no remote branch.** Checked every branch on `origin`: `pyproject.toml` does not exist on any of them. It is presumably an unpushed local commit on the Mac. **Push it** — this is the single most time-boxed artifact in the project and it currently exists on one machine.

Note the bound carries its own clock in the other direction: `mcp` 1.x caps at protocol 2025-11-25, so a 1.x Tome will refuse a client that opens with a modern envelope.

### 2. #36's wording — ratify, don't grill

The fence passes every pre-registered threshold **on both runtimes**, measured within each. The proposed `CONTEXT.md` diff is in [`research/ladder-probe/FENCE-FINDINGS.md`](./research/ladder-probe/FENCE-FINDINGS.md), written in the glossary's register and **deliberately not applied**.

The judgement that rides with it changed shape after the 0.32.4 re-measurement, so decide on these numbers rather than the ones the body of that document reports:

- **Recall cost is now −0.3 pp**, not −0.9 pp. Cheaper than when it was flagged.
- **Net accuracy gain is now +0.34 pp — one real error per eight draws**, down from three. The targeted confusion still more than halves (`Event → Fact` 7 → 3), but relocation into `Commitment → Decision` (+2.0) and `Commitment → Fact` (+1.0) gives back three-quarters of it.
- **`Commitment → Decision` +2.0 per run is now established, not suspected** — identical on both runtimes. Neither fence touches that boundary; it is the "rule out every other type" clause pushing borderline Commitments at the nearest fenced neighbour. If you ratify, ratify knowing you are buying a smaller `Event → Fact` at the price of a larger `Commitment → Decision`.

**Trimming the "rule out every other type" clause and keeping only the two `_Avoid_` lines is the obvious untested variant** — it is the clause both side effects are attributed to. Nothing measures it yet; that would be one more A/B, ~15 min of GPU.

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

**The fence (#36), `qwen3:14b`, three independent runs per condition, Ollama 0.32.1:** `Event → Fact` **4.7 [3–6] → 1.0**, ranges non-overlapping; type accuracy **96.8% → 97.7%**; coverage **98.4% → 97.5%**. At `qwen3:4b` (directional only — see traps): `Event → Fact` 9.3 → 2.0, accuracy 91.1% → 92.6%.

**The same fence on Ollama 0.32.4 (2 control + 3 fenced, `qwen3:14b`):** `Event → Fact` **7.0 → 3.0**; type accuracy **96.49% → 96.83%**; coverage **99.1% → 98.8%**; net real errors 11 → 10. The 0.32.4 *control* is worse than the 0.32.1 control on the target confusion (7.0 vs 4.7) and better on coverage (99.1% vs 98.4%) — the runtime shifted the whole distribution. Not re-run at 4b.

**#36's real error structure, corrected:** 36 real misclassifications, not the ticket's 31 — **Fact 17, Project 11, Preference 3, Decision 2, Event 2, Commitment 1, Person 0.** Plus 10 omissions that the original scheme miscounted as misclassifications, 8 of them landing on Person.

**#34, verified against primary sources 2026-07-26:** v1.28.1 matches §7.5 exactly (confirmed in source *and* by running it). Spec PR #3002 merged 2026-07-16, `clientInfo` optional, still draft-only, released revision still 2025-11-25. The "on main (2.0.0b2)" attribution is **wrong** — the behaviour post-dates the published beta, which *rejects* a `clientInfo`-less request with `-32602`. And the prior research's "structurally unreachable on stdio" is **false**: `serve_dual_era_loop` builds a fresh `Connection` per request for a modern client, reproduced over real pipes.

## Traps that cost time — the list grew tonight

- **The probe is not reproducible.** An unchanged prompt moved `Event → Fact` by 3 with nothing changed but the wall clock. `temperature: 0` and a fixed `seed` fix sampling, not kernel scheduling, and `keep_alive: 0` reloads the model every call. **Never read a single run as a measurement.**
- **Determinism varies by the whole configuration — model × prompt × corpus × runtime — and is not predictable from any part of it.** `qwen3:4b` reproduces bit-exactly; `qwen3:14b` does not on the control prompts but *does* on the fenced ones, which is the opposite of what it did on `corpus.py`; and on **Ollama 0.32.4 `qwen3:14b` reproduces bit-exactly on both prompts**, where on 0.32.1 it reproduced on neither. Replicate *files* are not replicate *observations* — **hash the payloads** before treating replicate count as sample size. This silently turned three 4b runs into one, and it makes the 0.32.4 non-overlap test empty. (`CRITERIA.md`, fifth, sixth and seventh amendments.)
- **A pre-registered check can pass on a technicality.** The relocation criterion tests the *largest single* new confusion against the reduction, not the sum. On 0.32.4 it passes (+2.0 < −4.0) while summed relocation (+3.0) cancels three-quarters of the gain. Read the criterion's exact words before quoting it as passed. (Seventh amendment.)
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
| `compare_runtime.py` | **new** — the fence scored *within* each Ollama version, with per-file runtime-stamp checks and payload hashing. Reproduces the 0.32.1 published table before scoring 0.32.4 |
| `PROVENANCE.md` | **new** — runtime and model digests for every measurement here |
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
