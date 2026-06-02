from datetime import date

from evaluation import InMemoryEvaluationRepository, store_evaluation_trace
from feedback import InMemoryFeedbackRepository, capture_feedback
from ingestion import IngestionError, run_ingestion_job
from planning import plan_request
from ranking import select_ranked_evidence
from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    AnswerRecord,
    ClaimRecord,
    ErrorSeverity,
    ErrorType,
    EvidenceCandidate,
    FallbackAction,
    LicensePolicy,
    LogEventType,
    Partition,
    ReliabilityLevel,
    RepairAction,
    RetrievalMode,
    RetrievalRequest,
    SourceRecord,
    SourceStatus,
    SourceType,
    SupportStatus,
    SupportType,
    UserRating,
    ValidationCriterion,
    create_error_envelope,
    create_error_log_event,
    create_start_log_event,
    create_success_log_event,
)
from source_registry import InMemorySourceRepository, SourceRegistry
from synthesis import generate_answer
from validation import validate_answer_evidence


def _log_core(log) -> dict[str, object]:
    payload = log.to_dict()
    return {
        "correlation_id": payload["correlation_id"],
        "partition": payload["partition"],
        "event_type": payload["event_type"],
        "operation_name": payload["operation_name"],
        "message": payload["message"],
        "input_reference": payload["input_reference"],
        "output_reference": payload["output_reference"],
        "details": payload["details"],
    }


def _error_core(error) -> dict[str, object]:
    payload = error.to_dict()
    return {
        "correlation_id": payload["correlation_id"],
        "partition": payload["partition"],
        "operation_name": payload["operation_name"],
        "severity": payload["severity"],
        "error_type": payload["error_type"],
        "error_message": payload["error_message"],
        "retryable": payload["retryable"],
        "retry_count": payload["retry_count"],
        "max_retries": payload["max_retries"],
        "fallback_action": payload["fallback_action"],
        "details": payload["details"],
    }


def _candidate(
    *,
    evidence_id: str,
    text: str,
    request_id: str = "req_telemetry",
    source_id: str = "src_telemetry",
    chunk_id: str = "chunk_telemetry",
    normalized_score: float = 0.8,
    access_decision: AccessDecision = AccessDecision.ALLOWED,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id=request_id,
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=source_id,
        document_id=f"doc_{source_id}",
        chunk_id=chunk_id,
        text_snippet=text,
        normalized_score=normalized_score,
        source_reliability=ReliabilityLevel.MEDIUM,
        published_at=date(2026, 5, 1),
        citation_link="https://example.test/source#chunk-0",
        access_decision=access_decision,
        evidence_id=evidence_id,
    )


def _answer(*, request_id: str = "req_telemetry", answer_id: str = "answer_telemetry") -> AnswerRecord:
    claim = ClaimRecord(
        request_id=request_id,
        answer_id=answer_id,
        claim_text="Telemetry records preserve fallback decisions.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_support",
        support_status=SupportStatus.SUPPORTED,
        claim_id="claim_telemetry",
    )
    return AnswerRecord(
        request_id=request_id,
        answer_id=answer_id,
        answer_text="Telemetry records preserve fallback decisions. [1]",
        citation_map={"claim_telemetry": ["ev_support"]},
        claim_records=[claim],
    )


def test_shared_policy_builder_golden_payloads() -> None:
    start = create_start_log_event(
        correlation_id="corr_policy",
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_started",
        input_reference="plan_gold",
    )
    success = create_success_log_event(
        correlation_id="corr_policy",
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_completed",
        output_reference="ev_a,ev_b",
        details={"candidate_count": 2},
    )
    error_log = create_error_log_event(
        correlation_id="corr_policy",
        partition=Partition.RANKING,
        operation_name="select_ranked_evidence",
        event_name="reranker_fallback",
        error_type=ErrorType.MODEL,
        message="Reranker failed; using normalized retrieval scores.",
    )
    error = create_error_envelope(
        correlation_id="corr_policy",
        partition=Partition.RANKING,
        operation_name="select_ranked_evidence",
        error_type=ErrorType.MODEL,
        error_message="Reranker failed: model unavailable",
    )

    assert _log_core(start) == {
        "correlation_id": "corr_policy",
        "partition": "retrieval",
        "event_type": "start",
        "operation_name": "run_retrieval",
        "message": "Started run_retrieval.",
        "input_reference": "plan_gold",
        "output_reference": None,
        "details": {"event_name": "retrieval_started"},
    }
    assert _log_core(success) == {
        "correlation_id": "corr_policy",
        "partition": "retrieval",
        "event_type": "success",
        "operation_name": "run_retrieval",
        "message": "Completed run_retrieval.",
        "input_reference": None,
        "output_reference": "ev_a,ev_b",
        "details": {"candidate_count": 2, "event_name": "retrieval_completed"},
    }
    assert _log_core(error_log) == {
        "correlation_id": "corr_policy",
        "partition": "ranking",
        "event_type": "error",
        "operation_name": "select_ranked_evidence",
        "message": "Reranker failed; using normalized retrieval scores.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "event_name": "reranker_fallback",
            "error_type": "model",
            "fallback_action": "skip",
            "retry_count": 0,
        },
    }
    assert _error_core(error) == {
        "correlation_id": "corr_policy",
        "partition": "ranking",
        "operation_name": "select_ranked_evidence",
        "severity": "recoverable",
        "error_type": "model",
        "error_message": "Reranker failed: model unavailable",
        "retryable": False,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "skip",
        "details": {},
    }


def test_source_registry_access_policy_and_block_telemetry_golden() -> None:
    source = SourceRecord(
        source_name="Restricted telemetry source",
        source_type=SourceType.DOCUMENT,
        owner="security",
        access_method=AccessMethod.UPLOAD,
        license_policy=LicensePolicy.ALLOWED,
        access_policy_id="access:restricted",
        allowed_principals=["alice"],
        status=SourceStatus.ACTIVE,
        source_id="src_source_gold",
    )
    registry = SourceRegistry(InMemorySourceRepository([source]))

    access = registry.check_source_access(source.source_id, principal="bob", correlation_id="corr_source")
    policy = registry.apply_source_policy(source.source_id, principal="bob", correlation_id="corr_source_policy")
    _updated, blocked_log = registry.update_source_status(
        source.source_id,
        SourceStatus.BLOCKED,
        correlation_id="corr_source_block",
    )

    assert _log_core(access.log) == {
        "correlation_id": "corr_source",
        "partition": "source_registry",
        "event_type": "success",
        "operation_name": "check_source_access",
        "message": "restricted source denied for principal",
        "input_reference": None,
        "output_reference": source.source_id,
        "details": {"allowed": False, "event_name": "source_access_checked", "principal": "bob", "source_id": source.source_id},
    }
    assert _error_core(access.error) == {
        "correlation_id": "corr_source",
        "partition": "source_registry",
        "operation_name": "check_source_access",
        "severity": "recoverable",
        "error_type": "access",
        "error_message": "restricted source denied for principal",
        "retryable": False,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "stop",
        "details": {"principal": "bob", "source_id": source.source_id},
    }
    assert _log_core(policy.log) == {
        "correlation_id": "corr_source_policy",
        "partition": "source_registry",
        "event_type": "decision",
        "operation_name": "apply_source_policy",
        "message": "restricted source denied for principal",
        "input_reference": None,
        "output_reference": source.source_id,
        "details": {
            "event_name": "source_policy_decision",
            "policy_name": "access",
            "allowed": False,
            "access_decision": "denied",
        },
    }
    assert _log_core(blocked_log) == {
        "correlation_id": "corr_source_block",
        "partition": "source_registry",
        "event_type": "error",
        "operation_name": "update_source_status",
        "message": "Source was blocked by registry policy.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "source_id": source.source_id,
            "status": "blocked",
            "event_name": "source_blocked",
            "error_type": "policy",
            "fallback_action": "stop",
            "retry_count": 0,
        },
    }


def test_ingestion_retry_failure_telemetry_golden() -> None:
    source = SourceRecord(
        source_name="Timeout source",
        source_type=SourceType.DOCUMENT,
        access_method=AccessMethod.FILESYSTEM,
        source_id="src_ingestion_gold",
    )

    def timeout_extractor(_source: SourceRecord, **_kwargs: object) -> object:
        raise IngestionError("temporary timeout", error_type=ErrorType.TIMEOUT, retryable=True)

    result = run_ingestion_job(source, max_retries=2, extractor=timeout_extractor)
    start_log, first_retry, second_retry, failed_log = result.logs
    final_error = result.errors[-1]

    assert _log_core(start_log) == {
        "correlation_id": result.job.correlation_id,
        "partition": "ingestion",
        "event_type": "start",
        "operation_name": "start_ingestion_job",
        "message": "Started start_ingestion_job.",
        "input_reference": source.source_id,
        "output_reference": None,
        "details": {"event_name": "ingestion_started", "source_id": source.source_id, "ingestion_job_id": result.job.ingestion_job_id},
    }
    assert _log_core(first_retry)["details"] == {
        "event_name": "ingestion_retry",
        "source_id": source.source_id,
        "retry_count": 1,
        "error_type": "timeout",
    }
    assert _log_core(second_retry)["details"] == {
        "event_name": "ingestion_retry",
        "source_id": source.source_id,
        "retry_count": 2,
        "error_type": "timeout",
    }
    assert _log_core(failed_log) == {
        "correlation_id": result.job.correlation_id,
        "partition": "ingestion",
        "event_type": "error",
        "operation_name": "complete_ingestion_job",
        "message": "Ingestion job failed.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "event_name": "ingestion_failed",
            "source_id": source.source_id,
            "ingestion_job_id": result.job.ingestion_job_id,
            "status": "failed",
            "error_ids": [error.error_id for error in result.errors],
        },
    }
    assert _error_core(final_error) == {
        "correlation_id": result.job.correlation_id,
        "partition": "ingestion",
        "operation_name": "extract_source_content",
        "severity": "recoverable",
        "error_type": "timeout",
        "error_message": "temporary timeout",
        "retryable": True,
        "retry_count": 2,
        "max_retries": 2,
        "fallback_action": "retry",
        "details": {"source_id": source.source_id},
    }


def test_planning_decision_telemetry_golden() -> None:
    request = RetrievalRequest(
        user_query="Compare RAG and CAG",
        normalized_query="Compare RAG and CAG",
        request_id="req_plan_gold",
    )

    result = plan_request(request, correlation_id="corr_plan")
    logs_by_event = {log.details["event_name"]: log for log in result.logs}

    assert _log_core(logs_by_event["query_classified"]) == {
        "correlation_id": "corr_plan",
        "partition": "planning",
        "event_type": "decision",
        "operation_name": "classify_query",
        "message": "Classified query for retrieval planning.",
        "input_reference": None,
        "output_reference": request.request_id,
        "details": {
            "request_id": request.request_id,
            "query_type": result.plan.query_type.value,
            "classification_reason": "semantic routing signal detected",
            "conservative_fallback": False,
            "event_name": "query_classified",
        },
    }
    assert _log_core(logs_by_event["retrieval_plan_created"]) == {
        "correlation_id": "corr_plan",
        "partition": "planning",
        "event_type": "decision",
        "operation_name": "create_retrieval_plan",
        "message": "Created retrieval plan with traceable routing reason.",
        "input_reference": None,
        "output_reference": result.plan.plan_id,
        "details": {
            "request_id": request.request_id,
            "plan_id": result.plan.plan_id,
            "query_type": result.plan.query_type.value,
            "selected_modes": [mode.value for mode in result.plan.selected_modes],
            "plan_reason": result.plan.plan_reason,
            "repair_attempt": 0,
            "max_repair_attempts": result.plan.max_repair_attempts,
            "fallback_actions": [action.value for action in result.plan.fallback_actions],
            "direct_response": False,
            "event_name": "retrieval_plan_created",
        },
    }


def test_ranking_fallback_and_success_telemetry_golden() -> None:
    low = _candidate(
        evidence_id="ev_low",
        source_id="src_low",
        chunk_id="chunk_low",
        text="Relevant graph retrieval evidence.",
        normalized_score=0.2,
    )
    high = _candidate(
        evidence_id="ev_high",
        source_id="src_high",
        chunk_id="chunk_high",
        text="Less relevant text.",
        normalized_score=0.9,
    )

    def failing_reranker(_query: str, _candidates: object) -> dict[str, float]:
        raise RuntimeError("model unavailable")

    result = select_ranked_evidence(
        "graph retrieval evidence",
        [low, high],
        reranker=failing_reranker,
        correlation_id="corr_rank",
    )

    assert _error_core(result.errors[0]) == {
        "correlation_id": "corr_rank",
        "partition": "ranking",
        "operation_name": "select_ranked_evidence",
        "severity": "recoverable",
        "error_type": "model",
        "error_message": "Reranker failed: model unavailable",
        "retryable": False,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "skip",
        "details": {"event_name": "reranker_fallback", "candidate_count": 2},
    }
    assert _log_core(result.logs[0]) == {
        "correlation_id": "corr_rank",
        "partition": "ranking",
        "event_type": "error",
        "operation_name": "select_ranked_evidence",
        "message": "Reranker failed; using normalized retrieval scores.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "candidate_count": 2,
            "event_name": "reranker_fallback",
            "error_type": "model",
            "fallback_action": "skip",
            "retry_count": 0,
        },
    }
    assert _log_core(result.logs[-1]) == {
        "correlation_id": "corr_rank",
        "partition": "ranking",
        "event_type": "success",
        "operation_name": "select_ranked_evidence",
        "message": "Selected ranked evidence.",
        "input_reference": None,
        "output_reference": "ev_high,ev_low",
        "details": {
            "query": "graph retrieval evidence",
            "input_count": 2,
            "deduplicated_count": 0,
            "candidate_count": 2,
            "selected_count": 2,
            "used_fallback": True,
            "source_ids": ["src_high", "src_low"],
            "event_name": "evidence_selected",
        },
    }


def test_validation_repair_and_failure_telemetry_golden() -> None:
    weak = _candidate(
        evidence_id="ev_weak",
        text="Unrelated billing export.",
        normalized_score=0.0,
    )
    denied = _candidate(
        evidence_id="ev_denied",
        text="Restricted evidence must not appear in an answer.",
        access_decision=AccessDecision.DENIED,
    )

    repair = validate_answer_evidence(
        "How does validation cite evidence?",
        [weak],
        required_validations=[ValidationCriterion.RELEVANCE],
        correlation_id="corr_validation_repair",
    )
    failed = validate_answer_evidence(
        "Summarize the restricted source",
        [denied],
        required_validations=[ValidationCriterion.ACCESS],
        correlation_id="corr_validation_fail",
    )

    assert _error_core(repair.errors[0]) == {
        "correlation_id": "corr_validation_repair",
        "partition": "validation",
        "operation_name": "validate_answer_evidence",
        "severity": "recoverable",
        "error_type": "validation",
        "error_message": "Validation failed criteria: relevance.",
        "retryable": True,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "repair",
        "details": {
            "event_name": "validation_repair_needed",
            "validation_id": repair.validation.validation_id,
            "repair_action": RepairAction.REWRITE.value,
        },
    }
    assert _log_core(repair.logs[-1]) == {
        "correlation_id": "corr_validation_repair",
        "partition": "validation",
        "event_type": "error",
        "operation_name": "validate_answer_evidence",
        "message": "Validation requires repair before synthesis.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "validation_id": repair.validation.validation_id,
            "repair_action": RepairAction.REWRITE.value,
            "event_name": "validation_repair_needed",
            "error_type": "validation",
            "fallback_action": "repair",
            "retry_count": 0,
        },
    }
    assert _error_core(failed.errors[0]) == {
        "correlation_id": "corr_validation_fail",
        "partition": "validation",
        "operation_name": "validate_answer_evidence",
        "severity": "recoverable",
        "error_type": "access",
        "error_message": "Validation failed criteria: access.",
        "retryable": False,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "stop",
        "details": {
            "event_name": "validation_failed",
            "validation_id": failed.validation.validation_id,
            "repair_action": RepairAction.STOP.value,
        },
    }


def test_synthesis_no_evidence_error_telemetry_golden() -> None:
    denied = _candidate(
        evidence_id="ev_denied",
        text="Denied evidence cannot support an answer.",
        access_decision=AccessDecision.DENIED,
    )

    result = generate_answer("denied evidence", [denied], correlation_id="corr_synthesis")

    assert _log_core(result.logs[0]) == {
        "correlation_id": "corr_synthesis",
        "partition": "synthesis",
        "event_type": "success",
        "operation_name": "create_claim_records",
        "message": "Created cited claim records.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "query": "denied evidence",
            "approved_evidence_count": 0,
            "claim_count": 0,
            "event_name": "claim_records_created",
        },
    }
    assert _error_core(result.errors[0]) == {
        "correlation_id": "corr_synthesis",
        "partition": "synthesis",
        "operation_name": "generate_answer",
        "severity": "recoverable",
        "error_type": "validation",
        "error_message": "No approved cited evidence was available for synthesis.",
        "retryable": False,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "stop",
        "details": {"event_name": "insufficient_cited_evidence", "query": "denied evidence"},
    }
    assert _log_core(result.logs[1]) == {
        "correlation_id": "corr_synthesis",
        "partition": "synthesis",
        "event_type": "error",
        "operation_name": "generate_answer",
        "message": "No approved cited evidence was available for synthesis.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "query": "denied evidence",
            "event_name": "insufficient_cited_evidence",
            "error_type": "validation",
            "fallback_action": "stop",
            "retry_count": 0,
        },
    }


def test_feedback_and_evaluation_write_failure_telemetry_golden() -> None:
    class FailingFeedbackRepository(InMemoryFeedbackRepository):
        def save_feedback(self, feedback, trace_reference):
            raise RuntimeError("metadata store unavailable")

    class FailingEvaluationRepository(InMemoryEvaluationRepository):
        def save_trace(self, trace):
            raise RuntimeError("metadata store unavailable")

    feedback = capture_feedback(
        request_id="req_feedback_gold",
        answer=_answer(request_id="req_feedback_gold", answer_id="answer_feedback_gold"),
        user_rating=UserRating.INCORRECT,
        repository=FailingFeedbackRepository(),
        correlation_id="corr_feedback",
    )
    evaluation = store_evaluation_trace(
        request_id="req_eval_gold",
        answer=_answer(request_id="req_eval_gold", answer_id="answer_eval_gold"),
        repository=FailingEvaluationRepository(),
        correlation_id="corr_eval",
    )

    assert _error_core(feedback.errors[0]) == {
        "correlation_id": "corr_feedback",
        "partition": "feedback",
        "operation_name": "capture_feedback",
        "severity": "recoverable",
        "error_type": "storage",
        "error_message": "Feedback write failed: metadata store unavailable",
        "retryable": True,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "retry",
        "details": {
            "request_id": "req_feedback_gold",
            "answer_id": "answer_feedback_gold",
            "feedback_id": feedback.feedback.feedback_id,
            "trace_reference": feedback.trace_reference.to_dict(),
        },
    }
    assert _log_core(feedback.logs[0]) == {
        "correlation_id": "corr_feedback",
        "partition": "feedback",
        "event_type": "error",
        "operation_name": "capture_feedback",
        "message": "Feedback write failed; preserved trace for retry.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "request_id": "req_feedback_gold",
            "answer_id": "answer_feedback_gold",
            "feedback_id": feedback.feedback.feedback_id,
            "trace_reference": feedback.trace_reference.to_dict(),
            "policy_mutation": False,
            "event_name": "feedback_capture_failed",
            "error_type": "storage",
            "fallback_action": "retry",
            "retry_count": 0,
        },
    }
    assert _error_core(evaluation.errors[0]) == {
        "correlation_id": "corr_eval",
        "partition": "evaluation",
        "operation_name": "store_evaluation_trace",
        "severity": "recoverable",
        "error_type": "storage",
        "error_message": "Evaluation trace write failed: metadata store unavailable",
        "retryable": True,
        "retry_count": 0,
        "max_retries": 0,
        "fallback_action": "retry",
        "details": {
            "request_id": "req_eval_gold",
            "answer_id": "answer_eval_gold",
            "trace_id": evaluation.trace.trace_id,
        },
    }
    assert _log_core(evaluation.logs[0]) == {
        "correlation_id": "corr_eval",
        "partition": "evaluation",
        "event_type": "error",
        "operation_name": "store_evaluation_trace",
        "message": "Evaluation trace write failed; preserved trace for retry.",
        "input_reference": None,
        "output_reference": None,
        "details": {
            "request_id": "req_eval_gold",
            "answer_id": "answer_eval_gold",
            "trace_id": evaluation.trace.trace_id,
            "policy_mutation": False,
            "event_name": "evaluation_trace_store_failed",
            "error_type": "storage",
            "fallback_action": "retry",
            "retry_count": 0,
        },
    }
