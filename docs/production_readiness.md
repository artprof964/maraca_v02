# Production Readiness Runbook

## Scope

Milestone 6 hardens the dependency-free in-memory implementation so production concerns are visible before durable services are introduced. The current code remains standard-library only and does not create external service clients.

For the current cross-repo setup, MARACA production readiness means retrieval backend readiness. Live thestone Telegram bot containers are owned by AI-Art Compose and are documented outside this repo.

## Readiness Checklist

- Access checks fail closed when source, document, or chunk access metadata is absent.
- Restricted and confidential evidence is filtered before merge, ranking, synthesis, and feedback/evaluation storage.
- License policy remains separate from access policy and blocks high-risk use when unknown or restricted.
- Ingestion and storage logs keep correlation IDs and partition-level event names.
- Storage bundle commits can be retried with stable record IDs and a rollback snapshot.
- Partial storage writes are restored before retry or final failure.
- Source refresh checks identify due, stale, never-checked, blocked, and failed sources.
- Stale active sources can be deprecated without mutating access policy or allow lists.
- Evaluation and feedback workflows remain append-only and do not mutate governance fields.

## Storage Recovery Procedure

Use `commit_storage_bundle_with_recovery` for multi-record writes that must behave as one operational unit. The helper snapshots repository dictionaries before each attempt, calls the existing commit path, and restores the snapshot if any write raises an exception.

Retryable storage adapters should raise `StorageOperationError(..., retryable=True)`. The helper records `storage_commit_retry` and tries again up to `max_retries`. Non-retryable failures record `storage_commit_failed`, restore the pre-attempt snapshot, and return `committed=False`.

After recovery, run `verify_storage_commit` with the expected raw artifact, document, and chunks. Treat any missing access metadata as a release blocker because retrieval filters rely on those fields to prevent leakage.

## Source Refresh Procedure

Use `SourceRegistry.monitor_source_refreshes()` for an operational sweep. The monitor checks `refresh_interval`, then `freshness_sla`, then the default interval for the source freshness policy.

Supported interval strings are minutes, hours, days, and weeks, such as `15m`, `12h`, `2d`, and `1w`. Scheduled and event-driven sources default to one day. Real-time sources default to fifteen minutes. Manual and static sources are not automatically due.

When a source is stale and active, `update_stale_source_status` marks it deprecated while preserving access policy and allowed principals. A later ingestion flow can reactivate the source after successful refresh and verification.

## Security Review

Access and license enforcement are intentionally layered:

- Source registry checks source-level access and high-risk license policy.
- Retrieval checks source, document, and chunk access metadata before evidence merge.
- Synthesis only uses approved evidence candidates.
- Feedback and evaluation create trace/improvement records without mutating source reliability, access policy, or allow lists.

The main residual production risk is durable backend parity. When replacing in-memory stores with databases, object stores, vector indexes, and graph stores, each adapter must preserve the same fail-closed access behavior, retry/error envelope fields, and rollback or compensating transaction semantics.

## Load Test Report

The Milestone 6 test suite includes a local load-style regression that builds 120 chunk records, commits vector and sparse indexes, runs hybrid retrieval, and ranks the top results. The target for the dependency-free local path is under 750 ms for retrieval plus ranking on this fixture set.

This is a guardrail, not a production benchmark. Real production latency and cost targets should be remeasured once Qdrant, Neo4j, metadata storage, raw source storage, model services, and orchestration runtimes are connected.

## Environment Readiness

The runtime env contract is sourced from `.env.example`:

- LLM settings: `deepseek-open-art`, `LLM_API_URL`, `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_CLASSIFIER_MODEL`, `LLM_EMBEDDING_MODEL`.
- Qdrant settings: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`.
- Neo4j settings: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
- Local storage/profile settings: `RAG_STORAGE_ROOT`, `RAG_MODEL_PROFILE`.

Strict readiness requires Qdrant and Neo4j to be running before `rag-center-health --strict-services --env-file .env`.
