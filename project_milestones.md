# Project Milestones: Agent-Orchestrated Hybrid Retrieval Center

## Purpose

This milestone plan turns the Agent-Orchestrated Hybrid Retrieval Center into a staged development project. Each milestone has scope, deliverables, exit criteria, risks, and required test gates. The plan is stack-neutral but assumes the preferred architecture: LlamaIndex, Neo4j, Qdrant, LangGraph, metadata store, raw source store, and model services.

## Milestone 0: Project Foundation

### Goal

Create the project baseline, architecture records, naming conventions, data contracts, and development workflow.

### Main Tasks

- Define repository layout for source registry, ingestion, enrichment, storage, planning, retrieval, ranking, validation, synthesis, feedback, and evaluation.
- Finalize core data fields from `research/method_detail_AgentOrchHybrid.md`.
- Define shared correlation_id, error envelope, and log event format.
- Define environment profiles: local, test, staging, production.
- Select initial stack components and fallback mocks.
- Create sample source fixtures: document, web page, table, API-like JSON, and restricted source.

### Deliverables

- Architecture baseline.
- Data contract baseline.
- Test fixture catalog.
- Logging and error contract.
- Development environment checklist.

### Exit Criteria

- Every partition has an owner, contract, and test plan.
- Shared IDs and trace fields are consistent across records.
- Sample fixtures cover public, internal, restricted, stale, and malformed sources.

### Test Gate

- Contract validation tests pass.
- Fixture loading tests pass.
- Logging schema tests pass.

## Milestone 1: Source Registry and Hybrid Text Retrieval

### Goal

Build the minimum useful retrieval center with source registration, ingestion, chunking, vector retrieval, keyword retrieval, reranking, cited synthesis, and feedback capture.

### Main Tasks

- Implement source registry with access policy, external_link, reliability, freshness, and status fields.
- Implement ingestion jobs with retry/error handling and partition logs.
- Implement document and chunk records with access metadata and stable IDs.
- Implement raw source storage and metadata storage.
- Implement vector indexing.
- Implement keyword or sparse indexing.
- Implement hybrid keyword-vector retrieval.
- Implement basic reranking.
- Implement cited synthesis from approved evidence.
- Implement feedback capture and evaluation trace storage.

### Deliverables

- Source registry module.
- Ingestion module.
- Chunking module.
- Vector retrieval module.
- Keyword retrieval module.
- Hybrid merge module.
- Basic reranker module.
- Basic synthesis module.
- Feedback capture module.

### Exit Criteria

- Public and internal sources can be registered, ingested, chunked, indexed, and retrieved.
- Restricted sources are excluded when access scope does not allow them.
- Answers include citation links to evidence.
- Every request and ingestion job has partition logs.
- Ingestion failures produce error envelopes.

### Test Gate

- Unit tests for source registry, ingestion, chunking, vector retrieval, keyword retrieval, merge, reranking, synthesis, feedback.
- Access-control tests pass.
- Ingestion try/error tests pass.
- End-to-end happy path test passes.

## Milestone 2: Planner, Routing, and Traceability

### Goal

Add planner-driven routing with explicit retrieval plans, budgets, no-retrieval path, and traceable decisions.

### Main Tasks

- Implement retrieval request records.
- Implement planner query classification.
- Implement retrieval plan generation.
- Implement no-retrieval direct response path.
- Implement retrieval budgets: top-k, latency target, cost target, max repair attempts.
- Implement planner logs and decision traces.
- Add conservative fallback behavior for uncertain classifications.
- Add repair-loop state fields.

### Deliverables

- Planner module.
- Retrieval plan schema.
- Direct response record.
- Planner trace records.
- Repair-loop controls.

### Exit Criteria

- Planner can route exact queries to keyword retrieval.
- Planner can route semantic queries to vector or hybrid retrieval.
- Planner can route source-backed general questions to hybrid retrieval.
- Planner can select no-retrieval for formatting or conversational tasks.
- Planner logs plan_reason and selected modes.
- Repair-loop state is bounded and observable.

### Test Gate

- Planner unit tests pass.
- No-retrieval path tests pass.
- Routing decision tests pass.
- Repair-limit tests pass.
- Planner logging tests pass.

## Milestone 3: Graph Layer

### Goal

Add optional graph retrieval for entity, relationship, provenance, and multi-hop questions.

### Main Tasks

- Implement entity extraction.
- Implement relation extraction.
- Implement graph node and edge records.
- Implement chunk-to-entity and chunk-to-relation links.
- Implement graph storage.
- Implement entity resolution.
- Implement graph traversal retrieval.
- Implement graph-plus-text hybrid retrieval.
- Add graph quality flags and graph logs.

### Deliverables

- Entity extraction module.
- Relation extraction module.
- Graph storage module.
- Entity resolution module.
- Graph traversal retrieval module.
- Graph-text merge path.

### Exit Criteria

- Entity records link back to supporting chunks.
- Relation records include evidence_chunk_ids and confidence.
- Graph retrieval can answer relationship questions with source evidence.
- Graph retrieval is optional and does not block Phase 1 text retrieval.
- Graph extraction failures degrade gracefully.

### Test Gate

- Entity extraction unit tests pass.
- Relation extraction unit tests pass.
- Graph commit tests pass.
- Entity resolution tests pass.
- Graph traversal tests pass.
- Graph degraded-mode tests pass.

## Milestone 4: Validator Agent and Claim-Level Support

Status: complete. Completed in commit `40c733f` on 2026-05-22.

Completion notes:

- Validator module, repair action handling, validation logs, in-memory validation persistence, and claim-level support checks are implemented.
- Planned query execution validates ranked evidence before synthesis.
- Non-pass validation blocks evidence-backed synthesis claims.
- Passing answers re-check and store supported claim records.
- Exit criteria are covered for access rejection, stale evidence flagging, contradiction repair/failure handling, claim-level evidence links, and bounded repair attempts.
- Milestone 5 has since been completed as the evaluation and observability milestone.

### Goal

Add validator review before synthesis, including relevance, sufficiency, freshness, access, contradiction, and claim-level citation support.

### Main Tasks

- Implement validation records.
- Implement access validation.
- Implement relevance validation.
- Implement sufficiency validation.
- Implement freshness validation.
- Implement contradiction detection.
- Implement claim records.
- Implement claim-level support checks.
- Implement validator repair actions.
- Integrate bounded repair loop.

### Deliverables

- Validator module.
- Claim record module.
- Validation policy configuration.
- Repair action handler.
- Validator logs.

### Exit Criteria

- Unsupported evidence is rejected before synthesis.
- Restricted evidence cannot pass validation for unauthorized users.
- Stale evidence is flagged according to freshness policy.
- Contradictions trigger repair, uncertainty, or conflict disclosure.
- Important claims link to exact evidence spans where available.
- Repair loops stop at max_repair_attempts.

### Test Gate

- Validator unit tests pass.
- Claim-level support tests pass.
- Access validation tests pass.
- Freshness validation tests pass.
- Contradiction tests pass.
- Repair-loop integration tests pass.

## Milestone 5: Evaluation, Observability, and Optimization

Status: complete. Completed on 2026-05-22.

Completion notes:

- Evaluation dataset case records, batch reports, and in-memory persistence hooks are implemented.
- Batch metrics cover retrieval recall, citation precision, unsupported claim rate, validator rejection rate, graph hit rate, reranker improvement, latency, and cost.
- Observability reports summarize partition logs, event counts, error counts, latency, and cost for dashboard-ready consumption.
- Feedback can create append-only improvement tasks by failure category without automatic policy, access, or reliability mutation.
- Regression coverage protects metrics, observability summaries, improvement task creation, storage failure paths, and governance non-mutation.
- Milestone 6 has since been completed as the production-readiness hardening milestone.

### Goal

Build continuous quality measurement and operational visibility.

### Main Tasks

- Implement evaluation dataset format.
- Implement retrieval recall metrics.
- Implement citation precision metrics.
- Implement unsupported claim rate.
- Implement validator rejection rate.
- Implement graph hit rate.
- Implement reranker improvement measurement.
- Implement latency and cost metrics.
- Implement dashboard-ready logs and reports.
- Implement feedback-to-improvement workflow.
- Add regression test sets.

### Deliverables

- Evaluation store.
- Metric definitions.
- Regression test suite.
- Observability reports.
- Improvement task workflow.

### Exit Criteria

- System can separate retrieval failures from synthesis failures.
- Evaluation metrics are produced per request batch.
- Regression tests protect core retrieval behavior.
- Feedback creates improvement tasks, not automatic policy changes.
- Cost and latency are visible per partition.

### Test Gate

- Evaluation metric tests pass.
- Observability tests pass.
- Regression suite passes.
- Feedback workflow tests pass.

## Milestone 6: Hardening and Production Readiness

Status: complete. Completed on 2026-05-22.

Completion notes:

- Storage bundle commits now support retryable idempotent recovery with rollback of partial writes and structured storage retry/failure telemetry.
- Source refresh monitoring detects due, stale, never-checked, blocked, and failed sources with interval parsing for scheduled/real-time policies.
- Stale active sources can be deprecated without mutating access policy or allowed principals.
- Production readiness, security review, source refresh, recovery, and load-test guidance are documented in `docs/production_readiness.md`.
- Focused regression coverage protects failure injection, rollback recovery, source staleness checks, governance non-mutation, and local retrieval/ranking load behavior.

### Goal

Harden access control, error handling, scalability, source refresh, and recovery behavior.

### Main Tasks

- Add idempotent ingestion and storage retries.
- Add source refresh monitoring.
- Add stale-source detection.
- Add rollback or partial-commit handling.
- Add load tests for retrieval and ranking.
- Add failure injection tests.
- Add security review for access and license enforcement.
- Add backup and recovery procedures.

### Deliverables

- Production readiness checklist.
- Load test report.
- Security and access review.
- Recovery runbook.
- Source refresh monitor.

### Exit Criteria

- Restricted source leakage tests pass.
- Failure injection tests pass.
- Storage recovery procedures are documented.
- Refresh and staleness checks work.
- Performance meets agreed latency and cost targets.

### Test Gate

- Security tests pass.
- Load tests pass.
- Failure injection tests pass.
- Recovery tests pass.

## Milestone 7: Durable Backend Integration Baseline

Status: complete. Completed on 2026-05-22.

Completion notes:

- Added a dependency-free durable storage repository that preserves the in-memory repository API while persisting core storage records to JSON snapshots.
- Logs and error envelopes now have an append-only JSONL persistence path for durable telemetry history.
- Recovery skips malformed persisted records or JSONL rows and records warnings without blocking valid persisted state.
- Failed durable bundle commits restore local JSON/JSONL files as well as in-memory fields, preventing partial records from reappearing after reload.
- Persistence round trips preserve access policy IDs, allowed principals, and other governance fields without mutation.
- Scope remains conservative: this milestone introduces local durable files only, not external metadata stores, object stores, vector databases, or graph databases.

### Goal

Add a conservative durable persistence baseline that complements existing in-memory repositories without introducing external services.

### Main Tasks

- Implement JSON snapshot persistence for core storage records.
- Implement append-only JSONL persistence for logs and errors.
- Preserve existing in-memory save and commit helper behavior.
- Add recovery behavior for malformed persisted records.
- Protect access and governance fields during persistence round trips.
- Keep the implementation dependency-free.

### Deliverables

- Durable storage repository extension.
- JSON snapshot format for raw artifacts, sources, documents, chunks, graph records, and ingestion jobs.
- JSONL format for logs and error envelopes.
- Durable storage regression tests.
- Milestone and process-status documentation updates.

### Exit Criteria

- Core records round trip through durable persistence.
- Logs and errors append without compacting prior telemetry rows.
- Malformed persisted records are skipped while valid records recover.
- Access policy and allowed-principal fields are unchanged by persistence.
- No runtime dependencies are introduced.

### Test Gate

- Durable storage round-trip tests pass.
- Append-only log/error tests pass.
- Malformed recovery tests pass.
- Governance non-mutation tests pass.

## Milestone 8: External Backend Adapter Contracts

Status: complete. Completed on 2026-05-27.

Completion notes:

- Added dependency-free backend adapter contracts for metadata, raw source, vector, graph, and telemetry backends.
- Added adapter capability manifests, health-check records, deterministic adapter selection, and governed error envelopes when required capabilities are unavailable.
- Added a local backend registry that maps the current JSON/JSONL and in-memory indexes into future external-backend roles without introducing runtime dependencies.
- Added credential redaction for serialized adapter connection settings while preserving environment-variable references.
- Added tests for baseline plan validation, missing-capability failures, health-based fallback selection, and serialized adapter summaries.

### Goal

Define the external backend integration boundary before adding real service clients.

### Main Tasks

- Define backend types for metadata, raw source/object, vector, graph, and telemetry stores.
- Define adapter capability manifests and health status records.
- Implement deterministic selection for adapters that satisfy required capabilities.
- Surface governed failures when required capabilities are missing or adapters are unavailable.
- Provide a local baseline registry for the existing dependency-free storage path.
- Keep the implementation dependency-free and free of service credentials.

### Deliverables

- Backend adapter contract module.
- Local baseline backend registry.
- Adapter plan validation helper.
- Backend adapter regression tests.
- Milestone and process-status documentation updates.

### Exit Criteria

- Current local storage/indexing roles can be represented as adapter manifests.
- Backend plans can require capabilities such as read, write, snapshot, append-only, vector search, graph traversal, and access filtering.
- Missing capabilities produce structured storage errors instead of silent fallback.
- Unavailable primary adapters do not block selection of a healthy fallback candidate.
- Adapter summaries serialize without mutating connection settings or adding runtime dependencies.

### Test Gate

- Backend adapter selection tests pass.
- Missing capability tests pass.
- Health fallback tests pass.
- Adapter serialization tests pass.

## Milestone 9: Executable Local Durable Backend Adapter

Status: complete. Completed on 2026-05-27.

Completion notes:

- Added a dependency-free executable adapter protocol and operation result record on top of the Milestone 8 adapter manifests.
- Added `LocalDurableStorageBackendAdapter`, wrapping the JSON/JSONL durable repository with health checks and recovery-aware storage bundle commits.
- Health checks verify local durable storage writability, report latency, and surface missing capabilities without exposing credentials.
- Adapter commits reuse the existing rollback and retry semantics from `commit_storage_bundle_with_recovery`.
- Regression coverage proves transactional adapter selection and persisted governed records through adapter execution.

### Goal

Turn the adapter contract boundary into the first executable backend runtime without introducing external service dependencies.

### Main Tasks

- Define an executable backend adapter protocol.
- Define a serializer-friendly backend operation result.
- Implement a local durable backend adapter around the existing JSON/JSONL repository.
- Expose adapter health checks for required capabilities.
- Execute storage bundle commits through adapter runtime semantics.
- Preserve access metadata and rollback behavior during adapter-driven writes.

### Deliverables

- Backend runtime adapter protocol.
- Backend operation result record.
- Local durable backend adapter.
- Adapter runtime regression tests.
- Milestone and process-status documentation updates.

### Exit Criteria

- The local durable adapter can be registered and selected by required capabilities.
- Health checks report ready/degraded/unavailable status with checked capabilities.
- Adapter-driven commits persist raw artifacts, metadata, chunks, logs, and errors.
- Access policy and allowed-principal fields remain unchanged.
- No runtime dependencies are introduced.

### Test Gate

- Adapter runtime health tests pass.
- Transactional capability selection tests pass.
- Adapter-driven durable commit tests pass.
- Governance persistence tests pass.

## Milestone 10: Executable Vector Backend Adapter Baseline

Status: complete. Completed on 2026-05-27.

Completion notes:

- Added `InMemoryVectorBackendAdapter`, an executable vector runtime adapter around the current dependency-free vector index.
- Health checks report vector backend readiness, checked capabilities, indexed chunk counts, and missing-capability degradation.
- Vector indexing executes through the existing `commit_vectors` path so chunk embedding links and storage logs remain consistent.
- Vector search returns governed hit metadata such as chunk IDs, scores, matched terms, and index record IDs without exposing chunk text or bypassing the retrieval access filter.
- Regression coverage proves vector adapter selection, indexing, search serialization, governance field preservation, and empty-index failure reporting.

### Goal

Add the first executable vector backend runtime behind the Milestone 8 adapter contracts and Milestone 9 operation-result shape.

### Main Tasks

- Implement an executable vector adapter around the local vector index.
- Expose health checks for read, write, vector search, access-filter, and health-check capabilities.
- Execute vector indexing through the existing storage/indexing boundary.
- Execute vector search through the existing deterministic vector search boundary.
- Return structured operation results without leaking document text.
- Preserve access metadata and downstream access-filter ownership.

### Deliverables

- In-memory vector backend adapter.
- Vector indexing operation result.
- Vector search operation result.
- Backend adapter regression tests.
- Milestone and process-status documentation updates.

### Exit Criteria

- The vector adapter can be registered and selected by required vector capabilities.
- Health checks report ready or degraded status with checked capabilities.
- Adapter-driven indexing persists embeddings and updates chunk embedding IDs.
- Adapter search returns candidate metadata suitable for retrieval hydration and access filtering.
- Access policy and allowed-principal fields remain unchanged.
- No runtime dependencies are introduced.

### Test Gate

- Vector adapter health tests pass.
- Vector capability selection tests pass.
- Adapter-driven indexing tests pass.
- Adapter search serialization tests pass.
- Empty-content indexing failure tests pass.

## Milestone 11: Qdrant-Compatible Vector Backend Adapter

Status: complete. Completed on 2026-05-27.

Completion notes:

- Added `QdrantVectorBackendAdapter`, a dependency-optional adapter for injected Qdrant-compatible clients.
- Health checks report Qdrant reachability, collection point counts, missing capabilities, and governed unavailable-client errors without exposing API keys.
- Vector indexing converts chunk embeddings into Qdrant point payloads that preserve source, document, access policy, allowed principals, embedding IDs, and searchable terms while excluding chunk text.
- Vector search supports Qdrant-style `search` and `query_points` clients and returns candidate metadata suitable for downstream hydration and access filtering.
- Regression coverage proves Qdrant adapter selection, offline unavailable-client behavior, governed payload indexing/search, no text leakage, and write-failure error envelopes.

### Goal

Introduce the first service-backed vector adapter boundary while keeping local development dependency-free and testable without a running Qdrant service.

### Main Tasks

- Implement a Qdrant-compatible vector adapter with injected-client support.
- Preserve the existing backend capability, health-check, fallback, and operation-result contracts.
- Convert deterministic local embeddings into service point upserts.
- Store only governed payload metadata in vector backend search results.
- Surface unavailable clients and write failures through storage error envelopes.
- Keep Qdrant as an optional runtime integration, not a required project dependency.

### Deliverables

- Qdrant-compatible vector backend adapter.
- Qdrant health, indexing, and search operation results.
- Offline fake-client regression coverage.
- Milestone and process-status documentation updates.

### Exit Criteria

- The Qdrant adapter can be registered and selected by required vector capabilities.
- Health checks report ready, degraded, or unavailable status without leaking secrets.
- Adapter-driven indexing emits service points with governed metadata and no chunk text.
- Adapter search returns candidate metadata suitable for retrieval hydration and access filtering.
- Write failures are represented as governed backend operation errors.
- No required runtime dependencies are introduced.

### Test Gate

- Qdrant adapter health tests pass.
- Qdrant capability selection tests pass.
- Qdrant indexing/search serialization tests pass.
- Secret redaction and no-text-leakage tests pass.
- Qdrant write-failure tests pass.

## Milestone 12: Neo4j-Compatible Graph Backend Adapter

Status: complete. Completed on 2026-05-27.

Completion notes:

- Added `Neo4jGraphBackendAdapter`, a dependency-optional adapter for injected Neo4j-compatible clients.
- Health checks report graph backend reachability, missing capabilities, and unavailable-client errors without exposing credentials.
- Graph indexing converts entity, relation, and chunk graph metadata into governed service payloads while excluding chunk text.
- Graph traversal supports Neo4j-style `execute_query` clients and returns candidate metadata suitable for downstream hydration and access filtering.
- Regression coverage proves Neo4j adapter selection, offline unavailable-client behavior, governed graph indexing/traversal, no text leakage, and write-failure error envelopes.

### Goal

Introduce the first service-backed graph adapter boundary while keeping local development dependency-free and testable without a running Neo4j service.

### Main Tasks

- Implement a Neo4j-compatible graph adapter with injected-client support.
- Preserve the existing backend capability, health-check, fallback, and operation-result contracts.
- Convert deterministic local graph records into service graph payloads.
- Store only governed payload metadata in graph backend traversal results.
- Surface unavailable clients and write failures through storage error envelopes.
- Keep Neo4j as an optional runtime integration, not a required project dependency.

### Deliverables

- Neo4j-compatible graph backend adapter.
- Neo4j health, graph indexing, and traversal operation results.
- Offline fake-client regression coverage.
- Milestone and process-status documentation updates.

### Exit Criteria

- The Neo4j adapter can be registered and selected by required graph capabilities.
- Health checks report ready, degraded, or unavailable status without leaking secrets.
- Adapter-driven indexing emits service graph payloads with governed metadata and no chunk text.
- Adapter traversal returns candidate metadata suitable for retrieval hydration and access filtering.
- Write failures are represented as governed backend operation errors.
- No required runtime dependencies are introduced.

### Test Gate

- Neo4j adapter health tests pass.
- Neo4j capability selection tests pass.
- Neo4j indexing/traversal serialization tests pass.
- Secret redaction and no-text-leakage tests pass.
- Neo4j write-failure tests pass.

## Milestone 13: LangGraph-Compatible Orchestration Runtime Boundary

Status: complete. Completed on 2026-05-29.

Completion notes:

- Added `LangGraphCompatibleOrchestrationAdapter`, a dependency-optional orchestration adapter for injected LangGraph-style apps.
- Added orchestration runtime config, capability, health-check, and run-result records.
- Health checks report ready, degraded fallback, or unavailable states without requiring `langgraph` as a runtime dependency.
- Adapter-driven query execution supports injected app `invoke` calls and local planned-query fallback.
- Orchestration run results summarize selected modes, executed modes, validation status, log counts, errors, and output references without serializing evidence text.
- Regression coverage proves local fallback execution, injected app execution, app-failure fallback, and unavailable behavior when fallback is disabled.

### Goal

Introduce the first dependency-optional orchestration runtime boundary around the existing planned query flow while keeping local development and tests free of LangGraph installation requirements.

### Main Tasks

- Implement a LangGraph-compatible orchestration adapter with injected-app support.
- Preserve existing planner, retrieval, ranking, validation, synthesis, and logging semantics.
- Add health checks for orchestration capabilities and fallback availability.
- Return structured orchestration run results suitable for future observability.
- Keep LangGraph as an optional runtime integration, not a required project dependency.

### Deliverables

- LangGraph-compatible orchestration runtime adapter.
- Orchestration config, health, and operation result records.
- Local fallback and injected-app regression coverage.
- Milestone and process-status documentation updates.

### Exit Criteria

- The orchestration adapter can run the existing planned-query flow through local fallback.
- Injected LangGraph-style apps receive request state and can return planned-query results.
- Health checks report ready, degraded, or unavailable states.
- App execution failures can fall back to local planned-query execution when configured.
- No required runtime dependencies are introduced.

### Test Gate

- Orchestration fallback health and execution tests pass.
- Injected app invocation tests pass.
- App-failure fallback tests pass.
- Disabled-fallback unavailable tests pass.

## Milestone Dependencies

- Milestone 1 depends on Milestone 0.
- Milestone 2 depends on Milestone 1.
- Milestone 3 depends on Milestone 1 and can run partly in parallel with Milestone 2.
- Milestone 4 depends on Milestone 2 and benefits from Milestone 3.
- Milestone 5 depends on Milestones 1 and 2, then expands after Milestones 3 and 4.
- Milestone 6 depends on the full integrated system.
- Milestone 7 depends on Milestone 6 recovery and governance hardening.
- Milestone 8 depends on Milestone 7 durable storage and Milestone 6 recovery contracts.
- Milestone 9 depends on Milestone 8 adapter contracts and Milestone 7 durable storage.
- Milestone 10 depends on Milestone 8 adapter contracts, Milestone 9 runtime operation results, and Milestone 1 vector indexing.
- Milestone 11 depends on Milestone 10 vector runtime semantics and Milestone 8 adapter contracts.
- Milestone 12 depends on Milestone 3 graph records and Milestone 8 adapter contracts.
- Milestone 13 depends on Milestone 2 planner orchestration, Milestone 6 validation hardening, and Milestone 8 adapter contracts.

## Primary Risks

- Access control leakage through merged retrieval.
- Planner over-routing to expensive retrieval.
- Graph extraction quality below useful threshold.
- Validator accepting weak citation support.
- External retrieval bypassing source governance.
- Repair loops increasing latency.
- Logs becoming too noisy to support debugging.
- Local durable files growing without compaction or retention policies.
- External backend adapters drifting from local governance and recovery semantics.

## Success Definition

The project succeeds when it can ingest governed sources, retrieve through hybrid modes, route requests with a planner, validate evidence, generate cited answers, log every partition, recover from common failures, persist a conservative durable baseline, execute backend adapters behind explicit contracts, and measure quality with repeatable tests.
