# Detailed Method: Agent-Orchestrated Hybrid Retrieval Center

## 1. Objective

Create a general, partitioned retrieval center that can ingest many source types, represent knowledge in multiple retrieval stores, route each user request through the best retrieval path, validate evidence, and synthesize source-backed answers.

The design is intentionally modular. Each part communicates through explicit interface protocols so the system can swap models, storage engines, rerankers, graph stores, and validators without redesigning the whole process.

## 2. Core Design Requirements

- General enough for documents, databases, APIs, web sources, logs, tickets, reports, and research papers.
- Partitioned by responsibility: source management, ingestion, enrichment, storage, planning, retrieval, validation, synthesis, feedback.
- Hybrid retrieval by default: vector, keyword, graph, structured lookup, and external retrieval can be combined.
- Agentic only where useful: the planner and validator make decisions, while retrieval tools remain deterministic where possible.
- Evidence-first output: every claim should connect to validated evidence or be marked as uncertain.
- Evaluation-aware: every query should create a trace that can be reviewed, scored, and improved.

## 3. Recommended Stack

### Primary Stack

- LlamaIndex: ingestion, document abstractions, indexing, retrieval adapters.
- Neo4j: knowledge graph, entity relationships, graph traversal, Cypher-based retrieval.
- Qdrant: dense vector retrieval and hybrid dense/sparse retrieval.
- LangGraph: planner workflow, conditional routing, validation loops, repair loops.
- Object store or filesystem: raw source files, extracted text, snapshots, audit artifacts.
- Relational metadata store: source registry, ingestion jobs, traces, evaluations, feedback.

### Model Stack

- Planner model: small-to-medium instruction model.
- Embedding model: domain-appropriate semantic embedding model.
- Sparse model or BM25: exact-term and rare-token retrieval.
- Reranker: dedicated reranker or cross-encoder.
- Extraction model: medium or large model for entity and relation extraction.
- Validator model: strong reasoning-capable model.
- Synthesis model: medium model by default, larger model for high-risk or complex synthesis.

## 4. System Partitions

### Partition A: Source Registry

Owns source identity, access metadata, governance, freshness, and reliability.

Main responsibilities:

- Track source ownership and access method.
- Track external links and internal paths.
- Track refresh schedule and last ingestion.
- Track source reliability and license restrictions.
- Track allowed users, groups, roles, and policy references for access control.
- Decide whether a source is active, deprecated, blocked, or pending review.

### Partition B: Ingestion

Owns extraction and normalization of source content.

Main responsibilities:

- Pull or receive source payloads.
- Extract text, tables, metadata, links, and structure.
- Normalize encoding, dates, headings, and document hierarchy.
- Split content into stable chunks.
- Deduplicate repeated or near-duplicate content.
- Preserve raw source and processed source versions.

### Partition C: Enrichment

Owns computed knowledge fields.

Main responsibilities:

- Generate embeddings.
- Extract keywords and sparse retrieval terms.
- Extract entities and relationships.
- Create chunk summaries and document summaries.
- Link entities to chunks and source records.
- Assign confidence scores to extracted entities and relations.

### Partition D: Storage

Owns persistence and retrieval stores.

Main responsibilities:

- Store raw sources.
- Store chunks and metadata.
- Store vectors.
- Store keyword/sparse index entries.
- Store graph nodes and edges.
- Store audit traces and validation records.

### Partition E: Query Planning

Owns routing decisions.

Main responsibilities:

- Classify query type.
- Estimate freshness requirement.
- Estimate risk level.
- Select retrieval tools.
- Decide whether graph traversal, external retrieval, or iterative retrieval is needed.
- Set retrieval budgets such as top-k, max hops, max loops, and latency target.

### Partition F: Retrieval Execution

Owns search and evidence collection.

Main responsibilities:

- Run selected retrieval tools.
- Apply metadata filters.
- Merge candidates across stores.
- Deduplicate candidates.
- Normalize result scores.
- Return evidence candidates with provenance.

### Partition G: Evidence Ranking

Owns relevance scoring and evidence selection.

Main responsibilities:

- Rerank candidates against the user query and retrieval objective.
- Balance relevance, diversity, source reliability, and recency.
- Remove weak or duplicate evidence.
- Preserve enough context for validation.

### Partition H: Validation

Owns quality control before answer generation.

Main responsibilities:

- Check evidence relevance.
- Check evidence sufficiency.
- Check citation support.
- Check freshness.
- Detect contradictions.
- Decide pass, repair, clarify, or fail.

### Partition I: Synthesis

Owns final user-facing output.

Main responsibilities:

- Generate answer from validated evidence.
- Cite supporting evidence.
- State uncertainty and conflicts.
- Avoid unsupported claims.
- Provide structured output when requested.

### Partition J: Feedback and Evaluation

Owns learning from system behavior.

Main responsibilities:

- Store query traces and outcomes.
- Capture user ratings and corrections.
- Track retrieval, validation, and synthesis metrics.
- Build evaluation datasets.
- Identify recurring failure modes.

## 5. Core Data Fields

### Shared Error Envelope

- error_id: stable error identifier.
- correlation_id: request, ingestion job, or workflow trace identifier.
- partition: source_registry, ingestion, enrichment, storage, planning, retrieval, ranking, validation, synthesis, feedback.
- operation_name: function or process step that failed.
- severity: info, warning, recoverable, critical.
- error_type: access, timeout, parsing, extraction, model, storage, validation, policy, network, unknown.
- error_message: concise human-readable failure description.
- retryable: true or false.
- retry_count: number of attempts already made.
- max_retries: maximum allowed retry attempts.
- fallback_action: skip, retry, partial_commit, repair, clarify, stop, escalate.
- created_at: timestamp.

### Shared Log Event

- log_id: stable log event identifier.
- correlation_id: request, ingestion job, or workflow trace identifier.
- partition: source_registry, ingestion, enrichment, storage, planning, retrieval, ranking, validation, synthesis, feedback.
- event_type: start, success, warning, error, retry, fallback, decision, metric.
- operation_name: function or process step being logged.
- input_reference: source_id, document_id, request_id, plan_id, evidence_id, or answer_id.
- output_reference: created or updated artifact identifier.
- duration_ms: elapsed time when available.
- cost_estimate: optional model, API, storage, or retrieval cost estimate.
- model_or_tool: model, connector, database, or service used.
- message: concise event message.
- created_at: timestamp.

### Source Record

- source_id: stable source identifier.
- source_name: human-readable name.
- source_type: document, database, API, web, log, ticket, report, paper, repository, other.
- owner: person, team, or system responsible.
- access_method: upload, connector, URL, API, database, filesystem, manual.
- external_link: HTTP or HTTPS link where applicable.
- internal_location: local path, object-store key, database reference, or connector reference.
- license_policy: allowed, restricted, confidential, unknown.
- license_constraints: usage limits, redistribution limits, citation rules, retention limits.
- access_policy_id: linked access-control policy.
- allowed_principals: users, groups, roles, or services allowed to retrieve the source.
- reliability_level: high, medium, low, unverified.
- reliability_score: numeric score used for ranking and validation.
- freshness_policy: static, scheduled, event-driven, real-time, manual.
- freshness_sla: maximum acceptable source age by risk level or use case.
- refresh_interval: expected refresh cycle.
- last_checked_at: latest source availability check.
- last_ingested_at: latest successful ingestion.
- status: active, pending, deprecated, blocked, failed.
- notes: human-readable source notes.

### Ingestion Job

- ingestion_job_id: stable ingestion run identifier.
- source_id: linked source record.
- trigger_type: manual, scheduled, webhook, dependency, repair.
- started_at: job start timestamp.
- completed_at: job completion timestamp.
- status: queued, running, completed, failed, partial.
- input_version: source version or snapshot identifier.
- output_version: processed version identifier.
- error_summary: short failure description.
- error_ids: linked shared error records.
- log_ids: linked ingestion log events.
- quality_flags: extraction issues, missing metadata, duplicate content, broken links.

### Document Record

- document_id: stable document identifier.
- source_id: linked source.
- title: document title.
- author_or_owner: creator or responsible owner.
- published_at: publication or release date.
- retrieved_at: retrieval date.
- document_type: PDF, HTML, markdown, database row set, API response, transcript, other.
- language: detected or declared language.
- canonical_url: preferred external link.
- checksum: content fingerprint.
- version: document version.
- access_level: public, internal, confidential, restricted.
- as_of_date: date the document claims to represent.
- valid_from: optional start date for time-bounded facts.
- valid_to: optional end date for time-bounded facts.
- access_policy_id: inherited or document-specific access policy.

### Chunk Record

- chunk_id: stable chunk identifier.
- document_id: linked document.
- source_id: linked source.
- chunk_index: chunk position in document.
- heading_path: section hierarchy.
- text: chunk text.
- token_count: estimated token count.
- page_number: page reference when available.
- start_offset: source text start position.
- end_offset: source text end position.
- created_at: chunk creation timestamp.
- embedding_id: linked vector record.
- sparse_terms_id: linked sparse index record.
- quality_flags: OCR issue, table fragment, low text quality, duplicate, short chunk.
- access_policy_id: inherited or chunk-specific access policy.
- allowed_principals: users, groups, roles, or services allowed to retrieve this chunk.
- as_of_date: date represented by the chunk content.
- valid_from: optional start date for chunk facts.
- valid_to: optional end date for chunk facts.

### Entity Record

- entity_id: stable entity identifier.
- entity_name: canonical entity label.
- entity_type: person, organization, product, concept, date, location, dataset, system, method, paper, other.
- aliases: known alternative names.
- description: short definition.
- confidence: extraction or resolution confidence.
- source_ids: sources supporting the entity.
- first_seen_at: first observed timestamp.
- last_seen_at: latest observed timestamp.

### Relation Record

- relation_id: stable relation identifier.
- subject_entity_id: source node.
- relation_type: depends_on, authored_by, cites, belongs_to, caused_by, updates, contradicts, supports, similar_to, other.
- object_entity_id: target node.
- evidence_chunk_ids: chunks supporting the relation.
- confidence: relation confidence.
- valid_from: optional start date.
- valid_to: optional end date.
- extracted_at: extraction timestamp.

### Retrieval Request

- request_id: stable request identifier.
- user_query: original request.
- normalized_query: planner-normalized objective.
- user_context: optional user or session context.
- required_freshness: none, recent, date-bounded, real-time.
- risk_level: low, medium, high.
- output_intent: answer, comparison, summary, audit, extraction, recommendation.
- constraints: filters, date range, source types, access restrictions.

### Retrieval Plan

- plan_id: stable plan identifier.
- request_id: linked request.
- query_type: exact, semantic, entity, graph, multi-hop, fresh-data, high-risk, mixed.
- selected_modes: no_retrieval, keyword, vector, hybrid, graph, database, API, external, iterative.
- retrieval_budget: top-k, max graph hops, max loops, latency target, cost target.
- repair_attempt: current repair-loop attempt number.
- max_repair_attempts: hard upper limit for repair loops.
- previous_actions: retrieval or repair actions already attempted.
- required_validations: relevance, sufficiency, freshness, citation, contradiction, access.
- fallback_actions: rewrite, expand_graph, add_keyword, add_vector, external_lookup, clarify, fail_with_uncertainty.
- plan_reason: short explanation for traceability.

### Evidence Candidate

- evidence_id: stable evidence identifier.
- request_id: linked request.
- retrieval_mode: keyword, vector, graph, database, API, external.
- source_id: linked source.
- document_id: linked document.
- chunk_id: linked chunk when applicable.
- entity_ids: related entities.
- relation_ids: related graph relations.
- text_snippet: candidate evidence text.
- score: raw retrieval score.
- normalized_score: comparable score across modes.
- source_reliability: inherited source rating.
- published_at: source publication date.
- retrieved_at: retrieval timestamp.
- citation_link: canonical citation URL or source reference.
- access_scope: user, group, role, or service scope used for retrieval.
- access_decision: allowed, denied, redacted, unknown.
- exclusion_reason: reason evidence was excluded by access, license, freshness, or quality rules.
- license_constraints: inherited license constraints for downstream use.

### Claim Record

- claim_id: stable claim identifier.
- answer_id: linked answer when available.
- request_id: linked request.
- claim_text: atomic claim made or proposed by the synthesis model.
- support_type: direct_quote, paraphrase, table_value, graph_path, inference, unsupported.
- evidence_id: linked evidence item.
- evidence_span: exact text span, page range, offset range, table cell, or graph path supporting the claim.
- source_quote: short supporting excerpt when allowed.
- support_status: supported, partially_supported, contradicted, unsupported, not_checked.
- confidence: claim-level support confidence.
- validator_notes: concise claim-level validation explanation.

### Ranked Evidence

- ranked_evidence_id: stable ranked item identifier.
- evidence_id: linked evidence candidate.
- rank: selected order.
- rerank_score: reranker score.
- relevance_label: high, medium, low.
- diversity_group: topic, entity, source, or cluster label.
- selection_reason: why the item was retained.

### Validation Record

- validation_id: stable validation identifier.
- request_id: linked request.
- evidence_ids: evidence reviewed.
- validation_status: pass, repair_needed, clarification_needed, fail.
- relevance_score: evidence relevance estimate.
- sufficiency_score: answerability estimate.
- freshness_status: fresh, acceptable, stale, unknown.
- contradiction_status: none, possible, confirmed.
- citation_status: complete, partial, missing, weak.
- unsupported_claim_risk: low, medium, high.
- repair_action: none, rewrite, expand_graph, retrieve_more, external_lookup, clarify, stop.
- failed_criteria: validation criteria that failed.
- stop_reason: why the system stopped repairing or declined to answer.
- validator_notes: concise explanation.

### Answer Record

- answer_id: stable answer identifier.
- request_id: linked request.
- validation_id: linked validation.
- answer_text: final answer.
- citation_map: claims linked to evidence IDs.
- claim_records: claim-level support records for important answer claims.
- confidence_level: high, medium, low.
- limitations: missing evidence, stale source, contradiction, access limitation.
- generated_at: answer timestamp.
- model_used: synthesis model identifier.

### Feedback Record

- feedback_id: stable feedback identifier.
- request_id: linked request.
- answer_id: linked answer.
- user_rating: useful, partially useful, not useful, incorrect.
- correction_text: user correction.
- failure_category: retrieval, ranking, validation, synthesis, freshness, access, unclear_query.
- reviewed_by: user, evaluator, system.
- created_at: feedback timestamp.

## 6. Interface Protocols Between Parts

### Shared Try/Error Protocol

Every partition should wrap its main operation in the same conceptual try/error pattern:

1. Log start event with correlation_id and operation_name.
2. Validate required input fields.
3. Execute operation.
4. If operation succeeds, log success event with output_reference, duration, and quality flags.
5. If operation fails with a retryable error, log error event, increment retry_count, and retry until max_retries.
6. If retries fail or error is non-retryable, create shared error envelope.
7. Apply fallback_action according to partition rules.
8. Return either a valid output, partial output with quality flags, or a stop reason.

Default fallback rules:

- Source registry: block source or mark pending review.
- Ingestion: retry, then partial ingest or fail job.
- Enrichment: continue without optional enrichment when allowed.
- Storage: stop on unsafe partial commit unless rollback or idempotent retry is available.
- Planning: use conservative default hybrid retrieval or ask clarification.
- Retrieval: return partial candidates with retrieval_errors.
- Ranking: fall back to normalized retrieval scores when reranker fails.
- Validation: fail closed for high-risk outputs, request repair for medium-risk outputs.
- Synthesis: return uncertainty or structured failure when validated evidence is insufficient.
- Feedback: log failure and preserve original trace without changing policies.

### Protocol 1: Source Registration Protocol

Producer: user, connector, admin, scheduler.

Consumer: source registry.

Input fields:

- source_name
- source_type
- owner
- access_method
- external_link
- internal_location
- license_policy
- license_constraints
- access_policy_id
- allowed_principals
- reliability_level
- reliability_score
- freshness_policy
- freshness_sla

Output fields:

- source_id
- status
- registration_notes

Relevant functions:

- register_source
- update_source_status
- check_source_access
- apply_source_policy

### Protocol 2: Ingestion Protocol

Producer: source registry or scheduler.

Consumer: ingestion pipeline.

Input fields:

- source_id
- input_version
- trigger_type
- access_method
- internal_location
- external_link
- access_policy_id
- license_constraints

Output fields:

- ingestion_job_id
- document_records
- raw_artifact_references
- extraction_quality_flags

Relevant functions:

- start_ingestion_job
- extract_source_content
- normalize_document
- create_document_record

### Protocol 3: Chunking Protocol

Producer: ingestion pipeline.

Consumer: enrichment pipeline and storage.

Input fields:

- document_id
- normalized_text
- document_structure
- metadata

Output fields:

- chunk_records
- chunk_quality_flags

Relevant functions:

- split_document_into_chunks
- assign_chunk_ids
- preserve_chunk_offsets

### Protocol 4: Enrichment Protocol

Producer: chunking pipeline.

Consumer: vector index, keyword index, graph store, metadata store.

Input fields:

- chunk_records
- document_record
- source_record

Output fields:

- embeddings
- sparse_terms
- entity_records
- relation_records
- summaries
- enrichment_quality_flags

Relevant functions:

- generate_embeddings
- extract_sparse_terms
- extract_entities
- extract_relations
- link_chunks_to_entities

### Protocol 5: Storage Commit Protocol

Producer: enrichment pipeline.

Consumer: storage layer.

Input fields:

- source_record
- document_records
- chunk_records
- embeddings
- sparse_terms
- entity_records
- relation_records

Output fields:

- commit_id
- index_status
- graph_status
- storage_quality_flags

Relevant functions:

- commit_raw_source
- commit_chunks
- commit_vectors
- commit_sparse_index
- commit_graph_updates
- verify_storage_commit
- verify_access_metadata

### Protocol 6: Query Intake Protocol

Producer: user interface, API, automation, agent.

Consumer: planner agent.

Input fields:

- user_query
- user_context
- constraints
- access_scope
- output_intent

Output fields:

- request_id
- normalized_query
- initial_risk_level

Relevant functions:

- create_retrieval_request
- normalize_query
- assign_access_scope
- verify_user_access_scope

### Protocol 7: Planning Protocol

Producer: planner agent.

Consumer: retrieval execution layer.

Input fields:

- retrieval_request
- source_availability
- access_scope
- prior_feedback_patterns

Output fields:

- retrieval_plan
- selected_modes
- retrieval_budget
- repair_attempt
- max_repair_attempts
- fallback_actions

Relevant functions:

- classify_query
- select_retrieval_modes
- set_retrieval_budget
- define_fallback_actions
- enforce_repair_limits

### Protocol 8: Retrieval Execution Protocol

Producer: retrieval execution layer.

Consumer: vector index, keyword index, graph store, database connectors, API connectors, external retrieval.

Input fields:

- retrieval_plan
- normalized_query
- filters
- retrieval_budget
- access_scope

Output fields:

- evidence_candidates
- access_decisions
- retrieval_trace
- retrieval_errors

Relevant functions:

- run_vector_search
- run_keyword_search
- run_hybrid_search
- run_graph_traversal
- run_structured_lookup
- run_external_lookup
- apply_access_filter
- register_external_result
- merge_evidence_candidates

### Protocol 9: Ranking Protocol

Producer: retrieval execution layer.

Consumer: reranker.

Input fields:

- user_query
- normalized_query
- evidence_candidates
- ranking_policy

Output fields:

- ranked_evidence
- discarded_evidence
- ranking_trace

Relevant functions:

- rerank_evidence
- deduplicate_evidence
- diversify_evidence_set

### Protocol 10: Validation Protocol

Producer: reranker.

Consumer: validator agent.

Input fields:

- retrieval_request
- retrieval_plan
- ranked_evidence
- source_metadata
- required_validations

Output fields:

- validation_record
- repair_action
- approved_evidence

Relevant functions:

- validate_relevance
- validate_sufficiency
- validate_freshness
- validate_citations
- validate_access
- validate_claim_support
- detect_contradictions
- choose_repair_action

### Protocol 11: Repair Protocol

Producer: validator agent.

Consumer: planner agent and retrieval execution layer.

Input fields:

- validation_record
- repair_action
- failed_criteria
- prior_retrieval_trace
- repair_attempt
- max_repair_attempts
- previous_actions

Output fields:

- revised_retrieval_plan
- clarification_question
- stop_reason

Relevant functions:

- rewrite_query
- expand_graph_scope
- broaden_retrieval
- narrow_retrieval
- request_external_lookup
- request_clarification
- stop_with_uncertainty

### Protocol 12: Synthesis Protocol

Producer: validator agent.

Consumer: synthesis agent.

Input fields:

- user_query
- normalized_query
- approved_evidence
- validation_record
- output_intent
- constraints

Output fields:

- answer_record
- citation_map
- claim_records
- limitations

Relevant functions:

- generate_answer
- create_claim_records
- attach_citations
- state_limitations
- format_output

### Protocol 13: Feedback Protocol

Producer: user, evaluator, monitoring system.

Consumer: feedback and evaluation layer.

Input fields:

- request_id
- answer_id
- user_rating
- correction_text
- observed_failure

Output fields:

- feedback_record
- evaluation_update
- improvement_task

Relevant functions:

- capture_feedback
- classify_failure
- update_evaluation_dataset
- recommend_system_improvement

## 7. End-to-End Flow

### Data Preparation Flow

1. Register source and log source_registered.
2. Check source access and license policy; on failure, create error envelope and mark pending review or blocked.
3. Start ingestion job and log ingestion_started.
4. Try to extract source content; on retryable failure, retry, then preserve raw artifact and mark failed or partial.
5. Normalize document and log normalization warnings.
6. Create document record with access, freshness, and reliability fields.
7. Split document into chunks and log chunk quality flags.
8. Generate embeddings and sparse terms; on partial failure, record degraded retrieval modes.
9. Optionally extract entities and relations when the graph layer is enabled.
10. Optionally link chunks, entities, relations, and sources when graph storage is enabled.
11. Commit vectors, sparse index entries, chunks, metadata, and optional graph updates with idempotent retries.
12. Verify storage commit and access metadata; stop eligibility for records that fail access metadata checks.
13. Mark ingestion job complete, failed, or partial and log final status.

### Query Answering Flow

1. Receive user query and create correlation_id.
2. Create retrieval request and log query intake.
3. Planner classifies query type and risk; on uncertainty, choose conservative hybrid retrieval or ask clarification.
4. Planner selects retrieval modes, budgets, retry limits, and max repair attempts.
5. If no retrieval is selected, create a direct-response record with the reason and citation requirement.
6. Retrieval layer applies access filters and runs selected tools with try/error logging per tool.
7. External retrieval results are registered as temporary or persisted source records before ranking.
8. Results are merged, normalized, deduplicated, and excluded when access or license rules fail.
9. Reranker filters and prioritizes evidence; on reranker failure, fall back to normalized retrieval scores.
10. Validator checks evidence quality and claim-level support.
11. If validation fails, planner repairs the retrieval plan until max repair attempts are reached.
12. If repair attempts are exhausted, return uncertainty, clarification, or governed failure reason.
13. If validation passes, synthesis agent writes the answer.
14. Answer is stored with citation map, claim records, logs, and trace.
15. Feedback is captured as evaluation input; policy or routing changes require review before adoption.

## 8. Minimal Function Layout

The following functions are conceptual responsibilities, not implementation code.

### Source and Ingestion

- register_source: create or update a source record.
- check_source_access: verify that the source can be reached and used.
- apply_source_policy: enforce access and license rules for source use.
- start_ingestion_job: create a tracked ingestion run.
- extract_source_content: obtain raw content from the source.
- normalize_document: clean and normalize extracted content.
- split_document_into_chunks: create stable chunks from normalized content.

### Enrichment and Storage

- generate_embeddings: create vector representations for chunks.
- extract_sparse_terms: create exact-match retrieval terms.
- extract_entities: identify entities in source content.
- extract_relations: identify relationships between entities.
- link_chunks_to_entities: connect graph objects to evidence chunks.
- commit_storage_updates: persist chunks, vectors, sparse terms, graph records, and metadata.
- verify_storage_commit: confirm all required stores are synchronized.
- verify_access_metadata: confirm records carry enforceable access and license fields.

### Planning and Retrieval

- create_retrieval_request: capture user query and constraints.
- classify_query: determine query type, risk, and freshness requirement.
- select_retrieval_modes: choose keyword, vector, hybrid, graph, external, or iterative retrieval.
- set_retrieval_budget: define top-k, graph hops, loops, cost, and latency.
- enforce_repair_limits: stop repeated repair loops according to budget and policy.
- run_retrieval_plan: execute selected retrieval tools.
- apply_access_filter: remove or redact unauthorized evidence before ranking.
- register_external_result: create governed source and document records for external retrieval results.
- merge_evidence_candidates: combine results across retrieval modes.

### Ranking and Validation

- rerank_evidence: score candidates against the query.
- deduplicate_evidence: remove repeated or near-repeated candidates.
- validate_evidence: run relevance, sufficiency, freshness, citation, and contradiction checks.
- validate_claim_support: check exact support spans for important answer claims.
- validate_access: confirm approved evidence is allowed for the user and output context.
- choose_repair_action: decide whether to retrieve more, clarify, or stop.

### Synthesis and Feedback

- generate_answer: produce answer from approved evidence.
- create_claim_records: create claim-level support records before or during citation attachment.
- attach_citations: connect answer claims to evidence IDs.
- state_limitations: expose uncertainty, conflicts, or missing evidence.
- capture_feedback: store user or evaluator feedback.
- classify_failure: label root cause for improvement.

## 9. Routing Logic

### No Retrieval

Use when the request is conversational, asks about already provided context, or requires formatting rather than new knowledge.

Required record:

- direct_response_reason: why retrieval was skipped.
- citation_required: whether the answer still needs citations.
- allowed_answer_type: conversational, formatting, transformation, explanation from provided context.
- audit_trace: record showing that no external or indexed evidence was used.

### Keyword Retrieval

Use when the query contains exact phrases, identifiers, legal clauses, error messages, product codes, dates, or names.

### Vector Retrieval

Use when the query is semantic, exploratory, vague, conceptual, or likely expressed differently from stored documents.

### Hybrid Keyword-Vector Retrieval

Use as the default for general source-backed questions.

### Graph Retrieval

Use when the query involves relationships, dependencies, ownership, lineage, influence, timelines, or multi-hop reasoning.

### External Retrieval

Use when freshness is required, internal evidence is missing, or the user explicitly asks for recent or external sources.

### Iterative Retrieval

Use when validation finds insufficient evidence, contradictions, unresolved entities, low citation support, or stale sources.

Hard stopping rules:

- Stop when max_repair_attempts is reached.
- Stop when the same failed_criteria repeats without improved evidence.
- Stop when access rules block the needed evidence.
- Stop when freshness requirements cannot be met.
- Escalate to clarification when the query is under-specified.
- Return uncertainty when reliable evidence is unavailable.

## 9A. Access and Governance Rules

- Retrieval must apply access filters before ranking.
- Unauthorized evidence must not be passed to reranking, validation, or synthesis unless redacted according to policy.
- Every evidence candidate should carry access_decision and exclusion_reason.
- External retrieval must create temporary or persisted source and document records before merging with internal evidence.
- Feedback cannot automatically change source reliability, routing policy, or access status without review.
- Source reliability and freshness are separate signals: a reliable source can be stale, and a fresh source can be unreliable.

## 9B. Claim-Level Citation Rules

- Important answer claims should become claim records.
- Each claim should link to exact evidence spans where possible.
- Direct source support, paraphrase, graph-path support, and inference should be labeled separately.
- Unsupported or partially supported claims should be removed, revised, or marked as uncertain.
- Table values, page references, offsets, and graph paths should be preserved when available.

## 10. Storage Partitioning

### Raw Source Store

Stores original source snapshots and extracted artifacts for audit and reprocessing.

### Metadata Store

Stores source records, document records, ingestion jobs, traces, validation records, answer records, and feedback records.

### Vector Store

Stores chunk embeddings and vector retrieval metadata.

### Sparse or Keyword Store

Stores lexical index data for exact and rare-term retrieval.

### Graph Store

Stores entities, relations, evidence links, temporal fields, and provenance paths.

### Evaluation Store

Stores benchmark queries, expected evidence, answer ratings, failure labels, and regression results.

## 11. Quality Gates

### Ingestion Quality Gate

Checks extraction quality, chunk completeness, duplicate content, missing dates, broken links, and source availability.

### Enrichment Quality Gate

Checks embedding coverage, entity confidence, relation confidence, graph duplicates, and chunk-entity alignment.

### Retrieval Quality Gate

Checks whether retrieved evidence covers query entities, subquestions, and source constraints.

### Validation Quality Gate

Checks relevance, sufficiency, freshness, citation support, and contradictions.

### Output Quality Gate

Checks that the final answer only uses approved evidence, includes citations, and states limitations.

## 11A. Partition Logging Plan

Each partition keeps its own log stream. All streams share correlation_id so one request or ingestion job can be reconstructed across the whole system.

### Source Registry Log

Records source creation, updates, access checks, license checks, source status changes, reliability changes, and policy review outcomes.

Useful events:

- source_registered
- source_access_checked
- source_policy_applied
- source_blocked
- source_marked_pending_review

### Ingestion Log

Records ingestion job start, source fetch, extraction success, extraction failures, normalization issues, partial ingestion, retries, and completion.

Useful events:

- ingestion_started
- source_fetch_failed
- extraction_completed
- normalization_warning
- ingestion_retry
- ingestion_partial
- ingestion_completed

### Enrichment Log

Records embedding generation, sparse-term extraction, entity extraction, relation extraction, optional graph extraction skips, quality warnings, and model failures.

Useful events:

- embeddings_generated
- sparse_terms_extracted
- entity_extraction_completed
- relation_extraction_completed
- graph_extraction_skipped
- enrichment_model_failed
- enrichment_completed

### Storage Log

Records commits to raw store, metadata store, vector store, keyword index, graph store, access metadata checks, rollback, retry, and commit verification.

Useful events:

- raw_source_committed
- chunks_committed
- vectors_committed
- sparse_index_committed
- graph_updates_committed
- storage_commit_failed
- storage_rollback
- storage_verified

### Planner Log

Records query classification, selected retrieval modes, risk assessment, freshness requirement, budgets, no-retrieval decisions, repair decisions, and stop decisions.

Useful events:

- query_classified
- retrieval_modes_selected
- retrieval_budget_set
- no_retrieval_selected
- repair_plan_created
- repair_limit_reached
- clarification_required

### Retrieval Log

Records execution of vector, keyword, graph, database, API, and external retrieval. Also records access filtering, redactions, exclusions, timeouts, and partial retrieval.

Useful events:

- vector_search_started
- keyword_search_started
- graph_traversal_started
- external_lookup_started
- external_result_registered
- access_filter_applied
- evidence_excluded
- retrieval_partial
- retrieval_completed

### Ranking Log

Records reranker start, reranker failure, fallback to retrieval scores, deduplication, diversity balancing, and final ranked evidence selection.

Useful events:

- rerank_started
- rerank_completed
- rerank_failed
- ranking_fallback_used
- evidence_deduplicated
- evidence_selected

### Validation Log

Records relevance checks, sufficiency checks, freshness checks, access checks, citation checks, claim-level support checks, contradictions, validation status, and repair recommendations.

Useful events:

- validation_started
- relevance_checked
- sufficiency_checked
- freshness_checked
- access_validated
- claim_support_checked
- contradiction_detected
- validation_passed
- validation_failed

### Synthesis Log

Records answer generation, citation attachment, claim record creation, limitation statements, unsupported claim removal, and synthesis failures.

Useful events:

- synthesis_started
- answer_generated
- citations_attached
- claim_records_created
- unsupported_claim_removed
- limitations_added
- synthesis_failed

### Feedback and Evaluation Log

Records feedback capture, failure classification, evaluation updates, metric updates, improvement tasks, and policy-review decisions.

Useful events:

- feedback_captured
- failure_classified
- evaluation_dataset_updated
- metric_updated
- improvement_task_created
- policy_review_completed

## 11B. Error Handling Rules By Partition

### Source Registry Errors

- Access failure: mark source pending review or blocked.
- License uncertainty: block downstream retrieval until reviewed.
- Missing owner: allow registration only as pending review.

### Ingestion Errors

- Network timeout: retry within max_retries.
- Parsing failure: preserve raw artifact, mark extraction failed, and create error envelope.
- Partial extraction: continue only if minimum text and metadata thresholds are met.

### Enrichment Errors

- Embedding failure: block vector indexing for affected chunks.
- Sparse-term extraction failure: continue with vector-only if policy allows.
- Entity or relation extraction failure: continue without graph update in Phase 1 or Phase 2.

### Storage Errors

- Vector commit failure: retry idempotently.
- Metadata commit failure: stop the workflow because traceability is compromised.
- Graph commit failure: continue only if graph is optional for the current phase and record degraded mode.
- Access metadata failure: stop retrieval eligibility for affected records.

### Planner Errors

- Classification uncertainty: choose conservative hybrid retrieval or ask clarification.
- Policy conflict: stop and return governed failure reason.
- Repair loop exhaustion: stop with uncertainty or clarification request.

### Retrieval Errors

- One retrieval mode fails: continue with other modes only if validation can still pass.
- Access filter failure: fail closed and exclude evidence.
- External lookup failure: continue with internal evidence and mark freshness limitation.

### Ranking Errors

- Reranker failure: fall back to normalized retrieval scores and log degraded ranking.
- Deduplication failure: keep source-diverse top candidates and require validator review.

### Validation Errors

- Validator uncertainty: request repair or clarification.
- Citation check failure: remove unsupported claims or stop answer generation.
- Access validation failure: exclude evidence and repair retrieval.

### Synthesis Errors

- Generation failure: retry once with the same approved evidence.
- Citation attachment failure: stop source-backed answer and return failure reason.
- Unsupported claim detected after generation: revise answer or remove claim.

### Feedback Errors

- Feedback write failure: preserve local trace and retry later.
- Policy update failure: do not apply automatic changes; create review task.

## 12. Bottleneck-Aware Design Choices

- Keep planner decisions simple and traceable.
- Use deterministic retrieval tools where possible.
- Avoid making every query multi-agent.
- Run graph retrieval only when the query benefits from relationships.
- Use reranking after broad recall, not before.
- Use validator repair loops with strict maximum loop counts.
- Separate source freshness from source reliability.
- Store all intermediate traces for later debugging.

## 13. Success Metrics

- Retrieval recall.
- Citation precision.
- Unsupported claim rate.
- Validator rejection rate.
- Repair-loop success rate.
- Entity resolution accuracy.
- Graph hit rate.
- Reranker improvement.
- Freshness compliance.
- User usefulness rating.
- Latency per query.
- Cost per query.

## 14. Implementation Phases

### Phase 1: Source and Hybrid Text Retrieval

Build source registry, ingestion, chunking, metadata, vector retrieval, keyword retrieval, reranking, cited synthesis, and feedback capture.

### Phase 2: Planner and Traceability

Add planner routing, query classification, retrieval budgets, traces, and basic repair actions.

### Phase 3: Graph Layer

Add entity extraction, relation extraction, graph store, graph traversal, and chunk-to-entity linking.

### Phase 4: Validator Agent

Add validation records, citation checks, sufficiency checks, freshness checks, contradiction checks, and controlled repair loops.

### Phase 5: Evaluation and Optimization

Add evaluation datasets, dashboards, regression tests, cost-quality tuning, source freshness monitoring, and model-routing policies.

## 15. Expected Output Artifacts

- Source registry.
- Ingestion records.
- Document and chunk index.
- Entity and relation graph.
- Vector and keyword indexes.
- Retrieval plans.
- Evidence candidates.
- Ranked evidence sets.
- Validation records.
- Answer records.
- Feedback records.
- Evaluation reports.

## 16. Governance Notes

- Do not ingest sources without access rights.
- Mark source reliability separately from freshness.
- Preserve external links and retrieval dates.
- Keep raw source snapshots for audit where policy allows.
- Require stronger validation for high-risk domains.
- Record when answers rely on stale, conflicting, or incomplete evidence.
