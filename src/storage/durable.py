"""Dependency-free JSON/JSONL persistence for the storage baseline."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import fields
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar, get_args, get_origin, get_type_hints

from ingestion import RawArtifact
from shared.contracts import ErrorEnvelope, LogEvent, _serialize_contract
from shared.records import (
    ChunkRecord,
    DocumentRecord,
    EntityRecord,
    IngestionJob,
    RelationRecord,
    SourceRecord,
)

from . import InMemoryStorageRepository
from .adapters import (
    BackendAdapterConfig,
    BackendCapability,
    BackendHealthCheck,
    BackendOperationResult,
    BackendStatus,
    BackendType,
)

T = TypeVar("T")

SNAPSHOT_VERSION = 1
_DURABLE_FILENAMES = (
    "raw_artifacts.json",
    "sources.json",
    "documents.json",
    "chunks.json",
    "entities.json",
    "relations.json",
    "ingestion_jobs.json",
    "logs.jsonl",
    "errors.jsonl",
)


class DurableStorageError(RuntimeError):
    """Raised when durable storage cannot read or write its local files."""


class DurableStorageRepository(InMemoryStorageRepository):
    """In-memory repository with conservative local JSON/JSONL persistence.

    Record dictionaries are stored as JSON snapshots. Logs and errors are
    append-only JSONL streams so telemetry history is not compacted by snapshot
    rewrites.
    """

    def __init__(self, base_path: str | Path, *, load_existing: bool = True) -> None:
        super().__init__()
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.recovery_warnings: list[str] = []
        if load_existing:
            self.load()

    def load(self) -> None:
        """Load persisted records, skipping malformed rows with warnings."""

        self.raw_artifacts.update(
            _load_snapshot(
                self.base_path / "raw_artifacts.json",
                RawArtifact,
                "raw_artifact_id",
                self.recovery_warnings,
                _raw_artifact_from_dict,
            )
        )
        self.sources.update(
            _load_snapshot(
                self.base_path / "sources.json",
                SourceRecord,
                "source_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(SourceRecord, data),
            )
        )
        self.documents.update(
            _load_snapshot(
                self.base_path / "documents.json",
                DocumentRecord,
                "document_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(DocumentRecord, data),
            )
        )
        self.chunks.update(
            _load_snapshot(
                self.base_path / "chunks.json",
                ChunkRecord,
                "chunk_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(ChunkRecord, data),
            )
        )
        self.entities.update(
            _load_snapshot(
                self.base_path / "entities.json",
                EntityRecord,
                "entity_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(EntityRecord, data),
            )
        )
        self.relations.update(
            _load_snapshot(
                self.base_path / "relations.json",
                RelationRecord,
                "relation_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(RelationRecord, data),
            )
        )
        self.ingestion_jobs.update(
            _load_snapshot(
                self.base_path / "ingestion_jobs.json",
                IngestionJob,
                "ingestion_job_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(IngestionJob, data),
            )
        )
        self.logs.update(
            _load_jsonl(
                self.base_path / "logs.jsonl",
                LogEvent,
                "log_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(LogEvent, data),
            )
        )
        self.errors.update(
            _load_jsonl(
                self.base_path / "errors.jsonl",
                ErrorEnvelope,
                "error_id",
                self.recovery_warnings,
                lambda data: _dataclass_from_dict(ErrorEnvelope, data),
            )
        )
        self._rebuild_indexes()

    def save_raw_artifact(self, raw_artifact: RawArtifact) -> RawArtifact:
        saved = super().save_raw_artifact(raw_artifact)
        self._write_snapshot("raw_artifacts.json", self.raw_artifacts.values(), _raw_artifact_to_dict)
        return saved

    def save_source(self, source: SourceRecord) -> SourceRecord:
        saved = super().save_source(source)
        self._write_snapshot("sources.json", self.sources.values(), lambda record: record.to_dict())
        return saved

    def save_document(self, document: DocumentRecord) -> DocumentRecord:
        saved = super().save_document(document)
        self._write_snapshot("documents.json", self.documents.values(), lambda record: record.to_dict())
        return saved

    def save_chunk(self, chunk: ChunkRecord) -> ChunkRecord:
        saved = super().save_chunk(chunk)
        self._write_snapshot("chunks.json", self.chunks.values(), lambda record: record.to_dict())
        return saved

    def save_entity(self, entity: EntityRecord) -> EntityRecord:
        saved = super().save_entity(entity)
        self._write_snapshot("entities.json", self.entities.values(), lambda record: record.to_dict())
        return saved

    def save_relation(self, relation: RelationRecord) -> RelationRecord:
        saved = super().save_relation(relation)
        self._write_snapshot("relations.json", self.relations.values(), lambda record: record.to_dict())
        return saved

    def save_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        saved = super().save_ingestion_job(job)
        self._write_snapshot("ingestion_jobs.json", self.ingestion_jobs.values(), lambda record: record.to_dict())
        return saved

    def add_log(self, log: LogEvent) -> LogEvent:
        saved = super().add_log(log)
        _append_jsonl(self.base_path / "logs.jsonl", saved.to_dict())
        return saved

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        saved = super().save_error(error)
        _append_jsonl(self.base_path / "errors.jsonl", saved.to_dict())
        return saved

    def _write_snapshot(
        self,
        filename: str,
        records: Iterable[T],
        serializer: Callable[[T], dict[str, Any]],
    ) -> None:
        path = self.base_path / filename
        payload = {
            "version": SNAPSHOT_VERSION,
            "records": [serializer(record) for record in records],
        }
        _atomic_write_json(path, payload)

    def _rebuild_indexes(self) -> None:
        self.entity_ids_by_alias.clear()
        self.entity_ids_by_chunk_id.clear()
        self.chunk_ids_by_entity_id.clear()
        self.relation_ids_by_chunk_id.clear()
        self.relation_ids_by_entity_id.clear()
        entities = tuple(self.entities.values())
        relations = tuple(self.relations.values())
        self.entities.clear()
        self.relations.clear()
        for entity in entities:
            InMemoryStorageRepository.save_entity(self, entity)
        for relation in relations:
            InMemoryStorageRepository.save_relation(self, relation)

    def _snapshot_durable_state(self) -> dict[str, str | None]:
        """Capture local durable files so bundle rollback can restore disk state."""

        state: dict[str, str | None] = {}
        for filename in _DURABLE_FILENAMES:
            path = self.base_path / filename
            state[filename] = path.read_text(encoding="utf-8") if path.exists() else None
        return state

    def _restore_durable_state(self, state: dict[str, str | None]) -> None:
        """Restore local durable files after a failed multi-record commit."""

        for filename in _DURABLE_FILENAMES:
            path = self.base_path / filename
            content = state.get(filename)
            if content is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


class LocalDurableStorageBackendAdapter:
    """Executable local durable adapter used as the first backend runtime."""

    def __init__(
        self,
        base_path: str | Path,
        *,
        adapter_name: str = "local_durable_storage",
        backend_type: BackendType = BackendType.METADATA,
        priority: int = 5,
        load_existing: bool = True,
    ) -> None:
        self.base_path = Path(base_path)
        self.config = BackendAdapterConfig(
            adapter_name=adapter_name,
            backend_type=backend_type,
            capabilities=(
                BackendCapability.READ,
                BackendCapability.WRITE,
                BackendCapability.TRANSACTIONAL_WRITE,
                BackendCapability.SNAPSHOT,
                BackendCapability.APPEND_ONLY,
                BackendCapability.HEALTH_CHECK,
            ),
            priority=priority,
            endpoint_reference=f"file://{self.base_path}",
            connection_settings={"base_path": str(self.base_path)},
        )
        self.repository = DurableStorageRepository(self.base_path, load_existing=load_existing)

    def to_config(self) -> BackendAdapterConfig:
        return self.config

    def health_check(
        self,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_backend_health",
    ) -> BackendHealthCheck:
        started = time.perf_counter()
        required = tuple(dict.fromkeys(required_capabilities))
        missing = tuple(capability for capability in required if capability not in self.config.capabilities)
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            probe = self.base_path / ".adapter_healthcheck"
            probe.write_text(correlation_id, encoding="utf-8")
            probe.unlink(missing_ok=True)
            status = BackendStatus.DEGRADED if missing else BackendStatus.READY
            message = "missing required capabilities" if missing else "local durable storage is writable"
            error = None
        except OSError as exc:
            status = BackendStatus.UNAVAILABLE
            message = str(exc)
            error = _durable_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=True,
                details={"base_path": str(self.base_path)},
            )
        latency_ms = (time.perf_counter() - started) * 1000
        return BackendHealthCheck(
            adapter_name=self.config.adapter_name,
            backend_type=self.config.backend_type,
            status=status,
            latency_ms=latency_ms,
            message=message,
            checked_capabilities=required or self.config.capabilities,
            error=error,
            details={
                "base_path": str(self.base_path),
                "missing_capabilities": tuple(capability.value for capability in missing),
            },
        )

    def commit_storage_bundle(
        self,
        *,
        raw_artifact: RawArtifact | None = None,
        source: SourceRecord | None = None,
        document: DocumentRecord | None = None,
        chunks: Iterable[ChunkRecord] = (),
        job: IngestionJob | None = None,
        logs: Iterable[LogEvent] = (),
        errors: Iterable[ErrorEnvelope] = (),
        enrich_graph: bool = False,
        max_retries: int = 1,
        correlation_id: str = "corr_backend_commit",
    ) -> BackendOperationResult:
        from . import commit_storage_bundle_with_recovery

        health = self.health_check(
            required_capabilities=(BackendCapability.WRITE, BackendCapability.TRANSACTIONAL_WRITE),
            correlation_id=correlation_id,
        )
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _durable_backend_error(
                correlation_id=correlation_id,
                operation_name="commit_storage_bundle",
                message="local durable storage is unavailable",
                retryable=True,
                details={"base_path": str(self.base_path)},
            )
            return BackendOperationResult(
                adapter_name=self.config.adapter_name,
                backend_type=self.config.backend_type,
                operation_name="commit_storage_bundle",
                ok=False,
                correlation_id=correlation_id,
                health=health,
                error=error,
            )

        chunk_tuple = tuple(chunks)
        result = commit_storage_bundle_with_recovery(
            self.repository,
            raw_artifact=raw_artifact,
            source=source,
            document=document,
            chunks=chunk_tuple,
            job=job,
            logs=logs,
            errors=errors,
            enrich_graph=enrich_graph,
            max_retries=max_retries,
            correlation_id=correlation_id,
        )
        return BackendOperationResult(
            adapter_name=self.config.adapter_name,
            backend_type=self.config.backend_type,
            operation_name="commit_storage_bundle",
            ok=result.committed,
            correlation_id=correlation_id,
            output_reference=_bundle_output_reference(raw_artifact, document, chunk_tuple),
            health=health,
            error=result.errors[-1] if result.errors and not result.committed else None,
            details={
                "attempts": result.attempts,
                "partial_commit_rolled_back": result.partial_commit_rolled_back,
                "error_count": len(result.errors),
                "log_count": len(result.logs),
            },
        )


def _raw_artifact_to_dict(raw_artifact: RawArtifact) -> dict[str, Any]:
    return _serialize_contract(
        {
            "source_id": raw_artifact.source_id,
            "content_base64": base64.b64encode(raw_artifact.content_bytes).decode("ascii"),
            "location": raw_artifact.location,
            "external_link": raw_artifact.external_link,
            "content_type": raw_artifact.content_type,
            "metadata": raw_artifact.metadata,
            "raw_artifact_id": raw_artifact.raw_artifact_id,
        }
    )


def _raw_artifact_from_dict(data: dict[str, Any]) -> RawArtifact:
    if "content_base64" in data:
        content_bytes = base64.b64decode(str(data["content_base64"]).encode("ascii"), validate=True)
    else:
        content_bytes = str(data.get("text", "")).encode("utf-8")
    return RawArtifact(
        source_id=str(data["source_id"]),
        content_bytes=content_bytes,
        location=str(data["location"]),
        external_link=data.get("external_link"),
        content_type=str(data.get("content_type", "application/octet-stream")),
        metadata=dict(data.get("metadata", {})),
        raw_artifact_id=str(data["raw_artifact_id"]),
    )


def _durable_backend_error(
    *,
    correlation_id: str,
    operation_name: str,
    message: str,
    retryable: bool,
    details: dict[str, object],
) -> ErrorEnvelope:
    from shared.contracts import ErrorSeverity, ErrorType, FallbackAction, Partition
    from shared.policies import create_error_envelope

    return create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.STORAGE,
        operation_name=operation_name,
        error_type=ErrorType.STORAGE,
        error_message=message,
        severity=ErrorSeverity.RECOVERABLE if retryable else ErrorSeverity.CRITICAL,
        retryable=retryable,
        fallback_action=FallbackAction.RETRY if retryable else FallbackAction.STOP,
        details=details,
    )


def _bundle_output_reference(
    raw_artifact: RawArtifact | None,
    document: DocumentRecord | None,
    chunks: tuple[ChunkRecord, ...],
) -> str | None:
    references = []
    if raw_artifact is not None:
        references.append(raw_artifact.raw_artifact_id)
    if document is not None:
        references.append(document.document_id)
    references.extend(chunk.chunk_id for chunk in chunks)
    return ",".join(references) or None


def _load_snapshot(
    path: Path,
    record_type: type[T],
    id_field: str,
    warnings: list[str],
    factory: Callable[[dict[str, Any]], T],
) -> dict[str, T]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("records", [])
        if not isinstance(rows, list):
            raise ValueError("snapshot records must be a list")
    except Exception as exc:
        warnings.append(f"{path.name}: skipped unreadable snapshot: {exc}")
        return {}
    records: dict[str, T] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            warnings.append(f"{path.name}:{index}: skipped non-object {record_type.__name__}")
            continue
        try:
            record = factory(row)
            records[str(getattr(record, id_field))] = record
        except Exception as exc:
            warnings.append(f"{path.name}:{index}: skipped malformed {record_type.__name__}: {exc}")
    return records


def _load_jsonl(
    path: Path,
    record_type: type[T],
    id_field: str,
    warnings: list[str],
    factory: Callable[[dict[str, Any]], T],
) -> dict[str, T]:
    if not path.exists():
        return {}
    records: dict[str, T] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("row must be a JSON object")
            record = factory(row)
            records[str(getattr(record, id_field))] = record
        except Exception as exc:
            warnings.append(f"{path.name}:{line_number}: skipped malformed {record_type.__name__}: {exc}")
    return records


def _dataclass_from_dict(record_type: type[T], data: dict[str, Any]) -> T:
    values = {}
    type_hints = get_type_hints(record_type)
    for field in fields(record_type):
        if field.name not in data:
            continue
        values[field.name] = _coerce_value(data[field.name], type_hints.get(field.name, field.type))
    return record_type(**values)


def _coerce_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list:
        item_type = args[0] if args else Any
        return [_coerce_value(item, item_type) for item in value]
    if origin is dict:
        return dict(value)
    if origin in (tuple,):
        item_type = args[0] if args else Any
        return tuple(_coerce_value(item, item_type) for item in value)
    if origin is not None and type(None) in args:
        non_none = next((arg for arg in args if arg is not type(None)), Any)
        return _coerce_value(value, non_none)
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    if annotation is datetime:
        return datetime.fromisoformat(str(value))
    if annotation is date:
        return date.fromisoformat(str(value))
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise DurableStorageError(f"failed to write {path}") from exc


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True))
            stream.write("\n")
    except OSError as exc:
        raise DurableStorageError(f"failed to append {path}") from exc


__all__ = [
    "DurableStorageError",
    "DurableStorageRepository",
    "LocalDurableStorageBackendAdapter",
    "SNAPSHOT_VERSION",
]
