from shared import (
    DEFAULT_FALLBACK_ACTIONS,
    REQUIRED_ERROR_TYPES_BY_PARTITION,
    SUCCESSFUL_INGESTION_LOG_EXPECTATIONS,
    SUCCESSFUL_QUERY_LOG_EXPECTATIONS,
    SUCCESSFUL_QUERY_OPTIONAL_LOG_EXPECTATIONS,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEventType,
    Partition,
    create_error_envelope,
    create_error_log_event,
    create_error_telemetry,
    create_start_log_event,
    create_success_log_event,
    default_fallback_action,
    new_correlation_id,
)


def test_default_fallback_actions_follow_partition_baseline() -> None:
    assert default_fallback_action(Partition.SOURCE_REGISTRY) == FallbackAction.ESCALATE
    assert DEFAULT_FALLBACK_ACTIONS[Partition.INGESTION] == (
        FallbackAction.RETRY,
        FallbackAction.PARTIAL_COMMIT,
        FallbackAction.STOP,
    )
    assert DEFAULT_FALLBACK_ACTIONS[Partition.ENRICHMENT] == (FallbackAction.SKIP,)
    assert DEFAULT_FALLBACK_ACTIONS[Partition.STORAGE] == (
        FallbackAction.RETRY,
        FallbackAction.STOP,
    )
    assert DEFAULT_FALLBACK_ACTIONS[Partition.VALIDATION] == (
        FallbackAction.REPAIR,
        FallbackAction.STOP,
    )


def test_successful_ingestion_log_checklist_matches_required_events() -> None:
    events = {expectation.event_name for expectation in SUCCESSFUL_INGESTION_LOG_EXPECTATIONS}
    operations = {
        expectation.operation_name for expectation in SUCCESSFUL_INGESTION_LOG_EXPECTATIONS
    }
    accepted_by_operation = {
        expectation.operation_name: expectation.accepted_events()
        for expectation in SUCCESSFUL_INGESTION_LOG_EXPECTATIONS
    }

    assert events == {
        "source_registered",
        "source_access_checked",
        "ingestion_started",
        "extraction_completed",
        "chunks_committed",
        "vectors_committed",
        "sparse_index_committed",
        "storage_verified",
        "ingestion_completed",
    }
    assert "register_source" in operations
    assert "verify_storage_commit" in operations
    assert accepted_by_operation["commit_vectors"] == (
        "vectors_committed",
        "vectors_degraded",
    )
    assert accepted_by_operation["commit_sparse_index"] == (
        "sparse_index_committed",
        "sparse_index_degraded",
    )


def test_successful_query_log_checklist_matches_required_events() -> None:
    events = {expectation.event_name for expectation in SUCCESSFUL_QUERY_LOG_EXPECTATIONS}
    partitions = {
        expectation.event_name: expectation.partition
        for expectation in SUCCESSFUL_QUERY_LOG_EXPECTATIONS
    }

    assert events == {
        "query_classified",
        "retrieval_modes_selected",
        "retrieval_budget_set",
        "retrieval_completed",
        "evidence_selected",
        "validation_passed",
        "claim_records_created",
        "answer_generated",
    }
    assert "feedback_captured" not in events
    assert partitions["query_classified"] == Partition.PLANNING
    assert partitions["retrieval_completed"] == Partition.RETRIEVAL
    assert partitions["answer_generated"] == Partition.SYNTHESIS


def test_successful_query_optional_logs_capture_feedback_when_present() -> None:
    assert SUCCESSFUL_QUERY_OPTIONAL_LOG_EXPECTATIONS[0].event_name == "feedback_captured"
    assert SUCCESSFUL_QUERY_OPTIONAL_LOG_EXPECTATIONS[0].partition == Partition.FEEDBACK
    assert SUCCESSFUL_QUERY_OPTIONAL_LOG_EXPECTATIONS[0].operation_name == "capture_feedback"


def test_required_error_types_cover_expected_partition_failures() -> None:
    assert REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.SOURCE_REGISTRY] == (
        ErrorType.ACCESS,
        ErrorType.POLICY,
    )
    assert ErrorType.EXTRACTION in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.INGESTION]
    assert ErrorType.STORAGE in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.STORAGE]
    assert ErrorType.TIMEOUT in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.RETRIEVAL]
    assert ErrorType.MODEL in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.RANKING]
    assert ErrorType.VALIDATION in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.VALIDATION]
    assert ErrorType.POLICY in REQUIRED_ERROR_TYPES_BY_PARTITION[Partition.FEEDBACK]


def test_policy_helpers_create_traceable_log_events_and_error_envelope() -> None:
    correlation_id = new_correlation_id("query")

    start_event = create_start_log_event(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_started",
        input_reference="plan_123",
    )
    success_event = create_success_log_event(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_completed",
        output_reference="candidates_123",
        duration_ms=12.5,
        details={"quality_flags": ["partial_ok"]},
    )
    error_event = create_error_log_event(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="run_vector_search",
        event_name="vector_search_timeout",
        error_type=ErrorType.TIMEOUT,
        message="Vector search timed out.",
        retry_count=1,
    )
    envelope = create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="run_vector_search",
        error_type=ErrorType.TIMEOUT,
        error_message="Vector search timed out.",
        severity=ErrorSeverity.RECOVERABLE,
        retryable=True,
        retry_count=1,
        max_retries=2,
    )

    assert start_event.event_type == LogEventType.START
    assert start_event.correlation_id == correlation_id
    assert start_event.partition == Partition.RETRIEVAL
    assert start_event.operation_name == "run_retrieval"
    assert start_event.details["event_name"] == "retrieval_started"
    assert start_event.input_reference == "plan_123"
    assert success_event.event_type == LogEventType.SUCCESS
    assert success_event.correlation_id == correlation_id
    assert success_event.partition == Partition.RETRIEVAL
    assert success_event.operation_name == "run_retrieval"
    assert success_event.details["event_name"] == "retrieval_completed"
    assert success_event.details["quality_flags"] == ["partial_ok"]
    assert success_event.output_reference == "candidates_123"
    assert error_event.event_type == LogEventType.ERROR
    assert error_event.correlation_id == correlation_id
    assert error_event.partition == Partition.RETRIEVAL
    assert error_event.operation_name == "run_vector_search"
    assert error_event.details["error_type"] == "timeout"
    assert error_event.details["fallback_action"] == "skip"
    assert error_event.details["retry_count"] == 1
    assert envelope.correlation_id == correlation_id
    assert envelope.partition == Partition.RETRIEVAL
    assert envelope.operation_name == "run_vector_search"
    assert envelope.fallback_action == FallbackAction.SKIP
    assert envelope.retryable is True
    assert envelope.to_dict()["partition"] == "retrieval"


def test_create_error_telemetry_keeps_error_and_log_details_separate() -> None:
    error, log = create_error_telemetry(
        correlation_id="corr_policy_pair",
        partition=Partition.FEEDBACK,
        operation_name="capture_feedback",
        error_type=ErrorType.STORAGE,
        error_message="Feedback write failed.",
        log_message="Feedback write failed; preserved trace for retry.",
        retryable=True,
        fallback_action=FallbackAction.RETRY,
        event_name="feedback_capture_failed",
        error_details={"request_id": "req_123"},
        log_details={"request_id": "req_123", "policy_mutation": False},
    )

    assert error.details == {"request_id": "req_123"}
    assert log.details == {
        "request_id": "req_123",
        "policy_mutation": False,
        "event_name": "feedback_capture_failed",
        "error_type": "storage",
        "fallback_action": "retry",
        "retry_count": 0,
    }
    assert "event_name" not in error.details
    assert error.retryable is True
    assert error.fallback_action == FallbackAction.RETRY


def test_create_error_telemetry_preserves_explicit_error_event_name() -> None:
    error, log = create_error_telemetry(
        correlation_id="corr_policy_pair",
        partition=Partition.RANKING,
        operation_name="select_ranked_evidence",
        error_type=ErrorType.MODEL,
        error_message="Reranker failed.",
        log_message="Reranker failed; using normalized retrieval scores.",
        fallback_action=FallbackAction.SKIP,
        event_name="reranker_fallback",
        error_details={"event_name": "reranker_fallback", "candidate_count": 2},
        log_details={"candidate_count": 2},
    )

    assert error.details == {"event_name": "reranker_fallback", "candidate_count": 2}
    assert log.details["event_name"] == "reranker_fallback"
    assert log.details["candidate_count"] == 2
