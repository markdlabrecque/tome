# Tome

A personal memory-keeper: an immutable raw layer of manually captured entries, enriched into a structured layer of derived entities.

## Language

**Raw Entry**:
A single captured data point — text plus its embedding, plus capture metadata (timestamp, source client, situational context, embedding model version, enrichment state). The atomic unit of write; the sole source of truth for the entire store. Never written to directly by enrichment — only appended via the write path.
_Avoid_: Memory, note, record

**Enrichment**:
The batch process that classifies and derives structured Entities from Raw Entries. Periodic and normally incremental, but fully re-runnable from scratch on the raw layer at any time (e.g. after swapping the enrichment model). One Raw Entry may yield zero, one, or multiple Entities.
_Avoid_: Processing, indexing

**Entity**:
A structured, classified record derived from one or more Raw Entries by Enrichment. Read-only from the outside — never written to directly; always re-derivable from raw. Belongs to exactly one Entity Type, and is identified by exactly one Natural Key.
_Avoid_: Memory, record, fact (lowercase)

**Enrichment Run**:
A single execution of Enrichment, in two phases: embed every Raw Entry missing an embedding, then swap models once and classify/extract every pending Raw Entry. **Incremental** processes only pending entries; **full** wipes all Entities and reprocesses every Raw Entry from scratch. Only one Run may be in flight at a time.
_Avoid_: Job, batch, sync

**Natural Key**:
An Entity's identity handle — a canonical, normalized string emitted by Enrichment, unique within its Entity Type. Decides whether an extraction merges into an existing Entity or creates a new one. Deliberately coarse for Person and Project, so repeated mentions of the same subject collapse; deliberately specific (usually date-scoped) for episodic types, so distinct occurrences stay distinct.
_Avoid_: Id, slug (the id is the database's; the Natural Key is the domain's)

**Resolution Required**:
The state of a Raw Entry whose Enrichment failed for a reason retrying cannot fix — unparseable model output, oversized entry, irreducible type ambiguity — and which now awaits a human decision. Never retried automatically; the counterpart to a transient failure, which is retried silently and never surfaced. Every Raw Entry is therefore either progressing or Resolution Required; it is never quietly stuck. Resolved in exactly three ways: retried (after the cause is fixed), given a Type Override, or Tombstoned.
_Avoid_: Failed (a transient failure is not Resolution Required), error

**Type Override**:
A human-supplied classification recorded against a Raw Entry to settle an ambiguity Enrichment could not. Durable **input** to Enrichment, not derived output — so it survives a full Enrichment Run and the Entity remains fully derived. Applies as a tie-break only: it decides extractions whose confidence falls below threshold and leaves confidently-classified extractions from the same entry alone. Never a blanket relabel of the entry, since one Raw Entry may yield many Entities.
_Avoid_: Manual entity edit (there is no such thing — see Entity), forced type

**Tombstone**:
A Raw Entry whose content has been deliberately dropped — text, context and embedding nulled — while its identity, capture metadata and audit trail are retained. The outcome of deciding a Resolution Required entry can never be processed: too large for the enrichment model, or content the classifier cannot parse. Excluded from every Enrichment Run and from raw search by virtue of having no text. **Not a retraction**: it reaches only entries Enrichment could not process, never a mis-captured one, which enriches perfectly well.
_Avoid_: Delete (the row and its history remain), skip (that is the action; this is the result)

**Derivation Epoch**:
The span since the current full Enrichment Run began — the period over which the present Entity layer was derived under one set of rules (prompt, entity-type definitions, models). The default window for schema-governance review, because a full re-run regenerates every Type Suggestion, so counts spanning epochs double-count and make a fixed type boundary look unfixed.
_Avoid_: Generation, version

### Entity Types

**Person**:
Someone Mark knows or works with, and salient facts about them.

**Project**:
An ongoing effort (e.g. Tome itself) and its state or goals.

**Preference**:
A standing, recurring default — an opinion or convention Mark applies repeatedly (e.g. "prefers Postgres over DuckDB for personal projects").
_Avoid_: Decision (a Preference recurs; a Decision is a one-off choice)

**Decision**:
A specific one-off choice that was made, and why.
_Avoid_: Preference (see above)

**Fact**:
A standalone piece of knowledge that doesn't fit another Entity Type. Deliberately kept small and generic — a catch-all, not a default.

**Commitment**:
An open obligation or promise, tracked until fulfilled.
_Avoid_: Event (see below)

**Event**:
Something that happened, or is scheduled to happen, at a point in time — a record of occurrence, past or future, with no obligation-tracking.
_Avoid_: Commitment ("meeting with Alex Friday" is an Event; "promised to send Alex the report by Friday" is a Commitment)

**Type Suggestion**:
A note logged by Enrichment when classification strains, in one of two kinds. **No fit**: the Raw Entry is a poor/low-confidence fit for every existing Entity Type — records why it strained, plus a guessed name for a possible new type. **Ambiguous**: several Entity Types fit plausibly and confidence fell below threshold — records the competing types. Governance metadata, not itself an Entity Type: both kinds exist only to feed the periodic manual review of the entity-type schema, where a recurring Ambiguous pair is evidence that a type *boundary* is wrong rather than that a guess was.
_Avoid_: New entity, candidate type
