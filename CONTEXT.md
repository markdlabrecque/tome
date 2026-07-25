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
A structured, classified record derived from one or more Raw Entries by Enrichment. Read-only from the outside — never written to directly; always re-derivable from raw. Belongs to exactly one Entity Type.
_Avoid_: Memory, record, fact (lowercase)

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
A note logged by Enrichment when a Raw Entry is a poor/low-confidence fit for every existing Entity Type, referencing the entry, why it strained the fit, and a guessed name for a possible new type. Governance metadata, not itself an Entity Type — exists only to feed the periodic manual review of the entity-type schema.
_Avoid_: New entity, candidate type
