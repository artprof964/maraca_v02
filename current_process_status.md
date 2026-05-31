# Current Process Status

Date: 2026-05-29
Workspace: `C:\Users\Fred_U\Documents\MA-RAG-CAG-Graph`

## Current Goal

Implement the project according to the milestone plan, using a worker/validator pair for each part and one repair loop when the validator finds actionable suggestions.

The current implementation loop has completed Milestone 13: LangGraph-compatible orchestration runtime boundary.

## Finished Work

### Project Read-Through

The project planning and research files were read and used as the implementation source of truth:

- `project_milestones.md`
- `project_tests.md`
- `research/method_detail_AgentOrchHybrid.md`
- `research/method_flow_AgentOrchHybrid.mmd`
- `research/skill_AgentOrchHybrid.md`
- `research/project_summary_outline_AgentOrchHybrid.md`
- `research/proposals.md`
- `research/top_10_methods.md`
- `research/papers_database.csv`
- `research/papers_database.sqlite`

The SQLite database was inspected and contains one `papers` table with 21 rows and fields matching the CSV research database.

### Recent Repository Updates

Status: complete.

Latest local commits:

- `45690cc` Move research artifacts into research folder.
- `40c733f` Complete milestone 4 validation support.
- `4668d74` Implement milestone 3 graph layer.

Repository organization update:

- Research artifacts now live under `research/`.
- `pyproject.toml` now uses `research/project_summary_outline_AgentOrchHybrid.md` as the package readme.
- Root-level references to moved research files were updated in the status and baseline docs.

### Milestone 0: Project Foundation

Status: complete.

Implemented:

- Python project baseline with `pyproject.toml`.
- Source package layout under `src/` for:
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
- Shared core contracts in `src/shared/contracts.py`:
  - `Partition`
  - `ErrorEnvelope`
  - `LogEvent`
  - `new_correlation_id`
  - error/log enums and serialization helpers
- Shared core records in `src/shared/records.py`:
  - source, ingestion, document, chunk, entity, relation, retrieval request, retrieval plan, evidence, ranked evidence, validation, claim, answer, and feedback records
- Shared policy defaults in `src/shared/policies.py`:
  - fallback actions by partition
  - successful ingestion/query log expectations
  - degraded vector/sparse alternatives
  - required error-type coverage
  - helper constructors for log/error records
- Static environment profiles in `src/shared/environment.py`:
  - local
  - test
  - staging
  - production
- Declarative stack selections in `src/shared/stack.py`:
  - LlamaIndex
  - Neo4j
  - Qdrant
  - LangGraph
  - metadata store
  - raw source store
  - model services
  - dependency-free fallback mocks
- Fixture catalog and synthetic source fixtures under `fixtures/`:
  - public document
  - external web page
  - internal CSV table
  - API-like JSON
  - restricted source
  - stale source
  - malformed source
  - conflict pair
  - graph relationship fixture
- Fixture loader and validator in `src/shared/fixtures.py`.
- Foundation documentation in `docs/development_baseline.md`.
- Tests for package layout, shared contracts, shared records, policies, environment profiles, stack selections, and fixtures.

Validator repairs completed:

- Added optional `pytest` test extra.
- Tightened package layout tests to require exact partition names.
- Added first-class `ClaimRecord`.
- Split optional feedback logs from always-required query logs.
- Added degraded vector/sparse log alternatives.
- Aligned environment serialization with shared serializer.
- Added staging behavior assertions.
- Added path traversal protection for fixtures.
- Added explicit internal fixture coverage.
- Added `SourceType.TABLE` so the catalog and shared enum are consistent.

### Milestone 1 Part 1: Source Registry and Access Policy

Status: complete.

Implemented in:

- `src/source_registry/registry.py`
- `src/source_registry/__init__.py`
- `tests/test_source_registry.py`

Implemented:

- In-memory source repository.
- `SourceRegistry`.
- Source registration preserving:
  - `external_link`
  - access metadata
  - license policy
  - reliability fields
  - freshness fields
  - status
- Source status updates.
- Access checks for public, internal, restricted, and confidential sources.
- Fail-closed behavior for missing access metadata.
- License/status/source policy decisions.
- Structured log/error output with shared `LogEvent` and `ErrorEnvelope`.

Validator repairs completed:

- Missing `access_policy_id` now resolves to unknown and fails closed.
- Internal access now requires `internal` scope or allow-list membership.

### Milestone 1 Part 2: Ingestion Jobs and Raw Source Loading

Status: complete.

Implemented in:

- `src/ingestion/__init__.py`
- `tests/test_ingestion.py`

Implemented:

- In-memory ingestion job repository.
- Correlated `start_ingestion_job`.
- `RawArtifact`.
- Safe raw fixture/local source loading.
- Lightweight normalization for:
  - Markdown
  - HTML
  - JSON
  - CSV
- `DocumentRecord` creation with inherited:
  - access policy
  - access level
  - canonical link
  - owner
  - checksum
  - freshness date
- `run_ingestion_job` orchestration.
- Retry logging and error envelopes.
- Completed, failed, and partial ingestion statuses.

Validator repairs completed:

- ISO datetime date extraction now handles values like `2026-05-20T09:00:00Z`.
- Added retry-exhaustion coverage.
- Added successful HTML, JSON, and CSV normalization coverage.
- Removed pytest-only temp-path usage from ingestion tests.

### Milestone 1 Part 3: Document/Chunk Records and Storage Baseline

Status: complete.

Implemented in:

- `src/ingestion/__init__.py`
- `src/storage/__init__.py`
- `tests/test_chunking_storage.py`

Implemented:

- Deterministic `split_document_into_chunks`.
- Stable `ChunkRecord` IDs.
- Chunk text offsets.
- Heading path metadata.
- Token counts.
- Page metadata where available.
- Access metadata inheritance.
- In-memory storage repository for:
  - raw artifacts
  - sources
  - documents
  - chunks
  - vector embeddings
  - sparse terms
  - ingestion jobs
  - logs
  - errors
- Commit helpers for raw artifacts, documents, chunks, and ingestion metadata.
- Storage verification.
- Access metadata verification.

Validator repairs completed:

- Chunk IDs no longer depend on generated `document_id`; equivalent fresh document records now produce stable chunk IDs.
- Storage verification now reports missing raw artifacts.
- Chunk/storage tests were converted to `unittest.TestCase`.

### Milestone 1 Part 4: Vector and Keyword Indexing

Status: complete.

Implemented in:

- `src/retrieval/indexing.py`
- `src/retrieval/__init__.py`
- `src/storage/__init__.py`
- `tests/test_indexing.py`

Implemented:

- Deterministic hashed bag-of-terms embedding records.
- Sparse keyword/phrase extraction.
- Exact identifier preservation.
- Phrase n-gram indexing.
- In-memory vector index.
- In-memory keyword index.
- Vector commit helper.
- Sparse index commit helper.
- Vector search returning scored chunk candidates.
- Keyword search returning exact candidates.
- Degraded behavior for empty chunks.

Validator repairs completed:

- `commit_vectors` and `commit_sparse_index` now preserve the other existing chunk index pointer.
- Added regression coverage for vector-then-sparse and sparse-then-vector commit order.
- Fixed the unquoted exact phrase test.
- Documented the `unittest` fallback command.

### Milestone 1 Part 5: Hybrid Retrieval, Access Filtering, and Merge

Status: complete.

Implemented in:

- `src/retrieval/execution.py`
- `src/retrieval/__init__.py`
- `tests/test_retrieval_execution.py`

Implemented:

- Vector retrieval hydration into `EvidenceCandidate`.
- Keyword retrieval hydration into `EvidenceCandidate`.
- Provenance metadata:
  - source ID
  - document ID
  - chunk ID
  - snippet
  - reliability
  - citation link
  - license constraints
  - access scope
- Access filtering before merge/ranking.
- Fail-closed behavior for missing source/document/chunk access metadata.
- Restricted/confidential/internal exclusion for unauthorized principals.
- Stricter document/chunk policy checks.
- Hybrid search orchestration.
- Score normalization by retrieval mode.
- Deduplication by source/chunk.
- Retrieval/access logs and access errors.

Validator repairs completed:

- Removed the hybrid multi-mode score bonus from merge so merge does not act as reranking.
- Added regression coverage proving lower-scored hybrid duplicates do not overtake stronger single-mode candidates.

### Milestone 1 Part 6: Basic Reranking

Status: complete.

Implemented in:

- `src/ranking/__init__.py`
- `tests/test_ranking.py`

Implemented:

- Dependency-free `select_ranked_evidence` ranking flow.
- Safe evidence deduplication by source/chunk, citation, or snippet fallback.
- Query relevance scoring with retrieval-score, source-reliability, and freshness modifiers.
- Configurable ranking weights.
- Source diversity selection with `max_per_source`.
- Optional external reranker integration.
- Fallback to normalized retrieval scores when the reranker fails.
- Ranking logs using the shared `LogEvent` conventions.
- Ranking errors using shared `ErrorEnvelope` conventions.

Validator repairs completed:

- Non-finite external reranker scores such as `NaN` are treated as `0.0`.
- Added regression coverage for invalid external reranker scores.

## Continued Finished Work

### Milestone 1 Part 7: Cited Synthesis

Status: complete.

Implemented in:

- `src/synthesis/__init__.py`
- `tests/test_synthesis.py`

Implemented:

- Dependency-free `generate_answer` synthesis flow.
- Answer generation only from approved `AccessDecision.ALLOWED` evidence.
- Claim record creation tied to supporting evidence IDs.
- Citation maps containing evidence IDs and citation links where available.
- Ranked evidence ordering support.
- Limitations for no evidence, no approved evidence, single evidence, missing links, stale evidence, low/unverified reliability, weak validation, and underspecified queries.
- Conservative uncertainty answer when cited evidence is insufficient.
- Synthesis logs for claim creation, citation attachment, and answer generation.
- Synthesis error envelope when no approved cited evidence is available.

Validator repairs completed:

- Public `create_claim_records` now skips denied/unapproved evidence when called directly.
- Citation attachment telemetry now emits a `citations_attached` log.

### Milestone 1 Part 8: Feedback Capture and Evaluation Trace Storage

Status: complete.

Implemented in:

- `src/feedback/__init__.py`
- `src/evaluation/__init__.py`
- `src/storage/__init__.py`
- `tests/test_feedback_evaluation.py`

Implemented:

- Append-only feedback capture.
- Feedback trace references for request, answer, claims, evidence, source, document, chunk, citation, and validation IDs.
- Failure category classification from rating, correction text, validation criteria, and evidence signals.
- Append-only evaluation trace records with feedback/failure references and scalar metrics.
- Shared-style feedback and evaluation logs.
- Retry-safe handling for feedback/evaluation write failures.
- In-memory storage persistence for feedback records, feedback trace references, and evaluation traces.
- Regression coverage proving feedback/evaluation do not automatically mutate source reliability or access policy.

Validator repairs completed:

- `InMemoryStorageRepository` now persists feedback records, feedback trace references, and evaluation traces instead of only receiving logs.
- Write failures preserve local feedback/trace records and emit retryable storage errors.

### Milestone 1 Final Validation and Smoke Flow

Status: complete.

Implemented in:

- `tests/test_milestone1_smoke.py`

Implemented:

- Run an end-to-end happy path:
  - register source
  - ingest source
  - chunk
  - store
  - index vector and keyword data
  - hybrid retrieval
  - rerank
  - synthesize cited answer
  - capture feedback
  - store evaluation trace
- Restricted source exclusion before ranking and synthesis.
- Malformed source partial/error path and failed extractor path.
- Logs across source registry, ingestion, storage, retrieval, ranking, synthesis, feedback, and evaluation partitions.
- Errors across source registry, ingestion, and retrieval partitions.

Validator repairs completed:

- Final smoke coverage now asserts access-approved ranking, ranked-to-synthesis evidence continuity, feedback trace references, claim IDs, citation links, and evaluation trace persistence.
- Restricted-source coverage now confirms restricted evidence is absent from retrieval, ranking, and synthesis.
- Removed stale status-file caveats for already completed reranking, synthesis, and feedback/evaluation behavior.

### Milestone 2 Part 1: Planner Baseline and Routing Plan Generation

Status: complete.

Implemented in:

- `src/planning/__init__.py`
- `tests/test_planning.py`

Implemented:

- Dependency-free planner request helper using existing `RetrievalRequest`.
- Query classification for exact, semantic, graph, multi-hop, fresh-data, high-risk, and mixed/uncertain queries.
- Conservative retrieval-mode selection:
  - exact to keyword
  - semantic to vector/hybrid
  - graph to graph/hybrid
  - uncertain to hybrid
  - direct/no-retrieval only for explicit or inline-content cases
- Retrieval budget generation for `top_k`, latency target, cost target, and bounded repair attempts.
- Shared `RetrievalPlan` creation with repair-loop fields and fallback actions.
- No-retrieval direct response decision metadata without answer synthesis.
- Planner trace records carrying plan reason, retrieval budget, selected modes, fallback actions, and repair bounds.
- Planner decision logs for:
  - `query_classified`
  - `retrieval_modes_selected`
  - `retrieval_budget_set`
  - `retrieval_plan_created`

Validator repairs completed:

- Source-backed queries beginning with greetings no longer route to `NO_RETRIEVAL`.
- Transform-style wording such as `Rewrite this policy from approved sources` no longer bypasses retrieval without inline content.
- Planner logs now include a `retrieval_plan_created` event carrying `plan_reason`.
- Planner trace now includes explicit repair-loop bounds.

### Milestone 2 Part 2: Planner-to-Retrieval Orchestration Smoke Flow

Status: complete.

Implemented in:

- `src/planning/__init__.py`
- `tests/test_planner_orchestration.py`

Implemented:

- `run_planned_query` orchestration helper connecting planner output to retrieval, ranking, and cited synthesis.
- Shared `PlannedQueryResult` carrying planning, retrieval, ranking, synthesis, executed modes, logs, and errors.
- Exact query execution through keyword-only retrieval with access filtering and retrieval completion logs.
- Semantic and uncertain/source-backed query execution through hybrid text retrieval.
- No-retrieval route that preserves planner trace and skips retrieval, ranking, and synthesis.
- Request ID continuity from planner request to retrieval evidence and generated answer.
- Planner, retrieval, ranking, and synthesis log coverage against the currently available shared successful-query expectations.
- Milestone 2 smoke tests for exact, semantic, hybrid fallback, no-retrieval, and log expectation behavior.

Validator repairs completed:

- Not yet needed; the initial local test gate passed.

### Milestone 3: Graph Layer

Status: complete.

Implemented in:

- `src/enrichment/__init__.py`
- `src/storage/__init__.py`
- `src/retrieval/execution.py`
- `src/retrieval/__init__.py`
- `src/planning/__init__.py`
- `tests/test_graph_layer.py`

Implemented:

- Deterministic dependency-free graph extraction for fixture-style relationship sentences.
- Entity extraction into shared `EntityRecord` records with stable IDs, aliases, confidence, and source provenance.
- Relation extraction into shared `RelationRecord` records for `depends_on`, `supports`, and `updates`, with evidence chunk IDs and confidence.
- Chunk-to-entity and chunk-to-relation links through graph quality flags and repository-side graph indexes.
- In-memory graph storage dictionaries and indexes for entities, relations, aliases, chunks, and entity adjacency.
- `commit_graph_records` and `verify_graph_storage` helpers with graph commit/verification logs.
- Graph traversal retrieval producing `EvidenceCandidate` records with:
  - `RetrievalMode.GRAPH`
  - entity IDs
  - relation IDs
  - source/document/chunk provenance
  - source reliability
  - citation links
  - access metadata
- Graph retrieval degraded-mode logs when no traversable graph is available.
- Graph/text merge compatibility so graph provenance survives evidence deduplication.
- Planner execution priority for graph plans so graph-selected requests execute graph traversal before hybrid fallback.
- End-to-end planned graph query flow through retrieval, ranking, and synthesis.

Validator repairs completed:

- Graph-selected planner routes now execute graph retrieval before hybrid retrieval.
- Added a full-flow graph orchestration test to lock planner-to-graph behavior.
- Tightened graph alias matching so one-character aliases do not match inside unrelated words.
- Added optional graph enrichment to the storage bundle path.
- Strengthened graph storage verification to check alias, chunk, relation, and reverse indexes.
- Added regression tests for unrelated graph evidence, graph-aware bundle commits, and corrupted graph indexes.

### Milestone 4: Validator Agent and Claim-Level Support

Status: complete.

Implemented in:

- `src/validation/__init__.py`
- `src/planning/__init__.py`
- `src/storage/__init__.py`
- `tests/test_validation.py`
- `tests/test_planner_orchestration.py`

Implemented:

- Dependency-free validator module with relevance, sufficiency, freshness, access, contradiction, and citation checks.
- `ValidationResult`, `EvidenceCheck`, and `ClaimSupportResult` result contracts.
- Claim-level support checks that annotate `ClaimRecord` support status, support type, confidence, and validator notes.
- Repair-action selection with bounded repair-loop handling.
- Validation logs and error envelopes for pass, repair-needed, and failure outcomes.
- In-memory validation and claim persistence hooks in `InMemoryStorageRepository`.
- Planner integration so ranked evidence is validated before synthesis.
- Non-pass validation blocks evidence-backed synthesis claims by passing no approved evidence to synthesis.
- Passing planned answers re-check generated claims and store supported claim records.
- Fresh-data phrasing now adds freshness validation even when the request did not explicitly set a freshness enum.

Validator repairs completed:

- Validation repair/failure status is now behaviorally enforced before synthesis, not only logged.
- Generated synthesis claims are rechecked and persisted on the passing orchestration path.
- Empty `required_validations=[]` stays explicit instead of falling back to default checks.
- Orchestration tests now require validation logs instead of skipping the validation partition.

### Milestone 5: Evaluation, Observability, and Optimization

Status: complete.

Implemented in:

- `src/evaluation/__init__.py`
- `src/feedback/__init__.py`
- `src/storage/__init__.py`
- `tests/test_evaluation_metrics.py`
- `tests/test_feedback_improvement.py`

Implemented:

- Dependency-free evaluation dataset case records for reviewed request/answer/evidence/validation/feedback context.
- Batch evaluation reports with retrieval recall, citation precision, unsupported claim rate, validator rejection rate, graph hit rate, and reranker improvement metrics.
- Dashboard-ready observability reports for partition log counts, event counts, error counts, latency, and cost.
- Feedback-to-improvement task records that group failure categories into append-only queued work without mutating source reliability, access policy, or governance state.
- In-memory persistence hooks for evaluation cases, evaluation reports, observability reports, and improvement tasks.
- Retryable storage error handling for evaluation reports, observability reports, and improvement tasks.

Validator repairs completed:

- Metric aggregation skips non-applicable reranker-improvement cases instead of treating missing baselines as regressions.
- Citation precision treats requests with no emitted citations as having no precision denominator, while unsupported-claim and validation metrics still track quality failures.
- Full test coverage now includes evaluation metrics, observability summaries, improvement task creation, deduplication, storage failure handling, and policy non-mutation.

### Milestone 6: Hardening and Production Readiness

Status: complete.

Implemented in:

- `src/storage/__init__.py`
- `src/source_registry/registry.py`
- `src/source_registry/__init__.py`
- `docs/production_readiness.md`
- `tests/test_milestone6_hardening.py`

Implemented:

- Retryable storage bundle commits with rollback snapshots for partial-write recovery.
- `StorageOperationError` and `StorageRecoveryResult` contracts for failure injection and recovery reporting.
- Structured storage retry, failure, and successful recovery telemetry.
- Source refresh monitoring for scheduled, event-driven, real-time, static, and manual sources.
- Duration parsing for `refresh_interval` and `freshness_sla` values such as `15m`, `12h`, `2d`, and `1w`.
- Stale-source detection for overdue, never-checked, blocked, and failed sources.
- Stale active source deprecation that preserves access policy and allowed principals.
- Production readiness checklist, recovery procedure, security review, source refresh procedure, and load-test report.
- Local load-style retrieval/ranking guardrail over 120 in-memory chunks.

Validator repairs completed:

- Initial focused Milestone 6 test gate passed.

### Milestone 7: Durable Backend Integration Baseline

Status: complete.

Implemented in:

- `src/storage/durable.py`
- `src/storage/__init__.py`
- `tests/test_durable_storage.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `DurableStorageRepository`, a dependency-free extension of `InMemoryStorageRepository`.
- JSON snapshot persistence for:
  - raw artifacts
  - sources
  - documents
  - chunks
  - entities
  - relations
  - ingestion jobs
- Append-only JSONL persistence for logs and error envelopes.
- Durable reload behavior that reconstructs shared dataclasses and enum/date/datetime fields from existing serializers.
- Recovery warnings for malformed snapshots and JSONL rows, while valid persisted records continue to load.
- Graph index rebuild on durable reload for entity aliases and relation reverse indexes.
- Regression coverage for round-trip persistence, append-only logs/errors, malformed persisted rows, and access/governance non-mutation.

Validator repairs completed:

- Focused Milestone 7 durable storage test gate passed.
- Durable rollback now restores local JSON/JSONL files as well as in-memory repository fields, preventing phantom persisted records after failed bundle commits.
- Status/test notes were refreshed after the final Milestone 7 repair pass.

### Milestone 8: External Backend Adapter Contracts

Status: complete.

Implemented in:

- `src/storage/adapters.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `BackendType` roles for metadata, raw source, vector, graph, and telemetry backends.
- `BackendCapability` manifests for read/write, snapshot, append-only telemetry, access filtering, vector search, graph traversal, health checks, and transactional write requirements.
- `BackendAdapterConfig`, `BackendHealthCheck`, and `BackendSelection` records with serializer-friendly dictionaries.
- `BackendAdapterRegistry` for deterministic registration, health recording, adapter selection, and missing-capability failure reporting.
- `create_local_backend_registry`, mapping the current JSON/JSONL durable store and in-memory indexes into future backend roles.
- `validate_backend_plan`, a small helper for checking multi-backend requirements before future external service clients are introduced.
- Redacted serialized adapter connection settings for secret-like keys while preserving environment-variable references.

Validator repairs completed:

- Focused Milestone 8 adapter contract test gate passed.

### Milestone 9: Executable Local Durable Backend Adapter

Status: complete.

Implemented in:

- `src/storage/adapters.py`
- `src/storage/durable.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `BackendRuntimeAdapter`, a dependency-free protocol for executable backend adapters.
- `BackendOperationResult`, a serializer-friendly operation outcome record.
- `LocalDurableStorageBackendAdapter`, the first executable backend adapter around `DurableStorageRepository`.
- Adapter health checks that verify local durable storage writability and report missing capabilities without exposing credentials.
- Adapter commit execution through the existing `commit_storage_bundle_with_recovery` rollback and retry boundary.
- Registry selection coverage for transactional durable write capabilities.
- Regression coverage proving adapter commits persist raw artifacts, sources, documents, chunks, logs, and access-governance fields.

Validator repairs completed:

- Focused Milestone 9 adapter runtime test gate passed.

### Milestone 10: Executable Vector Backend Adapter Baseline

Status: complete.

Implemented in:

- `src/storage/vector_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `InMemoryVectorBackendAdapter`, an executable runtime adapter around the existing dependency-free vector index.
- Vector backend health checks with capability reporting, latency, indexed chunk counts, and degraded missing-capability details.
- Adapter-driven vector indexing through the existing `commit_vectors` storage/indexing path.
- Adapter-driven vector search through the existing deterministic vector search path.
- `BackendOperationResult` output for vector indexing and search.
- Search result details that expose candidate IDs, scores, matched terms, and index record IDs without exposing chunk text.
- Regression coverage for vector runtime selection, indexing, search serialization, access-governance preservation, and empty-content indexing failure behavior.

Validator repairs completed:

- Focused Milestone 10 vector runtime adapter test gate passed.

### Milestone 11: Qdrant-Compatible Vector Backend Adapter

Status: complete.

Implemented in:

- `src/storage/qdrant_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `QdrantVectorBackendAdapter`, a dependency-optional service-backed vector adapter boundary with injected-client support.
- Qdrant health checks with capability reporting, collection point counts, unavailable-client errors, and secret-safe connection summaries.
- Adapter-driven point indexing from deterministic chunk embeddings into governed Qdrant payloads.
- Qdrant-style search support for both `search` and `query_points` client APIs.
- Search result details exposing chunk IDs, scores, matched terms, index IDs, source/document IDs, and access metadata without exposing chunk text.
- Regression coverage for Qdrant adapter selection, indexing, search serialization, unavailable-client behavior, no-text-leakage, and write-failure error envelopes.

Validator repairs completed:

- Focused Milestone 11 Qdrant-compatible adapter test gate passed.

### Milestone 12: Neo4j-Compatible Graph Backend Adapter

Status: complete.

Implemented in:

- `src/storage/neo4j_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `Neo4jGraphBackendAdapter`, a dependency-optional service-backed graph adapter boundary with injected-client support.
- Neo4j health checks with capability reporting, unavailable-client errors, and secret-safe connection summaries.
- Adapter-driven graph indexing from deterministic entity, relation, and chunk graph metadata into governed service payloads.
- Neo4j-style traversal support through `execute_query` clients.
- Traversal result details exposing chunk IDs, scores, entity IDs, relation IDs, source/document IDs, and access metadata without exposing chunk text.
- Regression coverage for Neo4j adapter selection, graph indexing, traversal serialization, unavailable-client behavior, no-text-leakage, and write-failure error envelopes.

Validator repairs completed:

- Focused Milestone 12 Neo4j-compatible adapter test gate passed.

### Milestone 13: LangGraph-Compatible Orchestration Runtime Boundary

Status: complete.

Implemented in:

- `src/planning/orchestration_runtime.py`
- `src/planning/__init__.py`
- `tests/test_planner_orchestration.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `LangGraphCompatibleOrchestrationAdapter`, a dependency-optional orchestration adapter for injected LangGraph-style apps.
- Orchestration runtime config, capability, health-check, and run-result records.
- Health checks for ready, degraded local fallback, missing capability, and unavailable runtime states.
- Adapter-driven planned-query execution through injected app `invoke` calls or the existing local `run_planned_query` fallback.
- App-failure fallback behavior that preserves the original error envelope while completing through local planned-query execution.
- Regression coverage for local fallback, injected app execution, app-failure fallback, unavailable disabled-fallback behavior, and serialized operation summaries.

Validator repairs completed:

- Focused Milestone 13 orchestration runtime test gate passed.

### Full Backend Environment and Short Keyword Manual

Status: complete.

Implemented in:

- `pyproject.toml`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `src/backend_app/__init__.py`
- `src/backend_app/health.py`
- `src/backend_app/manual.py`
- `scripts/setup_full_backend.ps1`
- `scripts/test_full_backend.ps1`
- `tests/test_backend_health.py`
- `tests/test_backend_manual.py`
- `tests/test_backend_setup_artifacts.py`
- `docs/local_environment.md`
- `docs/service_setup.md`
- `docs/short_keyword_manual.md`
- `project_tests.md`

Implemented:

- `backend`, `test`, and `full` package extras for reproducible local installs.
- Full optional backend software installed in `.venv`: Qdrant client, Neo4j driver, LangGraph, and LlamaIndex core.
- Docker Compose definitions for local Qdrant and Neo4j service containers.
- `.env.example` with local Qdrant, Neo4j, storage, and model-profile defaults.
- `rag-center-health`, a console command that checks optional client imports, Docker availability, environment variables, service adapter health, and LangGraph fallback status.
- `rag-center-smoke`, a console command that ingests the public fixture, commits storage records, builds vector and sparse keyword indexes, runs an exact keyword path, and prints a cited answer.
- `scripts/setup_full_backend.ps1`, a repeatable setup workflow for venv creation, full extra install, `.env` creation, optional Docker Desktop install request, optional service startup, health checks, and smoke run.
- `scripts/test_full_backend.ps1`, a repeatable validation workflow for dependency checks, health checks, smoke run, unittest discovery, and pytest.
- A short keyword manual documenting the smoke path and its proof points.
- Regression coverage for demo repository construction, short keyword manual execution, and CLI success output.
- Setup artifact coverage for console entry points, full/backend extras, `.env.example`, Docker Compose services, and setup/test script wiring.

Validated:

- Full backend imports passed.
- Optional backend imports passed.
- `pip check` reported no broken requirements.
- `rag-center-health` passed in regular mode with Docker/service warnings.
- `rag-center-health --strict-services --env-file .env.example` reported blocked Qdrant and Neo4j services because Docker is not installed on the current host.
- `rag-center-smoke` returned one keyword candidate, keyword execution mode, one citation, and a cited answer.
- Standard-library unittest discovery passed with 115 tests.
- Pytest passed with 205 tests.
- `scripts/test_full_backend.ps1` passed end to end.
- Docker Desktop is not available on the current host, so local Qdrant and Neo4j containers were not started.

## Unfinished Work

### Later Milestones

Status:

- Milestone 2: complete.
- Milestone 3: complete.
- Milestone 4: complete.
- Milestone 5: complete.
- Milestone 6: complete.
- Milestone 7: complete.
- Milestone 8: complete.
- Milestone 9: complete.
- Milestone 10: complete.
- Milestone 11: complete.
- Milestone 12: complete.
- Milestone 13: complete.

## Known Issues and Caveats

### Test Runner Availability

`python -m pytest` is available in the current environment. Standard-library unittest discovery is still kept as a dependency-light test gate:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Current status:

- Standard-library unittest discovery passes.
- Latest observed unittest result: 115 standard-library unittest tests passed.
- Latest observed pytest result: 205 tests passed.

### Runtime Dependencies and Optional Integrations

The base project still has no required runtime dependencies. The `full` extra installs optional integration libraries for local development and compatibility checks.

Installed optional integration libraries:

- LlamaIndex
- Neo4j
- Qdrant
- LangGraph

Deferred real services and credentials:

- model services
- durable metadata store
- durable raw source/object store

### In-Memory First With Local Durable Baseline

Current implementations remain dependency-free and in-memory first:

- source registry
- ingestion job repository
- raw artifact repository
- metadata storage
- vector index
- keyword index
- retrieval execution
- ranking
- validation
- synthesis
- feedback capture
- evaluation trace storage
- planner routing
- graph extraction, storage, and traversal retrieval

Milestone 7 adds a local durable baseline for storage records, logs, and errors through JSON snapshots and append-only JSONL files. External durable services are still future work.

Milestone 8 adds dependency-free adapter contracts so external metadata stores, raw source/object stores, vector databases, graph databases, and telemetry stores can be introduced behind explicit capability and health checks.

Milestone 9 adds the first executable adapter runtime by wrapping the local durable JSON/JSONL repository behind health-check, transactional-write selection, and recovery-aware commit semantics.

Milestone 10 adds an executable vector backend runtime around the current dependency-free vector index, preserving adapter health checks, operation results, storage-index commit behavior, and downstream access-filter ownership.

Milestone 11 adds a Qdrant-compatible vector backend adapter with injected-client support, governed point payloads, service search result serialization, and dependency-optional runtime behavior.

Milestone 12 adds a Neo4j-compatible graph backend adapter with injected-client support, governed graph payloads, service traversal result serialization, and dependency-optional runtime behavior.

Milestone 13 adds a LangGraph-compatible orchestration runtime boundary with injected-app support, local planned-query fallback, health checks, operation summaries, and dependency-optional behavior.

### No Real Embeddings Yet

Vector indexing uses deterministic hashed bag-of-terms vectors. This is suitable for unit tests and early behavior checks, but not for production retrieval quality.

### Planner Orchestration Has a Dependency-Optional Runtime Boundary

Milestone 2 provides planner classification, routing, budgets, trace records, and a dependency-free planner-to-retrieval smoke flow. Milestone 13 wraps that flow in a LangGraph-compatible adapter boundary, but it does not yet implement durable orchestration traces, explicit graph nodes, or production LangGraph workflows.

### Graph Layer Is Deterministic

The graph layer is implemented with deterministic fixture-friendly extraction and in-memory traversal. It is suitable for milestone tests and orchestration checks, but it does not yet use a production entity extraction model or durable graph database.

## Current Test Status

Latest unittest command run:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Latest unittest result:

```text
Ran 115 tests
OK
```

Latest pytest result:

```text
205 passed
```

`python -m pytest` is available in the current environment.

## Recommended Next Step

Use the Milestone 13 orchestration runtime boundary as the handoff point for adding richer repair-loop execution state, including explicit repair attempts, previous action traces, and optional external lookup nodes.
