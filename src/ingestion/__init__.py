"""Dependency-free ingestion behavior for early Milestone 1."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from shared.contracts import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    new_correlation_id,
    _utc_now,
)
from shared.enums import coerce_str_enum
from shared.fixtures import fixture_catalog_base, fixture_sources_base, resolve_fixture_path
from shared.policies import create_error_envelope, create_start_log_event, create_success_log_event
from shared.records import (
    ChunkRecord,
    DocumentRecord,
    DocumentType,
    FreshnessPolicy,
    IngestionJob,
    IngestionStatus,
    IngestionTriggerType,
    SourceRecord,
    SourceType,
)
from source_registry import access_level_from_source

PARTITION = "ingestion"
DEFAULT_CHUNK_MAX_CHARS = 800


class IngestionError(RuntimeError):
    """Raised when a deterministic ingestion step cannot continue."""

    def __init__(
        self,
        message: str,
        *,
        error_type: ErrorType = ErrorType.EXTRACTION,
        retryable: bool = False,
        raw_artifact: "RawArtifact | None" = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.raw_artifact = raw_artifact
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """In-memory reference to source bytes captured before parsing."""

    source_id: str
    content_bytes: bytes
    location: str
    external_link: str | None = None
    content_type: str = "application/octet-stream"
    metadata: dict[str, object] = field(default_factory=dict)
    raw_artifact_id: str = field(default_factory=lambda: new_correlation_id("raw"))

    @property
    def text(self) -> str:
        return self.content_bytes.decode("utf-8", errors="replace")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.content_bytes).hexdigest()

    def reference(self) -> dict[str, object]:
        return {
            "raw_artifact_id": self.raw_artifact_id,
            "source_id": self.source_id,
            "location": self.location,
            "external_link": self.external_link,
            "content_type": self.content_type,
            "byte_length": len(self.content_bytes),
            "checksum": self.checksum,
            **self.metadata,
        }


@dataclass(frozen=True, slots=True)
class NormalizedDocument:
    """Minimal normalized text and metadata before chunking exists."""

    source_id: str
    text: str
    title: str | None = None
    published_at: date | None = None
    document_type: DocumentType = DocumentType.OTHER
    metadata: dict[str, object] = field(default_factory=dict)
    quality_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class IngestionRunResult:
    """Complete outcome of a single ingestion run."""

    job: IngestionJob
    raw_artifact: RawArtifact | None = None
    normalized_document: NormalizedDocument | None = None
    document_record: DocumentRecord | None = None
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


class InMemoryIngestionJobRepository:
    """Tiny in-memory repository for jobs, logs, errors, and raw artifacts."""

    def __init__(self, initial_jobs: Iterable[IngestionJob] | None = None) -> None:
        self._jobs: dict[str, IngestionJob] = {}
        self._logs: dict[str, LogEvent] = {}
        self._errors: dict[str, ErrorEnvelope] = {}
        self._raw_artifacts: dict[str, RawArtifact] = {}
        self._documents: dict[str, DocumentRecord] = {}
        for job in initial_jobs or ():
            self.save_job(job)

    def save_job(self, job: IngestionJob) -> IngestionJob:
        self._jobs[job.ingestion_job_id] = job
        return job

    def get_job(self, ingestion_job_id: str) -> IngestionJob:
        try:
            return self._jobs[ingestion_job_id]
        except KeyError as exc:
            raise IngestionError(f"unknown ingestion_job_id: {ingestion_job_id}") from exc

    def add_log(self, job: IngestionJob, log: LogEvent) -> IngestionJob:
        self._logs[log.log_id] = log
        updated = replace(job, log_ids=[*job.log_ids, log.log_id])
        return self.save_job(updated)

    def add_error(self, job: IngestionJob, error: ErrorEnvelope) -> IngestionJob:
        self._errors[error.error_id] = error
        updated = replace(job, error_ids=[*job.error_ids, error.error_id], error_summary=error.error_message)
        return self.save_job(updated)

    def save_raw_artifact(self, raw_artifact: RawArtifact) -> RawArtifact:
        self._raw_artifacts[raw_artifact.raw_artifact_id] = raw_artifact
        return raw_artifact

    def save_document(self, document: DocumentRecord) -> DocumentRecord:
        self._documents[document.document_id] = document
        return document

    def logs_for_job(self, job: IngestionJob) -> tuple[LogEvent, ...]:
        return tuple(self._logs[log_id] for log_id in job.log_ids)

    def errors_for_job(self, job: IngestionJob) -> tuple[ErrorEnvelope, ...]:
        return tuple(self._errors[error_id] for error_id in job.error_ids)


def start_ingestion_job(
    source: SourceRecord,
    *,
    repository: InMemoryIngestionJobRepository | None = None,
    trigger_type: IngestionTriggerType | str = IngestionTriggerType.MANUAL,
    correlation_id: str | None = None,
) -> IngestionJob:
    """Create and log a running ingestion job for a source."""

    repo = repository or InMemoryIngestionJobRepository()
    corr = correlation_id or new_correlation_id("ingestion")
    resolved_trigger_type = coerce_str_enum(
        IngestionTriggerType,
        trigger_type,
        field_name="trigger_type",
        error_factory=_ingestion_enum_error,
    )
    job = repo.save_job(
        IngestionJob(
            source_id=source.source_id,
            trigger_type=resolved_trigger_type,
            correlation_id=corr,
            status=IngestionStatus.RUNNING,
        )
    )
    log = create_start_log_event(
        correlation_id=corr,
        partition=Partition.INGESTION,
        operation_name="start_ingestion_job",
        event_name="ingestion_started",
        input_reference=source.source_id,
        details={"source_id": source.source_id, "ingestion_job_id": job.ingestion_job_id},
    )
    return repo.add_log(job, log)


def _ingestion_enum_error(field_name: str, value: object) -> IngestionError:
    return IngestionError(
        f"invalid {field_name}: {value!r}",
        error_type=ErrorType.PARSING,
        retryable=False,
    )


def extract_source_content(
    source: SourceRecord,
    *,
    fixture_entry: dict[str, object] | None = None,
    catalog_path: str | Path | None = None,
) -> RawArtifact:
    """Load raw bytes from a safe fixture path or local source location."""

    path = _resolve_source_path(source, fixture_entry=fixture_entry, catalog_path=catalog_path)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise IngestionError(
            f"could not read source content: {path}",
            error_type=ErrorType.EXTRACTION,
            retryable=False,
            details={"location": str(path)},
        ) from exc

    raw_artifact = RawArtifact(
        source_id=source.source_id,
        content_bytes=content,
        location=str(path),
        external_link=source.external_link,
        content_type=_content_type_for_path(path),
        metadata={
            "source_name": source.source_name,
            "internal_location": source.internal_location,
            "external_fixture_path": str(fixture_entry["path"]) if fixture_entry else None,
        },
    )
    return raw_artifact


def normalize_document(raw_artifact: RawArtifact, source: SourceRecord) -> NormalizedDocument:
    """Normalize raw content enough to create document metadata, without chunking."""

    text = raw_artifact.text
    quality_flags: list[str] = []
    metadata = {"raw_artifact": raw_artifact.reference()}

    try:
        if raw_artifact.content_type == "application/json":
            normalized_text, title, parsed_metadata = _normalize_json(text, source)
            metadata.update(parsed_metadata)
        elif raw_artifact.content_type == "text/csv":
            normalized_text, title, parsed_metadata = _normalize_csv(text, source)
            metadata.update(parsed_metadata)
        elif raw_artifact.content_type == "text/html":
            normalized_text, title, parsed_metadata, html_flags = _normalize_html(text, source)
            metadata.update(parsed_metadata)
            quality_flags.extend(html_flags)
        else:
            normalized_text = _collapse_whitespace(text)
            title = _extract_markdown_title(text) or source.source_name
    except (csv.Error, json.JSONDecodeError) as exc:
        raise IngestionError(
            "source parsing failed",
            error_type=ErrorType.PARSING,
            retryable=False,
            raw_artifact=raw_artifact,
            details={"raw_artifact_id": raw_artifact.raw_artifact_id},
        ) from exc

    published_at = _first_date(normalized_text) or _first_date(text)
    if not normalized_text:
        raise IngestionError(
            "required source text is missing",
            error_type=ErrorType.EXTRACTION,
            retryable=False,
            raw_artifact=raw_artifact,
            details={"raw_artifact_id": raw_artifact.raw_artifact_id},
        )

    return NormalizedDocument(
        source_id=source.source_id,
        text=normalized_text,
        title=title,
        published_at=published_at,
        document_type=_document_type_for_source(source, raw_artifact),
        metadata=metadata,
        quality_flags=quality_flags,
    )


def create_document_record(
    source: SourceRecord,
    normalized: NormalizedDocument,
    raw_artifact: RawArtifact,
) -> DocumentRecord:
    """Create document metadata while inheriting source governance fields."""

    retrieved_at = source.last_checked_at or _utc_now()
    document = DocumentRecord(
        source_id=source.source_id,
        title=normalized.title,
        author_or_owner=source.owner,
        published_at=normalized.published_at,
        retrieved_at=retrieved_at,
        document_type=normalized.document_type,
        canonical_url=source.external_link,
        checksum=raw_artifact.checksum,
        version=source.last_ingested_at.isoformat() if source.last_ingested_at else None,
        access_level=access_level_from_source(source),
        as_of_date=_freshness_date(source, normalized),
        access_policy_id=source.access_policy_id,
    )
    return document


def split_document_into_chunks(
    normalized: NormalizedDocument,
    document: DocumentRecord,
    *,
    source: SourceRecord | None = None,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap_chars: int = 0,
) -> tuple[ChunkRecord, ...]:
    """Split normalized text into deterministic chunk records with inherited access metadata."""

    spans = _chunk_text_spans(normalized.text, max_chars=max_chars, overlap_chars=overlap_chars)
    chunks = [
        ChunkRecord(
            document_id=document.document_id,
            source_id=document.source_id,
            chunk_index=index,
            heading_path=_heading_path_for_offset(normalized.text, start_offset),
            text=normalized.text[start_offset:end_offset],
            token_count=_token_count(normalized.text[start_offset:end_offset]),
            page_number=_page_for_offset(normalized.metadata, start_offset),
            start_offset=start_offset,
            end_offset=end_offset,
            access_policy_id=document.access_policy_id or (source.access_policy_id if source else None),
            allowed_principals=list(source.allowed_principals if source else ()),
            as_of_date=document.as_of_date,
            valid_from=document.valid_from,
            valid_to=document.valid_to,
        )
        for index, (start_offset, end_offset) in enumerate(spans)
    ]
    return assign_chunk_ids(chunks, document=document)


def assign_chunk_ids(
    chunks: Iterable[ChunkRecord],
    *,
    document: DocumentRecord,
) -> tuple[ChunkRecord, ...]:
    """Assign stable chunk IDs from source/checksum/index/offset/text inputs."""

    assigned: list[ChunkRecord] = []
    checksum = document.checksum or _stable_digest(document.source_id, document.title or "")
    for chunk in chunks:
        chunk_digest = _stable_digest(
            document.source_id,
            checksum,
            str(chunk.chunk_index),
            str(chunk.start_offset),
            str(chunk.end_offset),
            chunk.text,
        )
        assigned.append(replace(chunk, chunk_id=f"chunk_{chunk_digest[:24]}"))
    return tuple(assigned)


def run_ingestion_job(
    source: SourceRecord,
    *,
    repository: InMemoryIngestionJobRepository | None = None,
    max_retries: int = 1,
    fixture_entry: dict[str, object] | None = None,
    catalog_path: str | Path | None = None,
    extractor: Callable[..., RawArtifact] | None = None,
) -> IngestionRunResult:
    """Run extraction, normalization, and document-record creation with retry logs."""

    repo = repository or InMemoryIngestionJobRepository()
    job = start_ingestion_job(source, repository=repo)
    raw_artifact: RawArtifact | None = None
    normalized: NormalizedDocument | None = None
    document: DocumentRecord | None = None
    errors: list[ErrorEnvelope] = []
    extractor_fn = extractor or extract_source_content

    for attempt in range(max_retries + 1):
        try:
            raw_artifact = extractor_fn(source, fixture_entry=fixture_entry, catalog_path=catalog_path)
            repo.save_raw_artifact(raw_artifact)
            extraction_log = create_success_log_event(
                correlation_id=job.correlation_id or new_correlation_id("ingestion"),
                partition=Partition.INGESTION,
                operation_name="extract_source_content",
                event_name="extraction_completed",
                output_reference=raw_artifact.raw_artifact_id,
                details=raw_artifact.reference(),
            )
            job = repo.add_log(job, extraction_log)
            break
        except IngestionError as exc:
            raw_artifact = exc.raw_artifact or raw_artifact
            error = _error_from_exception(job, "extract_source_content", exc, attempt, max_retries)
            errors.append(error)
            job = repo.add_error(job, error)
            if exc.retryable and attempt < max_retries:
                job = repo.add_log(job, _retry_log(job, "extract_source_content", exc, attempt + 1))
                continue
            return _finish_job(repo, job, IngestionStatus.FAILED, raw_artifact, None, None, errors)

    try:
        if raw_artifact is None:
            raise IngestionError("source extraction produced no raw artifact", error_type=ErrorType.EXTRACTION)
        normalized = normalize_document(raw_artifact, source)
        if normalized.quality_flags:
            error = create_error_envelope(
                correlation_id=job.correlation_id or new_correlation_id("ingestion"),
                partition=Partition.INGESTION,
                operation_name="normalize_document",
                error_type=ErrorType.PARSING,
                error_message="document parsed with degraded metadata or malformed structure",
                severity=ErrorSeverity.WARNING,
                retryable=False,
                fallback_action=FallbackAction.PARTIAL_COMMIT,
                details={
                    "source_id": source.source_id,
                    "raw_artifact_id": raw_artifact.raw_artifact_id,
                    "quality_flags": normalized.quality_flags,
                },
            )
            errors.append(error)
            job = repo.add_error(job, error)
        document = create_document_record(source, normalized, raw_artifact)
        repo.save_document(document)
    except IngestionError as exc:
        raw_artifact = exc.raw_artifact or raw_artifact
        error = _error_from_exception(job, "normalize_document", exc, 0, 0)
        errors.append(error)
        job = repo.add_error(job, error)
        return _finish_job(repo, job, IngestionStatus.FAILED, raw_artifact, normalized, document, errors)

    status = IngestionStatus.PARTIAL if normalized.quality_flags else IngestionStatus.COMPLETED
    return _finish_job(repo, job, status, raw_artifact, normalized, document, errors)


def _finish_job(
    repo: InMemoryIngestionJobRepository,
    job: IngestionJob,
    status: IngestionStatus,
    raw_artifact: RawArtifact | None,
    normalized: NormalizedDocument | None,
    document: DocumentRecord | None,
    errors: list[ErrorEnvelope],
) -> IngestionRunResult:
    event_name = {
        IngestionStatus.COMPLETED: "ingestion_completed",
        IngestionStatus.PARTIAL: "ingestion_partial",
        IngestionStatus.FAILED: "ingestion_failed",
    }[status]
    operation_name = "complete_ingestion_job"
    details = {
        "event_name": event_name,
        "source_id": job.source_id,
        "ingestion_job_id": job.ingestion_job_id,
        "status": status.value,
        "error_ids": [error.error_id for error in errors],
    }
    if status is IngestionStatus.COMPLETED:
        log = create_success_log_event(
            correlation_id=job.correlation_id or new_correlation_id("ingestion"),
            partition=Partition.INGESTION,
            operation_name=operation_name,
            event_name=event_name,
            output_reference=document.document_id if document else None,
            details=details,
        )
    else:
        log = LogEvent(
            correlation_id=job.correlation_id or new_correlation_id("ingestion"),
            partition=Partition.INGESTION,
            event_type=LogEventType.ERROR if status is IngestionStatus.FAILED else LogEventType.WARNING,
            operation_name=operation_name,
            message=f"Ingestion job {status.value}.",
            output_reference=document.document_id if document else None,
            details=details,
        )
    job = repo.add_log(job, log)
    job = replace(
        job,
        status=status,
        completed_at=_utc_now(),
        quality_flags=list(normalized.quality_flags if normalized else ()),
    )
    job = repo.save_job(job)
    return IngestionRunResult(
        job=job,
        raw_artifact=raw_artifact,
        normalized_document=normalized,
        document_record=document,
        logs=repo.logs_for_job(job),
        errors=tuple(errors),
    )


def _resolve_source_path(
    source: SourceRecord,
    *,
    fixture_entry: dict[str, object] | None,
    catalog_path: str | Path | None,
) -> Path:
    if fixture_entry is not None:
        return resolve_fixture_path(fixture_entry, catalog_path)
    if not source.internal_location:
        raise IngestionError(
            "source internal_location or fixture_entry is required",
            error_type=ErrorType.EXTRACTION,
            retryable=False,
            details={"source_id": source.source_id},
        )

    location = Path(source.internal_location)
    if location.is_absolute():
        return location

    base = fixture_catalog_base(catalog_path) if location.parts[:1] == ("sources",) else fixture_sources_base(catalog_path)
    candidate = (base / location).resolve()
    allowed_base = fixture_sources_base(catalog_path).resolve()
    try:
        candidate.relative_to(allowed_base)
        return candidate
    except ValueError:
        return (Path.cwd() / location).resolve()


def _content_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".json": "application/json",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")


def _document_type_for_source(source: SourceRecord, raw_artifact: RawArtifact) -> DocumentType:
    if raw_artifact.content_type == "text/html":
        return DocumentType.HTML
    if raw_artifact.content_type == "text/markdown":
        return DocumentType.MARKDOWN
    if raw_artifact.content_type == "application/json" or source.source_type is SourceType.API:
        return DocumentType.API_RESPONSE
    if raw_artifact.content_type == "text/csv" or source.source_type is SourceType.TABLE:
        return DocumentType.DATABASE_ROW_SET
    return DocumentType.OTHER


def _normalize_html(
    text: str,
    source: SourceRecord,
) -> tuple[str, str | None, dict[str, object], list[str]]:
    flags: list[str] = []
    lowered = text.lower()
    if "</html>" not in lowered or "</body>" not in lowered:
        flags.append("parsing_degraded")
    title = _regex_text(r"<title[^>]*>(.*?)</title>", text) or _regex_text(r"<h1[^>]*>(.*?)</h1>", text)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<[^>]+>", " ", body)
    return _collapse_whitespace(html.unescape(body)), title or source.source_name, {}, flags


def _normalize_json(text: str, source: SourceRecord) -> tuple[str, str | None, dict[str, object]]:
    data = json.loads(text)
    lines: list[str] = []
    if isinstance(data, dict):
        title = str(data.get("service") or data.get("title") or source.source_name)
        for key, value in data.items():
            if key == "items" and isinstance(value, list):
                for item in value:
                    lines.append(json.dumps(item, sort_keys=True))
            elif value is not None:
                lines.append(f"{key}: {value}")
        return _collapse_whitespace("\n".join(lines)), title, {"json_keys": sorted(data)}
    return _collapse_whitespace(json.dumps(data, sort_keys=True)), source.source_name, {}


def _normalize_csv(text: str, source: SourceRecord) -> tuple[str, str | None, dict[str, object]]:
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        return _collapse_whitespace(text), source.source_name, {"row_count": 0}
    headings = rows[0].keys()
    lines = [" | ".join(str(row.get(heading, "")) for heading in headings) for row in rows]
    return "\n".join(lines), source.source_name, {"row_count": len(rows), "columns": list(headings)}


def _extract_markdown_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _regex_text(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _collapse_whitespace(re.sub(r"<[^>]+>", " ", match.group(1)))


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_date(text: str) -> date | None:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})(?=\D|$)", text)
    if not match:
        return None
    return date.fromisoformat(match.group(1))


def _freshness_date(source: SourceRecord, normalized: NormalizedDocument) -> date | None:
    if normalized.published_at is not None:
        return normalized.published_at
    if source.last_checked_at is not None:
        return source.last_checked_at.date()
    if source.freshness_policy is FreshnessPolicy.REAL_TIME:
        return _utc_now().date()
    return None


def _chunk_text_spans(text: str, *, max_chars: int, overlap_chars: int) -> tuple[tuple[int, int], ...]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    spans: list[tuple[int, int]] = []
    start = _next_non_whitespace(text, 0)
    while start < len(text):
        end = _chunk_end(text, start, max_chars)
        spans.append((start, end))
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap_chars)
        start = _next_non_whitespace(text, next_start)
    return tuple(spans)


def _next_non_whitespace(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _chunk_end(text: str, start: int, max_chars: int) -> int:
    hard_end = min(len(text), start + max_chars)
    if hard_end == len(text):
        return len(text.rstrip())
    paragraph_break = text.rfind("\n\n", start + 1, hard_end)
    if paragraph_break > start:
        return paragraph_break
    whitespace_break = max(text.rfind(" ", start + 1, hard_end), text.rfind("\n", start + 1, hard_end))
    if whitespace_break > start:
        return whitespace_break
    return hard_end


def _heading_path_for_offset(text: str, offset: int) -> list[str]:
    headings: list[str] = []
    for match in re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text):
        if match.start() > offset:
            break
        level = len(match.group(1))
        heading = match.group(2).strip()
        headings = headings[: level - 1]
        headings.append(heading)
    return headings


def _page_for_offset(metadata: dict[str, object], offset: int) -> int | None:
    pages = metadata.get("pages")
    if not isinstance(pages, list):
        return None
    page_number: int | None = None
    for page in pages:
        if not isinstance(page, dict):
            continue
        start = page.get("start_offset")
        end = page.get("end_offset")
        number = page.get("page_number")
        if isinstance(start, int) and isinstance(end, int) and isinstance(number, int) and start <= offset < end:
            page_number = number
            break
    return page_number


def _token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _stable_digest(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _error_from_exception(
    job: IngestionJob,
    operation_name: str,
    exc: IngestionError,
    retry_count: int,
    max_retries: int,
) -> ErrorEnvelope:
    return create_error_envelope(
        correlation_id=job.correlation_id or new_correlation_id("ingestion"),
        partition=Partition.INGESTION,
        operation_name=operation_name,
        error_type=exc.error_type,
        error_message=str(exc),
        severity=ErrorSeverity.RECOVERABLE if exc.retryable else ErrorSeverity.WARNING,
        retryable=exc.retryable,
        retry_count=retry_count,
        max_retries=max_retries,
        fallback_action=FallbackAction.RETRY if exc.retryable else FallbackAction.STOP,
        details={"source_id": job.source_id, **exc.details},
    )


def _retry_log(job: IngestionJob, operation_name: str, exc: IngestionError, retry_count: int) -> LogEvent:
    return LogEvent(
        correlation_id=job.correlation_id or new_correlation_id("ingestion"),
        partition=Partition.INGESTION,
        event_type=LogEventType.RETRY,
        operation_name=operation_name,
        message=str(exc),
        details={
            "event_name": "ingestion_retry",
            "source_id": job.source_id,
            "retry_count": retry_count,
            "error_type": exc.error_type.value,
        },
    )


__all__ = [
    "PARTITION",
    "IngestionError",
    "InMemoryIngestionJobRepository",
    "IngestionRunResult",
    "NormalizedDocument",
    "RawArtifact",
    "assign_chunk_ids",
    "create_document_record",
    "extract_source_content",
    "normalize_document",
    "run_ingestion_job",
    "split_document_into_chunks",
    "start_ingestion_job",
]
