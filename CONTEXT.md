# Tome

A personal memory-keeper: an immutable raw layer of manually captured entries, enriched into a structured layer of derived entities.

## Language

**Raw Entry**:
A single captured data point — text plus its embedding (computed over the text alone), plus capture metadata (timestamp, source client, situational context, the Derivation Epoch its embedding was produced under, enrichment state). Its situational context is not inert metadata: it is agent-authored, holds only the referents the text leaves dangling and the setting of the capture, and Enrichment reads it as a *subordinated* input — it may resolve a referent or break a type tie the text leaves open, but never grounds an Entity on its own. Being outside the embedding, it is unreachable by raw search by design. The atomic unit of write; the sole source of truth for the entire store. Never written to directly by enrichment — only appended via the write path. Immutable once written: it is never edited, and leaves only by Tombstone or Retraction. Bounded in size **as a quality ceiling, not merely a capacity one** — the embedding model would accept roughly four times more than the limit allows, but extraction recall falls away well below that, so a generous ceiling would buy long-form capture at the cost of entries that enrich into a fraction of themselves while reporting success. The limit sits at the knee where recall begins to fall; an entry above it is refused at capture, and the same content captured as several entries reassembles through Natural Key merging.
_Avoid_: Memory, note, record

**Enrichment**:
The batch process that classifies and derives structured Entities from Raw Entries. Periodic and normally incremental, but fully re-runnable from scratch on the raw layer at any time (e.g. after swapping the enrichment model). One Raw Entry may yield zero, one, or multiple Entities.
_Avoid_: Processing, indexing

**Entity**:
A structured, classified record derived from one or more Raw Entries by Enrichment. Read-only from the outside — never written to directly; always re-derivable from raw. Belongs to exactly one Entity Type, and is identified by exactly one Natural Key.
_Avoid_: Memory, record, fact (lowercase)

**Enrichment Run**:
A single execution of Enrichment, in two phases divided by kind of work: embed every Raw Entry missing an embedding, then classify/extract every pending Raw Entry. Three modes. **Incremental** processes only pending entries; **full** wipes all Entities and reprocesses every Raw Entry from scratch; **re-embed** rewrites only the vectors whose Derivation Epoch is no longer current, leaving Entities and their text untouched — a distinct operation because a change of embedding model invalidates vectors without invalidating what was extracted, and costs minutes where a full Run costs hours. Only one Run may be in flight at a time.
_Avoid_: Job, batch, sync

**Natural Key**:
An Entity's identity handle — a canonical, normalized string emitted by Enrichment, unique within its Entity Type. Decides whether an extraction merges into an existing Entity or creates a new one. Deliberately coarse for Person and Project, so repeated mentions of the same subject collapse; deliberately specific (usually date-scoped) for episodic types, so distinct occurrences stay distinct.
_Avoid_: Id, slug (the id is the database's; the Natural Key is the domain's)

**Resolution Required**:
The state of a Raw Entry whose Enrichment failed for a reason retrying cannot fix — an entry exceeding the derivation budget, irreducible type ambiguity, or unparseable model output *whose retries are exhausted* — and which now awaits a human decision. Never retried automatically; the counterpart to a transient failure, which is retried silently and never surfaced. Unparseable model output is **not** itself non-retryable: it is measurably stochastic (identical input at temperature 0 yields a clean extraction about half the time), so it belongs to the transient class and reaches this state only after N retries fail. The reason code distinguishes exhausted retries from a genuine deterministic refusal, so triage never mistakes a bad run for an entry that can never be processed. Every Raw Entry is therefore either progressing or Resolution Required; it is never quietly stuck. Resolved in exactly three ways: retried (after the cause is fixed), given a Type Override, or Tombstoned — a Retraction also ends the state, but by removing the entry altogether rather than resolving it. An oversized entry reaches this state only when capture could not measure it (the embedding attempt having timed out), since an oversized entry is otherwise refused at capture.
_Avoid_: Failed (a transient failure is not Resolution Required), error

**Type Override**:
A human-supplied classification recorded against a Raw Entry to settle an ambiguity Enrichment could not. Durable **input** to Enrichment, not derived output — so it survives a full Enrichment Run and the Entity remains fully derived. Applies as a tie-break only: it decides extractions that emit Fact — the catch-all, and the measured destination of mis-typing — and leaves every other extraction from the same entry alone. Never a blanket relabel of the entry, since one Raw Entry may yield many Entities. *(This read "extractions whose confidence falls below threshold" until #35 deleted the threshold; the replacement is a starting point, not a measurement — PRD §5.6.)*
_Avoid_: Manual entity edit (there is no such thing — see Entity), forced type

**Tombstone**:
A Raw Entry whose content has been deliberately dropped — text, context and embedding nulled — while its identity, capture metadata and audit trail are retained. The outcome of deciding a Resolution Required entry can never be processed — in practice, content the classifier cannot parse, since an entry too large for the enrichment model can no longer be captured. Excluded from every Enrichment Run and from raw search by virtue of having no text. **Not a Retraction**: it reaches only entries Enrichment could not process, never a mis-captured one, which enriches perfectly well. A Tombstone still retains an excerpt of the dropped text in its audit row, so a Retraction is the escalation that removes even that.
_Avoid_: Delete (the row and its history remain), skip (that is the action; this is the result), Retraction (see below)

**Retraction**:
The deliberate, permanent removal of a Raw Entry and everything derived from it: the row deleted outright, its audit rows cascaded with it, the Entities it fed deleted, and those Entities' surviving source entries requeued so they re-derive from what remains. The answer to a mis-capture — wrong information, something private, a duplicate — which is exactly the case a Tombstone cannot reach, because such an entry enriches perfectly well. Reaches an entry in any state, including one already Tombstoned. Irreversible, and leaves no trace in the store beyond a content-free ledger entry outside the database, whose only purpose is to keep a restore from resurrecting what was retracted.
_Avoid_: Tombstone (that preserves identity and audit trail; this preserves nothing), delete, edit (raw is never edited)

**Retraction Ledger**:
The append-only, content-free record of every Retraction, held outside the database as a file so that restoring the database cannot restore it. Its sole purpose is to name the Raw Entries that must not exist; it is replayed against the store on every start, not only after a restore, so a Retraction cannot be undone by forgetting to replay it. Being content-free, it is safe to retain indefinitely and travels with the backups. Editing it is therefore the only way to reverse a Retraction: remove an entry's line, then restore. Its loss is silent — nothing else would notice, and the guarantee simply stops holding — which is why it belongs in the backup set rather than beside it.
_Avoid_: Audit log (that is `enrichment_events`, inside the database and cascaded away by Retraction), tombstone record, backup

**Derivation Epoch**:
The complete set of inputs an Entity was derived under — extraction prompt, entity-type definitions, enrichment model, embedding model, and inference runtime version, each recorded by content so that a model tag moving under its own name is visible. Not a span of time: it is deduplicated by content, so an epoch begins only when a human deliberately changes the machine (a deploy, a config edit, a model pull) and never when data is captured. Its purpose is **attribution** — naming the rules behind a derived record, and detecting that today's rules differ — never reproduction, which is unreachable once a mutable model tag has moved and is unwanted anyway, since re-deriving under better rules should yield better Entities rather than identical ones. Recorded against every Entity, every audit row, and every embedding.
_Avoid_: Generation, version, span (the governance window for schema review is a *time* window — since the last full Enrichment Run began — and is a separate thing)

### Entity Types

**Person**:
Someone Mark knows or works with, and salient facts about them.

**Project**:
An ongoing effort (e.g. Tome itself) and its state or goals.
_Avoid_: Event (a Project is an ongoing effort with a state; an Event is a single
occurrence — "the effort to consolidate three authentication paths" is a Project, "the
cutover happened over a weekend" is an Event)

**Preference**:
A standing, recurring default — an opinion or convention Mark applies repeatedly (e.g. "prefers Postgres over DuckDB for personal projects").
_Avoid_: Decision (a Preference recurs; a Decision is a one-off choice)

**Decision**:
A specific one-off choice that was made, and why.
_Avoid_: Preference (see above)

**Fact**:
A standalone piece of knowledge that doesn't fit another Entity Type. Deliberately kept small and generic — a catch-all, not a default. Choose Fact only after every other Entity Type has been ruled out.
_Avoid_: Event (an Event happened or will happen at a point in time; a Fact is a standing
state with no occurrence)

**Commitment**:
An open obligation or promise, tracked until fulfilled.
_Avoid_: Event (see below)

**Event**:
Something that happened, or is scheduled to happen, at a point in time — a record of occurrence, past or future, with no obligation-tracking. A completed occurrence remains an Event; it does not become a Fact once it is over.
_Avoid_: Commitment ("meeting with Alex Friday" is an Event; "promised to send Alex the report by Friday" is a Commitment)

**Schema Evidence**:
What the periodic manual review of the entity-type schema reads. Two kinds, neither of them a model self-report. **A recurring confusion pair** in the ground-truth corpus probe is evidence that a type *boundary* is wrong rather than that one guess was. **A recurring theme inside Fact** is evidence that a type is *missing* — Fact is the designed catch-all, so what accumulates there is the homeless-subject signal. Governance metadata, not itself an Entity Type.
_Avoid_: Type Suggestion (the model-emitted version — it was specified, measured, and removed; see PRD §3.9), new entity, candidate type
