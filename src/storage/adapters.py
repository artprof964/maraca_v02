"""Dependency-free backend adapter contracts for external storage integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Iterable, Protocol

from shared.contracts import ErrorEnvelope, ErrorSeverity, ErrorType, FallbackAction, Partition, _serialize_contract
from shared.policies import create_error_envelope


class BackendType(StrEnum):
    METADATA = "metadata"
    RAW_SOURCE = "raw_source"
    VECTOR = "vector"
    GRAPH = "graph"
    TELEMETRY = "telemetry"


class BackendCapability(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    TRANSACTIONAL_WRITE = "transactional_write"
    APPEND_ONLY = "append_only"
    ACCESS_FILTER = "access_filter"
    HEALTH_CHECK = "health_check"
    SNAPSHOT = "snapshot"
    VECTOR_SEARCH = "vector_search"
    GRAPH_TRAVERSAL = "graph_traversal"


class BackendStatus(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class BackendAdapterConfig:
    """Configuration summary for a future external backend adapter."""

    adapter_name: str
    backend_type: BackendType
    capabilities: tuple[BackendCapability, ...]
    enabled: bool = True
    priority: int = 100
    endpoint_reference: str | None = None
    fallback_adapter: str | None = None
    connection_settings: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["connection_settings"] = _redact_connection_settings(self.connection_settings)
        return _serialize_contract(data)


@dataclass(frozen=True, slots=True)
class BackendHealthCheck:
    """Health result for an adapter without exposing raw credentials."""

    adapter_name: str
    backend_type: BackendType
    status: BackendStatus
    latency_ms: float | None = None
    message: str = ""
    checked_capabilities: tuple[BackendCapability, ...] = ()
    error: ErrorEnvelope | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    def healthy(self) -> bool:
        return self.status is BackendStatus.READY

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class BackendSelection:
    """Selected primary adapter and optional fallback for one backend type."""

    backend_type: BackendType
    primary: BackendAdapterConfig | None
    fallback: BackendAdapterConfig | None = None
    missing_capabilities: tuple[BackendCapability, ...] = ()
    health: BackendHealthCheck | None = None
    error: ErrorEnvelope | None = None

    @property
    def ok(self) -> bool:
        return self.primary is not None and not self.missing_capabilities and self.error is None

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class BackendOperationResult:
    """Outcome of an executable backend adapter operation."""

    adapter_name: str
    backend_type: BackendType
    operation_name: str
    ok: bool
    correlation_id: str
    output_reference: str | None = None
    health: BackendHealthCheck | None = None
    error: ErrorEnvelope | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return _serialize_contract(asdict(self))


class BackendRuntimeAdapter(Protocol):
    """Executable adapter boundary used before service-specific clients exist."""

    config: BackendAdapterConfig

    def health_check(
        self,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_backend_health",
    ) -> BackendHealthCheck:
        """Return current adapter health without exposing credentials."""

    def to_config(self) -> BackendAdapterConfig:
        """Return the manifest used by selection and plan validation."""


class BackendAdapterRegistry:
    """Small registry for adapter manifests and deterministic selection."""

    def __init__(self, adapters: Iterable[BackendAdapterConfig] = ()) -> None:
        self._adapters: dict[str, BackendAdapterConfig] = {}
        self._health: dict[str, BackendHealthCheck] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: BackendAdapterConfig) -> BackendAdapterConfig:
        if not adapter.adapter_name.strip():
            raise ValueError("adapter_name is required")
        self._adapters[adapter.adapter_name] = adapter
        return adapter

    def record_health(self, health: BackendHealthCheck) -> BackendHealthCheck:
        if health.adapter_name not in self._adapters:
            raise ValueError(f"unknown adapter: {health.adapter_name}")
        self._health[health.adapter_name] = health
        return health

    def adapters_for(self, backend_type: BackendType) -> tuple[BackendAdapterConfig, ...]:
        return tuple(
            sorted(
                (
                    adapter
                    for adapter in self._adapters.values()
                    if adapter.backend_type is backend_type and adapter.enabled
                ),
                key=lambda adapter: (adapter.priority, adapter.adapter_name),
            )
        )

    def select(
        self,
        backend_type: BackendType,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_backend_selection",
    ) -> BackendSelection:
        required = tuple(dict.fromkeys(required_capabilities))
        for adapter in self.adapters_for(backend_type):
            missing = _missing_capabilities(adapter, required)
            health = self._health.get(adapter.adapter_name)
            if missing or _unhealthy(health):
                continue
            return BackendSelection(
                backend_type=backend_type,
                primary=adapter,
                fallback=self._fallback_for(adapter),
                health=health,
            )
        best_candidate = next(iter(self.adapters_for(backend_type)), None)
        missing = _missing_capabilities(best_candidate, required) if best_candidate is not None else required
        return BackendSelection(
            backend_type=backend_type,
            primary=None,
            fallback=self._fallback_for(best_candidate) if best_candidate is not None else None,
            missing_capabilities=missing,
            health=self._health.get(best_candidate.adapter_name) if best_candidate is not None else None,
            error=create_error_envelope(
                correlation_id=correlation_id,
                partition=Partition.STORAGE,
                operation_name="select_backend_adapter",
                error_type=ErrorType.STORAGE,
                error_message=f"no usable {backend_type.value} backend adapter is available",
                severity=ErrorSeverity.RECOVERABLE,
                retryable=False,
                fallback_action=FallbackAction.PARTIAL_COMMIT,
                details={
                    "backend_type": backend_type.value,
                    "required_capabilities": tuple(capability.value for capability in required),
                    "missing_capabilities": tuple(capability.value for capability in missing),
                },
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "adapters": [adapter.to_dict() for adapter in self._adapters.values()],
            "health": [health.to_dict() for health in self._health.values()],
        }

    def _fallback_for(self, adapter: BackendAdapterConfig | None) -> BackendAdapterConfig | None:
        if adapter is None or adapter.fallback_adapter is None:
            return None
        fallback = self._adapters.get(adapter.fallback_adapter)
        if fallback is None or not fallback.enabled:
            return None
        return fallback


def create_local_backend_registry() -> BackendAdapterRegistry:
    """Return the dependency-free local baseline adapters used before external services."""

    registry = BackendAdapterRegistry(
        [
            BackendAdapterConfig(
                adapter_name="local_json_metadata",
                backend_type=BackendType.METADATA,
                capabilities=(
                    BackendCapability.READ,
                    BackendCapability.WRITE,
                    BackendCapability.SNAPSHOT,
                    BackendCapability.HEALTH_CHECK,
                ),
                priority=10,
                endpoint_reference="file://storage/*.json",
            ),
            BackendAdapterConfig(
                adapter_name="local_raw_snapshot",
                backend_type=BackendType.RAW_SOURCE,
                capabilities=(
                    BackendCapability.READ,
                    BackendCapability.WRITE,
                    BackendCapability.SNAPSHOT,
                    BackendCapability.HEALTH_CHECK,
                ),
                priority=10,
                endpoint_reference="file://storage/raw_artifacts.json",
            ),
            BackendAdapterConfig(
                adapter_name="local_jsonl_telemetry",
                backend_type=BackendType.TELEMETRY,
                capabilities=(
                    BackendCapability.READ,
                    BackendCapability.WRITE,
                    BackendCapability.APPEND_ONLY,
                    BackendCapability.HEALTH_CHECK,
                ),
                priority=10,
                endpoint_reference="file://storage/*.jsonl",
            ),
            BackendAdapterConfig(
                adapter_name="in_memory_vector_index",
                backend_type=BackendType.VECTOR,
                capabilities=(
                    BackendCapability.READ,
                    BackendCapability.WRITE,
                    BackendCapability.VECTOR_SEARCH,
                    BackendCapability.ACCESS_FILTER,
                    BackendCapability.HEALTH_CHECK,
                ),
                priority=20,
                endpoint_reference="memory://vector_index",
            ),
            BackendAdapterConfig(
                adapter_name="in_memory_graph_index",
                backend_type=BackendType.GRAPH,
                capabilities=(
                    BackendCapability.READ,
                    BackendCapability.WRITE,
                    BackendCapability.GRAPH_TRAVERSAL,
                    BackendCapability.ACCESS_FILTER,
                    BackendCapability.HEALTH_CHECK,
                ),
                priority=20,
                endpoint_reference="memory://graph_index",
            ),
        ]
    )
    for adapter in registry.adapters_for(BackendType.METADATA):
        registry.record_health(_ready(adapter))
    for backend_type in (BackendType.RAW_SOURCE, BackendType.TELEMETRY, BackendType.VECTOR, BackendType.GRAPH):
        for adapter in registry.adapters_for(backend_type):
            registry.record_health(_ready(adapter))
    return registry


def validate_backend_plan(
    registry: BackendAdapterRegistry,
    requirements: dict[BackendType, tuple[BackendCapability, ...]],
    *,
    correlation_id: str = "corr_backend_plan",
) -> tuple[BackendSelection, ...]:
    """Select adapters for a backend plan and surface governed failures."""

    return tuple(
        registry.select(
            backend_type,
            required_capabilities=required_capabilities,
            correlation_id=correlation_id,
        )
        for backend_type, required_capabilities in requirements.items()
    )


def _ready(adapter: BackendAdapterConfig) -> BackendHealthCheck:
    return BackendHealthCheck(
        adapter_name=adapter.adapter_name,
        backend_type=adapter.backend_type,
        status=BackendStatus.READY,
        checked_capabilities=adapter.capabilities,
    )


def _missing_capabilities(
    adapter: BackendAdapterConfig | None,
    required_capabilities: tuple[BackendCapability, ...],
) -> tuple[BackendCapability, ...]:
    if adapter is None:
        return required_capabilities
    available = set(adapter.capabilities)
    return tuple(capability for capability in required_capabilities if capability not in available)


def _unhealthy(health: BackendHealthCheck | None) -> bool:
    return health is not None and health.status not in (BackendStatus.READY, BackendStatus.DEGRADED)


def _redact_connection_settings(settings: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in settings.items():
        normalized = key.lower()
        if normalized.endswith("_env"):
            redacted[key] = value
            continue
        if any(marker in normalized for marker in ("secret", "password", "token", "api_key")):
            redacted[key] = "<redacted>"
            continue
        redacted[key] = value
    return redacted


__all__ = [
    "BackendAdapterConfig",
    "BackendAdapterRegistry",
    "BackendCapability",
    "BackendHealthCheck",
    "BackendOperationResult",
    "BackendRuntimeAdapter",
    "BackendSelection",
    "BackendStatus",
    "BackendType",
    "create_local_backend_registry",
    "validate_backend_plan",
]
