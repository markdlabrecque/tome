# Tome

A personal memory-keeper: an immutable raw layer of manually captured entries, enriched into a structured layer of derived entities.

## Language

**Raw Entry**:
A single captured data point — text plus its embedding, plus capture metadata (timestamp, source client, situational context, the Derivation Epoch its embedding was produced under, enrichment state). The atomic unit of write; the sole source of truth for the entire store. Never written to directly by enrichment — only appended via the write path. Immutable once written: it is never edited, and leaves only by Tombstone or Retraction. Bounded in size by what the embedding model can accept, since an entry that cannot be embedded is refused at capture rather than stored unsearchable.
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
The state of a Raw Entry whose Enrichment failed for a reason retrying cannot fix — unparseable model output, oversized entry, irreducible type ambiguity — and which now awaits a human decision. Never retried automatically; the counterpart to a transient failure, which is retried silently and never surfaced. Every Raw Entry is therefore either progressing or Resolution Required; it is never quietly stuck. Resolved in exactly three ways: retried (after the cause is fixed), given a Type Override, or Tombstoned — a Retraction also ends the state, but by removing the entry altogether rather than resolving it. An oversized entry reaches this state only when capture could not measure it (the embedding attempt having timed out), since an oversized entry is otherwise refused at capture.
_Avoid_: Failed (a transient failure is not Resolution Required), error

**Type Override**:
A human-supplied classification recorded against a Raw Entry to settle an ambiguity Enrichment could not. Durable **input** to Enrichment, not derived output — so it survives a full Enrichment Run and the Entity remains fully derived. Applies as a tie-break only: it decides extractions whose confidence falls below threshold and leaves confidently-classified extractions from the same entry alone. Never a blanket relabel of the entry, since one Raw Entry may yield many Entities.
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
The complete set of inputs an Entity was derived under — extraction prompt, entity-type definitions, enrichment model, embedding model, confidence threshold, and inference runtime version, each recorded by content so that a model tag moving under its own name is visible. Not a span of time: it is deduplicated by content, so an epoch begins only when a human deliberately changes the machine (a deploy, a config edit, a model pull) and never when data is captured. Its purpose is **attribution** — naming the rules behind a derived record, and detecting that today's rules differ — never reproduction, which is unreachable once a mutable model tag has moved and is unwanted anyway, since re-deriving under better rules should yield better Entities rather than identical ones. Recorded against every Entity, every audit row, and every embedding.
_Avoid_: Generation, version, span (the governance window for schema review is a *time* window — since the last full Enrichment Run began — and is a separate thing)

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
