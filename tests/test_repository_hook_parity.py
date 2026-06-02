from types import SimpleNamespace

import pytest

import ranking as ranking_module
import synthesis as synthesis_module
import validation as validation_module
from planning import LangGraphCompatibleOrchestrationAdapter, RetrievalMode, run_planned_query
from shared import (
    ClaimRecord,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    ValidationRecord,
)


def _log() -> LogEvent:
    return LogEvent(
        correlation_id="corr_hook",
        partition=Partition.RANKING,
        event_type=LogEventType.SUCCESS,
        operation_name="hook_test",
        message="hook test log",
        details={"event_name": "hook_test"},
        log_id="log_hook",
    )


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        correlation_id="corr_hook",
        partition=Partition.RANKING,
        operation_name="hook_test",
        severity=ErrorSeverity.RECOVERABLE,
        error_type=ErrorType.STORAGE,
        error_message="hook test error",
        retryable=True,
        fallback_action=FallbackAction.RETRY,
        error_id="err_hook",
    )


class RecordingRepository:
    def __init__(self) -> None:
        self.logs: list[LogEvent] = []
        self.errors: list[ErrorEnvelope] = []
        self.validations: list[ValidationRecord] = []
        self.claims: list[ClaimRecord] = []

    def add_log(self, log: LogEvent) -> LogEvent:
        self.logs.append(log)
        return log

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        self.errors.append(error)
        return error

    def save_validation_record(self, validation: ValidationRecord) -> ValidationRecord:
        self.validations.append(validation)
        return validation

    def save_claim_record(self, claim: ClaimRecord) -> ClaimRecord:
        self.claims.append(claim)
        return claim


class FailingRepository(RecordingRepository):
    def add_log(self, log: LogEvent) -> LogEvent:
        raise RuntimeError("add_log failed")

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        raise RuntimeError("save_error failed")

    def save_validation_record(self, validation: ValidationRecord) -> ValidationRecord:
        raise RuntimeError("save_validation_record failed")

    def save_claim_record(self, claim: ClaimRecord) -> ClaimRecord:
        raise RuntimeError("save_claim_record failed")


class NoHookRepository:
    pass


def test_ranking_local_hooks_noop_for_none_and_direct_call_when_present() -> None:
    log = _log()
    error = _error()
    repository = RecordingRepository()

    assert ranking_module._add_log(None, log) is log
    assert ranking_module._save_error(None, error) is error
    assert ranking_module._add_log(repository, log) is log
    assert ranking_module._save_error(repository, error) is error
    assert repository.logs == [log]
    assert repository.errors == [error]


def test_ranking_local_hooks_require_methods_and_propagate_failures() -> None:
    with pytest.raises(AttributeError):
        ranking_module._add_log(NoHookRepository(), _log())
    with pytest.raises(AttributeError):
        ranking_module._save_error(NoHookRepository(), _error())
    with pytest.raises(RuntimeError, match="add_log failed"):
        ranking_module._add_log(FailingRepository(), _log())
    with pytest.raises(RuntimeError, match="save_error failed"):
        ranking_module._save_error(FailingRepository(), _error())


def test_synthesis_local_hooks_noop_for_none_and_direct_call_when_present() -> None:
    log = _log()
    error = _error()
    repository = RecordingRepository()

    assert synthesis_module._add_log(None, log) is log
    assert synthesis_module._save_error(None, error) is error
    assert synthesis_module._add_log(repository, log) is log
    assert synthesis_module._save_error(repository, error) is error
    assert repository.logs == [log]
    assert repository.errors == [error]


def test_synthesis_local_hooks_require_methods_and_propagate_failures() -> None:
    with pytest.raises(AttributeError):
        synthesis_module._add_log(NoHookRepository(), _log())
    with pytest.raises(AttributeError):
        synthesis_module._save_error(NoHookRepository(), _error())
    with pytest.raises(RuntimeError, match="add_log failed"):
        synthesis_module._add_log(FailingRepository(), _log())
    with pytest.raises(RuntimeError, match="save_error failed"):
        synthesis_module._save_error(FailingRepository(), _error())


def test_validation_local_hooks_noop_for_none_and_missing_optional_methods() -> None:
    log = _log()
    error = _error()
    validation = ValidationRecord(request_id="req_validation", validation_id="validation_hook")
    claim = ClaimRecord(request_id="req_validation", claim_text="A supported claim.", claim_id="claim_hook")
    repository = NoHookRepository()

    assert validation_module._add_log(None, log) is log
    assert validation_module._save_error(None, error) is error
    assert validation_module._save_validation(None, validation) is validation
    assert validation_module._save_claim(None, claim) is claim
    assert validation_module._add_log(repository, log) is log
    assert validation_module._save_error(repository, error) is error
    assert validation_module._save_validation(repository, validation) is validation
    assert validation_module._save_claim(repository, claim) is claim


def test_validation_local_hooks_direct_call_and_failure_propagation() -> None:
    log = _log()
    error = _error()
    validation = ValidationRecord(request_id="req_validation", validation_id="validation_hook")
    claim = ClaimRecord(request_id="req_validation", claim_text="A supported claim.", claim_id="claim_hook")
    repository = RecordingRepository()

    assert validation_module._add_log(repository, log) is log
    assert validation_module._save_error(repository, error) is error
    assert validation_module._save_validation(repository, validation) is validation
    assert validation_module._save_claim(repository, claim) is claim
    assert repository.logs == [log]
    assert repository.errors == [error]
    assert repository.validations == [validation]
    assert repository.claims == [claim]
    with pytest.raises(RuntimeError, match="add_log failed"):
        validation_module._add_log(FailingRepository(), log)
    with pytest.raises(RuntimeError, match="save_error failed"):
        validation_module._save_error(FailingRepository(), error)
    with pytest.raises(RuntimeError, match="save_validation_record failed"):
        validation_module._save_validation(FailingRepository(), validation)
    with pytest.raises(RuntimeError, match="save_claim_record failed"):
        validation_module._save_claim(FailingRepository(), claim)


def test_planned_query_requires_repository_add_log_for_runtime_planning_logs() -> None:
    with pytest.raises(AttributeError):
        run_planned_query("hello", NoHookRepository())


def test_orchestration_runtime_records_start_and_complete_logs_when_hook_exists() -> None:
    repository = RecordingRepository()
    planned_query = SimpleNamespace(
        logs=(),
        errors=(),
        executed_modes=(RetrievalMode.NO_RETRIEVAL,),
        planning=SimpleNamespace(
            request=SimpleNamespace(request_id="req_runtime"),
            plan=SimpleNamespace(selected_modes=(RetrievalMode.NO_RETRIEVAL,)),
        ),
        validation=None,
        synthesis=SimpleNamespace(answer=SimpleNamespace(answer_id="answer_runtime")),
    )
    adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=lambda _payload: planned_query)

    result = adapter.run_query("hello", repository, correlation_id="corr_runtime")

    assert result.ok is True
    assert [log.details["event_name"] for log in repository.logs] == [
        "orchestration_started",
        "orchestration_completed",
    ]
    assert repository.logs[-1].output_reference == "answer_runtime"
    assert result.logs[0] is repository.logs[0]
    assert result.logs[-1] is repository.logs[-1]


def test_orchestration_runtime_saves_error_when_app_fails_without_fallback() -> None:
    repository = RecordingRepository()

    def failing_app(_payload: dict[str, object]) -> object:
        raise RuntimeError("graph app failed")

    adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=failing_app, allow_local_fallback=False)

    result = adapter.run_query("hello", repository, correlation_id="corr_runtime_fail")

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_message == "graph app failed"
    assert result.error.details == {"runtime_name": "LangGraph", "exception_type": "RuntimeError"}
    assert repository.errors == [result.error]
    assert [log.details["event_name"] for log in repository.logs] == ["orchestration_started"]


def test_orchestration_runtime_missing_hooks_are_noop_on_unavailable_path() -> None:
    adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=None, allow_local_fallback=False)

    result = adapter.run_query("hello", NoHookRepository(), correlation_id="corr_runtime_unavailable")

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_message == "langgraph app is unavailable"
    assert [log.details["event_name"] for log in result.logs] == ["orchestration_started"]
