from datetime import date
import unittest

from evaluation import InMemoryEvaluationRepository, store_evaluation_trace
from feedback import InMemoryFeedbackRepository, build_feedback_trace_reference, capture_feedback, classify_failure_category
from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    AnswerRecord,
    CitationStatus,
    ClaimRecord,
    DocumentRecord,
    EvidenceCandidate,
    FailureCategory,
    FeedbackRecord,
    LogEventType,
    FreshnessStatus,
    LicensePolicy,
    ReliabilityLevel,
    RetrievalMode,
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
from storage import InMemoryStorageRepository


def _evidence(
    *,
    evidence_id: str = "ev_feedback",
    request_id: str = "req_feedback",
    source_id: str = "src_feedback",
    document_id: str = "doc_feedback",
    chunk_id: str = "chunk_feedback",
    citation_link: str | None = "https://example.test/source#chunk-0",
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id=request_id,
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=source_id,
        document_id=document_id,
        chunk_id=chunk_id,
        text_snippet="Hybrid retrieval keeps an auditable evidence trace.",
        normalized_score=0.82,
        source_reliability=ReliabilityLevel.MEDIUM,
        published_at=date(2026, 5, 1),
        citation_link=citation_link,
        access_decision=AccessDecision.ALLOWED,
        evidence_id=evidence_id,
    )


def _answer(*, request_id: str = "req_feedback", answer_id: str = "answer_feedback") -> AnswerRecord:
    claim = ClaimRecord(
        request_id=request_id,
        answer_id=answer_id,
        claim_text="Hybrid retrieval keeps an auditable evidence trace.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_feedback",
        evidence_span="chunk_feedback",
        support_status=SupportStatus.SUPPORTED,
        claim_id="claim_feedback",
    )
    return AnswerRecord(
        request_id=request_id,
        answer_id=answer_id,
        answer_text="Hybrid retrieval keeps an auditable evidence trace. [1]",
        citation_map={"claim_feedback": ["ev_feedback", "https://example.test/source#chunk-0"]},
        claim_records=[claim],
    )


class FeedbackEvaluationTests(unittest.TestCase):
    def test_capture_feedback_stores_rating_and_trace_references(self) -> None:
        repository = InMemoryFeedbackRepository()
        evidence = _evidence()
        answer = _answer()

        result = capture_feedback(
            request_id="req_feedback",
            answer=answer,
            evidence=[evidence],
            user_rating=UserRating.PARTIALLY_USEFUL,
            correction_text="The answer cites the source but misses one detail.",
            repository=repository,
        )

        self.assertIn(result.feedback.feedback_id, repository.feedback)
        self.assertEqual(result.feedback.user_rating, UserRating.PARTIALLY_USEFUL)
        self.assertEqual(result.trace_reference.evidence_ids, ("ev_feedback",))
        self.assertEqual(result.trace_reference.claim_ids, ("claim_feedback",))
        self.assertEqual(result.trace_reference.citation_links, ("https://example.test/source#chunk-0",))
        self.assertEqual(result.logs[0].details["event_name"], "feedback_captured")
        self.assertEqual(result.logs[0].event_type, LogEventType.SUCCESS)

    def test_failure_category_classification_uses_text_and_validation_signals(self) -> None:
        stale = classify_failure_category(
            user_rating=UserRating.INCORRECT,
            correction_text="This answer is outdated and needs fresh evidence.",
        )
        access_validation = ValidationRecord(
            request_id="req_feedback",
            validation_status=ValidationStatus.FAIL,
            failed_criteria=[ValidationCriterion.ACCESS],
        )
        access = classify_failure_category(user_rating=UserRating.INCORRECT, validation=access_validation)

        self.assertEqual(stale, FailureCategory.FRESHNESS)
        self.assertEqual(access, FailureCategory.ACCESS)
        self.assertIsNone(classify_failure_category(user_rating=UserRating.USEFUL))

    def test_build_trace_reference_includes_validation_and_deduplicates_evidence(self) -> None:
        answer = _answer()
        validation = ValidationRecord(
            request_id="req_feedback",
            validation_status=ValidationStatus.REPAIR_NEEDED,
            freshness_status=FreshnessStatus.STALE,
            citation_status=CitationStatus.PARTIAL,
            failed_criteria=[ValidationCriterion.FRESHNESS],
        )

        trace = build_feedback_trace_reference(
            request_id="req_feedback",
            answer=answer,
            evidence=[_evidence(), _evidence(evidence_id="ev_feedback")],
            validation=validation,
        )

        self.assertEqual(trace.evidence_ids, ("ev_feedback",))
        self.assertEqual(trace.source_ids, ("src_feedback",))
        self.assertEqual(trace.validation_id, validation.validation_id)

    def test_evaluation_trace_storage_records_feedback_and_metrics(self) -> None:
        repository = InMemoryEvaluationRepository()
        answer = _answer()
        evidence = _evidence()
        feedback = FeedbackRecord(
            request_id="req_feedback",
            answer_id=answer.answer_id,
            user_rating=UserRating.INCORRECT,
            failure_category=FailureCategory.SYNTHESIS,
        )

        result = store_evaluation_trace(
            request_id="req_feedback",
            answer=answer,
            evidence=[evidence],
            feedback=[feedback],
            metrics={"citation_precision": 1.0, "supported_claims": 1},
            repository=repository,
        )

        self.assertIn(result.trace.trace_id, repository.traces)
        self.assertEqual(result.trace.feedback_ids, (feedback.feedback_id,))
        self.assertEqual(result.trace.failure_categories, ("synthesis",))
        self.assertEqual(result.trace.metrics["citation_precision"], 1.0)
        self.assertEqual(result.logs[0].details["event_name"], "evaluation_trace_stored")

    def test_feedback_and_evaluation_do_not_mutate_source_reliability_or_access_policy(self) -> None:
        storage = InMemoryStorageRepository()
        source = SourceRecord(
            source_name="Feedback source",
            source_type=SourceType.DOCUMENT,
            access_method=AccessMethod.URL,
            external_link="https://example.test/source",
            license_policy=LicensePolicy.ALLOWED,
            access_policy_id="policy_public",
            reliability_level=ReliabilityLevel.HIGH,
            reliability_score=0.94,
            status=SourceStatus.ACTIVE,
        )
        document = DocumentRecord(
            source_id=source.source_id,
            document_id="doc_feedback",
            access_level=AccessLevel.PUBLIC,
            access_policy_id="policy_public",
        )
        storage.save_source(source)
        storage.save_document(document)
        answer = _answer()
        feedback_result = capture_feedback(
            request_id="req_feedback",
            answer=answer,
            evidence=[_evidence(source_id=source.source_id)],
            user_rating=UserRating.INCORRECT,
            correction_text="The answer used the wrong citation.",
            repository=storage,
        )
        evaluation_result = store_evaluation_trace(
            request_id="req_feedback",
            answer=answer,
            evidence=[_evidence(source_id=source.source_id)],
            feedback=[feedback_result.feedback],
            repository=storage,
        )

        self.assertEqual(storage.sources[source.source_id].reliability_level, ReliabilityLevel.HIGH)
        self.assertEqual(storage.sources[source.source_id].reliability_score, 0.94)
        self.assertEqual(storage.sources[source.source_id].access_policy_id, "policy_public")
        self.assertIn("feedback_captured", [log.details.get("event_name") for log in storage.logs.values()])
        self.assertIn("evaluation_trace_stored", [log.details.get("event_name") for log in storage.logs.values()])
        self.assertIn(feedback_result.feedback.feedback_id, storage.feedback)
        self.assertIn(feedback_result.feedback.feedback_id, storage.feedback_trace_references)
        self.assertIn(evaluation_result.trace.trace_id, storage.evaluation_traces)
        self.assertFalse(feedback_result.logs[0].details["policy_mutation"])
        self.assertFalse(evaluation_result.logs[0].details["policy_mutation"])

    def test_feedback_write_failure_preserves_trace_for_retry(self) -> None:
        class FailingFeedbackRepository(InMemoryFeedbackRepository):
            def save_feedback(self, feedback: FeedbackRecord, trace_reference: object) -> FeedbackRecord:
                raise RuntimeError("metadata store unavailable")

        result = capture_feedback(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.INCORRECT,
            repository=FailingFeedbackRepository(),
        )

        self.assertEqual(result.trace_reference.evidence_ids, ("ev_feedback",))
        self.assertEqual(result.logs[0].event_type, LogEventType.ERROR)
        self.assertEqual(result.logs[0].details["event_name"], "feedback_capture_failed")
        self.assertTrue(result.errors[0].retryable)

    def test_feedback_optional_log_error_hooks_are_noops_when_missing(self) -> None:
        class PartialFeedbackRepository:
            def __init__(self) -> None:
                self.feedback: dict[str, FeedbackRecord] = {}

            def save_feedback(self, feedback: FeedbackRecord, trace_reference: object) -> FeedbackRecord:
                self.feedback[feedback.feedback_id] = feedback
                return feedback

        repository = PartialFeedbackRepository()

        result = capture_feedback(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.PARTIALLY_USEFUL,
            repository=repository,  # type: ignore[arg-type]
        )

        self.assertIn(result.feedback.feedback_id, repository.feedback)
        self.assertEqual(result.logs[0].details["event_name"], "feedback_captured")
        self.assertEqual(result.errors, ())

    def test_feedback_error_persistence_is_optional_on_write_failure(self) -> None:
        class FailingPartialFeedbackRepository:
            def save_feedback(self, feedback: FeedbackRecord, trace_reference: object) -> FeedbackRecord:
                raise RuntimeError("metadata store unavailable")

        result = capture_feedback(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.INCORRECT,
            repository=FailingPartialFeedbackRepository(),  # type: ignore[arg-type]
        )

        self.assertEqual(result.logs[0].details["event_name"], "feedback_capture_failed")
        self.assertTrue(result.errors[0].retryable)

    def test_evaluation_trace_write_failure_preserves_trace_for_retry(self) -> None:
        class FailingEvaluationRepository(InMemoryEvaluationRepository):
            def save_trace(self, trace: object) -> object:
                raise RuntimeError("metadata store unavailable")

        result = store_evaluation_trace(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            repository=FailingEvaluationRepository(),
        )

        self.assertEqual(result.trace.evidence_ids, ("ev_feedback",))
        self.assertEqual(result.logs[0].event_type, LogEventType.ERROR)
        self.assertEqual(result.logs[0].details["event_name"], "evaluation_trace_store_failed")
        self.assertTrue(result.errors[0].retryable)

    def test_evaluation_optional_log_error_hooks_are_noops_when_missing(self) -> None:
        class PartialEvaluationRepository:
            def __init__(self) -> None:
                self.traces: dict[str, object] = {}

            def save_trace(self, trace: object) -> object:
                self.traces[trace.trace_id] = trace
                return trace

        repository = PartialEvaluationRepository()

        result = store_evaluation_trace(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            repository=repository,  # type: ignore[arg-type]
        )

        self.assertIn(result.trace.trace_id, repository.traces)
        self.assertEqual(result.logs[0].details["event_name"], "evaluation_trace_stored")
        self.assertEqual(result.errors, ())

    def test_evaluation_error_persistence_is_optional_on_write_failure(self) -> None:
        class FailingPartialEvaluationRepository:
            def save_trace(self, trace: object) -> object:
                raise RuntimeError("metadata store unavailable")

        result = store_evaluation_trace(
            request_id="req_feedback",
            answer=_answer(),
            evidence=[_evidence()],
            repository=FailingPartialEvaluationRepository(),  # type: ignore[arg-type]
        )

        self.assertEqual(result.logs[0].details["event_name"], "evaluation_trace_store_failed")
        self.assertTrue(result.errors[0].retryable)


if __name__ == "__main__":
    unittest.main()
