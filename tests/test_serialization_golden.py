import json
from datetime import UTC, date, datetime

from planning import DirectResponseDecision, PlannerTrace, RepairExecutionTrace
from planning.orchestration_runtime import (
    OrchestrationCapability,
    OrchestrationHealthCheck,
    OrchestrationRunResult,
    OrchestrationRuntimeConfig,
    OrchestrationStatus,
)
from shared import (
    AccessDecision,
    AccessLevel,
    AnswerRecord,
    ChunkRecord,
    ClaimRecord,
    ConfidenceLevel,
    CitationStatus,
    ContradictionStatus,
    DocumentRecord,
    DocumentType,
    EntityRecord,
    EntityType,
    EnvironmentName,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    EvidenceCandidate,
    FallbackAction,
    FailureCategory,
    FeedbackRecord,
    FreshnessStatus,
    IngestionJob,
    IngestionStatus,
    IngestionTriggerType,
    LogEvent,
    LogEventType,
    OutputIntent,
    Partition,
    PlanFallbackAction,
    QueryType,
    RankedEvidence,
    RelevanceLabel,
    RelationRecord,
    RelationType,
    ReliabilityLevel,
    RepairAction,
    RequiredFreshness,
    ReviewerType,
    RetrievalMode,
    RetrievalPlan,
    RetrievalRequest,
    RiskLevel,
    SourceRecord,
    SourceType,
    StackComponent,
    StackComponentCategory,
    StackComponentType,
    SupportStatus,
    SupportType,
    UserRating,
    ValidationCriterion,
    ValidationRecord,
    ValidationStatus,
    get_baseline_component,
    get_baseline_stack,
    get_environment_profile,
    serialize_environment_profile,
    serialize_environment_profiles,
    serialize_stack_component,
    serialize_stack_components,
)


CREATED_AT = datetime(2026, 5, 21, 10, 30, 45, tzinfo=UTC)
PUBLISHED_AT = date(2026, 5, 20)


def _json_roundtrip(payload):
    return json.loads(json.dumps(payload))


def test_shared_contracts_to_dict_golden_output() -> None:
    error = ErrorEnvelope(
        correlation_id="corr_serialization",
        partition=Partition.PLANNING,
        operation_name="plan_request",
        severity=ErrorSeverity.RECOVERABLE,
        error_type=ErrorType.POLICY,
        error_message="planning policy rejected input",
        retryable=True,
        fallback_action=FallbackAction.CLARIFY,
        retry_count=1,
        max_retries=2,
        error_id="err_serialization",
        created_at=CREATED_AT,
        details={
            "partitions": [Partition.PLANNING, Partition.RETRIEVAL],
            "window": {"as_of": PUBLISHED_AT, "checked_at": CREATED_AT},
        },
    )
    log = LogEvent(
        correlation_id="corr_serialization",
        partition=Partition.PLANNING,
        event_type=LogEventType.DECISION,
        operation_name="create_retrieval_plan",
        message="Created plan.",
        input_reference="req_serialization",
        output_reference="plan_serialization",
        duration_ms=12.5,
        cost_estimate=0.01,
        model_or_tool="planner",
        log_id="log_serialization",
        created_at=CREATED_AT,
        details={"selected_modes": [RetrievalMode.HYBRID], "as_of": PUBLISHED_AT},
    )

    assert error.to_dict() == {
        "correlation_id": "corr_serialization",
        "partition": "planning",
        "operation_name": "plan_request",
        "severity": "recoverable",
        "error_type": "policy",
        "error_message": "planning policy rejected input",
        "retryable": True,
        "fallback_action": "clarify",
        "retry_count": 1,
        "max_retries": 2,
        "error_id": "err_serialization",
        "created_at": "2026-05-21T10:30:45+00:00",
        "details": {
            "partitions": ["planning", "retrieval"],
            "window": {
                "as_of": "2026-05-20",
                "checked_at": "2026-05-21T10:30:45+00:00",
            },
        },
    }
    assert log.to_dict() == {
        "correlation_id": "corr_serialization",
        "partition": "planning",
        "event_type": "decision",
        "operation_name": "create_retrieval_plan",
        "message": "Created plan.",
        "input_reference": "req_serialization",
        "output_reference": "plan_serialization",
        "duration_ms": 12.5,
        "cost_estimate": 0.01,
        "model_or_tool": "planner",
        "log_id": "log_serialization",
        "created_at": "2026-05-21T10:30:45+00:00",
        "details": {"selected_modes": ["hybrid"], "as_of": "2026-05-20"},
    }
    assert _json_roundtrip(error.to_dict())["details"]["partitions"] == ["planning", "retrieval"]


def test_shared_records_to_dict_golden_output() -> None:
    source = SourceRecord(
        source_name="Serialization inventory",
        source_type=SourceType.REPORT,
        source_id="src_serialization",
    )
    request = RetrievalRequest(
        user_query="Compare current approaches",
        normalized_query="Compare current approaches",
        user_context={"requested_at": CREATED_AT, "source_types": [SourceType.REPORT]},
        required_freshness=RequiredFreshness.RECENT,
        risk_level=RiskLevel.MEDIUM,
        output_intent=OutputIntent.COMPARISON,
        constraints={"after": PUBLISHED_AT, "modes": [RetrievalMode.HYBRID]},
        request_id="req_serialization",
    )
    plan = RetrievalPlan(
        request_id=request.request_id,
        query_type=QueryType.FRESH_DATA,
        selected_modes=[RetrievalMode.HYBRID],
        retrieval_budget={"top_k": 8, "as_of": PUBLISHED_AT},
        repair_attempt=1,
        max_repair_attempts=2,
        previous_actions=["add_keyword"],
        fallback_actions=[PlanFallbackAction.CLARIFY],
        plan_reason="fresh-data query routed to hybrid retrieval.",
        plan_id="plan_serialization",
    )
    claim = ClaimRecord(
        request_id=request.request_id,
        claim_text="Current approaches require source-backed freshness checks.",
        answer_id="answer_serialization",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_serialization",
        support_status=SupportStatus.PARTIALLY_SUPPORTED,
        claim_id="claim_serialization",
    )
    answer = AnswerRecord(
        request_id=request.request_id,
        answer_text="Use source-backed freshness checks.",
        validation_id="validation_serialization",
        citation_map={"claim_serialization": ["ev_serialization"]},
        claim_records=[claim],
        confidence_level=ConfidenceLevel.MEDIUM,
        limitations=["requires refresh"],
        generated_at=CREATED_AT,
        model_used="test-model",
        answer_id="answer_serialization",
    )

    assert source.to_dict() == {
        "source_name": "Serialization inventory",
        "source_type": "report",
        "owner": None,
        "access_method": "manual",
        "external_link": None,
        "internal_location": None,
        "license_policy": "unknown",
        "license_constraints": [],
        "access_policy_id": None,
        "allowed_principals": [],
        "reliability_level": "unverified",
        "reliability_score": None,
        "freshness_policy": "manual",
        "freshness_sla": None,
        "refresh_interval": None,
        "last_checked_at": None,
        "last_ingested_at": None,
        "status": "pending",
        "notes": None,
        "source_id": "src_serialization",
    }
    assert request.to_dict() == {
        "user_query": "Compare current approaches",
        "normalized_query": "Compare current approaches",
        "user_context": {
            "requested_at": "2026-05-21T10:30:45+00:00",
            "source_types": ["report"],
        },
        "required_freshness": "recent",
        "risk_level": "medium",
        "output_intent": "comparison",
        "constraints": {"after": "2026-05-20", "modes": ["hybrid"]},
        "request_id": "req_serialization",
    }
    assert plan.to_dict() == {
        "request_id": "req_serialization",
        "query_type": "fresh-data",
        "selected_modes": ["hybrid"],
        "retrieval_budget": {"top_k": 8, "as_of": "2026-05-20"},
        "repair_attempt": 1,
        "max_repair_attempts": 2,
        "previous_actions": ["add_keyword"],
        "required_validations": ["relevance", "sufficiency", "citation"],
        "fallback_actions": ["clarify"],
        "plan_reason": "fresh-data query routed to hybrid retrieval.",
        "plan_id": "plan_serialization",
    }
    assert answer.to_dict() == {
        "request_id": "req_serialization",
        "answer_text": "Use source-backed freshness checks.",
        "validation_id": "validation_serialization",
        "citation_map": {"claim_serialization": ["ev_serialization"]},
        "claim_records": [
            {
                "request_id": "req_serialization",
                "claim_text": "Current approaches require source-backed freshness checks.",
                "answer_id": "answer_serialization",
                "support_type": "paraphrase",
                "evidence_id": "ev_serialization",
                "evidence_span": None,
                "source_quote": None,
                "support_status": "partially_supported",
                "confidence": None,
                "validator_notes": None,
                "claim_id": "claim_serialization",
            }
        ],
        "confidence_level": "medium",
        "limitations": ["requires refresh"],
        "generated_at": "2026-05-21T10:30:45+00:00",
        "model_used": "test-model",
        "answer_id": "answer_serialization",
    }
    assert _json_roundtrip(answer.to_dict())["claim_records"][0]["support_type"] == "paraphrase"


def test_remaining_shared_records_to_dict_golden_output() -> None:
    job = IngestionJob(
        source_id="src_serialization",
        trigger_type=IngestionTriggerType.REPAIR,
        correlation_id="corr_serialization",
        started_at=CREATED_AT,
        completed_at=CREATED_AT,
        status=IngestionStatus.PARTIAL,
        input_version="raw:v1",
        output_version="normalized:v2",
        error_summary="one chunk failed",
        error_ids=["err_serialization"],
        log_ids=["log_serialization"],
        quality_flags=["partial"],
        ingestion_job_id="ingest_serialization",
    )
    document = DocumentRecord(
        source_id="src_serialization",
        title="Serialization report",
        author_or_owner="retrieval team",
        published_at=PUBLISHED_AT,
        retrieved_at=CREATED_AT,
        document_type=DocumentType.MARKDOWN,
        language="en",
        canonical_url="https://example.test/serialization",
        checksum="sha256:abc123",
        version="v1",
        access_level=AccessLevel.INTERNAL,
        as_of_date=PUBLISHED_AT,
        valid_from=PUBLISHED_AT,
        valid_to=date(2026, 6, 20),
        access_policy_id="policy_serialization",
        document_id="doc_serialization",
    )
    chunk = ChunkRecord(
        document_id=document.document_id,
        source_id=document.source_id,
        chunk_index=2,
        heading_path=["Overview", "Serialization"],
        text="Serialization behavior must stay stable.",
        token_count=7,
        page_number=3,
        start_offset=10,
        end_offset=55,
        created_at=CREATED_AT,
        embedding_id="emb_serialization",
        sparse_terms_id="sparse_serialization",
        quality_flags=["golden"],
        access_policy_id="policy_serialization",
        allowed_principals=["team:retrieval"],
        as_of_date=PUBLISHED_AT,
        valid_from=PUBLISHED_AT,
        valid_to=date(2026, 6, 20),
        chunk_id="chunk_serialization",
    )
    entity = EntityRecord(
        entity_name="Serialization helper",
        entity_type=EntityType.CONCEPT,
        aliases=["serializer"],
        description="Shared serialization behavior.",
        confidence=0.91,
        source_ids=[document.source_id],
        first_seen_at=CREATED_AT,
        last_seen_at=CREATED_AT,
        entity_id="entity_serialization",
    )
    relation = RelationRecord(
        subject_entity_id=entity.entity_id,
        object_entity_id="entity_contract",
        relation_type=RelationType.SUPPORTS,
        evidence_chunk_ids=[chunk.chunk_id],
        confidence=0.82,
        valid_from=PUBLISHED_AT,
        valid_to=date(2026, 6, 20),
        extracted_at=CREATED_AT,
        relation_id="rel_serialization",
    )
    evidence = EvidenceCandidate(
        request_id="req_serialization",
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=document.source_id,
        document_id=document.document_id,
        chunk_id=chunk.chunk_id,
        entity_ids=[entity.entity_id],
        relation_ids=[relation.relation_id],
        text_snippet="Serialization behavior must stay stable.",
        score=12.5,
        normalized_score=0.76,
        source_reliability=ReliabilityLevel.HIGH,
        published_at=PUBLISHED_AT,
        retrieved_at=CREATED_AT,
        citation_link="https://example.test/serialization#overview",
        access_scope="team:retrieval",
        access_decision=AccessDecision.REDACTED,
        exclusion_reason="redacted for principal",
        license_constraints=["internal only"],
        evidence_id="ev_serialization",
    )
    ranked = RankedEvidence(
        evidence_id=evidence.evidence_id,
        rank=1,
        rerank_score=0.94,
        relevance_label=RelevanceLabel.HIGH,
        diversity_group="serialization",
        selection_reason="highest stable payload coverage",
        ranked_evidence_id="ranked_serialization",
    )
    validation = ValidationRecord(
        request_id=evidence.request_id,
        evidence_ids=[evidence.evidence_id],
        validation_status=ValidationStatus.REPAIR_NEEDED,
        relevance_score=0.88,
        sufficiency_score=0.67,
        freshness_status=FreshnessStatus.STALE,
        contradiction_status=ContradictionStatus.POSSIBLE,
        citation_status=CitationStatus.PARTIAL,
        unsupported_claim_risk=RiskLevel.HIGH,
        repair_action=RepairAction.RETRIEVE_MORE,
        failed_criteria=[ValidationCriterion.FRESHNESS, ValidationCriterion.CITATION],
        stop_reason="needs newer citation",
        validator_notes="Refresh source before synthesis.",
        validation_id="validation_serialization",
    )
    feedback = FeedbackRecord(
        request_id=evidence.request_id,
        answer_id="answer_serialization",
        user_rating=UserRating.PARTIALLY_USEFUL,
        correction_text="Use a newer source.",
        failure_category=FailureCategory.FRESHNESS,
        reviewed_by=ReviewerType.EVALUATOR,
        created_at=CREATED_AT,
        feedback_id="feedback_serialization",
    )

    assert job.to_dict() == {
        "source_id": "src_serialization",
        "trigger_type": "repair",
        "correlation_id": "corr_serialization",
        "started_at": "2026-05-21T10:30:45+00:00",
        "completed_at": "2026-05-21T10:30:45+00:00",
        "status": "partial",
        "input_version": "raw:v1",
        "output_version": "normalized:v2",
        "error_summary": "one chunk failed",
        "error_ids": ["err_serialization"],
        "log_ids": ["log_serialization"],
        "quality_flags": ["partial"],
        "ingestion_job_id": "ingest_serialization",
    }
    assert document.to_dict() == {
        "source_id": "src_serialization",
        "title": "Serialization report",
        "author_or_owner": "retrieval team",
        "published_at": "2026-05-20",
        "retrieved_at": "2026-05-21T10:30:45+00:00",
        "document_type": "markdown",
        "language": "en",
        "canonical_url": "https://example.test/serialization",
        "checksum": "sha256:abc123",
        "version": "v1",
        "access_level": "internal",
        "as_of_date": "2026-05-20",
        "valid_from": "2026-05-20",
        "valid_to": "2026-06-20",
        "access_policy_id": "policy_serialization",
        "document_id": "doc_serialization",
    }
    assert chunk.to_dict() == {
        "document_id": "doc_serialization",
        "source_id": "src_serialization",
        "chunk_index": 2,
        "heading_path": ["Overview", "Serialization"],
        "text": "Serialization behavior must stay stable.",
        "token_count": 7,
        "page_number": 3,
        "start_offset": 10,
        "end_offset": 55,
        "created_at": "2026-05-21T10:30:45+00:00",
        "embedding_id": "emb_serialization",
        "sparse_terms_id": "sparse_serialization",
        "quality_flags": ["golden"],
        "access_policy_id": "policy_serialization",
        "allowed_principals": ["team:retrieval"],
        "as_of_date": "2026-05-20",
        "valid_from": "2026-05-20",
        "valid_to": "2026-06-20",
        "chunk_id": "chunk_serialization",
    }
    assert entity.to_dict() == {
        "entity_name": "Serialization helper",
        "entity_type": "concept",
        "aliases": ["serializer"],
        "description": "Shared serialization behavior.",
        "confidence": 0.91,
        "source_ids": ["src_serialization"],
        "first_seen_at": "2026-05-21T10:30:45+00:00",
        "last_seen_at": "2026-05-21T10:30:45+00:00",
        "entity_id": "entity_serialization",
    }
    assert relation.to_dict() == {
        "subject_entity_id": "entity_serialization",
        "object_entity_id": "entity_contract",
        "relation_type": "supports",
        "evidence_chunk_ids": ["chunk_serialization"],
        "confidence": 0.82,
        "valid_from": "2026-05-20",
        "valid_to": "2026-06-20",
        "extracted_at": "2026-05-21T10:30:45+00:00",
        "relation_id": "rel_serialization",
    }
    assert evidence.to_dict() == {
        "request_id": "req_serialization",
        "retrieval_mode": "hybrid",
        "source_id": "src_serialization",
        "document_id": "doc_serialization",
        "chunk_id": "chunk_serialization",
        "entity_ids": ["entity_serialization"],
        "relation_ids": ["rel_serialization"],
        "text_snippet": "Serialization behavior must stay stable.",
        "score": 12.5,
        "normalized_score": 0.76,
        "source_reliability": "high",
        "published_at": "2026-05-20",
        "retrieved_at": "2026-05-21T10:30:45+00:00",
        "citation_link": "https://example.test/serialization#overview",
        "access_scope": "team:retrieval",
        "access_decision": "redacted",
        "exclusion_reason": "redacted for principal",
        "license_constraints": ["internal only"],
        "evidence_id": "ev_serialization",
    }
    assert ranked.to_dict() == {
        "evidence_id": "ev_serialization",
        "rank": 1,
        "rerank_score": 0.94,
        "relevance_label": "high",
        "diversity_group": "serialization",
        "selection_reason": "highest stable payload coverage",
        "ranked_evidence_id": "ranked_serialization",
    }
    assert validation.to_dict() == {
        "request_id": "req_serialization",
        "evidence_ids": ["ev_serialization"],
        "validation_status": "repair_needed",
        "relevance_score": 0.88,
        "sufficiency_score": 0.67,
        "freshness_status": "stale",
        "contradiction_status": "possible",
        "citation_status": "partial",
        "unsupported_claim_risk": "high",
        "repair_action": "retrieve_more",
        "failed_criteria": ["freshness", "citation"],
        "stop_reason": "needs newer citation",
        "validator_notes": "Refresh source before synthesis.",
        "validation_id": "validation_serialization",
    }
    assert feedback.to_dict() == {
        "request_id": "req_serialization",
        "answer_id": "answer_serialization",
        "user_rating": "partially useful",
        "correction_text": "Use a newer source.",
        "failure_category": "freshness",
        "reviewed_by": "evaluator",
        "created_at": "2026-05-21T10:30:45+00:00",
        "feedback_id": "feedback_serialization",
    }
    assert _json_roundtrip(validation.to_dict())["failed_criteria"] == ["freshness", "citation"]


def test_environment_and_stack_serialization_golden_output() -> None:
    test_profile = serialize_environment_profile(get_environment_profile(EnvironmentName.TEST))
    profiles_payload = serialize_environment_profiles()
    vector_component = serialize_stack_component(
        get_baseline_component(StackComponentCategory.VECTOR_STORE)
    )
    stack_payload = serialize_stack_components(get_baseline_stack())
    fallback_component = serialize_stack_component(
        StackComponent(
            category=StackComponentCategory.ORCHESTRATION,
            name="Mock LangGraph",
            component_type=StackComponentType.MOCK,
            purpose="Dependency-free local/test substitute.",
            fallback_for=StackComponentCategory.ORCHESTRATION,
        )
    )

    assert test_profile == {
        "name": "test",
        "debug": True,
        "storage_root": "memory://test/storage",
        "vector_store_url": "mock://test/vector-store",
        "graph_store_url": "mock://test/graph-store",
        "model_profile_name": "test-mock",
        "external_access_enabled": False,
        "graph_enabled": False,
        "strict_access": True,
        "max_retries": 0,
        "default_top_k": 3,
        "default_budget_tokens": 1024,
    }
    assert list(profiles_payload) == ["local", "test", "staging", "production"]
    assert profiles_payload["production"]["name"] == "production"
    assert vector_component == {
        "category": "vector_store",
        "name": "Qdrant",
        "component_type": "database",
        "purpose": "Dense vector retrieval and hybrid dense/sparse search.",
        "package_names": ["qdrant-client"],
        "runtime_dependency_required": False,
        "fallback_for": None,
    }
    assert [component["category"] for component in stack_payload] == [
        "ingestion_indexing",
        "graph_store",
        "vector_store",
        "orchestration",
        "metadata_store",
        "raw_source_store",
        "model_services",
    ]
    assert fallback_component == {
        "category": "orchestration",
        "name": "Mock LangGraph",
        "component_type": "mock",
        "purpose": "Dependency-free local/test substitute.",
        "package_names": [],
        "runtime_dependency_required": False,
        "fallback_for": "orchestration",
    }


def test_planning_trace_serialization_golden_output() -> None:
    trace = PlannerTrace(
        request_id="req_serialization",
        query_type=QueryType.SEMANTIC,
        selected_modes=(RetrievalMode.VECTOR, RetrievalMode.HYBRID),
        plan_reason="semantic query routed to vector, hybrid retrieval.",
        direct_response=DirectResponseDecision(
            should_respond_directly=False,
            reason="retrieval required before answer synthesis",
            metadata={"requires_retrieval": True},
        ),
        retrieval_budget={"top_k": 6, "cost_target": 0.02},
        repair_attempt=0,
        max_repair_attempts=1,
        fallback_actions=(PlanFallbackAction.ADD_KEYWORD, PlanFallbackAction.CLARIFY),
    )
    repair_trace = RepairExecutionTrace(
        validation_status=ValidationStatus.REPAIR_NEEDED,
        repair_action=RepairAction.RETRIEVE_MORE,
        repair_attempt=1,
        max_repair_attempts=2,
        previous_actions=("add_keyword",),
        fallback_actions=(PlanFallbackAction.ADD_VECTOR,),
        exhausted=False,
        retrieval_rerun_requested=False,
    )

    assert trace.to_dict() == {
        "request_id": "req_serialization",
        "query_type": "semantic",
        "selected_modes": ["vector", "hybrid"],
        "plan_reason": "semantic query routed to vector, hybrid retrieval.",
        "direct_response": {
            "should_respond_directly": False,
            "reason": "retrieval required before answer synthesis",
            "metadata": {"requires_retrieval": True},
        },
        "retrieval_budget": {"top_k": 6, "cost_target": 0.02},
        "repair_attempt": 0,
        "max_repair_attempts": 1,
        "fallback_actions": ["add_keyword", "clarify"],
    }
    assert repair_trace.to_dict() == {
        "validation_status": "repair_needed",
        "repair_action": "retrieve_more",
        "repair_attempt": 1,
        "max_repair_attempts": 2,
        "previous_actions": ["add_keyword"],
        "fallback_actions": ["add_vector"],
        "exhausted": False,
        "retrieval_rerun_requested": False,
    }


def test_orchestration_runtime_serialization_golden_output() -> None:
    config = OrchestrationRuntimeConfig(
        adapter_name="adapter_serialization",
        runtime_name="Runtime",
        capabilities=(OrchestrationCapability.PLAN, OrchestrationCapability.RETRIEVE),
        priority=3,
        fallback_runtime="local",
        package_names=("runtime-package",),
        connection_settings={"enabled": True},
    )
    error = ErrorEnvelope(
        correlation_id="corr_serialization",
        partition=Partition.PLANNING,
        operation_name="health_check",
        severity=ErrorSeverity.CRITICAL,
        error_type=ErrorType.POLICY,
        error_message="missing capability",
        retryable=False,
        fallback_action=FallbackAction.STOP,
        error_id="err_health",
        created_at=CREATED_AT,
    )
    health = OrchestrationHealthCheck(
        adapter_name=config.adapter_name,
        runtime_name=config.runtime_name,
        status=OrchestrationStatus.DEGRADED,
        latency_ms=1.25,
        message="missing required orchestration capabilities",
        checked_capabilities=(OrchestrationCapability.PLAN,),
        error=error,
        details={"missing_capabilities": ("synthesize",)},
    )
    log = LogEvent(
        correlation_id="corr_serialization",
        partition=Partition.PLANNING,
        event_type=LogEventType.SUCCESS,
        operation_name="run_query",
        message="Completed.",
        output_reference="answer_serialization",
        log_id="log_run",
        created_at=CREATED_AT,
    )
    result = OrchestrationRunResult(
        adapter_name=config.adapter_name,
        runtime_name=config.runtime_name,
        operation_name="run_query",
        ok=False,
        correlation_id="corr_serialization",
        request_id="req_serialization",
        planned_query={"ignored": "not exported"},
        output_reference="answer_serialization",
        health=health,
        error=error,
        logs=(log,),
        details={"fallback_used": False, "executed_modes": (RetrievalMode.HYBRID,)},
    )

    assert config.to_dict() == {
        "adapter_name": "adapter_serialization",
        "runtime_name": "Runtime",
        "capabilities": ("plan", "retrieve"),
        "priority": 3,
        "fallback_runtime": "local",
        "package_names": ("runtime-package",),
        "connection_settings": {"enabled": True},
    }
    error_payload = {
        "correlation_id": "corr_serialization",
        "partition": "planning",
        "operation_name": "health_check",
        "severity": "critical",
        "error_type": "policy",
        "error_message": "missing capability",
        "retryable": False,
        "fallback_action": "stop",
        "retry_count": 0,
        "max_retries": 0,
        "error_id": "err_health",
        "created_at": "2026-05-21T10:30:45+00:00",
        "details": {},
    }
    health_payload = {
        "adapter_name": "adapter_serialization",
        "runtime_name": "Runtime",
        "status": "degraded",
        "latency_ms": 1.25,
        "message": "missing required orchestration capabilities",
        "checked_capabilities": ("plan",),
        "error": error_payload,
        "details": {"missing_capabilities": ("synthesize",)},
    }
    log_payload = {
        "correlation_id": "corr_serialization",
        "partition": "planning",
        "event_type": "success",
        "operation_name": "run_query",
        "message": "Completed.",
        "input_reference": None,
        "output_reference": "answer_serialization",
        "duration_ms": None,
        "cost_estimate": None,
        "model_or_tool": None,
        "log_id": "log_run",
        "created_at": "2026-05-21T10:30:45+00:00",
        "details": {},
    }
    assert error.to_dict() == error_payload
    assert health.to_dict() == health_payload
    assert log.to_dict() == log_payload
    assert result.to_dict() == {
        "adapter_name": "adapter_serialization",
        "runtime_name": "Runtime",
        "operation_name": "run_query",
        "ok": False,
        "correlation_id": "corr_serialization",
        "request_id": "req_serialization",
        "output_reference": "answer_serialization",
        "health": health_payload,
        "error": error_payload,
        "logs": (log_payload,),
        "details": {"fallback_used": False, "executed_modes": ("hybrid",)},
    }
    assert "planned_query" not in result.to_dict()
    assert _json_roundtrip(result.to_dict())["logs"][0]["operation_name"] == "run_query"
