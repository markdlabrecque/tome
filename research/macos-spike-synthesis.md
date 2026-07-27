# Spike synthesis: retargeting Tome to an on-device MacBook

**Issue:** [#32](https://github.com/markdlabrecque/tome/issues/32) · **Date:** 2026-07-26 · **Branch:** `spike/macos-target`

Synthesis of five parallel research agents. Their findings are in `research/macos-spike-{inference,interface,service-management,logging,storage-durability}.md` (440 KB total). Every claim below is sourced from one of those documents; each carries its own measured / documented / assumed labelling, which this document does not repeat. **Where this synthesis states a number, it is the agent's, and the agent's caveats travel with it.**

---

## 1. Verdict

**No — not as a replacement target, and not as a second supported target.**

The move buys a large, genuine simplification and pays for it with a **2.4–3.0× throughput regression** that lands precisely on the system's weakest and most architecturally load-bearing operation. That trade is bad on its own terms, and it gets worse: the same regression prices out the *known* fix for the one question the PRD leaves open.

**But the spike was worth running for reasons unrelated to macOS.** It produced **six findings that apply to the Fedora target today**, four of which are improvements to the shipped spec and one of which is a latent defect that wants deciding before first capture. See §6. If nothing else comes of this, that harvest justifies the exercise.

---

## 2. The decisive finding

Agent 1 reconstructed the per-entry cost model the PRD asserts but never decomposes, using a measurement the PRD already contains without stating: §4.4's runaway (17,957 output tokens / 602 s ⇒ **~30 tok/s decode on the 6900 XT**). Combined with a third-party `llama-bench` run on the exact card, the resulting two-parameter model **reproduces all four of §4.10's measured rows to within a few percent** and recovers a constant ~59 output tokens per extracted Entity. That reproduction is what makes the projection credible rather than a guess.

| Path | Per entry | vs. baseline | 10k full run |
|---|---|---|---|
| **Fedora + ROCm** (baseline; model reproduces the PRD's 18 s) | 18.0 s | 1.00× | ~50 h |
| Mac + MLX, 20-core GPU | 43.6 s | 2.41× | ~121 h |
| Mac + Ollama/GGUF, 20-core | 47.8 s | 2.65× | ~128 h |
| Mac + Ollama/GGUF, **16**-core | 54.5 s | 3.02× | ~147 h |

**MLX does not rescue it.** Three independent sources — Apple's own `mlx-lm` benchmarks, Apple's M4-vs-M5 research post on *exactly* Qwen3-14B-4bit, and llama.cpp's Metal thread — converge on ~220 t/s prefill and 20–24 t/s decode for an M4 Pro. MLX's advantage on a **dense** 14B model is ~0% on prefill and ~19% on decode, and part of that 19% is a smaller, slightly lower-quality quantisation. The widely-cited 3× figure is **MoE-only**. Decisively: **Ollama on Apple silicon has been MLX-backed since 2026-03-30**, so the gap is already captured by the baseline Ollama path.

**The cost also changes shape.** Prefill's share rises from 41% to ~68%. Two consequences: §4.9's "costs only prefill; owes no full run" now prices the *expensive* half, and §4.4's 3,000-token prompt budget would cost ~22 hours per full run if actually spent.

### Why this matters more than the raw multiple

Steady-state incremental enrichment is **fine on both machines** — roughly 6 min/day of GPU on Fedora against ~15 min/day on the Mac, in 18–44 s bursts. Nobody would notice. The regression bites in one place: **full re-derivation.**

And Agent 3 found that the calendar cost compounds. 50 hours of *awake* time is 2–4 calendar weeks on a laptop; ~131 hours is therefore plausibly **5–10 calendar weeks**, during which §4.1's contract says `search_entities` errors. On the desktop, a full run is a long weekend. On the Mac it is a season.

**That is not a performance complaint — it is an architectural one.** "Entities are always fully re-derivable from raw" (#4) is the system's central claim, and #17's argument that re-derivation should yield *better* entities is the entire upgrade path. A guarantee that costs a season with search down is no longer functioning as a guarantee.

**And it forecloses the known fix for the known problem.** §13.1's one open question is whether one extraction pass per entry is enough. Its suspected remedy is a per-type or two-stage pass — which multiplies call count on a target where every call already costs 2.6×. The Mac makes the fix for Tome's most likely quality defect unaffordable. Agent 1 also killed the obvious escape: a dense 32B model would be ~11 days per full run.

---

## 3. Per-section verdicts

*S = survives unchanged · N = survives with a native substitute · D = dissolves (the problem does not exist here) · B = breaks (no acceptable substitute)*

| Section | | Note |
|---|---|---|
| §1.3 exc. 1 Tailscale signalling | **D** | Definitional exception, gone with the tailnet |
| §1.3 exc. 2 NTP | **N** | `timed`; stated justification void, replacement found |
| §1.3 exc. 3 `uv sync` | **S** | Half its bound removed (no units to run outside of) |
| §1.3 exc. 4 model weights | **B/N** | Runtime-conditional; **on Ollama it gets *worse*** — see §5 |
| §1.3 framing sentence | **B** | The where-they-run vs. who-invokes distinction collapses |
| §7.4 | **D + B** | Dissolves as a bind decision; **breaks** as an egress control |
| §7.5 | **D** | Except the provenance mechanism, which is separately at risk |
| §9.1 / §9.2 / §9.3 / §9.4 | **N / D / D / S** | §9.2 is the largest single deletion (`mcp-remote` goes) |
| §10.2 mobile ruling | **S** | Basis replaced; the ruling gets *stronger* |
| §7.3 unit inventory | **N** | 7 systemd objects → 4–5 launchd jobs |
| §7.3 system-not-user constraint | **D** | Homebrew Postgres is itself a user agent; both accepted costs refunded |
| §7.3 ordering/binding | **B** | launchd *"has no explicit dependency model"*; asymmetry moves into code |
| §7.6 `/opt/tome` | **S** | Literally — `/opt` is a firmlink |
| §7.6 SELinux constraint | **D** | Must be re-argued as a preference, not a constraint |
| §7.9 paths / `chattr +C` / clock | **N / D / D** | Clock clauses are all dual-boot-specific |
| §4.8 cadence | **N** | Closer to intent than the original |
| §4.8 staleness alarm | **B** | **And the sign flips** — see §6 |
| §7.10 invariant C + helpers | **S** | Code-level, ports untouched |
| §7.10 stdout capture | **B** | launchd captures nothing |
| §7.11 namespace + 30-day bound | **B** | No retention knob exists at any setting |
| §7.12 leak tripwire | **B** | `lines_scanned` structurally ~0 — see §5 |
| §8.3 scoped purge | **B** | `log erase` takes only `--all`/`--ttl` |
| §8.2 mechanism / destination | **S / flips** | Off-machine backup becomes cheap — see §4 |
| §8.5 | **S** | One of its two justifications dissolves; the number survives |
| §8.7 | **D** | Inverts under FileVault |
| §8.9 | **N** | Four substitutions |
| §1.4 storage facts | — | All must be re-measured |

---

## 4. What the move genuinely buys

Recorded fairly, because it is more than a rounding error.

- **The largest deletion in the document.** Essentially all of §7.5 and §9.2/§9.3: the custom Starlette edge, the `GET /mcp` → 405 route, the `Host` allowlist, the ~20-line `TransportSecuritySettings` subclass, the DNS-rebinding reasoning, and **`mcp-remote` — which §13.2 carries as an accepted risk** (untended, pinned to a dead repo, swallowed transport errors, crashes on Node 26). The MCP spec says clients *"SHOULD support stdio whenever possible"*, and both Claude clients' only non-cloud path is stdio.
- **Two accepted costs refunded.** Under Homebrew, Postgres is a user LaunchAgent in the same domain as Tome's jobs, so §7.3's "system units on a hard constraint" dissolves — taking with it the `sudo`-to-read-logs cost and the no-notification-bus cost. §10.3's deferred desktop notifications become a one-line `osascript`.
- **Off-machine backup flips from ruled-out to cheap.** Both facts that ruled it out were Fedora-box facts. Time Machine carrying the **`pg_dump` output** (never `PGDATA` — a data-directory snapshot cannot be replayed into by the retraction ledger, which is the incompatibility #19 dissolved) retires §13.2's largest durability risk for the price of two exclusions and an encrypted destination.
- **The duty-cycle fear was largely unfounded.** ~6 min/day of GPU in short bursts, and — structurally — **capture and enrichment share a duty cycle on-device**, so a backlog cannot accumulate. "Wake to hours of queued work" is impossible, not merely unlikely.
- **FileVault helps, modestly.** Exactly *one* §8 bound was load-bearing on unencrypted-at-rest: §8.5's framing of the 90-day window. The 90-day number itself was derived from the judged-set sample-size argument and is unaffected.
- **The SELinux constraint dissolves** and `/opt/tome` works literally.

---

## 5. What the move costs, beyond throughput

- **Kernel-enforced egress breaks — and inverts.** §7.4 was quietly doing a second job. macOS has no launchd equivalent, and the substitutes are all dead ends (`sandbox-exec` deprecated and undocumented; `pf`-by-user unverified; App Sandbox needs a signed bundle; NEFilter needs an Apple entitlement). Worse: under stdio the MCP server runs as the logged-in user, **as a child of a GUI app** — so the component that touches every raw entry goes from *most* sealed on Fedora to unsealable. §1.2's hard constraint downgrades from an enforced property to a claim.
- **The leak tripwire fails in the worst possible way.** macOS's retention gradient runs *backwards* to the leak risk: Info is not persisted, Error/Fault are, in the longest-lived store. §7.10's carve-out exists precisely because the **exception** path is where an unowned string carries a natural key (Postgres's `ON CONFLICT` DETAIL). So macOS retains the risky records and discards the content-free narrative, making `lines_scanned` structurally ~0 — *the exact failure §7.12 was designed to detect* ("a check that scans nothing looks identical to a passing check"), as a permanent property.
- **Postgres cannot be enclosed.** Homebrew points at one unrotated plain file. #26's "a decade" becomes "forever", and `logging_collector` inverts from `off` to `on`.
- **`ollama pull` stops being human-initiated.** Ollama's own FAQ documents that macOS builds **auto-download updates** — found independently by two agents. That kills the only remaining bound on §1.3's fourth exception, and breaks §12.1's "version pinning is already satisfied structurally". The install route becomes a spec-level decision.
- **A new egress path with no Fedora analogue:** unified-log data is swept into `sysdiagnose` bundles, which routinely leave the machine.
- **A real durability defect:** Postgres's default `wal_sync_method` on macOS is `open_datasync`, which **does not flush the drive write cache**. PG's own reliability chapter names the fix (`fsync_writethrough`). New build obligation.
- **APFS does not checksum file data** (confirmed against Apple's APFS reference — no checksum field on the extent record), which makes §8.2's *"a dump that reads at all is reading its original bytes"* false and removes one of two legs supporting withdrawal of the weekly restore-into-scratch check.
- **Operational legibility degrades:** no drop-in mechanism (`brew upgrade` overwrites), `plutil -lint` is far weaker than `systemd-analyze verify`, and Background Task Management gives the user a silent off-switch for the agent.

---

## 6. The harvest — six findings that apply to the Fedora box today

**This is the spike's most durable output.** Each should become its own ticket; none depends on the macOS question going anywhere.

1. **`source` provenance is already going stale, and raw is immutable.** SDK v1.28.1 matches §7.5 exactly, but on main `client_params` has moved to a `Connection` object, and draft protocol **2026-07-28 makes client info optional** — so `source` can legitimately be `None`. Transport-independent, therefore not a macOS issue at all. §13.2 accepts null provenance as a rare risk; this would make it routine. **Wants deciding before first capture**, because no later fix can reach an entry already written. *Verify against the SDK and spec PR before acting.*
2. **Abandon the system logger, on both targets.** `TimedRotatingFileHandler(when='midnight', backupCount=30)` reproduces `MaxFileSec=1day` + `MaxRetentionSec=30day` exactly with no host facilities; the purge (`rm` + truncate) is **strictly more complete** than `journalctl --namespace=tome --rotate --vacuum-time=1s` because it reaches the active file; and Postgres joins the bound via `log_directory`, removing §7.11's dependence on drop-in-ing a distro-packaged unit. ~3 MB per 30 days. **This revises #26**, so it needs weighing against that ticket's actual reasoning — the honest cost is hard-crash capture, and the proposed mitigation puts raw tracebacks inside Tome's own store, which is exactly what invariant C exists to prevent.
3. **Measure staleness in awake time, not uptime.** `CLOCK_MONOTONIC` on Linux, `CLOCK_UPTIME_RAW` on macOS. One stored value plus a boot-session id. Better on Fedora too: it denominates the alarm in the same clock the timer runs on.
4. **`initdb --locale-provider=builtin --locale=C.UTF-8`.** Strengthens §8.2's "a file on any Unix" claim on the current target. Discovered by the host change rather than caused by it.
5. **Reproducibility may be reachable, and it is a runtime question, not a hardware one.** §3.7 calls it *"unreachable, not merely expensive"* on facts that are pure Ollama-registry artifacts (`PruneLayers()` at server start, confirmed in source; mutable tags; refusal of digest-addressed models). A runtime that pins by content hash and does not GC its cache would overturn that — **on Fedora, today**. This reaches into #17's epoch design, so it is a substantial ticket, not a tweak.
6. **A correction to a current-PRD fact.** btrfs documents that `nodatacow` implies `nodatasum` and disables compression — so `chattr +C` means **PGDATA was never compressed on Fedora either**. §8.2's space arithmetic is right; its stated reasoning is not.

---

## 7. The portability boundary, sharpened

The boundary held better than expected: the data and durability layer ported essentially for free, and operational plumbing was replaceable at real but bounded cost. Two corrections, both from evidence:

- **Agent 3's, and it is the sharp one.** §4.8's staleness alarm *looked* like plumbing and was not — it encoded a host assumption (*"a machine that is not working shows low uptime"*) in a place the data layer depends on. That is a more dangerous failure mode than plumbing being expensive to replace, because it is invisible until the host changes and then it fails **silently and backwards**. The boundary needs a third category: **host assumptions embedded in domain logic.**
- **Agent 5's refinement of the backup case.** The boundary is really three layers: the recovery *artifact* must be host-agnostic (non-negotiable); the mechanism producing it should be; the mechanism *moving it to other media* need not be. Time Machine carrying `pg_dump` output **complements** the principle. Time Machine snapshotting `PGDATA` would violate it — that is the btrfs-snapshot proposal in a new costume.

---

## 8. Measure-on-the-machine

The five agents produced 61 items between them. These are the ones that could change a verdict rather than refine a number:

| # | Check | Settles |
|---|---|---|
| 1 | `llama-bench` on `qwen3:14b` Q4_K_M at `-p 6656 -n 320` | Everything downstream of §2 |
| 2 | `mlx_lm.benchmark` on `mlx-community/Qwen3-14B-4bit`, same shape | The MLX question, definitively |
| 3 | 16-core or 20-core GPU? (48 GB is offered on both) | ~20% swing in every figure |
| 4 | Re-run §6.4's truncation probe on the Apple-silicon MLX engine | *"The single highest-value line in the whole configuration"* is being carried onto a code path it was never measured against |
| 5 | Sustained-vs-peak derate over 60–90 min | Every figure in §2 is a peak figure; no source has this |
| 6 | Is a merging extraction one `qwen3` call or two? | §13.3's largest uncertainty — **if two, every figure doubles on both platforms** |
| 7 | `log show --last 30d \| head -1` | The *de facto* macOS retention number: 8 h or 3 weeks |
| 8 | The undocumented `TTL` key in Apple's subsystem plists | Whether §7.11 softens from "breaks" to "undocumented substitute" |
| 9 | `pfctl -nf` with a `user` rule | Whether *any* kernel-enforced egress substitute exists |
| 10 | `fdesetup status`; free space on `/System/Volumes/Data` | Replaces the 876 GB figure in three sections |

Item 6 is not macOS-specific and is worth doing regardless.

---

## 9. What would change the verdict

Stated so the conclusion is falsifiable rather than merely argued:

- **A measured head-to-head showing MLX >40% faster on prefill** for Qwen3-14B at a ~6.7k prompt (Agent 1's own falsifiable condition). The projection is built on third-party benchmarks; item 1–2 above would replace it with a real number.
- **A 20-core part plus a better-than-projected sustained derate**, narrowing 2.4× toward ~1.8×. That would not make the full-run cost good, but it would make it arguable.
- **Full re-derivation ceasing to be architecturally load-bearing** — for instance if §4.1's build-alongside-then-swap were adopted, removing the "search errors for the duration" contract. Agent 3 notes the Mac may reopen that rejection on host grounds. If re-derivation became a background operation, the central objection in §2 weakens considerably.
- **A different motivation.** This spike answered "what does the port cost". It did not ask *why* — and if the real driver is **mobility** rather than simplification, the port is the wrong question entirely, and the right one is whether Tome can be split at all. Nothing here bears on that.
