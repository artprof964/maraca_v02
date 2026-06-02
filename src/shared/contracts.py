"""Lightweight shared contracts used across retrieval-center partitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .serialization import (
    serialize_dataclass,
    serialize_mapping,
    serialize_value,
)


def new_correlation_id(prefix: str = "corr") -> str:
    """Create a stable trace identifier for a request, job, or workflow."""
    return f"{prefix}_{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


_serialize_value = serialize_value
_serialize_contract = serialize_mapping


class Partition(StrEnum):
    SOURCE_REGISTRY = "source_registry"
    INGESTION = "ingestion"
    ENRICHMENT = "enrichment"
    STORAGE = "storage"
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    RANKING = "ranking"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    FEEDBACK = "feedback"
    EVALUATION = "evaluation"


class ErrorSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    RECOVERABLE = "recoverable"
    CRITICAL = "critical"


class ErrorType(StrEnum):
    ACCESS = "access"
    TIMEOUT = "timeout"
    PARSING = "parsing"
    EXTRACTION = "extraction"
    MODEL = "model"
    STORAGE = "storage"
    VALIDATION = "validation"
    POLICY = "policy"
    NETWORK = "network"
    UNKNOWN = "unknown"


class FallbackAction(StrEnum):
    SKIP = "skip"
    RETRY = "retry"
    PARTIAL_COMMIT = "partial_commit"
    REPAIR = "repair"
    CLARIFY = "clarify"
    STOP = "stop"
    ESCALATE = "escalate"


class LogEventType(StrEnum):
    START = "start"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    RETRY = "retry"
    FALLBACK = "fallback"
    DECISION = "decision"
    METRIC = "metric"


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    correlation_id: str
    partition: Partition
    operation_name: str
    severity: ErrorSeverity
    error_type: ErrorType
    error_message: str
    retryable: bool
    fallback_action: FallbackAction
    retry_count: int = 0
    max_retries: int = 0
    error_id: str = field(default_factory=lambda: f"err_{uuid4().hex}")
    created_at: datetime = field(default_factory=_utc_now)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_dataclass(self)


@dataclass(frozen=True, slots=True)
class LogEvent:
    correlation_id: str
    partition: Partition
    event_type: LogEventType
    operation_name: str
    message: str
    input_reference: str | None = None
    output_reference: str | None = None
    duration_ms: float | None = None
    cost_estimate: float | None = None
    model_or_tool: str | None = None
    log_id: str = field(default_factory=lambda: f"log_{uuid4().hex}")
    created_at: datetime = field(default_factory=_utc_now)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_dataclass(self)
