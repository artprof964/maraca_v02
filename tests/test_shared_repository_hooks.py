import pytest

from shared.repository_hooks import add_repository_log, call_repository_hook, save_repository_error


class RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def save_record(self, *args: object, **kwargs: object) -> str:
        self.calls.append(("save_record", args, kwargs))
        return "saved"

    def add_log(self, log: object) -> str:
        self.calls.append(("add_log", (log,), {}))
        return "stored log"

    def save_error(self, error: object) -> str:
        self.calls.append(("save_error", (error,), {}))
        return "stored error"


class FailingRepository:
    def save_record(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("write failed")


def test_call_repository_hook_noops_when_repository_is_absent() -> None:
    record = object()

    assert call_repository_hook(None, "save_record", record, default=record) is record


def test_call_repository_hook_noops_when_method_is_missing() -> None:
    record = object()

    assert call_repository_hook(object(), "save_record", record, default=record) is record


def test_call_repository_hook_preserves_strict_missing_method_behavior() -> None:
    with pytest.raises(AttributeError):
        call_repository_hook(object(), "save_record", required=True)


def test_call_repository_hook_invokes_existing_method_with_args_and_kwargs() -> None:
    repository = RecordingRepository()

    result = call_repository_hook(repository, "save_record", "record", mode="append")

    assert result == "saved"
    assert repository.calls == [("save_record", ("record",), {"mode": "append"})]


def test_call_repository_hook_propagates_existing_hook_failures() -> None:
    with pytest.raises(RuntimeError, match="write failed"):
        call_repository_hook(FailingRepository(), "save_record", "record")


def test_add_repository_log_returns_original_log() -> None:
    repository = RecordingRepository()
    log = object()

    assert add_repository_log(repository, log) is log
    assert repository.calls == [("add_log", (log,), {})]


def test_save_repository_error_returns_original_error() -> None:
    repository = RecordingRepository()
    error = object()

    assert save_repository_error(repository, error) is error
    assert repository.calls == [("save_error", (error,), {})]


def test_log_and_error_wrappers_noop_for_missing_optional_hooks() -> None:
    log = object()
    error = object()

    assert add_repository_log(object(), log) is log
    assert save_repository_error(object(), error) is error
