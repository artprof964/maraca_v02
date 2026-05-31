"""Dependency-free evaluation trace storage and metrics for Milestone 5."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping
from uuid import uuid4

from shared.contracts import (
    ErrorEnvelope,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    _serialize_contract,
    _utc_now,
    new_correlation_id,
)
from shared.policies import create_error_envelope, create_error_log_event, create_success_log_event
from shared.records import (
    AnswerRecord,
    EvidenceCandidate,
    FeedbackRecord,
    RetrievalMode,
    SupportStatus,
    ValidationRecord,
    ValidationStatus,
)

try:
    from storage import InMemoryStorageRepository
except ImportError:  # pragma: no cover - keeps the type optional for isolated imports.
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]

PARTITION = "evaluation"


@dataclass(frozen=True, slots=True)
class EvaluationTraceRecord:
    """Stored references needed to reproduce or audit an answer evaluation."""

    request_id: str
    answer_id: str
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    citation_links: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    validation_id: str | None = None
    feedback_ids: tuple[str, ...] = ()
    failure_categories: tuple[str, ...] = ()
    metrics: Mapping[str, float | int | str | bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    trace_id: str = field(default_factory=lambda: f"eval_trace_{uuid4().hex}")

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(
            {
                "request_id": self.request_id,
                "answer_id": self.answer_id,
                "evidence_ids": list(self.evidence_ids),
                "source_ids": list(self.source_ids),
                "document_ids": list(self.document_ids),
                "chunk_ids": list(self.chunk_ids),
                "citation_links": list(self.citation_links),
                "claim_ids": list(self.claim_ids),
                "validation_id": self.validation_id,
                "feedback_ids": list(self.feedback_ids),
                "failure_categories": list(self.failure_categories),
                "metrics": dict(self.metrics),
                "created_at": self.created_at,
                "trace_id": self.trace_id,
            }
        )


@dataclass(frozen=True, slots=True)
class EvaluationTraceResult:
    """Stored evaluation trace plus emitted telemetry."""

    trace: EvaluationTraceRecord
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationDatasetCase:
    """One reviewed request used for repeatable quality measurement."""

    request_id: str
    answer: AnswerRecord
    evidence: tuple[EvidenceCandidate, ...] = ()
    validation: ValidationRecord | None = None
    feedback: tuple[FeedbackRecord, ...] = ()
    expected_evidence_ids: tuple[str, ...] = ()
    expected_modes: tuple[RetrievalMode, ...] = ()
    baseline_ranked_evidence_ids: tuple[str, ...] = ()
    latency_ms_by_partition: Mapping[str, float] = field(default_factory=dict)
    cost_by_partition: Mapping[str, float] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    case_id: str = field(default_factory=lambda: f"eval_case_{uuid4().hex}")

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(
            {
                "request_id": self.request_id,
                "answer_id": self.answer.answer_id,
                "evidence_ids": [candidate.evidence_id for candidate in self.evidence],
                "validation_id": self.validation.validation_id if self.validation is not None else self.answer.validation_id,
                "feedback_ids": [item.feedback_id for item in self.feedback],
                "expected_evidence_ids": list(self.expected_evidence_ids),
                "expected_modes": [mode.value for mode in self.expected_modes],
                "baseline_ranked_evidence_ids": list(self.baseline_ranked_evidence_ids),
                "latency_ms_by_partition": dict(self.latency_ms_by_partition),
                "cost_by_partition": dict(self.cost_by_partition),
                "tags": list(self.tags),
                "case_id": self.case_id,
            }
        )


@dataclass(frozen=True, slots=True)
class EvaluationBatchReport:
    """Dashboard-ready quality and operating metrics for a case batch."""

    case_ids: tuple[str, ...]
    metrics: Mapping[str, float | int] = field(default_factory=dict)
    failure_counts: Mapping[str, int] = field(default_factory=dict)
    latency_ms_by_partition: Mapping[str, float] = field(default_factory=dict)
    cost_by_partition: Mapping[str, float] = field(default_factory=dict)
    improvement_task_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    report_id: str = field(default_factory=lambda: f"eval_report_{uuid4().hex}")

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(
            {
                "case_ids": list(self.case_ids),
                "metrics": dict(self.metrics),
                "failure_counts": dict(self.failure_counts),
                "latency_ms_by_partition": dict(self.latency_ms_by_partition),
                "cost_by_partition": dict(self.cost_by_partition),
                "improvement_task_ids": list(self.improvement_task_ids),
                "created_at": self.created_at,
                "report_id": self.report_id,
            }
        )


@dataclass(frozen=True, slots=True)
class EvaluationBatchResult:
    """Batch report plus emitted observability telemetry."""

    report: EvaluationBatchReport
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(frozen=True, slots=True)
class ObservabilityReport:
    """Partition-level log, error, latency, and cost summary."""

    log_counts_by_partition: Mapping[str, int] = field(default_factory=dict)
    event_counts: Mapping[str, int] = field(default_factory=dict)
    error_counts_by_partition: Mapping[str, int] = field(default_factory=dict)
    latency_ms_by_partition: Mapping[str, float] = field(default_factory=dict)
    cost_by_partition: Mapping[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    report_id: str = field(default_factory=lambda: f"obs_report_{uuid4().hex}")

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(
            {
                "log_counts_by_partition": dict(self.log_counts_by_partition),
                "event_counts": dict(self.event_counts),
                "error_counts_by_partition": dict(self.error_counts_by_partition),
                "latency_ms_by_partition": dict(self.latency_ms_by_partition),
                "cost_by_partition": dict(self.cost_by_partition),
                "created_at": self.created_at,
                "report_id": self.report_id,
            }
        )


@dataclass(frozen=True, slots=True)
class ObservabilityReportResult:
    """Observability report plus emitted metric telemetry."""

    report: ObservabilityReport
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(slots=True)
class InMemoryEvaluationRepository:
    """Small append-only evaluation store used before durable storage exists."""

    traces: dict[str, EvaluationTraceRecord] = field(default_factory=dict)
    cases: dict[str, EvaluationDatasetCase] = field(default_factory=dict)
    reports: dict[str, EvaluationBatchReport] = field(default_factory=dict)
    observability_reports: dict[str, ObservabilityReport] = field(default_factory=dict)
    logs: dict[str, LogEvent] = field(default_factory=dict)
    errors: dict[str, ErrorEnvelope] = field(default_factory=dict)

    def save_trace(self, trace: EvaluationTraceRecord) -> EvaluationTraceRecord:
        self.traces[trace.trace_id] = trace
        return trace

    def save_evaluation_case(self, case: EvaluationDatasetCase) -> EvaluationDatasetCase:
        self.cases[case.case_id] = case
        return case

    def save_evaluation_report(self, report: EvaluationBatchReport) -> EvaluationBatchReport:
        self.reports[report.report_id] = report
        return report

    def save_observability_report(self, report: ObservabilityReport) -> ObservabilityReport:
        self.observability_reports[report.report_id] = report
        return report

    def add_log(self, log: LogEvent) -> LogEvent:
        self.logs[log.log_id] = log
        return log

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        self.errors[error.error_id] = error
        return error


def store_evaluation_trace(
    *,
    request_id: str,
    answer: AnswerRecord,
    evidence: Iterable[EvidenceCandidate] = (),
    validation: ValidationRecord | None = None,
    feedback: Iterable[FeedbackRecord] = (),
    metrics: Mapping[str, float | int | str | bool] | None = None,
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> EvaluationTraceResult:
    """Persist an evaluation trace made only of references and scalar metrics."""

    corr = correlation_id or new_correlation_id("evaluation")
    evidence_tuple = tuple(evidence)
    feedback_tuple = tuple(feedback)
    trace = EvaluationTraceRecord(
        request_id=request_id,
        answer_id=answer.answer_id,
        evidence_ids=_unique(candidate.evidence_id for candidate in evidence_tuple),
        source_ids=_unique(candidate.source_id for candidate in evidence_tuple),
        document_ids=_unique(candidate.document_id for candidate in evidence_tuple),
        chunk_ids=_unique(candidate.chunk_id for candidate in evidence_tuple),
        citation_links=_unique(candidate.citation_link for candidate in evidence_tuple),
        claim_ids=_claim_ids(answer),
        validation_id=validation.validation_id if validation is not None else answer.validation_id,
        feedback_ids=_unique(item.feedback_id for item in feedback_tuple),
        failure_categories=_unique(
            item.failure_category.value if item.failure_category is not None else None for item in feedback_tuple
        ),
        metrics=dict(metrics or {}),
    )
    try:
        _save_trace(repository, trace)
    except Exception as exc:
        error = create_error_envelope(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="store_evaluation_trace",
            error_type=ErrorType.STORAGE,
            error_message=f"Evaluation trace write failed: {exc}",
            retryable=True,
            fallback_action=FallbackAction.RETRY,
            details={
                "request_id": request_id,
                "answer_id": answer.answer_id,
                "trace_id": trace.trace_id,
            },
        )
        _save_error(repository, error)
        log = create_error_log_event(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="store_evaluation_trace",
            event_name="evaluation_trace_store_failed",
            error_type=ErrorType.STORAGE,
            message="Evaluation trace write failed; preserved trace for retry.",
            fallback_action=FallbackAction.RETRY,
            details={
                "request_id": request_id,
                "answer_id": answer.answer_id,
                "trace_id": trace.trace_id,
                "policy_mutation": False,
            },
        )
        _add_log(repository, log)
        return EvaluationTraceResult(trace=trace, logs=(log,), errors=(error,))

    log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.EVALUATION,
        operation_name="store_evaluation_trace",
        event_name="evaluation_trace_stored",
        message="Stored evaluation trace references.",
        output_reference=trace.trace_id,
        details={
            "request_id": request_id,
            "answer_id": answer.answer_id,
            "trace_id": trace.trace_id,
            "evidence_count": len(trace.evidence_ids),
            "feedback_count": len(trace.feedback_ids),
            "metric_names": sorted(trace.metrics),
            "policy_mutation": False,
        },
    )
    _add_log(repository, log)
    return EvaluationTraceResult(trace=trace, logs=(log,))


def build_evaluation_case(
    *,
    request_id: str,
    answer: AnswerRecord,
    evidence: Iterable[EvidenceCandidate] = (),
    validation: ValidationRecord | None = None,
    feedback: Iterable[FeedbackRecord] = (),
    expected_evidence_ids: Iterable[str] = (),
    expected_modes: Iterable[RetrievalMode] = (),
    baseline_ranked_evidence_ids: Iterable[str] = (),
    logs: Iterable[LogEvent] = (),
    tags: Iterable[str] = (),
) -> EvaluationDatasetCase:
    """Create a deterministic evaluation case from reviewed run artifacts."""

    log_tuple = tuple(logs)
    return EvaluationDatasetCase(
        request_id=request_id,
        answer=answer,
        evidence=tuple(evidence),
        validation=validation,
        feedback=tuple(feedback),
        expected_evidence_ids=_unique(expected_evidence_ids),
        expected_modes=tuple(dict.fromkeys(expected_modes)),
        baseline_ranked_evidence_ids=_unique(baseline_ranked_evidence_ids),
        latency_ms_by_partition=_sum_log_values(log_tuple, "duration_ms"),
        cost_by_partition=_sum_log_values(log_tuple, "cost_estimate"),
        tags=_unique(tags),
    )


def evaluate_batch(
    cases: Iterable[EvaluationDatasetCase],
    *,
    improvement_task_ids: Iterable[str] = (),
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> EvaluationBatchResult:
    """Compute dashboard-ready quality, latency, and cost metrics for a batch."""

    corr = correlation_id or new_correlation_id("evaluation")
    case_tuple = tuple(cases)
    report = EvaluationBatchReport(
        case_ids=tuple(case.case_id for case in case_tuple),
        metrics=_batch_metrics(case_tuple),
        failure_counts=_failure_counts(case_tuple),
        latency_ms_by_partition=_sum_case_mapping(case_tuple, "latency_ms_by_partition"),
        cost_by_partition=_sum_case_mapping(case_tuple, "cost_by_partition"),
        improvement_task_ids=_unique(improvement_task_ids),
    )
    try:
        for case in case_tuple:
            _save_evaluation_case(repository, case)
        _save_evaluation_report(repository, report)
    except Exception as exc:
        error = create_error_envelope(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="evaluate_batch",
            error_type=ErrorType.STORAGE,
            error_message=f"Evaluation report write failed: {exc}",
            retryable=True,
            fallback_action=FallbackAction.RETRY,
            details={"report_id": report.report_id, "case_count": len(case_tuple)},
        )
        _save_error(repository, error)
        log = create_error_log_event(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="evaluate_batch",
            event_name="evaluation_report_store_failed",
            error_type=ErrorType.STORAGE,
            message="Evaluation report write failed; metrics remain available for retry.",
            fallback_action=FallbackAction.RETRY,
            details={"report_id": report.report_id, "case_count": len(case_tuple), "policy_mutation": False},
        )
        _add_log(repository, log)
        return EvaluationBatchResult(report=report, logs=(log,), errors=(error,))

    log = LogEvent(
        correlation_id=corr,
        partition=Partition.EVALUATION,
        event_type=LogEventType.METRIC,
        operation_name="evaluate_batch",
        message="Computed evaluation batch metrics.",
        output_reference=report.report_id,
        details={
            "event_name": "evaluation_batch_reported",
            "report_id": report.report_id,
            "case_count": len(case_tuple),
            "metrics": dict(report.metrics),
            "failure_counts": dict(report.failure_counts),
            "latency_ms_by_partition": dict(report.latency_ms_by_partition),
            "cost_by_partition": dict(report.cost_by_partition),
            "improvement_task_ids": list(report.improvement_task_ids),
            "policy_mutation": False,
        },
    )
    _add_log(repository, log)
    return EvaluationBatchResult(report=report, logs=(log,))


def build_observability_report(
    logs: Iterable[LogEvent],
    errors: Iterable[ErrorEnvelope] = (),
    *,
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> ObservabilityReportResult:
    """Summarize telemetry into dashboard-ready partition counters."""

    corr = correlation_id or new_correlation_id("evaluation")
    log_tuple = tuple(logs)
    error_tuple = tuple(errors)
    report = ObservabilityReport(
        log_counts_by_partition=_count_by_partition(log_tuple),
        event_counts=_count_event_names(log_tuple),
        error_counts_by_partition=_count_by_partition(error_tuple),
        latency_ms_by_partition=_sum_log_values(log_tuple, "duration_ms"),
        cost_by_partition=_sum_log_values(log_tuple, "cost_estimate"),
    )
    try:
        _save_observability_report(repository, report)
    except Exception as exc:
        error = create_error_envelope(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="build_observability_report",
            error_type=ErrorType.STORAGE,
            error_message=f"Observability report write failed: {exc}",
            retryable=True,
            fallback_action=FallbackAction.RETRY,
            details={"report_id": report.report_id},
        )
        _save_error(repository, error)
        log = create_error_log_event(
            correlation_id=corr,
            partition=Partition.EVALUATION,
            operation_name="build_observability_report",
            event_name="observability_report_store_failed",
            error_type=ErrorType.STORAGE,
            message="Observability report write failed; summary remains available for retry.",
            fallback_action=FallbackAction.RETRY,
            details={"report_id": report.report_id, "policy_mutation": False},
        )
        _add_log(repository, log)
        return ObservabilityReportResult(report=report, logs=(log,), errors=(error,))

    log = LogEvent(
        correlation_id=corr,
        partition=Partition.EVALUATION,
        event_type=LogEventType.METRIC,
        operation_name="build_observability_report",
        message="Created observability report.",
        output_reference=report.report_id,
        details={
            "event_name": "observability_report_created",
            "report_id": report.report_id,
            "log_counts_by_partition": dict(report.log_counts_by_partition),
            "event_counts": dict(report.event_counts),
            "error_counts_by_partition": dict(report.error_counts_by_partition),
            "latency_ms_by_partition": dict(report.latency_ms_by_partition),
            "cost_by_partition": dict(report.cost_by_partition),
            "policy_mutation": False,
        },
    )
    _add_log(repository, log)
    return ObservabilityReportResult(report=report, logs=(log,))


def _batch_metrics(cases: tuple[EvaluationDatasetCase, ...]) -> dict[str, float | int]:
    case_count = len(cases)
    expected_cases = [case for case in cases if case.expected_evidence_ids]
    validation_cases = [case for case in cases if case.validation is not None]
    reranker_cases = [case for case in expected_cases if case.baseline_ranked_evidence_ids]
    graph_expected_cases = [case for case in cases if RetrievalMode.GRAPH in case.expected_modes]
    graph_observed_cases = [
        case for case in graph_expected_cases if any(candidate.retrieval_mode is RetrievalMode.GRAPH for candidate in case.evidence)
    ]
    metrics: dict[str, float | int] = {
        "case_count": case_count,
        "retrieval_recall": _average(_case_retrieval_recall(case) for case in expected_cases),
        "citation_precision": _average(_case_citation_precision(case) for case in cases),
        "unsupported_claim_rate": _safe_rate(_unsupported_claim_count(cases), _claim_count(cases)),
        "validator_rejection_rate": _safe_rate(
            sum(
                1
                for case in validation_cases
                if case.validation is not None and case.validation.validation_status is not ValidationStatus.PASS
            ),
            len(validation_cases),
        ),
        "graph_hit_rate": _safe_rate(len(graph_observed_cases), len(graph_expected_cases)),
        "reranker_improvement": _average(_case_reranker_improvement(case) for case in reranker_cases),
    }
    return metrics


def _case_retrieval_recall(case: EvaluationDatasetCase) -> float:
    observed = {candidate.evidence_id for candidate in case.evidence}
    expected = set(case.expected_evidence_ids)
    return _safe_rate(len(expected & observed), len(expected))


def _case_citation_precision(case: EvaluationDatasetCase) -> float:
    evidence_ids = {candidate.evidence_id for candidate in case.evidence}
    citation_ids: list[str] = []
    for values in case.answer.citation_map.values():
        citation_ids.extend(value for value in values if value in evidence_ids)
    return _safe_rate(len(set(citation_ids)), len(citation_ids)) if citation_ids else 1.0


def _case_reranker_improvement(case: EvaluationDatasetCase) -> float:
    if not case.baseline_ranked_evidence_ids:
        return 0.0
    current = [candidate.evidence_id for candidate in case.evidence]
    expected = set(case.expected_evidence_ids)
    current_best = _best_rank(current, expected)
    baseline_best = _best_rank(case.baseline_ranked_evidence_ids, expected)
    if baseline_best is None or current_best is None:
        return 0.0
    return float(baseline_best - current_best)


def _best_rank(ids: Iterable[str], expected: set[str]) -> int | None:
    for index, evidence_id in enumerate(ids, start=1):
        if evidence_id in expected:
            return index
    return None


def _claim_count(cases: tuple[EvaluationDatasetCase, ...]) -> int:
    return sum(len(case.answer.claim_records) for case in cases)


def _unsupported_claim_count(cases: tuple[EvaluationDatasetCase, ...]) -> int:
    total = 0
    unsupported = {SupportStatus.UNSUPPORTED, SupportStatus.CONTRADICTED, SupportStatus.NOT_CHECKED}
    for case in cases:
        for claim in case.answer.claim_records:
            status = claim.get("support_status") if isinstance(claim, dict) else claim.support_status
            if isinstance(status, str):
                total += status in {item.value for item in unsupported}
            else:
                total += status in unsupported
    return total


def _failure_counts(cases: tuple[EvaluationDatasetCase, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for item in case.feedback:
            if item.failure_category is None:
                continue
            counts[item.failure_category.value] = counts.get(item.failure_category.value, 0) + 1
    return dict(sorted(counts.items()))


def _count_by_partition(items: Iterable[LogEvent | ErrorEnvelope]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = item.partition.value
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_event_names(logs: tuple[LogEvent, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for log in logs:
        name = log.details.get("event_name") if isinstance(log.details, dict) else None
        key = str(name or log.event_type.value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _sum_log_values(logs: tuple[LogEvent, ...], attribute_name: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for log in logs:
        value = getattr(log, attribute_name)
        if value is None:
            continue
        key = log.partition.value
        totals[key] = totals.get(key, 0.0) + float(value)
    return dict(sorted(totals.items()))


def _sum_case_mapping(cases: tuple[EvaluationDatasetCase, ...], attribute_name: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for case in cases:
        mapping = getattr(case, attribute_name)
        for key, value in mapping.items():
            totals[key] = totals.get(key, 0.0) + float(value)
    return dict(sorted(totals.items()))


def _average(values: Iterable[float]) -> float:
    value_tuple = tuple(values)
    if not value_tuple:
        return 0.0
    return sum(value_tuple) / len(value_tuple)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _claim_ids(answer: AnswerRecord) -> tuple[str, ...]:
    claim_ids: list[str] = []
    for claim in answer.claim_records:
        if isinstance(claim, dict):
            claim_id = claim.get("claim_id")
        else:
            claim_id = claim.claim_id
        if isinstance(claim_id, str) and claim_id:
            claim_ids.append(claim_id)
    return tuple(dict.fromkeys(claim_ids))


def _unique(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _save_trace(repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None, trace: EvaluationTraceRecord) -> None:
    if repository is not None and hasattr(repository, "save_trace"):
        repository.save_trace(trace)


def _save_evaluation_case(
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None,
    case: EvaluationDatasetCase,
) -> None:
    if repository is not None and hasattr(repository, "save_evaluation_case"):
        repository.save_evaluation_case(case)


def _save_evaluation_report(
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None,
    report: EvaluationBatchReport,
) -> None:
    if repository is not None and hasattr(repository, "save_evaluation_report"):
        repository.save_evaluation_report(report)


def _save_observability_report(
    repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None,
    report: ObservabilityReport,
) -> None:
    if repository is not None and hasattr(repository, "save_observability_report"):
        repository.save_observability_report(report)


def _add_log(repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None, log: LogEvent) -> LogEvent:
    if repository is not None and hasattr(repository, "add_log"):
        repository.add_log(log)
    return log


def _save_error(repository: InMemoryEvaluationRepository | InMemoryStorageRepository | None, error: ErrorEnvelope) -> None:
    if repository is not None and hasattr(repository, "save_error"):
        repository.save_error(error)


__all__ = [
    "PARTITION",
    "EvaluationBatchReport",
    "EvaluationBatchResult",
    "EvaluationDatasetCase",
    "EvaluationTraceRecord",
    "EvaluationTraceResult",
    "InMemoryEvaluationRepository",
    "ObservabilityReport",
    "ObservabilityReportResult",
    "build_evaluation_case",
    "build_observability_report",
    "evaluate_batch",
    "store_evaluation_trace",
]
