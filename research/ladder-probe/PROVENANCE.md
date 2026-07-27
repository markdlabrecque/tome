# Runtime provenance for every measurement in this directory

**Captured 2026-07-27, immediately before the Fedora Ollama upgrade**, because none of it was
recorded at the time and an upgrade would have made it unrecoverable.

`run.py` records the model tag, but **not the inference runtime version and not the model
digest**. PRD.md's Derivation Epoch is defined as *"extraction prompt, entity-type definitions,
enrichment model, embedding model, confidence threshold, **and inference runtime version**, each
recorded **by content** so that a model tag moving under its own name is visible."* The probe
did not meet its own project's standard. This file closes the gap retrospectively for the runs
already made; `run.py` now stamps each record going forward.

## The runtime every committed result was measured on

**Ollama 0.32.1**, `/usr/local/bin/ollama` (installed via the upstream script — not owned by any
RPM; binary mtime 2026-07-15), `127.0.0.1:11434`, systemd unit `ollama.service` with drop-in
`/etc/systemd/system/ollama.service.d/90-pi-local-rocm.conf`:

```
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_KEEP_ALIVE=24h        # overridden per request with keep_alive: 0
```

Host: Fedora, `Linux-7.1.4-204.fc44.x86_64`, AMD RX 6900 XT (16 GB), ROCm.

## Model digests at the time of measurement

| tag | digest (20 hex) | quant | pulled |
|---|---|---|---|
| `qwen3:14b` | `bdbd181c33f2ed1b31c9` | Q4_K_M | 2026-07-26 |
| `qwen3:8b` | `500a1f067a9f782620b4` | Q4_K_M | 2026-07-26 |
| `qwen3:4b` | `359d7dd4bcdab3d86b87` | Q4_K_M | 2026-07-26 |
| `gpt-oss:20b` | `17052f91a42e97930aa6` | MXFP4 | 2026-07-22 |
| `bge-m3:latest` | `7907646426070047a772` | F16 | 2026-07-19 |

## What this stamps

Everything in this directory measured before 2026-07-27, i.e. **all of it**: the model ladder
(`raw*.jsonl`, `FINDINGS.md`), the #36 fence A/B and its three replicates per condition
(`FENCE-FINDINGS.md`), #35's 2×2×2 plus the third wording (`CONFIDENCE-FINDINGS.md`), and
`CRITERIA.md`'s six amendments — including the reproducibility findings, which are **properties
of this runtime version** and should not be assumed to survive an upgrade.

`research/gate-b/embed-latency-odin.json` already records its own runtime and environment and
needs nothing here.

## What is *not* 0.32.1

**`raw-{control,fenced}-ollama0324*.jsonl` (five files, 40 draws, 2026-07-27) are Ollama
0.32.4** and say so in every record — `run.py` self-stamps from that date, so these carry
their own provenance and are not covered by the table above. `qwen3:14b`'s digest is
unchanged across the upgrade (`bdbd181c33f2ed1b31c9`), so the model is identical by content
and the runtime is the only variable between them and the 0.32.1 files.

Their result is in `FENCE-FINDINGS.md`'s closing section, and `compare_runtime.py` verifies
the stamp on every file before scoring. **The upgrade moved the numbers**: on 0.32.4 the
unfenced control's `Event → Fact` is 7.0 against 4.7 on 0.32.1, and `qwen3:14b` became
bit-reproducible where it had not been. Both are recorded in `CRITERIA.md`'s seventh
amendment. This is the worked example of why this file exists.

## Why this matters beyond bookkeeping

The fourth, fifth and sixth amendments establish that determinism on this stack varies by
model, by prompt, and by corpus. **A runtime upgrade is exactly the kind of change that could
move those results**, and without this file there would be no way to say which version they
described. If the fence or confidence results are ever re-run on a different Ollama, compare
against this stamp rather than assuming continuity.
