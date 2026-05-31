from datetime import date

from planning import create_retrieval_plan, create_retrieval_request
from shared import (
    AccessDecision,
    ClaimRecord,
    ContradictionStatus,
    EvidenceCandidate,
    FreshnessStatus,
    OutputIntent,
    Partition,
    PlanFallbackAction,
    ReliabilityLevel,
    RepairAction,
    RequiredFreshness,
    RetrievalMode,
    RiskLevel,
    SupportStatus,
    ValidationCriterion,
    ValidationStatus,
)
from storage import InMemoryStorageRepository
from validation import (
    choose_repair_action,
    detect_contradictions,
    validate_answer_evidence,
    validate_claim_support,
    validate_freshness,
    validate_relevance,
    validate_sufficiency,
)


def _evidence(
    *,
    request_id: str = "req_validation",
    evidence_id: str,
    text: str,
    access_decision: AccessDecision = AccessDecision.ALLOWED,
    citation_link: str | None = "https://example.test/source#chunk-0",
    normalized_score: float = 0.8,
    reliability: ReliabilityLevel = ReliabilityLevel.MEDIUM,
    published_at: date | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id=request_id,
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=f"src_{evidence_id}",
        document_id=f"doc_{evidence_id}",
        chunk_id=f"chunk_{evidence_id}",
        text_snippet=text,
        normalized_score=normalized_score,
        source_reliability=reliability,
        published_at=published_at,
        citation_link=citation_link,
        access_decision=access_decision,
        evidence_id=evidence_id,
    )


def test_access_denied_evidence_is_rejected_before_answer_use() -> None:
    request = create_retrieval_request("Summarize the restricted source")
    denied = _evidence(
        request_id=request.request_id,
        evidence_id="ev_denied",
        text="Restricted evidence must not appear in an answer.",
        access_decision=AccessDecision.DENIED,
    )

    result = validate_answer_evidence(
        request.user_query,
        [denied],
        required_validations=[ValidationCriterion.ACCESS],
    )

    assert result.approved_evidence == ()
    assert result.rejected_evidence == (denied,)
    assert result.validation.validation_status is ValidationStatus.FAIL
    assert result.validation.repair_action is RepairAction.STOP
    assert result.validation.failed_criteria == [ValidationCriterion.ACCESS]
    assert result.errors[0].error_type.value == "access"


def test_relevance_and_sufficiency_threshold_failures_request_more_evidence() -> None:
    request = create_retrieval_request(
        "Compare source-backed retrieval quality",
        output_intent=OutputIntent.COMPARISON,
    )
    weak = _evidence(
        request_id=request.request_id,
        evidence_id="ev_weak",
        text="This source mentions billing export formats.",
        normalized_score=0.05,
    )

    relevance = validate_relevance(request.user_query, [weak])
    sufficiency = validate_sufficiency([weak], min_score=0.8)
    action = choose_repair_action(
        [ValidationCriterion.RELEVANCE, ValidationCriterion.SUFFICIENCY],
        repair_attempt=0,
        max_repair_attempts=1,
        query=request.user_query,
    )

    assert relevance.passed is False
    assert sufficiency.passed is False
    assert action is RepairAction.RETRIEVE_MORE


def test_freshness_validation_tracks_stale_evidence_for_current_queries() -> None:
    request = create_retrieval_request(
        "What is the current policy?",
        required_freshness=RequiredFreshness.RECENT,
    )
    stale = _evidence(
        request_id=request.request_id,
        evidence_id="ev_stale",
        text="Old policy evidence.",
        published_at=date(2024, 2, 1),
    )

    check = validate_freshness(
        [stale],
        required=True,
        current_date=date(2026, 5, 22),
    )
    result = validate_answer_evidence(
        request.user_query,
        [stale],
        required_validations=[ValidationCriterion.FRESHNESS],
        required_freshness=True,
        current_date=date(2026, 5, 22),
    )

    assert check.status == FreshnessStatus.STALE.value
    assert result.validation.freshness_status is FreshnessStatus.STALE
    assert result.validation.repair_action is RepairAction.EXTERNAL_LOOKUP
    assert result.validation.failed_criteria == [ValidationCriterion.FRESHNESS]


def test_contradiction_validation_prefers_repair_over_unsupported_synthesis() -> None:
    request = create_retrieval_request("Is the rollout date June 1?")
    primary = _evidence(
        request_id=request.request_id,
        evidence_id="ev_primary",
        text="The rollout date is June 1 and the schedule is confirmed.",
        reliability=ReliabilityLevel.HIGH,
    )
    secondary = _evidence(
        request_id=request.request_id,
        evidence_id="ev_secondary",
        text="The rollout date is not June 1 and the schedule is false.",
    )

    check = detect_contradictions([primary, secondary])
    result = validate_answer_evidence(
        request.user_query,
        [primary, secondary],
        required_validations=[ValidationCriterion.CONTRADICTION],
    )

    assert check.status == ContradictionStatus.POSSIBLE.value
    assert result.validation.validation_status is ValidationStatus.REPAIR_NEEDED
    assert result.validation.repair_action is RepairAction.RETRIEVE_MORE
    assert result.validation.failed_criteria == [ValidationCriterion.CONTRADICTION]


def test_claim_level_support_records_map_each_claim_to_evidence_span() -> None:
    request = create_retrieval_request("Explain citation quality controls")
    supported = _evidence(
        request_id=request.request_id,
        evidence_id="ev_controls",
        text="Validators compare generated claims with retrieved evidence spans.",
        reliability=ReliabilityLevel.HIGH,
    )
    claim = ClaimRecord(
        request_id=request.request_id,
        answer_id="answer_controls",
        claim_text="Validators compare generated claims with retrieved evidence spans.",
        evidence_id=supported.evidence_id,
        evidence_span=supported.chunk_id,
        source_quote="Validators compare generated claims with retrieved evidence spans.",
    )

    support = validate_claim_support([claim], [supported])

    assert support.passed is True
    assert support.claims[0].evidence_id == supported.evidence_id
    assert support.claims[0].support_status is SupportStatus.SUPPORTED
    assert support.claims[0].confidence and support.claims[0].confidence > 0.9


def test_validator_logs_include_success_and_repair_needed_events() -> None:
    repository = InMemoryStorageRepository()
    request = create_retrieval_request("How does validation cite evidence?")
    good = _evidence(
        request_id=request.request_id,
        evidence_id="ev_good",
        text="Validation cites evidence before synthesis uses claims.",
    )
    weak = _evidence(
        request_id=request.request_id,
        evidence_id="ev_weak",
        text="Unrelated billing export.",
        normalized_score=0.0,
    )

    passed = validate_answer_evidence(request.user_query, [good], repository=repository)
    repair = validate_answer_evidence(request.user_query, [weak], repository=repository)
    event_names = [log.details.get("event_name") for log in (*passed.logs, *repair.logs)]

    assert "validation_passed" in event_names
    assert "validation_repair_needed" in event_names
    assert passed.logs[0].partition is Partition.VALIDATION
    assert passed.validation.validation_id in repository.validation_records
    assert repair.validation.repair_action is not RepairAction.NONE


def test_planner_sets_bounded_repair_loop_for_future_validation_repairs() -> None:
    request = create_retrieval_request(
        "latest high-risk answer requiring validation",
        required_freshness=RequiredFreshness.RECENT,
        risk_level=RiskLevel.HIGH,
        constraints={"max_repair_attempts": 99, "top_k": 99},
    )
    plan = create_retrieval_plan(request)

    assert plan.repair_attempt == 0
    assert plan.max_repair_attempts == 3
    assert plan.retrieval_budget["max_repair_attempts"] == 3
    assert plan.retrieval_budget["top_k"] == 20
    assert plan.previous_actions == []
    assert PlanFallbackAction.CLARIFY in plan.fallback_actions
    assert ValidationCriterion.ACCESS in plan.required_validations
    assert ValidationCriterion.FRESHNESS in plan.required_validations


def test_repair_loop_stops_when_attempt_limit_is_reached() -> None:
    action = choose_repair_action(
        [ValidationCriterion.SUFFICIENCY],
        repair_attempt=1,
        max_repair_attempts=1,
        query="need more evidence",
    )

    assert action is RepairAction.STOP


def test_empty_required_validation_list_can_disable_required_failures() -> None:
    denied = _evidence(
        evidence_id="ev_denied_optional",
        text="Denied evidence should still be rejected from approved evidence.",
        access_decision=AccessDecision.DENIED,
    )

    result = validate_answer_evidence(
        "optional validation",
        [denied],
        required_validations=[],
    )

    assert result.validation.validation_status is ValidationStatus.PASS
    assert result.approved_evidence == ()
    assert result.rejected_evidence == (denied,)
    assert result.validation.failed_criteria == []
