from datetime import date
import unittest

from evaluation import store_evaluation_trace
from feedback import (
    InMemoryFeedbackRepository,
    build_feedback_trace_reference,
    capture_feedback,
    create_improvement_tasks,
)
from shared import (
    AccessDecision,
    AccessMethod,
    AnswerRecord,
    ClaimRecord,
    DocumentRecord,
    EvidenceCandidate,
    FailureCategory,
    FeedbackRecord,
    LicensePolicy,
    LogEventType,
    ReliabilityLevel,
    RetrievalMode,
    SourceRecord,
    SourceStatus,
    SourceType,
    SupportStatus,
    SupportType,
    UserRating,
)
from storage import InMemoryStorageRepository


def _evidence(
    *,
    evidence_id: str = "ev_improvement",
    request_id: str = "req_improvement",
    source_id: str = "src_improvement",
    document_id: str = "doc_improvement",
    chunk_id: str = "chunk_improvement",
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id=request_id,
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=source_id,
        document_id=document_id,
        chunk_id=chunk_id,
        text_snippet="Feedback can be converted into task records.",
        normalized_score=0.44,
        source_reliability=ReliabilityLevel.HIGH,
        published_at=date(2026, 5, 1),
        citation_link="https://example.test/improvement#chunk-0",
        access_decision=AccessDecision.ALLOWED,
        evidence_id=evidence_id,
    )


def _answer(*, request_id: str = "req_improvement", answer_id: str = "answer_improvement") -> AnswerRecord:
    claim = ClaimRecord(
        request_id=request_id,
        answer_id=answer_id,
        claim_text="Feedback can be converted into task records.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_improvement",
        support_status=SupportStatus.SUPPORTED,
        claim_id="claim_improvement",
    )
    return AnswerRecord(
        request_id=request_id,
        answer_id=answer_id,
        answer_text="Feedback can be converted into task records. [1]",
        citation_map={"claim_improvement": ["ev_improvement", "https://example.test/improvement#chunk-0"]},
        claim_records=[claim],
    )


class FeedbackImprovementTests(unittest.TestCase):
    def test_create_improvement_task_from_captured_feedback_and_evaluation_context(self) -> None:
        repository = InMemoryFeedbackRepository()
        answer = _answer()
        evidence = [_evidence()]
        feedback_result = capture_feedback(
            request_id="req_improvement",
            answer=answer,
            evidence=evidence,
            user_rating=UserRating.INCORRECT,
            correction_text="The answer is wrong and missing evidence.",
            failure_category=FailureCategory.RETRIEVAL,
            repository=repository,
        )
        evaluation_result = store_evaluation_trace(
            request_id="req_improvement",
            answer=answer,
            evidence=evidence,
            feedback=[feedback_result.feedback],
            metrics={"citation_precision": 0.25, "supported_claims": 0},
        )

        result = create_improvement_tasks(
            feedback=feedback_result.feedback,
            trace_reference=feedback_result.trace_reference,
            evaluation_trace=evaluation_result.trace,
            repository=repository,
        )

        self.assertEqual(len(result.tasks), 1)
        task = result.tasks[0]
        self.assertIn(task.task_id, repository.improvement_tasks)
        self.assertEqual(task.failure_category, FailureCategory.RETRIEVAL)
        self.assertEqual(task.feedback_ids, (feedback_result.feedback.feedback_id,))
        self.assertEqual(task.evidence_ids, ("ev_improvement",))
        self.assertEqual(task.source_ids, ("src_improvement",))
        self.assertEqual(task.chunk_ids, ("chunk_improvement",))
        self.assertEqual(task.claim_ids, ("claim_improvement",))
        self.assertEqual(task.evaluation_trace_id, evaluation_result.trace.trace_id)
        self.assertEqual(task.metric_signals["citation_precision"], 0.25)
        self.assertEqual(task.priority, 1)
        self.assertFalse(task.policy_mutation)
        self.assertEqual(task.to_dict()["policy_mutation"], False)
        self.assertEqual(result.logs[0].event_type, LogEventType.SUCCESS)
        self.assertEqual(result.logs[0].details["event_name"], "improvement_tasks_created")
        self.assertFalse(result.logs[0].details["policy_mutation"])

    def test_multiple_feedback_categories_become_deduplicated_tasks(self) -> None:
        repository = InMemoryFeedbackRepository()
        trace = build_feedback_trace_reference(request_id="req_improvement", answer=_answer(), evidence=[_evidence()])
        feedback = [
            FeedbackRecord(
                request_id="req_improvement",
                answer_id="answer_improvement",
                user_rating=UserRating.NOT_USEFUL,
                failure_category=FailureCategory.RANKING,
                feedback_id="feedback_ranking",
            ),
            FeedbackRecord(
                request_id="req_improvement",
                answer_id="answer_improvement",
                user_rating=UserRating.PARTIALLY_USEFUL,
                failure_category=FailureCategory.RANKING,
                feedback_id="feedback_ranking_again",
            ),
            FeedbackRecord(
                request_id="req_improvement",
                answer_id="answer_improvement",
                user_rating=UserRating.PARTIALLY_USEFUL,
                failure_category=FailureCategory.SYNTHESIS,
                feedback_id="feedback_synthesis",
            ),
        ]

        result = create_improvement_tasks(feedback=feedback, trace_reference=trace, repository=repository)

        self.assertEqual([task.failure_category for task in result.tasks], [FailureCategory.RANKING, FailureCategory.SYNTHESIS])
        self.assertEqual(len(repository.improvement_tasks), 2)
        self.assertEqual(result.tasks[0].feedback_ids, ("feedback_ranking", "feedback_ranking_again", "feedback_synthesis"))

    def test_useful_feedback_without_failure_context_creates_no_tasks(self) -> None:
        repository = InMemoryFeedbackRepository()
        feedback = FeedbackRecord(
            request_id="req_improvement",
            answer_id="answer_improvement",
            user_rating=UserRating.USEFUL,
            feedback_id="feedback_useful",
        )

        result = create_improvement_tasks(feedback=feedback, repository=repository)

        self.assertEqual(result.tasks, ())
        self.assertEqual(repository.improvement_tasks, {})
        self.assertEqual(result.logs[0].details["task_count"], 0)
        self.assertFalse(result.logs[0].details["policy_mutation"])

    def test_improvement_tasks_do_not_mutate_source_reliability_or_access_policy(self) -> None:
        storage = InMemoryStorageRepository()
        source = SourceRecord(
            source_name="Improvement source",
            source_type=SourceType.DOCUMENT,
            access_method=AccessMethod.URL,
            external_link="https://example.test/improvement",
            license_policy=LicensePolicy.ALLOWED,
            access_policy_id="policy_public",
            reliability_level=ReliabilityLevel.HIGH,
            reliability_score=0.91,
            status=SourceStatus.ACTIVE,
            source_id="src_improvement",
        )
        storage.save_source(source)
        storage.save_document(
            DocumentRecord(
                source_id=source.source_id,
                document_id="doc_improvement",
                access_policy_id="policy_public",
            )
        )
        feedback = FeedbackRecord(
            request_id="req_improvement",
            answer_id="answer_improvement",
            user_rating=UserRating.INCORRECT,
            failure_category=FailureCategory.ACCESS,
        )

        result = create_improvement_tasks(
            feedback=feedback,
            trace_reference=build_feedback_trace_reference(
                request_id="req_improvement",
                answer=_answer(),
                evidence=[_evidence(source_id=source.source_id)],
            ),
            repository=storage,
        )

        self.assertEqual(storage.sources[source.source_id].reliability_level, ReliabilityLevel.HIGH)
        self.assertEqual(storage.sources[source.source_id].reliability_score, 0.91)
        self.assertEqual(storage.sources[source.source_id].access_policy_id, "policy_public")
        self.assertEqual(result.tasks[0].source_ids, (source.source_id,))
        self.assertFalse(result.tasks[0].policy_mutation)
        self.assertFalse(result.logs[0].details["policy_mutation"])

    def test_task_write_failure_returns_retryable_error_and_tasks(self) -> None:
        class FailingImprovementRepository(InMemoryFeedbackRepository):
            def save_improvement_task(self, task: object) -> object:
                raise RuntimeError("task store unavailable")

        feedback = FeedbackRecord(
            request_id="req_improvement",
            answer_id="answer_improvement",
            user_rating=UserRating.NOT_USEFUL,
            failure_category=FailureCategory.RETRIEVAL,
        )

        result = create_improvement_tasks(feedback=feedback, repository=FailingImprovementRepository())

        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.logs[0].event_type, LogEventType.ERROR)
        self.assertEqual(result.logs[0].details["event_name"], "improvement_task_creation_failed")
        self.assertTrue(result.errors[0].retryable)


if __name__ == "__main__":
    unittest.main()
