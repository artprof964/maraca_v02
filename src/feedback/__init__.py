"""Dependency-free feedback capture for early Milestone 1."""

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
    Partition,
    _serialize_contract,
    _utc_now,
    new_correlation_id,
)
from shared.policies import (
    create_error_envelope,
    create_error_log_event,
    create_error_telemetry,
    create_success_log_event,
)
from shared.repository_hooks import add_repository_log, call_repository_hook, save_repository_error
from shared.records import (
    AnswerRecord,
    CitationStatus,
    EvidenceCandidate,
    FailureCategory,
    FeedbackRecord,
    FreshnessStatus,
    ReviewerType,
    UserRating,
    ValidationCriterion,
    ValidationRecord,
    ValidationStatus,
)

try:
    from storage import InMemoryStorageRepository
except ImportError:  # pragma: no cover - keeps the type optional for isolated imports.
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]

PARTITION = "feedback"


@dataclass(frozen=True, slots=True)
class FeedbackTraceReference:
    """Append-only references to the answer context that received feedback."""

    request_id: str
    answer_id: str
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    citation_links: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    validation_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "answer_id": self.answer_id,
            "evidence_ids": list(self.evidence_ids),
            "source_ids": list(self.source_ids),
            "document_ids": list(self.document_ids),
            "chunk_ids": list(self.chunk_ids),
            "citation_links": list(self.citation_links),
            "claim_ids": list(self.claim_ids),
            "validation_id": self.validation_id,
        }


@dataclass(frozen=True, slots=True)
class FeedbackCaptureResult:
    """Captured feedback plus emitted telemetry."""

    feedback: FeedbackRecord
    trace_reference: FeedbackTraceReference
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(frozen=True, slots=True)
class ImprovementTaskRecord:
    """Append-only work item derived from feedback and evaluation context."""

    request_id: str
    answer_id: str
    failure_category: FailureCategory
    title: str
    recommended_action: str
    feedback_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    validation_id: str | None = None
    evaluation_trace_id: str | None = None
    metric_signals: Mapping[str, float | int | str | bool] = field(default_factory=dict)
    priority: int = 3
    status: str = "queued"
    policy_mutation: bool = False
    created_at: datetime = field(default_factory=_utc_now)
    task_id: str = field(default_factory=lambda: f"improve_{uuid4().hex}")

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(
            {
                "request_id": self.request_id,
                "answer_id": self.answer_id,
                "failure_category": self.failure_category,
                "title": self.title,
                "recommended_action": self.recommended_action,
                "feedback_ids": list(self.feedback_ids),
                "evidence_ids": list(self.evidence_ids),
                "source_ids": list(self.source_ids),
                "document_ids": list(self.document_ids),
                "chunk_ids": list(self.chunk_ids),
                "claim_ids": list(self.claim_ids),
                "validation_id": self.validation_id,
                "evaluation_trace_id": self.evaluation_trace_id,
                "metric_signals": dict(self.metric_signals),
                "priority": self.priority,
                "status": self.status,
                "policy_mutation": self.policy_mutation,
                "created_at": self.created_at,
                "task_id": self.task_id,
            }
        )


@dataclass(frozen=True, slots=True)
class ImprovementTaskResult:
    """Generated improvement tasks plus emitted telemetry."""

    tasks: tuple[ImprovementTaskRecord, ...] = ()
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(slots=True)
class InMemoryFeedbackRepository:
    """Small append-only feedback store used before durable storage exists."""

    feedback: dict[str, FeedbackRecord] = field(default_factory=dict)
    trace_references: dict[str, FeedbackTraceReference] = field(default_factory=dict)
    improvement_tasks: dict[str, ImprovementTaskRecord] = field(default_factory=dict)
    logs: dict[str, LogEvent] = field(default_factory=dict)
    errors: dict[str, ErrorEnvelope] = field(default_factory=dict)

    def save_feedback(self, feedback: FeedbackRecord, trace_reference: FeedbackTraceReference) -> FeedbackRecord:
        self.feedback[feedback.feedback_id] = feedback
        self.trace_references[feedback.feedback_id] = trace_reference
        return feedback

    def save_improvement_task(self, task: ImprovementTaskRecord) -> ImprovementTaskRecord:
        self.improvement_tasks[task.task_id] = task
        return task

    def add_log(self, log: LogEvent) -> LogEvent:
        self.logs[log.log_id] = log
        return log

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        self.errors[error.error_id] = error
        return error


def capture_feedback(
    *,
    request_id: str,
    answer: AnswerRecord,
    user_rating: UserRating,
    evidence: Iterable[EvidenceCandidate] = (),
    validation: ValidationRecord | None = None,
    correction_text: str | None = None,
    reviewed_by: ReviewerType = ReviewerType.USER,
    failure_category: FailureCategory | None = None,
    repository: InMemoryFeedbackRepository | InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> FeedbackCaptureResult:
    """Capture user/evaluator feedback without mutating retrieval policy state."""

    corr = correlation_id or new_correlation_id("feedback")
    evidence_tuple = tuple(evidence)
    category = failure_category or classify_failure_category(
        user_rating=user_rating,
        correction_text=correction_text,
        answer=answer,
        validation=validation,
        evidence=evidence_tuple,
    )
    feedback = FeedbackRecord(
        request_id=request_id,
        answer_id=answer.answer_id,
        user_rating=user_rating,
        correction_text=correction_text,
        failure_category=category,
        reviewed_by=reviewed_by,
    )
    trace_reference = build_feedback_trace_reference(
        request_id=request_id,
        answer=answer,
        evidence=evidence_tuple,
        validation=validation,
    )
    errors: tuple[ErrorEnvelope, ...] = ()
    try:
        _save_feedback(repository, feedback, trace_reference)
    except Exception as exc:
        error, log = create_error_telemetry(
            correlation_id=corr,
            partition=Partition.FEEDBACK,
            operation_name="capture_feedback",
            error_type=ErrorType.STORAGE,
            error_message=f"Feedback write failed: {exc}",
            log_message="Feedback write failed; preserved trace for retry.",
            retryable=True,
            fallback_action=FallbackAction.RETRY,
            event_name="feedback_capture_failed",
            error_details={
                "request_id": request_id,
                "answer_id": answer.answer_id,
                "feedback_id": feedback.feedback_id,
                "trace_reference": trace_reference.to_dict(),
            },
            log_details={
                "request_id": request_id,
                "answer_id": answer.answer_id,
                "feedback_id": feedback.feedback_id,
                "trace_reference": trace_reference.to_dict(),
                "policy_mutation": False,
            },
        )
        _save_error(repository, error)
        _add_log(repository, log)
        return FeedbackCaptureResult(feedback=feedback, trace_reference=trace_reference, logs=(log,), errors=(error,))

    log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.FEEDBACK,
        operation_name="capture_feedback",
        event_name="feedback_captured",
        message="Captured answer feedback.",
        output_reference=feedback.feedback_id,
        details={
            "request_id": request_id,
            "answer_id": answer.answer_id,
            "feedback_id": feedback.feedback_id,
            "user_rating": user_rating.value,
            "failure_category": category.value if category is not None else None,
            "evidence_ids": list(trace_reference.evidence_ids),
            "policy_mutation": False,
        },
    )
    _add_log(repository, log)
    return FeedbackCaptureResult(feedback=feedback, trace_reference=trace_reference, logs=(log,), errors=errors)


def create_improvement_tasks(
    *,
    feedback: FeedbackRecord | Iterable[FeedbackRecord],
    trace_reference: FeedbackTraceReference | None = None,
    evaluation_trace: object | None = None,
    metrics: Mapping[str, float | int | str | bool] | None = None,
    repository: InMemoryFeedbackRepository | object | None = None,
    correlation_id: str | None = None,
) -> ImprovementTaskResult:
    """Create improvement tasks from feedback/evaluation context without policy mutation."""

    corr = correlation_id or new_correlation_id("feedback_improvement")
    feedback_tuple = _feedback_tuple(feedback)
    context = _improvement_context(trace_reference=trace_reference, evaluation_trace=evaluation_trace)
    metric_signals = _metric_signals(metrics, evaluation_trace)
    tasks = _build_improvement_tasks(feedback_tuple, context=context, metric_signals=metric_signals)

    try:
        for task in tasks:
            _save_improvement_task(repository, task)
    except Exception as exc:
        error = create_error_envelope(
            correlation_id=corr,
            partition=Partition.FEEDBACK,
            operation_name="create_improvement_tasks",
            error_type=ErrorType.STORAGE,
            error_message=f"Improvement task write failed: {exc}",
            retryable=True,
            fallback_action=FallbackAction.RETRY,
            details={
                "task_ids": [task.task_id for task in tasks],
                "feedback_ids": _unique(item.feedback_id for item in feedback_tuple),
            },
        )
        _save_error(repository, error)
        log = create_error_log_event(
            correlation_id=corr,
            partition=Partition.FEEDBACK,
            operation_name="create_improvement_tasks",
            event_name="improvement_task_creation_failed",
            error_type=ErrorType.STORAGE,
            message="Improvement task write failed; task records are returned for retry.",
            fallback_action=FallbackAction.RETRY,
            details={
                "task_count": len(tasks),
                "task_ids": [task.task_id for task in tasks],
                "policy_mutation": False,
            },
        )
        _add_log(repository, log)
        return ImprovementTaskResult(tasks=tasks, logs=(log,), errors=(error,))

    log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.FEEDBACK,
        operation_name="create_improvement_tasks",
        event_name="improvement_tasks_created",
        message="Created feedback improvement task records.",
        output_reference=",".join(task.task_id for task in tasks) or None,
        details={
            "task_count": len(tasks),
            "task_ids": [task.task_id for task in tasks],
            "failure_categories": [task.failure_category.value for task in tasks],
            "feedback_ids": _unique(item.feedback_id for item in feedback_tuple),
            "evaluation_trace_id": context["evaluation_trace_id"],
            "policy_mutation": False,
        },
    )
    _add_log(repository, log)
    return ImprovementTaskResult(tasks=tasks, logs=(log,))


def build_feedback_trace_reference(
    *,
    request_id: str,
    answer: AnswerRecord,
    evidence: Iterable[EvidenceCandidate] = (),
    validation: ValidationRecord | None = None,
) -> FeedbackTraceReference:
    """Collect request, answer, claim, evidence, and citation references."""

    evidence_tuple = tuple(evidence)
    return FeedbackTraceReference(
        request_id=request_id,
        answer_id=answer.answer_id,
        evidence_ids=_unique(candidate.evidence_id for candidate in evidence_tuple),
        source_ids=_unique(candidate.source_id for candidate in evidence_tuple),
        document_ids=_unique(candidate.document_id for candidate in evidence_tuple),
        chunk_ids=_unique(candidate.chunk_id for candidate in evidence_tuple),
        citation_links=_unique(candidate.citation_link for candidate in evidence_tuple),
        claim_ids=_claim_ids(answer),
        validation_id=validation.validation_id if validation is not None else answer.validation_id,
    )


def classify_failure_category(
    *,
    user_rating: UserRating,
    correction_text: str | None = None,
    answer: AnswerRecord | None = None,
    validation: ValidationRecord | None = None,
    evidence: Iterable[EvidenceCandidate] = (),
) -> FailureCategory | None:
    """Classify feedback into the shared failure taxonomy using explicit signals."""

    text = " ".join(
        part
        for part in (
            correction_text or "",
            " ".join(answer.limitations) if answer is not None else "",
            validation.validator_notes if validation is not None and validation.validator_notes else "",
        )
        if part
    ).lower()
    category = _category_from_text(text)
    if category is not None:
        return category

    if validation is not None:
        category = _category_from_validation(validation)
        if category is not None:
            return category

    evidence_tuple = tuple(evidence)
    if evidence_tuple and all(candidate.exclusion_reason for candidate in evidence_tuple):
        return FailureCategory.ACCESS

    if user_rating is UserRating.USEFUL:
        return None
    if user_rating is UserRating.NOT_USEFUL:
        return FailureCategory.RETRIEVAL
    if user_rating is UserRating.PARTIALLY_USEFUL:
        return FailureCategory.VALIDATION
    return FailureCategory.SYNTHESIS


def _category_from_text(text: str) -> FailureCategory | None:
    keyword_groups: tuple[tuple[FailureCategory, tuple[str, ...]], ...] = (
        (FailureCategory.ACCESS, ("access", "restricted", "confidential", "permission", "secret", "leak")),
        (FailureCategory.FRESHNESS, ("fresh", "stale", "outdated", "old", "obsolete", "expired")),
        (FailureCategory.RANKING, ("rank", "ranking", "top result", "buried", "irrelevant first")),
        (FailureCategory.RETRIEVAL, ("missing source", "wrong source", "not retrieved", "no evidence", "could not find")),
        (FailureCategory.UNCLEAR_QUERY, ("unclear", "ambiguous", "vague", "clarify")),
        (FailureCategory.SYNTHESIS, ("citation", "cite", "unsupported", "hallucinat", "answer is wrong")),
    )
    for category, keywords in keyword_groups:
        if any(keyword in text for keyword in keywords):
            return category
    return None


def _category_from_validation(validation: ValidationRecord) -> FailureCategory | None:
    failed = set(validation.failed_criteria)
    if ValidationCriterion.ACCESS in failed:
        return FailureCategory.ACCESS
    if ValidationCriterion.FRESHNESS in failed or validation.freshness_status is FreshnessStatus.STALE:
        return FailureCategory.FRESHNESS
    if validation.citation_status is CitationStatus.MISSING:
        return FailureCategory.SYNTHESIS
    if ValidationCriterion.RELEVANCE in failed or ValidationCriterion.SUFFICIENCY in failed:
        return FailureCategory.RETRIEVAL
    if validation.validation_status in {ValidationStatus.FAIL, ValidationStatus.REPAIR_NEEDED}:
        return FailureCategory.VALIDATION
    return None


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


def _feedback_tuple(feedback: FeedbackRecord | Iterable[FeedbackRecord]) -> tuple[FeedbackRecord, ...]:
    if isinstance(feedback, FeedbackRecord):
        return (feedback,)
    return tuple(feedback)


def _improvement_context(
    *,
    trace_reference: FeedbackTraceReference | None,
    evaluation_trace: object | None,
) -> dict[str, object]:
    return {
        "evidence_ids": _context_tuple("evidence_ids", trace_reference, evaluation_trace),
        "source_ids": _context_tuple("source_ids", trace_reference, evaluation_trace),
        "document_ids": _context_tuple("document_ids", trace_reference, evaluation_trace),
        "chunk_ids": _context_tuple("chunk_ids", trace_reference, evaluation_trace),
        "claim_ids": _context_tuple("claim_ids", trace_reference, evaluation_trace),
        "validation_id": _first_context_value("validation_id", trace_reference, evaluation_trace),
        "evaluation_trace_id": getattr(evaluation_trace, "trace_id", None),
    }


def _context_tuple(
    attribute: str,
    trace_reference: FeedbackTraceReference | None,
    evaluation_trace: object | None,
) -> tuple[str, ...]:
    values: list[str | None] = []
    for source in (trace_reference, evaluation_trace):
        if source is None:
            continue
        value = getattr(source, attribute, ())
        if value is None:
            continue
        if isinstance(value, str):
            values.append(value)
        else:
            values.extend(item for item in value if isinstance(item, str))
    return _unique(values)


def _first_context_value(
    attribute: str,
    trace_reference: FeedbackTraceReference | None,
    evaluation_trace: object | None,
) -> str | None:
    for source in (trace_reference, evaluation_trace):
        if source is None:
            continue
        value = getattr(source, attribute, None)
        if isinstance(value, str) and value:
            return value
    return None


def _metric_signals(
    metrics: Mapping[str, float | int | str | bool] | None,
    evaluation_trace: object | None,
) -> dict[str, float | int | str | bool]:
    signals: dict[str, float | int | str | bool] = {}
    trace_metrics = getattr(evaluation_trace, "metrics", None)
    if isinstance(trace_metrics, Mapping):
        signals.update({str(key): value for key, value in trace_metrics.items() if _is_metric_scalar(value)})
    if metrics is not None:
        signals.update({str(key): value for key, value in metrics.items() if _is_metric_scalar(value)})
    return signals


def _is_metric_scalar(value: object) -> bool:
    return isinstance(value, str | bool | int | float)


def _build_improvement_tasks(
    feedback: tuple[FeedbackRecord, ...],
    *,
    context: dict[str, object],
    metric_signals: Mapping[str, float | int | str | bool],
) -> tuple[ImprovementTaskRecord, ...]:
    categories = _task_categories(feedback)
    if not categories:
        return ()

    request_id = _first_feedback_value(feedback, "request_id")
    answer_id = _first_feedback_value(feedback, "answer_id")
    feedback_ids = _unique(item.feedback_id for item in feedback)
    tasks: list[ImprovementTaskRecord] = []
    for category in categories:
        tasks.append(
            ImprovementTaskRecord(
                request_id=request_id,
                answer_id=answer_id,
                failure_category=category,
                title=_task_title(category),
                recommended_action=_task_action(category),
                feedback_ids=feedback_ids,
                evidence_ids=context["evidence_ids"],  # type: ignore[arg-type]
                source_ids=context["source_ids"],  # type: ignore[arg-type]
                document_ids=context["document_ids"],  # type: ignore[arg-type]
                chunk_ids=context["chunk_ids"],  # type: ignore[arg-type]
                claim_ids=context["claim_ids"],  # type: ignore[arg-type]
                validation_id=context["validation_id"],  # type: ignore[arg-type]
                evaluation_trace_id=context["evaluation_trace_id"],  # type: ignore[arg-type]
                metric_signals=dict(metric_signals),
                priority=_task_priority(category, feedback, metric_signals),
            )
        )
    return tuple(tasks)


def _task_categories(feedback: tuple[FeedbackRecord, ...]) -> tuple[FailureCategory, ...]:
    categories: list[FailureCategory] = []
    for item in feedback:
        category = item.failure_category or _category_from_rating(item.user_rating)
        if category is not None:
            categories.append(category)
    return tuple(dict.fromkeys(categories))


def _category_from_rating(user_rating: UserRating) -> FailureCategory | None:
    if user_rating is UserRating.USEFUL:
        return None
    if user_rating is UserRating.NOT_USEFUL:
        return FailureCategory.RETRIEVAL
    if user_rating is UserRating.PARTIALLY_USEFUL:
        return FailureCategory.VALIDATION
    return FailureCategory.SYNTHESIS


def _first_feedback_value(feedback: tuple[FeedbackRecord, ...], attribute: str) -> str:
    for item in feedback:
        value = getattr(item, attribute)
        if isinstance(value, str) and value:
            return value
    return ""


def _task_title(category: FailureCategory) -> str:
    return {
        FailureCategory.RETRIEVAL: "Improve retrieval coverage",
        FailureCategory.RANKING: "Tune evidence ranking",
        FailureCategory.VALIDATION: "Strengthen validation repair",
        FailureCategory.SYNTHESIS: "Repair answer synthesis",
        FailureCategory.FRESHNESS: "Refresh stale evidence",
        FailureCategory.ACCESS: "Review access-safe evidence handling",
        FailureCategory.UNCLEAR_QUERY: "Improve clarification handling",
    }[category]


def _task_action(category: FailureCategory) -> str:
    return {
        FailureCategory.RETRIEVAL: "Inspect missing evidence patterns and add a retrieval repair case.",
        FailureCategory.RANKING: "Compare selected evidence order with feedback and add a ranking regression case.",
        FailureCategory.VALIDATION: "Add or adjust validation checks so repair is triggered before answer delivery.",
        FailureCategory.SYNTHESIS: "Review cited claims and add a synthesis regression case for unsupported content.",
        FailureCategory.FRESHNESS: "Identify stale evidence references and queue ingestion or freshness validation follow-up.",
        FailureCategory.ACCESS: "Audit evidence selection for access-safe alternatives without changing source policy.",
        FailureCategory.UNCLEAR_QUERY: "Add a clarification prompt case for ambiguous requests.",
    }[category]


def _task_priority(
    category: FailureCategory,
    feedback: tuple[FeedbackRecord, ...],
    metric_signals: Mapping[str, float | int | str | bool],
) -> int:
    if any(item.user_rating is UserRating.INCORRECT for item in feedback):
        return 1
    if category in {FailureCategory.ACCESS, FailureCategory.FRESHNESS}:
        return 1
    if any(_low_metric(value) for value in metric_signals.values()):
        return 2
    if any(item.user_rating is UserRating.NOT_USEFUL for item in feedback):
        return 2
    return 3


def _low_metric(value: float | int | str | bool) -> bool:
    if isinstance(value, bool):
        return value is False
    if isinstance(value, int | float):
        return value < 0.5
    return value.lower() in {"fail", "failed", "low", "missing", "false"}


def _save_feedback(
    repository: InMemoryFeedbackRepository | InMemoryStorageRepository | None,
    feedback: FeedbackRecord,
    trace_reference: FeedbackTraceReference,
) -> None:
    call_repository_hook(repository, "save_feedback", feedback, trace_reference)


def _add_log(repository: InMemoryFeedbackRepository | InMemoryStorageRepository | None, log: LogEvent) -> LogEvent:
    return add_repository_log(repository, log)


def _save_improvement_task(repository: InMemoryFeedbackRepository | object | None, task: ImprovementTaskRecord) -> None:
    call_repository_hook(repository, "save_improvement_task", task)


def _save_error(repository: InMemoryFeedbackRepository | InMemoryStorageRepository | None, error: ErrorEnvelope) -> None:
    save_repository_error(repository, error)


__all__ = [
    "PARTITION",
    "FeedbackCaptureResult",
    "FeedbackTraceReference",
    "ImprovementTaskRecord",
    "ImprovementTaskResult",
    "InMemoryFeedbackRepository",
    "build_feedback_trace_reference",
    "capture_feedback",
    "classify_failure_category",
    "create_improvement_tasks",
]
