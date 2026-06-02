from pathlib import Path
from tempfile import TemporaryDirectory

from ingestion import (
    InMemoryIngestionJobRepository,
    IngestionError,
    extract_source_content,
    normalize_document,
    run_ingestion_job,
    start_ingestion_job,
)
from shared import (
    AccessMethod,
    DocumentType,
    ErrorType,
    IngestionStatus,
    IngestionTriggerType,
    LicensePolicy,
    LogEventType,
    Partition,
    ReliabilityLevel,
    SourceRecord,
    SourceStatus,
    SourceType,
    fixtures_by_set,
    load_fixture_catalog,
)
from shared.contracts import _utc_now


def _fixture(fixture_id: str) -> dict[str, object]:
    catalog = load_fixture_catalog()
    return next(entry for entry in catalog["fixtures"] if entry["id"] == fixture_id)


def _source_from_fixture(fixture_id: str, *, access_policy_id: str = "access:public") -> SourceRecord:
    entry = _fixture(fixture_id)
    return SourceRecord(
        source_name=str(entry["source_name"]),
        source_type=SourceType(str(entry["source_type"])),
        owner="fixtures",
        access_method=AccessMethod.FILESYSTEM,
        external_link=entry["external_link"],
        internal_location=str(entry["path"]),
        license_policy=LicensePolicy(str(entry["license"])),
        access_policy_id=access_policy_id,
        reliability_level=ReliabilityLevel(str(entry["reliability"])),
        status=SourceStatus(str(entry["status"])),
        last_checked_at=_utc_now(),
    )


def test_start_ingestion_job_creates_correlation_id() -> None:
    repository = InMemoryIngestionJobRepository()
    source = _source_from_fixture("fixture_a_public_document")

    job = start_ingestion_job(source, repository=repository)
    logs = repository.logs_for_job(job)

    assert job.status is IngestionStatus.RUNNING
    assert job.correlation_id is not None
    assert logs[0].correlation_id == job.correlation_id
    assert logs[0].details["event_name"] == "ingestion_started"


def test_start_ingestion_job_accepts_string_trigger_type() -> None:
    repository = InMemoryIngestionJobRepository()
    source = _source_from_fixture("fixture_a_public_document")

    job = start_ingestion_job(source, repository=repository, trigger_type="repair")

    assert job.trigger_type is IngestionTriggerType.REPAIR


def test_start_ingestion_job_rejects_invalid_trigger_type() -> None:
    source = _source_from_fixture("fixture_a_public_document")

    try:
        start_ingestion_job(source, trigger_type="not_a_trigger")
    except IngestionError as exc:
        assert str(exc) == "invalid trigger_type: 'not_a_trigger'"
        assert exc.error_type is ErrorType.PARSING
        assert isinstance(exc.__cause__, ValueError)
        return

    raise AssertionError("Expected IngestionError for invalid trigger_type.")


def test_extract_source_content_returns_raw_artifact_reference() -> None:
    source = _source_from_fixture("fixture_a_public_document")

    raw_artifact = extract_source_content(source)
    reference = raw_artifact.reference()

    assert reference["source_id"] == source.source_id
    assert reference["external_link"] == source.external_link
    assert reference["byte_length"] > 0
    assert reference["checksum"] == raw_artifact.checksum
    assert "Public Retrieval Primer" in raw_artifact.text


def test_normalize_document_preserves_title_headings_dates() -> None:
    source = _source_from_fixture("fixture_a_public_document")
    raw_artifact = extract_source_content(source)

    normalized = normalize_document(raw_artifact, source)

    assert normalized.title == "Public Retrieval Primer"
    assert normalized.published_at is not None
    assert normalized.published_at.isoformat() == "2026-05-20"
    assert "alpha evidence bridge" in normalized.text
    assert normalized.document_type is DocumentType.MARKDOWN


def test_normalize_html_fixture_preserves_title_date_type_and_text() -> None:
    source = _source_from_fixture("fixture_g_external_web_page")
    raw_artifact = extract_source_content(source)

    normalized = normalize_document(raw_artifact, source)

    assert normalized.title == "Acme Public Status Page"
    assert normalized.published_at is not None
    assert normalized.published_at.isoformat() == "2026-05-20"
    assert normalized.document_type is DocumentType.HTML
    assert "standard support window is four business hours" in normalized.text
    assert normalized.quality_flags == []


def test_normalize_json_fixture_preserves_iso_datetime_date_type_and_metadata() -> None:
    source = _source_from_fixture("fixture_api_json")

    result = run_ingestion_job(source)

    assert result.job.status is IngestionStatus.COMPLETED
    assert result.normalized_document is not None
    assert result.normalized_document.title == "acme-retrieval-metadata"
    assert result.normalized_document.published_at is not None
    assert result.normalized_document.published_at.isoformat() == "2026-05-20"
    assert result.normalized_document.document_type is DocumentType.API_RESPONSE
    assert "api-item-001" in result.normalized_document.text
    assert result.normalized_document.metadata["json_keys"] == [
        "items",
        "next_page",
        "retrieved_at",
        "service",
    ]
    assert result.document_record is not None
    assert result.document_record.published_at is not None
    assert result.document_record.published_at.isoformat() == "2026-05-20"
    assert result.document_record.as_of_date is not None
    assert result.document_record.as_of_date.isoformat() == "2026-05-20"


def test_normalize_csv_fixture_preserves_type_text_and_metadata() -> None:
    source = _source_from_fixture("fixture_table_csv", access_policy_id="access:internal")
    raw_artifact = extract_source_content(source)

    normalized = normalize_document(raw_artifact, source)

    assert normalized.title == "Sample Metrics Table"
    assert normalized.published_at is not None
    assert normalized.published_at.isoformat() == "2026-05-20"
    assert normalized.document_type is DocumentType.DATABASE_ROW_SET
    assert "indexed_documents | public | 42 | 2026-05-20" in normalized.text
    assert normalized.metadata["row_count"] == 3
    assert normalized.metadata["columns"] == [
        "metric",
        "segment",
        "value",
        "as_of_date",
        "citation_note",
    ]


def test_create_document_record_inherits_access_policy() -> None:
    source = _source_from_fixture("fixture_b_restricted_source", access_policy_id="access:restricted")

    result = run_ingestion_job(source)

    assert result.document_record is not None
    assert result.document_record.access_policy_id == source.access_policy_id
    assert result.document_record.access_level.value == "restricted"
    assert result.document_record.canonical_url == source.external_link


def test_ingestion_job_status_completed_on_success() -> None:
    source = _source_from_fixture("fixture_a_public_document")

    result = run_ingestion_job(source)
    event_names = [log.details["event_name"] for log in result.logs]

    assert result.job.status is IngestionStatus.COMPLETED
    assert result.document_record is not None
    assert event_names == ["ingestion_started", "extraction_completed", "ingestion_completed"]


def test_ingestion_job_status_failed_when_required_text_missing() -> None:
    with TemporaryDirectory() as temporary_directory:
        empty_file = Path(temporary_directory) / "empty.txt"
        empty_file.write_text("", encoding="utf-8")
        source = SourceRecord(
            source_name="Empty source",
            source_type=SourceType.DOCUMENT,
            access_method=AccessMethod.FILESYSTEM,
            internal_location=str(empty_file),
            access_policy_id="access:public",
        )

        result = run_ingestion_job(source)

    assert result.job.status is IngestionStatus.FAILED
    assert result.raw_artifact is not None
    assert result.document_record is None
    assert result.errors[0].error_type is ErrorType.EXTRACTION


def test_parsing_failure_preserves_raw_artifact_and_creates_error_envelope() -> None:
    source = _source_from_fixture("fixture_f_malformed_source")

    result = run_ingestion_job(source)

    assert result.job.status is IngestionStatus.PARTIAL
    assert result.raw_artifact is not None
    assert result.errors
    assert result.errors[0].partition is Partition.INGESTION
    assert result.errors[0].error_type is ErrorType.PARSING
    assert result.errors[0].details["raw_artifact_id"] == result.raw_artifact.raw_artifact_id
    assert "parsing_degraded" in result.job.quality_flags


def test_ingestion_logs_start_retry_partial_completed() -> None:
    source = _source_from_fixture("fixture_a_public_document")
    calls = {"count": 0}

    def flaky_extractor(source: SourceRecord, **kwargs: object):
        calls["count"] += 1
        if calls["count"] == 1:
            raise IngestionError("temporary timeout", error_type=ErrorType.TIMEOUT, retryable=True)
        return extract_source_content(source, **kwargs)

    result = run_ingestion_job(source, max_retries=1, extractor=flaky_extractor)
    event_names = [log.details["event_name"] for log in result.logs]
    retry_logs = [log for log in result.logs if log.event_type is LogEventType.RETRY]

    assert result.job.status is IngestionStatus.COMPLETED
    assert calls["count"] == 2
    assert "ingestion_started" in event_names
    assert "ingestion_retry" in event_names
    assert "extraction_completed" in event_names
    assert "ingestion_completed" in event_names
    assert retry_logs[0].details["retry_count"] == 1


def test_retryable_timeout_fails_after_max_retries_with_logs_and_errors() -> None:
    source = _source_from_fixture("fixture_a_public_document")
    calls = {"count": 0}

    def timeout_extractor(source: SourceRecord, **kwargs: object):
        calls["count"] += 1
        raise IngestionError("temporary timeout", error_type=ErrorType.TIMEOUT, retryable=True)

    result = run_ingestion_job(source, max_retries=2, extractor=timeout_extractor)
    event_names = [log.details["event_name"] for log in result.logs]
    retry_logs = [log for log in result.logs if log.event_type is LogEventType.RETRY]

    assert result.job.status is IngestionStatus.FAILED
    assert calls["count"] == 3
    assert result.raw_artifact is None
    assert result.document_record is None
    assert event_names == [
        "ingestion_started",
        "ingestion_retry",
        "ingestion_retry",
        "ingestion_failed",
    ]
    assert len(retry_logs) == 2
    assert len(result.errors) == 3
    assert all(error.error_type is ErrorType.TIMEOUT for error in result.errors)
    assert result.errors[-1].retry_count == 2
    assert result.errors[-1].max_retries == 2
    assert result.errors[-1].retryable is True


def test_fixture_catalog_public_and_malformed_examples_remain_available() -> None:
    grouped = fixtures_by_set(load_fixture_catalog())

    assert grouped["A"]
    assert grouped["F"][0]["expected_behavior"] == "fail_or_partial_with_error_envelope"
