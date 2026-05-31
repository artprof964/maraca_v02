from datetime import UTC, date, datetime

from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    AnswerRecord,
    ChunkRecord,
    CitationStatus,
    ClaimRecord,
    DocumentRecord,
    DocumentType,
    EntityRecord,
    EvidenceCandidate,
    FailureCategory,
    FeedbackRecord,
    FreshnessPolicy,
    FreshnessStatus,
    IngestionJob,
    IngestionStatus,
    LicensePolicy,
    OutputIntent,
    RankedEvidence,
    RelationRecord,
    ReliabilityLevel,
    RequiredFreshness,
    RetrievalMode,
    RetrievalPlan,
    RetrievalRequest,
    RepairAction,
    RiskLevel,
    SourceRecord,
    SourceStatus,
    SourceType,
    SupportStatus,
    SupportType,
    UserRating,
    ValidationCriterion,
    ValidationRecord,
    ValidationStatus,
)


def test_source_record_keeps_access_freshness_and_reliability_separate() -> None:
    checked_at = datetime(2026, 5, 20, 8, 30, tzinfo=UTC)
    source = SourceRecord(
        source_name="Architecture paper",
        source_type=SourceType.PAPER,
        access_method=AccessMethod.URL,
        external_link="https://example.test/paper",
        license_policy=LicensePolicy.RESTRICTED,
        license_constraints=["cite source"],
        access_policy_id="policy_research",
        allowed_principals=["role:researcher"],
        reliability_level=ReliabilityLevel.HIGH,
        reliability_score=0.92,
        freshness_policy=FreshnessPolicy.SCHEDULED,
        freshness_sla="30d",
        refresh_interval="P30D",
        last_checked_at=checked_at,
        status=SourceStatus.ACTIVE,
    )

    payload = source.to_dict()

    assert source.source_id.startswith("src_")
    assert payload["source_type"] == "paper"
    assert payload["license_policy"] == "restricted"
    assert payload["access_policy_id"] == "policy_research"
    assert payload["allowed_principals"] == ["role:researcher"]
    assert payload["reliability_level"] == "high"
    assert payload["reliability_score"] == 0.92
    assert payload["freshness_policy"] == "scheduled"
    assert payload["freshness_sla"] == "30d"
    assert payload["refresh_interval"] == "P30D"
    assert payload["last_checked_at"] == "2026-05-20T08:30:00+00:00"
    assert payload["status"] == "active"


def test_ingestion_document_and_chunk_defaults_and_serialization() -> None:
    source = SourceRecord(source_name="Runbook")
    job = IngestionJob(source_id=source.source_id)
    document = DocumentRecord(
        source_id=source.source_id,
        title="Incident runbook",
        document_type=DocumentType.MARKDOWN,
        published_at=date(2026, 1, 15),
        access_level=AccessLevel.INTERNAL,
    )
    chunk = ChunkRecord(
        document_id=document.document_id,
        source_id=source.source_id,
        chunk_index=0,
        heading_path=["Intro"],
        text="Use the latest validated procedure.",
        allowed_principals=["team:sre"],
        as_of_date=date(2026, 1, 15),
    )

    assert job.status is IngestionStatus.QUEUED
    assert job.started_at.tzinfo is UTC
    assert job.to_dict()["status"] == "queued"
    assert document.to_dict()["published_at"] == "2026-01-15"
    assert document.to_dict()["access_level"] == "internal"
    assert chunk.to_dict()["heading_path"] == ["Intro"]
    assert chunk.to_dict()["allowed_principals"] == ["team:sre"]
    assert chunk.to_dict()["as_of_date"] == "2026-01-15"


def test_retrieval_request_plan_and_evidence_contracts() -> None:
    request = RetrievalRequest(
        user_query="Compare current approaches",
        required_freshness=RequiredFreshness.RECENT,
        risk_level=RiskLevel.MEDIUM,
        output_intent=OutputIntent.COMPARISON,
        constraints={"source_types": [SourceType.PAPER], "after": date(2025, 1, 1)},
    )
    plan = RetrievalPlan(
        request_id=request.request_id,
        selected_modes=[RetrievalMode.KEYWORD, RetrievalMode.VECTOR],
        required_validations=[
            ValidationCriterion.RELEVANCE,
            ValidationCriterion.FRESHNESS,
            ValidationCriterion.ACCESS,
        ],
        retrieval_budget={"top_k": 8},
    )
    evidence = EvidenceCandidate(
        request_id=request.request_id,
        retrieval_mode=RetrievalMode.VECTOR,
        source_id="src_1",
        document_id="doc_1",
        chunk_id="chunk_1",
        score=12.4,
        normalized_score=0.81,
        source_reliability=ReliabilityLevel.MEDIUM,
        access_scope="role:researcher",
        access_decision=AccessDecision.ALLOWED,
        citation_link="https://example.test/paper#section-2",
        license_constraints=["no redistribution"],
    )

    request_payload = request.to_dict()
    plan_payload = plan.to_dict()
    evidence_payload = evidence.to_dict()

    assert request_payload["required_freshness"] == "recent"
    assert request_payload["constraints"]["source_types"] == ["paper"]
    assert request_payload["constraints"]["after"] == "2025-01-01"
    assert plan_payload["selected_modes"] == ["keyword", "vector"]
    assert plan_payload["required_validations"] == ["relevance", "freshness", "access"]
    assert evidence_payload["retrieval_mode"] == "vector"
    assert evidence_payload["source_reliability"] == "medium"
    assert evidence_payload["access_decision"] == "allowed"
    assert evidence_payload["citation_link"] == "https://example.test/paper#section-2"
    assert evidence_payload["license_constraints"] == ["no redistribution"]


def test_ranking_validation_answer_and_feedback_records() -> None:
    ranked = RankedEvidence(
        evidence_id="ev_1",
        rank=1,
        rerank_score=0.94,
        selection_reason="highest source-backed relevance",
    )
    validation = ValidationRecord(
        request_id="req_1",
        evidence_ids=[ranked.evidence_id],
        validation_status=ValidationStatus.REPAIR_NEEDED,
        freshness_status=FreshnessStatus.STALE,
        citation_status=CitationStatus.PARTIAL,
        repair_action=RepairAction.RETRIEVE_MORE,
        failed_criteria=[ValidationCriterion.FRESHNESS],
    )
    claim = ClaimRecord(
        request_id="req_1",
        answer_id="answer_1",
        claim_text="Current evidence is stale.",
        support_type=SupportType.PARAPHRASE,
        evidence_id=ranked.evidence_id,
        evidence_span="section 2",
        source_quote="Evidence age exceeds the freshness policy.",
        support_status=SupportStatus.PARTIALLY_SUPPORTED,
        confidence=0.63,
        validator_notes="Needs refreshed evidence.",
    )
    answer = AnswerRecord(
        request_id="req_1",
        validation_id=validation.validation_id,
        answer_text="Current evidence is stale.",
        citation_map={"claim_1": [ranked.evidence_id]},
        claim_records=[claim],
        limitations=["stale source"],
    )
    feedback = FeedbackRecord(
        request_id="req_1",
        answer_id=answer.answer_id,
        user_rating=UserRating.PARTIALLY_USEFUL,
        correction_text="Refresh the source before final answer.",
        failure_category=FailureCategory.FRESHNESS,
    )

    claim_payload = claim.to_dict()
    answer_payload = answer.to_dict()

    assert ranked.to_dict()["rank"] == 1
    assert validation.to_dict()["validation_status"] == "repair_needed"
    assert validation.to_dict()["freshness_status"] == "stale"
    assert validation.to_dict()["repair_action"] == "retrieve_more"
    assert validation.to_dict()["failed_criteria"] == ["freshness"]
    assert claim_payload["support_type"] == "paraphrase"
    assert claim_payload["support_status"] == "partially_supported"
    assert claim_payload["evidence_span"] == "section 2"
    assert answer_payload["citation_map"] == {"claim_1": ["ev_1"]}
    assert answer_payload["claim_records"][0]["claim_text"] == "Current evidence is stale."
    assert answer_payload["claim_records"][0]["support_status"] == "partially_supported"
    assert answer_payload["generated_at"].endswith("+00:00")
    assert feedback.to_dict()["user_rating"] == "partially useful"
    assert feedback.to_dict()["failure_category"] == "freshness"
    assert feedback.to_dict()["reviewed_by"] == "user"


def test_compact_entity_and_relation_records_are_available() -> None:
    entity = EntityRecord(entity_name="Hybrid retrieval", source_ids=["src_1"])
    relation = RelationRecord(
        subject_entity_id=entity.entity_id,
        object_entity_id="entity_2",
        evidence_chunk_ids=["chunk_1"],
    )

    assert entity.to_dict()["entity_type"] == "other"
    assert entity.to_dict()["source_ids"] == ["src_1"]
    assert relation.to_dict()["relation_type"] == "other"
    assert relation.to_dict()["evidence_chunk_ids"] == ["chunk_1"]
