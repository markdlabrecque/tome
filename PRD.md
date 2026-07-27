# Tome — Product Requirements & Specification

**Status:** v1 specification, complete. Assembled 2026-07-26 from the twenty closed decision tickets of [the wayfinding map (#1)](https://github.com/markdlabrecque/tome/issues/1), whose frontier is empty.

**What this document is.** The single buildable spec. It states the *current* answer to every settled question, with supersessions noted rather than replayed. Where a ticket's reasoning matters to getting the implementation right, it is carried across; where it is only the record of a rejected alternative, it is left in the ticket. Every section cites its sources so any claim can be traced back.

**What this document is not.** It does not re-open a decision. It contains no schema DDL as a deliverable artifact, no code, and no eval harness — those are the build's, or explicitly out of scope. §13 lists what is known to be unmeasured; §14 lists what assembling this surfaced without deciding.

**Reading order for a builder.** §1 for the constraints, §3 for the data model, §11 for the checklist that must not be missed, §13 before making any claim about quality.

**Examples are synthetic.** `markdlabrecque/tome` is public, and the map ruled permanently that no artifact drawn from real memory content lives in this repo (#23 §9). Every name, key and query in this document is invented.

---

## 1. Overview & scope

### 1.1 The destination

A personal memory-keeper for a single user, fully self-hosted.

An **immutable raw layer** of manually captured entries — text plus an embedding, in Postgres with pgvector — is the sole source of truth. A **periodic, incremental, fully re-runnable enrichment process** derives a structured **entity layer** on top of it. An **MCP server is the only interface**, used by both AI chat clients and agents. Entity search is the default and primary query surface; raw semantic search is a secondary fallback the calling agent selects deliberately. There are no direct writes to the entity layer — entities only ever arrive by derivation from raw.

All embedding and enrichment inference runs locally on the machine. All components run as systemd services and come back on boot.

*Source: map Destination; #2, #3, #4, #6, #7.*

### 1.2 Hard constraints

| Constraint | Meaning | Source |
|---|---|---|
| **Local inference only** | Every embedding and every classification/extraction call goes to a local Ollama on this machine. No hosted model API, at any point, for any purpose. | map, #8 |
| **Tailscale is the sole ingress** | The MCP endpoint is reachable only from the tailnet. Nothing is published to the public internet. | map, #5, #9 |
| **No Tome data leaves the machine** | The literal reading of "no external egress" is already broken by Tailscale's own coordination traffic, so the constraint is stated as its real meaning: no memory content, derived or raw, is transmitted off the box. Enforced in the kernel for the units (§7.4). | #15 §9 |
| **Raw is immutable** | A Raw Entry is never edited. It leaves only by Tombstone (content dropped, identity kept) or Retraction (removed outright). | #4, #18 |
| **No direct entity writes** | Nothing outside enrichment writes an Entity — not the MCP server, not a human, not a triage action. | #4, #14 §3 |
| **Single user, no adversary modelled** | No app-level auth. Design trade-offs are made against a thin threat model, stated where they bite. | #5, #13 |

### 1.3 Named egress exceptions

The no-egress rule has explicitly named exceptions. Each is human-initiated or carries no memory content; none is an automatic path out for Tome data. **Three of the four are bounded by *where they run*; the fourth is bounded only by nobody invoking it** — see item 4 and the scope note below.

1. **Tailscale's own signalling** — coordination server and DERP relays. Without it there is no tailnet, so this is definitional rather than conceded. (#15 §9)
2. **NTP** — `chronyd`, kept deliberately. Refusing it makes the RTC the sole authority, dual-boot drift becomes permanent, and a bad enough drift breaks Tailscale's handshakes and so takes down the only ingress path. Carries no memory content. (#15 §9)
3. **`uv sync` reaching PyPI during a deploy** — human-initiated, never automatic, and it runs as root *outside* the units, so §7.4's kernel-enforced `IPAddressDeny=any` on the running system is untouched. (#20)
4. **`ollama pull`, and hand-driven Ollama upgrades** — human-initiated and never automatic (#17: Ollama is hand-installed at `/usr/local/bin`, owned by no package, with no unattended upgrade path), and carrying no Tome data outbound. **But it does not clear the bar item 3 clears.** Measured on this machine: a bare `POST /api/pull` with no CLI in the picture returns `pulling manifest` followed by a registry error, so the fetch happens **inside `ollama.service`** rather than in the operator's shell. Sealing that unit was measured and declined (§7.7), so the daemon has **standing outbound access for the life of the system** — the *act* is human-initiated, the *capability* is not. (#28)

**What *kernel-enforced* covers, precisely.** §7.4's `IPAddressDeny=any` is set on the three **Tome** units. It is not set on `ollama.service`, which carries no address policy at all. So *no external egress* is a kernel-enforced property of the units Tome ships, and a property of **application behaviour** for the Ollama daemon — which is the unit that receives every raw entry text, on both the embed and the enrichment path. This is stated rather than sealed, on the judgement recorded in §7.7. (#28)

### 1.4 The machine

Measured facts that decided things, kept because several arguments rest on them.

- Fedora 44, systemd 259. `/` is **btrfs** with `compress=zstd:1`; `/` and `/home` are subvolumes of one filesystem. 888 GB free.
- **AMD RX 6900 XT**, native target `gfx1030`, 16 GB VRAM (15.98 GiB usable), **80 CUs**. The Raphael iGPU (`gfx1036`) has **2 CUs** and no rocblas — ruled out (#15 §5).
- 64 GB system RAM. The desktop holds a measured **1.16 GiB of VRAM with no model loaded**.
- **Ollama v0.32.1 at `/usr/local/bin`**, hand-installed, owned by no package. Tome is its sole consumer and owns its unit. There is no unattended upgrade path.
- Postgres is **not yet installed**. Fedora 44 ships `postgresql-server` 18.3 and `pgvector` 0.8.0; `pg_trgm` comes from `postgresql-contrib`.
- **firewalld**: the default `FedoraWorkstation` zone opens ports 1025–65535 on `eno1`; `tailscale0` is in no zone. This is why the bind decision in §7.4 is load-bearing rather than defence-in-depth.
- Tailnet identity: `odin.tailc0e3c3.ts.net`, short name `odin`, `100.124.36.8`, `fd7a:115c:a1e0::4f37:240a`. Peers are an iPhone and a MacBook — **no always-on peer**.
- `nvme0n1p3` (root, live DB, all backups) has **no LUKS layer**. Unencrypted at rest.
- The machine is **dual-booted with Windows and is sometimes off for stretches**. Uptime is intermittent, which is why staleness alarms measure against uptime rather than wall-clock age (§4.8).
- **SELinux is Enforcing**; `/home/mark` is `0700` and labelled `user_home_dir_t`, which makes running the units out of the dev checkout structurally impossible (§7.6).

*Source: #15 §0, #17, #19, #20, #22, #24, #26.*

### 1.5 Scale assumptions

Everything downstream is sized against **manual capture at roughly 20 entries/day** — about 7k raw entries a year. The entity layer is a compression of that. Two consequences recur:

- Exact vector search is affordable for years (§6.2), and the index tripwire sits at ~30–50k rows or `search_entities` p95 > 150 ms (§13.4), whichever comes first.
- One extraction call is **~18 s**, so a full re-derivation is **~5 h at 1k entries, ~25 h at 5k, ~50 h at 10k** — reaching ~36 h within a year. Full runs are rare *and expensive*; the second half of that is easy to forget.

*Source: #16 §4, #18 §5.*

### 1.6 Roadmap boundary

v1 is **answer-when-asked**. Tome never volunteers content; the only unprompted channel is the operational `warnings` field on `capture_entry` (§5.10). Everything ruled out, and the reasoning that would otherwise be rediscovered, is in §10.

---

## 2. Domain model

**[CONTEXT.md](./CONTEXT.md) is the glossary of record and is not duplicated here.** It defines Raw Entry, Enrichment, Entity, Enrichment Run, Natural Key, Resolution Required, Type Override, Tombstone, Retraction, Retraction Ledger, Derivation Epoch, and the Entity Types. It is a spec artifact in its own right, for two reasons beyond documentation:

1. **The entity-type definitions and their `_Avoid_` rules go into the extraction prompt verbatim** (#12 §2). Editing CONTEXT.md's type definitions is therefore editing program logic, and it changes the Derivation Epoch (§4.9).
2. Its terminology is the naming discipline for the whole system. The `_Avoid_` lines are decision rules, not style notes.

### 2.1 The seven Entity Types

**Person, Project, Preference, Decision, Fact, Commitment, Event.** Defined in CONTEXT.md.

**Type Suggestion** is governance metadata, *not* an eighth Entity Type — it is how classification strain is recorded for review (§4.7).

Adding or retiring a type has **zero migration cost** by design: entities are fully re-derivable, so it is a definition change plus a full Enrichment Run. The cost is the run's hours, not a migration.

*Source: #10, #12 §2, #17.*

### 2.2 Governance

Manual, periodic, exception-driven review — no automated schema evolution. The loop is:

1. `review_schema` (§5.7) reports per-type counts, mean confidence, a confidence histogram, and aggregated Type Suggestions over a time window.
2. Recurrence is the signal. A **recurring `ambiguous` pair** is evidence a type *boundary* is wrong, not that one guess was; a recurring `no_fit` guess is evidence a type is missing.
3. The fix is sharpening the definitions in CONTEXT.md (or adding/retiring a type) and re-running.

Nothing is ever marked as reviewed or dismissed. Dismissal would delete exactly the evidence the loop reads. There is no `dismissed_at` column and no review watermark table.

*Source: #10, #12 §7, #14 §6, #17.*

---

## 3. Data model

### 3.1 Three data categories

Every table falls into one of three classes, and the class decides how it is migrated, backed up and retained. This is the organising principle of §8 and it is worth stating before the tables.

| Class | Members | Migration | Backup | Retention |
|---|---|---|---|---|
| **Durable input** | `raw_entries`, `enrichment_events`, Type Overrides | Needs care — losing it loses the system | Yes | Never expires |
| **Derived** | `entities`, Type Suggestions | Never needs a *data* migration: DDL, then reset all raw to `pending` and the next run backfills | Yes, but only to avoid paying §1.5's re-derivation cost | Re-derived, not retained |
| **Sample** | `query_log` | Not re-derivable, but losing it costs at most 90 days that refill on their own | **No** — excluded from every dump | 90 days |

The third class exists because a query log is neither: it cannot be re-derived, but it is not precious either. That is precisely why not backing it up is correct rather than a compromise.

*Source: #20 (first two), #23 §5 (the third).*

### 3.2 `raw_entries` — the sole source of truth

Append-only. The only mutations are `enrichment_state` and its companions, a Type Override, a Tombstone (content nulled), and a Retraction (row deleted).

| Field | Notes | Source |
|---|---|---|
| `id` | **`bigint`, generated as identity.** Referred to as `raw_entry_id` throughout the tool surface; the wire type is `string` regardless. Immutable and stable, unlike an entity id. | #11, #30 |
| `text` | The captured content. **Nullable** — a Tombstone nulls it. Every work query must therefore carry `AND text IS NOT NULL` (§11). | #14 §4 |
| `context` | Optional, agent-authored, **≤ 1,000 characters**, holding **referents and setting only**. **Excluded from the embedding.** Read by extraction as a *subordinated* tie-break. Nullable; nulled by Tombstone, purged by Retraction. Full treatment in §3.3. | #25 |
| `embedding` | `vector(1024)`, **nullable** — capture may defer it (§4.5). `SET STORAGE PLAIN`. Computed over `text` **alone**. | #16, #25 §2 |
| `embedding_epoch_id` | FK to `derivation_epochs`. Replaces #10's `embedding_model` text column: the epoch record already names the model *and* carries its digest. **Written at capture, and never reconstructable** — see the write-once warning below. | #17 |
| `captured_at` | **Caller-supplied and required**, no server default, so backfills are expressible. The server flags a wild disagreement with its own clock rather than silently accepting it (§11). | #11, #15 §9 |
| `source` | Capturing **client type only**, read from `clientInfo.name` at `initialize` and stored **verbatim**. **Nullable** — `NULL` means *not recorded*, never a sentinel (§9.4). The two real values are `claude-code` and **`claude-ai`** (Desktop; *not* `claude-desktop`, which no client sends). Never device. Never agent-supplied. **Never read to change behaviour.** | #10, #13, #34 |
| `enrichment_state` | `pending` \| `enriched` \| `failed` \| `resolution_required` \| `skipped`. There is deliberately **no `in_progress`** state (§4.6). | #12 §4, #14 §4 |
| `last_enriched_at` | | #10 |
| `attempt_count` | N = 3 before an entry leaves normal incremental runs. Capture-time embed timeouts **never** count toward it. | #12 §4–5 |
| `last_error` | | #12 §4 |
| `last_failed_stage` | `embed` \| `enrich` — two different models, so one opaque error string would be much harder to act on. | #12 §4 |
| `reason_code` | Set with `resolution_required` and with `skipped`. Enumerated in §4.7. | #12, #18, #24 |
| `prompt_eval_count` | The exact bge-m3 token count returned by the inline embed at capture. Worth storing: it is the input to §4.4's pre-flight assertion, which must not re-measure. | #18 §6 |
| `type_override` | A nullable `entity_type`, recorded by `resolve_entry`'s `set_type`; `null` clears it. **Durable *input* to derivation**, so it survives a full run. Applies as a **tie-break only**. A column rather than a table: it is one per-entry value, and its history already lives in `enrichment_events` as a never-prunable class — the same relationship `enrichment_state` has with `prior_decisions`. | #14 §3, §5; #31 |

**The one thing that cannot slip: record the embedding model's tag *and* digest at capture.** The derived side is fully reversible — add a column in six months and one full run backfills the corpus. The raw side is write-once and *already decaying*: there is no re-derivation for the source of truth, so a raw vector's provenance is recorded once or never. Every raw vector written without a digest goes permanently ambiguous the moment `bge-m3:latest` republishes, and you can neither backfill a digest you never captured nor obtain the old artifact to compare against. (#17)

**Known window, accepted:** capture embeds inline while `tome-mcp` holds its epoch fingerprint from startup, so an `ollama pull` between restarts leaves captures carrying new-model vectors stamped with the old epoch. The alternative — an `/api/tags` call per capture — reintroduces a hard Ollama dependency on the one path §7.3 deliberately made soft. This is attribution, not forensics. (#17)

### 3.3 `context` — one column, two decisions spent in opposite directions

`context` is the only field on the raw row that is neither captured content nor derivable from anything, so it gets its own treatment.

It **stays a distinct column** rather than being folded into `text`, and the reason is not purity — `text` is already agent-composed prose. It is that raw is immutable: fold framing into `text` and "is it embedded" and "does the classifier see it" become *consequences* rather than decisions, unmakeable for every entry already stored. One nullable column buys two independently revisable decisions, and they land on opposite sides:

- **Not embedded.** The raw vector is over `text` alone. Three reasons: #22 measured a generic instruction ahead of content at **−5.95 nDCG@10** on `bge-m3`, and `context` ahead of `text` is structurally the same act; `context` is repetitive by nature, so a dozen captures from one session carry near-identical framing whose shared mass would pull twelve unrelated entries toward each other — silently, since §6.2 made search exact so no ANN fuzz masks it and §8.5 confirms no telemetry would notice; and it would eat the capture budget, where #18's rejection message says *split the text*, the wrong remedy for a problem the text did not cause.
- **Read by extraction, subordinated.** Without this nothing in the system reads `context` at all. With it, the loss above is a *re-routing* rather than a loss: the referent reaches the entity layer, which is the **primary** surface, instead of the fallback. And it is cheap — extraction is decode-dominant, and a short `context` is prefill.

**The subordination rule, verbatim for the prompt:** *`context` may resolve a referent or break a type tie that `text` leaves open; it may never be the sole ground for an Entity.* This is #14's Type Override shape reused, and it is needed because a model-improvised, un-reviewed field left to author freely mints a Person who was never mentioned — a lie with a schema, with nothing able to catch it.

**Prescribed content.** In: **referents** (what the pronouns and bare nouns in `text` point at) and **setting** (what was happening at capture). Out: **motive** — it has no consumer once extraction is subordinated and proactive surfacing is out of scope, and it is the most hallucination-prone content in the field; and **free-form "anything useful"**, which is the status quo this replaced.

**Accepted costs, stated rather than solved:**
- `context` is **unreachable by search**. If `text` says "he'd rather move the retry to the timer" and only `context` names the person, no `search_raw` query for that name finds the entry. Payable only because extraction reads it.
- It reaches the *entity* vector by a back door — the classifier folds it into a `summary`, and summaries are embedded. Real, but laundered through a model told what `context` is, so the prefix finding does not transfer.
- **Nothing can verify context quality.** There is no telemetry and no ground truth for a situational note, so the tool description is not merely the chosen lever, it is the only one available. The residual is "the agent misjudged the trigger" — narrower than "the agent improvised", but permanent and per-capture.
- The **1,000-char cap is an estimate, labelled as such** (≈240–475 bge-m3 tokens at the measured 2.1–4.2 chars/token spread). It is safe to be an estimate because no stored row depends on the cap in force when it was written. It lives **in code, not `tome.env`** — a design constant, not a measurement against a moving model — and it is **coupled to the 500-token allowance** in §4.4: raising one means raising the other, and both are reviewed together.

*Source: #25 in full.*

### 3.4 `entities` — the schema, in one place

*This is the gap the map flagged from the day it was charted. The fields below are spread across #10's domain model, #12's addenda, #14's state changes, #16's vector column and #17's epoch stamps; nothing collected them until now.*

Read-only from outside. Written **only** by enrichment, in the per-entry transaction (§4.6). Wholly disposable: `mode: "full"` deletes every row and rebuilds.

| Field | Notes | Source |
|---|---|---|
| `id` | **`bigint`, generated as identity** — matching raw's, since the discipline protecting the two tables' opposite stability is #23's rule rather than a type difference. Unstable by design: reassigned by every full run and every retraction cascade, so **nothing durable is keyed on it** (§8.5). | #12 §8, #23, #30 |
| `entity_type` | One of the seven. Exactly one per Entity; multi-typing is off the table. | #10, #12 §2 |
| `natural_key` | The domain identity. Canonical, normalised, model-emitted. **`UNIQUE (entity_type, natural_key)`** — this is the merge key, and the merge is `INSERT … ON CONFLICT … DO UPDATE`. | #12 §1 |
| `summary` | The derived prose. **Length-bounded** — both to stay inside the embedder's window and because an unbounded summary undermines the compression premise the tiering rests on. **1,200 characters — a starting point, not a requirement (§13.4).** Re-derived on every merge as `old summary + new raw entry → new summary`. | #16 §3 |
| `embedding` | `vector(1024)`, **`NOT NULL`**, `SET STORAGE PLAIN`. Over `summary`. Written inline in phase 2 in the same short transaction, and **re-embedded on every merge** — the merge destroys the old summary, so a stale vector would point at prose that no longer exists. | #16 §3 |
| `embedding_epoch_id` | FK to `derivation_epochs`, the **embedding axis** — the re-embed handle. Subsumes the `embedding_model` column #16 originally specified, the same way it subsumed raw's. | #16 §3, #17 |
| `derivation_epoch_id` | FK to `derivation_epochs`, the **extraction axis** — which rules produced this Entity. Distinct from the above because `--reembed` rewrites the vector while leaving the derivation untouched, which is the whole point of the mode; a single stamp would either never clear or restamp every Entity as freshly derived. Also the stamp `get_enrichment_status`'s epoch grouping reads. | #17, #29 |
| `type_confidence` | The classifier's confidence in `entity_type`. Surfaced under `debug`; feeds `review_schema`'s histogram and mean. | #12 §2 |
| `considered_types` | The types that also fit. Surfaced under `debug`; feeds the `ambiguous` Type Suggestion. | #12 §2 |
| `source_entry_ids` | Every Raw Entry that contributed. Appended on merge. Read by `get_history` as `related_ids`, and by the retraction cascade as its match predicate. **A purged id left here is a dangling reference**, which is why the cascade is structural rather than statistical (§8.3). | #12 §1, #18 §3 |
| `last_enriched_at` | Returned under `debug` on `search_entities`. | #11 |

**Identity and merge, in full.** No per-type branching exists in the pipeline; what varies is *how specific a key the prompt asks for*:

- **Person** → `"alex chen"`, **Project** → `"tome"` — deliberately **coarse**, so repeated mentions collapse into one Entity.
- **Event** → date-scoped, e.g. `"standup-with-alex-2026-07-31"`. **Decision** → subject plus date. **Fact** → its specific claim.

Episodic types therefore de-facto never merge, purely as a consequence of key specificity rather than a special case in code. **Key-specificity guidance is asymmetric on purpose:** a too-specific key yields a duplicate — graceful and harmless; a too-generic one **conflates** two distinct things and loses information in the merged summary. So every type biases over-specific, and Person/Project are the only deliberate exceptions.

**Type stickiness.** Resolution looks up `natural_key` *ignoring* `entity_type` first. If an Entity exists under a different type, the existing type wins and the extraction merges into it — unless the new classification's confidence is substantially higher: **≥ the incumbent's + 0.20, and ≥ the global threshold**, both a starting point (§13.4). The margin stops a 0.71-vs-0.70 flicker from re-typing an Entity on every run; the floor stops two low-confidence guesses from re-typing on a technicality. Without this, a subject classified Preference in March and Decision in July fragments into two Entities and never merges, defeating the merge design exactly where it should help.

**Accepted caveat.** Merge is order-dependent, so folding the same entries in a different sequence yields differently-worded summaries. "Fully re-derivable" therefore weakens to **re-derivable up to summary wording** — same Entity set, same `source_entry_ids`, prose may differ.

**Fidelity is inversely proportional to merge depth**, which puts the loss where it hurts least: Event/Decision/Fact summaries are first-generation and near-verbatim, while Person/Project are the telephone game by design — and those are the ones asked about broadly, where an eroded-but-on-topic summary still works. Unchecked (§13).

*Source: #12 §1, #16 §1.*

### 3.5 `enrichment_events` — the audit trail

One row per `(run_id, raw_entry_id, stage, outcome, detail JSONB)`, written **in the same transaction as the entry's state**, **never updated**.

| Field | Notes |
|---|---|
| `run_id` | FK to `enrichment_runs`. |
| `raw_entry_id` | FK to `raw_entries`, **`ON DELETE CASCADE`**. |
| `stage`, `outcome`, `at` | |
| `gist` | The lean summary `get_history` returns by default. |
| `detail` | JSONB, returned in full only under `debug` — an Entity mentioned 200 times carries 200 merge events holding before/after summary text, and returning that unconditionally would drop tens of thousands of tokens into the session you are debugging in. |
| `derivation_epoch_id` | FK. So "did my fix land?" is answerable from the audit trail, which is the whole retry story. |

**It captures what `enrichment_state` structurally cannot**, that column being last-write-wins — it says where an entry stands, never how it got there:

- an entry that yielded **zero** Entities (otherwise indistinguishable from a successful one — both read `enriched`)
- extractions discarded as low-confidence
- **merges, with before/after summary text** in the detail — the merge is destructive to the old summary, so without this an over-merge is invisible after the fact
- capture-time embed timeouts later filled
- failed → retry → succeeded chains, each distinct error preserved
- Type Suggestions logged, human decisions from `resolve_entry`, Tombstone reason codes and excerpts, and the path of the pre-wipe dump on a full run

**The invariant, and it has no carve-out:** ***`enrichment_events` is append-only for the lifetime of its entry.*** Retraction's `ON DELETE CASCADE` is its sole deletion path. This is cleaner than it would have been under a tombstone-flavoured retraction, which would have needed a DELETE-or-redact exception to the one table hardened against mutation.

**Enforced at the database level, not by convention** — `REVOKE UPDATE/DELETE` from the app role, with entity mutations routed through a function or trigger that writes the event. Otherwise the log is a side effect a code path can forget, and the audit trail silently lies.

**No pruning in v1.** ~5 rows/entry/run at ~1 KB JSONB is ~50 MB per full pass at 10k entries, and full passes are rare (§1.5) — call it ~300 MB ever, against 888 GB free. The `prior_decisions` join and `review_schema`'s aggregates are indexed lookups that will not notice half a million rows. Never-prunable classes are drawn in §8.6 so a future policy has its boundary pre-drawn.

*Source: #12 §7, #18 §2, #19.*

### 3.6 `enrichment_runs` — the run log

`run_id`, `mode` (`incremental` | `full` | `reembed`), `status`, `started_at`, `completed_at`, `entries_processed`, `entities_created`, `derivation_epoch_id`.

Two things read it besides `get_enrichment_status`: live progress during a run (there being no `in_progress` entry state), and **`review_schema`'s window — "since the last full Enrichment Run began"**, which is a *time* question answered from here and never needed epoch identity (§4.9).

*Source: #12 §4, §8; #17.*

### 3.7 `derivation_epochs` — attribution, never reproducibility

A **Derivation Epoch is a content-addressed set of inputs, not a span of time.** One row, itemised into named fields:

| Field | Source at run start |
|---|---|
| Extraction prompt text hash | the prompt module, hashed after rendering |
| Entity-type definitions hash | same module — the definitions go into the prompt verbatim |
| Enrichment model tag **+ digest** | `qwen3:14b` + `/api/tags` |
| Embedding model tag **+ digest** | `bge-m3` + `/api/tags` |
| Confidence threshold | `tome.env` |
| Ollama version | `ollama --version` |

**How it works:** at the start of a process that produces derived output, the fingerprint is assembled. If an identical row exists it is reused; otherwise one is inserted. Derived rows carry its id. Deduplicated by content, so there are **no rollover rules**, no "does a capture start an epoch" question — a capture produces no row, so the question cannot arise — and no sensitivity whatever to capture frequency. Over Tome's whole life this table holds perhaps a dozen rows.

**Reproducibility is unreachable, not merely expensive, and this is the fact that settles it.** Ollama refuses digest-addressed models — `{"model":"bge-m3@sha256:…"}` returns `invalid model name`, measured on this machine. `latest` is a mutable pointer, and Ollama prunes unreferenced blobs at server start, so once upstream republishes, the artifact that embedded the first 500 entries is gone from both the registry and the disk. Recording the digest buys **detection and honest labelling**, at any budget.

That is no loss. Raw being the sole source of truth already makes "reproduce" mean *re-derive from raw under today's rules*, and the non-determinism is the feature: a better model should produce better Entities, not identical ones. **So the spec claims attribution and explicitly disclaims reproducibility.**

**Why itemised fields rather than one hash or two axes.** The membership test is *"if this changes, could the same Raw Entry yield a different result?"*, and it splits the inputs in two with wildly asymmetric remedies:

| Axis | Governs | A change makes them | Remedy | Cost |
|---|---|---|---|---|
| **Extraction** (prompt, type definitions, `qwen3:14b`, threshold) | Entities | **stale** — a quality problem | full run | ~50 h / 10k |
| **Embedding** (`bge-m3`) | vectors on **both** layers | **incoherent** — a correctness problem, since cosine across model versions is meaningless and exact search leaves no fuzz to hide it | `--reembed` | ~6 min / 10k |

A single opaque version over-triggers in **both** directions, and the dangerous direction is a model re-pull inviting a fifty-hour re-run for something that never touched extraction. Itemising gives one identity to stamp with, plus field-level diffing so a human reads which half moved and picks the remedy.

**Excluded on measurement:** the ~16k `num_ctx` ceiling (it cannot bind — capture is capped far below it) and `num_batch: 8192` (a capture-time size gate, not a derivation input). And the fingerprint reads **specific named keys, never a hash of `tome.env`** — otherwise adding a host to the allowlist or changing backup retention would register as a rule change.

**Every trigger is a deliberate human act on the box; none is data:**

| Event | New epoch? |
|---|---|
| `capture_entry` — one, or ten thousand | No — data, never rules |
| Incremental run, config untouched | No |
| Type Override, `resolve_entry retry` | No — per-entry input, recorded per-entry |
| `tome-migrate` DDL | No — a real change arrives with a prompt change |
| Service restart, backup restore | No — the table restores with the database |
| Editing the prompt or the type definitions | **Yes** (via `make deploy`) |
| Changing the threshold or a model tag | **Yes** (`tome.env` edit + restart) |
| `ollama pull` moving a digest under a fixed tag | **Yes** |
| `ollama pull` returning the same digest | No — content-addressed |
| Ollama upgrade | **Yes** |

The `ollama pull` row is the one a human fires **without meaning to** — one word that silently repartitions the vector column. That is why the digest is recorded at all, and why its warning is the persistent one (§5.10).

*Source: #17 in full.*

### 3.8 `query_log` — retrieval telemetry

Written on **every** search, always, with **no `debug` gate**. Adds zero MCP tools and returns nothing to the caller — which is why always-on is not an exception to the lean-response convention.

| Field | Notes |
|---|---|
| `ts` | |
| `session_id` | The judgement column. See below. |
| `tool` | `search_entities` \| `search_raw` |
| `query_text` | **The asset.** Without it there is no quality half at all. |
| `entity_type` | the filter, when given |
| `from`, `to` | `search_raw`'s optional date range |
| `limit`, `result_count` | |
| `duration_ms` | Makes the ANN tripwire one `percentile_cont(0.95)`. |
| `derivation_epoch_id` | FK — one, not two, because the epoch is already itemised. |
| `results` | JSONB. Entities as **`(entity_type, natural_key, score)`**; raw as `(entry_id, score)`. |

**Keyed on `(entity_type, natural_key)`, never entity ids.** Full mode and the retraction cascade both reassign every entity id, while the unique constraint keeps the *domain* identity stable — so an id-keyed log would be invalidated by precisely the event most likely to prompt a replay. **Raw results keep ids**, a deliberate asymmetry: raw entries are immutable and have no natural key, and it gives retraction a precise cascade target.

**The stored scores are not a cross-time baseline, and that is fine.** Summaries re-derive on every merge, so the same natural key has a different summary and a different vector months later; a replay cannot diff new scores against logged ones because the corpus moved underneath them. A fair comparison runs **both** models against **today's** corpus, which is always possible because both are local and the query was kept. So the query text is the asset and the stored results exist for a different job — making a query *reviewable* ("that one came back wrong"), which is the only way judgements ever get made. **Stated explicitly so nobody builds the naive score-diff.**

**Why it is in v1 at all: a query log cannot be backfilled.** Every other deferral on this map is re-capturable later at the same cost. This one is not — skip it and the day you want to compare models you start from zero and wait for a query set to accumulate. Deferring does not postpone the cost, it postpones *the start of the clock*. Structurally the same argument as "tag + digest at capture".

**Both tools are logged, which is forced** — the fallback signal below cannot exist unless `search_raw` calls are logged too. It also happens to be right for the tripwire: no ANN index exists on *either* layer, and raw rows grow faster than entities, so raw is what hits the wall first.

**Judgements: a session id, and nothing else.** Sessions are stateful by force (§7.5), so the server has a session identity at every `tools/call`. The tool description names the trigger *reach for `search_raw` when scores come back uniformly low* — so `search_raw` shortly after `search_entities` in the same session **is** a relevance judgement, revealed rather than self-reported. One column turns it into a negative signal: here are the queries entity search failed on. **Noisy, and recorded as such** — there is also a *structural* reason to fall back (the entry may be newer than the last run), so some fallbacks are not quality failures; the optional date range gives a partial filter.

**"Same session" has three different grains, and the coarsest is why the predicate is time-bounded.** Measured (#33 Gate A, #34):

| Entry point | One session lasts |
|---|---|
| Claude Code over loopback HTTP | one client session — 8 sessions were served by one server process over 944 s |
| Claude Code over stdio | one `claude -p` invocation — a fresh process each time |
| **Claude Desktop over stdio** | **one app launch** — which can be days, and spans every conversation in it |

The Desktop grain is the problem: `search_raw` in one conversation would otherwise read as a judgement on a `search_entities` from an unrelated conversation hours earlier. So the pairing rule is **same session *and* within a bounded interval** — a starting-point value (§13.4), not a measurement. **Store the session id raw and apply the interval at read time**, so the bound is re-cuttable against logged history rather than baked into rows.

**The session id is minted by Tome, not lifted from the transport.** `session_id` is `None` on stdio, so there is nothing to read; a process-lifetime UUID gives exactly the grains in the table above. That the id is a *process* identity rather than a conversation identity is the whole of the finding — for Desktop, process means app-launch-to-quit. (#34, #33)

Row cost ~650–700 bytes, results dominating: ~4 MB / ~18 MB / ~73 MB per year at 10 / 50 / 200 searches a day. **Capacity is irrelevant at any window**, which is what makes retention purely a privacy dial (§8.5).

*Source: #23 in full.*

### 3.9 Type Suggestions

Written by enrichment when classification strains, in two kinds:

- **`no_fit`** — the entry is a poor/low-confidence fit for *every* existing type. Records why it strained plus a guessed name for a possible new type.
- **`ambiguous`** — several types fit plausibly and confidence fell below threshold. Records the competing types.

They are recorded as `enrichment_events` rows (§3.5 lists them among what that table captures) and are therefore **not deleted by full mode**, which deletes Entities only. `review_schema` bounds them by *time* instead (§5.7). Their classification as "derived" in §3.1 is about **migration cost** — nothing needs migrating because re-derivation refills them — not about being wiped.

Three consequences follow from their living in the log, and none needed a separate ruling: they **cascade on retraction** with their entry (a suggestion is a statement about an entry that no longer exists); they fall inside #19's never-prunable *current governance window* class, so **#19's "no second exception" stands**; and full mode leaves them alone, which is what makes #17's window necessary rather than a defect.

*Source: #10, #12 §7, #14 §6.*

### 3.10 The retraction ledger — outside Postgres, on purpose

An append-only, **content-free** file recording `(raw_entry_id, retracted_at, reason_code)`. It is held outside the database *so that restoring the database cannot restore it*.

Its sole purpose is to name the Raw Entries that must not exist. It **replays on every start, not only after a restore** — `tome-migrate` runs it unconditionally, and replay is an idempotent `DELETE` by id. That deletes the "restored and forgot" failure mode entirely, which mattered because a silent resurrection would be re-enriched into Entities by the next timer tick.

Consequences worth stating:
- **Undoing a regretted retraction is an explicit act**: delete its line from the ledger *first*, then restore.
- Being content-free, it is safe to retain indefinitely and it **travels with the backups** (§8.2) rather than beside them.
- **Its loss is silent** — nothing else would notice, and the guarantee simply stops holding. That is why it is in the backup set.
- It is the reason `pg_dump` beats btrfs snapshots structurally rather than on cost: a dump composes with a replay into the *restored* database, whereas a read-only snapshot cannot be replayed into at all and only deleting it removes the content (§8.2).

*Source: #18 §4, #19.*

### 3.11 Indexes, storage, and the two extensions

| Obligation | Why it is not optional |
|---|---|
| **`SET STORAGE PLAIN` on both vector columns** | A 1024-dim vector is ~4 KB, past Postgres's ~2 KB TOAST threshold, so by default every vector goes out-of-line and a sequential scan detoasts every row — quietly undoing the entire exact-search analysis. |
| **`UNIQUE (entity_type, natural_key)`** | The merge key. `ON CONFLICT` targets it. |
| **GIN trigram index on `entities.natural_key`** | Serves the `word_similarity` membership branch (§6.1). |
| **`pgvector` + `pg_trgm`** | Distro RPMs (`pgvector` 0.8.0; `pg_trgm` from `postgresql-contrib`). pgvector must be installed *before* any restore is attempted — the dump opens with `CREATE EXTENSION vector`. |
| **No ANN index on either layer** | §6.2. Revisit at the tripwire. |
| **Fixed `vector(1024)`**, not an unconstrained `vector` | No index needs it, but mixed dimensions would break every query at *runtime* instead of at migration time. A model change is DDL plus a re-embed. |
| **`chattr +C` on the Postgres data directory before `initdb`** | Postgres on copy-on-write btrfs fragments badly and suffers write amplification. Applying it after the fact does not affect existing files. |

*Source: #15 §10, #16 §4–5, #19.*

---

## 4. Enrichment pipeline

### 4.1 The three run modes

Only **one run may be in flight at a time**, enforced by a Postgres advisory lock (§4.8).

| Mode | What it does | Reached by | Cost |
|---|---|---|---|
| **`incremental`** | Processes only pending entries. The normal operation. | 15-min timer, or `trigger_enrichment` | seconds to minutes |
| **`full`** | `pg_dump` the entity table → `DELETE FROM entities` → reset every raw entry to `pending` (`WHERE text IS NOT NULL`) → the ordinary loop. | `trigger_enrichment({ mode: "full" })` | **~5 h / 1k, ~25 h / 5k, ~50 h / 10k** |
| **`reembed`** | Rewrites only the vectors whose embedding epoch is no longer current, over **both** layers. No extraction, no wipe, no dump. | **`tome-enrich --reembed` — CLI only, never MCP** | **~6 min / 10k** |

**Full mode *is* incremental mode with a wipe in front of it** — no `run_id` on entities, no live-set pointer, no second entity set. Build-alongside-then-swap was considered (atomic flip, revertible by one row update) and rejected for the simpler schema: the pre-wipe dump recovers most of the revertibility as an operational step, and `search_raw` covers the read gap.

**When a full run actually happens:** manually and rarely — after swapping the enrichment model, adding or retiring an entity type, tuning the extraction prompt or the disambiguation rules, or fixing an over-merging natural key. Never part of normal operation.

**`reembed` exists because "re-embed everything" was otherwise inexpressible**: phase 1 sweeps rows *missing* an embedding, and entity vectors are `NOT NULL`, so nothing could say "these vectors are fine, they are simply from the wrong model." Its predicate is `embedding_epoch_id != current`, the same shape as the pending sweep and therefore **idempotent and resumable** — kill it halfway and re-running finishes. The manual `UPDATE … SET embedding = NULL` runbook cannot touch entities at all under `NOT NULL`, and would put `search_raw` into silently-partial results. Folding it into full mode is fifty hours to do a six-minute job.

```sql
-- tome-enrich --reembed
raw_entries WHERE embedding_epoch_id <> $current AND text IS NOT NULL
entities    WHERE embedding_epoch_id <> $current
```

Raw carries the Tombstone predicate; entities cannot be tombstoned. Note that it reads **`embedding_epoch_id`** on both layers and never touches `derivation_epoch_id` — that separation is the whole reason entities carry two stamps (§3.4).

**It is CLI-only because it follows a deliberate operator act** — an `ollama pull`, a model swap — and belongs behind a log-in-to-the-box gate, consistent with how full mode's blast radius is reached. An agent has no business pressing it.

**Reads during a destructive mode.** Refused with an error naming the alternative, never silently degraded:

- **Full run:** `search_entities` errors — *"entity layer rebuilding, 1,240/5,000 processed; use `search_raw`."* This is a real fallback, not a blackout: raw is never wiped. `capture_entry` and `get_enrichment_status` keep working throughout.
- **`--reembed`:** the *affected* tool refuses, naming the operation, while the other layer stays up — because the raw and entity halves are separate phases, so the tiering degrades to a working fallback instead of going dark.

Why refuse rather than serve partial results: every raw entry goes through `qwen3:14b` sequentially on one GPU, so a full run is **hours**. Silently returning partial results for hours from the primary surface would mean working with an agent that quietly has amnesia.

**Crash recovery is free in every mode.** Each entry commits atomically and the wipe already reset everything to `pending`, so a crashed run leaves the remainder plainly `pending`: re-triggering resumes where it died. **Run scope is fixed at start** — entries captured mid-run stay `pending` and land in the next incremental run, so a run never chases a moving target.

*Source: #12 §8, #17.*

### 4.2 Two phases, divided by kind of work

1. **Phase 1 — embed** every raw row missing an embedding. Sweeps **every** such row, not just newly-captured ones, so nothing is lost to time. **Batched** — measured at 105 ms/entry singly against 37 ms at batch 50, worth ~3×, and `/api/embed` already takes an array.
2. **Phase 2 — enrich** every `pending` row, and embed the Entities it produces.

The phases originally existed to pay a 9 GB model load exactly once. **That is superseded**: both models are co-resident (§7.7), so there is no swap, and the phases now divide work by **kind**. The VRAM budget is untouched because the embedder is resident either way.

*Source: #12 §6, #16 §3, #17.*

### 4.3 The per-entry state machine

```
                    ┌──────────────────────────────────────┐
                    │                                      │
  capture ──▶ pending ──▶ [embed] ──▶ [extract] ──▶ enriched
                    ▲         │            │
                    │         │            ├─▶ transient failure ──▶ failed
                    │         │            │      (attempt_count++, N=3)
                    │         │            │            │
                    └─────────┴────────────┴────────────┘
                              retried silently

                                          ├─▶ deterministic, or N exhausted
                                          │        ▼
                                          │   resolution_required + reason_code
                                          │        │
                                          │        ├── resolve_entry retry    ──▶ pending
                                          │        ├── resolve_entry set_type ──▶ pending (+ Type Override)
                                          │        └── resolve_entry skip     ──▶ skipped (Tombstone)
                                          │
                                          └─▶ retract_entry (from ANY state) ──▶ row deleted
```

**The invariant:** every Raw Entry is either **progressing** or **explicitly awaiting a human**. There is no third state where it loops forever unnoticed. An earlier draft retried all `failed` rows on a weekly backoff; that was rejected for converting a loud permanent failure into a quiet recurring one.

**No `in_progress` state.** With the single-runner lock and per-entry transactions, a crashed run leaves rows plainly `pending` — already the correct state, self-healing, with no stale-claim reaper and no orphaned entities to clean up. Live progress comes from the run record.

*Source: #12 §4.*

### 4.4 Budgets, and the pre-flight assertion

Every measurement below was taken on this machine at `num_ctx: 16384`, `temperature: 0`, thinking disabled, `q8_0` KV cache.

| Quantity | Value | Note |
|---|---|---|
| Extraction prompt, measured | **P = 1,215 qwen3 tokens** | Built faithfully from the seven type definitions with `_Avoid_` lines verbatim, plus the output contract and Type-Suggestion rules. The earlier 3–6k assumption was 2.5–5× too high. |
| **Stated prompt budget** | **3,000 qwen3 tokens**, asserted at run start | 2.5× today's measurement. Unbounded, the prompt silently narrows the largest enrichable entry — and immutability makes that narrowing **retroactive**. |
| `context` allowance | **flat 500 qwen3 tokens**, added unconditionally | Budgeting the cap, not the actual context. |
| Output reserve | **1,500 tokens**, and **`num_predict` is bounded to it** | |
| Tokenizer ratio | **qwen3 = 0.906 × bge-m3**, stable across five sizes | The capture gate counts in bge-m3 tokens; the enrichment budget is spent in qwen3 tokens. The gate is ~10% conservative by construction. |
| Per-request `num_ctx` | **~16,384** | Correct and needs no revisiting. |
| Worst case at the 2048 ceiling | `1215 + 1856 + 500 + 1500 = 5,071` against 16,384 | ~11.3k spare. |

**The pre-flight budget assertion**, in the runner, before any model call:

```
P + entry_tokens × 0.906 + context_allowance + reserve  ≤  num_ctx
```

Pure arithmetic — the entry's token count is known from capture, P is known at run start. Over budget is a `resolution_required` reason code, not a model call. **This is what turns the collapsed threshold into a guarded invariant rather than an argument that happens to hold.**

**The two counts diverge, by design.** The capture gate and this assertion do not measure the same thing, and a spec that made them agree would now be wrong:

- **The capture gate counts `text` alone** — `context` is not embedded, and the inline embed *is* the size oracle.
- **This assertion counts `text` + `context`** — extraction genuinely reads `context`.

So the requirement is not that they count the same thing, but that **each counts its own call's actual input**.

**`context` has no token oracle.** It never reaches `/api/embed`, so its token count is never measured; only its character count exists, against a 2.1–4.2 chars/token spread. Hence a flat constant rather than an estimate: the failure mode being guarded against is a **cliff**, not a slope (see below), and an estimator occasionally 20% low is exactly the wrong error shape against a cliff, while a constant that is always high cannot be wrong.

**The two failure modes this arithmetic exists for.** Both were measured, and both are worse than they sound:

1. **The prompt-side cliff is silent and inverted.** Send more than `num_ctx` and retention is exactly **`num_ctx/2 + 2`** however much was sent — and it is the **tail** that survives. No error, no `truncated` field, `done_reason` stays `"stop"`. This is llama.cpp context-shift, which Ollama passes unconditionally with **no environment variable to disable it**. Because the prompt puts instructions first and the entry last, **what gets discarded is the entire instruction block** while the entry survives — extraction with no rules, recorded as `enriched`.
2. **Runaway generation, not context exhaustion, is the reachable failure.** At 6,046 tokens — 26% *below* the 8192 embedder cap — the same entry at `temperature: 0` went **2 clean / 2 unparseable (n=4)**. The worst run emitted **17,957 output tokens for a total of 24,618 against a 16,384 window**, so context-shift fired *mid-generation*, sliding the window off the instructions and then off the entry; it burned **602 s — 33× the 18 s baseline — producing nothing**. Bounding `num_predict` converts that into an ordinary, loud, cheap parse failure.

*Source: #24, #25 §9.*

### 4.5 Capture-time embedding: inline, 5 s, falling back to deferred

`capture_entry` attempts the embedding inline with a **5-second timeout**. On timeout or Ollama error the row commits with `embedding NULL` and state `pending`, and the tool **returns success as normal**. There is no error to hand the caller and no extra branch — the fast path's `catch` *is* the deferred path.

**Nothing is lost to time**: phase 1 sweeps every row missing an embedding, raw is immutable, and full runs reconsider everything.

**Visibility.** A single timeout is *routine*, not a signal — a structured log line only. Warning on it would make `warnings` noise and train it to be ignored. Escalation happens only on **persistence**: a row still un-embedded *after* a run completed means the pass failed its job, which counts toward `attempt_count` and feeds §5.10's warnings.

**Capture-time timeouts never count toward `attempt_count`.** They are best-effort and expected during runs; if they counted, capturing three entries mid-run would exhaust the budget and mark three perfectly good entries `failed` without a single real error.

**Why this path still exists.** Its original rationale — avoiding a model swap — was voided when both models became co-resident. It is re-justified: entity embedding makes the enrichment runner a *continuous* client of the same `NUM_PARALLEL=1` embedder that serves interactive capture, so a capture embed can queue behind an entity embed. Fine on the numbers, and the deferred path is what covers it.

*Source: #12 §5, #16 §3, §7.*

### 4.6 Transactions, locking and concurrency

- **Each entry's state is written in the same transaction as the Entities derived from it.** Per-entry atomicity: either the Entities exist and the row is `enriched`, or neither happened.
- **No transaction is held across an HTTP call.** The LLM calls happen first; then one short transaction writes entry state, Entities and vectors atomically.
- **The per-entry transaction takes `SELECT … FOR UPDATE` on the raw row**, and `retract_entry` takes the same lock. Without it, a run that read the text *before* a retraction commits its Entities *after* the purge — orphans no query would ever notice. A retraction issued mid-run blocks for one entry (~18 s) and then wins.
- **A Postgres advisory lock** enforces one run at a time. It is the right mechanism because it is the only one covering *every* entry point — timer firings, `trigger_enrichment`, and a run started by hand at a shell — since all three contend for the same lock in the same database.
- **A message queue was considered and rejected.** The raw table already *is* a durable transactional work queue (`enrichment_state = 'pending'`). A broker would be a second source of truth about what needs enriching, and everything it would buy is already spoken for: retries → `attempt_count`, backlog visibility → `pending_count`, crash safety → per-entry transactions. Net effect would be one more service that can die silently. The real fragility the queue instinct pointed at was the LLM call sitting in the write path, and that was fixed by moving it out.

*Source: #12 §4–5, #18 §1.*

### 4.7 Failure classification and reason codes

| Class | Examples | Behaviour |
|---|---|---|
| **Transient** | Ollama down, timeout, model loading, **unparseable model output** | Retried silently on subsequent runs, N = 3. A human can do nothing useful, so surfacing them would be noise. |
| **Deterministic** | over-budget (§4.4), irreducible type ambiguity below threshold, a genuine parse refusal | Stops immediately, marked `resolution_required` with a reason code, awaits a human. **No backoff retry.** |

**Unparseable output is transient, and this corrects the original taxonomy.** Measured at **~50% on identical input at `temperature: 0` (n=4)**, it is precisely what a retry fixes, and N=3 clears it with high probability. As originally written, the taxonomy routed Tome's most likely real failure to a human instead of to the retry loop. It reaches `resolution_required` only after retries are exhausted.

**Reason codes must distinguish exhausted-retries from a deterministic refusal**, so triage never mistakes "the model had a bad night" for "this entry can never be processed." The set the tickets name:

- `too_large` — reachable **only** via the deferred-embed path, where capture could not measure the text (§5.1)
- `over_budget` — the pre-flight assertion refused
- unparseable output, **retries exhausted**
- unparseable output, **deterministic refusal**
- irreducible type ambiguity

Exact spellings are the builder's; the distinctions are not.

*Source: #12 §4, #18 §6, #24.*

### 4.8 Cadence and the idle path

A **~15-minute monotonic systemd timer**, `OnBootSec≈5min`, **no `Persistent=`**. Every firing does two cheap checks **in order, before any model is loaded**:

1. **Try the advisory lock, non-blocking. If it cannot be acquired, exit immediately.** A run is already underway. This is essential, not defensive: a full run takes hours and plows straight through dozens of timer windows, and even an incremental run can outlast 15 minutes on a large backlog. A skipped firing is **normal operation**, logged at debug level, and **must not** count as a failed run or touch `last_successful_run_at` — or a long full run would set off its own stale-run alarm.
2. **Check `pending_count` and the un-embedded count** (both carrying `AND text IS NOT NULL`). Exit without loading any model if there is nothing to do, so idle cost is one query. Measured import cost for the runner is **0.17 s warm / 0.45 s cold**, which against a 15-minute timer is noise.

**Nightly was rejected** because it guarantees the "I told Tome this an hour ago and it can't find it" failure. Captures made in one session are enriched by the next firing, and a burst batches naturally into one run.

**The timer *is* the retry mechanism.** With a `oneshot` runner fired by a timer, no `Restart=` is needed — a failed run leaves entries `pending` and the next tick picks them up. This dissolves the crash-loop-backoff question rather than answering it.

**Staleness is measured against uptime, not wall-clock age.** The machine is dual-booted and sometimes off, so a wall-clock alarm would fire every time it returns from Windows when nothing is wrong — landing on the one channel that has to stay quiet enough to be trusted. Alarm only once the system has been up longer than the threshold without a successful run, and **tolerate a `last_successful_run_at` in the future**, which a backwards clock correction after boot can produce.

*Source: #12 §9, #15 §6, #20.*

### 4.9 The extraction prompt

**The prompt is code, not configuration.** It ships in the `tome` package, in git, deployed by `make deploy`. Identity is the hash of the rendered text, computed at run start; history is the commit log, so "which prompt produced this" resolves to an actual commit rather than an opaque hash. `/etc/tome/` was named early and **rejected**: the prompt is the program logic defining what an Entity *is*, and it will be edited more than anything else in the system — there it would sit outside git, outside `make deploy`, outside review and outside the backup allowlist, editable in place on a live system with no record of what it previously said. The price is that editing it needs a deploy rather than an `$EDITOR`, which is one command on the same machine and is what makes it versioned at all.

**Required content:**

| Requirement | Why |
|---|---|
| **The seven type definitions and their `_Avoid_` lines, verbatim from CONTEXT.md** | They are already written as decision rules; they resolve most ambiguity before it becomes a runtime problem. |
| **Exactly one type is forced** per extraction; multi-typing is off the table. | CONTEXT.md's constraint. Ambiguity is made *visible* instead (§3.9). |
| **`Fact` is explicitly not the tie-break** | CONTEXT.md already says "a catch-all, not a default". Draining ambiguity into Fact turns it into the junk drawer that eats the schema's signal. |
| **Per-type natural-key specificity**, biased over-specific, coarse only for Person and Project | §3.4. |
| **The `context` subordination rule, verbatim** | §3.3. |
| **The name-precedence rule:** *when the summary bound forces a cut, drop narrative detail before dropping a named entity.* | Precedence, **not** preservation — "always keep every proper noun" is unbounded and would blow the bounded-summary obligation and degrade the primary vector. Needed because repeated re-summarisation drifts toward "works with Mark on several projects", and relationships were ruled out on the premise that prose carries them. Costs only prefill; **owes no full run**, since the eroding hub keys are the ones re-merged on every mention. |
| **No concrete example natural keys** | **Measured, reproducible in 8 of 12 responses:** example keys in the prompt are re-emitted as **fabricated Entities** with confabulated summaries welded onto real details — a Commitment claiming "promised to send Alex the retrieval report by August 1st" when the entry says the opposite. *A fabricated Commitment in a memory-keeper does not read as an error; it reads as a memory.* Use abstract or clearly-fenced examples. |
| **A case-preservation carve-out** in the natural-key rules | Observed: `ROCm` → `roc-m`. |
| **Prefer the event's own date over `captured_at`** | Observed: `2026-07-26-standup-on-22nd`. |
| **Thinking mode disabled** | Otherwise `qwen3:14b` returns a reasoning preamble instead of clean JSON. |
| **A stated budget of 3,000 tokens, asserted at run start** | §4.4. |

**Whole-corpus context is ruled out, and the bound is structural.** Corpus knowledge enters at exactly two points and Postgres answers both: identity resolution is an indexed lookup on `(entity_type, natural_key)`, and merge needs only **one Entity's summary**. So a single call is bounded at *prompt + one entry + one summary* — **O(1) in corpus size, forever.** Retrieval is also strictly better than stuffing: a unique-index hit is exact where spotting a match inside 100k tokens is probabilistic. The only thing that would consume a large window is batching entries per call, which is ruled out structurally by per-entry state, per-entry events, and one malformed JSON failing fifty entries with no attribution.

*Source: #12 §2, #15 §5, #17, #21 §4, #24.*

### 4.10 Extraction recall — the known limitation

**One extraction pass per entry may not be enough, and this is the one open question the map could not ticket.**

Measured, holding 40 subjects constant and varying only how many captures they arrive in:

| Same 40 subjects, as… | Entities | per subject | wall |
|---|---|---|---|
| 1 entry (4,525 tok) | 18 | 0.45 | 42 s |
| 4 entries (~1,130 tok) | 41 | 1.02 | 92 s |
| 10 entries (~450 tok) | 36 | 0.90 | 93 s |
| **40 entries (~113 tok)** | **46** | **1.15** | 133 s |

**One subject per capture recovers 2.6× the Entities of one large capture**, with zero parse failures at any granularity. Recall runs 1.00 → 0.25 from 620 to 7,620 tokens. There is no interior optimum.

**And Decisions do not scale at all.** The test corpus held 7 decision-shaped subjects, so expected Decision counts across six sizes were ~1, 1, 2, 4, 6, 7. Actual: **1, 1, 1, 1, 1, 1** — including the run that extracted 42 Entities. What grows with entry length is **Person and Event**, name-and-date shaped — the two types a calendar and a contact list already cover. **The analytical content a memory-keeper exists for is exactly what is lost.**

Holding the capture ceiling at ~2048 tokens *mitigates* this — a 2k entry holds few enough subjects that the loss is small — but does not remove it: 3–4 decisions in one entry would still yield one. The suspected fix is a per-type or two-stage extraction pass, which is a revision of the one-call-per-entry state machine and therefore expensive to get wrong.

**Recorded as a limitation, not resolved here.** It is not ticketable because nothing can yet say how much recall is actually being lost in practice — that needs the query log plus a judged set, both of which sit behind 90 days of real usage. **Retrieval telemetry landing does not close it**: telemetry measures *retrieval* quality, and under-extraction is invisible to it **by construction**, producing **plausible results rather than empty ones**. Ask about a decision and the one extracted Decision returns looking correct; nothing signals that six others were never derived.

*Source: #24, map Not-yet-specified.*

---

## 5. MCP tool surface

**Nine tools, one endpoint, one server.** A separate `tome-admin` server was considered — it would keep the destructive verbs out of ambient agent sessions — and rejected: a second endpoint, a second consumer of the Host allowlist, another bridge on Desktop, and extra unit topology, all against a speculative risk on a single-user machine with no adversary. Tool descriptions carry the discipline instead, and MCP clients can disable a tool per-project if over-reach ever bites.

**The `debug` convention.** Every tool takes an optional `debug?: boolean` (default `false`) that expands the return shape with provenance and internal fields. Default responses stay lean.

**Three deliberate departures from lean-by-default**, each with a reason stronger than convention:

| Field | Where | Why it is not `debug`-gated |
|---|---|---|
| `warnings` | `capture_entry` | Capture is the one path that cannot be avoided, so it needs no dashboard, no polling and no discipline (§5.10). Absent when healthy. |
| `score` | `search_entities` | The caller owns the fallback routing decision and was otherwise given nothing to decide with — three results with no scores cannot be distinguished from the best of a bad lot. The score is the *input* to a delegated decision, so it sits on the other side of the line `debug` draws. |
| `context` | `get_enrichment_status` items | Those items exist solely to decide `retry`/`skip`/`set_type`, one deterministic failure reason is irreducible type ambiguity, and `context` is the field extraction reads *specifically* to break type ties. Withholding the disambiguating field from the surface whose whole job is disambiguation would be perverse. **The item is a decision packet, not a search result.** |

The always-on `query_log` is **not** a fourth exception: `debug` governs what the *caller* sees, and the log returns nothing to the caller.

**Tool descriptions are spec artifacts, not implementation detail.** Two load-bearing routing triggers and one prohibition live only in descriptions; they are specified in §5.11 and must be written, not improvised.

*Source: #11, #12 §7, #14, #16 §6, #18, #25.*

### 5.1 `capture_entry` — the only write path

```
capture_entry({
  text: string,
  context?: string,          // ≤ 1,000 chars; referents and setting only
  captured_at: string,       // ISO 8601, REQUIRED — no server default
  debug?: boolean
})
→ { id, warnings?: string[] }                             normally
→ { id, captured_at, source, warnings?, … }               when debug: true
```

`captured_at` is required rather than defaulted so the caller is always explicit about *when the thing happened*, including backfills. `source` is inferred from the handshake, never agent-supplied. The embedding and its epoch stamp are computed server-side.

**It refuses text it cannot embed.** `truncate: false` is set on **every** embed call, always — the alternative is storing a vector of the first 8% of a document and calling it the entry's embedding. The inline embed *is* the size oracle: exact `prompt_eval_count` on success, a clean 400 on oversize, no tokenizer and no heuristic. The limit lives in `tome.env` as the embedding model's measured effective context.

**The ceiling is ~2048 tokens, and the reason is quality rather than capacity.** It was originally a measured runtime artifact; that measurement was then corrected — the 2048 cap was Ollama's default `num_batch`, and lifting it gives the full 8192. The ceiling was **nevertheless held at ~2048**, on §4.10's evidence and on an asymmetry: *raising is reversible at any time, while an entry captured at 8192 is immutable and permanent — so the reversible option is the low one.* 2048 also happens to sit at the knee where recall begins to fall.

**Why reject rather than accept-and-flag.** The decisive asymmetry is *when* the content is recoverable. At capture it is still in the calling agent's conversation and a failed `capture_entry` rolls back whole, so rejection costs a retry. One tick later it is a row with no embedding that no read tool can reach, whose only exits are destruction or retraction. Splitting is also the caller's job on the merits — it knows the semantic boundaries, where a server-side split would cut mid-sentence and break the `→ { id }` contract by returning N ids. **And splitting is measurably the better path, not a consolation** (§4.10): merge-on-natural-key reassembles the subjects, and 40 separate captures returned 46 distinct keys with no collisions.

**The rejection is a tool-level error result** (`isError: true` with text content) — not a JSON-RPC protocol error, and emphatically **not** a `warnings` entry, which rides on *successful* captures and would return `{ id }` for a write that did not happen. The text is written **for the model as primary reader** and carries three elements:

1. **Permanent — do not retry unchanged.** Otherwise a model retries identical text until it gives up.
2. **The numbers** — characters/tokens received, and the cap.
3. **The remedy** — split into parts under the cap, one `capture_entry` per part.

Both branches then end well: a model that silently splits stores the memory correctly; a model that surfaces the error tells you. **Ollama's upstream message is translated, not passed through** — *"the input length exceeds the context length"* tells a model nothing about splitting.

**Build-time obligation:** FastMCP masks unexpected exception detail behind a generic message, and only its dedicated tool-error type is guaranteed to deliver the text. Raised as a bare `ValueError`, all three elements become "internal error", reinstating the silent failure this exists to prevent. **The same obligation covers `context`'s 1,000-char rejection.**

**A ~40,000-character absurdity backstop.** When the inline embed defers on its 5 s timeout, capture cannot measure the text, so an oversized entry would land `pending` and fail in phase 1 (→ `resolution_required`, `too_large`, text intact). To stop a 40-page paste entering that way while Ollama is busy, capture also refuses above a deliberately generous bound — ~9,400 tokens even at the most favourable 4.24 chars/token, so it can never false-reject a real note. **Exact check when available, absurdity check always.**

**A character limit can never be tight** — chars/token varies more than 2× with content shape (prose 4.24, terse fragments 2.89, URLs+ids 2.32, JSON/code 2.11), which is why the real gate is the token oracle.

*Source: #11, #18 §6, #22 §1, #24, #25 §8.*

### 5.2 `search_entities` — the primary surface

```
search_entities({
  query: string,
  entity_type?: "Person" | "Project" | "Preference"
              | "Decision" | "Fact" | "Commitment" | "Event",
  limit?: number,
  debug?: boolean
})
→ { id, entity_type, summary, score }[]                                        normally
→ { …, natural_key, source_entry_ids, type_confidence,
       considered_types, last_enriched_at }[]                                  when debug: true
```

Mechanism in §6.1. Refuses with an error naming `search_raw` during a full run or an entity re-embed (§4.1). `score` is in the normal response (§5).

The `entity_type` filter is an ordinary `WHERE` predicate, and the default query is **unfiltered** — which is what bounds the cost of a mis-type: a mis-typed Entity is still found by the default path, and only an explicitly filtered query misses it. Not worth duplicating Entities and letting the copies drift.

*Source: #11, #12 §2, #16.*

### 5.3 `search_raw` — the fallback, selected by the caller

```
search_raw({
  query: string,
  from?: string,
  to?: string,
  limit?: number,
  debug?: boolean
})
→ { id, text, captured_at, score }[]                                    normally
→ { …, context, source }[]                                              when debug: true
```

A separate tool, **not a server-side auto-fallback** — the calling agent decides when to reach for it. Excludes Tombstones by virtue of their having no text.

`context` stays `debug`-only here, and for a stronger reason than convention: because `context` is excluded from the vector, **a returned `context` is not why the result matched**, so in the normal response it would hand the caller a string that reads like matched content and rationalise a hit from text that played no part in it.

Two triggers must be in the description (§5.11). Refuses during a raw re-embed.

*Source: #11, #16 §6, #21, #25 §6.*

### 5.4 `trigger_enrichment`

```
trigger_enrichment({ mode: "incremental" | "full" })
→ { run_id, status }
```

Same code path as the timer. The advisory lock makes a manual trigger during a scheduled run a **no-op, not a conflict**. `reembed` is deliberately absent — CLI only (§4.1).

*Source: #11, #12 §9, #17.*

### 5.5 `get_enrichment_status` — status, and the attention list

```
get_enrichment_status({
  run_id?: string,           // omit for most recent
  include_items?: boolean,   // default false
  only_new?: boolean,        // default true
  debug?: boolean
})
→ { run_id, status, started_at, completed_at?, entries_processed?, entities_created?,
    pending_count, failed_count, resolution_required_count,
    un_embedded_count, tombstoned_count, last_successful_run_at,
    entities_by_epoch: [{ derivation_epoch_id, entity_count }] }
→ + items: [{ raw_entry_id, reason_code, attempt_count, last_error,
              last_failed_stage, captured_at, text_excerpt, context,
              prior_decisions: [{ action, reason_code, note, at }] }]
```

**Itemising is a zoom on the same concern, not a sibling tool** — this already reported `resolution_required_count`, and two tools counting the same set can disagree, at which point one of them is wrong.

**Only `resolution_required` rows are itemised.** `failed_count` (transient) and `un_embedded_count` stay counts: they describe **service health, not triage**, and `resolve_entry` can do nothing useful for a transient failure. A non-zero `failed_count` beside a healthy `last_successful_run_at` sends you to journald. Itemising every unhealthy row was rejected because the deferred-embedding path makes un-embedded rows *routine* mid-run — permanent noise in a list whose entire value is being exception-driven.

**Retirement needs no new schema and no dismissal flag.** Each item carries its decision history joined from `enrichment_events`, and `only_new` (default true) suppresses items whose current reason code matches a prior `skip` on the same entry. This works because the log is already append-only and DB-enforced, and because full mode deletes *Entities* only — the log survives every rebuild. A denormalised `last_triaged_at` pair was rejected as a second, lossy copy governed by a "this column is reset but that one is not" rule a future migration will forget.

**`entities_by_epoch` is the passive half of §5.10's asymmetric surfacing** — "how mixed is my store?" answerable on request, silent otherwise.

`last_successful_run_at` is what catches the *nothing ran at all* failure — broken timer, Ollama down, service did not come back after boot — which produces zero errors and would otherwise leave the entity layer quietly going stale. Measured against uptime (§4.8).

*Source: #11, #12 §7, #14 §1–2, #17, #25 §6.*

### 5.6 `resolve_entry` — triage, and zero entity writes

```
resolve_entry({
  raw_entry_id: string,
  action: "retry" | "skip" | "set_type",
  entity_type?: EntityType | null,   // set_type; null clears an existing override
  note?: string,
  debug?: boolean
}) → { raw_entry_id, enrichment_state }
```

Reaches **only `resolution_required` entries**.

- **`retry`** — reset to `pending`, zero `attempt_count`. What you call after fixing the prompt, swapping the model, or sharpening a definition in CONTEXT.md.
- **`set_type`** — record a **Type Override** and reset to `pending`.
- **`skip`** — **Tombstone** the entry: null `text`, `context` and `embedding`; retain `id`, `captured_at`, `source` and the reason code; set terminal state `skipped`; append an event row recording the deletion with the reason code, the note, the original token count and a **~200-character excerpt**.

**All three write raw-entry state and an event row. None writes an Entity**, so the no-direct-entity-writes rule is untouched.

**The Type Override is durable *input* to re-derivation, not derived output** — which is what keeps it clear of that rule. Enrichment consumes it on the next pass and the Entity remains fully derived; without persistence across a full run the override would be meaningless, since re-derivation is the only thing that reads it.

**It applies as a tie-break hint only**, firing *only* where classification would otherwise fall below threshold: extractions that strain resolve to the override type; confidently-classified extractions from the same entry are untouched. A blanket relabel was rejected because it fabricates mis-typed Entities for any mixed entry — forcing Preference onto an entry that also names a person and a project manufactures two wrong Entities deliberately. Keying the override to `(raw_entry_id, natural_key)` was rejected too: the key is model-emitted and its wording changes across prompt or model changes, so the override would silently stop matching at exactly the moment you re-run — and it is unusable for the `no_fit` case, where no key was minted.

**`skip` narrowed to unparseable content only.** Its original primary justification — an entry too large to enrich — is unreachable, because an entry that large could never have been captured. What remains is content the classifier cannot produce valid JSON for: a base64 blob, minified JSON, instruction-shaped text in a note *about* prompt engineering.

**Retaining an excerpt is safe because `skip` is not a retraction path.** An entry captured by mistake — wrong, private, duplicative — *enriches successfully*; it never fails, never reaches `resolution_required`, and `resolve_entry` never sees it. `skip` operates exclusively on entries the pipeline could not process. `retract_entry` is the escalation that removes even the excerpt.

**Full mode's reset is `WHERE text IS NOT NULL`.** It was first decided as unconditional — from-scratch means from-scratch, and a skip taken because the prompt was bad at the time deserves reconsidering. The Tombstone removes the case that reasoning defended: with the text gone, no prompt fix can ever make the entry classifiable, so resetting it is not reconsidering a decision but parking an unprocessable row in the queue permanently. **The carve-out is structural — *do not queue rows that cannot be processed* — not a preservation of a human decision, which stays overruled:** nothing about a *retryable* entry survives a full run, and `retry` remains the only thing that reconsiders a live decision.

Its description must state that it **records a decision a human has already made and must not be called autonomously** (§5.11).

*Source: #14 §3–5, #18 §6.*

### 5.7 `review_schema` — aggregate-only, windowed

```
review_schema({ since?: string }) → {
  window_started_at,              // default: since the last full run began
  confidence_threshold,
  types:     [{ entity_type, entity_count, source_entry_count, mean_type_confidence }],
  no_fit:    [{ guessed_type, count, example_entry_ids }],
  ambiguous: [{ competing_types: [A, B], count, confidence_p50, example_entry_ids }],
  confidence_histogram: [{ bucket, count }]
}
```

**Suggestions are aggregates, not a list to tick off — which dissolves retirement rather than solving it.** A recurring Preference-vs-Decision pair is evidence the type *boundary* is wrong; dismissing individual suggestions would delete exactly that evidence. Recurrence is the signal. A pair's count drops when you sharpen the definitions and re-run — nothing is ever marked as seen.

**The window is "since the last full Enrichment Run began".** *(Originally phrased as the current Derivation Epoch; restated when the Epoch became an input set with no time in it. Behaviour is unchanged.)* The reasoning is a double-count rule: a **full** run re-derives every entry and regenerates its Type Suggestion, so summing across a full-run boundary double-counts; an **incremental** run touches only pending entries, so summing across epochs *not* separated by a full run double-counts nothing. The window is therefore a *time* question answered from the run log, and it never needed epoch identity. `since` overrides it for deliberate cross-window trend analysis.

An itemised view with a review watermark was considered and rejected: it puts a write path on a read tool, adds a table, and re-introduces the resurfacing problem — every regenerated suggestion postdates the watermark, so a full run hands back the entire backlog as unreviewed.

**The confidence threshold is one global value, visible here but not writable through MCP.** A change is meaningful only paired with a re-run, and it is configuration rather than a decision the review loop makes. The histogram exists so the line can be re-cut counterfactually before anything changes. **Per-type thresholds were rejected** on the pipeline's own reasoning: type disambiguation lives in prompt-level `_Avoid_` rules rather than numeric tuning, and seven knobs is calibration there is no data to perform for one user. Its value is in `tome.env`, and the **starting point is 0.7 — a guess, not a requirement (§13.4)**.

*Source: #14 §6, §8; #17.*

### 5.8 `get_history` — audit, either id, lean by default

```
get_history({
  entity_id?: string,
  raw_entry_id?: string,
  limit?: number,     // default 50
  before?: string,
  debug?: boolean
})
→ { subject: { kind, id }, related_ids: [...],
    events: [{ run_id, stage, outcome, at, gist }],
    text?, context? }                                  // text/context for a raw_entry_id
→ events[].detail (full JSONB), context                when debug: true
```

Answers both "why does this Entity say what it says" and "what happened to this Raw Entry" — an Entity's `source_entry_ids` and a Raw Entry's derived Entity ids both come back as `related_ids`. Still resolves Tombstones, which is the point of keeping the id.

**It must return `text` when called with `raw_entry_id`.** There is otherwise **no tool that reads a raw entry by id** — `search_raw` needs an embedding to reach it, status items carry only a 200-char excerpt, and this returned events and `related_ids`. That gap bites twice: an entry landing un-embedded via the deferred path is unreadable, and `retract_entry`'s prefix guard is unusable for an entry found via an Entity rather than via `search_raw`. `context` rides along under `debug`.

It reuses `debug` rather than inventing a second flag, and needs to: an Entity mentioned 200 times carries 200 merge events each holding before/after summary text.

**Its bidirectional traversal is an audit path and nothing more.** Recorded explicitly so nobody later mistakes it for a free relationship graph (§10).

*Source: #14 §7, #18 §7, #21, #25 §6.*

### 5.9 `retract_entry` — the ninth tool

```
retract_entry({
  raw_entry_id: string,
  text_prefix: string,               // first ~40 chars, server-verified
  reason_code: "mis_capture" | "sensitive" | "duplicate",
  debug?: boolean
}) → { raw_entry_id, entities_deleted, entries_requeued }
```

**Not a fourth `resolve_entry` action.** Their reach is opposite: `resolve_entry` touches only `resolution_required` entries and cannot reach a mis-captured one; retraction reaches **any entry in any state**, including one already Tombstoned, and its common case is an entry that enriched perfectly. Folding it in would also put an irreversible content-destroying verb inside the tool an agent calls for routine triage.

**The intuition that a retracted entry is "probably garbage anyway, so nothing was derived from it" is right about frequency and wrong about which cases need the feature.** Garbage and blank text is what *strains* the classifier, so it lands in `resolution_required` and `skip` already handles it. The entries needing a new mechanism are precisely those that classified cleanly — a wrong phone number, a private fact, a duplicate that merged into a Person summary. Safe to act on the intuition anyway, because the cascade self-calibrates: nothing derived means `entities_deleted: 0, entries_requeued: 0` at zero cost, with no special case.

**A server-verified `text_prefix`, not a bare id and not a `confirm` flag.** There is no undo and no trace, and ids arrive from `search_raw` in an agent's context, possibly several turns stale. The prefix converts "wrong id" from silent total loss into a legible 400, at the cost of one parameter copied from the search result the caller already holds. `confirm: true` is theatre — the calling LLM fills it in unread.

**A `reason_code` enum, not a free-text note.** For the `sensitive` case, a note restating what was retracted reintroduces the content it just removed: the audit trail becomes the leak.

**Under `bigint` ids the prefix guard is load-bearing, not defence-in-depth** (#30). A stale or off-by-one id lands on a **real neighbouring entry**, where a wrong uuid would land on nothing. The guard was chosen for exactly this failure, so it must never be relaxed to a confirmation flag and its verification must stay server-side.

Mechanics, cascade, and the precise guarantee are in §8.3.

*Source: #18 §1, §3.*

### 5.10 The `warnings` channel

`capture_entry` returns `warnings: string[]`, **absent when healthy**. Capture is the one path that cannot be avoided, so stuck work reaches the user in-band with no dashboard, no polling and no discipline. There is **no server-initiated SSE** and no push channel (§7.5, §9.3).

Six producers, and the split between transient and persistent is deliberate:

| Warning | Kind | Source |
|---|---|---|
| Last successful run is stale (measured against **uptime**) | transient | #12, #15 |
| Anything awaiting resolution | transient | #12 |
| Rows still un-embedded *after* a run completed | transient | #12 |
| A dump failed, its verify failed, or the free-space guard skipped it | transient | #19 |
| **Vectors span more than one embedding epoch — run `tome-enrich --reembed`** | **persistent**, until no stale vectors remain | #17 |
| **The journald leak tripwire found a hit** | **persistent**, cleared by the scoped purge | #26 |

**Warn on the cheap fix, report the expensive one.** An embedding-input change gets a persistent warning because clearing it takes six minutes, so nagging is proportionate. An extraction-input change gets only the passive `entities_by_epoch` count on `get_enrichment_status`, because warning persistently about a fifty-hour remedy you may rightly have declined is alarm fatigue that would poison the genuine stuck-work channel along with it.

**What must *not* go here:** a single capture-time embed timeout (routine, log line only), and a rejected capture (that is a tool-level error — `warnings` rides on *successful* captures and would return `{ id }` for a write that did not happen).

*Source: #12 §7, #17, #19, #26.*

### 5.11 Tool descriptions — the spec artifact

These are not documentation. Load-bearing behaviour lives only here, and it must be written rather than improvised.

**`capture_entry` — three things about `context`:**
1. **Prescribed content** — the referents `text` leaves dangling, and the setting of the capture. Motive and free-form "anything useful" are **excluded**.
2. **A prohibition** — `text` records what the user stated or asked to be remembered; if the agent has a read of its own it says so **in `text`** as honest content ("Claude's read: Mark seemed unconvinced by…"), never smuggled into `context` as neutral metadata. *This stands in place of an `attribution: stated|inferred` field, which was rejected because the label cannot survive the merge — an Entity fed by one stated and one inferred entry has no coherent value, and nowhere on the entity row to put it, so the label would be reliable on the fallback tier and structurally absent from the primary one. A prohibition also beats a label because tagging an inference legitimises it while still returning it as an Entity.*
3. **A populate-trigger** — populate `context` when `text` contains a referent that only the surrounding conversation resolves, or when the setting is not recoverable from `text`; **omit it otherwise.** *Making it required was rejected: a required field with nothing to say yields ritual filler that then feeds the classifier.*

**`search_entities` — the fallback trigger, concretely:** reach for `search_raw` when looking for a phrase or name believed written verbatim, when scores come back uniformly low, **or when the entry may be newer than the last enrichment run.** That last clause is structural rather than quality — a mid-run capture stays `pending` until the next ~15-minute tick.

**`search_raw` — a second, orthogonal trigger:** *reach for `search_raw` when the question is about frequency, recurrence, or anything spanning subjects — even if `search_entities` returned good-looking results.* This is not a duplicate of the relevance trigger. A pattern question fails *differently*: `search_entities` returns entirely **plausible** results and is still the wrong tool, because the passing mention was never extracted. A relevance check cannot detect that by construction, so without this trigger **the fallback is unreachable in precisely the case it exists for.**

**`resolve_entry`:** states that it records a decision a human has already made, and **must not be called autonomously**.

**`retract_entry`:** irreversible, leaves no trace, requires the verified prefix.

*Source: #10, #14 §3, #16 §6, #21 §2, #25 §5, §7.*

---

## 6. Search & retrieval

### 6.1 `search_entities` — exact vector similarity, plus a membership branch

**Two signals, one scale, no fusion.**

**Vector spine.** Exact k-NN over `entities.embedding`, which is over the entity `summary`. The queries arriving are LLM-written conversational phrasings against LLM-written prose — the vocabulary gap embeddings exist for and lexical search is worst at, and it is worse than usual here because the merge *rewrites* the summary on every contributing entry, so no original phrasing is preserved. `entity_type` is an ordinary `WHERE` predicate.

**Identity branch.** `natural_key` is the one field on the row the merge **cannot** erode — it *is* the merge key: canonical, normalised, stable by construction, and biased over-specific. It is the antidote to the telephone game, and it covers exactly where dense retrieval is weakest: a proper noun thinly represented in a paragraph-length summary.

Matched with `pg_trgm`'s **`word_similarity` (`<<%`)**, not plain `similarity` — the incoming query is a sentence, not a key, so plain trigram similarity over the union of both strings reads low, while `word_similarity` scores the best-matching *span*. GIN trigram index; lossy-with-recheck, so results stay exact.

**The key branch decides membership; the vector decides the score.** A key hit is **force-included and cannot be cut by `limit`**, but its score is still its cosine similarity. So there is one comparable number per result, and **no fusion weight exists anywhere** — a key hit is a fact about identity, not a score to blend.

**Hybrid FTS over the summary with RRF or weighted fusion was rejected.** It needs tuning and there is nothing to tune against: single user, no relevance judgements, no query log at the time of the decision. Picking fusion weights by vibe and never learning whether they were right is worse than not having the signal.

*Source: #16 §1–2.*

### 6.2 No ANN index on either layer

**HNSW is approximate: you pay recall to buy latency. For a memory-keeper, recall *is* the product** — "I know I wrote this down and it won't come back" is the cardinal failure. Honest magnitudes: HNSW at defaults gives 95–99% recall@10, so exact search recovers roughly "occasionally one result differs", against sub-ms → ~10–20 ms. Both imperceptible inside an LLM turn.

**The larger prizes are not the recall points:**

- **The `entity_type` filter stops being a problem.** A filtered ANN query is the classic under-return bug; pgvector's iterative scans exist to paper over it and bring their own knobs. With exact search a predicate is just a predicate — **`limit: 10` cannot quietly return 4**.
- **Determinism.** When a query misses something the cause is reasonable-about: the summary dropped it, or the embedding did not separate the concepts. Never "the graph traversal didn't visit that node." Given no relevance data, removing an unexplainable variable is worth more than 1–5%.
- **No knobs** (`m`, `ef_construction`, `ef_search`, iterative-scan settings) set blind.

**IVFFlat rejected outright:** it needs representative data at build time and degrades as the corpus grows past its training — wrong for a store that only accretes.

**Affordable because of the numbers.** A 1024-dim vector is ~4 KB, so at ~7k raw rows a year the working set lives in `shared_buffers` and an exact scan is pure CPU. Note the coherence: the primary surface is the *smaller* table, so the compression that justifies the tiering also makes the cheap index choice safer.

**The trade is not static, which is why the tripwire is load-bearing.** Exact scan grows linearly, HNSW logarithmically. **Revisit at ~30–50k rows or measured `search_entities` p95, whichever comes first** — one migration file, no data migration. The tripwire is now *fireable* — `percentile_cont(0.95)` over `query_log.duration_ms` — and its starting threshold is **p95 > 150 ms over a trailing 7 days, minimum 50 logged queries**, a chosen value rather than a measured one (§13.4). The window and the minimum sample matter more than the number: without them a cold-cache outlier or a quiet week fires it. Raw rows grow faster than entities, so raw is what hits the wall first.

*A forward-compatibility constraint on any future index choice:* chunked raw embedding is on the roadmap, and its shape — one Raw Entry plus a child table of `(entry_id, ordinal, span, embedding)` — multiplies raw vector rows ~5× and makes raw search a *group-by-entry* query rather than a flat top-k.

*Source: #16 §4, #18, #23 §10.*

### 6.3 What "primary" actually buys, stated rather than assumed

**Compression, not a better retrieval method.** The mechanism is nearly identical to `search_raw`, so the tiering is justified by compression alone. The win is real and sufficient: one Person Entity carrying twelve accreted mentions returns as **one** result instead of twelve competing for the `limit` — exactly the recall dilution that append-only extractions were rejected to avoid. It is **not** a claim that entity search retrieves *better*.

**What is being indexed is an Nth-generation gloss, and that is a deliberate trade.** The merge sees only the prior gloss plus one entry — recursive lossy compression — so a distinctive phrase from entry 1 survives only if every subsequent rewrite kept it. Fidelity is inversely proportional to merge depth, which puts the loss where it hurts least (§3.4).

**Considered and rejected — index raw's vectors and join through `source_entry_ids`.** Genuinely attractive: zero new vectors, no re-embed on merge, no embedding step after the extraction phase, and it makes the compression claim literally true in the mechanism. Rejected because raw entries are noisy and multi-topic — one long entry may yield several *unrelated* Entities — so a vector over "Tuesday's meeting" is muddied by everything else in it, where a summary about one person is purely about that person. And nothing synthesised across entries would be findable.

*Source: #16 §1; unchecked, see §13.*

### 6.4 Embedding model and call configuration

**`bge-m3`, `vector(1024)`** — retained against six alternatives with everything measured on this machine. Three obligations on **every** `/api/embed` call:

| Setting | Why |
|---|---|
| **`truncate: false`** | The default silently truncates: a 135,000-character input returned a valid 1024-dim vector with `prompt_eval_count: 2048` — an embedding of the opening ~8% of the text, indistinguishable from a real one. **The single highest-value line in the whole configuration.** |
| **`options.num_batch: 8192`** | Ollama's embed path is gated by `min(num_ctx, GGUF context_length, num_batch)`, and the **default 2048 batch is what binds** — because a non-causal encoder must hold the whole sequence in one batch. `num_ctx` can only *lower* the ceiling, never raise it, which makes the global `OLLAMA_CONTEXT_LENGTH` inert here. **Without this the usable window is 2048, not 8192.** Costs 276 MB resident VRAM. Verified to produce *correct* vectors, not merely accepted ones: a distinctive fact buried past the 2048 default in a 6,689-token document lifted query cosine by +0.0202 against a truncated control. |
| **Prepend nothing** — on queries and documents alike | `bge-m3`'s card states it "no longer requires adding instructions", and adding a generic instruction costs it **5.95 nDCG@10**. This is an **explicit rule, not an omission** — otherwise a later well-meaning `"Represent this summary for retrieval:"` silently pays that cost with no signal, and there is no telemetry to notice. |

**The `num_batch` behaviour is undocumented and sits beside a `TODO` in Ollama's source.** Re-run the ceiling probe after any Ollama upgrade — the failure mode is a `400` on entries that used to capture fine.

**Why `bge-m3` and not the alternatives:**

| Candidate | Verdict |
|---|---|
| **`bge-m3`** (560M, 1024d, MIT, 8192 with `num_batch`, 940 MB, prefix-free) | **Retained.** The best model that can serve *both* layers. |
| `embeddinggemma:300m` (307M, 768d, 2048 **hard-capped**) | **Measurably better on entity-shaped retrieval** — +0.069 nDCG@10 (hard set), +0.010 (easy), both CIs excluding zero, the only result replicating across two query sets with opposing biases. **Cannot serve the raw layer at all.** Deferred, not dismissed (§6.5). |
| `qwen3-embedding:0.6b` | **Eliminated on quality** at matched fp16 — below the incumbent on both sets. Its earlier apparent lead was a 40-document pool plus an 8-bit-vs-fp16 mismatch. |
| `nomic-embed-text` (the original pick) | **Disqualified twice**: its Ollama GGUF declares **2048**, not 8192, and no option raises it; plus mandatory two-sided prefixes (`search_query: ` / `search_document: `) that Ollama never applies. |
| `snowflake-arctic-embed2` | Viable, strictly dominated — identical dimension, footprint and window, plus a prefix obligation for a lateral move. |
| `granite-embedding:278m` | 512 tokens. The 8192-context `granite-embedding-english-r2` is **not in the Ollama library** — the strongest near-miss, worth re-checking. |

**The prefix finding, corrected within its own research:** *generic* task instructions are volatile, swinging −10.85 to +6.57 nDCG@10 with model-dependent sign — corroborated independently by MTEB maintainers, who moved two models by +9.5 and +12.4 by changing only instruction text. But **a model's own native prefix is worth only ~+0.024**, CI spanning zero, and **smaller than the spread between models (0.172)**. So model choice is the larger lever on Tome-shaped data. What survives is the *asymmetry of risk*: a required prefix Ollama will never apply is the highest-risk item in the decision, because the mistake is permanently silent. For `bge-m3` the instruction lever points **down**, so prefix-freedom here is insurance rather than performance.

*Source: #22, #16 §5.*

### 6.5 One embedder per layer — deferred, not dismissed

`embeddinggemma:300m` for entity summaries (inherently short) plus `bge-m3` for raw is coherent, and **not a VRAM problem** — measured ~11.6 GB of 16 with `qwen3:14b` at 16k, both embedders pinnable.

Deferred on four grounds: it **permanently doubles the re-embed design** (two `embedding_model` semantics, the entity side re-triggered by every merge); two pinned models serialise on `NUM_PARALLEL=1`; it **forecloses cross-layer vector comparison permanently** (768d vs 1024d); and the gain is **re-capturable later at identical cost**.

**That last point was itself corrected, and the correction strengthens the deferral.** Swapping the entity embedder does **not** cost a full entity re-derive: the summary *text* is unchanged, so only its vector is invalid — a **re-embed, minutes rather than fifty hours**. So picking it up later is even cheaper than assumed. The architectural objection is unaffected and remains the real reason to defer.

**Most likely trigger to reopen:** if raw embedding ever moves to the roadmapped chunked scheme, chunks would sit well under 2048 and the context objection disappears entirely — making `embeddinggemma` a *single*-model candidate on the merits. **A path to evidence also now exists**, from 90 days after deploy (§8.5).

*Source: #22 §5, #17.*

### 6.6 Nothing is prioritised — stated once

Recorded here because it was implicit across three tickets. **Ollama has no priority, pinning or reservation concept**; eviction is plain LRU and `keep_alive` is only a per-model idle timer. So contention is **removed** rather than arbitrated, by keeping both models permanently resident (§7.7).

The resulting policy:

- **`qwen3:14b` gets the GPU.** Enrichment is never interrupted.
- **Capture gets correctness by degrading rather than waiting** — a 5 s inline budget, and on timeout the row commits with `embedding NULL` and the tool returns success, those timeouts not counting toward `attempt_count`.
- **Enrichment throughput quietly pays.** A mid-run capture stays `pending` for the next tick.

*Source: #16 §7, #15 §5.*

---

## 7. Deployment & operations

### 7.1 Implementation stack

**Python 3.13+ on uv**, with a **uv-managed interpreter pinned in the repo** rather than Fedora's system Python, so an OS upgrade cannot break the venv. This is not a capability argument — both official MCP SDKs implement Streamable HTTP properly — it is that the entire dependency chain already exists on this box, and TypeScript would mean adding a runtime for no offsetting gain.

**One repo, one installed `tome` package, three console scripts:** `tome-mcp`, `tome-enrich`, `tome-migrate`.

**Two codebases was rejected** because the two processes share a single state machine: `resolve_entry` / `review_schema` / `get_enrichment_status --include_items` live on the **MCP server**, writing raw entry state and reading `enrichment_events` — so the server writes rows in the state machine the runner owns. And the Tombstone predicate (`AND text IS NOT NULL` on every work query, *including* full mode's reset) is **one invariant that must hold in both processes**; written down twice it eventually drifts, and re-derivability cannot survive that drift.

So `tome.db` (schema + queries, holding the Tombstone predicate exactly once) and `tome.llm` (Ollama) are shared, with `tome.mcp` and `tome.enrich` as thin edges. **Both edges are async** so there is one query layer rather than a sync copy and an async copy — forced on the server by ASGI, and free for the runner, whose loop reads identically either way.

**psycopg3 with hand-written SQL. No ORM.** Every query already committed is one an ORM either does not help with or actively worsens: the `ON CONFLICT (entity_type, natural_key)` merge, `pg_try_advisory_lock`, the per-entry transaction, the `prior_decisions` join, the windowed aggregates, the `width_bucket` histogram, the full-mode wipe, and the vector operators. The schema is a handful of tables and the entity tables are disposable by design. Verified: pgvector's psycopg3 adapter registers against a plain connection and accepts ordinary Python lists — **no numpy dependency**.

Cost accepted: there are no declarative models to double as this document's schema section. `schema.sql` plus the migration files serve that role.

**Dependency set:** `mcp`, `psycopg[binary,pool]`, `pgvector`, `ollama`, `pydantic-settings`, with `uvicorn` and `starlette` arriving via `mcp`. Dev: `pytest`, `pytest-asyncio`, `ruff`. Pinned by `uv.lock`, deployed with `--frozen` — which also satisfies the standing advice to pin the SDK and the spec revision built against.

*Source: #20.*

### 7.2 Migrations

**Plain numbered SQL files (`migrations/NNN_*.sql`) plus a ~40-line runner**, each applied in its own transaction against a `schema_migrations(version, applied_at)` table.

**Alembic rejected on measurement:** `alembic init` generates ~255 lines of scaffolding, and its dependency tree pulls **SQLAlchemy in full** plus greenlet, mako and markupsafe — purely to obtain an ordered-script runner, immediately after the ORM was rejected. Its remaining advantage, downgrades, is weak here: the raw layer's recovery path is a **restore**, not a reverse migration, and the derived layer has nothing to reverse because full mode re-derives it.

**`tome-migrate` takes a `pg_dump` before applying anything.** Migrations being rare and small argues *for* this: the cost is seconds, and it converts "did a bad `ALTER TABLE` eat my raw layer?" from a question into a restore. **This is the only scenario anywhere in the deploy path that can actually destroy data.** Retention for these dumps is in §8.2.

**Migrations never run on the boot path** — both units restart on boot, and two units racing a schema change is a bad place to discover a bad migration. They run only inside an explicitly invoked deploy.

**The asymmetry that governs them** (§3.1): an entity-side schema change **never needs a data migration** — it is DDL plus "reset all raw to pending", and the next run backfills by re-deriving. Only raw-side changes need careful migration.

*Source: #20, #19.*

### 7.3 Unit inventory — seven units

All **system** units under a dedicated `tome` system user, which needs **no `render`/`video` group membership** because Tome reaches the GPU only through Ollama's HTTP API.

| Unit | Type | Ownership |
|---|---|---|
| `postgresql.service` | distro, plus a Tome drop-in for `LogNamespace=` | Fedora |
| `ollama.service` | `simple`, pre-existing | Tome, via a drop-in |
| `tome-mcp.service` | long-lived, `Restart=on-failure` | Tome |
| `tome-enrich.service` | `oneshot` | Tome |
| `tome-enrich.timer` | monotonic, ~15 min | Tome |
| `tome-backup.service` | `oneshot` | Tome |
| `tome-backup.timer` | daily | Tome |

**System, not user units — on a hard constraint, not a preference.** A systemd *user* manager **cannot express ordering against system units**: `After=postgresql.service` is simply unavailable to a user unit. Since the MCP server must not accept connections before Postgres is up, and Postgres is Fedora's system unit, user units cannot state the one dependency that matters. Secondarily, `/var/lib/systemd/linger/` is empty, so user units would stay down on exactly the boot-back-from-Windows case that motivated the uptime work.

Accepted cost: editing units and reading `journalctl` needs `sudo`, and a system unit has no clean route to the desktop notification bus (§10).

**Ordering and binding:**
- `tome-enrich`: **hard** on Postgres and Ollama both — it exists to run models against the database.
- `tome-mcp`: **hard** on Postgres, **soft on Ollama.** A capture *degrades* rather than fails when Ollama is unavailable (§4.5); a hard dependency would discard that design and make a broken Ollama block capture, which is the one thing that design protected. Accepted cost: "search degraded, capture fine" is reachable without noticing, which is what `warnings` exists to announce.
- **No dependency on `tailscaled` at all** — §7.4.
- `tome-backup`: **no ordering against `tome-enrich`** is required — `pg_dump` runs in an MVCC snapshot and takes no conflicting lock.

*Source: #15 §2–3, #19, #26.*

### 7.4 Networking: bind broadly, filter in the kernel

**Decision: bind `0.0.0.0`, restrict by source address in the unit.**

```ini
[Service]
IPAddressDeny=any
IPAddressAllow=100.64.0.0/10 fd7a:115c:a1e0::/48 localhost
```

**Why a tailnet-only bind is load-bearing rather than defence-in-depth:** `FedoraWorkstation` opens **every port from 1025–65535 inbound on `eno1`**, and `tailscale0` is in no zone. A `0.0.0.0` bind is therefore reachable from the physical LAN, unfirewalled.

**But binding the tailnet address directly races, and `After=tailscaled.service` does not fix it.** `tailscaled.service` is `Type=notify`, so systemd considers it started when the daemon signals ready — which precedes authenticating and precedes `tailscale0` acquiring its address. Ordering against it still fails with `EADDRNOTAVAIL`. `FreeBind=` exists only on **socket** units, so using it would mean socket activation.

What the chosen shape buys:

- **The startup race disappears** rather than being timed — `0.0.0.0` is always bindable, so no `ExecStartPre=` wait loop and **no ordering on `tailscaled`**.
- **A tailnet flap needs no restart.** The listening socket is unaffected when `tailscale0` drops and returns. Nothing happens.
- **It filters both directions**, so these two lines make *no external egress* a **kernel-enforced property of the unit** rather than a claim about application behaviour. `localhost` covers Postgres on 5432 and Ollama on 11434.
- **It composes with the `Host` allowlist rather than replacing it**: this restricts *who may connect*; `Host` checking covers DNS rebinding.

**Accepted caveats:** `100.64.0.0/10` is the shared CGNAT range, so this is a source-address filter rather than a true interface filter — a LAN numbered inside 100.64/10 would pass. And the port remains *bound* broadly, so `ss -ltn` shows it listening on all interfaces even though policy blocks non-tailnet sources.

**`tailscale serve` was considered and rejected** (it also eliminates both the race and the LAN exposure) because it moves configuration out of unit files into tailscaled's prefs, and the proxy rewrites headers in ways that would need verifying against the `Host` allowlist first. **Restricting the firewalld zone was rejected** as a machine-wide change with side effects on unrelated work.

*Source: #15 §4.*

### 7.5 The HTTP edge

**FastMCP for the tool definitions** (its decorators generate the schemas from type hints) but **a custom Starlette app for the HTTP edge**, which is what makes the client obligations fall out of the framework instead of being hand-enforced:

| Requirement | How it is met |
|---|---|
| **`GET /mcp` → 405** | `Route("/mcp", methods=["POST"])` gives it from the router, with an `Allow` header, for free. FastMCP's own `streamable_http_app()` registers the route with **no method restriction**, so GET would otherwise open an SSE stream. |
| **Unknown paths → immediate 404** | Starlette's default. |
| **`Host` allowlist; absent `Origin` allowed, present-but-unallowlisted rejected** | `TransportSecuritySettings` already implements exactly this. |
| **The `*.tailc0e3c3.ts.net` suffix pattern** | Needs a **~20-line subclass** — the SDK's wildcards are **port-only** (`host:*`). |
| **A legible 403 naming the mismatch** | Same subclass — the SDK returns **421**. |
| No SSE streams remain | `json_response=True`. |

**Sessions are stateful — forced, not chosen, and the forcing is only as durable as the version pin.** `_client_params` is per-`ServerSession` instance state, set only when `initialize` arrives on that session. Stateless mode builds a fresh transport and session *per request*, so a `tools/call` would arrive with `client_params is None`, **breaking `source`**. There would be no retained handshake to read. **Verified in the shipped source and by running it** at `mcp` v1.28.1 (`777b8d06`, 2026-06-26): stateless → `client_params is None`; stateful → the handshake's `clientInfo` is there to read (#34).

**The premise is `mcp>=1.28,<2` (§8.8), and outside that pin this paragraph is wrong.** On `mcp` 2.x's modern protocol era, `client_params is None` is a *served* outcome that **no server-side setting can prevent** — `Connection.from_envelope` builds a fresh connection per request over stdio, the request succeeds, and there is no `stateless` flag to decline. The client's first frame chooses the era; the server does not. So "never stateless" is a real and sufficient obligation **on the pinned line** and would become an empty one off it. That is the pin's load-bearing job, not merely dependency hygiene. (#34)

Two side effects, and they are **downstream of `source` rather than independent of it** — if `source` were ever dropped, both would have to be re-argued on their own terms rather than inherited (#34):

- The SDK's reported memory leak was **stateless-mode only**, so this avoids it by construction rather than by trusting a fix. But the *reason* stateless is off the table is `source`; delete the column and stateless becomes the simpler choice for the HTTP entry point, at which point the leak is a live consideration again rather than a closed one.
- The session identity that makes the fallback judgement signal possible (§3.8) exists only because sessions are stateful. **Its grain is not uniform across entry points** — see §3.8, which now states the three grains and bounds the predicate in time because of the coarsest of them.

**No server-initiated SSE, ever.** The spec makes the server-initiated stream a MAY, and `warnings` already resolved the only thing that would have needed it. Building the stream would mean per-client connection state plus event-ID replay for resumability, with no traffic on it. **The door this closes:** the server can never *volunteer* anything without a retrofit.

**Never hang.** A 405 on GET sends `mcp-remote` down its longer discovery path (three `.well-known` probes rather than one) at each Desktop launch; on the tailnet a prompt 404 costs microseconds, but its 5–10 s per-probe timeout ceiling only bites against a server that hangs.

*Source: #13, #20, #9.*

### 7.6 Deployment: `/opt/tome` and one `make deploy`

**`/opt/tome`, with `/opt/tome/.venv` built by `uv sync --frozen`**, root-owned and merely *readable* by the `tome` user.

**Running the units out of the dev checkout is structurally impossible, not merely unwise.** Measured: SELinux is **Enforcing**, and `/home/mark` is `drwx------` labelled `user_home_dir_t`, so the `tome` user cannot even traverse it. Loosening the mode would not fix it, because executing service code out of a home-labelled directory is precisely the pattern policy denies. `/opt` is labelled `usr_t`, the correct home for read-only service code. `uv` is `/usr/bin/uv`, a system RPM, so the units need no PATH handling.

**One `make deploy`, in this order:**

```
stop tome-enrich.timer
  → copy code to /opt/tome
  → uv sync --frozen
  → restorecon -R /opt/tome
  → tome-migrate      (which pg_dumps first, and replays the retraction ledger)
  → restart tome-mcp and tome-enrich
  → start tome-enrich.timer
```

**`restorecon` is not optional:** files copied out of a home directory **carry home labels with them**. This is the classic Fedora footgun and it belongs in the spec, not in a debugging session eight months from now.

**The timer is stopped first** because the runner is an actor even when the operator is not: a run can be in flight on the 15-minute timer during a deploy, with nobody having triggered it. The per-entry transaction would self-heal it, but stopping the timer removes the case rather than relying on recovery.

**No data-loss window**, for three independent reasons: a failed `capture_entry` rolls back whole and the text still exists in the calling conversation, so it is *un-captured and visibly retryable*, not lost; a killed run leaves finished entries `enriched` and the in-flight one `pending` for the next tick (a deploy is a scheduled crash); and the pre-migration dump covers the only genuinely destructive case. Migrate-then-restart does leave a few seconds where old code meets new schema — additive changes do not notice, a destructive one would briefly error, and that is accepted rather than building a two-phase deploy for a single-user system whose operator is watching the deploy run.

*Source: #20.*

### 7.7 Ollama configuration and model residency

**Both models are co-resident. There is no swap** — `OLLAMA_MAX_LOADED_MODELS` resolves to auto = 3 × GPU count, which supersedes the original sequential-hot-swap conclusion and is what the pinning below depends on.

**Measured VRAM at `num_ctx: 16384` with both models resident: 13.12 GB of 15.98 GiB (76.4%), 100% GPU, no spill.** This depends on the `q8_0` KV cache; an f16 cache would not fit as comfortably. `qwen3:14b` is **10 GB** at 16k, not the 9.3 GB download figure.

| Setting | Value | Why |
|---|---|---|
| **Pin the embedding model** | pre-warm `bge-m3` at MCP server start with `keep_alive=-1` | So it is **never** the model that has to be loaded — see the failure mode below. |
| **Shorten the global keep-alive** | from 24 h, in a Tome-owned drop-in | Chosen with explicit unload over global-long, for crash behaviour: a run that dies before unloading pins ~10 GiB for minutes, not a day. |
| **Unload `qwen3:14b` at the end of every run** | explicitly | Same. |
| **`OLLAMA_GPU_OVERHEAD`** | raise to ~1.5 GiB from `0` | At `0`, Ollama sizes models as though all 15.98 GiB were free when ~1.16 GiB is not. **This, not cgroup limits, is the real guardrail** — VRAM is not cgroup-controllable at all. |
| **Drop the global `OLLAMA_CONTEXT_LENGTH`** | in favour of a **per-request `num_ctx` ceiling ~16k** | The global override was 8× Ollama's own VRAM-derived choice for this card; ~55k would fit, and the headroom is left unspent. Inert on the embed path anyway (§6.4). |
| **`OLLAMA_NUM_PARALLEL`** | stays **1** | At 4, KV alone would be ~10.9 GiB and nothing fits. |
| **Bind loopback only** | **`OLLAMA_HOST=127.0.0.1:11434`**, moved into the Tome drop-in | Already the bind on this machine — but only via a **non-Tome** drop-in this document did not own. See *The bind is pinned* below. |

**Address policy: `ollama.service` is deliberately left unsealed.** Unlike the Tome units (§7.4) it carries no `IPAddressDeny=` — measured, both properties empty — so the daemon has standing outbound access. A seal (`IPAddressDeny=any`, `IPAddressAllow=localhost`) was measured on the live box and **declined**:

- **It works, and costs nothing in steady state.** `systemctl set-property --runtime` applies the filter to the *running* daemon with **no restart** — `MainPID` unchanged across both flips — so the pinned embedder and a resident `qwen3:14b` survive it. `localhost` expands to `127.0.0.0/8 ::1/128`, which keeps the MCP server and the enrichment runner on 11434, and DNS survives via the `127.0.0.53` stub because `systemd-resolved` makes the upstream query in its own unit. `--runtime` also means a forgotten reseal self-heals at the next boot.
- **But it breaks pulls opaquely.** `IPAddressDeny=` is a cgroup BPF filter that **drops packets** rather than refusing the syscall, so a sealed pull never sees `EPERM` — it stalls indefinitely at `pulling manifest` with no diagnostic naming the seal. A `make pull` wrapper (unseal → pull → reseal, the reseal in a `trap`) would reduce the ordinary case to a spelling change, but habit still reaches for bare `ollama pull`, and the failure it produces is a hang.
- **The threat is real as a capability, unobserved as a behaviour.** The binary carries client code for Ollama's *cloud* services — `api/web_search`, `api/experimental/model-recommendations`, `v1/models`, `connect`, `settings/keys` — and `web_search` POSTs query text to ollama.com. This daemon receives every raw entry text; its upgrade path is an unreviewable `curl | sh` (§1.4); and §7.12's tripwire greps journald, so it cannot see a socket. Against that: nothing here is observed to fire unbidden, and the journal shows no update-check chatter.

**Declined on proportion, not on the argument.** The exposure is a capability rather than an observed behaviour, and the seal spends a new and *silent* failure mode on a rare hand-driven act. **Named as the thing to revisit** if Ollama ships a feature that egresses by default, or makes cloud routing implicit rather than opt-in — revisiting is cheap, since the seal is two lines and needs no restart. What it costs meanwhile is stated plainly in §1.3 rather than papered over.

**The bind, however, is pinned** — a *different* exposure, inbound, and separately decided. `OLLAMA_HOST=127.0.0.1:11434` moves into the Tome drop-in. It is already the bind here, but only through the pre-existing `90-pi-local-rocm.conf`, which this document neither owned nor mentioned. A rebuild from this PRD, or a lost drop-in, leaves Ollama on `0.0.0.0:11434` — and §1.4's measured firewalld fact (**1025–65535 open inbound on `eno1`**, `tailscale0` in no zone) makes that reachable from the physical LAN, unauthenticated, with no `Host` allowlist and no auth of Ollama's own. That is exactly the exposure §7.4 calls load-bearing rather than defence-in-depth. One line, no ritual, no new failure mode — so unlike the seal it is not a trade.

**The failure mode pinning makes unreachable.** Ollama evicts only models that have gone **idle**, with no priority or reservation concept. So if the embedder is *not* resident when a capture arrives mid-run: the request cannot evict a busy `qwen3`, it queues, it blows the 5 s budget into the deferred path, and then **once `qwen3` idles it is evicted to make room for a 275 MB model**, forcing a 10 GiB reload on the run's next entry. A trickle of saves thrashes the run. Pinning the small model removes the branch entirely.

**No CPU, memory or IO limits** — the knobs are not connected to the contended resource. The enrichment runner is a thin client that hands prompts to Ollama and waits, so limits on it would throttle a process that is mostly idle; limits on `ollama.service` would also throttle the interactive capture-embedding path; and VRAM has no cgroup control. **No idle-gating** either — the machine is assumed not in use during enrichment, and the settings above stand independently of that.

**The iGPU is ruled out on hard data.** Capacity-wise the reasoning was sound (`mem_info_gtt_total` is ~30 GiB on *both* cards). It inverts on compute: **2 CUs against 80**, no rocblas for `gfx1036` (Vulkan only), DDR5 at ~96 GB/s against GDDR6 at ~512 GB/s. Decisively, **a larger context makes prefill dominant and prefill is compute-bound**, so the iGPU is at its worst precisely at the operation the extra capacity was for — order-of-magnitude ~20 s versus ~9 minutes for a 10k-token prompt, per entry. Against a 15-minute tick that is one or two entries per run: not "slow but fine in the background" but "cannot drain a backlog." Also mechanical: Ollama has **no per-model device selection** — visible devices are per *server process* — so splitting the models across both GPUs would require two Ollama services on two ports.

*Source: #15 §5–6, #22, #24, #28.*

### 7.8 Configuration

**`/etc/tome/tome.env`, via `EnvironmentFile=`.** Contents:

- the `Host` allowlist — the literal short name, the tailnet IPv4 and IPv6, `localhost`/`127.0.0.1`, and a **suffix pattern** (`*.tailc0e3c3.ts.net`) so a *device* rename cannot break every client
- the **global confidence threshold** (starting value **0.7**, §13.4)
- model names
- the per-request `num_ctx` ceiling
- the database URL
- the log level
- **`TOME_MAX_ENTRY_TOKENS`** — the measured effective embedding context, ~2048

**In code, not `tome.env`** — the extraction prompt and the entity-type definitions (§4.9), `context`'s 1,000-char cap, and the 500-token context allowance. The dividing line: `tome.env` holds things *measured against something that can move under you*; code holds design constants, which belong where they are reviewed alongside what they feed.

**Deriving the allowlist at startup from `tailscale status` was rejected**: it never drifts, but the server then cannot start until `tailscaled` is not merely running but *authenticated*, reinstating exactly the startup dependency §7.4 was designed to remove — a boot with the network down would leave Tome entirely down. The drift risk is rare and manual; the startup dependency would bite on every slow-network boot. And a 403 that names the mismatch makes the failure self-diagnosing.

**The epoch fingerprint reads specific named keys from this file, never a hash of it** — otherwise adding a host to the allowlist or changing backup retention would register as a rule change.

`tome.env` holds *decisions*, not defaults, which is why it is a member of the backup set (§8.2).

*Source: #15 §7, #17, #19, #25 §8.*

### 7.9 Storage placement and clock

| Path | Contents |
|---|---|
| `/var/lib/pgsql/data` | Postgres data (Fedora default). **`chattr +C` before `initdb`.** |
| `/var/lib/tome/` | Tome state |
| `/var/lib/tome/dumps/` | pre-wipe and pre-migrate dumps |
| `/var/lib/tome/backups/` | daily dumps, ledger, `tome.env` copy — **`0700`, owned by `tome`** |
| `/opt/tome/` | code + venv, root-owned |

**Clock.** NTP stays as a named exception (§1.3). **Fix the RTC properly rather than relying on sync to paper over it:** `RTC in local TZ: yes` is currently set, the direction systemd documents as not recommended and as mishandling DST. Correct it on the **Windows** side — `HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation\RealTimeIsUniversal` (DWORD) `= 1` — then `timedatectl set-local-rtc 0` on Fedora. The clock is then right *before* the network comes up, and NTP becomes a correction rather than a crutch.

**The server obligation this creates:** `captured_at` is caller-supplied, so the clock that matters is whichever machine runs the client — capture from the MacBook and it is the MacBook's clock. Since raw is immutable and episodic natural keys are date-scoped, a wrong clock writes a permanently wrong date that every full re-run faithfully reproduces. **So the server compares the incoming `captured_at` against its own clock and flags a wild disagreement** rather than silently accepting it. It must also **tolerate a future-dated `last_successful_run_at`**, which a backwards correction after boot can produce.

*Source: #15 §9–10, #19, #20.*

### 7.10 Observability

**journald only** for v1, with `SyslogIdentifier=` per unit. **stdlib `logging` to stdout**, captured by journald automatically, no timestamp in the format (journald adds one). No `structlog`, and no journal binding — `python3-systemd` is RPM-installed but **invisible from a uv venv**, and it is not needed, because per-entry queryability lives in `enrichment_events` and journald only has to carry the operational narrative.

**Invariant C — the privacy invariant, and it is the primary lever:**

> **No text derived from a Raw Entry, and no Natural Key, ever reaches a log line — only ids, entity types, counts, durations, confidences, reason codes and model tags.**
>
> **Carve-out (exception path):** never log `str(e)` verbatim for a database or HTTP error. Log the exception class plus a curated message, and never psycopg's `diag.message_detail`.

`entity_type` stays in the clear because `Person`/`Project`/`Decision` is *schema*, not content.

**The carve-out closes a real, specific hole, not a hypothetical one.** The merge is `ON CONFLICT` on a unique `(entity_type, natural_key)` index, and a violation on that index makes Postgres emit:

```
DETAIL:  Key (entity_type, natural_key)=(person, alex-chen) already exists.
```

A developer who wrote no key at all lands a real name in the journal, in a line **fully compliant with the invariant's first sentence.** Ollama's error path has the same shape. So the rule is **C on the ordinary path and the stricter class-only on the exception path** — strictness placed exactly where the string is not ours to control.

Banning Natural Keys *alone* was rejected as too narrow (it leaves query text, which is memory content). Banning free text *everywhere* was rejected as too strict — it costs the difference between "connection reset", "too many connections" and "SSL handshake failed" at 3 a.m., which is the whole reason to want logs.

**Identifiers that replace the key: `raw_entry_id` + `entity_type` + `entity_id`.**

```
INFO  tome.enrich: entry 331 → merged into person entity 4821 (conf 0.91)
WARN  tome.enrich: entry 412 type_ambiguous: decision|preference (0.52) → suggestion logged
ERROR tome.mcp:    search_raw failed after 1204ms: OperationalError: connection reset
```

`raw_entry_id` is the load-bearing one: it joins into `enrichment_events` and `get_history`, so a line resolves to the full story on demand — **and retraction deletes the row, so the id in an old line dangles.** That is not retraction *reach*, but it is the useful half of it, free. Entity-id decay at a full-mode wipe — the reason `query_log` refuses to key on ids — **inverts here into a feature**: the pointer stops resolving.

**A hash or key-prefix is rejected outright.** Coarse Person/Project keys are real names — perhaps 20 bits against a wordlist, far less for a known colleague. A hash brute-forced in seconds is worse than plaintext, because it *looks* like protection.

Accepted cost: `journalctl --namespace=tome -u tome-enrich` during a live debug shows `entry 331 → person entity 4821` and needs a second query to say *who*.

**Enforcement is the rule plus two functions:**
- **`log_exception(logger, exc)`** — the carve-out implemented once. Emits `type(exc).__name__` plus a curated message; never `str(exc)`, never `diag.message_detail`. One function to review instead of every `except` block.
- **`configure_logging()`** — pins all non-`tome` loggers to `WARNING`, with a one-time audit at build. **This is the non-obvious one:** Tome's code is not the only thing writing to that stdout. A pinned FastMCP version that logs incoming tool-call arguments at `DEBUG` would put `capture_entry`'s full text in the journal **without a line of Tome code being involved.** Starlette's access log is safe by inspection (the payload is in the `POST /mcp` body, not the URL); FastMCP's needs checking against the pinned version.

A typed `log_event()` helper was dropped as more ceremony than a single-user system earns. **A regex scrubber on the handler is rejected on substance, not cost:** it can only match the *structured* leaks — `person:alex-chen`, Postgres's `Key (…)=(…)` wrapper — which are precisely the ones the rule and the carve-out already catch. It cannot match what actually worries us, because a Raw Entry's text and a bare coarse key are ordinary English tokens with no signature. It buys nothing real and costs the false confidence that something is watching.

Target shape of a run, and of an idle tick showing the lock-check-then-work-check before any model loads:

```
tome-enrich[12871]: run 41 starting (incremental)
tome-enrich[12871]: 7 entries pending, 2 missing embeddings
tome-enrich[12871]: phase 1: embedded 2 entries (bge-m3, 0.8s)
tome-enrich[12871]: phase 2: loading qwen3:14b
tome-enrich[12871]: entry 4711 → 3 entities (person, commitment, event)
tome-enrich[12871]: entry 4712 → 1 entity (decision), merged into existing
tome-enrich[12871]: entry 4713 → type suggestion (ambiguous: preference|decision, conf 0.41)
tome-enrich[12871]: entry 4714 transient failure (ollama timeout), attempt 1/3
tome-enrich[12871]: entry 4715 RESOLUTION REQUIRED (unparseable_output_exhausted)
tome-enrich[12871]: unloaded qwen3:14b
tome-enrich[12871]: run 41 done: 5 enriched, 1 retrying, 1 resolution_required, 61s
```
```
tome-enrich[12903]: run 42: nothing pending, exiting (18ms)
```

*(An earlier version of this shape carried natural keys in the entity list — `person:alex-reid`, `commitment:send-alex-report-2026-07-24`. That is superseded by invariant C; the lines above are the current form.)*

A line is also emitted whenever a run inserts a new Derivation Epoch, so journald carries the epoch history for free.

*Source: #20, #26 §1–3.*

### 7.11 The journald namespace and its retention

**`LogNamespace=tome`** on `tome-mcp`, `tome-enrich`, `tome-backup`, **and `postgresql.service`** (the last via a drop-in, which can set `LogNamespace=` like any other `[Service]` directive).

This is the fact that made the whole thing tractable: **journald retention is per-namespace, not whole-box.** A unit with `LogNamespace=tome` is served by a `systemd-journald@tome.service` instance reading `/etc/systemd/journald@tome.conf`, and each namespace carries a distinct configuration — retention included. So this was never a decision about the machine.

**Postgres is in the namespace** because it is the one remaining process that can emit a Natural Key (§7.10's `DETAIL`). Including it means the bound covers *every* process that can touch memory content, statable flatly with no asterisk about `ON CONFLICT`. **Also set `logging_collector=off`** so Postgres logs to stderr → journald → the namespace; if left on, PG writes files under the data dir instead — a *third* log store, outside journald, outside every bound here, and outside the dumps.

**Ollama stays in the default journal, on measurement.** All **160,988** of its journal lines on this box were read: token counts, `t/s`, slot lifecycle, and `[GIN] … POST "/api/generate"` access lines. **No prompts, no responses at default verbosity** — so it carries no memory content and needs no privacy bound. And an empty `journalctl -u ollama` would be a trap set for exactly the wrong moment, given that Tome merely *owns* an Ollama that predates it and that Mark drives by hand.

**`LogNamespace=` implies only `BindLogSockets=`** — *not* `PrivateTmp=`, *not* `MountAPIVFS=` — plus ordering and requirement dependencies on the `journald@tome` socket units. It does not collide with the existing hardening.

**Two bounds, of two different kinds. Conflating them is what made this look like a whole-box privacy decision.**

```
# /etc/systemd/journald@tome.conf        — PRIVACY, Tome only
MaxRetentionSec=30day
MaxFileSec=1day
SystemMaxUse=1G
```
```
# whole-box drop-in                      — CAPACITY, no privacy policy at all
SystemMaxUse=4G
# no time limit
```

The whole-box cap is justified **entirely** by Ollama's ~20k lines/day, about to worsen: ~6 `print_timing` lines per enriched entry, on a 15-minute timer, forever. **Tome will materially accelerate the decade-to-first-eviction** — in content-free noise. 93 GB of `tg = 34.05 t/s` is not a debugging asset; 4 GB is ~5 months at the current 24 MB/day.

**`MaxFileSec=1day` is load-bearing — without it the retention number is fiction.** `MaxRetentionSec=` deletes whole **files**, not entries, so at the default `MaxFileSec=1month` a month-spanning file is deleted only once its *newest* entry is 30 days old: an effective bound near **60 days**. Size-based rotation cannot rescue it, because under invariant C the namespace is too quiet to ever reach `SystemMaxFileSize`, leaving time rotation as the only thing that rotates.

**Why 30 days and not the query log's 90.** The asymmetry is the reasoning. The query log is a *curated asset* whose content is known and whose window was calibrated on the minimum sample it needs to be useful. This is the opposite: under invariant C the namespace should hold **no memory content at all**, so the bound is insurance against residue C failed to catch — a bug, an unaudited logger, an error routed unexpectedly. You cannot argue that window is harmless, because **by construction you do not know what is in it**. *The less you know about what a store holds, the shorter its retention should be.* The floor is the gap between something breaking and you noticing it, which `warnings` and triage already cover in-band, so 30 days covers a month of silence — and a two-month-old timing line has no diagnostic value.

**Accepted cost, and it goes in the runbook:** `journalctl -u tome-enrich` returns nothing. The working form is `journalctl --namespace=tome -u tome-enrich`.

*Source: #26 §4–5, #23 Finding C.*

### 7.12 The leak tripwire

**Invariant C is checked, not asserted.** Otherwise it joins the list of things this design asserts without measuring — and if `configure_logging()` misses a chatty dependency, nothing would ever notice.

```
journalctl --namespace=tome --since -1day -o cat \
  | grep -Ff <(psql -At -c "select natural_key from entities")
```

- **Process substitution, never a keys file.** Automating this otherwise means writing every name in the corpus to disk unattended, on a filesystem with **no LUKS**, with cleanup that must never fail — and in a **public repo** one `git add -A` away from publishing exactly the artifact ruled out permanently. `<(…)` never touches disk and retires the cleanup obligation entirely.
- **Counts only, never content.** A durable record saying "found `alex-chen` at 14:02" *is* the leak, made permanent, in the store just bounded. This is invariant C applied to the checker itself. Record **`keys_checked`, `keys_suppressed`, `lines_scanned`, `hits`**.
- **`lines_scanned` is why it is numbers and not a boolean** — a check that scans nothing and finds nothing looks identical to a passing check.
- **It is a tripwire, not a proof.** Coarse keys mean `project:tome` has natural key `tome`, which matches `tome-enrich`, `/opt/tome`, and half of every line. Colliding keys need a small **visible allowlist**, and `keys_suppressed` keeps the suppression visible rather than quietly growing until the check tests nothing. It also only covers keys still in the corpus: a key that leaked and was then retracted leaves a hit with nothing left to match against.
- **Cadence: daily, on the existing backup timer** (`--since -1day`) — no new unit, no third timer. **Plus once at the end of a *full* run**, a different code path that re-exercises every merge and is rare enough to cost nothing. Explicitly **not** after every incremental run: a journal scan every 15 minutes to find nothing.
- **Nonzero fires a persistent `warnings` entry** (§5.10).

**The strong argument for automating was never the dataset** — a time series of zeros is an alarm that has not gone off. It is **regression detection**: a `uv sync` pulling a FastMCP that starts logging tool arguments is a leak no manual week-one check can see, by construction.

**This gives the scoped purge a trigger, closing the loop:** leak detected → persistent warning → operator runs the purge → next day's check reads zero → warning clears.

*Source: #26 §7.*

---

## 8. Durability, retention & privacy

### 8.1 What each bound does not touch

Stated first, because in a memory-keeper every retention policy reads as though it might reach the memories.

- **Raw Entries never expire.** There is no age-based deletion of memory content anywhere in this system. A Raw Entry leaves only by a deliberate human act — `resolve_entry skip` or `retract_entry`.
- **Entities are never retained or expired** — they are re-derived.
- **`enrichment_events` is never pruned** in v1.
- The three time bounds that exist reach only: **`query_log` (90 days)**, **Tome's journald namespace (30 days)**, and **backup dumps (7 daily, 3 event-triggered)**. None of them holds a Raw Entry.

### 8.2 Backups: logical `pg_dump`, on the same filesystem

**The backup set:**

| Member | Why |
|---|---|
| `pg_dump -Fc` of the `tome` database | one sub-GB file; internally consistent against a live server via its MVCC snapshot |
| `pg_dumpall --globals-only` | cluster roles and grants, a few KB |
| **the retraction ledger** | the one file whose loss silently breaks the retraction guarantee |
| **`/etc/tome/tome.env`** | holds *decisions*, not defaults — the allowlist, the threshold, the measured capture cap |

**Deliberately excluded:** the ~9 GB of Ollama blobs (re-pullable; their pinning is structural, §8.8); `/opt/tome` and the systemd units (covered by git and `uv sync --frozen`); and **`query_log` data** (§8.5). **A restore prerequisite, not data:** the dump opens with `CREATE EXTENSION vector`, so the pgvector RPM must be installed *before* a restore is attempted.

**btrfs snapshot/`send` was rejected on coupling, not cost** — the store should not marry a Fedora-default filesystem. A dump is a file on any Unix, needs no interaction with `chattr +C`, requires no stopping of Postgres, and restores into a *newer* Postgres than it came from. **And it dissolves rather than solves the retraction incompatibility**: the ledger replays *at restore time, into the restored database*, never into the backup — where a read-only snapshot cannot be replayed into at all, and only deleting it removes the content.

**There is no raw-only backup.** The whole database is one sub-gigabyte dump, so separating raw from entities would add a decision without saving anything — and backing up derived data is independently justified, because a raw-only restore costs **~50 h of re-derivation at 10k entries** before the entity layer is whole. The durable/derived asymmetry governs *migration*, not backup.

**Destination: `nvme0n1p3` — the same btrfs filesystem as the live database.** Both alternatives were ruled out on facts: `nvme1n1` is earmarked for **Windows**, and the tailnet has **no always-on peer**, leaving only a push to an intermittently-present laptop or a plug-in-a-drive ritual. Both are backups that quietly stop working, and **a mechanism nobody can rely on is worse than a documented gap.**

> **Accepted risk, stated plainly: a dead `nvme0n1` loses the store and its backups together.** These dumps defend against *logical* loss on a healthy disk — a bad `ALTER TABLE`, a mistaken full wipe, a regretted retraction — and against nothing else.

That scoping is affordable partly because **raw cannot slow-burn**: it is append-only and immutable, and its only mutations are state, overrides, tombstones and retractions. Every logical-loss event is therefore **discrete and noticed at once**, which is why a short window suffices rather than months of history to catch a silent drift.

**Cadence and rotation:**
- **Daily. 7 retained, rotated by count.** Hourly was rejected as unearned at manual-capture rates, especially since a failed `capture_entry` fails *visibly* in the calling conversation, so a lost capture is one you would plausibly notice and retype. WAL archiving / PITR rejected on the same reasoning: real machinery for a gap of a handful of hand-typed entries.
- **Rotate *after* verifying, not before** — write the new dump, verify it, then delete the oldest, so a failed dump can never cost a good one. Peak occupancy is therefore **8**, not 7.
- **Event-triggered dumps (pre-wipe, pre-migrate): keep the last 3, by count, not age.** Count because they are event-triggered — **an age policy would garbage-collect your only pre-migration dump *precisely because* you had not migrated in a while.** The pre-wipe dump earns its keep independently: at ~50 h per full run, it is the only fast rollback from a bad full pass.
- **Below 10 GB free: skip the dump and raise a warning instead of writing it.** The failure mode this exists for is not "backups stop working" but **"Postgres stops working"** — `/var/lib/tome` shares a filesystem with root and the live database, so a runaway backup directory fills the disk, Postgres cannot write WAL, and `capture_entry` starts failing. btrfs sharpens this by returning ENOSPC on metadata while apparently having free space. **A skipped backup you are told about is strictly better than a full filesystem that takes the store down.** Count-based rotation bounds *files, not bytes*, and with no `enrichment_events` pruning every one of the 7 retained dumps grows with that table — so the bound is a **guard, not arithmetic**.

Space budget (arithmetic, not measurement): a mature dump runs ~16 KB/entry, so ~160 MB total bound at 1k entries, ~1.6 GB at 10k, ~8 GB at 50k. Comfortable against 888 GB — but estimates in this project have already been wrong by 4× in the wrong direction, which is the other reason the guard exists.

**Verification: `pg_restore -f /dev/null` after every dump.** It decompresses and processes every data block, emitting the archive as SQL and discarding it — catching mid-file corruption, a broken compression stream, any damaged block — with **no database, no `CREATE DATABASE` privilege, and no transient space.** Seconds for a 160 MB dump. `pg_restore --list` was rejected as the gate: it reads only the table of contents, catching truncation and a corrupt header and nothing else.

**A weekly restore-into-scratch was considered and withdrawn.** Once `-f /dev/null` is the gate, a real restore adds only restore-*environment* failures (pgvector missing or incompatible, roles the dump references not existing) — and that is a **static** property, not a drifting one, so re-testing it weekly carries almost no information. Genuine drift, such as a Fedora upgrade swapping pgvector for an incompatible build, breaks the **live** database the moment it happens, so it surfaces as Tome failing rather than as a backup check failing. It also wanted `CREATE DATABASE`, which the `tome` user does not have and should not get. Reinforcing this: **btrfs checksums all data by default and returns EIO rather than bad bytes**, and `chattr +C` (which disables checksums) is applied only to the Postgres data directory — so the backup directory keeps them, and a dump that reads at all is reading its original bytes.

**What is kept from that idea is the part actually at risk: the procedure, not the artifact.** The realistic failure is reaching for a runbook that was never tried and getting the order wrong. Hence §8.9.

*Source: #19, #18 §5, #20.*

### 8.3 Retraction — mechanics and the precise guarantee

**Hard purge, not a tombstone.** The row is **deleted**, and `enrichment_events` **cascades** with it. Three things get simpler rather than harder:

1. **No append-only carve-out.** Nulling a raw row does not remove its content — per-stage events carry a `gist`, merge events hold before/after summary text, and `get_history` surfaces them. A tombstone-flavoured retraction would have needed a DELETE-or-redact exception to the one table hardened DB-side. `ON DELETE CASCADE` does the work, and the invariant restates with **no "except"** (§3.5).
2. **No phantom risk.** A purged row is absent from the pending set, the un-embedded sweep, `pending_count`, `un_embedded_count` and full mode's reset **by construction**.
3. **It supersedes `skip`.** A Tombstone retains a 200-char excerpt and a token count in its event row; retracting an already-tombstoned entry purges those — so there is an escalation path when skipped content turns out to be sensitive.

**What it costs.** You lose the ability to distinguish "never captured" from "retracted" — no `get_history` answer, no count, no trace. **For `sensitive` that is the point**: a Tombstone advertises *"something existed at 15:04 and Mark removed it"*, which is metadata you may specifically not want. For `mis_capture` it makes "did I ever capture that?" unanswerable. Accepted at single-user scale as the honest reading of "retract". **Total-capture counts can now go down**; nothing depends on them today, and no growth metric should be built on one.

**The cascade: delete the affected Entities, requeue their surviving source entries, one hop.** Delete every Entity whose `source_entry_ids` contains the retracted id; reset those Entities' *other* source entries to `pending`; the next tick rebuilds from surviving raw.

**The cascade is not optional even if nothing was derived — this is structural, not statistical.** With a hard purge, an Entity still holding the purged id in `source_entry_ids` is a **dangling reference**; there is no FK to catch it if that is an array, and `get_history` resolves `related_ids`, so it would silently return an id that does not exist. **Purge without cascade doesn't remove a lie, it creates one.**

**One hop is deliberately not the correct closure.** One entry yields multiple Entities, so a requeued survivor also feeds Entities the retraction never touched, and the merge folds its content into those a **second time**. Avoiding that means deleting them too and requeueing *their* sources — a transitive closure that does not stay small, because the coarse Person and Project keys are hubs and the entry↔entity graph on a personal store is almost certainly one giant connected component. **Done correctly, one retraction re-derives the entire corpus.**

So: one hop plus **approximate idempotency**, on three grounds — the merge takes *old summary + new entry*, so re-merging an entry whose facts the summary already states is close to a no-op by construction; the re-derivability guarantee already disclaims summary wording; and the alternative is measurably expensive. **Unconditional, not reason-dependent** — a `sensitive`-only requeue would make the tool's completeness contingent on which enum value an agent picked, the least reliable input in the call.

*Per-entry contribution storage — a `(entity_id, raw_entry_id, extraction)` table letting one Entity rebuild from its surviving contributions with no re-extraction and without touching any other Entity — is noted as the genuinely correct answer. It is new schema and a revision of the merge rather than a retraction detail, so it is deferred.*

**No auto-trigger.** Requeued entries wait for the next 15-minute tick; the advisory lock makes an immediate run a coin flip, and the timer *is* the retry mechanism. **Consequence: for up to 15 minutes after a retraction, `search_entities` returns nothing for that subject, then a rebuilt Entity appears.** `entries_requeued` is what tells the caller a rebuild is pending.

**Cascade reach, complete:** the raw row, its `enrichment_events` rows, the Entities it fed, and **`query_log` rows naming a natural key the retraction removed**. That last is the *same* exception, not a second one, and it is honestly partial — it catches queries that **matched** the retracted subject, not queries about the topic that missed. It earns its place despite the 90-day bound because the motivating case is "something private", and waiting up to 90 days for the query that found it to expire is not an answer.

**The guarantee, stated precisely rather than aspirationally:**

> **Retraction removes content from the live store immediately, and from backups within 7 days.**

Replay-on-restore governs only what happens *if* you restore; it does nothing about the bytes sitting in a dump right now. Retract on Monday and every earlier dump still holds the full text until it ages out. **Purging backups on retraction was rejected** — rewriting each `-Fc` dump means restore-into-scratch, delete, re-dump per file, and a half-completed rewrite leaves a **corrupt recovery set**, a worse failure than the exposure it removes; the blunt variant (delete all backups on any retraction) makes every retraction cost the entire recovery window.

**The exposure is tolerable because on an unencrypted filesystem, retraction's threat model cannot be disk forensics** — the live database is equally exposed, so it never was. What retraction actually buys is that content stops being **reachable by an agent** through `search_raw`, stops feeding Entities, and stops surfacing in conversation. A dump file is none of those things.

**A logical delete is not an erasure**, and `sensitive` implies a promise worth writing down rather than assuming. Postgres leaves the old tuple in the heap until vacuum and the content persists in WAL — equally true of a Tombstone's `UPDATE`, which *adds* a tuple rather than removing one, so purge is no worse, but neither delivers erasure.

**Retraction owes journald nothing, and this is structural rather than declined.** Per-entry deletion in journald does not exist — `--vacuum-*` operates on whole files and skips active ones — so targeted reach is impossible. But under invariant C **there are no Natural Keys and no Raw-Entry text in the logs by construction**, and residue that escapes ages out of the namespace within 30 days. The namespace does unlock a **scoped purge that did not previously exist**:

```
journalctl --namespace=tome --rotate --vacuum-time=1s
```

`--rotate` is **required, not optional** — vacuum skips active files, and the rotate call does not return until rotation completes, so the two combine safely in one invocation. A bare `--vacuum-time=1s` would leave everything recent behind. **`retract_entry` does not fire it automatically** — that is the already-rejected blunt variant, spending 30 days of operational history to remove content invariant C says is not there. It is the right answer to a *different* question ("I have reason to think something leaked"), and §7.12 gives it that trigger.

*Source: #18, #19, #23 §5, #26 §6.*

### 8.4 The known narrowing: retracted content in neighbours' event payloads

**Accepted and documented, because it is indefinite rather than bounded by the 7-day window.**

Event payloads hold before/after entity summaries, and those summaries are built from **multiple** raw entries. Entries A and B both feed one Person Entity. A's merge event records that Entity's before/after summary, which contains B's contribution. **Retract B**: the cascade removes B's row, B's own event rows, and re-derives the Entity correctly — **but A's event row still quotes a summary containing B's content, and nothing in the cascade reaches it.** An entity summary gets re-derived and cleaned; an append-only event row never will.

Bounds on it:
- What survives is B's content **as distilled into a summary**, not verbatim — a short entry survives near-verbatim, a 2,000-token entry leaks only its condensed contribution.
- It only touches entries **sharing an Entity** with B, which by the key design concentrates it almost entirely on the deliberately coarse **Person and Project** hubs and barely touches the date-scoped episodic types.
- It is **unsearchable but not unreachable**: no semantic index reaches event payloads, so neither search tool can surface it — but `get_history` with `debug: true` returns the full JSONB, so an agent explicitly requesting a neighbour's audit trail can retrieve it.

Accepted on the judgement that retraction is not expected to be common, and because the alternatives cost real capability: dropping before/after summaries from payloads removes most of what the audit trail exists for — reconstructing *why* an Entity looks the way it does. **Ageing out payload JSONB while retaining the row, its timestamp and its outcome is named as the first thing to revisit** if this stops feeling right (§10).

*Source: #19, #18 §3.*

### 8.5 `query_log` retention: 90 days, exact

**What it does not touch:** nothing but itself. No Raw Entry, no Entity, no event row.

**Capacity is irrelevant at any window** — a year costs 4–73 MB against 876 GB free — so **the window controls exactly one thing: how long a record of what you were searching for exists on a disk with no LUKS layer.** It is a privacy dial, stated as one.

**90 days is calibrated against the only real evidence available.** The decisive embedding-model probe ran on **40 hand-written queries and 200 model-generated ones**, and its writeup is explicit that *"power is set by query count, not corpus size."* Set A discriminated well but was underpowered at n=40; set B had power from n=200 but was near-saturated. So the target is **a few hundred real queries** — and real queries beat *both* of those sets, carrying neither the authorship bias nor the shared-vocabulary bias that made set B too easy. A few hundred arrives in **weeks**: 200 queries is 20 days at 10 searches/day, and even at a quiet 3/day, 90 days yields ~270 — more than the largest synthetic set.

**Excluded from every dump** — `pg_dump --exclude-table-data=query_log`, **DDL retained** so a restore recreates the table empty. **Without this the bound would be a fiction.** The 7 daily dumps would give it a 7-day tail (structurally identical to retraction's accepted 7 days — fine), but the pre-wipe and pre-migrate dumps are retained *"last 3 by count, not age"*, so one can be **arbitrarily old**: a pre-migrate dump from eleven months ago would hold query text that aged out of the live table eight months earlier.

**Not backing it up is right rather than a compromise** — it is the third data category (§3.1). Cost accepted plainly: restore from backup and the log is empty, so an unbuilt judged set loses its source material and the clock restarts. Affordable against the already-accepted risk that a dead disk loses the store and its backups together.

**This amends the "no second exception" rule.** That rule was written about `enrichment_events`, whose purpose is audit; it has nothing to say about a table with no entry to be the lifetime of. The query log is **Tome's first time-based retention policy**, and it is one because it is the first thing that is neither durable input nor derived.

**The prune rides the existing daily backup timer** — a `DELETE … WHERE ts < now() - interval '90 days'`, at the right cadence. **No new unit, no third timer.**

*Source: #23 §5, §10.*

### 8.6 `enrichment_events`: no pruning, with the boundary pre-drawn

**No pruning in v1**, on the numbers in §3.5.

**Never-prunable classes, drawn now so a future policy has its boundary pre-drawn:**
- **Human decisions from `resolve_entry`** (`retry` / `skip` / `set_type`) — they back the `prior_decisions` retirement mechanism, and a Type Override is durable *input* to re-derivation, so deleting one changes future output.
- **Tombstone reason codes and excerpts** — post-retraction that is the only surviving record of dropped content.
- **Anything inside the current governance window** — `review_schema` reads it, and recurrence is the signal.

**Prunable in principle, and the only place a future policy should look:** per-stage operational progress events from *superseded* epochs, which are most of the volume.

*Source: #19.*

### 8.7 Encryption, stated as a calibrating fact

**`nvme0n1p3` carries no LUKS layer.** The filesystem holding root, the live database, and every dump is **unencrypted at rest.**

This does not change any decision above — it *calibrates* several. It is why retraction's threat model is agent reachability rather than forensics (§8.3); why the query log's window is a privacy dial doing real work (§8.5); why the journald bound matters *because* of it rather than instead of it (§7.11); and why the leak tripwire refuses to write a keys file (§7.12).

*Source: #19.*

### 8.8 Version pinning — structural for Ollama, explicit for `mcp`

**The Python side needed a real pin, and it is `mcp>=1.28,<2`** in `pyproject.toml`, with the reasoning recorded inline in the file. This is not dependency hygiene: it is the premise of §7.5's statefulness obligation and therefore of `source` existing at all. On `mcp` 2.x, `mcp.server.fastmcp` does not exist, and `client_params is None` is a *served* outcome no server-side setting can prevent — so the ⚠ "never stateless" obligation would go on being followed while silently ceasing to be sufficient.

**The bound carries a clock in the other direction**, and it is the reason to revisit rather than to forget: `mcp` 1.x caps at protocol revision 2025-11-25, so a 1.x Tome will refuse a client that opens with a 2026-07-28 envelope. Lifting the pin means re-deciding §7.5 and §9.4's `NULL` handling *first*, not afterwards. (#34)

**Ollama is not RPM-installed**: `/usr/local/bin/ollama`, owned by no package, v0.32.1, upgradeable only by re-running the install script by hand. So "pin the Ollama version" is satisfied by construction — **there is no unattended upgrade path to defend against, and no `dnf versionlock` to install.** What was missing was never pinning, it was *recording*, which the Ollama-version field of the Derivation Epoch now does.

The manual half stands: **re-run the `num_batch` ceiling probe after any hand-driven Ollama upgrade** (§6.4).

*Source: #17, #22 §1, #19.*

### 8.9 The restore procedure

**Written here, and walked by hand once at deploy time to prove it is correct.** The risk being managed is the untried runbook, not the artifact — getting the order wrong: restoring before installing pgvector, forgetting the ledger replay, restoring globals after the database.

1. **Install the pgvector RPM.** The dump opens with `CREATE EXTENSION vector` and will fail without it.
2. **Restore globals** — `psql -f` the `pg_dumpall --globals-only` output. Roles and grants must exist before the database references them.
3. **Restore the database** — `pg_restore` the `-Fc` dump.
4. **Replay the retraction ledger** — an idempotent `DELETE` by id for every line. `tome-migrate` does this unconditionally on every start, so simply starting the system performs it; do it explicitly if starting is deferred. **If you are deliberately undoing a retraction, delete its line from the ledger *first*.**
5. **Restore `/etc/tome/tome.env`** from the backup set if it was lost — it holds decisions, not defaults.
6. **Start the units.** The next timer tick will re-embed or re-enrich anything the restored state marks `pending`.

**Note what a restore costs beyond the mechanics:** `query_log` comes back empty by design (§8.5), and if only raw were restored the entity layer would cost ~50 h of re-derivation at 10k entries — which is why the whole database is in the dump.

**The scoped journald purge** (§8.3) belongs in the same runbook, as the remediation step for a tripwire hit.

*Source: #19, #26.*

---

## 9. Client setup

### 9.1 Which clients, and why iOS is not one

**v1 supports Claude Code and Claude Desktop.** The server is already centrally hosted — one instance, Streamable HTTP on the tailnet, shared by every device. Nothing server-side is per-device; what is irreducibly per-device is *client configuration*.

**iOS/mobile is excluded structurally, not as a scoping choice.** The Claude mobile app reaches MCP servers only through cloud-mediated connectors, which cannot see a Tailscale-only host. Exposing the server publicly is ruled out by the destination.

**Verified rather than assumed** at decision time: Claude Desktop still has **no native remote-MCP support** in `claude_desktop_config.json` (stdio only), and Custom Connectors remain cloud-mediated and unable to reach a private/VPN host. **Re-check this before building** — if Desktop has since gained direct remote support, the bridge disappears and §9.2 collapses.

**Transport: Streamable HTTP.** It is the current spec transport; HTTP+SSE is deprecated.

*Source: #9, #13.*

### 9.2 Endpoint and per-device configuration

**Plain HTTP over the tailnet. No TLS.** Tailscale is WireGuard end-to-end, so TLS would encrypt an already-encrypted tunnel. Against that: `tailscale cert` makes **direct outbound ACME requests to Let's Encrypt** (Tailscale only publishes the `*.ts.net` TXT record for the DNS-01 challenge), which is egress the constraint does not otherwise permit; and certs expire every 90 days with manual renewal — a silent-failure generator against a systemd-on-boot system.

Cost of plain HTTP: `mcp-remote` allows non-TLS only for literal `localhost`, so the Desktop config needs `--allow-http`. Claude Code needs nothing.

**Claude Code** — direct, no bridge:

```bash
claude mcp add --transport http tome http://odin.<tailnet>.ts.net:PORT/mcp
```

**Claude Desktop** (MacBook only — Desktop does not ship for Linux):

```json
{
  "mcpServers": {
    "tome": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.1.38", "http://odin.<tailnet>.ts.net:PORT/mcp", "--allow-http"]
    }
  }
}
```

**The bridge cannot be centralized even in principle** — Desktop launches its MCP connection as a stdio subprocess, so the bridge must be a local process on that machine. Hosting it server-side would leave nothing for Desktop to spawn.

**`mcp-remote` pinned to 0.1.38, not floating on `@latest`.** The repo is untended — ~5.5 months without commits at decision time, 99 open issues — but the risk is far lower than that suggests: its known bugs are all in **OAuth and header-passing paths**, and this deployment has no auth and passes no headers. Roughly 80% of the package is OAuth machinery that never executes here. **Pinning matters precisely *because* the repo is dead:** `@latest` offers no fixes, only the chance of a regression.

**Two open issues can reach this setup:** transport errors on server send are swallowed, so a request **hangs rather than erroring**; and the OAuth discovery probe crashes on **Node 26** with gzipped responses — and that probe **runs unconditionally, even with no auth.** **Target Node 20 or 22 LTS on the Mac; avoid Node 26.**

**A custom bridge is a documented fallback, not built.** It would not be MCP logic — stdio and Streamable HTTP carry byte-identical JSON-RPC, so a shim is a dumb pipe with seven responsibilities: read newline-delimited JSON from stdin; POST with `Content-Type: application/json` and `Accept: application/json, text/event-stream`; handle both plain-JSON and SSE reply shapes; capture `MCP-Session-Id` at initialize and echo it; send `MCP-Protocol-Version` after init; write replies to stdout newline-delimited; log to **stderr only**. **Its real risks are sharp edges, not volume:** framing bugs surface as an opaque "server failed to start", and spec drift becomes yours to track — the session header was already renamed `Mcp-Session-Id` → `MCP-Session-Id` between spec revisions 2025-06-18 and 2025-11-25.

*Source: #13, #9.*

### 9.3 Host allowlisting — the sole remaining rebinding defence

**Neither client sends an `Origin` header at all.** The SDK's `_commonHeaders()` sets only `Authorization`, `mcp-session-id` and `mcp-protocol-version`, and Node's `fetch` adds no `Origin` server-side. So the spec's Origin-validation MUST **cannot be read strictly** — a server rejecting requests that lack `Origin` would reject *both* clients.

**The policy:**
- **Validate `Host` against an allowlist enumerating every legitimate spelling:** the MagicDNS FQDN, the **short name**, the tailnet **IPv4 and IPv6**, and **`localhost` / `127.0.0.1`** — easy to forget, but that is how Claude Code running on the box itself connects. Plus the `*.tailc0e3c3.ts.net` suffix pattern.
- **Reject a request whose `Origin` is present and not allowlisted; allow an absent `Origin`.**
- **Rejections return a legible 403** naming the received `Host` and the allowed set. A bare 403 surfaces client-side as an unexplained connection failure.

**Why it matters once TLS is off the table.** Tailscale controls *which devices* reach the box but cannot control *what runs on* an authorized device. A rebound page on the MacBook is a genuine tailnet peer making a same-origin request, **invisible at the network layer** — and `search_entities` would hand over the entire memory layer. `Host` and `Origin` are browser-forbidden headers that JavaScript cannot forge, so a rebound request always carries the attacker's hostname and is rejected. Chrome 142+ classifies 100.64.0.0/10 as local-network space and prompts on public→local requests, which mitigates this browser-side, but that is a clickable prompt, Chrome-specific, and outside this system's control.

**Crucially, this adds no authentication.** No credential, token or secret; `Host` and `Origin` are set automatically from the URL already configured, and neither client config gains a flag. **The no-app-level-auth decision stands untouched.** Residual cost: the allowlist is coupled to how the box is addressed, so a device or tailnet rename is a rare, delayed breakage point — self-diagnosing via the 403.

*Source: #13, #9, #15 §7, #5.*

### 9.4 Provenance

**`source` records client type only**, from `clientInfo.name` in the `initialize` payload. Not device.

The bridge runs on the MacBook, so it does not obscure device identity — the server still sees the Mac's tailnet IP — but device is an operational detail rather than provenance you would query, and reading it would require inspecting the connection and doing a tailnet lookup: a genuinely new capability rather than a field lifted from a payload already being parsed.

**Accepted asymmetry: raw is immutable, so entries captured without device provenance can never gain it.**

### What the field actually carries — measured, not assumed

The observed payloads (#33 Gate A, `mcp` 1.28.1, protocol 2025-11-25; #34):

| Client | `clientInfo` |
|---|---|
| Claude Desktop 1.24012.9 | `{"name": "claude-ai", "version": "0.1.0"}` — nothing else |
| Claude Code 2.1.219/220 | `{"name": "claude-code", "title": "Claude Code", "version": "<real>", "description": …, "websiteUrl": …}`, byte-identical over stdio and HTTP |

Three consequences, all recorded because each is a place someone would otherwise assume more:

- **`name` only is stored, deliberately.** Claude Code offers four more fields; none is load-bearing and each would be a second thing to keep honest in an immutable row.
- **`version` is unusable and is not stored.** Desktop reports `0.1.0` while the app is 1.24012.9. **Nothing may ever be gated on a client's reported version.**
- **The field is one bit with two values on this deployment**, and `claude-ai` does not distinguish Desktop from any other first-party surface — it distinguishes it from `claude-code`, which is the whole of the information. The column name oversells it; read it as *which client wrote this*, not as provenance in any richer sense.

**Stored verbatim, never normalised.** `claude-ai` is not rewritten to `claude-desktop`. A normalising map is a guess about a vendor's naming baked permanently into rows that cannot be corrected, and the mapping is not even stable — `claude-ai` may later cover surfaces that are not Desktop. Legibility is a read-side concern; the stored value is what the client said.

### `source` is kept, and why — the write-once asymmetry

The column earns its place on availability rather than on current demand. **Nothing reads it today**: it is returned only under `debug: true` (§5.1, §5.3) and retained through a Tombstone (§5.6). Nothing filters on it, and nothing branches on it.

It stays anyway, for the reason that already decided `embedding_epoch_id` and `query_log`: **raw is immutable, so this is recorded at capture or never.** Add the column in six months and every prior entry is permanently anonymous — deferring does not postpone the cost, it postpones the start of the clock. Against that, the cost of keeping it is ~15 bytes a row and one dictionary read on a path with 11× measured headroom (§4.5).

What it buys, stated as expectation rather than fact: the two values separate **human-in-chat capture from Desktop** from **agent-driven capture inside Claude Code**, which are different capture regimes. That is the only available slice on two questions the system cannot otherwise answer — whether `context` quality differs by client (§3.3 says nothing can verify it and the tool description is the only lever, so knowing *which* client's agent misjudges the trigger is the one handle available) and whether extraction recall differs by regime (§13.1, §10.4). Neither is measured. **This is the argument for keeping a cheap unbackfillable field, not a claim that the field is already useful.**

**It must stay non-behavioural.** Protocol revision 2026-07-28 adds an explicit note that `clientInfo` is "intended for display, logging, and debugging" and that servers **SHOULD NOT** use it to change their behaviour. A provenance column sits inside that blessed use; anything downstream branching on `source` leaves it. Recorded as a rule, since the field's existence is a standing invitation to break it.

### When client identity is absent: `NULL`, never a sentinel, never a refusal

| Option | Verdict |
|---|---|
| **`NULL`** | **Chosen.** It is the true statement — *not recorded* — and it is what SQL's `NULL` already means. |
| A sentinel (`unknown`, `anonymous`) | **Rejected.** It is a lie that survives forever in a row that cannot be corrected, and off the pin it cannot even be an accurate lie: on `mcp` 2.x a **malformed** `clientInfo` is silently degraded to the same `None` as an absent one (#34), so a sentinel would merge "the client declined to identify itself", "the client sent garbage", and "Tome was misconfigured" into one value with no way back. |
| Refuse the capture | **Rejected.** §7.3 makes the capture path degrade rather than fail on purpose, §5.1's rejections are reserved for content that *cannot be stored correctly*, and #33 Gate A found Claude Desktop **never restarts a dead stdio server**, so failures on this path are unusually expensive. Trading a memory for a label about the client is the wrong direction: the label is metadata about the writer, the memory is the asset. |

**On the pinned line `None` is unreachable from any client, which is what makes it a tripwire.** Measured on `mcp` 1.28.1 over real stdio pipes (#34): `clientInfo` is a **required** field of `InitializeRequestParams`, and every ill-formed variant is rejected at the handshake with `-32602` before Tome sees a thing — absent, `null`, `{}`, wrong types, and extra-keys-only all fail. It is not degraded, it is refused. No examined client omits it anyway: python-sdk substitutes a default, the TS SDK takes it as a required constructor argument, Claude Code hard-codes it, and Desktop sends `claude-ai` (#34, #33).

So `client_params is None` at capture time on the pinned line means **Tome is misconfigured** — stateless mode enabled, or the pin crossed — not that a client chose anonymity.

**The one hole the pin does *not* close: an empty name.** `{"name": "", "version": "1"}` passes validation and is **served**, with `clientInfo.name == ""` (probed, same run). Pydantic constrains the field's presence and type, not its content. An empty string is neither an identity nor an honest absence, so **an empty or whitespace-only `name` is treated as absent** — `NULL`, same as `None`, same warning. This is the *absence* case, not an exception to storing real names verbatim. No client Tome will meet does this; it is written down because it is the only reachable path to a junk `source` value on the pinned line, and an immutable row is the wrong place to discover it.

**Build obligation:** write `NULL`, complete the capture, and emit **one `WARNING`-level log line** naming the entry id (never its text — invariant C, §7.10). It is a health signal, not a caller-facing one, so it is **not** a `warnings` entry (§5.10): the caller cannot act on it, and if the pin were ever crossed it would fire on every capture. **And the `NULL` must never be read as "the client chose anonymity"** — the day the pin lifts, `NULL` also covers a malformed payload.

*Source: #13; measured and revised by #34, #33.*

---

## 10. Out of scope & roadmap

Reasoning is carried across, not just the verdict — several of these were ruled out on facts that would otherwise be rediscovered from scratch.

### 10.1 The organising principle: projections vs. observations

Stated once, because it decides most of this list.

**Anything that is a *projection* of state Tome keeps anyway is cheap to defer** — cross-entry synthesis, entity relationships, co-occurrence. Raw is the sole source of truth, immutable, and in the backup set, so each is recomputable in full at any future point, **retroactively over all of history**, including entries captured today long before anyone decided the projection was interesting. Declining to build them forecloses nothing. Same distinction covers granularity: same-*sentence* adjacency is not in `source_entry_ids`, but it is sitting verbatim in `raw.text`.

**An *observation* is the opposite** — it exists only forward from the moment recording starts, so declining it genuinely costs the past. That is why `query_log` is in v1 and everything in this section is not.

> **Scope decisions at the entity layer are reversible by re-derivation. Scope decisions about measurement are not.**

**One thing does destroy a projection: retraction.** A retracted entry's contribution is gone permanently, by design. Storing any of this eagerly would not have helped — it would be one more surface the cascade had to reach.

*Source: #21.*

### 10.2 Ruled out permanently

**Any test fixture, sample, or eval artifact drawn from real memory content living in this repo.** Not deferred — ruled out. `markdlabrecque/tome` is **public**, and such artifacts contain real query text and real natural keys (a colleague's name, a question about their habits), which would publish exactly what the 90-day bound and the backup exclusion exist to contain. The committed research files are safe **only because their corpora are synthetic** — that was luck, and it is now policy. When a judged set lands, the leading candidate is a Postgres table: it inherits the backups, falls inside the retraction cascade, and cannot be pushed to a remote by accident. *(Source: #23 §9.)*

**Mobile/iOS access.** Structurally incompatible with Tailscale-only ingress, not a deferral (§9.1). *(Source: #13.)*

**Who *initiates* a capture** — user-directed versus a standing "capture anything notable from this session". **Outside the server's boundary rather than deferred:** the capture *path* is settled (MCP only) and the initiative never was; `capture_entry`'s prohibition covers the one dangerous case — an agent capturing its own inference as though the user had stated it. Beyond that, what prompts a call happens entirely in the calling conversation, is unobservable to Tome, and has no server-side lever, so there is nothing to specify. *(Source: #25.)*

### 10.3 Out of scope for v1, with the reasoning kept

**Typed entity relationships / edges — and any co-occurrence read.** Roadmap. Rejected **not on cost**:
- **A second governed vocabulary.** Edges need their own type list (`works_on`, `knows`, `attended`), their own identity rule (does the key for "Alex works on Tome" span the pair, or the pair plus the verb?), and their own merge semantics. An entire governance loop was built for *one* vocabulary; a second either duplicates that machinery or goes ungoverned.
- **It lands on the dominant cost term.** Relationship output is more tokens *out*, and extraction is **decode-dominant** — which is what makes a full run ~50 h at 10k entries.
- **It converts a soft failure mode into a hard one.** Everything the entity layer asserts today is a *summary*; vaguely wrong is a quality problem. An edge is a discrete factual claim an agent will restate flatly. **A hallucinated edge is a lie with a schema**, and nothing would notice.

**Co-occurrence** — two Entities whose `source_entry_ids` intersect; computed from *provenance*, never reading text; symmetric, untyped, unverbed. The traversal already exists via `get_history` (1 + N calls, zero new schema, no model). Smoothing it into one read is the tempting middle path and is wrong: **co-occurrence is not a relationship** (one entry may yield several *unrelated* Entities — a Person, a Project and a dentist appointment, mutually co-occurrent and mutually irrelevant); it is **systematically worst where it would be used** (a Project in 200 entries co-occurs with nearly everything, so it discriminates least exactly where it is asked most); it is **affordable only where it is useless** (1 + N is viable for leaf entities, which are the first-generation summaries whose prose is already intact); and **fixing it means inventing a score** with no ground truth to tune against.

**Relied on instead**, concretely — three surfaces, none able to state a false edge as structured fact: the trigram branch force-includes the named Project and cannot be cut by `limit`; that Entity's summary names people in prose; and `search_raw` is the authoritative, never-eroding answer. **"Which people are on Tome" answers as prose, deliberately.** `get_history`'s bidirectional traversal **stays audit-only** — recorded so nobody later mistakes it for a free relationship graph. Not a data risk: raw is uneroded, so a future pass extracts edges from raw retroactively. *(Source: #21.)*

**A cross-entry synthesis *surface*** (any tool returning patterns spanning subjects). Out of scope **because the caller already does this, and the entity layer already helps.** The motivating example inverts on inspection: six entries about wanting to leave a job do *not* merge — none is a Preference (a standing default; this is unsettled), none is a Decision (nothing decided), and keys are biased over-specific — so `search_entities` returns **six uneroded first-generation summaries** and the calling agent says "you have raised this six times since March." **That is the synthesis, and it works because the keys did not collapse.** Accretion would have *destroyed* the count and the dates, which are the entire signal. The residual gap is only the **never-extracted passing mention** — a note about Tuesday's meeting that happens to grumble about work — which is the raw tier working as designed, and is why `search_raw`'s recurrence trigger is an obligation (§5.11). *(Source: #21 §2.)*

**Proactive / unprompted content surfacing** (Tome noticing a pattern and volunteering it). Roadmap. v1 is strictly answer-when-asked. Ruled out as a subsystem nothing else implies: a pattern pass is periodic *over the corpus*, abandoning the prompt + one entry + one summary shape that makes an enrichment call O(1) in corpus size; it needs told-you-already state, reprising the retirement problem that aggregation dissolved; **the only delivery channel is a field on the write tool**, so Tome would report on your job dissatisfaction inside the response to an unrelated capture; and it inverts the trust model — an unprompted claim about the user, distilled from an Nth-generation gloss, with nothing to catch it being wrong. *(Source: #21 §1.)*

**Document ingestion** (auto-ingesting files, email, etc. into the raw layer) and **passive/ambient capture.** Roadmap. *(Source: map.)*

**CLI quick-capture** and a **standalone non-MCP chat UI.** Roadmap; the MCP write tool is the only v1 capture path. *(Source: #6.)*

**App-level auth beyond Tailscale.** Roadmap. *(Source: #5.)*

**Chunked embedding of over-cap captures.** Roadmap, and feasible: one Raw Entry holding the full text (preserving the atomic write and the `→ { id }` contract) plus a child table of `(entry_id, ordinal, span, embedding)`, with `search_raw` querying chunks and deduping to entries. `/api/embed` already accepts an array and returns N vectors in one call, so the embed phase costs no more per token. **It raises the cap to the enrichment budget (~5×), not to unbounded** — going past that needs chunked *enrichment*, which breaks the one-entry-one-transaction state machine on its own "one malformed JSON failing fifty entries with no attribution" reasoning. **The stronger motivation is quality, not capacity** — a single vector over 1,400 words averages away specifics — which clusters it with document ingestion, the thing that would need it first. Mean-pooling chunks into one vector is the no-schema variant, but averaging spends exactly the quality that motivates chunking. **Judge it against what client-side splitting already gives for free:** merge-on-natural-key reassembles Entities across entries, and §4.10 *measured* that splitting is the better path anyway. What splitting actually loses is narrower than it sounds — `search_raw` returns a fragment instead of the whole note, and `captured_at`/`context` get duplicated. **If this lands it also reopens the one-embedder-per-layer question** (§6.5). *(Source: #18, #22 §5.)*

**Off-machine / off-site backup.** Roadmap, with the risk accepted explicitly (§8.2). Would also need a ruling on whether replicating raw content to Mark's own laptop counts as egress under *no Tome data leaves*. *(Source: #19.)*

**Ageing out `enrichment_events` payload content** — deleting the JSONB body of superseded operational events while retaining the row, its timestamp and its outcome. Roadmap, and **the only form of pruning that would earn its place**, since capacity never justifies pruning rows at this scale. Motivated not by space but by the residue in §8.4. Deferred because retraction is uncommon and the alternatives cost real capability. **Named as the first thing to revisit** if the residue stops feeling acceptable. *(Source: #19.)*

**Desktop notifications for stuck work** (`OnFailure=` firing `notify-send`). Roadmap. Technically feasible — `/run/user/1000/bus` exists and `notify-send` is installed — but it means hardcoding a uid into a system unit and goes silent when nobody is logged in. Affordable to defer because the attention interface plus `warnings` already surface stuck work inside the tool. **Known gap while deferred: that channel is dead if the MCP server itself fails to start**, which surfaces only as a Claude connection error — obvious that something is wrong, not *what*, requiring `journalctl --namespace=tome` to diagnose. *(Source: #15 §8, #26.)*

**Per-entry contribution storage** — the genuinely correct answer to the retraction cascade's approximation (§8.3). *(Source: #18 §3.)*

### 10.4 The judged set and eval harness — out of scope, route recorded

A **judged set** is an answer key (query → graded natural keys) and it is what turns a replay into a *score*. Without it you get two ranked lists and no verdict, since scores are comparable neither across models (different vector spaces) nor across time (§3.8). With it, a model comparison becomes two nDCG@10 numbers on the same key plus a paired bootstrap CI.

**Out of scope rather than fog: it needs 90 days of real usage that does not exist yet**, so it cannot precede deployment and no PRD can specify it. Deferring is also *safe* in the way deferring the log is not — judgements are constructible from the log at any point inside the window.

Recorded so it is not rediscovered:

- **Grades are 0/1/2, not binary** — the model probe's own stated limitation was *"no relevance judgements beyond one gold answer per query; several 'misses' are arguably correct."*
- **An offline `qwen3:14b` judge drafts, a human reviews.** The judge is **genuinely independent of the system under test**, since what is evaluated is the *embedding* model — so the usual LLM-as-judge circularity does not arise, and Tome gets a free local independent judge purely because the two model choices landed on different models. The human pass is **not optional**: the same model already generated 200 queries and 770 distractors and its set B was noisy, "generic-knowledge rather than personal-memory shaped".
- **On-demand, never a routine** — a log-in-to-the-box act like `--reembed` and full mode. **No new unit, no third timer.**
- **A natural-key sanity pass before each comparison.** If a revised prompt starts emitting `person:alex chen` where it emitted `person:alex-chen`, that judgement silently reads as a miss. Cheap, and a real maintenance cost.
- **It benchmarks the retrieval pipeline, not just a model** — at least six things, **five of which this document currently asserts without measuring**: the embedder choice; the **`natural_key` trigram branch** (ablate and read the difference — closing the "entirely conjectural" question); **merge-depth erosion** (nobody has checked whether a twelve-times-merged summary is still findable); **the tiering premise** (the mechanism is conceded to be near-identical to `search_raw`, with primary buying compression rather than method); the one-vs-two-embedder question; and **exact-vs-HNSW recall** if the tripwire fires, giving *your* number rather than a general "~1–5%".
- **Never in this repo** (§10.2).

**A pleasing consequence.** Tome's derivation can never be reproducible — Ollama refuses digest-addressed models, tags are mutable, blobs are pruned — and that is fine because re-deriving under better rules should yield *better* Entities, not identical ones. **A judged set is how you would ever know it did.** Fixed query set + fixed answer key + today's corpus is a number comparable across model swaps: *the evaluation is reproducible even though the system is not*, which is the right way round.

*Source: #23 §8, #17.*

### 10.5 Rejected surfaces, recorded so they are not proposed again

| Rejected | Reason |
|---|---|
| **A `judge_search` MCP tool / any self-reported relevance** | The agent would grade retrieval it just performed and is about to act on, inviting sycophancy; it costs a tool call and tokens on every search; server-side score thresholds were already turned down as unmeasurable knobs; and the offline route (§10.4) is strictly better. |
| **A second `tome-admin` MCP server** | A second endpoint, a second `Host`-allowlist consumer, another Desktop bridge, extra unit topology — all against a speculative risk on a single-user machine. Tool descriptions carry the discipline instead. |
| **A server-side low-score threshold appending a fallback hint** | Another unmeasurable knob, duplicating a judgement the caller is better placed to make once it can see scores. |
| **A message queue / broker in front of enrichment** | §4.6. |
| **Full event sourcing** | Tome is already event-sourced where it counts — raw is immutable and the sole source of truth, entities are purely derived, and full mode is replay. Adopting it literally would put a log *underneath* the raw table, contradicting that directly, to gain nothing. What was actually missing was process telemetry. |
| **The saga pattern with an orchestrator** | Sagas exist because distributed services cannot share a transaction. Tome is one Postgres, one runner, one machine, with each entry's writes already in a single transaction — **`ROLLBACK` *is* the compensation, for free.** The two-phase run looks saga-shaped but its phases are independently idempotent and cross-phase compensation is never wanted: if enrichment fails, the embedding is kept. |
| **Build-alongside-then-swap for full mode** | §4.1. |
| **Append-only extractions** (every extraction its own row, reader merges) | The entity layer stops being a *compression* of raw — entity count would grow roughly linearly with raw entries, making the primary surface a re-shaped copy of raw with a type label. Plus recall dilution proportional to capture frequency (the people mentioned most return worst), no designated moment where contradictions get reconciled, no stable handle for a thing, and per-type counts measuring capture volume rather than distinct subjects. |
| **Embedding-similarity entity resolution** | Merges above a threshold, and mis-merges **silently**. |
| **An `attribution: stated \| inferred` field** | §5.11. |
| **A regex scrubber on the log handler** | §7.10. |
| **`tailscale serve`; restricting the firewalld zone** | §7.4. |
| **Alembic; an ORM** | §7.1–7.2. |
| **Deriving the Host allowlist from `tailscale status`** | §7.8. |
| **The `UPDATE … SET embedding = NULL` re-embed runbook; folding re-embed into full mode** | §4.1. |
| **Purging backups on retraction** | §8.3. |
| **A weekly restore-into-scratch** | §8.2. |
| **Whole-corpus context; the iGPU; splitting models across both GPUs** | §4.9, §7.7. |
| **Hybrid FTS/RRF over summaries; IVFFlat; HNSW in v1** | §6.1–6.2. |
| **Per-type confidence thresholds; a writable threshold** | §5.7. |
| **An itemized `review_schema` with a review watermark; a `dismissed_at` column** | §5.7. |
| **A denormalized `last_triaged_at` / `last_triage_action` pair** | §5.5. |
| **A hash or prefix instead of a natural key in logs** | §7.10. |

---

## 11. Collected build obligations

**Read this section before writing code, and again before calling the build done.**

Most decisions on this map created obligations that land on *other* parts of the system. Several are one-line settings whose omission **silently voids an entire analysis** — and a builder who misses one will not find out from a test. Those are marked ⚠.

### 11.1 The silent voiders

If only one part of this section is checked, check this table. Every row is a case where the system keeps working and the reasoning behind it quietly stops being true.

| ⚠ | Obligation | What its absence silently voids | § |
|---|---|---|---|
| ⚠ | **`truncate: false` on every `/api/embed` call** | A 135k-char input returns a *valid* 1024-dim vector of the opening ~8%. Stored as the entry's embedding, indistinguishable from a real one. | 6.4 |
| ⚠ | **`options.num_batch: 8192` on every `/api/embed` call** | The usable window is **2048, not 8192**. `num_ctx` cannot raise it. Every capacity argument downstream. | 6.4 |
| ⚠ | **`SET STORAGE PLAIN` on both vector columns** | Every 4 KB vector TOASTs out-of-line, so a sequential scan detoasts every row — quietly undoing the whole exact-search analysis. | 3.11 |
| ⚠ | **`MaxFileSec=1day` in `journald@tome.conf`** | `MaxRetentionSec` deletes whole *files*, so at the 1-month default the effective bound is **~60 days, not 30** — and size rotation cannot rescue it, because invariant C makes the namespace too quiet to ever hit `SystemMaxFileSize`. | 7.11 |
| ⚠ | **`AND text IS NOT NULL` on *every* work query** — pending set, phase-1 sweep, `pending_count`, `un_embedded_count`, **and full mode's reset** | A Tombstone becomes a permanent phantom in the backlog, and the timer checks `pending_count` before loading a model — so every idle tick loads `qwen3:14b` for nothing. Must exist **exactly once** in shared code. | 5.6, 7.1 |
| ⚠ | **`pg_dump --exclude-table-data=query_log`** (DDL retained) | The 90-day bound becomes fiction: event-triggered dumps are retained *by count*, so one can be arbitrarily old and hold query text that aged out of the live table months earlier. | 8.5 |
| ⚠ | **`restorecon -R /opt/tome` in `make deploy`** | Files copied out of a home directory carry home labels with them. SELinux is Enforcing. The classic Fedora footgun. | 7.6 |
| ⚠ | **Bound `num_predict` to the output reserve** | An unbounded generation ran **17,957 output tokens / 602 s / 33× baseline, producing nothing**, with context-shift firing mid-generation. | 4.4 |
| ⚠ | **`chattr +C` on the Postgres data dir *before* `initdb`** | Applying it later does not affect existing files. Postgres on CoW btrfs fragments badly. | 3.11 |
| ⚠ | **`--rotate` with any scoped journald vacuum** | Vacuum skips *active* files, so a bare `--vacuum-time=1s` leaves everything recent behind. | 8.3 |
| ⚠ | **No concrete example natural keys in the extraction prompt** | Reproducible in **8 of 12 responses**: example keys are re-emitted as **fabricated Entities** with confabulated summaries. A fabricated Commitment does not read as an error; it reads as a memory. | 4.9 |
| ⚠ | **Rejections must use FastMCP's dedicated tool-error type, not a bare `ValueError`** | FastMCP masks unexpected exception detail, so *permanent / the numbers / the remedy* all collapse into "internal error" — reinstating the silent failure the rejection exists to prevent. Applies to both the size gate and `context`'s cap. | 5.1 |
| ⚠ | **Stateful sessions (never `stateless`) on the HTTP entry point** | `_client_params` is per-`ServerSession` state set at `initialize`, so a stateless `tools/call` arrives with none — **breaking `source`** and the session id the fallback signal depends on. | 7.5 |
| ⚠ | **`mcp>=1.28,<2` in `pyproject.toml`** | The row above. On 2.x, `mcp.server.fastmcp` **does not exist**, and `client_params is None` becomes a *served* outcome no server-side setting can refuse — so "never stateless" silently stops being sufficient while still being followed. | 7.5, 8.8 |
| ⚠ | **`configure_logging()` pinning non-`tome` loggers to `WARNING`** | A FastMCP version that logs tool arguments at `DEBUG` puts `capture_entry`'s full text in the journal **with no Tome code involved**. | 7.10 |
| ⚠ | **`logging_collector=off` and `log_parameter_max_length_on_error=0` on Postgres** | The first makes PG write files under the data dir — a third log store outside every bound and outside the dumps. The second means a failed insert into `raw_entries` **logs the entry text itself**. | 7.11 |
| ⚠ | **Record the embedding model **tag *and* digest** at capture** | The only piece of this design that **cannot be fixed later**. Raw provenance is write-once and already decaying: every vector written without a digest goes permanently ambiguous the moment the tag republishes. | 3.2 |
| ⚠ | **The pre-flight budget assertion** | Without it the collapsed capture/enrichment threshold is an argument that happens to hold rather than a guarded invariant — and the failure it guards is a **cliff** that discards the entire instruction block and records the entry `enriched`. | 4.4 |

### 11.2 Schema, DDL and database

- [ ] `UNIQUE (entity_type, natural_key)` on `entities` — the `ON CONFLICT` merge target. *(#12)*
- [ ] `entities.embedding vector(1024) NOT NULL`, `SET STORAGE PLAIN`. *(#16)*
- [ ] `raw_entries.embedding vector(1024)` **nullable**, `SET STORAGE PLAIN`. *(#12, #16)*
- [ ] Fixed dimension, not an unconstrained `vector` — mixed dimensions fail at runtime instead of at migration time. *(#16)*
- [ ] GIN trigram index on `entities.natural_key`. *(#16)*
- [ ] `pgvector` and `pg_trgm` RPMs installed; pgvector present **before** any restore. *(#16, #19)*
- [ ] `enrichment_events.raw_entry_id` → `ON DELETE CASCADE`. *(#18)*
- [ ] `enrichment_events` append-only, **DB-enforced** (`REVOKE UPDATE/DELETE` from the app role; entity mutations routed through a function or trigger that writes the event). *(#12)*
- [ ] `derivation_epoch_id` FK on `entities`, `enrichment_events`, and **every `query_log` row**. *(#17, #23)*
- [ ] `embedding_epoch_id` on **both** `raw_entries` and `entities` — the `--reembed` predicate reads it on both layers. *(#17)*
- [ ] `raw_entries.prompt_eval_count` stored at capture. *(#18)*
- [ ] Bounded `entities.summary` — **1,200 chars**, a starting point (§13.4). *(#16)*
- [ ] Type Override persists across full mode; full mode's reset is `WHERE text IS NOT NULL`. *(#14)*
- [ ] `schema_migrations(version, applied_at)`; numbered SQL files, each in its own transaction. *(#20)*

### 11.3 Ollama call sites

- [ ] **Embed:** `truncate: false`, `options.num_batch: 8192`, **prepend nothing**. *(#18, #22)*
- [ ] Embed phase **batches** (~3× measured: 105 ms singly → 37 ms at batch 50). *(#17)*
- [ ] **Extract:** thinking mode disabled, `temperature: 0`, per-request `num_ctx` ~16k, **`num_predict` bounded to the reserve**. *(#8, #15, #24)*
- [ ] Pre-warm `bge-m3` at MCP server start with `keep_alive=-1`. *(#15)*
- [ ] **Explicitly unload `qwen3:14b` at the end of every run.** *(#15)*
- [ ] Capture embed: **5 s timeout**, `catch` *is* the deferred path, tool returns success, **timeout does not count toward `attempt_count`**, structured log line only (no warning). *(#12)*
- [ ] Translate Ollama's oversize message; never pass it through. *(#18)*
- [ ] Re-run the `num_batch` ceiling probe after any Ollama upgrade. *(#22, #17)*

### 11.4 The extraction prompt

- [ ] Ships **in the `tome` package, in git**, covered by `make deploy`. Not `/etc/tome/`. *(#17)*
- [ ] Identity = hash of the **rendered** text, computed at run start. *(#17)*
- [ ] **Stated budget: 3,000 qwen3 tokens, asserted at run start** alongside the hash. *(#24)*
- [ ] Entity-type definitions and `_Avoid_` lines **verbatim from CONTEXT.md**. *(#12)*
- [ ] Exactly one type forced; **`Fact` is never the tie-break**. *(#12)*
- [ ] Per-type key-specificity rules, biased over-specific; coarse only for Person and Project. *(#12)*
- [ ] **The `context` subordination rule, verbatim.** *(#25)*
- [ ] **The name-precedence rule** — drop narrative before a named entity. *(#21)*
- [ ] ⚠ **No concrete example natural keys.** *(#24)*
- [ ] Case-preservation carve-out in the key rules (`ROCm`, not `roc-m`). *(#24)*
- [ ] Prefer the event's own date over `captured_at`. *(#24)*
- [ ] Type Override enters as a **tie-break constraint firing only below threshold**, never a blanket relabel. *(#14)*

### 11.5 The MCP HTTP edge

- [ ] `Route("/mcp", methods=["POST"])` → **405 on GET**, with an `Allow` header. *(#13, #20)*
- [ ] Unmatched paths → **immediate 404**. Never hang. *(#13)*
- [ ] `Host` allowlist: FQDN, **short name**, tailnet **IPv4 and IPv6**, **`localhost` and `127.0.0.1`**, plus the `*.tailc0e3c3.ts.net` **suffix** pattern (the SDK's wildcards are port-only → ~20-line subclass). *(#13, #15, #20)*
- [ ] **Allow an absent `Origin`; reject a present-but-unallowlisted one.** *(#13)*
- [ ] **Legible 403** naming the received `Host` and the allowed set — the SDK returns 421. *(#13, #20)*
- [ ] `json_response=True`. **No server-initiated SSE, ever.** *(#13, #20)*
- [ ] ⚠ **Stateful sessions**, and ⚠ **`mcp>=1.28,<2`** — the second is what makes the first sufficient. *(#20, #34)*
- [ ] `source` read from `clientInfo.name` at `initialize` — **client type only**, stored **verbatim** (`claude-ai`, not `claude-desktop`), never agent-supplied, never device, never read to change behaviour. *(#10, #13, #34)*
- [ ] `raw_entries.source` **nullable**; write `NULL` when client info is absent **or its `name` is empty/whitespace** (the one junk value 1.x validation lets through), never a sentinel, and **never refuse the capture**. Log one `WARNING` when it happens — on the pinned line it should be unreachable. *(#34)*
- [ ] The fallback-judgement pairing (§3.8) applies its interval **at read time**; the session id is stored raw. Never bake the bound into a row. *(#34)*
- [ ] Flag a `captured_at` that disagrees wildly with the server clock. *(#15)*

### 11.6 The runner

- [ ] Non-blocking advisory lock **first**, then the work check — **before any model loads**. A skipped firing is normal, logged at debug, and **must not touch `last_successful_run_at`**. *(#12)*
- [ ] Per-entry transaction: entry state + Entities + vectors, atomically. **No transaction across an HTTP call.** *(#12, #16)*
- [ ] `SELECT … FOR UPDATE` on the raw row at the start of the per-entry transaction. *(#18)*
- [ ] N = 3; **no backoff retry** for deterministic failures. *(#12)*
- [ ] **Unparseable output is transient**, reaching `resolution_required` only after exhaustion — with a reason code distinguishing that from a deterministic refusal. *(#24)*
- [ ] ⚠ **Pre-flight budget assertion** `P + entry×0.906 + 500 + reserve ≤ num_ctx`, reusing the stored `prompt_eval_count`. Over budget → `resolution_required`, no model call. *(#24, #25)*
- [ ] Entity vector **re-embedded on every merge**. *(#16)*
- [ ] Full mode: `pg_dump` → wipe → reset (`WHERE text IS NOT NULL`) → ordinary loop; dump path recorded in the run's event log. *(#12)*
- [ ] `--reembed`: predicate `embedding_epoch_id != current` over **both** layers; no extraction, no wipe, no dump; idempotent and resumable; **CLI only**. *(#17)*
- [ ] Refuse the affected read tool during full mode / re-embed, **naming the operation and the alternative**. *(#12, #17)*
- [ ] Staleness measured against **uptime**; tolerate a future-dated `last_successful_run_at`. *(#15)*
- [ ] Run the leak tripwire once at the end of a **full** run. *(#26)*

### 11.7 Tool surface and descriptions

- [ ] Nine tools, one endpoint. `debug?: boolean` on every one. *(#11, #14, #18)*
- [ ] `score` in `search_entities`' **normal** response. *(#16)*
- [ ] `context` in `get_enrichment_status` items' **normal** response; `debug`-only on `search_raw` and `get_history`. *(#25)*
- [ ] `get_history` returns **`text`** for a `raw_entry_id`. *(#18)*
- [ ] `warnings` absent when healthy; six producers, two persistent (§5.10). *(#12, #17, #19, #26)*
- [ ] `capture_entry` description: prescribed `context` content, the **inference-goes-in-`text` prohibition**, and the populate-trigger. *(#25)*
- [ ] `search_entities` description: the concrete fallback trigger, including *the entry may be newer than the last run*. *(#16)*
- [ ] `search_raw` description: **both** triggers — relevance **and recurrence/cross-subject**. *(#16, #21)*
- [ ] `resolve_entry` description: records a decision a human has already made; **must not be called autonomously**. *(#14)*
- [ ] `context` cap **1,000 chars in code**, coupled to the **500-token** allowance — raise one, raise the other. *(#25)*
- [ ] `capture_entry` size rejection: **permanent / the numbers / split-and-retry**, written for the model as primary reader. Plus the ~40,000-char absurdity backstop. *(#18)*
- [ ] Confidence threshold **visible via `review_schema`, not writable through MCP**. Starting value **0.7**; type-stickiness override margin **+0.20 and ≥ threshold** (§13.4). *(#14)*
- [ ] `get_enrichment_status` gains **entity counts grouped by epoch**. *(#17)*
- [ ] `review_schema`'s window = **since the last full run began**, read from the run log. *(#17)*

### 11.8 systemd, OS and logging

- [ ] Seven units; `tome` system user with **no `render`/`video` groups**. *(#15, #19)*
- [ ] `tome-mcp`: hard on Postgres, **soft on Ollama**. `tome-enrich`: hard on both. **No `tailscaled` dependency.** *(#15)*
- [ ] `IPAddressDeny=any` + `IPAddressAllow=100.64.0.0/10 fd7a:115c:a1e0::/48 localhost`; bind `0.0.0.0`. *(#15)*
- [ ] Timer: monotonic, ~15 min, `OnBootSec≈5min`, **no `Persistent=`**, no `Restart=` on the runner. *(#15)*
- [ ] Ollama drop-in: shorten the global keep-alive; **`OLLAMA_GPU_OVERHEAD` ~1.5 GiB**; drop the global `OLLAMA_CONTEXT_LENGTH`; `NUM_PARALLEL=1`. *(#15)*
- [ ] ⚠ **`OLLAMA_HOST=127.0.0.1:11434` in the *Tome* drop-in.** It is already the bind here, but only via the pre-existing `90-pi-local-rocm.conf`, which Tome does not own — and `0.0.0.0:11434` is LAN-reachable given the firewalld zone. **`ollama.service` gets no `IPAddressDeny=`** — deliberately, §7.7. *(#28)*
- [ ] **`LogNamespace=tome`** on `tome-mcp`, `tome-enrich`, `tome-backup`, **and `postgresql.service`** (drop-in). *(#26)*
- [ ] `/etc/systemd/journald@tome.conf`: `MaxRetentionSec=30day`, ⚠ **`MaxFileSec=1day`**, `SystemMaxUse=1G`. Whole-box drop-in: `SystemMaxUse=4G`, no time limit. *(#26)*
- [ ] ⚠ `logging_collector=off`, `log_parameter_max_length_on_error=0`. *(#26)*
- [ ] ⚠ `chattr +C` on the PG data dir before `initdb`. *(#15)*
- [ ] `SyslogIdentifier=` per unit. `/var/lib/tome/backups/` mode **0700**, owned by `tome`. *(#15, #19)*
- [ ] **Invariant C**, plus `log_exception()` and ⚠ `configure_logging()`, plus the one-time third-party logger audit. *(#26)*
- [ ] RTC: `RealTimeIsUniversal=1` on the Windows side, then `timedatectl set-local-rtc 0`. *(#15)*
- [ ] Runbook note: the working form is `journalctl --namespace=tome -u …`. *(#26)*

### 11.9 Deploy, backup and runbook

- [ ] `make deploy` in order: **stop timer** → copy → `uv sync --frozen` → ⚠ `restorecon -R` → `tome-migrate` → restart → start timer. *(#20)*
- [ ] `tome-migrate` **`pg_dump`s first** and **replays the retraction ledger unconditionally on every start**. *(#19, #20)*
- [ ] Migrations never on the boot path. *(#20)*
- [ ] Daily backup: `pg_dump -Fc` + `pg_dumpall --globals-only` + **ledger** + **`tome.env`**. ⚠ `--exclude-table-data=query_log`. *(#19, #23)*
- [ ] **`pg_restore -f /dev/null` per dump**; **rotate only after verifying** (peak 8, not 7). *(#19)*
- [ ] **Below 10 GB free: skip and warn.** *(#19)*
- [ ] Event-triggered dumps: **last 3 by count, not age**. *(#19)*
- [ ] 90-day `query_log` prune on the **same daily timer** — no third timer. *(#23)*
- [ ] Daily leak tripwire on the same timer: **process substitution, counts only** (`keys_checked`/`keys_suppressed`/`lines_scanned`/`hits`), visible collision allowlist, nonzero → persistent warning. *(#26)*
- [ ] Retraction cascade reaches: raw row, its events, affected Entities (+ requeue survivors, one hop), **and `query_log` rows naming the removed key**. *(#18, #23)*
- [ ] **The restore procedure walked by hand once at deploy** (§8.9). *(#19)*
- [ ] Scoped journald purge in the runbook, **not fired by `retract_entry`**. *(#26)*

---

## 12. Superseded & corrected decisions

The map records corrections in place, so **a naive read of an early ticket gives the wrong answer.** This table gives the current answer; the history is in the tickets and is not replayed here.

### 12.1 Model and runtime — #8 was corrected three times

| Original (#8) | Current answer | Corrected by |
|---|---|---|
| Ollama as the runtime; `gfx1030` natively supported, no `HSA_OVERRIDE_GFX_VERSION`; vLLM ruled out (no RDNA2) | **Stands.** | — |
| `qwen3:14b` Q4_K_M for enrichment, thinking mode disabled | **Stands.** Size corrected: **10 GB at `num_ctx: 16384`**, not the 9.3 GB download figure. | #22 |
| **`nomic-embed-text` v1.5, 768-dim, for embeddings** | **`bge-m3`, `vector(1024)`.** `nomic-embed-text` is **disqualified twice**: its Ollama GGUF declares 2048 (not 8192 — #8 had this backwards) with no option to raise it, and it requires two-sided prefixes Ollama never applies. | #22 |
| **"Simultaneous residency isn't needed; sequential hot-swap loading is sufficient"** | **Both models are co-resident** — `OLLAMA_MAX_LOADED_MODELS` is auto = 3, so there is no swap. The embedder is *pinned* at `keep_alive=-1`, which the whole residency design depends on. | #15 |
| Version pinning flagged as an open risk | **Already satisfied structurally** — Ollama is hand-installed at `/usr/local/bin`, so there is no unattended upgrade path. What was missing was *recording*, now the epoch's Ollama-version field. | #17 |

### 12.2 Capture ceiling — the number survived, the reason changed

| Claim | Current answer |
|---|---|
| **#18: "the embedding ceiling is 2048 tokens, not 8k — an unavoidable Ollama runtime artifact"** | **The cap was Ollama's default `num_batch`, and it is liftable** — lifting it gives the full 8192 (~5,600 words). *(#22)* |
| **#22: "so the configured limit becomes 8192"** | **The ceiling is held at ~2048 anyway, on quality grounds** — a large entry does not fail, it silently enriches into a fraction of itself (§4.10), and raising is reversible while an immutable 8192-token entry is not. 2048 also happens to sit at the knee where recall begins to fall. *(#24)* |
| **#18/#24: "capture and enrichment thresholds collapse to one"** | **Upheld, with a ~6× margin — and now *guarded*** by the pre-flight assertion rather than resting on an argument that happens to hold. *(#24)* |
| **#15: "the extraction prompt is ~3–6k tokens"** | **P = 1,215 measured** — 2.5–5× too high, but wrong in the safe direction, so the ~16k per-request ceiling needs no revisiting. *(#24)* |
| **#17 declined to bound the prompt's size** | **Bounded at 3,000 qwen3 tokens**, asserted at run start — because an unbounded prompt narrows the largest enrichable entry **retroactively**, and raw is immutable. *(#24)* |
| **#25's inherited expectation that the capture gate and the pre-flight assertion would count the same thing** | **They diverge, by design** — the gate counts `text` alone, the assertion counts `text` + `context`. Each must count **its own call's actual input**. *(#25 §9)* |

### 12.3 Logging and retention

| Original | Current answer | Corrected by |
|---|---|---|
| **#20: "log lines include natural keys, accepting that memory content lands in the journal"** | **Superseded by invariant C** — no Raw-Entry text and no Natural Key ever reaches a log line. Identifiers are `raw_entry_id` + `entity_type` + `entity_id`. | #26 |
| **#18/#20: "natural keys persist in journald until rotation"** | **Restates as true rather than true-modulo-a-decade**: no keys by construction, and residue ages out of Tome's namespace in **30 days**. *(The intermediate correction — that journald here had no time-based retention, making "until rotation" ~a decade — was #23's Finding C.)* | #23, #26 |
| **#23: "bounding journald retention is a decision about the whole machine"** | **False, and that was the unlock.** `LogNamespace=tome` gives a unit its own journald instance reading `/etc/systemd/journald@tome.conf` — **retention is per-namespace.** | #26 |
| **#12: "journald is operational and ephemeral"** | **Holds in intent, not in fact on this box.** A successful search is not an operational event and does not go there; `duration_ms` lives in `query_log`. | #23 |
| **#19: `enrichment_events` is append-only, retraction-cascade the sole deletion path, "no second exception"** | **Amended.** That rule was about a table whose purpose is audit; it says nothing about a table with no entry to be the lifetime of. `query_log` is a **third data category** and Tome's **first time-based retention policy**. | #23 |

### 12.4 Pipeline and schema

| Original | Current answer | Corrected by |
|---|---|---|
| **#12: phases exist to pay the model load once (embed all → swap → enrich all)** | **Redescribed, not broken.** There is no swap, so phases divide work by **kind**: phase 1 embeds raw, phase 2 enriches and embeds Entities. | #15, #16 |
| **#12: the deferred-embed path exists to avoid a model swap** | **Re-justified.** That rationale was voided by pinning; the path now covers a capture embed queueing behind an *entity* embed on the same `NUM_PARALLEL=1` instance. | #16 |
| **#12: `nomic-embed-text` in the two-phase description** | Reads **`bge-m3`**. | #22 |
| **#12: unparseable model output is a *deterministic* failure** | **Transient**, retried N=3 — measured at ~50% on identical input at `temperature: 0`. As written, the taxonomy routed Tome's most likely failure to a human instead of the retry loop. **CONTEXT.md was corrected.** | #24 |
| **#12: staleness measured by wall-clock age** | **Measured against uptime**, and tolerant of a future-dated timestamp — the machine is dual-booted and sometimes off. | #15 |
| **#10: `embedding_model` (+ version) text column on raw** | **`embedding_epoch_id`** — the epoch record names the model *and* carries the digest #10 could not. | #17 |
| **#16: entities carry `embedding_model`** | Subsumed by **`embedding_epoch_id`**, plus a separate **`derivation_epoch_id`** for the extraction axis. *(Naming harmonised — §14.)* | #17 |
| **#14: `review_schema` is "scoped to the current Derivation Epoch", returning `epoch_started_at`** | **"Since the last full Enrichment Run began"** — a *time* question answered from the run log. Behaviourally identical; the Epoch stopped being a span. | #17 |
| **#14: the primary justification for the `skip` Tombstone is an oversized entry** | **Unreachable** — an entry that large could never have been captured. `skip` narrows to **unparseable content only**. | #18 |
| **#14: full mode's reset is unconditional** | **`WHERE text IS NOT NULL`** — on structural grounds (*do not queue rows that cannot be processed*), **not** to preserve a human decision, which stays overruled. | #14 §5, #18 |
| **#14: status items carry `text_excerpt` and no `context`** | **`context` is added, in the normal response** — the item is a decision packet, not a search result. | #25 |
| **#14: eight tools** | **Nine** — `retract_entry`. | #18 |
| **#12/#14: `enrichment_events` needs a redaction carve-out for content removal** | **No carve-out.** Hard-purge retraction + `ON DELETE CASCADE` means the invariant restates with no "except". | #18 |
| **#14: the tombstone phantom risk threaded through five queries** | **Removed for retraction** (a purged row is absent by construction) but **still live for `skip`** — the predicate obligation stands. | #18 |
| **#22: adopting `embeddinggemma` later costs "a full entity re-derive"** | **It costs a re-embed — minutes, not 50 hours.** The summary text is unchanged. This *strengthens* the deferral rather than overturning it; the architectural objection is the real reason. | #17 |
| **#15: the extraction prompt lives in `/etc/tome/`** | **The prompt is code**, shipped in the package, in git, inside `make deploy` and inside review. | #17 |
| **#15: process startup cost is a concern for a 15-min `oneshot`** | **Retired on measurement** — 0.17 s warm / 0.45 s cold. | #20 |
| **#9: the transport's `Origin` MUST** | Cannot be read strictly — **neither client sends `Origin` at all.** Implemented as a `Host` allowlist, absent `Origin` allowed, present-but-unallowlisted rejected. | #13 |
| **#9: a reported memory leak in the Python SDK's Streamable HTTP** | **Stateless-mode only**, and stateless is *declined* here — avoided by construction on the pinned 1.x line. Two corrections: "impossible" was too strong (it is a setting Tome refuses, not an unavailable one), and the avoidance is **downstream of `source`** rather than independent — drop the column and the leak is a live consideration again. | #20, #34 |
| **#13/#10: `source` example value `claude-desktop`** | **No client sends it.** Desktop announces `{"name": "claude-ai", "version": "0.1.0"}` — a placeholder version against app 1.24012.9. Stored verbatim; nothing may be gated on a reported version. | #33, #34 |
| **#20: sessions are stateful "forced, not chosen", full stop** | **True only on `mcp>=1.28,<2`.** On 2.x's modern era a `clientInfo`-less request is *served* with `client_params is None` and no server-side setting refuses it; the client's first frame picks the era. The pin is the premise, not a detail. Also corrected: the earlier reading that the 2.x failure was "structurally unreachable on stdio" is **false** — reproduced over real pipes. | #34 |
| **#16: the tripwire fires on "measured `search_entities` p95"** | **Now fireable** — `percentile_cont(0.95)` over `query_log.duration_ms`. **The threshold number is still open.** | #23 |
| **#11's lean-response convention** | **Three named departures** — `warnings`, `score`, and `context` on status items (§5). The always-on `query_log` is *not* a fourth: `debug` governs what the caller sees. | #12, #16, #23, #25 |
| **#21: `context` is "the only channel carrying *why* something was captured"** | **Contradicted, and motive is cut.** It has no consumer once extraction is subordinated and proactive surfacing is out of scope, and it is the most hallucination-prone content in the field. | #25 |
| **#12: "full runs are rare"** | **Right that they are rare, wrong that they are cheap** — ~5 h / 1k, ~25 h / 5k, ~50 h / 10k. | #18 |

---

## 13. Known limitations, accepted risks, and unmeasured claims

Kept separate from §10 on purpose: nothing here is out of scope. These are things v1 will ship *with*.

### 13.1 The one open question

**Whether one extraction pass per entry is enough.** §4.10 in full. Not resolvable before deployment: it needs the query log plus a judged set, and telemetry cannot see it by construction because under-extraction produces **plausible results rather than empty ones.** The suspected shape is a per-type or two-stage pass — a revision of the one-call-per-entry state machine, and therefore expensive to get wrong. **Revisit when there is evidence rather than a synthetic corpus.**

### 13.2 Accepted risks

| Risk | Accepted because | § |
|---|---|---|
| **A dead `nvme0n1` loses the store and its backups together** | Both alternatives were ruled out on facts (Windows is taking the second NVMe; the tailnet has no always-on peer), and a mechanism nobody can rely on is worse than a documented gap. Raw cannot slow-burn, so what remains uncovered is **media failure alone, not mistakes**. | 8.2 |
| **The live database and every dump are unencrypted at rest** | No LUKS on `nvme0n1p3`. Not a decision so much as a calibrating fact — it is why several bounds exist and what retraction can be understood to promise. | 8.7 |
| **Retracted content persists in backups for up to 7 days** | Purging dumps risks a corrupt recovery set; the blunt variant costs the whole window. And on an unencrypted disk the threat model was never forensics — it is **agent reachability**, which retraction does deliver immediately. | 8.3 |
| **Retracted content persists *indefinitely* in neighbours' event payloads** | Distilled not verbatim, unsearchable though reachable via `get_history --debug`, concentrated on the coarse Person/Project hubs. Named as the first thing to revisit. | 8.4 |
| **Retraction makes "never captured" and "retracted" indistinguishable** | For `sensitive` that is the point. For `mis_capture` it makes "did I ever capture that?" unanswerable. Total-capture counts can go down. | 8.3 |
| **The cascade is one hop, so a survivor's content can fold into a neighbouring Entity twice** | Done correctly, one retraction re-derives the corpus. Approximate idempotency is near-no-op by construction, and re-derivability already disclaims summary wording. | 8.3 |
| **Up to 15 minutes where `search_entities` returns nothing for a retracted subject** | The timer is the retry mechanism; an immediate run is a coin flip against the advisory lock. `entries_requeued` tells the caller a rebuild is pending. | 8.3 |
| **Re-derivability holds only up to summary wording** | Merge is order-dependent. Same Entity set, same `source_entry_ids`, prose may differ. | 3.4 |
| **`100.64.0.0/10` is CGNAT, so this is a source-address filter, not an interface filter** | A LAN numbered inside 100.64/10 would pass. The port also remains bound broadly, so `ss -ltn` looks more open than policy allows. | 7.4 |
| **The `Host` allowlist is coupled to how the box is addressed** | A device or tailnet rename is a rare, delayed breakage — made self-diagnosing by the legible 403. | 9.3 |
| **`mcp-remote` is an untended dependency, pinned to a dead repo** | ~80% of it is OAuth machinery that never executes here. Its live risks: swallowed transport errors on server send (a request **hangs**), and an unconditional OAuth discovery probe that **crashes on Node 26**. Target Node 20/22 LTS. | 9.2 |
| **The server can never volunteer anything without a retrofit** | No server-initiated SSE. The door is closed knowingly. | 7.5 |
| **"Search degraded, capture fine" is reachable without noticing** | The deliberate consequence of `tome-mcp` being soft on Ollama — which is what protects capture. `warnings` is what announces it. | 7.3 |
| **The `warnings` channel is dead if the MCP server fails to start** | Surfaces only as a Claude connection error: obvious that something is wrong, not *what*. Desktop notifications are the deferred fix. | 10.3 |
| **Entries captured without device provenance can never gain it** | Raw is immutable; `source` is client type only. **Near-vacuous under the on-device deployment** — there is one device by construction — but it becomes live again the moment a second device captures, and by then the old rows are already silent. | 9.4 |
| **`source` is one bit with two values, and no client's reported version is usable** | Desktop announces `0.1.0` while the app is 1.24012.9, and `claude-ai` distinguishes Desktop from `claude-code` and from nothing else. Kept on the write-once asymmetry — unbackfillable, ~15 bytes — **not** because anything reads it yet. Nothing may ever be gated on a client's reported version. | 9.4 |
| **`source` arriving `NULL` is indistinguishable from a malformed `clientInfo`** | On the pinned `mcp` 1.x line neither is reachable from a client, so a `NULL` means Tome is misconfigured and is logged as a health signal. Off the pin, the two merge permanently — which is the reason there is no sentinel to merge them into. | 9.4 |
| **§3.8's fallback signal pairs across conversations on Claude Desktop** | Desktop's session is one *app launch*, so the "same session" predicate is bounded in time (§13.4) rather than made precise. The bound is applied at read time and re-cuttable; the signal was already recorded as noisy. | 3.8 |
| **An `ollama pull` between restarts leaves captures stamped with the old epoch** | Fixing it means an `/api/tags` call per capture, reintroducing a hard Ollama dependency on the one path made soft. Attribution, not forensics. | 3.2 |
| **Nothing can verify `context` quality; the residual is "the agent misjudged the trigger"** | No telemetry, no ground truth for a situational note. The tool description is not merely the chosen lever — it is the only one available, and **the absence of a check is a finding, not an oversight.** | 3.3 |
| **`context` is unreachable by search** | Payable only because extraction reads it, re-routing the referent to the primary tier. | 3.3 |
| **Migrate-then-restart leaves a few seconds of old code against new schema** | Additive changes do not notice; a destructive one briefly errors. Accepted rather than building a two-phase deploy for a single-user system whose operator is watching. | 7.6 |
| **`query_log` comes back empty from any restore** | It is a *sample*. Losing it costs 90 days that refill themselves. | 8.5 |
| **The query-log fallback signal is noisy** | Some fallbacks are *structural* (the entry is newer than the last run), not quality failures. Recorded as noisy rather than presented as clean. | 3.8 |
| **The leak tripwire needs a collision allowlist and cannot see retracted keys** | `project:tome` has key `tome`, which matches half of every line. `keys_suppressed` keeps the suppression visible. It is a tripwire, not a proof. | 7.12 |

### 13.3 Claims asserted without measurement

**Five of these are exactly what a judged set would settle (§10.4).** They are listed so nobody reads an assertion here as a finding.

| Claim | Status |
|---|---|
| **The tiering premise** — that entity-first retrieval is worth it. The mechanism is conceded to be *near-identical* to `search_raw`; what "primary" buys is **compression, not a better method**. | Argued, not measured |
| **The `natural_key` trigram membership branch helps at all** | "Entirely conjectural." Ablatable. |
| **"Fidelity is inversely proportional to merge depth"; Person/Project are "the telephone game by design"** | Nobody has checked whether a twelve-times-merged summary is still findable |
| **Exact-vs-HNSW recall on *this* corpus** | The "~1–5%" is a general figure, not Tome's |
| **The one-vs-two-embedder question** (`embeddinggemma`'s measured +0.069 on entity-shaped text) | Deferred; a path to evidence now exists from 90 days after deploy |
| **The ANN tripwire threshold, the `entities.summary` bound, the confidence threshold and the type-stickiness margin** | **Now have starting values (§13.4), none of them measured.** Exact-scan latency at 1024 dims was never measured; the other three were never specified by any ticket. Filled in so nothing blocks — every one is expected to move. |
| **`bge-m3` embed latency against the 5 s capture budget** | Never measured, and entity embedding added contention on the same `NUM_PARALLEL=1` instance |
| **Ollama's per-model runner queues** — the basis for "a capture embed doesn't queue behind a `qwen3` generation" | Reasoned from architecture, not measured |
| **Ollama's per-model pooling in GGUF conversion** | Unverified; `bge-m3` declares CLS, matching its card |
| **A merging extraction may be *two* `qwen3` calls, not one** (extract, then merge — resolution can only look up the key after extraction emits it) | Recorded as unverified. **This is the cost model that the ~18 s/entry and ~50 h figures rest on.** |
| **The `num_batch` behaviour is undocumented** and sits beside a `TODO` in Ollama's source | Re-probe after any upgrade |
| **The 1,000-char `context` cap and its 500-token allowance** | Explicitly labelled estimates, not calibration |
| **The backup space budget** | Arithmetic, not measurement — which is why the free-space guard exists rather than the table |
| **That `source`'s two values separate meaningfully different capture regimes** (Desktop's human-in-chat vs Claude Code's agent-driven) — the sole stated benefit of keeping the column | Expectation, not finding. The column is kept on the **unbackfillability** argument; this is what it is *hoped* to buy. Settleable from the query log and a judged set (§10.4) once rows exist. |
| **Claude Desktop's lack of native remote-MCP support** | Verified at decision time; **re-check before building** |
| **The `granite-embedding-english-r2` near-miss** | Not in the Ollama library at decision time; worth re-checking |

### 13.4 Starting-point values — chosen, not derived

> **Read this before using any number in this section.** The five values below are **educated guesses, filled in so that nothing blocks on an unmade decision.** None is a technical requirement, none was measured, and no analysis anywhere in this document depends on any of them being right. They exist so a builder is not forced to invent a number silently and so there is a single place to tune. **Expect to change all four**, and treat a change as configuration, not as overturning a decision.
>
> Each is stated at its use site with a pointer back here, so the caveat travels with the number.

| Value | Starting point | Reasoning — such as it is | Tune when |
|---|---|---|---|
| **`entities.summary` length bound** (§3.3) | **1,200 characters** | ~15% of a maximum-size capture (2,048 tokens ≈ 8,000 chars), so a summary stays visibly compressive even for a single-source Entity and dramatically so for a merged hub — which is the tiering premise's whole claim. Roughly 200 words: one solid paragraph. Sits beside `context`'s 1,000-char cap in the same idiom, and fits trivially in the merge prompt alongside a full-size entry. **Characters, not tokens**, so it enforces at write time with no tokenizer call. | Hub Entities read as truncated mid-thought, or summaries are padding out to the cap with filler. |
| **Global confidence threshold** (§5.7) | **0.7** | Below it, extraction records an `ambiguous` Type Suggestion instead of committing. LLM-emitted confidences are poorly calibrated and bunch high, so a conventional 0.5 would essentially never fire and the suggestion channel would go dead. 0.7 is high enough to catch genuine hesitation without flooding `review_schema`. | The `ambiguous` list is either empty for weeks or too long to review. `review_schema`'s histogram exists precisely to re-cut this line counterfactually first. |
| **Type-stickiness override margin** (§3.3) | **new confidence ≥ incumbent + 0.20, and ≥ the global threshold** | §3.3 says an existing type wins unless the new classification is "substantially higher" and never says what that means. Two conditions rather than one: a *margin* stops a 0.71-vs-0.70 flicker from re-typing an Entity every run, and the *floor* stops a low-confidence pair from re-typing on a technicality. | Entities are observed flip-flopping between types across runs (margin too small), or a genuinely mis-typed Entity will not correct itself (too large). |
| **Fallback-judgement pairing interval** (§3.8) | **`search_raw` within 300 s of a `search_entities` in the same session** | The signal wants "the caller looked at those scores and reached for the fallback", which is one or two LLM turns. Any bound at all is required only because Claude Desktop's session is one *app launch* (§3.8), so an unbounded predicate pairs across unrelated conversations; on both Claude Code grains the session is already tight enough that the interval rarely binds. 300 s is generous against a turn and short against a conversation boundary. **Applied at read time**, so it is re-cuttable against logged history without touching a row — which is why guessing it costs nothing. | The fallback list is full of pairs that read as unrelated on inspection (too long), or a fallback you remember making is absent (too short). |
| **ANN tripwire threshold** (§6.2) | **`search_entities` p95 > 150 ms, over a trailing 7 days, minimum 50 logged queries** | The companion trigger is ~30–50k rows, whichever comes first. §6.2's honest magnitudes put exact scan in the ~10–20 ms range, so 150 ms is ~10× headroom — it will not false-fire, but it fires *before* anything is perceptible inside an LLM turn, which is the point: it should be a warning, not a symptom. The **window and minimum sample** are the load-bearing part — without them a cold-cache outlier or a quiet week fires it. | It fires, or the row trigger arrives first and latency is still flat — in which case raise it rather than removing it. |

**None of these is in the epoch fingerprint.** They are operational tuning, not derivation rules: changing one must not invalidate the corpus. The confidence threshold is the closest call — it changes what extraction *records* — but §5.7 already establishes that a change is only meaningful paired with a re-run, which is the deliberate act, and §7.8's fingerprint reads named keys rather than hashing the file precisely so a tuning edit does not register as a rule change.

---

## 14. Surfaced while assembling

Four things came up in consolidation that no ticket settled. **None was a contradiction between closed tickets**, so none was resolved inside this document — each became a ticket. **All four are now closed and folded into the sections above.**

### Closed — the answers are in the sections above

| | Question | Answer | Now in |
|---|---|---|---|
| **[#28](https://github.com/markdlabrecque/tome/issues/28)** | Is `ollama pull` a fourth egress exception, and does `ollama.service` carry the deny? | **Named as the fourth exception; the unit is left unsealed.** Measured: the registry fetch happens in the **daemon** (a bare `POST /api/pull` reaches the registry with no CLI involved), and the unit carries no address policy at all — so the *act* is human-initiated but the *capability* is standing. A seal was measured working, live, with no restart, and declined on proportion: it drops packets rather than refusing the syscall, so a sealed pull **hangs at `pulling manifest`** with no diagnostic, which is a silent failure mode spent on an unobserved threat. §1.3 now states what *kernel-enforced* does and does not cover. Separately, the **loopback bind is pinned** into the Tome drop-in — an inbound gap the PRD had never specified. | §1.3, §7.7 |
| **[#29](https://github.com/markdlabrecque/tome/issues/29)** | Entity epoch stamps: one FK or two? | **Two** — `derivation_epoch_id` and `embedding_epoch_id`. Deduction, not a decision: the re-embed mode is *defined* as leaving Entities untouched, so one stamp would either never clear or restamp every Entity as freshly derived under rules that never touched extraction. #16's `embedding_model` is subsumed by the second, exactly as raw's was, because the epoch record carries the **digest** that a tag comparison cannot see. | §3.4, §4.1 |
| **[#30](https://github.com/markdlabrecque/tome/issues/30)** | `id` type, and must the two tables match? | **`bigint` for both.** uuid's real purposes — generation outside the database, unguessability — do not apply. Decided by #26's invariant C making the id the *only* identifier in a log line; the ordering/size leak is accepted as negligible beside an unencrypted disk. **Obligation recorded:** the `text_prefix` guard is now load-bearing, since an off-by-one lands on a real neighbouring entry. | §3.2, §3.4, §5.9 |
| **[#31](https://github.com/markdlabrecque/tome/issues/31)** | Where do Type Overrides and Type Suggestions live? | **Override: a column on `raw_entries`** (one per-entry value, history already in the log as a never-prunable class). **Suggestions: `enrichment_events` rows**, which #12 §7 already specified — the "derived" classification in #19/#20 is about migration cost, and the tension was manufactured. Retraction reach, pruning and wipe scope all follow automatically. | §3.2, §3.9 |

### Two smaller notes, **not ticketed** — recorded so they are not rediscovered

- **#12's DB-level enforcement sentence** reads *"`REVOKE UPDATE/DELETE` on `entities` … and route mutations through a function that writes the event."* The invariant restated across #18/#19/#23/#26 is unambiguously about **`enrichment_events` being append-only**, so §3.5 states it that way with the routing as its mechanism. Worth a glance from whoever writes the grants.
- **Numbers no ticket ever named** — the `entities.summary` length bound, the confidence threshold, the ANN tripwire's p95 value, and (found while filling the others in) the type-stickiness override margin, which §3.3 called "substantially higher" without ever saying how much. **All four now carry starting values in §13.4**, explicitly guesses rather than requirements, so that a builder tunes a stated number instead of inventing one silently.

---

## Sources

| § | Tickets |
|---|---|
| 1 Overview & scope | map, #2, #3, #4, #5, #6, #7, #8, #15, #17, #18, #19, #20, #22, #24, #26 |
| 2 Domain model | [CONTEXT.md](./CONTEXT.md), #10, #12, #14, #17 |
| 3 Data model | #10, #11, #12, #14, #16, #17, #18, #19, #20, #23, #25 |
| 4 Enrichment pipeline | #8, #12, #15, #16, #17, #18, #21, #24, #25 |
| 5 MCP tool surface | #10, #11, #12, #14, #16, #17, #18, #19, #21, #25, #26 |
| 6 Search & retrieval | #3, #16, #17, #18, #22, #23 |
| 7 Deployment & operations | #9, #13, #15, #17, #19, #20, #22, #24, #26 |
| 8 Durability, retention & privacy | #12, #18, #19, #20, #23, #26 |
| 9 Client setup | #5, #9, #13, #15 |
| 10 Out of scope & roadmap | map, #6, #13, #18, #19, #21, #22, #23, #25 |
| 11 Build obligations | all of the above |
| 12 Superseded decisions | #8, #9, #10, #11, #12, #14, #15, #16, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26 |
| 13 Limitations & unmeasured claims | #16, #18, #19, #22, #23, #24, #25 |

Research write-ups: [`research/local-llm-runtime-rocm.md`](./research/local-llm-runtime-rocm.md), [`research/mcp-remote-transport-tailscale.md`](./research/mcp-remote-transport-tailscale.md), [`research/embedding-model-short-english-retrieval.md`](./research/embedding-model-short-english-retrieval.md), [`research/oversize-enrichment-budget.md`](./research/oversize-enrichment-budget.md).
