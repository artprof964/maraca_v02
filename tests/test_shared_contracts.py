from datetime import UTC

from shared import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    new_correlation_id,
)


def test_new_correlation_id_uses_prefix_and_unique_value() -> None:
    first_id = new_correlation_id("req")
    second_id = new_correlation_id("req")

    assert first_id.startswith("req_")
    assert second_id.startswith("req_")
    assert first_id != second_id


def test_error_envelope_carries_trace_partition_and_retry_policy() -> None:
    correlation_id = new_correlation_id("ingestion")
    envelope = ErrorEnvelope(
        correlation_id=correlation_id,
        partition=Partition.INGESTION,
        operation_name="extract_source_content",
        severity=ErrorSeverity.RECOVERABLE,
        error_type=ErrorType.PARSING,
        error_message="Could not parse fixture document.",
        retryable=True,
        retry_count=1,
        max_retries=3,
        fallback_action=FallbackAction.RETRY,
    )

    payload = envelope.to_dict()

    assert envelope.error_id.startswith("err_")
    assert payload["correlation_id"] == correlation_id
    assert payload["partition"] == "ingestion"
    assert payload["severity"] == "recoverable"
    assert payload["fallback_action"] == "retry"
    assert payload["retryable"] is True
    assert payload["created_at"].endswith("+00:00")
    assert envelope.created_at.tzinfo is UTC


def test_log_event_carries_shared_trace_fields() -> None:
    correlation_id = new_correlation_id("query")
    event = LogEvent(
        correlation_id=correlation_id,
        partition=Partition.PLANNING,
        event_type=LogEventType.DECISION,
        operation_name="select_retrieval_modes",
        input_reference="request_123",
        output_reference="plan_123",
        model_or_tool="planner",
        message="Selected hybrid retrieval for source-backed query.",
    )

    payload = event.to_dict()

    assert event.log_id.startswith("log_")
    assert payload["correlation_id"] == correlation_id
    assert payload["event_type"] == "decision"
    assert payload["partition"] == "planning"
    assert payload["created_at"].endswith("+00:00")
