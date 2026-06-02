"""Duck-typed repository hook helpers shared by optional persistence paths."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def call_repository_hook(
    repository: object | None,
    method_name: str,
    *args: object,
    required: bool = False,
    default: T | None = None,
    **kwargs: object,
) -> object | T | None:
    """Call an optional repository hook and return ``default`` when absent.

    Missing repositories and missing methods are no-ops. Existing methods are
    invoked directly so write failures keep the caller's current error path.
    """

    if repository is None:
        return default
    if required:
        method = getattr(repository, method_name)
    else:
        method = getattr(repository, method_name, None)
    if method is None:
        return default
    return method(*args, **kwargs)


def add_repository_log(repository: object | None, log: T, *, required: bool = False) -> T:
    """Persist a log event when the repository exposes ``add_log``."""

    call_repository_hook(repository, "add_log", log, required=required)
    return log


def save_repository_error(repository: object | None, error: T, *, required: bool = False) -> T:
    """Persist an error envelope when the repository exposes ``save_error``."""

    call_repository_hook(repository, "save_error", error, required=required)
    return error


__all__ = [
    "add_repository_log",
    "call_repository_hook",
    "save_repository_error",
]
