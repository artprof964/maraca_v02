from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from evaluation import build_evaluation_case, build_observability_report, evaluate_batch, store_evaluation_trace
from feedback import capture_feedback, create_improvement_tasks
from shared import (
    AccessDecision,
    AnswerRecord,
    ClaimRecord,
    EvidenceCandidate,
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
)
from storage import DurableStorageRepository


def _answer() -> AnswerRecord:
    claim = ClaimRecord(
        request_id="req_broader_hooks",
        answer_id="answer_broader_hooks",
        claim_text="Repository save hooks preserve retryable telemetry.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_broader_hooks",
        support_status=SupportStatus.SUPPORTED,
        claim_id="claim_broader_hooks",
    )
    return AnswerRecord(
        request_id="req_broader_hooks",
        answer_id="answer_broader_hooks",
        answer_text="Repository save hooks preserve retryable telemetry. [1]",
        citation_map={"claim_broader_hooks": ["ev_broader_hooks"]},
        claim_records=[claim],
    )


def _evidence() -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id="req_broader_hooks",
        retrieval_mode=RetrievalMode.HYBRID,
        source_id="src_broader_hooks",
        document_id="doc_broader_hooks",
        chunk_id="chunk_broader_hooks",
        text_snippet="Repository save hooks preserve retryable telemetry.",
        normalized_score=0.86,
        source_reliability=ReliabilityLevel.HIGH,
        access_decision=AccessDecision.ALLOWED,
        evidence_id="ev_broader_hooks",
    )


class NoDomainSaveHooks:
    pass


class FeedbackWriteFails:
    def save_feedback(self, feedback: object, trace_reference: object) -> object:
        raise RuntimeError("feedback store unavailable")


class FeedbackWriteSucceedsButLogFails:
    def __init__(self) -> None:
        self.feedback: dict[str, object] = {}

    def save_feedback(self, feedback: object, trace_reference: object) -> object:
        feedback_id = getattr(feedback, "feedback_id")
        self.feedback[feedback_id] = feedback
        return feedback

    def add_log(self, log: object) -> object:
        raise RuntimeError("feedback log store unavailable")


class FeedbackWriteFailsAndErrorHookFails:
    def save_feedback(self, feedback: object, trace_reference: object) -> object:
        raise RuntimeError("feedback store unavailable")

    def save_error(self, error: object) -> object:
        raise RuntimeError("feedback error store unavailable")


class EvaluationTraceFailsAndErrorHookFails:
    def save_trace(self, trace: object) -> object:
        raise RuntimeError("trace store unavailable")

    def save_error(self, error: object) -> object:
        raise RuntimeError("evaluation error store unavailable")


class RecordingDomainSaveRepository:
    def __init__(self) -> None:
        self.improvement_tasks: dict[str, object] = {}
        self.cases: dict[str, object] = {}
        self.reports: dict[str, object] = {}
        self.observability_reports: dict[str, object] = {}
        self.logs: list[object] = []
        self.errors: list[object] = []

    def save_improvement_task(self, task: object) -> object:
        self.improvement_tasks[getattr(task, "task_id")] = task
        return task

    def save_evaluation_case(self, case: object) -> object:
        self.cases[getattr(case, "case_id")] = case
        return case

    def save_evaluation_report(self, report: object) -> object:
        self.reports[getattr(report, "report_id")] = report
        return report

    def save_observability_report(self, report: object) -> object:
        self.observability_reports[getattr(report, "report_id")] = report
        return report

    def add_log(self, log: object) -> object:
        self.logs.append(log)
        return log

    def save_error(self, error: object) -> object:
        self.errors.append(error)
        return error


class ImprovementTaskWriteFails(RecordingDomainSaveRepository):
    def save_improvement_task(self, task: object) -> object:
        raise RuntimeError("improvement task store unavailable")


class EvaluationCaseWriteFails(RecordingDomainSaveRepository):
    def save_evaluation_case(self, case: object) -> object:
        raise RuntimeError("evaluation case store unavailable")


class EvaluationReportWriteFails(RecordingDomainSaveRepository):
    def save_evaluation_report(self, report: object) -> object:
        raise RuntimeError("evaluation report store unavailable")


class ObservabilityReportWriteFails(RecordingDomainSaveRepository):
    def save_observability_report(self, report: object) -> object:
        raise RuntimeError("observability report store unavailable")


class DurableImprovementTaskWriteFails(DurableStorageRepository):
    def save_improvement_task(self, task: object) -> object:
        raise RuntimeError("durable improvement task store unavailable")


class DurableEvaluationReportWriteFails(DurableStorageRepository):
    def save_evaluation_report(self, report: object) -> object:
        raise RuntimeError("durable evaluation report store unavailable")


class DurableObservabilityReportWriteFails(DurableStorageRepository):
    def save_observability_report(self, report: object) -> object:
        raise RuntimeError("durable observability report store unavailable")


def _feedback() -> FeedbackRecord:
    return FeedbackRecord(
        request_id="req_broader_hooks",
        answer_id="answer_broader_hooks",
        user_rating=UserRating.INCORRECT,
        failure_category=FailureCategory.RETRIEVAL,
        feedback_id="feedback_broader_hooks",
    )


def _evaluation_case() -> object:
    return build_evaluation_case(
        request_id="req_broader_hooks",
        answer=_answer(),
        evidence=[_evidence()],
        feedback=[_feedback()],
        expected_evidence_ids=["ev_broader_hooks"],
    )


def _input_log() -> LogEvent:
    return LogEvent(
        correlation_id="corr_broader_hooks",
        partition=Partition.RETRIEVAL,
        event_type=LogEventType.SUCCESS,
        operation_name="run_retrieval",
        message="retrieved",
        details={"event_name": "retrieval_completed"},
    )


def test_broader_domain_save_hooks_are_permissive_when_methods_are_absent() -> None:
    repository = NoDomainSaveHooks()
    answer = _answer()
    evidence = [_evidence()]
    feedback = _feedback()
    case = build_evaluation_case(
        request_id="req_broader_hooks",
        answer=answer,
        evidence=evidence,
        feedback=[feedback],
        expected_evidence_ids=["ev_broader_hooks"],
    )
    input_log = _input_log()

    feedback_result = capture_feedback(
        request_id="req_broader_hooks",
        answer=answer,
        evidence=evidence,
        user_rating=UserRating.PARTIALLY_USEFUL,
        repository=repository,  # type: ignore[arg-type]
        correlation_id="corr_feedback_missing_hooks",
    )
    improvement_result = create_improvement_tasks(
        feedback=feedback,
        repository=repository,
        correlation_id="corr_improvement_missing_hooks",
    )
    trace_result = store_evaluation_trace(
        request_id="req_broader_hooks",
        answer=answer,
        evidence=evidence,
        feedback=[feedback],
        repository=repository,  # type: ignore[arg-type]
        correlation_id="corr_trace_missing_hooks",
    )
    batch_result = evaluate_batch(
        [case],
        repository=repository,  # type: ignore[arg-type]
        correlation_id="corr_batch_missing_hooks",
    )
    observability_result = build_observability_report(
        [input_log],
        repository=repository,  # type: ignore[arg-type]
        correlation_id="corr_observability_missing_hooks",
    )

    assert feedback_result.errors == ()
    assert feedback_result.logs[0].details == {
        "event_name": "feedback_captured",
        "request_id": "req_broader_hooks",
        "answer_id": "answer_broader_hooks",
        "feedback_id": feedback_result.feedback.feedback_id,
        "user_rating": "partially useful",
        "failure_category": "validation",
        "evidence_ids": ["ev_broader_hooks"],
        "policy_mutation": False,
    }
    assert improvement_result.errors == ()
    assert improvement_result.logs[0].details["event_name"] == "improvement_tasks_created"
    assert trace_result.errors == ()
    assert trace_result.logs[0].details["event_name"] == "evaluation_trace_stored"
    assert batch_result.errors == ()
    assert batch_result.logs[0].details["event_name"] == "evaluation_batch_reported"
    assert observability_result.errors == ()
    assert observability_result.logs[0].details["event_name"] == "observability_report_created"


def test_broader_domain_save_hooks_call_present_methods_and_log_success() -> None:
    repository = RecordingDomainSaveRepository()
    feedback = _feedback()
    case = _evaluation_case()

    improvement_result = create_improvement_tasks(
        feedback=feedback,
        repository=repository,
        correlation_id="corr_improvement_present_hooks",
    )
    batch_result = evaluate_batch(
        [case],
        repository=repository,
        correlation_id="corr_batch_present_hooks",
    )
    observability_result = build_observability_report(
        [_input_log()],
        repository=repository,
        correlation_id="corr_observability_present_hooks",
    )

    assert set(repository.improvement_tasks) == {task.task_id for task in improvement_result.tasks}
    assert repository.cases == {case.case_id: case}
    assert repository.reports == {batch_result.report.report_id: batch_result.report}
    assert repository.observability_reports == {
        observability_result.report.report_id: observability_result.report
    }
    assert [log.details["event_name"] for log in repository.logs] == [
        "improvement_tasks_created",
        "evaluation_batch_reported",
        "observability_report_created",
    ]
    assert repository.errors == []


def test_feedback_success_log_hook_failure_still_propagates_after_domain_save() -> None:
    repository = FeedbackWriteSucceedsButLogFails()

    with pytest.raises(RuntimeError, match="feedback log store unavailable"):
        capture_feedback(
            request_id="req_broader_hooks",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.USEFUL,
            repository=repository,  # type: ignore[arg-type]
        )

    assert len(repository.feedback) == 1


def test_error_hook_failures_propagate_on_feedback_and_evaluation_write_failures() -> None:
    with pytest.raises(RuntimeError, match="feedback error store unavailable"):
        capture_feedback(
            request_id="req_broader_hooks",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.INCORRECT,
            repository=FeedbackWriteFailsAndErrorHookFails(),  # type: ignore[arg-type]
            correlation_id="corr_feedback_error_hook",
        )

    with pytest.raises(RuntimeError, match="evaluation error store unavailable"):
        store_evaluation_trace(
            request_id="req_broader_hooks",
            answer=_answer(),
            evidence=[_evidence()],
            repository=EvaluationTraceFailsAndErrorHookFails(),  # type: ignore[arg-type]
            correlation_id="corr_trace_error_hook",
        )


def test_feedback_write_failure_return_shape_and_telemetry_payload_stay_stable() -> None:
    result = capture_feedback(
        request_id="req_broader_hooks",
        answer=_answer(),
        evidence=[_evidence()],
        user_rating=UserRating.INCORRECT,
        repository=FeedbackWriteFails(),  # type: ignore[arg-type]
        correlation_id="corr_feedback_write_failed",
    )

    assert result.feedback.request_id == "req_broader_hooks"
    assert result.trace_reference.to_dict() == {
        "request_id": "req_broader_hooks",
        "answer_id": "answer_broader_hooks",
        "evidence_ids": ["ev_broader_hooks"],
        "source_ids": ["src_broader_hooks"],
        "document_ids": ["doc_broader_hooks"],
        "chunk_ids": ["chunk_broader_hooks"],
        "citation_links": [],
        "claim_ids": ["claim_broader_hooks"],
        "validation_id": None,
    }
    assert result.logs[0].details == {
        "event_name": "feedback_capture_failed",
        "request_id": "req_broader_hooks",
        "answer_id": "answer_broader_hooks",
        "feedback_id": result.feedback.feedback_id,
        "trace_reference": result.trace_reference.to_dict(),
        "policy_mutation": False,
        "error_type": "storage",
        "fallback_action": "retry",
        "retry_count": 0,
    }
    assert result.errors[0].details == {
        "request_id": "req_broader_hooks",
        "answer_id": "answer_broader_hooks",
        "feedback_id": result.feedback.feedback_id,
        "trace_reference": result.trace_reference.to_dict(),
    }
    assert result.errors[0].retryable is True


def test_deferred_domain_save_failures_return_retryable_telemetry() -> None:
    feedback = _feedback()
    case = _evaluation_case()

    improvement_result = create_improvement_tasks(
        feedback=feedback,
        repository=ImprovementTaskWriteFails(),
        correlation_id="corr_improvement_failed",
    )
    case_result = evaluate_batch(
        [case],
        repository=EvaluationCaseWriteFails(),
        correlation_id="corr_case_failed",
    )
    report_result = evaluate_batch(
        [case],
        repository=EvaluationReportWriteFails(),
        correlation_id="corr_report_failed",
    )
    observability_result = build_observability_report(
        [_input_log()],
        repository=ObservabilityReportWriteFails(),
        correlation_id="corr_observability_failed",
    )

    assert improvement_result.errors[0].error_message.startswith("Improvement task write failed:")
    assert improvement_result.errors[0].retryable is True
    assert improvement_result.logs[0].details["event_name"] == "improvement_task_creation_failed"
    assert improvement_result.logs[0].details["policy_mutation"] is False
    assert case_result.errors[0].error_message.startswith("Evaluation report write failed:")
    assert case_result.errors[0].retryable is True
    assert case_result.logs[0].details == {
        "event_name": "evaluation_report_store_failed",
        "report_id": case_result.report.report_id,
        "case_count": 1,
        "policy_mutation": False,
        "error_type": "storage",
        "fallback_action": "retry",
        "retry_count": 0,
    }
    assert report_result.errors[0].details == {
        "report_id": report_result.report.report_id,
        "case_count": 1,
    }
    assert report_result.logs[0].details["event_name"] == "evaluation_report_store_failed"
    assert observability_result.errors[0].details == {
        "report_id": observability_result.report.report_id
    }
    assert observability_result.logs[0].details["event_name"] == "observability_report_store_failed"
    assert observability_result.logs[0].details["policy_mutation"] is False


def test_durable_repository_side_effects_for_domain_save_flows_are_log_jsonl_only() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        repository = DurableStorageRepository(temporary)
        feedback_result = capture_feedback(
            request_id="req_broader_hooks",
            answer=_answer(),
            evidence=[_evidence()],
            user_rating=UserRating.PARTIALLY_USEFUL,
            repository=repository,
            correlation_id="corr_durable_feedback",
        )
        trace_result = store_evaluation_trace(
            request_id="req_broader_hooks",
            answer=_answer(),
            evidence=[_evidence()],
            feedback=[feedback_result.feedback],
            repository=repository,
            correlation_id="corr_durable_trace",
        )
        recovered = DurableStorageRepository(temporary)
        log_payloads = [
            json.loads(line)
            for line in Path(temporary, "logs.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        durable_files = {path.name for path in Path(temporary).iterdir()}

    assert feedback_result.feedback.feedback_id in repository.feedback
    assert trace_result.trace.trace_id in repository.evaluation_traces
    assert [payload["details"]["event_name"] for payload in log_payloads] == [
        "feedback_captured",
        "evaluation_trace_stored",
    ]
    assert recovered.logs.keys() == {payload["log_id"] for payload in log_payloads}
    assert recovered.feedback == {}
    assert recovered.feedback_trace_references == {}
    assert recovered.evaluation_traces == {}
    assert "logs.jsonl" in durable_files
    assert "feedback.json" not in durable_files
    assert "evaluation_traces.json" not in durable_files


def test_durable_repository_side_effects_for_report_flows_are_log_jsonl_only() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        repository = DurableStorageRepository(temporary)
        feedback = _feedback()
        case = _evaluation_case()
        improvement_result = create_improvement_tasks(
            feedback=feedback,
            repository=repository,
            correlation_id="corr_durable_improvement",
        )
        batch_result = evaluate_batch(
            [case],
            repository=repository,
            correlation_id="corr_durable_batch",
        )
        observability_result = build_observability_report(
            [_input_log()],
            repository=repository,
            correlation_id="corr_durable_observability",
        )
        recovered = DurableStorageRepository(temporary)
        log_payloads = [
            json.loads(line)
            for line in Path(temporary, "logs.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        durable_files = {path.name for path in Path(temporary).iterdir()}

    assert set(repository.improvement_tasks) == {task.task_id for task in improvement_result.tasks}
    assert repository.evaluation_cases == {case.case_id: case}
    assert repository.evaluation_reports == {batch_result.report.report_id: batch_result.report}
    assert repository.observability_reports == {
        observability_result.report.report_id: observability_result.report
    }
    assert [payload["details"]["event_name"] for payload in log_payloads] == [
        "improvement_tasks_created",
        "evaluation_batch_reported",
        "observability_report_created",
    ]
    assert recovered.logs.keys() == {payload["log_id"] for payload in log_payloads}
    assert recovered.improvement_tasks == {}
    assert recovered.evaluation_cases == {}
    assert recovered.evaluation_reports == {}
    assert recovered.observability_reports == {}
    assert durable_files == {"logs.jsonl"}


def test_durable_repository_error_side_effects_for_deferred_domain_save_failures() -> None:
    with tempfile.TemporaryDirectory() as improvement_temporary:
        improvement_repository = DurableImprovementTaskWriteFails(improvement_temporary)
        improvement_result = create_improvement_tasks(
            feedback=_feedback(),
            repository=improvement_repository,
            correlation_id="corr_durable_improvement_failed",
        )
        improvement_recovered = DurableStorageRepository(improvement_temporary)
        improvement_error_payloads = [
            json.loads(line)
            for line in Path(improvement_temporary, "errors.jsonl").read_text(encoding="utf-8").splitlines()
        ]

    with tempfile.TemporaryDirectory() as report_temporary:
        report_repository = DurableEvaluationReportWriteFails(report_temporary)
        report_result = evaluate_batch(
            [_evaluation_case()],
            repository=report_repository,
            correlation_id="corr_durable_report_failed",
        )
        report_recovered = DurableStorageRepository(report_temporary)
        report_error_payloads = [
            json.loads(line)
            for line in Path(report_temporary, "errors.jsonl").read_text(encoding="utf-8").splitlines()
        ]

    with tempfile.TemporaryDirectory() as observability_temporary:
        observability_repository = DurableObservabilityReportWriteFails(observability_temporary)
        observability_result = build_observability_report(
            [_input_log()],
            repository=observability_repository,
            correlation_id="corr_durable_observability_failed",
        )
        observability_recovered = DurableStorageRepository(observability_temporary)
        observability_error_payloads = [
            json.loads(line)
            for line in Path(observability_temporary, "errors.jsonl").read_text(encoding="utf-8").splitlines()
        ]

    assert improvement_error_payloads[0]["error_id"] == improvement_result.errors[0].error_id
    assert report_error_payloads[0]["error_id"] == report_result.errors[0].error_id
    assert observability_error_payloads[0]["error_id"] == observability_result.errors[0].error_id
    assert set(improvement_recovered.errors) == {improvement_result.errors[0].error_id}
    assert set(report_recovered.errors) == {report_result.errors[0].error_id}
    assert set(observability_recovered.errors) == {observability_result.errors[0].error_id}
    assert improvement_recovered.improvement_tasks == {}
    assert report_recovered.evaluation_cases == {}
    assert report_recovered.evaluation_reports == {}
    assert observability_recovered.observability_reports == {}
