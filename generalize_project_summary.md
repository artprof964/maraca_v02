# MARACA Project Generalization Summary

Source: `generalize_project.json` generated from the current worktree AST scan. Evidence references use JSON paths such as `summary`, `modules`, `functions`, `duplicate_candidates.*`, `agent_reviews[A-D]`, and `summary_findings`.

## Project-Wide Function Inventory

The scan covers 30 source modules, 135 classes, and 506 functions or methods (`summary`). The largest function inventories are concentrated in the core pipeline and storage layers: `src/storage/__init__.py` has 44 functions, `src/ingestion/__init__.py` 41, `src/evaluation/__init__.py` 36, `src/validation/__init__.py` 36, `src/feedback/__init__.py` 32, `src/storage/durable.py` 29, `src/planning/__init__.py` 28, and `src/source_registry/registry.py` 27 (`functions`, grouped by `file`). The largest class inventory is `src/shared/records.py` with 46 classes, followed by adapter/runtime and trace-heavy modules such as `src/storage/adapters.py`, `src/planning/orchestration_runtime.py`, and `src/evaluation/__init__.py` (`classes`, grouped by `file`).

The module map (`modules`) shows that most high-density behavior lives in the vertical partitions: ingestion, source registry, storage, retrieval, planning, ranking, validation, synthesis, feedback, and evaluation. Shared contracts already exist in `src/shared/contracts.py`, `src/shared/records.py`, `src/shared/policies.py`, `src/shared/environment.py`, and `src/shared/stack.py`, but the duplicate inventory shows those shared modules have not yet absorbed all cross-partition conventions (`duplicate_candidates.exact_body_groups`, `duplicate_candidates.repeated_name_groups`).

## Major Duplicate and Generalization Themes

1. Shared telemetry, error, and repository-hook contracts are the strongest project-wide theme (`summary_findings[1]`; `agent_reviews` A-03, B-01, B-07, C-03, D-02, D-03). Exact duplicates include `add_log` and `save_error` implementations across `src/evaluation/__init__.py`, `src/feedback/__init__.py`, and `src/storage/__init__.py`; helper duplicates include `_add_log` and `_save_error` in feedback/evaluation and ranking/synthesis (`duplicate_candidates.exact_body_groups`). Repeated-name groups also show five `_add_log`, five `_save_error`, five `add_log`, and four `save_error` implementations (`duplicate_candidates.repeated_name_groups`).

2. Evidence, provenance, citation, and access policy should be centralized (`summary_findings[2]`; `agent_reviews` B-04, B-05, C-02, C-05, D-01). Retrieval, storage backends, validation, synthesis, feedback, and evaluation each hydrate, approve, cite, or extract evidence references across `src/retrieval/execution.py`, `src/storage/qdrant_runtime.py`, `src/storage/neo4j_runtime.py`, `src/validation/__init__.py`, `src/synthesis/__init__.py`, `src/feedback/__init__.py`, and `src/evaluation/__init__.py`. The theme candidate `access_metadata_flow` has 92 evidence hits (`duplicate_candidates.theme_candidates`).

3. Serialization is widespread and partly exact-duplicated (`summary_findings[3]`; `agent_reviews` A-01, C-07). The repeated-name group `to_dict` appears 33 times, and one exact duplicate body group covers 20 `to_dict` methods across `src/shared/contracts.py`, `src/shared/environment.py`, `src/shared/records.py`, and `src/storage/adapters.py` (`duplicate_candidates.repeated_name_groups`, `duplicate_candidates.exact_body_groups`). This suggests a common JSON-ready dataclass/export helper would reduce drift while preserving explicit record contracts.

4. Repository and persistence primitives repeat across in-memory and durable stores (`summary_findings[4]`; `agent_reviews` A-02, B-02, B-06, D-02). Duplicates include save/get/snapshot-style methods and exact matching `save_raw_artifact` and `save_document` bodies between `src/ingestion/__init__.py` and `src/storage/__init__.py`; related repeated names extend into `src/storage/durable.py` (`duplicate_candidates.exact_body_groups`, `duplicate_candidates.repeated_name_groups`).

5. Scoring, freshness, text normalization, and stable identifiers are parallel utilities rather than one policy surface (`summary_findings[5]`; `agent_reviews` A-05, A-07, B-07, C-01, C-04). Exact duplicates include `_stable_id` in `src/enrichment/__init__.py` and `src/retrieval/indexing.py`, `_terms` in `src/ranking/__init__.py` and `src/validation/__init__.py`, and `_clamp` in `src/synthesis/__init__.py` and `src/validation/__init__.py` (`duplicate_candidates.exact_body_groups`). These are small functions, but they sit on high-impact paths for IDs, ranking, retrieval, validation, and answer generation.

6. Adapter, health-check, and service-boundary templates are ready for extraction (`summary_findings[7]`; `agent_reviews` B-01, B-03, B-08, D-05, D-06). Repeated names include seven `health_check` methods and seven `to_config` methods across orchestration and backend adapters; exact duplicates include `OrchestrationRuntimeAdapter.health_check` / `BackendRuntimeAdapter.health_check`, `OrchestrationRuntimeAdapter.to_config` / `BackendRuntimeAdapter.to_config`, and a five-function `to_config` duplicate group across LangGraph, durable storage, Neo4j, Qdrant, and in-memory vector adapters (`duplicate_candidates.exact_body_groups`, `duplicate_candidates.repeated_name_groups`).

7. Table-driven policy surfaces would reduce conditional drift (`summary_findings[6]`; `agent_reviews` A-04, A-06, C-06, D-05, D-07). Candidate areas include enum coercion in shared/source/ingestion modules, content normalization in `src/ingestion/__init__.py`, query planning in `src/planning/__init__.py`, backend health descriptors in `src/backend_app/health.py`, and feedback failure taxonomy in `src/feedback/__init__.py`.

## Highest-Risk Standardization Areas

1. Error and telemetry standardization is high risk because it cuts across persistence, retries, fallback actions, repository hooks, and observability. Any shared helper must preserve event names, correlation IDs, fallback actions, retryability, severity, and optional repository behavior called out in A-03, C-03, D-02, and D-03 (`agent_reviews`; source modules include `src/shared/policies.py`, `src/source_registry/registry.py`, `src/ingestion/__init__.py`, `src/enrichment/__init__.py`, `src/planning/__init__.py`, `src/ranking/__init__.py`, `src/validation/__init__.py`, `src/synthesis/__init__.py`, `src/feedback/__init__.py`, and `src/evaluation/__init__.py`).

2. Evidence/provenance/access consolidation is high risk because MARACA appears to rely on fail-closed access behavior and citation integrity across storage, retrieval, validation, synthesis, feedback, and evaluation (`summary_findings[2]`; B-04, B-05, C-02, C-05, D-01). Standardizing this area should start with explicit source/document/chunk denial precedence and citation approval tests before moving logic.

3. Serialization generalization is deceptively risky despite many exact duplicate `to_dict` bodies. `src/shared/records.py` is the canonical record surface, while evaluation, feedback, planning, orchestration, stack, environment, and adapter DTOs all expose public dictionaries (`duplicate_candidates.repeated_name_groups`). A shared serializer should be introduced as an implementation detail first, with golden outputs proving API compatibility.

4. Repository abstraction could create broad behavior changes if save order, append semantics, ID keys, snapshots, graph rebuilds, and durable reload behavior diverge (`agent_reviews` A-02, B-02, B-06, D-02). The overlap between in-memory repositories, durable storage, ingestion job storage, and evaluation/feedback repositories makes this valuable but test-first.

5. Adapter templates and optional-client boundaries are risky because they represent external service readiness, degraded/unavailable states, and operation result contracts (`agent_reviews` B-01, B-08, D-05; `duplicate_candidates.repeated_name_groups` for `health_check` and `to_config`). Shared templates should preserve backend-specific details payloads and health semantics.

## Missing-Test Themes

The JSON review findings repeatedly call for golden/parity tests before generalization. The most common gaps are:

- Cross-partition telemetry golden tests for event names, fallback actions, retry counts, output references, severity, retryability, and repository-hook behavior (`agent_reviews` A-03, C-03, D-02, D-03).
- Serialization golden tests covering all shared dataclasses, enum/date/list/dict handling, planner/orchestration DTOs, and API/export compatibility (`agent_reviews` A-01, C-07; `duplicate_candidates.repeated_name_groups.to_dict`).
- Repository contract tests for unknown IDs, insertion order, seeded records, relation append behavior, save/snapshot tables, graph rebuild/verify/traversal, durable reload equivalence, and absent or partial repositories (`agent_reviews` A-02, B-02, B-06, D-02).
- Provenance and access-control parity tests for local index, graph, Qdrant, Neo4j payload hydration, source/document/chunk denial precedence, citation approval, claim lifecycle, and feedback/evaluation trace extraction (`agent_reviews` B-04, B-05, C-02, C-05, D-01).
- Normalization, freshness, scoring, and stable-ID parity tests covering content-type strategy cases, duration/date fallback order, text/term extraction across keyword/vector/graph paths, scoring parity across ranking/validation/synthesis, and deterministic ID format/truncation (`agent_reviews` A-05, A-06, A-07, B-07, C-01, C-04).
- Table-driven policy tests for enum coercion, planning routes and budgets, backend health descriptors, service readiness states, failure taxonomy category metadata, and PowerShell setup/test script behavior (`agent_reviews` A-04, C-06, D-05, D-06, D-07).

## Suggested Standardization Order

1. Add golden/parity tests around telemetry, serialization, provenance/access, and repository behavior before moving implementation.
2. Extract low-risk pure helpers first: stable ID, unique/list extraction, clamp/term/date utilities, and JSON-ready dataclass serialization.
3. Introduce repository and telemetry helper APIs behind existing module functions, preserving current public method names.
4. Consolidate provenance/access and adapter health boundaries only after parity tests cover local, durable, graph, Qdrant, Neo4j, feedback, and evaluation paths.
5. Convert conditional-heavy policy areas into explicit tables once behavior is locked: content normalization, enum coercion, planning routes, backend health descriptors, and feedback failure taxonomy.
