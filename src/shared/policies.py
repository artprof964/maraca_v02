"""Shared logging and error policy defaults for Milestone 0."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
)


@dataclass(frozen=True, slots=True)
class LogExpectation:
    """Expected operation/event pair for baseline log checklist tests."""

    partition: Partition
    operation_name: str
    event_name: str
    acceptable_event_names: tuple[str, ...] = ()

    def accepted_events(self) -> tuple[str, ...]:
        """Return all event names that satisfy this expectation."""
        return self.acceptable_event_names or (self.event_name,)


DEFAULT_FALLBACK_ACTIONS: Mapping[Partition, tuple[FallbackAction, ...]] = MappingProxyType(
    {
        Partition.SOURCE_REGISTRY: (FallbackAction.ESCALATE, FallbackAction.STOP),
        Partition.INGESTION: (
            FallbackAction.RETRY,
            FallbackAction.PARTIAL_COMMIT,
            FallbackAction.STOP,
        ),
        Partition.ENRICHMENT: (FallbackAction.SKIP,),
        Partition.STORAGE: (FallbackAction.RETRY, FallbackAction.STOP),
        Partition.PLANNING: (FallbackAction.CLARIFY, FallbackAction.STOP),
        Partition.RETRIEVAL: (FallbackAction.SKIP, FallbackAction.STOP),
        Partition.RANKING: (FallbackAction.SKIP,),
        Partition.VALIDATION: (FallbackAction.REPAIR, FallbackAction.STOP),
        Partition.SYNTHESIS: (FallbackAction.REPAIR, FallbackAction.STOP),
        Partition.FEEDBACK: (FallbackAction.RETRY, FallbackAction.ESCALATE),
        Partition.EVALUATION: (FallbackAction.RETRY, FallbackAction.ESCALATE),
    }
)

SUCCESSFUL_INGESTION_LOG_EXPECTATIONS: tuple[LogExpectation, ...] = (
    LogExpectation(Partition.SOURCE_REGISTRY, "register_source", "source_registered"),
    LogExpectation(Partition.SOURCE_REGISTRY, "check_source_access", "source_access_checked"),
    LogExpectation(Partition.INGESTION, "start_ingestion_job", "ingestion_started"),
    LogExpectation(Partition.INGESTION, "extract_source_content", "extraction_completed"),
    LogExpectation(Partition.STORAGE, "commit_chunks", "chunks_committed"),
    LogExpectation(
        Partition.STORAGE,
        "commit_vectors",
        "vectors_committed",
        ("vectors_committed", "vectors_degraded"),
    ),
    LogExpectation(
        Partition.STORAGE,
        "commit_sparse_index",
        "sparse_index_committed",
        ("sparse_index_committed", "sparse_index_degraded"),
    ),
    LogExpectation(Partition.STORAGE, "verify_storage_commit", "storage_verified"),
    LogExpectation(Partition.INGESTION, "complete_ingestion_job", "ingestion_completed"),
)

SUCCESSFUL_QUERY_LOG_EXPECTATIONS: tuple[LogExpectation, ...] = (
    LogExpectation(Partition.PLANNING, "classify_query", "query_classified"),
    LogExpectation(Partition.PLANNING, "select_retrieval_modes", "retrieval_modes_selected"),
    LogExpectation(Partition.PLANNING, "set_retrieval_budget", "retrieval_budget_set"),
    LogExpectation(Partition.RETRIEVAL, "run_retrieval", "retrieval_completed"),
    LogExpectation(Partition.RANKING, "select_ranked_evidence", "evidence_selected"),
    LogExpectation(Partition.VALIDATION, "validate_answer_evidence", "validation_passed"),
    LogExpectation(Partition.SYNTHESIS, "create_claim_records", "claim_records_created"),
    LogExpectation(Partition.SYNTHESIS, "generate_answer", "answer_generated"),
)

SUCCESSFUL_QUERY_OPTIONAL_LOG_EXPECTATIONS: tuple[LogExpectation, ...] = (
    LogExpectation(Partition.FEEDBACK, "capture_feedback", "feedback_captured"),
)

REQUIRED_ERROR_TYPES_BY_PARTITION: Mapping[Partition, tuple[ErrorType, ...]] = MappingProxyType(
    {
        Partition.SOURCE_REGISTRY: (ErrorType.ACCESS, ErrorType.POLICY),
        Partition.INGESTION: (
            ErrorType.NETWORK,
            ErrorType.TIMEOUT,
            ErrorType.PARSING,
            ErrorType.EXTRACTION,
        ),
        Partition.ENRICHMENT: (ErrorType.MODEL, ErrorType.EXTRACTION),
        Partition.STORAGE: (ErrorType.STORAGE,),
        Partition.PLANNING: (ErrorType.POLICY, ErrorType.VALIDATION),
        Partition.RETRIEVAL: (ErrorType.TIMEOUT, ErrorType.ACCESS, ErrorType.NETWORK),
        Partition.RANKING: (ErrorType.MODEL,),
        Partition.VALIDATION: (ErrorType.VALIDATION, ErrorType.ACCESS),
        Partition.SYNTHESIS: (ErrorType.MODEL, ErrorType.VALIDATION),
        Partition.FEEDBACK: (ErrorType.STORAGE, ErrorType.POLICY),
        Partition.EVALUATION: (ErrorType.STORAGE,),
    }
)


def default_fallback_action(partition: Partition) -> FallbackAction:
    """Return the first baseline fallback action for a partition."""
    return DEFAULT_FALLBACK_ACTIONS[partition][0]


def _details_with_event(
    event_name: str | None,
    details: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(details or {})
    if event_name is not None:
        merged.setdefault("event_name", event_name)
    return merged


def create_start_log_event(
    *,
    correlation_id: str,
    partition: Partition,
    operation_name: str,
    event_name: str | None = None,
    message: str | None = None,
    input_reference: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> LogEvent:
    """Create a shared start log event without committing to a log backend."""
    return LogEvent(
        correlation_id=correlation_id,
        partition=partition,
        event_type=LogEventType.START,
        operation_name=operation_name,
        message=message or f"Started {operation_name}.",
        input_reference=input_reference,
        details=_details_with_event(event_name, details),
    )


def create_success_log_event(
    *,
    correlation_id: str,
    partition: Partition,
    operation_name: str,
    event_name: str | None = None,
    message: str | None = None,
    output_reference: str | None = None,
    duration_ms: float | None = None,
    details: Mapping[str, Any] | None = None,
) -> LogEvent:
    """Create a shared success log event without committing to a log backend."""
    return LogEvent(
        correlation_id=correlation_id,
        partition=partition,
        event_type=LogEventType.SUCCESS,
        operation_name=operation_name,
        message=message or f"Completed {operation_name}.",
        output_reference=output_reference,
        duration_ms=duration_ms,
        details=_details_with_event(event_name, details),
    )


def create_error_envelope(
    *,
    correlation_id: str,
    partition: Partition,
    operation_name: str,
    error_type: ErrorType,
    error_message: str,
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE,
    retryable: bool = False,
    fallback_action: FallbackAction | None = None,
    retry_count: int = 0,
    max_retries: int = 0,
    details: Mapping[str, Any] | None = None,
) -> ErrorEnvelope:
    """Create an error envelope using the partition's baseline fallback."""
    return ErrorEnvelope(
        correlation_id=correlation_id,
        partition=partition,
        operation_name=operation_name,
        severity=severity,
        error_type=error_type,
        error_message=error_message,
        retryable=retryable,
        retry_count=retry_count,
        max_retries=max_retries,
        fallback_action=fallback_action or default_fallback_action(partition),
        details=dict(details or {}),
    )


def create_error_telemetry(
    *,
    correlation_id: str,
    partition: Partition,
    operation_name: str,
    error_type: ErrorType,
    error_message: str,
    log_message: str,
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE,
    retryable: bool = False,
    fallback_action: FallbackAction | None = None,
    retry_count: int = 0,
    max_retries: int = 0,
    event_name: str | None = None,
    error_details: Mapping[str, Any] | None = None,
    log_details: Mapping[str, Any] | None = None,
) -> tuple[ErrorEnvelope, LogEvent]:
    """Create paired error envelope and error log telemetry."""
    error = create_error_envelope(
        correlation_id=correlation_id,
        partition=partition,
        operation_name=operation_name,
        error_type=error_type,
        error_message=error_message,
        severity=severity,
        retryable=retryable,
        fallback_action=fallback_action,
        retry_count=retry_count,
        max_retries=max_retries,
        details=error_details,
    )
    log = create_error_log_event(
        correlation_id=correlation_id,
        partition=partition,
        operation_name=operation_name,
        error_type=error_type,
        message=log_message,
        event_name=event_name,
        fallback_action=fallback_action,
        retry_count=retry_count,
        details=log_details,
    )
    return error, log


def create_error_log_event(
    *,
    correlation_id: str,
    partition: Partition,
    operation_name: str,
    error_type: ErrorType,
    message: str,
    event_name: str | None = None,
    fallback_action: FallbackAction | None = None,
    retry_count: int = 0,
    details: Mapping[str, Any] | None = None,
) -> LogEvent:
    """Create a shared error log event without creating runtime infrastructure."""
    merged_details = _details_with_event(event_name, details)
    merged_details.setdefault("error_type", error_type.value)
    merged_details.setdefault(
        "fallback_action",
        (fallback_action or default_fallback_action(partition)).value,
    )
    merged_details.setdefault("retry_count", retry_count)

    return LogEvent(
        correlation_id=correlation_id,
        partition=partition,
        event_type=LogEventType.ERROR,
        operation_name=operation_name,
        message=message,
        details=merged_details,
    )
