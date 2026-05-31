from datetime import date
import unittest

from evaluation import (
    InMemoryEvaluationRepository,
    build_evaluation_case,
    build_observability_report,
    evaluate_batch,
)
from shared import (
    AccessDecision,
    AnswerRecord,
    ClaimRecord,
    EvidenceCandidate,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    FailureCategory,
    FeedbackRecord,
    LogEvent,
    LogEventType,
    Partition,
    ReliabilityLevel,
    RetrievalMode,
    SupportStatus,
    SupportType,
    UserRating,
    ValidationRecord,
    ValidationStatus,
)
from storage import InMemoryStorageRepository


def _evidence(
    evidence_id: str,
    *,
    mode: RetrievalMode = RetrievalMode.HYBRID,
    citation_link: str | None = "https://example.test/source#chunk",
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id="req_eval",
        retrieval_mode=mode,
        source_id="src_eval",
        document_id="doc_eval",
        chunk_id=f"chunk_{evidence_id}",
        text_snippet="Evaluation metrics separate retrieval and synthesis failures.",
        normalized_score=0.9,
        source_reliability=ReliabilityLevel.HIGH,
        published_at=date(2026, 5, 1),
        citation_link=citation_link,
        access_decision=AccessDecision.ALLOWED,
        evidence_id=evidence_id,
    )


def _answer(
    *,
    answer_id: str = "answer_eval",
    support_status: SupportStatus = SupportStatus.SUPPORTED,
    citation_map: dict[str, list[str]] | None = None,
) -> AnswerRecord:
    claim = ClaimRecord(
        request_id="req_eval",
        answer_id=answer_id,
        claim_text="Evaluation metrics separate retrieval and synthesis failures.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_expected",
        support_status=support_status,
        claim_id="claim_eval",
    )
    return AnswerRecord(
        request_id="req_eval",
        answer_id=answer_id,
        answer_text="Evaluation metrics separate retrieval and synthesis failures. [1]",
        citation_map=citation_map or {"claim_eval": ["ev_expected", "https://example.test/source#chunk"]},
        claim_records=[claim],
    )


class EvaluationMetricsTests(unittest.TestCase):
    def test_build_evaluation_case_collects_latency_and_cost_from_logs(self) -> None:
        logs = [
            LogEvent(
                correlation_id="corr_eval",
                partition=Partition.RETRIEVAL,
                event_type=LogEventType.SUCCESS,
                operation_name="run_retrieval",
                message="retrieved",
                duration_ms=25.5,
                cost_estimate=0.01,
                details={"event_name": "retrieval_completed"},
            ),
            LogEvent(
                correlation_id="corr_eval",
                partition=Partition.VALIDATION,
                event_type=LogEventType.SUCCESS,
                operation_name="validate_answer_evidence",
                message="validated",
                duration_ms=4.5,
                cost_estimate=0.002,
                details={"event_name": "validation_passed"},
            ),
        ]

        case = build_evaluation_case(
            request_id="req_eval",
            answer=_answer(),
            evidence=[_evidence("ev_expected")],
            expected_evidence_ids=["ev_expected"],
            expected_modes=[RetrievalMode.HYBRID],
            logs=logs,
            tags=["regression"],
        )

        self.assertEqual(case.latency_ms_by_partition["retrieval"], 25.5)
        self.assertEqual(case.latency_ms_by_partition["validation"], 4.5)
        self.assertEqual(case.cost_by_partition["retrieval"], 0.01)
        self.assertEqual(case.tags, ("regression",))

    def test_evaluate_batch_computes_quality_and_operating_metrics(self) -> None:
        repository = InMemoryEvaluationRepository()
        feedback = FeedbackRecord(
            request_id="req_eval",
            answer_id="answer_eval",
            user_rating=UserRating.INCORRECT,
            failure_category=FailureCategory.SYNTHESIS,
        )
        passing_case = build_evaluation_case(
            request_id="req_eval",
            answer=_answer(),
            evidence=[_evidence("ev_expected"), _evidence("ev_other", mode=RetrievalMode.GRAPH)],
            validation=ValidationRecord(request_id="req_eval", validation_status=ValidationStatus.PASS),
            feedback=[feedback],
            expected_evidence_ids=["ev_expected"],
            expected_modes=[RetrievalMode.GRAPH],
            baseline_ranked_evidence_ids=["ev_other", "ev_expected"],
            logs=[
                LogEvent(
                    correlation_id="corr_eval",
                    partition=Partition.RETRIEVAL,
                    event_type=LogEventType.SUCCESS,
                    operation_name="run_retrieval",
                    message="retrieved",
                    duration_ms=10,
                    cost_estimate=0.01,
                )
            ],
        )
        rejected_case = build_evaluation_case(
            request_id="req_eval_2",
            answer=_answer(answer_id="answer_eval_2", support_status=SupportStatus.UNSUPPORTED, citation_map={}),
            evidence=[],
            validation=ValidationRecord(request_id="req_eval_2", validation_status=ValidationStatus.REPAIR_NEEDED),
            expected_evidence_ids=["missing_ev"],
        )

        result = evaluate_batch(
            [passing_case, rejected_case],
            improvement_task_ids=["task_feedback"],
            repository=repository,
        )

        self.assertEqual(result.report.metrics["case_count"], 2)
        self.assertEqual(result.report.metrics["retrieval_recall"], 0.5)
        self.assertEqual(result.report.metrics["citation_precision"], 1.0)
        self.assertEqual(result.report.metrics["unsupported_claim_rate"], 0.5)
        self.assertEqual(result.report.metrics["validator_rejection_rate"], 0.5)
        self.assertEqual(result.report.metrics["graph_hit_rate"], 1.0)
        self.assertEqual(result.report.metrics["reranker_improvement"], 1.0)
        self.assertEqual(result.report.failure_counts["synthesis"], 1)
        self.assertIn(result.report.report_id, repository.reports)
        self.assertEqual(result.logs[0].event_type, LogEventType.METRIC)
        self.assertFalse(result.logs[0].details["policy_mutation"])

    def test_observability_report_counts_logs_errors_latency_and_cost(self) -> None:
        repository = InMemoryStorageRepository()
        logs = [
            LogEvent(
                correlation_id="corr_eval",
                partition=Partition.PLANNING,
                event_type=LogEventType.DECISION,
                operation_name="plan_request",
                message="planned",
                details={"event_name": "query_classified"},
            ),
            LogEvent(
                correlation_id="corr_eval",
                partition=Partition.RETRIEVAL,
                event_type=LogEventType.SUCCESS,
                operation_name="run_retrieval",
                message="retrieved",
                duration_ms=12,
                cost_estimate=0.015,
                details={"event_name": "retrieval_completed"},
            ),
        ]
        error = repository.save_error(
            ErrorEnvelope(
                correlation_id="corr_eval",
                partition=Partition.RETRIEVAL,
                operation_name="run_retrieval",
                severity=ErrorSeverity.WARNING,
                error_type=ErrorType.TIMEOUT,
                error_message="timeout",
                retryable=True,
                fallback_action=FallbackAction.RETRY,
            )
        )

        result = build_observability_report(logs, [error], repository=repository)

        self.assertEqual(result.report.log_counts_by_partition["planning"], 1)
        self.assertEqual(result.report.log_counts_by_partition["retrieval"], 1)
        self.assertEqual(result.report.error_counts_by_partition["retrieval"], 1)
        self.assertEqual(result.report.event_counts["retrieval_completed"], 1)
        self.assertEqual(result.report.latency_ms_by_partition["retrieval"], 12.0)
        self.assertEqual(result.report.cost_by_partition["retrieval"], 0.015)
        self.assertIn(result.report.report_id, repository.observability_reports)
        self.assertEqual(result.logs[0].details["event_name"], "observability_report_created")


if __name__ == "__main__":
    unittest.main()
