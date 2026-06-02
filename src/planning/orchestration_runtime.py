"""Dependency-optional orchestration runtime boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Protocol

from shared.contracts import ErrorEnvelope, ErrorSeverity, ErrorType, FallbackAction, LogEvent, Partition
from shared.policies import create_error_envelope, create_success_log_event
from shared.records import RetrievalRequest
from shared.repository_hooks import add_repository_log, save_repository_error
from shared.serialization import serialize_mapping


class OrchestrationCapability(StrEnum):
    PLAN = "plan"
    RETRIEVE = "retrieve"
    RANK = "rank"
    VALIDATE = "validate"
    SYNTHESIZE = "synthesize"
    REPAIR_LOOP = "repair_loop"
    HEALTH_CHECK = "health_check"


class OrchestrationStatus(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class OrchestrationRuntimeConfig:
    adapter_name: str
    runtime_name: str
    capabilities: tuple[OrchestrationCapability, ...]
    priority: int = 10
    fallback_runtime: str | None = None
    package_names: tuple[str, ...] = ()
    connection_settings: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return serialize_mapping(
            {
                "adapter_name": self.adapter_name,
                "runtime_name": self.runtime_name,
                "capabilities": self.capabilities,
                "priority": self.priority,
                "fallback_runtime": self.fallback_runtime,
                "package_names": self.package_names,
                "connection_settings": self.connection_settings,
            }
        )


@dataclass(frozen=True, slots=True)
class OrchestrationHealthCheck:
    adapter_name: str
    runtime_name: str
    status: OrchestrationStatus
    latency_ms: float
    message: str
    checked_capabilities: tuple[OrchestrationCapability, ...]
    error: ErrorEnvelope | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return serialize_mapping(
            {
                "adapter_name": self.adapter_name,
                "runtime_name": self.runtime_name,
                "status": self.status,
                "latency_ms": self.latency_ms,
                "message": self.message,
                "checked_capabilities": self.checked_capabilities,
                "error": self.error.to_dict() if self.error else None,
                "details": self.details,
            }
        )


@dataclass(frozen=True, slots=True)
class OrchestrationRunResult:
    adapter_name: str
    runtime_name: str
    operation_name: str
    ok: bool
    correlation_id: str
    request_id: str | None = None
    planned_query: object | None = None
    output_reference: str | None = None
    health: OrchestrationHealthCheck | None = None
    error: ErrorEnvelope | None = None
    logs: tuple[LogEvent, ...] = ()
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return serialize_mapping(
            {
                "adapter_name": self.adapter_name,
                "runtime_name": self.runtime_name,
                "operation_name": self.operation_name,
                "ok": self.ok,
                "correlation_id": self.correlation_id,
                "request_id": self.request_id,
                "output_reference": self.output_reference,
                "health": self.health.to_dict() if self.health else None,
                "error": self.error.to_dict() if self.error else None,
                "logs": tuple(log.to_dict() for log in self.logs),
                "details": self.details,
            }
        )


class OrchestrationRuntimeAdapter(Protocol):
    config: OrchestrationRuntimeConfig

    def health_check(
        self,
        *,
        required_capabilities: Iterable[OrchestrationCapability] = (),
        correlation_id: str = "corr_orchestration_health",
    ) -> OrchestrationHealthCheck:
        """Return runtime health without requiring the optional runtime package."""

    def to_config(self) -> OrchestrationRuntimeConfig:
        """Return runtime manifest metadata."""


class LocalPlannedQueryGraphApp:
    """LangGraph-compatible local app wrapper for the planned-query runtime."""

    def invoke(self, payload: dict[str, object]) -> object:
        return _run_local_planned_query(
            payload["request"],  # type: ignore[arg-type]
            payload["repository"],
            principal=payload.get("principal"),
            principal_scopes=payload.get("principal_scopes", ()),
            use_case=str(payload.get("use_case", "general")),
            ranking_config=payload.get("ranking_config"),
            current_date=payload.get("current_date"),
            correlation_id=str(payload.get("correlation_id", "corr_orchestration_run")),
        )


class LangGraphCompatibleOrchestrationAdapter:
    """Runtime adapter for LangGraph-style apps with a local fallback path."""

    def __init__(
        self,
        graph_app: object | None = None,
        *,
        adapter_name: str = "langgraph_orchestration_runtime",
        priority: int = 5,
        allow_local_fallback: bool = True,
    ) -> None:
        self.graph_app = graph_app
        self.allow_local_fallback = allow_local_fallback
        self.config = OrchestrationRuntimeConfig(
            adapter_name=adapter_name,
            runtime_name="LangGraph",
            capabilities=(
                OrchestrationCapability.PLAN,
                OrchestrationCapability.RETRIEVE,
                OrchestrationCapability.RANK,
                OrchestrationCapability.VALIDATE,
                OrchestrationCapability.SYNTHESIZE,
                OrchestrationCapability.REPAIR_LOOP,
                OrchestrationCapability.HEALTH_CHECK,
            ),
            priority=priority,
            fallback_runtime="local_planned_query" if allow_local_fallback else None,
            package_names=("langgraph",),
            connection_settings={
                "graph_app_injected": graph_app is not None,
                "allow_local_fallback": allow_local_fallback,
            },
        )

    def to_config(self) -> OrchestrationRuntimeConfig:
        return self.config

    def health_check(
        self,
        *,
        required_capabilities: Iterable[OrchestrationCapability] = (),
        correlation_id: str = "corr_orchestration_health",
    ) -> OrchestrationHealthCheck:
        started = time.perf_counter()
        required = tuple(dict.fromkeys(required_capabilities))
        missing = tuple(capability for capability in required if capability not in self.config.capabilities)
        details: dict[str, object] = {
            "graph_app_injected": self.graph_app is not None,
            "fallback_runtime": self.config.fallback_runtime,
            "missing_capabilities": tuple(capability.value for capability in missing),
        }

        if missing:
            status = OrchestrationStatus.DEGRADED
            message = "missing required orchestration capabilities"
            error = _orchestration_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=False,
                details={"missing_capabilities": tuple(capability.value for capability in missing)},
            )
        elif self.graph_app is not None:
            status = OrchestrationStatus.READY
            message = "langgraph-compatible orchestration app is available"
            error = None
        elif self.allow_local_fallback:
            status = OrchestrationStatus.DEGRADED
            message = "langgraph app is unavailable; local planned-query fallback is available"
            error = None
            details["fallback_active"] = True
        else:
            status = OrchestrationStatus.UNAVAILABLE
            message = "langgraph app is unavailable"
            error = _orchestration_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=True,
                details={"package_name": "langgraph"},
            )

        return OrchestrationHealthCheck(
            adapter_name=self.config.adapter_name,
            runtime_name=self.config.runtime_name,
            status=status,
            latency_ms=(time.perf_counter() - started) * 1000,
            message=message,
            checked_capabilities=required or self.config.capabilities,
            error=error,
            details=details,
        )

    def run_query(
        self,
        request_or_query: RetrievalRequest | str,
        repository: object,
        *,
        principal: str | None = None,
        principal_scopes: Iterable[str] = (),
        use_case: str = "general",
        ranking_config: object | None = None,
        current_date: object | None = None,
        correlation_id: str = "corr_orchestration_run",
    ) -> OrchestrationRunResult:
        health = self.health_check(
            required_capabilities=(
                OrchestrationCapability.PLAN,
                OrchestrationCapability.RETRIEVE,
                OrchestrationCapability.VALIDATE,
                OrchestrationCapability.SYNTHESIZE,
            ),
            correlation_id=correlation_id,
        )
        start_log = _orchestration_log(
            correlation_id,
            "run_query",
            "orchestration_started",
            "Started planned query orchestration.",
            details={"runtime_name": self.config.runtime_name, "fallback_runtime": self.config.fallback_runtime},
        )
        add_repository_log(repository, start_log)

        if health.status is OrchestrationStatus.UNAVAILABLE:
            error = health.error or _orchestration_error(
                correlation_id=correlation_id,
                operation_name="run_query",
                message="orchestration runtime is unavailable",
                retryable=True,
                details={},
            )
            return _run_result(
                self.config,
                False,
                correlation_id,
                health,
                error=error,
                logs=(start_log,),
                details={"fallback_used": False},
            )

        fallback_used = self.graph_app is None
        try:
            planned_query = (
                _run_local_planned_query(
                    request_or_query,
                    repository,
                    principal=principal,
                    principal_scopes=principal_scopes,
                    use_case=use_case,
                    ranking_config=ranking_config,
                    current_date=current_date,
                    correlation_id=correlation_id,
                )
                if fallback_used
                else _invoke_graph_app(
                    self.graph_app,
                    request_or_query,
                    repository,
                    principal=principal,
                    principal_scopes=principal_scopes,
                    use_case=use_case,
                    ranking_config=ranking_config,
                    current_date=current_date,
                    correlation_id=correlation_id,
                )
            )
        except Exception as exc:
            if self.graph_app is not None and self.allow_local_fallback:
                error = _orchestration_error(
                    correlation_id=correlation_id,
                    operation_name="run_query",
                    message=str(exc),
                    retryable=True,
                    details={"runtime_name": self.config.runtime_name, "fallback_runtime": self.config.fallback_runtime},
                )
                planned_query = _run_local_planned_query(
                    request_or_query,
                    repository,
                    principal=principal,
                    principal_scopes=principal_scopes,
                    use_case=use_case,
                    ranking_config=ranking_config,
                    current_date=current_date,
                    correlation_id=correlation_id,
                )
                fallback_used = True
            else:
                error = _orchestration_error(
                    correlation_id=correlation_id,
                    operation_name="run_query",
                    message=str(exc),
                    retryable=True,
                    details={"runtime_name": self.config.runtime_name, "exception_type": type(exc).__name__},
                )
                save_repository_error(repository, error)
                return _run_result(
                    self.config,
                    False,
                    correlation_id,
                    health,
                    error=error,
                    logs=(start_log,),
                    details={"fallback_used": False},
                )
        else:
            error = None

        request_id = getattr(getattr(planned_query, "planning", None), "request", None)
        request_id = getattr(request_id, "request_id", None)
        output_reference = _planned_query_output_reference(planned_query)
        complete_log = _orchestration_log(
            correlation_id,
            "run_query",
            "orchestration_completed",
            "Completed planned query orchestration.",
            output_reference=output_reference,
            details={
                "request_id": request_id,
                "runtime_name": self.config.runtime_name,
                "fallback_used": fallback_used,
                **_planned_query_summary(planned_query),
            },
        )
        add_repository_log(repository, complete_log)

        planned_logs = tuple(getattr(planned_query, "logs", ()))
        return _run_result(
            self.config,
            True,
            correlation_id,
            health,
            request_id=request_id,
            planned_query=planned_query,
            output_reference=output_reference,
            error=error,
            logs=(start_log, *planned_logs, complete_log),
            details={
                "fallback_used": fallback_used,
                **_planned_query_summary(planned_query),
            },
        )


def _run_local_planned_query(
    request_or_query: RetrievalRequest | str,
    repository: object,
    **kwargs: object,
) -> object:
    from . import run_planned_query

    return run_planned_query(request_or_query, repository, **kwargs)


def _invoke_graph_app(
    graph_app: object | None,
    request_or_query: RetrievalRequest | str,
    repository: object,
    **kwargs: object,
) -> object:
    if graph_app is None:
        raise RuntimeError("langgraph app is unavailable")
    payload = {
        "request": request_or_query,
        "repository": repository,
        **kwargs,
    }
    if hasattr(graph_app, "invoke"):
        result = graph_app.invoke(payload)
    elif callable(graph_app):
        result = graph_app(payload)
    else:
        raise RuntimeError("langgraph app does not expose invoke or callable execution")
    if result is None:
        raise RuntimeError("langgraph app returned no planned query result")
    return result


def _run_result(
    config: OrchestrationRuntimeConfig,
    ok: bool,
    correlation_id: str,
    health: OrchestrationHealthCheck,
    *,
    request_id: str | None = None,
    planned_query: object | None = None,
    output_reference: str | None = None,
    error: ErrorEnvelope | None = None,
    logs: tuple[LogEvent, ...] = (),
    details: dict[str, object] | None = None,
) -> OrchestrationRunResult:
    return OrchestrationRunResult(
        adapter_name=config.adapter_name,
        runtime_name=config.runtime_name,
        operation_name="run_query",
        ok=ok,
        correlation_id=correlation_id,
        request_id=request_id,
        planned_query=planned_query,
        output_reference=output_reference,
        health=health,
        error=error,
        logs=logs,
        details=details or {},
    )


def _planned_query_output_reference(planned_query: object) -> str | None:
    synthesis = getattr(planned_query, "synthesis", None)
    answer = getattr(synthesis, "answer", None)
    answer_id = getattr(answer, "answer_id", None)
    if answer_id:
        return answer_id
    retrieval = getattr(planned_query, "retrieval", None)
    candidates = tuple(getattr(retrieval, "candidates", ()) or ())
    return ",".join(candidate.evidence_id for candidate in candidates) or None


def _planned_query_summary(planned_query: object) -> dict[str, object]:
    planning = getattr(planned_query, "planning", None)
    plan = getattr(planning, "plan", None)
    validation = getattr(planned_query, "validation", None)
    validation_record = getattr(validation, "validation", None)
    return {
        "selected_modes": tuple(mode.value for mode in getattr(plan, "selected_modes", ()) or ()),
        "executed_modes": tuple(mode.value for mode in getattr(planned_query, "executed_modes", ()) or ()),
        "validation_status": getattr(getattr(validation_record, "validation_status", None), "value", None),
        "log_count": len(tuple(getattr(planned_query, "logs", ()) or ())),
        "error_count": len(tuple(getattr(planned_query, "errors", ()) or ())),
    }


def _orchestration_log(
    correlation_id: str,
    operation_name: str,
    event_name: str,
    message: str,
    *,
    output_reference: str | None = None,
    details: dict[str, object] | None = None,
) -> LogEvent:
    payload = dict(details or {})
    payload.setdefault("event_name", event_name)
    return create_success_log_event(
        correlation_id=correlation_id,
        partition=Partition.PLANNING,
        operation_name=operation_name,
        event_name=event_name,
        message=message,
        output_reference=output_reference,
        details=payload,
    )


def _orchestration_error(
    *,
    correlation_id: str,
    operation_name: str,
    message: str,
    retryable: bool,
    details: dict[str, object],
) -> ErrorEnvelope:
    return create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.PLANNING,
        operation_name=operation_name,
        error_type=ErrorType.POLICY,
        error_message=message,
        severity=ErrorSeverity.RECOVERABLE if retryable else ErrorSeverity.CRITICAL,
        retryable=retryable,
        fallback_action=FallbackAction.RETRY if retryable else FallbackAction.STOP,
        details=details,
    )


__all__ = [
    "LangGraphCompatibleOrchestrationAdapter",
    "LocalPlannedQueryGraphApp",
    "OrchestrationCapability",
    "OrchestrationHealthCheck",
    "OrchestrationRunResult",
    "OrchestrationRuntimeAdapter",
    "OrchestrationRuntimeConfig",
    "OrchestrationStatus",
]
