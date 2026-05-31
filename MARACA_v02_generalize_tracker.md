# MARACA v02 Generalization Tracker

Evidence source: `generalize_project.json` generated from the current worktree AST scan.

Scope baseline:
- Project: MARACA
- Target: MARACA v02
- Source root: `src`
- Inventory: 30 modules, 135 classes, 506 functions or methods
- Duplication signals: 18 exact duplicate body groups, 35 repeated name groups
- Validation state in evidence: draft

## Suggested Order

1. Establish shared contracts first: serialization, ids, enum coercion, repository hooks, telemetry, and operation result patterns.
2. Generalize provenance, evidence, citation, access, and claim lifecycle policy before changing retrieval, validation, synthesis, feedback, or evaluation behavior.
3. Standardize repository, persistence, graph index, and adapter boundaries so storage/retrieval changes have stable primitives.
4. Consolidate normalization, date/freshness, and scoring utilities, then wire ranking, validation, synthesis, retrieval, ingestion, and registry to the shared surfaces.
5. Convert conditional policy surfaces to tables: ingestion normalization, planning routing, backend health descriptors, and feedback failure taxonomy.
6. Finish backend/service templates and script helpers after the shared runtime boundaries are clear.

## Phase 0 - Review Gates and Evidence Lock

### P0.1 Confirm Evidence-Only Scope
- Evidence ids: summary, modules, agent_reviews, summary_findings, tracker, validation.
- Affected modules: none directly; review all listed modules before implementation planning.
- Acceptance criteria:
  - Every v02 task maps to at least one evidence id from `generalize_project.json`.
  - No new task is added without JSON evidence.
  - Reviewers agree that this tracker is a planning artifact, not an implementation change.
- Test plan:
  - Check each tracker item against `agent_reviews.generalization_opportunities` or `summary_findings`.
  - Confirm all affected modules are present in the JSON module inventory.
- Dependencies: none.
- Risks:
  - JSON evidence is draft and may miss runtime behavior outside AST-visible code.

### P0.2 Prioritize Summary Findings
- Evidence ids: summary_findings ranks 1-7.
- Affected modules:
  - Shared telemetry/repository hooks: `src/shared`, `src/source_registry`, `src/ingestion`, `src/enrichment`, `src/storage`, `src/retrieval`, `src/planning`, `src/ranking`, `src/validation`, `src/synthesis`, `src/feedback`, `src/evaluation`
  - Evidence/provenance/access: `src/retrieval`, `src/storage`, `src/validation`, `src/synthesis`, `src/feedback`, `src/evaluation`
  - Serialization/DTO: `src/shared`, `src/planning`
  - Repository/persistence: `src/source_registry`, `src/ingestion`, `src/storage`, `src/feedback`, `src/evaluation`
  - Scoring/freshness/normalization: `src/source_registry`, `src/ingestion`, `src/retrieval`, `src/storage`, `src/ranking`, `src/validation`, `src/synthesis`
  - Table-driven policies: `src/source_registry`, `src/shared`, `src/ingestion`, `src/planning`, `src/backend_app`, `src/feedback`
  - Adapter/service templates: `src/storage`, `src/retrieval`, `src/backend_app`, `scripts`
- Acceptance criteria:
  - Work is sequenced in rank order unless a dependency requires earlier foundational work.
  - Rank 1 and rank 2 receive architecture review before broad refactors.
- Test plan:
  - Use existing test areas listed in agent reviews as regression anchors.
- Dependencies: P0.1.
- Risks:
  - Over-generalization could obscure currently simple dependency-free flows.

## Phase 1 - Shared Foundation Contracts

### P1.1 Shared Dataclass Serialization and DTO Export
- Evidence ids: A-01, C-07, summary finding rank 3.
- Affected modules:
  - `src/shared/contracts.py`
  - `src/shared/records.py`
  - `src/shared/environment.py`
  - `src/shared/stack.py`
  - `src/planning/__init__.py`
  - `src/planning/orchestration_runtime.py`
- Task:
  - Define one json-ready serialization pattern for dataclasses, enum-rich DTOs, date/list/dict fields, planner traces, and orchestration runtime records.
  - Preserve existing `to_dict` contract shape while reducing manual serializer drift.
- Acceptance criteria:
  - Shared records/configs and planner/orchestration DTOs serialize through the common pattern.
  - Enum/date/list/dict serialization remains stable.
  - Existing public `to_dict` methods continue to return JSON-ready dictionaries.
- Test plan:
  - Parametrized serialization test for all shared dataclasses and enum/date/list/dict cases.
  - PlannerTrace and orchestration DTO `to_dict` golden serialization tests.
- Dependencies: P0.1.
- Risks:
  - Golden outputs may reveal current inconsistent serialization that reviewers must intentionally preserve or normalize.

### P1.2 Enum Coercion and Lookup Helper
- Evidence ids: A-04, summary finding rank 6.
- Affected modules:
  - `src/source_registry/registry.py`
  - `src/shared/environment.py`
  - `src/shared/stack.py`
  - `src/ingestion/__init__.py`
- Task:
  - Generalize enum-or-string input coercion and lookup behavior with consistent error wrapping.
- Acceptance criteria:
  - Invalid environment, stack, source, and ingestion enum strings fail consistently.
  - Existing accepted string and enum inputs continue to work.
- Test plan:
  - Negative tests for invalid environment/stack/source enum strings and consistent domain errors.
  - Positive table tests for valid string and enum inputs.
- Dependencies: P1.1 can share serialization/error conventions, but this task may run independently after P0.
- Risks:
  - Error message changes could affect tests or manual smoke expectations.

### P1.3 Deterministic Stable-ID Helper
- Evidence ids: A-05.
- Affected modules:
  - `src/ingestion/__init__.py`
  - `src/enrichment/__init__.py`
- Task:
  - Centralize SHA-256 deterministic id patterns for chunks, entities, relations, prefixes, separators, truncation, and repeatability.
- Acceptance criteria:
  - Chunk and graph ids preserve existing deterministic formats or have reviewed migration rules.
  - Repeated inputs produce identical ids across ingestion and enrichment.
- Test plan:
  - Shared stable-id tests for prefix format, separator handling, truncation, and repeatability.
- Dependencies: P1.1 if id helpers are exposed through shared records; otherwise P0.
- Risks:
  - Any id format change may break durable references, graph relations, or existing fixtures.

### P1.4 Generic Repository Hook and Persistence Wrapper
- Evidence ids: D-02, C-03, summary finding rank 1.
- Affected modules:
  - `src/feedback/__init__.py`
  - `src/evaluation/__init__.py`
  - `src/planning/__init__.py`
  - `src/planning/orchestration_runtime.py`
  - `src/ranking/__init__.py`
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
- Task:
  - Standardize duck-typed save/log/error repository hooks for absent, partial, in-memory, and durable repository implementations.
- Acceptance criteria:
  - Optional repository behavior is consistent when hooks are missing.
  - Partial repository implementations do not crash successful operations unless current behavior requires failure.
  - Hook helper keeps emitted telemetry compatible with current modules.
- Test plan:
  - Generic repository-save helper behavior with absent and partially implemented methods.
  - Common repository hook tests across planning, ranking, validation, synthesis, feedback, and evaluation.
- Dependencies: P1.1 recommended for shared result serialization.
- Risks:
  - Duck-typed behavior may hide repository integration mistakes if helper is too permissive.

### P1.5 Partition Outcome, Telemetry, and Operation Builders
- Evidence ids: A-03, B-01, C-03, D-03, summary finding rank 1.
- Affected modules:
  - `src/shared/policies.py`
  - `src/source_registry/registry.py`
  - `src/ingestion/__init__.py`
  - `src/enrichment/__init__.py`
  - `src/storage/durable.py`
  - `src/storage/vector_runtime.py`
  - `src/storage/qdrant_runtime.py`
  - `src/storage/neo4j_runtime.py`
  - `src/planning/__init__.py`
  - `src/planning/orchestration_runtime.py`
  - `src/ranking/__init__.py`
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
  - `src/feedback/__init__.py`
  - `src/evaluation/__init__.py`
- Task:
  - Build common helpers for logs, error envelopes, operation results, fallback actions, retryability, correlation ids, output references, and policy mutation details.
- Acceptance criteria:
  - Event names, fallback actions, retry counts, severities, and output references remain stable where tests assert them.
  - Feedback/evaluation success and error logs preserve `policy_mutation=false` details.
  - Storage adapter operation results preserve health/unavailable/degraded semantics.
- Test plan:
  - Cross-partition golden telemetry tests for event_name, fallback_action, retry_count, output_reference, and severity.
  - Operation helper golden tests for feedback/evaluation event payloads.
  - Common adapter template parity tests across durable/vector/Qdrant/Neo4j.
- Dependencies: P1.4.
- Risks:
  - Telemetry unification has high blast radius across most partitions.

## Phase 2 - Evidence, Provenance, Access, and Claims

### P2.1 Shared Trace and Provenance Extraction
- Evidence ids: D-01, summary finding rank 2.
- Affected modules:
  - `src/feedback/__init__.py`
  - `src/evaluation/__init__.py`
- Task:
  - Generalize evidence/source/document/chunk/citation/claim/validation id collection and unique helper behavior.
- Acceptance criteria:
  - Feedback and evaluation traces extract identical provenance from the same answer context.
  - Append-only reference records keep existing fields and ordering guarantees where present.
- Test plan:
  - Provenance extraction parity tests between feedback and evaluation traces.
- Dependencies: P1.1, P1.4.
- Risks:
  - Trace reference ordering or deduplication changes may alter review workflows.

### P2.2 Candidate Hydration Contract
- Evidence ids: B-04, summary finding rank 2.
- Affected modules:
  - `src/retrieval/execution.py`
  - `src/storage/qdrant_runtime.py`
  - `src/storage/neo4j_runtime.py`
- Task:
  - Define one candidate/evidence payload hydration contract for vector, keyword, graph, Qdrant, and Neo4j flows.
- Acceptance criteria:
  - Local index hits, graph hits, Qdrant payloads, and Neo4j payloads map to equivalent evidence fields.
  - Source metadata and citation fields are available consistently to downstream ranking, validation, and synthesis.
- Test plan:
  - Unified hydration tests for local index, graph, Qdrant, and Neo4j payloads.
- Dependencies: P1.1, P2.1.
- Risks:
  - Backend payload differences may require explicit optional fields rather than forced uniformity.

### P2.3 Central Access Metadata Policy
- Evidence ids: B-05, C-02, summary finding rank 2.
- Affected modules:
  - `src/storage/__init__.py`
  - `src/retrieval/execution.py`
  - `src/storage/qdrant_runtime.py`
  - `src/storage/neo4j_runtime.py`
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
- Task:
  - Generalize access metadata checks and citation approval rules into a fail-closed evidence policy.
- Acceptance criteria:
  - Source, document, and chunk denial precedence is preserved.
  - Validation usable-evidence and synthesis approved-evidence rules produce parity for citation eligibility.
  - Retrieval filtering and backend hit payloads use the same policy surface.
- Test plan:
  - Central access evaluator tests preserving source/document/chunk denial precedence.
  - Citation policy parity tests between validation approval and synthesis usage.
- Dependencies: P2.2.
- Risks:
  - Access-control drift can cause leakage; this phase should be reviewed before broad rollout.

### P2.4 Claim Lifecycle Service Boundary
- Evidence ids: C-05, summary finding rank 2.
- Affected modules:
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
  - `src/planning/__init__.py`
- Task:
  - Define the lifecycle boundary for claim creation, citation attachment, support validation, and final answer replacement.
- Acceptance criteria:
  - Synthesis-created claims, validation support checks, and planning claim mutations are coordinated through one contract.
  - Existing answer record and support status behavior is preserved.
- Test plan:
  - Claim lifecycle tests for creation, citation attach, validation update, and final answer replacement.
- Dependencies: P2.3.
- Risks:
  - Claim mutation timing may affect planner repair-loop behavior.

## Phase 3 - Repository, Persistence, Graph, and Index Primitives

### P3.1 Generic In-Memory Repository Primitives
- Evidence ids: A-02, summary finding rank 4.
- Affected modules:
  - `src/source_registry/registry.py`
  - `src/ingestion/__init__.py`
- Task:
  - Generalize save/get/id-keyed dictionary patterns and log/error append behavior for in-memory repositories.
- Acceptance criteria:
  - Unknown ids, seeded records, insertion order, and relation append behavior remain deterministic.
  - Existing source and ingestion repository APIs remain available.
- Test plan:
  - Repository contract tests for unknown ids, insertion order, seeded records, and relation append behavior.
- Dependencies: P1.4.
- Risks:
  - Shared primitives must not couple source registry and ingestion domain behavior too tightly.

### P3.2 Record Save and Snapshot Table
- Evidence ids: B-02, summary finding rank 4.
- Affected modules:
  - `src/storage/__init__.py`
  - `src/storage/durable.py`
- Task:
  - Convert repeated `save_*` id-field/store/write and snapshot routines into a table-driven record registry.
- Acceptance criteria:
  - Every record type preserves its id/store mapping.
  - In-memory and durable snapshot behavior remain equivalent.
  - JSON persistence shape remains compatible unless explicitly reviewed.
- Test plan:
  - Generic save/snapshot table tests preserving id/store mappings for every record type.
- Dependencies: P3.1 helpful but not mandatory; P1.1 recommended.
- Risks:
  - Durable serialization changes could affect existing JSON/JSONL persistence files.

### P3.3 Graph Index Abstraction
- Evidence ids: B-06, summary finding rank 4.
- Affected modules:
  - `src/storage/__init__.py`
  - `src/storage/durable.py`
  - `src/retrieval/execution.py`
- Task:
  - Encapsulate graph relation/entity/chunk reverse indexes for commit, rebuild, verification, durable reload, and traversal.
- Acceptance criteria:
  - Graph commit and rebuild produce equivalent indexes before and after durable reload.
  - Retrieval traversal uses the abstraction rather than manipulating reverse indexes directly.
- Test plan:
  - Graph index abstraction tests for rebuild, verify, traversal, and durable reload equivalence.
- Dependencies: P3.2.
- Risks:
  - Index abstraction may need careful naming to avoid hiding graph traversal diagnostics.

### P3.4 Generic Index Commit Pipeline
- Evidence ids: B-03, summary finding rank 7.
- Affected modules:
  - `src/retrieval/indexing.py`
- Task:
  - Generalize vector and sparse commit flow: generation, skip tracking, repository storage, chunk pointer updates, degraded logs, and result assembly.
- Acceptance criteria:
  - Vector and sparse commits keep identical result/log semantics to current behavior.
  - Chunk pointer updates remain mode-specific where required.
- Test plan:
  - Shared index commit tests proving identical logs/results for vector and sparse modes.
- Dependencies: P1.5, P3.2.
- Risks:
  - Over-abstracting vector and sparse differences could reduce clarity in index diagnostics.

## Phase 4 - Normalization, Freshness, and Scoring

### P4.1 Text Normalization and Term Extraction Surface
- Evidence ids: B-07, summary finding ranks 1 and 5.
- Affected modules:
  - `src/retrieval/indexing.py`
  - `src/retrieval/execution.py`
  - `src/storage/neo4j_runtime.py`
- Task:
  - Share alias/query normalization, tokenization, term extraction, phrase handling, and identifier normalization for search and graph lookup paths.
- Acceptance criteria:
  - Keyword, vector, and graph lookup paths normalize comparable inputs consistently.
  - Existing query and alias behavior remains covered by parity tests.
- Test plan:
  - Shared normalization parity tests across keyword, vector, and graph lookup paths.
- Dependencies: P2.2.
- Risks:
  - Normalization changes may affect ranking order and graph recall.

### P4.2 Freshness and Date Parsing Utilities
- Evidence ids: A-07, C-04, summary finding rank 5.
- Affected modules:
  - `src/source_registry/registry.py`
  - `src/ingestion/__init__.py`
  - `src/ranking/__init__.py`
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
- Task:
  - Generalize refresh interval parsing, first-date extraction, as-of-date fallback, published/retrieved/document metadata resolution, and staleness scoring inputs.
- Acceptance criteria:
  - Date fallback order is explicit and tested for evidence, chunk, document, retrieved_at, and missing-date cases.
  - Source freshness policy and downstream evidence freshness use compatible helpers.
- Test plan:
  - Focused duration parsing, default refresh intervals, stale transitions, and freshness fallback-order tests.
  - Date resolver tests for evidence, chunk, document, retrieved_at, and missing-date fallback order.
- Dependencies: P4.1 optional; P1.1 for date serialization.
- Risks:
  - Changed fallback order could affect ranking, validation, and synthesis decisions.

### P4.3 Shared Evidence Quality and Scoring Utilities
- Evidence ids: C-01, summary finding rank 5.
- Affected modules:
  - `src/ranking/__init__.py`
  - `src/validation/__init__.py`
  - `src/synthesis/__init__.py`
- Task:
  - Share tokenization, stopword policy, clamping, reliability scoring, retrieval-score selection, freshness scoring, and normalization.
- Acceptance criteria:
  - Ranking, validation, and synthesis produce equivalent scores where the evidence says logic overlaps.
  - Module-specific weights remain explicit.
- Test plan:
  - Shared scoring utility parity tests across ranking/validation/synthesis.
- Dependencies: P4.1, P4.2.
- Risks:
  - Shared scoring could make previously intentional module-specific differences less visible.

### P4.4 Quality Flag Append and Dedup Helper
- Evidence ids: A-08.
- Affected modules:
  - `src/ingestion/__init__.py`
  - `src/enrichment/__init__.py`
- Task:
  - Generalize quality flag preservation, append, deduplication, ordering, and namespacing across ingestion and enrichment.
- Acceptance criteria:
  - Existing flags are preserved.
  - Duplicate flags are avoided.
  - Combined ingestion and graph flags retain deterministic order.
- Test plan:
  - Tests for preserving existing flags, avoiding duplicates, ordering, and combining ingestion plus graph flags.
- Dependencies: P1.3 helpful for chunk/entity identity stability.
- Risks:
  - Flag ordering may be externally visible in tests or review dashboards.

## Phase 5 - Table-Driven Policy Surfaces

### P5.1 Content Normalizer Strategy Registry
- Evidence ids: A-06, summary finding rank 6.
- Affected modules:
  - `src/ingestion/__init__.py`
- Task:
  - Replace JSON/CSV/HTML/default normalization branching with a strategy registry keyed by content type or document type.
- Acceptance criteria:
  - Existing JSON, CSV, HTML, and default outputs preserve title/type/metadata/quality flag behavior.
  - New formats can be added without expanding a single conditional branch.
- Test plan:
  - Table-driven normalization tests by content_type, title, type, metadata, flags, and failure behavior.
- Dependencies: P4.4.
- Risks:
  - Parser dispatch changes may affect low-dependency ingestion guarantees.

### P5.2 Table-Driven Planning Policy
- Evidence ids: C-06, summary finding rank 6.
- Affected modules:
  - `src/planning/__init__.py`
- Task:
  - Generalize query type routing to retrieval modes, budgets, fallback actions, validations, plan reasons, and repair-loop behavior.
- Acceptance criteria:
  - Graph, multi-hop, budget override, and repair-loop cases are represented as explicit table entries.
  - Planner trace reasons remain reviewable.
- Test plan:
  - Graph, multi-hop, budget override, and repair-loop table cases.
- Dependencies: P2.4, P1.5.
- Risks:
  - Planner behavior is user-facing; small routing changes can cascade through retrieval and synthesis.

### P5.3 Backend Health Service Descriptors
- Evidence ids: D-05, summary findings ranks 6 and 7.
- Affected modules:
  - `src/backend_app/health.py`
- Task:
  - Generalize env parsing and Qdrant/Neo4j strict-service blocked/health/status logic into service descriptors.
- Acceptance criteria:
  - Ready/degraded/unavailable states match current health-check behavior.
  - Strict-services handling remains explicit per service.
  - Env file parsing edge cases are covered.
- Test plan:
  - Env parsing edge cases and mocked ready/degraded/unavailable service descriptor tests.
- Dependencies: P1.5 for operation/status conventions.
- Risks:
  - Health CLI behavior may be used by scripts and manual checks.

### P5.4 Failure Taxonomy Metadata Table
- Evidence ids: D-07, summary finding rank 6.
- Affected modules:
  - `src/feedback/__init__.py`
- Task:
  - Convert feedback category classification, task title, recommended action, validation signal, and priority hints into one metadata table.
- Acceptance criteria:
  - Every FailureCategory text signal maps to the same title/action/priority behavior as current code.
  - Feedback-derived improvement tasks keep current category semantics.
- Test plan:
  - Table-driven tests for every FailureCategory text signal, validation signal, title/action, and priority.
- Dependencies: P1.5.
- Risks:
  - Classification keyword changes may alter downstream improvement task queues.

## Phase 6 - Adapter, Runtime, Metrics, and Script Templates

### P6.1 Backend Runtime Adapter Template
- Evidence ids: B-01, summary findings ranks 1 and 7.
- Affected modules:
  - `src/storage/durable.py`
  - `src/storage/vector_runtime.py`
  - `src/storage/qdrant_runtime.py`
  - `src/storage/neo4j_runtime.py`
- Task:
  - Generalize capability checks, health status selection, unavailable handling, operation result construction, and storage error creation across backend adapters.
- Acceptance criteria:
  - Durable, vector, Qdrant, and Neo4j adapters pass parity tests for common states.
  - Adapter-specific capabilities remain explicit.
- Test plan:
  - Common adapter template parity tests across durable/vector/Qdrant/Neo4j.
- Dependencies: P1.5.
- Risks:
  - Runtime adapter changes may affect full backend smoke checks.

### P6.2 Optional Client Boundary Standardization
- Evidence ids: B-08, summary finding rank 7.
- Affected modules:
  - `src/storage/qdrant_runtime.py`
  - `src/storage/neo4j_runtime.py`
- Task:
  - Standardize optional dependency/client handling, fake-client-compatible calls, exception wrapping, and payload conversion.
- Acceptance criteria:
  - Qdrant and Neo4j clients report ready, degraded, and unavailable states consistently.
  - Deterministic fake clients remain supported for tests.
- Test plan:
  - Optional-client ready/degraded/unavailable tests using deterministic fake clients.
- Dependencies: P6.1, P2.2.
- Risks:
  - Optional dependency import handling must remain dependency-optional.

### P6.3 Shared Metrics Aggregation Utilities
- Evidence ids: D-04.
- Affected modules:
  - `src/evaluation/__init__.py`
- Task:
  - Extract generic sum, average, rate, count, latency, cost, partition-count, event-count, and safe-rate helpers for broader observability dashboards.
- Acceptance criteria:
  - Empty, partial, and non-scalar metrics are handled consistently.
  - Existing evaluation batch and observability reports preserve current values.
- Test plan:
  - Aggregation helper tests for empty, partial, and non-scalar metrics.
- Dependencies: P1.5.
- Risks:
  - Numeric edge cases could change dashboard-ready report outputs.

### P6.4 PowerShell Script Common Helper
- Evidence ids: D-06, summary finding rank 7.
- Affected files:
  - `scripts/setup_full_backend.ps1`
  - `scripts/test_full_backend.ps1`
- Task:
  - Generalize duplicated root/env resolution and command wiring for backend setup and test scripts.
- Acceptance criteria:
  - Setup and test scripts resolve root/env files consistently.
  - Existing health and smoke command wiring remains available.
- Test plan:
  - Executable script behavior tests beyond string-presence checks.
- Dependencies: P5.3.
- Risks:
  - Script changes need Windows PowerShell validation and should preserve developer workflow.

## Cross-Phase Acceptance Criteria

- All generalized helpers preserve dependency-free behavior where modules are documented as dependency-free.
- Public dataclass, repository, planner, retrieval, ranking, validation, synthesis, feedback, evaluation, health, and script behavior is covered by parity or golden tests before replacing local implementations.
- Each implementation PR references the evidence ids it addresses.
- No shared abstraction is introduced unless at least two evidence-backed modules use it or a summary finding ranks it as a cross-cutting theme.
- High-risk surfaces receive explicit reviewer signoff: telemetry/error envelopes, access policy, evidence hydration, claim lifecycle, durable persistence, backend adapters, and planner routing.

## Consolidated Test Plan

- Serialization and DTO:
  - Parametrized shared dataclass serialization tests.
  - PlannerTrace and orchestration DTO golden `to_dict` tests.
- Repository and persistence:
  - Generic repository contract tests.
  - Save/snapshot table tests for every record type.
  - Graph index rebuild, verify, traversal, and durable reload equivalence tests.
- Telemetry and hooks:
  - Cross-partition golden telemetry tests.
  - Generic repository hook tests for absent and partial repositories.
  - Feedback/evaluation operation helper golden payload tests.
- Evidence and access:
  - Unified hydration tests for local index, graph, Qdrant, and Neo4j payloads.
  - Central access evaluator denial-precedence tests.
  - Citation policy parity tests.
  - Claim lifecycle tests.
- Normalization, dates, scoring, flags:
  - Shared normalization parity tests.
  - Duration parsing and freshness fallback-order tests.
  - Date resolver tests.
  - Shared scoring parity tests.
  - Quality flag append/dedup tests.
- Policy tables:
  - Content normalizer table tests.
  - Planning routing table tests.
  - Backend service descriptor tests.
  - Failure taxonomy table tests.
- Adapter, metrics, scripts:
  - Adapter template parity tests.
  - Optional-client ready/degraded/unavailable fake-client tests.
  - Metrics aggregation edge-case tests.
  - Executable PowerShell script behavior tests.

## Dependency Map

- P1.1 supports P1.4, P1.5, P2.1, P2.2, P3.2, P4.2.
- P1.4 supports P1.5, P3.1, P6.3.
- P1.5 supports P2.3, P3.4, P5.2, P5.3, P5.4, P6.1.
- P2.1 supports P2.2.
- P2.2 supports P2.3, P4.1, P6.2.
- P2.3 supports P2.4.
- P2.4 supports P5.2.
- P3.2 supports P3.3 and P3.4.
- P4.1 and P4.2 support P4.3.
- P4.4 supports P5.1.
- P5.3 supports P6.4.
- P6.1 supports P6.2.

## Risk Register

- R1 Telemetry drift: centralizing logs/errors/results could alter event names, severities, fallback actions, retry counts, output references, or policy mutation details.
- R2 Access leakage: provenance/access/citation changes must remain fail-closed and preserve source/document/chunk denial precedence.
- R3 Durable compatibility: save/snapshot, graph index, serialization, and id helpers may affect JSON/JSONL persistence and reload behavior.
- R4 Retrieval quality changes: normalization, freshness, scoring, and hydration changes may shift ranking, validation, synthesis, and graph recall.
- R5 Planner cascade: table-driven routing can alter downstream retrieval modes, budgets, fallbacks, validations, and repair loops.
- R6 Optional dependency behavior: Qdrant/Neo4j boundaries must keep dependency-optional behavior and deterministic fake-client support.
- R7 Abstraction cost: shared helpers may make simple dependency-free modules harder to inspect if boundaries are too broad.

## Evidence Index

- A-01 Shared dataclass serialization/id helper: `src/shared/contracts.py`, `src/shared/records.py`, `src/shared/environment.py`, `src/shared/stack.py`
- A-02 Generic in-memory repository primitives: `src/source_registry/registry.py`, `src/ingestion/__init__.py`
- A-03 Partition outcome/event builders: `src/shared/policies.py`, `src/source_registry/registry.py`, `src/ingestion/__init__.py`, `src/enrichment/__init__.py`
- A-04 Enum coercion and lookup helper: `src/source_registry/registry.py`, `src/shared/environment.py`, `src/shared/stack.py`, `src/ingestion/__init__.py`
- A-05 Deterministic stable-id helper: `src/ingestion/__init__.py`, `src/enrichment/__init__.py`
- A-06 Content normalizer strategy registry: `src/ingestion/__init__.py`
- A-07 Freshness and date parsing utilities: `src/source_registry/registry.py`, `src/ingestion/__init__.py`
- A-08 Quality flag append/dedup helper: `src/ingestion/__init__.py`, `src/enrichment/__init__.py`
- B-01 Backend runtime adapter template: `src/storage/durable.py`, `src/storage/vector_runtime.py`, `src/storage/qdrant_runtime.py`, `src/storage/neo4j_runtime.py`
- B-02 Record save/snapshot table: `src/storage/__init__.py`, `src/storage/durable.py`
- B-03 Generic index commit pipeline: `src/retrieval/indexing.py`
- B-04 Candidate hydration contract: `src/retrieval/execution.py`, `src/storage/qdrant_runtime.py`, `src/storage/neo4j_runtime.py`
- B-05 Central access metadata policy: `src/storage/__init__.py`, `src/retrieval/execution.py`, `src/storage/qdrant_runtime.py`, `src/storage/neo4j_runtime.py`
- B-06 Graph index abstraction: `src/storage/__init__.py`, `src/storage/durable.py`, `src/retrieval/execution.py`
- B-07 Text normalization and term extraction surface: `src/retrieval/indexing.py`, `src/retrieval/execution.py`, `src/storage/neo4j_runtime.py`
- B-08 Optional client boundary standardization: `src/storage/qdrant_runtime.py`, `src/storage/neo4j_runtime.py`
- C-01 Shared evidence quality/scoring utilities: `src/ranking/__init__.py`, `src/validation/__init__.py`, `src/synthesis/__init__.py`
- C-02 Central evidence approval/citation policy: `src/validation/__init__.py`, `src/synthesis/__init__.py`
- C-03 Shared telemetry and repository hook adapter: `src/planning/__init__.py`, `src/planning/orchestration_runtime.py`, `src/ranking/__init__.py`, `src/validation/__init__.py`, `src/synthesis/__init__.py`
- C-04 Unified date/freshness extraction: `src/ranking/__init__.py`, `src/validation/__init__.py`, `src/synthesis/__init__.py`
- C-05 Claim lifecycle service boundary: `src/validation/__init__.py`, `src/synthesis/__init__.py`, `src/planning/__init__.py`
- C-06 Table-driven planning policy: `src/planning/__init__.py`
- C-07 Runtime result serialization pattern: `src/planning/__init__.py`, `src/planning/orchestration_runtime.py`
- D-01 Shared trace/reference extraction: `src/feedback/__init__.py`, `src/evaluation/__init__.py`
- D-02 Repository duck-typed persistence wrappers: `src/feedback/__init__.py`, `src/evaluation/__init__.py`
- D-03 Operation telemetry construction helper: `src/feedback/__init__.py`, `src/evaluation/__init__.py`
- D-04 Shared metrics aggregation utilities: `src/evaluation/__init__.py`
- D-05 Backend health service descriptors: `src/backend_app/health.py`
- D-06 PowerShell script common helper: `scripts/setup_full_backend.ps1`, `scripts/test_full_backend.ps1`
- D-07 Failure taxonomy metadata table: `src/feedback/__init__.py`

