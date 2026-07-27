# Next steps — un-deferrable work in the hopper

Written 2026-07-27 as a pickup handoff. Records only work that **cannot be deferred**, plus one item
that **expires**. Everything else on the open tickets is deliberately out of scope here.

> Not to be confused with the earlier `research/NEXT-STEPS.md`, which was deleted; its durable half is
> `research/MEASUREMENT-TRAPS.md`. Read that before running any measurement on this project.

## Read first

- **There is one unpushed commit on `main`: `72dcb22`** ("Record the searched-the-wrong-direction
  trap"). Tree is otherwise clean. Push it or decide not to.
- **No code exists yet** — the repo is `PRD.md`, `CONTEXT.md`, `research/`. Everything below is a
  ruling in a document, not an implementation.
- **`PRD.md` is still written for Fedora + Tailscale throughout.** That rewrite is #33's, and is
  deliberately not pre-empted. None of the work below touches transport, so none of it churns when
  §9.1 is rewritten.

## 1. #33 — needs a human at the MacBook, not an agent

Both gates passed. Two confirmations remain and **neither is scriptable at any privilege level**.

| Item | Why an agent can't | Effort |
|---|---|---|
| **Tool call from a Claude Desktop chat window** | Needs assistive access; the TCC database is SIP-protected, so root cannot grant it either. What is proven for Desktop is the `initialize` handshake plus the three list round trips — the actual tool-call leg has never been exercised. | ~5 min at the keyboard |
| **Time Machine exclusions (items 3.1 / 16)** | This is a **decision, not a measurement**. `tmutil destinationinfo` reports no destinations, so §8.2's off-device backup set and #33's "backups are off-device" premise are both currently unsupported. Either accept local-only durability explicitly in §8.2, or attach a disk. `tmutil addexclusion -p` then needs re-running with Full Disk Access — it silently no-opped last time and reported no error. | decision, then ~15 min |

Batching script for the attended items: `research/33-attended.sh` (run as root from a real terminal;
`sudo` cannot prompt from inside the Claude Code harness). Decide the backup question **before** the
on-device PRD rewrite, since §8.2 is part of what gets rewritten.

## 2. #37 — the four un-deferrable rulings

#37 records fifteen gaps; eleven are deferrable and A.4/A.6 are unanswerable until §9.1 is rewritten.
These four are not deferrable, and are filed as their own tickets.

**The clock has not started.** A.8 and A.15 become *impossible* rather than merely expensive at the
first captured row, and there is no capture path yet. A.2 and A.3 expire when their surfaces ship.
So: urgent-before-implementation, not urgent-this-week.

Ordered cheapest-first, which is also closest-to-decision-free-first.

### #38 — timestamp and timezone semantics (A.15) — ~45–90 min

The PRD never rules on this: `UTC`, `timezone`, `offset`, `naive`, `ISO 8601` return one hit and no
ruling. `timestamptz` + server-as-sole-clock + UTC are defensible defaults; the work is three edit
sites plus **supplying a §7.9 clock story from scratch**, since the Fedora dual-boot RTC material was
deleted and nothing replaced it. Must serve §3.8's 300 s pairing bound, which now carries the
fallback-judgement signal alone after the process-lifetime UUID was withdrawn. One owner yes/no.

### #37 obligation 4 — the briefing lesson — ~15 min

Write into how the next review is commissioned: **anything decided-but-unwritten is briefed as exactly
that.** A.4 and A.6 were false gaps because the reviewer was told the transport shape was decided and
correctly reported a document that does not say so. Blocked on nothing.

### #41 — `full` is agent-reachable, `reembed` is CLI-gated (A.3) — ~1–1.5 h

Self-contained. Two knobs, not one: the destructive mode being reachable via
`trigger_enrichment({ mode: "full" })`, and the harmless six-minute `reembed` being gated for no
recorded reason. Plus dump pinning — the dumps share one rotation pool, so three `full` runs evict the
pre-migration dump. Owner picks the gating mechanism.

### #39 — no idempotency on capture (A.8) — ~1.5–2 h

**The ticket says outright this is a decision, not an obvious fix.** A naive content hash silently
refuses a legitimate re-capture, which is arguably the worse failure. Retries are the *expected* case
here: Desktop spawns one server per app launch and never restarts a dead stdio server. Note `source`
cannot be part of the key (#34: it may arrive `NULL`). An agent can draft the options and recommend;
it cannot rule.

### #40 — replay performs no §8.3 cascade (A.2) — ~2–3 h

Most expensive. Four replay sites (L377, L1553, L1174, L1965), §8.3's cascade, §8.9's runbook
ordering, and no FK on `source_entry_ids` to catch a dangling id. The headline claim — that replay is
deploy-only — was **withdrawn on the text**; do not re-derive it. Must be settled before §8.9's
runbook is walked by hand at deploy.

**Total: roughly 6–8 h of agent time**, producing four drafted rulings — **not four closed tickets**.
Three of the four need an owner decision on a real trade-off, and #37 rule 5 stands: no entry closes
by agreement, every resolution must be checkable against the text.

## 3. Expiring — not un-deferrable, but it stops being possible

**The 2.36× warm-embed overshoot has no explanation left.** The env-var candidate was withdrawn (both
machines have `OLLAMA_FLASH_ATTENTION` and `OLLAMA_KV_CACHE_TYPE`, set on Fedora 2026-07-22, before any
benchmarking), and the overshoot survived like-for-like re-measurement with one instrument on both
sides. Residual untested differences: Ollama 0.32.4 (Mac) vs 0.32.1 (Fedora), and Metal vs ROCm.

The cheap test is pinning both machines to the same Ollama version and re-running
`research/gate-b/embed_latency.py`. **It can only be run while the Fedora box is still here.** ~1–2 h.

This does not gate anything — Gate B passes with 11.2× headroom either way. It is a question about the
*model* of platform difference, not about whether capture is fast enough. If the box goes, the question
goes unanswered permanently.

## What is deliberately not in this document

The eleven remaining #37 entries; A.4 and A.6 (blocked on #33's Gate A landing in §9.1); the on-device
PRD rewrite itself; enrichment-axis work (thermal derate, `NUM_PARALLEL` contention, MLX-vs-GGUF); and
the unrelated `omlx` Homebrew service noted on #33 as a possible GPU-memory contender.
