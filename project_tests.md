# Project Tests: Agent-Orchestrated Hybrid Retrieval Center

## Purpose

This test plan defines unit tests, validator tests, integration tests, logging/error tests, and acceptance tests for each part of the Agent-Orchestrated Hybrid Retrieval Center. The tests are implementation-neutral and should be translated into the chosen test framework during development.

## Test Principles

- Test each partition independently before testing the full flow.
- Use deterministic fixtures wherever possible.
- Separate retrieval failures from synthesis failures.
- Test access control before ranking and validation.
- Test failure paths, not only happy paths.
- Every test should assert logs or error envelopes where relevant.
- Validator tests should check evidence quality, not just answer text.

## Current Full Test Gate

Latest observed results after the 2026-06-04 P5.3 backend service/env defaults validation:

- Focused P5.3 pytest: 30 tests passed.
- Backend-adjacent phase pytest: 70 tests passed.
- Standard-library unittest discovery: 141 tests passed.
- Pytest suite: 307 tests passed.
- Full backend imports: local backend packages plus Qdrant client, Neo4j driver, LangGraph, and LlamaIndex core import successfully.
- Dependency check: no broken requirements.
- Service health command: lenient `rag-center-health --env-file .env.example` passes optional imports, Docker/env checks, Qdrant/Neo4j env defaults, and LangGraph runtime; strict service health was skipped because the Docker daemon/API pipe is unavailable on this host.
- Short keyword manual: `rag-center-smoke` returns one keyword candidate, keyword execution mode, one citation, 20 logs, and a cited answer.
- Setup artifact coverage verifies the package console commands, `full`/`backend` extras, local `.env.example` contract, Docker Compose service definitions, and setup/test script wiring.
- Backend adapter runtime coverage now includes local durable health checks, transactional capability selection, adapter-driven recovery commits, governance-preserving persistence, executable vector indexing/search, Qdrant-compatible health/index/search behavior, Neo4j-compatible graph health/index/traversal behavior, and governed backend write failure reporting.
- Orchestration runtime coverage now includes LangGraph-compatible local fallback execution, injected app execution, app-failure fallback, unavailable disabled-fallback behavior, and serialized run summaries.

## Shared Fixtures

### Fixture Set A: Public Source

- Public document with stable external_link.
- Contains exact phrase, semantic topic, and citation-friendly paragraph.
- Expected behavior: source is ingested, indexed, retrievable, and citeable.

### Fixture Set B: Restricted Source

- Internal or confidential document.
- Contains attractive answer evidence that unauthorized users must not retrieve.
- Expected behavior: evidence is filtered before ranking for unauthorized access_scope.

### Fixture Set C: Stale Source

- Document with old as_of_date and freshness_sla violation.
- Expected behavior: validator flags stale evidence when freshness is required.

### Fixture Set D: Conflicting Sources

- Two documents with contradictory claims.
- Expected behavior: validator detects possible or confirmed contradiction.

### Fixture Set E: Graph Source

- Documents containing entities and relations.
- Expected behavior: entity and relation records link back to source chunks.

### Fixture Set F: Malformed Source

- Broken PDF, bad HTML, missing metadata, or incomplete API response.
- Expected behavior: ingestion creates error envelope and logs partial or failed status.

### Fixture Set G: External Source

- Web or external-source fixture with URL, retrieval date, and reliability level.
- Expected behavior: external result is registered as governed temporary or persisted source before ranking.

## Unit Tests By Partition

## Partition A: Source Registry Tests

### Unit Tests

- `test_register_source_requires_name_type_owner_access_method`
- `test_register_source_preserves_external_link`
- `test_register_source_sets_default_status_pending_when_owner_missing`
- `test_update_source_status_allows_active_deprecated_blocked_failed`
- `test_check_source_access_allows_authorized_principal`
- `test_check_source_access_denies_unauthorized_principal`
- `test_apply_source_policy_blocks_unknown_license_for_restricted_use`
- `test_reliability_score_is_separate_from_freshness_sla`

### Error and Logging Tests

- `test_source_access_failure_creates_error_envelope`
- `test_source_policy_application_logs_decision`
- `test_blocked_source_logs_source_blocked_event`

### Validator Tests

- Unauthorized source must not appear in evidence candidates.
- Source with unknown license must not be used in high-risk answer.

## Partition B: Ingestion Tests

### Unit Tests

- `test_start_ingestion_job_creates_correlation_id`
- `test_extract_source_content_returns_raw_artifact_reference`
- `test_normalize_document_preserves_title_headings_dates`
- `test_create_document_record_inherits_access_policy`
- `test_ingestion_job_status_completed_on_success`
- `test_ingestion_job_status_partial_when_optional_extraction_fails`
- `test_ingestion_job_status_failed_when_required_text_missing`

### Error and Logging Tests

- `test_network_timeout_retries_until_max_retries`
- `test_parsing_failure_preserves_raw_artifact`
- `test_ingestion_failure_creates_error_envelope`
- `test_ingestion_logs_start_retry_partial_completed`

### Validator Tests

- Malformed sources should not silently enter retrieval stores.
- Partial ingestion must carry quality_flags.

## Partition C: Enrichment Tests

### Unit Tests

- `test_generate_embeddings_creates_embedding_for_each_valid_chunk`
- `test_extract_sparse_terms_preserves_exact_identifiers`
- `test_extract_entities_returns_entity_type_aliases_confidence`
- `test_extract_relations_links_subject_object_and_evidence_chunks`
- `test_link_chunks_to_entities_preserves_source_provenance`
- `test_graph_extraction_optional_before_phase_3`

### Error and Logging Tests

- `test_embedding_failure_blocks_vector_index_for_affected_chunk`
- `test_sparse_term_failure_allows_vector_only_degraded_mode`
- `test_entity_extraction_failure_logs_graph_extraction_skipped`
- `test_enrichment_model_failure_creates_error_envelope`

### Validator Tests

- Entity records without evidence chunks should fail graph quality validation.
- Relation records below confidence threshold should not be used as hard facts.

## Partition D: Storage Tests

### Unit Tests

- `test_commit_raw_source_stores_snapshot_reference`
- `test_commit_chunks_preserves_stable_chunk_ids`
- `test_commit_vectors_links_embedding_id_to_chunk_id`
- `test_commit_sparse_index_links_terms_to_chunk_id`
- `test_commit_graph_updates_links_entities_relations_chunks`
- `test_verify_storage_commit_detects_missing_vector`
- `test_verify_access_metadata_detects_missing_access_policy`

### Error and Logging Tests

- `test_vector_commit_retry_is_idempotent`
- `test_metadata_commit_failure_stops_workflow`
- `test_graph_commit_failure_marks_degraded_when_graph_optional`
- `test_storage_rollback_logged_on_failed_commit`

### Validator Tests

- Records missing access metadata must be ineligible for retrieval.
- Partial graph commit must not create unsupported graph paths.

## Partition E: Planner Tests

### Unit Tests

- `test_classify_exact_query_selects_keyword_retrieval`
- `test_classify_semantic_query_selects_vector_or_hybrid_retrieval`
- `test_classify_relationship_query_selects_graph_retrieval_when_enabled`
- `test_classify_fresh_query_selects_external_or_freshness_validation`
- `test_no_retrieval_selected_for_formatting_task`
- `test_set_retrieval_budget_sets_top_k_latency_cost_and_max_repairs`
- `test_enforce_repair_limits_stops_at_max_repair_attempts`

### Error and Logging Tests

- `test_planner_uncertainty_logs_warning`
- `test_policy_conflict_returns_governed_failure`
- `test_planner_logs_query_classification_and_modes`

### Validator Tests

- Planner must not select restricted sources outside access_scope.
- Planner must not choose graph-only retrieval for a broad semantic query unless graph is required.

## Partition F: Retrieval Tests

### Unit Tests

- `test_run_vector_search_returns_semantic_candidates`
- `test_run_keyword_search_returns_exact_phrase_candidates`
- `test_run_hybrid_search_merges_vector_and_keyword_candidates`
- `test_run_graph_traversal_returns_path_and_supporting_chunks`
- `test_run_structured_lookup_respects_filters`
- `test_register_external_result_creates_governed_source_record`
- `test_merge_evidence_candidates_deduplicates_by_chunk_and_source`
- `test_apply_access_filter_excludes_unauthorized_evidence`

### Error and Logging Tests

- `test_vector_search_timeout_logs_retrieval_error`
- `test_keyword_search_failure_allows_partial_candidates`
- `test_external_lookup_failure_marks_freshness_limitation`
- `test_access_filter_failure_fails_closed`

### Validator Tests

- Restricted evidence must be excluded before reranking.
- External evidence must have retrieval date and reliability before ranking.

## Partition G: Ranking Tests

### Unit Tests

- `test_rerank_evidence_orders_by_query_relevance`
- `test_deduplicate_evidence_removes_duplicate_chunks`
- `test_diversify_evidence_set_preserves_source_diversity`
- `test_reranker_respects_source_reliability_weight`
- `test_reranker_respects_freshness_weight_when_required`

### Error and Logging Tests

- `test_reranker_failure_falls_back_to_normalized_retrieval_scores`
- `test_ranking_fallback_logs_degraded_mode`
- `test_deduplication_failure_keeps_source_diverse_top_candidates`

### Validator Tests

- Reranking must not reintroduce excluded evidence.
- Low-relevance evidence should not be selected only because source reliability is high.

## Partition H: Validator Tests

Implementation status: active coverage added in `tests/test_validation.py` and planner integration coverage added in `tests/test_planner_orchestration.py`.

Latest observed results:

- Standard-library unittest discovery: 77 tests passed.
- Function-style test harness: 79 tests passed.

Implemented Milestone 4 checks include access-denied evidence rejection, relevance and sufficiency repair selection, stale evidence freshness repair, contradiction repair handling, claim-level support mapping, validator pass/repair logs, explicit empty required-validation handling, and bounded repair-loop stop behavior.

Planner integration coverage includes `test_validation_repair_blocks_evidence_backed_synthesis_claims`, which verifies that validation repair blocks evidence-backed synthesis claims.

### Unit Tests

- `test_validate_relevance_passes_directly_relevant_evidence`
- `test_validate_relevance_fails_unrelated_evidence`
- `test_validate_sufficiency_fails_single_weak_snippet`
- `test_validate_freshness_flags_stale_source`
- `test_validate_access_fails_unauthorized_evidence`
- `test_validate_citations_requires_source_link_or_reference`
- `test_validate_claim_support_passes_exact_supported_claim`
- `test_validate_claim_support_fails_unsupported_claim`
- `test_detect_contradictions_flags_conflicting_sources`
- `test_choose_repair_action_selects_retrieve_more_for_insufficient_evidence`
- `test_choose_repair_action_selects_clarify_for_under_specified_query`

### Error and Logging Tests

- `test_validator_uncertainty_requests_repair_or_clarification`
- `test_citation_check_failure_stops_source_backed_answer`
- `test_validation_logs_each_required_check`

### Validator Scenario Tests

- `test_validator_rejects_answer_when_evidence_does_not_support_claim`
- `test_validator_accepts_answer_when_claims_have_exact_spans`
- `test_validator_detects_stale_but_reliable_source`
- `test_validator_detects_fresh_but_unreliable_source`
- `test_validator_detects_access_policy_violation`
- `test_validator_repair_loop_stops_at_max_attempts`

## Partition I: Synthesis Tests

### Unit Tests

- `test_generate_answer_uses_only_approved_evidence`
- `test_attach_citations_maps_claims_to_evidence_ids`
- `test_create_claim_records_for_important_claims`
- `test_state_limitations_includes_stale_or_missing_evidence`
- `test_format_output_respects_requested_answer_type`
- `test_synthesis_removes_unsupported_claims`

### Error and Logging Tests

- `test_generation_failure_retries_once`
- `test_citation_attachment_failure_stops_answer`
- `test_synthesis_failure_creates_error_envelope`
- `test_synthesis_logs_answer_generated_and_citations_attached`

### Validator Tests

- Final answer must not include claims absent from claim records.
- Final answer must disclose unresolved contradictions.

## Partition J: Feedback and Evaluation Tests

Implementation status: active Milestone 5 coverage added in `tests/test_feedback_evaluation.py`, `tests/test_feedback_improvement.py`, and `tests/test_evaluation_metrics.py`.

Latest observed results:

- Standard-library unittest discovery: 85 tests passed.
- Pytest suite: 164 tests passed.

Implemented Milestone 5 checks include evaluation case creation, batch metrics for retrieval recall/citation precision/unsupported claims/validator rejection/graph hit/reranker improvement, observability log/error/latency/cost summaries, append-only improvement task creation, task deduplication by failure category, retryable task/report storage failures, and source-policy non-mutation.

### Unit Tests

- `test_capture_feedback_links_request_and_answer`
- `test_classify_failure_labels_retrieval_failure`
- `test_classify_failure_labels_validation_failure`
- `test_update_evaluation_dataset_adds_reviewed_case`
- `test_recommend_system_improvement_creates_task_not_policy_change`
- `test_metric_update_records_latency_cost_and_quality`

### Error and Logging Tests

- `test_feedback_write_failure_preserves_trace_for_retry`
- `test_policy_update_requires_review`
- `test_feedback_logs_failure_classified_and_improvement_created`

### Validator Tests

- User feedback must not automatically change source reliability.
- User correction must become evaluation data before changing retrieval policy.

## Integration Tests

### Ingestion Integration

- `test_public_document_full_ingestion_to_vector_and_keyword_indexes`
- `test_restricted_document_ingestion_preserves_access_policy`
- `test_malformed_document_ingestion_creates_error_and_no_retrievable_chunks`
- `test_optional_graph_extraction_degraded_mode_before_phase_3`

### Retrieval Integration

- `test_exact_query_keyword_to_answer_with_citation`
- `test_semantic_query_vector_to_answer_with_citation`
- `test_general_query_hybrid_to_answer_with_citation`
- `test_relationship_query_graph_to_answer_with_path_provenance`
- `test_fresh_query_external_result_registered_before_ranking`

### Validation Integration

- `test_insufficient_evidence_triggers_repair`
- `test_repair_loop_retrieves_more_then_passes_validation`
- `test_repair_loop_exhaustion_returns_uncertainty`
- `test_contradiction_results_in_conflict_disclosure`
- `test_stale_evidence_results_in_limitation_or_external_lookup`

### Full End-to-End Tests

- `test_e2e_public_source_answer_with_citations`
- `test_e2e_restricted_source_not_leaked`
- `test_e2e_malformed_source_does_not_break_query_flow`
- `test_e2e_graph_query_with_supporting_chunks`
- `test_e2e_feedback_creates_evaluation_case`

## Validator Test Suites

## Validator Suite 1: Evidence Quality

Purpose: ensure the system does not answer with weak or unrelated evidence.

Tests:

- Relevant evidence passes.
- Irrelevant evidence fails.
- Evidence with only keyword overlap but wrong meaning fails.
- Evidence with semantic similarity but no answer support fails.
- Evidence with direct answer and citation passes.

## Validator Suite 2: Access and Governance

Purpose: ensure restricted content cannot leak.

Tests:

- Unauthorized user receives no restricted evidence.
- Restricted evidence is excluded before reranking.
- Missing access_policy_id makes evidence ineligible.
- Unknown license blocks high-risk use.
- External evidence without source record is rejected.

## Validator Suite 3: Freshness and Reliability

Purpose: separate source trust from source recency.

Tests:

- Reliable stale source is flagged stale.
- Fresh unreliable source is flagged low reliability.
- Freshness-required query triggers external lookup or limitation.
- Date-bounded query rejects evidence outside range.
- Source as_of_date appears in validation record.

## Validator Suite 4: Claim-Level Citation

Purpose: ensure answer claims are supported.

Tests:

- Direct quote claim links to exact span.
- Paraphrase claim links to supporting span.
- Table value claim links to table coordinate.
- Graph-path claim links to relation IDs and evidence chunks.
- Inference claim is labeled as inference.
- Unsupported claim is removed or marked uncertain.

## Validator Suite 5: Repair Loops

Purpose: prevent runaway retrieval and planner drift.

Tests:

- Failed sufficiency triggers retrieve_more.
- Failed freshness triggers external_lookup.
- Failed access triggers source exclusion and repair.
- Repeated failed criteria stops at max_repair_attempts.
- Under-specified query triggers clarification.
- Repair trace records previous_actions.

## Validator Suite 6: Output Safety

Purpose: ensure the final answer follows evidence and limitations.

Tests:

- Answer uses only approved evidence.
- Contradictions are disclosed.
- Missing evidence results in uncertainty.
- Citation map covers important claims.
- High-risk output requires validator pass.

## Logging and Error Test Matrix

### Required Logs Per Successful Ingestion

- source_registered
- source_access_checked
- ingestion_started
- extraction_completed
- chunks_committed
- vectors_committed or degraded mode
- sparse_index_committed or degraded mode
- storage_verified
- ingestion_completed

### Required Logs Per Successful Query

- query_classified
- retrieval_modes_selected
- retrieval_budget_set
- retrieval_completed
- evidence_selected
- validation_passed
- claim_records_created
- answer_generated
- feedback_captured when feedback exists

### Required Error Envelopes

- source access failure
- license policy failure
- extraction failure
- embedding failure
- storage commit failure
- planner policy conflict
- retrieval timeout
- reranker failure
- validation failure
- synthesis failure
- feedback write failure

## Acceptance Tests

### Acceptance Test 1: Basic Public Retrieval

Given a public document is registered and ingested, when a user asks a semantic question, the system retrieves relevant evidence, validates it, and returns a cited answer.

Pass criteria:

- Answer cites evidence.
- Logs exist for each partition used.
- No error envelope is created.

### Acceptance Test 2: Restricted Source Protection

Given a restricted source contains the best answer, when an unauthorized user asks the relevant question, the system excludes restricted evidence before ranking.

Pass criteria:

- Restricted chunk is not present in ranked evidence.
- access_decision is denied or excluded.
- Answer states missing accessible evidence if no alternative exists.

### Acceptance Test 3: Validator Rejects Unsupported Claim

Given retrieved evidence does not support the generated claim, the validator rejects the claim.

Pass criteria:

- claim support_status is unsupported.
- Answer is revised, blocked, or marked uncertain.
- Validation log records citation failure.

### Acceptance Test 4: Repair Loop Stops

Given repeated retrieval cannot satisfy the validator, the system stops at max_repair_attempts.

Pass criteria:

- previous_actions are recorded.
- stop_reason is present.
- No unbounded loop occurs.

### Acceptance Test 5: External Source Governance

Given a fresh external source is needed, the system registers the external result before ranking.

Pass criteria:

- Temporary or persisted source record exists.
- retrieved_at and external_link are present.
- reliability and license fields are present.

### Acceptance Test 6: Full Graph Query

Given graph extraction is enabled, when a user asks a relationship question, the system retrieves graph paths and supporting chunks.

Pass criteria:

- relation_ids are present.
- evidence_chunk_ids support the relation.
- Final answer cites source chunks, not just graph edges.

## Regression Test Themes

- Exact identifiers remain findable through keyword retrieval.
- Semantic paraphrases remain findable through vector retrieval.
- Hybrid retrieval outperforms vector-only on mixed queries.
- Restricted sources remain blocked.
- Stale-source handling remains stable.
- Storage bundle recovery rolls back partial writes before retry or failure.
- Local retrieval and ranking load guardrails remain stable on larger in-memory fixture sets.
- Validator does not accept unsupported claims.
- Repair loop limits are enforced.
- Feedback does not automatically alter governance policy.

## Test Completion Definition

The test suite is complete when every partition has unit tests, every protocol boundary has integration tests, every validator requirement has scenario tests, every major failure mode has error/logging tests, and all acceptance tests pass on stable fixtures.
