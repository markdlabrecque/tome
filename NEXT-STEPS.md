# Next steps — handoff, 2026-07-26

Written to survive a context clear. Read this first; it should make re-deriving anything unnecessary.

## Where things stand

The v1 PRD is **complete and closed** ([`PRD.md`](./PRD.md), 14 sections; wayfinding map #1 and assembly #27 both closed). On top of that, a spike asked whether Tome should run on-device on the MacBook instead of the Fedora box.

**Decision: yes — move to the on-device MacBook.** Settled, not open. Reasoning in #32's closing comment. The short form:

- The desktop is dual-booted with Windows and off for stretches, while the **only** client is the MacBook — so capture and search are currently unavailable on a schedule uncorrelated with when they're wanted. On-device, client and server sleep together and that failure can't occur.
- Power: a desktop with an RX 6900 XT runs around the clock to serve one laptop.
- **Stated requirement: high reliability on search and capture; enrichment is explicitly allowed to be slow.** This is the axis that decides everything. Both hot paths need Postgres + the MCP server + the pinned embedder — *not* the enrichment model.
- Keep **`qwen3:14b`**. Storage ~11.7 GB against ~15 GB available.

## Repo state

- Branch **`spike/macos-target`**, pushed, **not merged to main**. Main has the PRD; the spike research is only on the branch. *Deciding whether to merge it to main is an open item* — it's reference material, not code.
- `research/macos-spike-*.md` — five area documents (440 KB) plus `macos-spike-synthesis.md`, which carries a **correction block at the top**; read that before the body, the original verdict in it is withdrawn.
- `research/ladder-probe/` — committed, re-runnable instrument: `corpus.py` (80 synthetic subjects, ground-truth types), `prompt.txt`, `CRITERIA.md` (pre-registered, two amendments recorded), `run.py`, `analyze.py`, `FINDINGS.md`, raw JSONL.

## Open issues

| # | What | Where it runs |
|---|---|---|
| **#33** | MacBook on-machine confirmations before deployment | **MacBook** |
| **#34** | `source` provenance may arrive `None` — decide before first capture | Split: verify on Fedora, decide on Mac |
| **#35** | §13.4's 0.7 confidence threshold measures as inert | **Fedora** |
| **#36** | The three types with no `_Avoid_` line are the three confusion sinks | **Fedora** |

## Recommended sequence

**#35 and #36 have a deadline: do them on Fedora before the move.** They need the GPU, Ollama, all four models (~13 GB already on disk) and the probe harness. Afterwards you'd be re-pulling models onto a 15 GB budget and waiting ~1.9× longer per arm.

1. **Fedora, now — verify #34's three claims** (pure reading, ~30 min). If they don't hold, #34 evaporates.
2. **Fedora — #36 first.** It *changes the extraction prompt*, and the prompt produces the distribution #35 calibrates against. Doing #35 first means tuning a number against a prompt you're about to replace. The dependency runs one way only.
3. **Fedora — #35 second.** Prerequisite the ticket names: the current corpus is deliberately *unambiguous* exemplars, so answering "should the threshold be numeric at all" needs a **second, deliberately ambiguous corpus** written first.
4. **Optional while there (~25 min):** re-run the full four-arm ladder after #36's prompt fix, to see whether fencing the confusion sinks narrows the 14b/4b gap. Not needed — 14b is settled — but it's the difference between "4b's SOFT FAIL was measured against a known-defective prompt" and a clean answer.
5. **MacBook — #33's two gates**, then #34's decision alongside them.

### How to work them

Each ticket has an **AFK half that produces evidence and a HITL half that spends it.** Don't grill cold; don't try to finish them without Mark.

- **#36** is ~90% agent work. Draft candidate `_Avoid_` lines, run before/after, bring the winning wording *with its measured effect*. The wording is a domain call (CONTEXT.md is the glossary) — ratify, don't grill.
- **#35** and **#34** have genuinely contested decisions behind their evidence.
- **Package all three decisions into one grilling pass**, not three. They share context — #35 and #36 both touch the extraction prompt, all three land in the same PRD sections.
- Mark's standing preferences: no bundled multiple-choice; decompose into knobs; measure first; one prose question with a recommendation. For candidate *rules* (like `_Avoid_` lines), show a worked example of each before asking.

## Measured facts — do not re-derive these

**Capture path, Fedora, RX 6900 XT, `bge-m3`, `num_batch: 8192`, against §4.5's 5,000 ms budget:**
- Ceiling-size entry (1,839 tok), warm: **184 ms**; cold incl. load: **1,261 ms**; query embed: **87 ms**. ~27× headroom. This is the number the reliability requirement rests on, and §13.3 had it as unmeasured on either machine.

**Ladder probe (8 paired draws of 40 subjects):**

| model | ent/subj | coverage | type accuracy | subjects producing *no* entity | decode |
|---|---|---|---|---|---|
| `qwen3:14b` | 1.01 | 99.1% | 95.6% | 0.9% | 41 tok/s |
| `qwen3:4b` | 0.95 | 92.5% | 89.2% | **7.5%** | 95 tok/s |
| `qwen3:8b` | worst rung — unusable in both decoding configs | | | | 64 tok/s |

- 4b's SOFT FAIL is **omission, not miscategorisation** — dropped subjects fall to the `search_raw` fallback rather than being lost.
- **Confusion sinks: Fact 16, Person 6, Project 5 wrong arrivals — exactly the three types with no `_Avoid_` line.** The four types that have one absorb 4 between them.
- **`type_confidence`: 0 of 626 entities below 0.7.** Means 0.915 (14b) / 0.945 (4b) / **1.000** (8b, on every entity).

**Cost model:** §1.5's "~18 s/entry, ~50 h full run" was measured on **`gpt-oss:20b`, not `qwen3:14b`** — #24 says so in its own ticket body. Mac÷Fedora is **1.83–2.22×**, and **flat across model size**, so the model choice never changes the platform comparison.

## Traps that cost time today

- **`format: "json"` induces degeneration.** It broke `qwen3:8b` on 3 of 8 draws (newline streams; runaway to the cap with duplicated keys) while 14b and 4b were fine. Same seeds ran clean with only that flag removed. Treat it as a per-model hazard, not a safety net.
- **`OLLAMA_KEEP_ALIVE=24h`** is set in the existing Ollama drop-in, so cycling models mid-run leaves them all resident and overflows 16 GB VRAM. Pass `keep_alive: 0` when benchmarking multiple models.
- **Three different JSON envelope shapes** came back across one model family: `{"entities":[…]}`, a bare `[…]`, and `[{"entities":[…]}]`. `analyze.py`'s `entities_in()` handles all three. A production runner will hit this too.
- **Agents anchor to numbers without checking which model produced them.** Two significant errors in this spike came from exactly that. When a research result reads as confident and consequential, challenge it against its own evidence before acting.
- **`sudo` can't prompt from inside the Claude Code harness** — no TTY. Ask Mark to run those in a real terminal.
- **#24's corpus was never committed**, which made its probe unrepeatable. `research/ladder-probe/corpus.py` is committed for exactly this reason. Keep it that way.

## Things deliberately not done

- `PRD.md` is **untouched** by the spike. Revising it for the on-device deployment is separate work, after #33 fixes the deployment shape.
- The remaining harvest items from #32 are recorded in the synthesis (§6) but not ticketed: the Tome-owned-logfiles change (revises #26), awake-time staleness measurement, `initdb --locale-provider=builtin`, the reproducibility-is-a-runtime-question finding, and the `chattr +C`/compression correction. Ticket them when they become relevant, not before.
