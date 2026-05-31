"""Dependency-free in-memory storage behavior for early Milestone 1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Iterable

from ingestion import RawArtifact
from shared.contracts import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    new_correlation_id,
)
from shared.policies import create_error_envelope, create_success_log_event
from shared.records import ChunkRecord, DocumentRecord, EntityRecord, IngestionJob, RelationRecord, SourceRecord

PARTITION = "storage"


class StorageOperationError(RuntimeError):
    """Raised by storage adapters when a write cannot be completed."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class StorageCommitResult:
    """Records persisted by a storage commit step plus the generated log."""

    raw_artifact_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    ingestion_job_ids: tuple[str, ...] = ()
    log: LogEvent | None = None


@dataclass(frozen=True, slots=True)
class StorageVerificationResult:
    """Deterministic eligibility summary for an in-memory storage snapshot."""

    ok: bool
    missing_raw_artifacts: tuple[str, ...] = ()
    missing_documents: tuple[str, ...] = ()
    missing_chunks: tuple[str, ...] = ()
    missing_entities: tuple[str, ...] = ()
    missing_relations: tuple[str, ...] = ()
    missing_access_metadata: tuple[str, ...] = ()
    log: LogEvent | None = None


@dataclass(frozen=True, slots=True)
class StorageRecoveryResult:
    """Outcome of a retryable bundle commit with rollback-on-failure handling."""

    committed: bool
    attempts: int
    partial_commit_rolled_back: bool = False
    results: tuple[StorageCommitResult, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()
    logs: tuple[LogEvent, ...] = ()


@dataclass(slots=True)
class InMemoryStorageRepository:
    """Small metadata/raw store used before durable storage exists."""

    raw_artifacts: dict[str, RawArtifact] = field(default_factory=dict)
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    documents: dict[str, DocumentRecord] = field(default_factory=dict)
    chunks: dict[str, ChunkRecord] = field(default_factory=dict)
    vector_embeddings: dict[str, object] = field(default_factory=dict)
    sparse_terms: dict[str, object] = field(default_factory=dict)
    entities: dict[str, EntityRecord] = field(default_factory=dict)
    relations: dict[str, RelationRecord] = field(default_factory=dict)
    entity_ids_by_alias: dict[str, set[str]] = field(default_factory=dict)
    entity_ids_by_chunk_id: dict[str, set[str]] = field(default_factory=dict)
    chunk_ids_by_entity_id: dict[str, set[str]] = field(default_factory=dict)
    relation_ids_by_chunk_id: dict[str, set[str]] = field(default_factory=dict)
    relation_ids_by_entity_id: dict[str, set[str]] = field(default_factory=dict)
    validation_records: dict[str, object] = field(default_factory=dict)
    claim_records: dict[str, object] = field(default_factory=dict)
    feedback: dict[str, object] = field(default_factory=dict)
    feedback_trace_references: dict[str, object] = field(default_factory=dict)
    evaluation_traces: dict[str, object] = field(default_factory=dict)
    evaluation_cases: dict[str, object] = field(default_factory=dict)
    evaluation_reports: dict[str, object] = field(default_factory=dict)
    observability_reports: dict[str, object] = field(default_factory=dict)
    improvement_tasks: dict[str, object] = field(default_factory=dict)
    ingestion_jobs: dict[str, IngestionJob] = field(default_factory=dict)
    logs: dict[str, LogEvent] = field(default_factory=dict)
    errors: dict[str, ErrorEnvelope] = field(default_factory=dict)

    def add_log(self, log: LogEvent) -> LogEvent:
        self.logs[log.log_id] = log
        return log

    def save_raw_artifact(self, raw_artifact: RawArtifact) -> RawArtifact:
        self.raw_artifacts[raw_artifact.raw_artifact_id] = raw_artifact
        return raw_artifact

    def save_source(self, source: SourceRecord) -> SourceRecord:
        self.sources[source.source_id] = source
        return source

    def save_document(self, document: DocumentRecord) -> DocumentRecord:
        self.documents[document.document_id] = document
        return document

    def save_chunk(self, chunk: ChunkRecord) -> ChunkRecord:
        self.chunks[chunk.chunk_id] = chunk
        return chunk

    def save_entity(self, entity: EntityRecord) -> EntityRecord:
        self.entities[entity.entity_id] = entity
        for alias in (entity.entity_name, *entity.aliases):
            self.entity_ids_by_alias.setdefault(_entity_alias_key(alias), set()).add(entity.entity_id)
        return entity

    def save_relation(self, relation: RelationRecord) -> RelationRecord:
        self.relations[relation.relation_id] = relation
        self.relation_ids_by_entity_id.setdefault(relation.subject_entity_id, set()).add(relation.relation_id)
        self.relation_ids_by_entity_id.setdefault(relation.object_entity_id, set()).add(relation.relation_id)
        for chunk_id in relation.evidence_chunk_ids:
            self.relation_ids_by_chunk_id.setdefault(chunk_id, set()).add(relation.relation_id)
        return relation

    def save_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        self.ingestion_jobs[job.ingestion_job_id] = job
        return job

    def save_validation_record(self, validation: object) -> object:
        validation_id = getattr(validation, "validation_id")
        self.validation_records[validation_id] = validation
        return validation

    def save_claim_record(self, claim: object) -> object:
        claim_id = getattr(claim, "claim_id")
        self.claim_records[claim_id] = claim
        return claim

    def save_feedback(self, feedback: object, trace_reference: object) -> object:
        feedback_id = getattr(feedback, "feedback_id")
        self.feedback[feedback_id] = feedback
        self.feedback_trace_references[feedback_id] = trace_reference
        return feedback

    def save_trace(self, trace: object) -> object:
        trace_id = getattr(trace, "trace_id")
        self.evaluation_traces[trace_id] = trace
        return trace

    def save_evaluation_case(self, case: object) -> object:
        case_id = getattr(case, "case_id")
        self.evaluation_cases[case_id] = case
        return case

    def save_evaluation_report(self, report: object) -> object:
        report_id = getattr(report, "report_id")
        self.evaluation_reports[report_id] = report
        return report

    def save_observability_report(self, report: object) -> object:
        report_id = getattr(report, "report_id")
        self.observability_reports[report_id] = report
        return report

    def save_improvement_task(self, task: object) -> object:
        task_id = getattr(task, "task_id")
        self.improvement_tasks[task_id] = task
        return task

    def save_error(self, error: ErrorEnvelope) -> ErrorEnvelope:
        self.errors[error.error_id] = error
        return error

    def chunks_for_document(self, document_id: str) -> tuple[ChunkRecord, ...]:
        return tuple(
            sorted(
                (chunk for chunk in self.chunks.values() if chunk.document_id == document_id),
                key=lambda chunk: chunk.chunk_index,
            )
        )


def commit_raw_artifact(
    repository: InMemoryStorageRepository,
    raw_artifact: RawArtifact,
    *,
    correlation_id: str | None = None,
) -> StorageCommitResult:
    """Persist a raw artifact reference/bytes object in memory and log it."""

    repository.save_raw_artifact(raw_artifact)
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="commit_raw_artifact",
        event_name="raw_artifact_committed",
        output_reference=raw_artifact.raw_artifact_id,
        details=raw_artifact.reference(),
    )
    repository.add_log(log)
    return StorageCommitResult(raw_artifact_ids=(raw_artifact.raw_artifact_id,), log=log)


def commit_document(
    repository: InMemoryStorageRepository,
    document: DocumentRecord,
    *,
    source: SourceRecord | None = None,
    correlation_id: str | None = None,
) -> StorageCommitResult:
    """Persist source/document metadata in memory and log it."""

    if source is not None:
        repository.save_source(source)
    repository.save_document(document)
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="commit_document",
        event_name="document_committed",
        output_reference=document.document_id,
        details={"source_id": document.source_id, "document_id": document.document_id},
    )
    repository.add_log(log)
    return StorageCommitResult(
        source_ids=(source.source_id,) if source else (),
        document_ids=(document.document_id,),
        log=log,
    )


def commit_chunks(
    repository: InMemoryStorageRepository,
    chunks: Iterable[ChunkRecord],
    *,
    correlation_id: str | None = None,
) -> StorageCommitResult:
    """Persist chunk records in memory and emit the baseline chunks_committed log."""

    chunk_ids: list[str] = []
    document_ids: set[str] = set()
    for chunk in chunks:
        repository.save_chunk(chunk)
        chunk_ids.append(chunk.chunk_id)
        document_ids.add(chunk.document_id)
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="commit_chunks",
        event_name="chunks_committed",
        output_reference=",".join(chunk_ids) if chunk_ids else None,
        details={
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
            "document_ids": sorted(document_ids),
        },
    )
    repository.add_log(log)
    return StorageCommitResult(chunk_ids=tuple(chunk_ids), log=log)


def commit_graph_records(
    repository: InMemoryStorageRepository,
    *,
    entities: Iterable[EntityRecord] = (),
    relations: Iterable[RelationRecord] = (),
    chunks: Iterable[ChunkRecord] = (),
    correlation_id: str | None = None,
) -> StorageCommitResult:
    """Persist graph records, graph-linked chunks, and repository indexes."""

    entity_ids: list[str] = []
    relation_ids: list[str] = []
    chunk_ids: list[str] = []
    for entity in entities:
        repository.save_entity(entity)
        entity_ids.append(entity.entity_id)
    for relation in relations:
        repository.save_relation(relation)
        relation_ids.append(relation.relation_id)
    for chunk in chunks:
        linked_entity_ids = _graph_flag_ids(chunk, "graph:entity:")
        linked_relation_ids = _graph_flag_ids(chunk, "graph:relation:")
        quality_flags = list(dict.fromkeys(chunk.quality_flags))
        for relation_id in linked_relation_ids:
            relation = repository.relations.get(relation_id)
            if relation is not None:
                linked_entity_ids.extend([relation.subject_entity_id, relation.object_entity_id])
        for entity_id in sorted(set(linked_entity_ids)):
            repository.entity_ids_by_chunk_id.setdefault(chunk.chunk_id, set()).add(entity_id)
            repository.chunk_ids_by_entity_id.setdefault(entity_id, set()).add(chunk.chunk_id)
            flag = f"graph:entity:{entity_id}"
            if flag not in quality_flags:
                quality_flags.append(flag)
        for relation_id in sorted(set(linked_relation_ids)):
            repository.relation_ids_by_chunk_id.setdefault(chunk.chunk_id, set()).add(relation_id)
            flag = f"graph:relation:{relation_id}"
            if flag not in quality_flags:
                quality_flags.append(flag)
        repository.save_chunk(replace(chunk, quality_flags=quality_flags))
        chunk_ids.append(chunk.chunk_id)
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="commit_graph_records",
        event_name="graph_commit_degraded" if not entity_ids and not relation_ids else "graph_records_committed",
        output_reference=",".join([*entity_ids, *relation_ids]) or None,
        details={
            "entity_count": len(entity_ids),
            "entity_ids": entity_ids,
            "relation_count": len(relation_ids),
            "relation_ids": relation_ids,
            "chunk_ids": chunk_ids,
        },
    )
    repository.add_log(log)
    return StorageCommitResult(
        chunk_ids=tuple(chunk_ids),
        entity_ids=tuple(entity_ids),
        relation_ids=tuple(relation_ids),
        log=log,
    )


def commit_ingestion_records(
    repository: InMemoryStorageRepository,
    *,
    jobs: Iterable[IngestionJob] = (),
    logs: Iterable[LogEvent] = (),
    errors: Iterable[ErrorEnvelope] = (),
) -> StorageCommitResult:
    """Persist ingestion job/log/error metadata produced upstream."""

    job_ids: list[str] = []
    for job in jobs:
        repository.save_ingestion_job(job)
        job_ids.append(job.ingestion_job_id)
    for log in logs:
        repository.add_log(log)
    for error in errors:
        repository.save_error(error)
    return StorageCommitResult(ingestion_job_ids=tuple(job_ids))


def commit_storage_bundle(
    repository: InMemoryStorageRepository,
    *,
    raw_artifact: RawArtifact | None = None,
    source: SourceRecord | None = None,
    document: DocumentRecord | None = None,
    chunks: Iterable[ChunkRecord] = (),
    job: IngestionJob | None = None,
    logs: Iterable[LogEvent] = (),
    errors: Iterable[ErrorEnvelope] = (),
    enrich_graph: bool = False,
    correlation_id: str | None = None,
) -> tuple[StorageCommitResult, ...]:
    """Commit raw/document/chunk records, with optional graph enrichment."""

    results: list[StorageCommitResult] = []
    if raw_artifact is not None:
        results.append(commit_raw_artifact(repository, raw_artifact, correlation_id=correlation_id))
    if document is not None:
        results.append(commit_document(repository, document, source=source, correlation_id=correlation_id))
    chunk_tuple = tuple(chunks)
    if chunk_tuple:
        results.append(commit_chunks(repository, chunk_tuple, correlation_id=correlation_id))
        if enrich_graph:
            from enrichment import extract_graph_records

            extraction = extract_graph_records(chunk_tuple, correlation_id=correlation_id)
            if extraction.log is not None:
                repository.add_log(extraction.log)
            results.append(
                commit_graph_records(
                    repository,
                    entities=extraction.entities,
                    relations=extraction.relations,
                    chunks=extraction.chunks,
                    correlation_id=correlation_id,
                )
            )
    if job is not None or logs or errors:
        results.append(
            commit_ingestion_records(
                repository,
                jobs=(job,) if job is not None else (),
                logs=logs,
                errors=errors,
            )
        )
    return tuple(results)


def commit_storage_bundle_with_recovery(
    repository: InMemoryStorageRepository,
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
    correlation_id: str | None = None,
) -> StorageRecoveryResult:
    """Commit a bundle with idempotent retry and rollback for partial writes."""

    corr = correlation_id or new_correlation_id("storage")
    chunk_tuple = tuple(chunks)
    log_tuple = tuple(logs)
    error_tuple = tuple(errors)
    attempts = max(1, max_retries + 1)
    recovery_errors: list[ErrorEnvelope] = []
    recovery_logs: list[LogEvent] = []
    rolled_back = False

    for attempt_index in range(attempts):
        snapshot = _repository_snapshot(repository)
        try:
            results = commit_storage_bundle(
                repository,
                raw_artifact=raw_artifact,
                source=source,
                document=document,
                chunks=chunk_tuple,
                job=job,
                logs=log_tuple,
                errors=error_tuple,
                enrich_graph=enrich_graph,
                correlation_id=corr,
            )
            recovery_log = _success_log(
                correlation_id=corr,
                operation_name="commit_storage_bundle_with_recovery",
                event_name="storage_bundle_committed",
                output_reference=_bundle_output_reference(raw_artifact, document, chunk_tuple),
                details={
                    "attempts": attempt_index + 1,
                    "max_retries": max_retries,
                    "idempotency_keys": _bundle_idempotency_keys(raw_artifact, document, chunk_tuple, job),
                },
            )
            repository.add_log(recovery_log)
            recovery_logs.append(recovery_log)
            return StorageRecoveryResult(
                committed=True,
                attempts=attempt_index + 1,
                partial_commit_rolled_back=rolled_back,
                results=results,
                errors=tuple(recovery_errors),
                logs=tuple(recovery_logs),
            )
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            _restore_repository_snapshot(repository, snapshot)
            rolled_back = True
            error = _storage_error_from_exception(
                exc,
                correlation_id=corr,
                retry_count=attempt_index,
                max_retries=max_retries,
                retryable=retryable and attempt_index < max_retries,
            )
            repository.save_error(error)
            recovery_errors.append(error)
            if retryable and attempt_index < max_retries:
                retry_log = _storage_retry_log(
                    correlation_id=corr,
                    message=str(exc),
                    retry_count=attempt_index + 1,
                    max_retries=max_retries,
                )
                repository.add_log(retry_log)
                recovery_logs.append(retry_log)
                continue
            failure_log = _storage_failure_log(
                correlation_id=corr,
                message=str(exc),
                retry_count=attempt_index,
                max_retries=max_retries,
            )
            repository.add_log(failure_log)
            recovery_logs.append(failure_log)
            return StorageRecoveryResult(
                committed=False,
                attempts=attempt_index + 1,
                partial_commit_rolled_back=rolled_back,
                errors=tuple(recovery_errors),
                logs=tuple(recovery_logs),
            )

    return StorageRecoveryResult(committed=False, attempts=attempts, partial_commit_rolled_back=rolled_back)


def verify_storage_commit(
    repository: InMemoryStorageRepository,
    *,
    raw_artifacts: Iterable[RawArtifact] | None = None,
    raw_artifact_ids: Iterable[str] | None = None,
    documents: Iterable[DocumentRecord] | None = None,
    chunks: Iterable[ChunkRecord] | None = None,
    correlation_id: str | None = None,
) -> StorageVerificationResult:
    """Verify raw artifacts/documents/chunks exist and access metadata is present."""

    expected_raw_artifact_ids = _expected_raw_artifact_ids(raw_artifacts, raw_artifact_ids)
    expected_documents = tuple(documents if documents is not None else repository.documents.values())
    explicit_chunks = chunks is not None
    expected_chunks = tuple(chunks if explicit_chunks else repository.chunks.values())
    missing_raw_artifacts = _missing_raw_artifact_ids(repository, expected_raw_artifact_ids)
    missing_documents = _missing_document_ids(repository, expected_documents, expected_chunks)
    missing_chunks = _missing_chunk_ids(
        repository,
        expected_documents,
        expected_chunks,
        require_document_chunks=not explicit_chunks,
    )
    missing_access = verify_access_metadata(
        [*repository.sources.values(), *expected_documents, *expected_chunks]
    )
    ok = not missing_raw_artifacts and not missing_documents and not missing_chunks and not missing_access
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="verify_storage_commit",
        event_name="storage_verified" if ok else "storage_verification_failed",
        details={
            "ok": ok,
            "missing_raw_artifacts": missing_raw_artifacts,
            "missing_documents": missing_documents,
            "missing_chunks": missing_chunks,
            "missing_access_metadata": missing_access,
        },
    )
    repository.add_log(log)
    return StorageVerificationResult(
        ok=ok,
        missing_raw_artifacts=missing_raw_artifacts,
        missing_documents=missing_documents,
        missing_chunks=missing_chunks,
        missing_access_metadata=missing_access,
        log=log,
    )


def verify_graph_storage(
    repository: InMemoryStorageRepository,
    *,
    entities: Iterable[EntityRecord] | None = None,
    relations: Iterable[RelationRecord] | None = None,
    correlation_id: str | None = None,
) -> StorageVerificationResult:
    """Verify graph endpoints, evidence chunks, and graph reverse indexes."""

    expected_entities = tuple(entities if entities is not None else repository.entities.values())
    expected_relations = tuple(relations if relations is not None else repository.relations.values())
    missing_entities = {
        entity.entity_id for entity in expected_entities if entity.entity_id not in repository.entities
    }
    missing_relations = {
        relation.relation_id for relation in expected_relations if relation.relation_id not in repository.relations
    }
    missing_chunks: set[str] = set()
    for relation in expected_relations:
        if relation.subject_entity_id not in repository.entities:
            missing_entities.add(relation.subject_entity_id)
        if relation.object_entity_id not in repository.entities:
            missing_entities.add(relation.object_entity_id)
        if relation.relation_id not in repository.relation_ids_by_entity_id.get(relation.subject_entity_id, set()):
            missing_relations.add(f"{relation.relation_id}:subject_index")
        if relation.relation_id not in repository.relation_ids_by_entity_id.get(relation.object_entity_id, set()):
            missing_relations.add(f"{relation.relation_id}:object_index")
        for chunk_id in relation.evidence_chunk_ids:
            if chunk_id not in repository.chunks:
                missing_chunks.add(chunk_id)
            if relation.relation_id not in repository.relation_ids_by_chunk_id.get(chunk_id, set()):
                missing_relations.add(f"{relation.relation_id}:chunk_index")
    for entity in expected_entities:
        for alias in (entity.entity_name, *entity.aliases):
            alias_key = _entity_alias_key(alias)
            if entity.entity_id not in repository.entity_ids_by_alias.get(alias_key, set()):
                missing_entities.add(f"{entity.entity_id}:alias_index")
        for chunk_id, entity_ids in repository.entity_ids_by_chunk_id.items():
            if entity.entity_id not in entity_ids:
                continue
            if chunk_id not in repository.chunk_ids_by_entity_id.get(entity.entity_id, set()):
                missing_entities.add(f"{entity.entity_id}:chunk_reverse_index")
    for chunk in repository.chunks.values():
        for entity_id in _graph_flag_ids(chunk, "graph:entity:"):
            if entity_id not in repository.entity_ids_by_chunk_id.get(chunk.chunk_id, set()):
                missing_entities.add(f"{entity_id}:chunk_index")
            if chunk.chunk_id not in repository.chunk_ids_by_entity_id.get(entity_id, set()):
                missing_entities.add(f"{entity_id}:chunk_reverse_index")
        for relation_id in _graph_flag_ids(chunk, "graph:relation:"):
            if relation_id not in repository.relation_ids_by_chunk_id.get(chunk.chunk_id, set()):
                missing_relations.add(f"{relation_id}:chunk_index")
    ok = not missing_entities and not missing_relations and not missing_chunks
    log = _success_log(
        correlation_id=correlation_id,
        operation_name="verify_graph_storage",
        event_name="graph_verified" if ok else "graph_verification_degraded",
        details={
            "ok": ok,
            "missing_entities": tuple(sorted(missing_entities)),
            "missing_relations": tuple(sorted(missing_relations)),
            "missing_chunks": tuple(sorted(missing_chunks)),
        },
    )
    repository.add_log(log)
    return StorageVerificationResult(
        ok=ok,
        missing_entities=tuple(sorted(missing_entities)),
        missing_relations=tuple(sorted(missing_relations)),
        missing_chunks=tuple(sorted(missing_chunks)),
        log=log,
    )


def verify_access_metadata(records: Iterable[SourceRecord | DocumentRecord | ChunkRecord]) -> tuple[str, ...]:
    """Return record IDs that do not carry an access policy."""

    missing: list[str] = []
    for record in records:
        access_policy_id = getattr(record, "access_policy_id", None)
        if access_policy_id:
            continue
        missing.append(_record_identity(record))
    return tuple(missing)


def _expected_raw_artifact_ids(
    raw_artifacts: Iterable[RawArtifact] | None,
    raw_artifact_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    expected_ids: list[str] = []
    if raw_artifacts is not None:
        expected_ids.extend(raw_artifact.raw_artifact_id for raw_artifact in raw_artifacts)
    if raw_artifact_ids is not None:
        expected_ids.extend(raw_artifact_ids)
    return tuple(dict.fromkeys(expected_ids))


def _missing_raw_artifact_ids(
    repository: InMemoryStorageRepository,
    raw_artifact_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(raw_artifact_id for raw_artifact_id in raw_artifact_ids if raw_artifact_id not in repository.raw_artifacts)


def _missing_document_ids(
    repository: InMemoryStorageRepository,
    documents: tuple[DocumentRecord, ...],
    chunks: tuple[ChunkRecord, ...],
) -> tuple[str, ...]:
    missing = {document.document_id for document in documents if document.document_id not in repository.documents}
    missing.update(chunk.document_id for chunk in chunks if chunk.document_id not in repository.documents)
    return tuple(sorted(missing))


def _missing_chunk_ids(
    repository: InMemoryStorageRepository,
    documents: tuple[DocumentRecord, ...],
    chunks: tuple[ChunkRecord, ...],
    *,
    require_document_chunks: bool,
) -> tuple[str, ...]:
    missing = {chunk.chunk_id for chunk in chunks if chunk.chunk_id not in repository.chunks}
    if require_document_chunks:
        for document in documents:
            if document.document_id in repository.documents and not repository.chunks_for_document(document.document_id):
                missing.add(f"{document.document_id}:chunks")
    return tuple(sorted(missing))


def _record_identity(record: SourceRecord | DocumentRecord | ChunkRecord) -> str:
    if isinstance(record, SourceRecord):
        return record.source_id
    if isinstance(record, DocumentRecord):
        return record.document_id
    return record.chunk_id


def _graph_flag_ids(chunk: ChunkRecord, prefix: str) -> list[str]:
    return [flag.removeprefix(prefix) for flag in chunk.quality_flags if flag.startswith(prefix)]


def _entity_alias_key(alias: str) -> str:
    return " ".join(alias.strip().lower().split())


def _repository_snapshot(repository: InMemoryStorageRepository) -> dict[str, object]:
    snapshot = {
        field_name: deepcopy(getattr(repository, field_name))
        for field_name in repository.__dataclass_fields__
    }
    durable_snapshot = getattr(repository, "_snapshot_durable_state", None)
    if callable(durable_snapshot):
        snapshot["__durable_state__"] = durable_snapshot()
    return snapshot


def _restore_repository_snapshot(
    repository: InMemoryStorageRepository,
    snapshot: dict[str, object],
) -> None:
    durable_state = snapshot.get("__durable_state__")
    for field_name, value in snapshot.items():
        if field_name == "__durable_state__":
            continue
        setattr(repository, field_name, deepcopy(value))
    durable_restore = getattr(repository, "_restore_durable_state", None)
    if durable_state is not None and callable(durable_restore):
        durable_restore(durable_state)


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


def _bundle_idempotency_keys(
    raw_artifact: RawArtifact | None,
    document: DocumentRecord | None,
    chunks: tuple[ChunkRecord, ...],
    job: IngestionJob | None,
) -> dict[str, object]:
    return {
        "raw_artifact_id": raw_artifact.raw_artifact_id if raw_artifact is not None else None,
        "document_id": document.document_id if document is not None else None,
        "chunk_ids": tuple(chunk.chunk_id for chunk in chunks),
        "ingestion_job_id": job.ingestion_job_id if job is not None else None,
    }


def _storage_error_from_exception(
    exc: Exception,
    *,
    correlation_id: str,
    retry_count: int,
    max_retries: int,
    retryable: bool,
) -> ErrorEnvelope:
    details = dict(getattr(exc, "details", {}) or {})
    details.setdefault("exception_type", type(exc).__name__)
    return create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.STORAGE,
        operation_name="commit_storage_bundle_with_recovery",
        error_type=ErrorType.STORAGE,
        error_message=str(exc),
        severity=ErrorSeverity.RECOVERABLE if retryable else ErrorSeverity.CRITICAL,
        retryable=retryable,
        retry_count=retry_count,
        max_retries=max_retries,
        fallback_action=FallbackAction.RETRY if retryable else FallbackAction.STOP,
        details=details,
    )


def _storage_retry_log(
    *,
    correlation_id: str,
    message: str,
    retry_count: int,
    max_retries: int,
) -> LogEvent:
    return LogEvent(
        correlation_id=correlation_id,
        partition=Partition.STORAGE,
        event_type=LogEventType.RETRY,
        operation_name="commit_storage_bundle_with_recovery",
        message=message,
        details={
            "event_name": "storage_commit_retry",
            "retry_count": retry_count,
            "max_retries": max_retries,
            "partial_commit_rolled_back": True,
        },
    )


def _storage_failure_log(
    *,
    correlation_id: str,
    message: str,
    retry_count: int,
    max_retries: int,
) -> LogEvent:
    return LogEvent(
        correlation_id=correlation_id,
        partition=Partition.STORAGE,
        event_type=LogEventType.ERROR,
        operation_name="commit_storage_bundle_with_recovery",
        message=message,
        details={
            "event_name": "storage_commit_failed",
            "retry_count": retry_count,
            "max_retries": max_retries,
            "partial_commit_rolled_back": True,
        },
    )


def _success_log(
    *,
    correlation_id: str | None,
    operation_name: str,
    event_name: str,
    output_reference: str | None = None,
    details: dict[str, object] | None = None,
) -> LogEvent:
    return create_success_log_event(
        correlation_id=correlation_id or new_correlation_id("storage"),
        partition=Partition.STORAGE,
        operation_name=operation_name,
        event_name=event_name,
        output_reference=output_reference,
        details=details,
    )


from .adapters import (
    BackendAdapterConfig,
    BackendAdapterRegistry,
    BackendCapability,
    BackendHealthCheck,
    BackendOperationResult,
    BackendRuntimeAdapter,
    BackendSelection,
    BackendStatus,
    BackendType,
    create_local_backend_registry,
    validate_backend_plan,
)
from .durable import DurableStorageError, DurableStorageRepository, LocalDurableStorageBackendAdapter, SNAPSHOT_VERSION
from .neo4j_runtime import Neo4jGraphBackendAdapter
from .qdrant_runtime import QdrantVectorBackendAdapter
from .vector_runtime import InMemoryVectorBackendAdapter

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
    "DurableStorageError",
    "DurableStorageRepository",
    "InMemoryVectorBackendAdapter",
    "LocalDurableStorageBackendAdapter",
    "Neo4jGraphBackendAdapter",
    "PARTITION",
    "QdrantVectorBackendAdapter",
    "InMemoryStorageRepository",
    "StorageCommitResult",
    "StorageOperationError",
    "StorageRecoveryResult",
    "StorageVerificationResult",
    "SNAPSHOT_VERSION",
    "commit_chunks",
    "commit_document",
    "commit_graph_records",
    "commit_ingestion_records",
    "commit_raw_artifact",
    "commit_storage_bundle",
    "commit_storage_bundle_with_recovery",
    "create_local_backend_registry",
    "validate_backend_plan",
    "verify_access_metadata",
    "verify_graph_storage",
    "verify_storage_commit",
]
