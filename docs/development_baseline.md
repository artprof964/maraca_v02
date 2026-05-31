# Development Baseline

This repository now has a minimal Python source layout for Milestone 0. The `src/` tree mirrors the project partitions from `project_milestones.md` and `research/method_detail_AgentOrchHybrid.md`:

- `source_registry`
- `ingestion`
- `enrichment`
- `storage`
- `planning`
- `retrieval`
- `ranking`
- `validation`
- `synthesis`
- `feedback`
- `evaluation`
- `shared`

The `shared` package owns the first lightweight cross-partition contracts: `Partition`, `ErrorEnvelope`, `LogEvent`, and `new_correlation_id`. These are intentionally small so later milestone work can add richer source, document, chunk, planning, evidence, validation, answer, feedback, and evaluation records without pulling in heavy runtime dependencies early.

The Milestone 0 shared baseline also includes lightweight data records for early source registration, ingestion, document/chunk storage, retrieval planning, evidence ranking, validation, answers, feedback, and compact entity/relation metadata. These records use only the Python standard library and keep access/licensing, freshness, and reliability fields explicit so later partitions can enforce those concerns independently.

The logging/error policy baseline lives in `shared.policies`. It defines partition default fallback actions, required successful ingestion/query log checklists, degraded ingestion alternatives for vector and sparse indexes, optional query logs such as feedback capture, required error-type coverage by partition, and tiny helper constructors for start/success/error log events and error envelopes. This is policy metadata only; no log backend, persistence layer, retry runner, or service runtime is introduced in Milestone 0.

The environment profile baseline lives in `shared.environment`. It defines local, test, staging, and production profiles with conservative defaults for debug mode, placeholder storage roots and store URLs, model profile names, external access, graph enablement, strict access, retry limits, and retrieval/budget defaults. These profiles do not read environment variables or secrets yet; they are static metadata for later runtime wiring.

The initial stack selection lives in `shared.stack`. It records the preferred components from the project docs: LlamaIndex, Neo4j, Qdrant, LangGraph, a relational metadata store, an object store or filesystem for raw sources, and model services. This is declarative only; the packages are not runtime dependencies yet, no clients are constructed, and dependency-free mock selections are available for local/test contracts.

The deterministic source fixture baseline lives under `fixtures/`. `fixtures/fixture_catalog.json` describes the public document, external web page, CSV table, API-like JSON response, restricted source, stale source, malformed source, conflict pair, and graph relation fixture used to seed later ingestion, validation, access-control, and citation tests. `shared.fixtures` can load and validate the catalog with the Python standard library only; it does not parse or ingest fixture content yet.

Milestone 1 begins with a small in-memory `source_registry` behavior layer. It registers governed `SourceRecord` entries, preserves external links, stores access/license/reliability/freshness metadata as separate fields, updates allowed source statuses, evaluates source access, blocks unsafe license use for high-risk contexts, and emits structured shared log/error records for policy decisions.

Milestone 1 Part 2 adds a dependency-free `ingestion` behavior layer. It uses an in-memory job repository, creates correlated `IngestionJob` records, loads raw fixture/local source bytes into `RawArtifact` references, performs lightweight text normalization and metadata extraction, creates `DocumentRecord` entries that inherit source access/canonical metadata, and emits structured ingestion start, extraction, retry, completion, partial, and failure records. Chunking, vector indexing, keyword indexing, and durable raw artifact storage are intentionally deferred.

Milestone 1 Part 3 adds deterministic document chunking and a dependency-free in-memory storage baseline. `ingestion.split_document_into_chunks` creates `ChunkRecord` entries with stable IDs derived from document/source/checksum/index/offset/text inputs, preserves text offsets, carries heading/page metadata where available, and inherits access metadata from the document/source. `storage.InMemoryStorageRepository` stores raw artifacts, source/document/chunk metadata, ingestion job/log/error records, and emits commit/verification logs. The storage verifier checks for missing documents, missing chunks, and missing access policies, but vector indexes, sparse indexes, and durable database/object-store writes remain deferred to later milestone work.

Milestone 1 Part 4 adds dependency-free indexing primitives in `retrieval.indexing`. Valid chunks can be converted into deterministic hashed bag-of-terms embedding records and sparse keyword records that preserve exact identifiers and quoted phrases. `commit_vectors` and `commit_sparse_index` persist those records into the in-memory storage repository, update the corresponding `ChunkRecord.embedding_id` and `ChunkRecord.sparse_terms_id`, and emit `vectors_committed`/`sparse_index_committed` logs, or degraded logs when empty chunks are skipped. Lightweight vector and keyword search functions now return scored chunk candidates for retrieval smoke tests; hybrid merge, graph traversal, access filtering, and durable vector/search stores remain deferred.

Milestone 1 Part 5 adds dependency-free retrieval execution in `retrieval.execution`. Vector and keyword index hits are hydrated into `EvidenceCandidate` records with chunk text, source/document provenance, reliability, citation, license, and access metadata. Hybrid search now runs keyword plus vector retrieval, fails closed on missing access metadata, excludes unauthorized evidence before merge/ranking, deduplicates by source/chunk, normalizes scores across retrieval modes, and emits retrieval/access filter logs and access errors without returning restricted source text in denied candidates. Graph traversal, external lookup, reranking, and synthesis remain deferred.

Milestone 2 adds dependency-free planner orchestration. `planning` classifies queries, selects retrieval modes, sets bounded budgets, records planner traces, supports no-retrieval direct-response paths, and runs an in-memory planned query flow through retrieval, ranking, and synthesis while preserving request IDs and correlation IDs.

Milestone 3 adds deterministic graph-layer behavior. `enrichment` extracts fixture-friendly entity and relation records, `storage` persists graph records and reverse indexes, `retrieval.execution` can run graph traversal retrieval with provenance-rich evidence candidates, and planner execution tries graph retrieval before hybrid fallback for graph-selected plans.

Milestone 4 adds dependency-free validator behavior. `validation` checks evidence access, relevance, sufficiency, freshness, contradictions, citations, and claim-level support; `planning.run_planned_query` validates ranked evidence before synthesis; non-pass validation blocks evidence-backed synthesis claims; and passing answers re-check and store supported claim records.

Milestone 5 adds dependency-free quality and observability behavior. `evaluation` can build reviewed evaluation cases, compute batch metrics for retrieval recall, citation precision, unsupported claims, validator rejection, graph hits, reranker improvement, latency, and cost, and create dashboard-ready observability summaries from logs and errors. `feedback` can convert reviewed feedback into append-only improvement task records without mutating source reliability, access policy, or governance state. `storage` persists evaluation cases, evaluation reports, observability reports, and improvement tasks in memory for tests and early workflows.

Milestone 6 adds dependency-free production-readiness hardening. `storage.commit_storage_bundle_with_recovery` wraps multi-record commits with stable idempotency keys, retry logs, error envelopes, and snapshot rollback for partial writes. `source_registry` can monitor source refresh health, detect stale or never-checked scheduled sources, and deprecate stale active sources without mutating access policy fields. `docs/production_readiness.md` captures the readiness checklist, security review, recovery procedure, source refresh procedure, and local load-test guardrail.

Research artifacts are organized under `research/`, including the method detail, Mermaid flow, proposal notes, project summary, skill guide, top-methods brief, and paper database CSV/SQLite files.

Run the foundation checks with:

```powershell
python -m pytest
```

If `pytest` is not installed, use the standard library fallback:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```
