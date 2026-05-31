from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import time
import unittest

from ingestion import NormalizedDocument, RawArtifact, create_document_record, split_document_into_chunks
from ranking import select_ranked_evidence
from retrieval import commit_sparse_index, commit_vectors, run_hybrid_search
from shared import AccessLevel, AccessMethod, DocumentType, FreshnessPolicy, LicensePolicy, SourceStatus, SourceType
from source_registry import SourceRegistry, check_source_refresh
from storage import InMemoryStorageRepository, StorageOperationError, commit_storage_bundle_with_recovery


def _source_bundle(text: str = "Graph retrieval source refresh evidence.") -> tuple[object, RawArtifact, object, tuple[object, ...]]:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Hardening source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.PUBLIC,
        license_policy=LicensePolicy.ALLOWED,
    )
    raw_artifact = RawArtifact(
        source_id=source.source_id,
        content_bytes=text.encode("utf-8"),
        location="memory://hardening.md",
        content_type="text/markdown",
    )
    normalized = NormalizedDocument(
        source_id=source.source_id,
        text=text,
        title="Hardening source",
        document_type=DocumentType.MARKDOWN,
    )
    document = create_document_record(source, normalized, raw_artifact)
    chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)
    return source, raw_artifact, document, chunks


class FailingOnceStorageRepository(InMemoryStorageRepository):
    def __init__(self) -> None:
        super().__init__()
        self.document_write_attempts = 0

    def save_document(self, document: object) -> object:
        self.document_write_attempts += 1
        if self.document_write_attempts == 1:
            raise StorageOperationError(
                "temporary metadata store timeout",
                retryable=True,
                details={"write_target": "documents"},
            )
        return super().save_document(document)  # type: ignore[arg-type]


class AlwaysFailingStorageRepository(InMemoryStorageRepository):
    def save_chunk(self, chunk: object) -> object:
        raise StorageOperationError(
            "chunk store rejected write",
            retryable=False,
            details={"write_target": "chunks"},
        )


class Milestone6HardeningTests(unittest.TestCase):
    def test_storage_recovery_rolls_back_partial_commit_and_retries_idempotently(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        repository = FailingOnceStorageRepository()

        result = commit_storage_bundle_with_recovery(
            repository,
            raw_artifact=raw_artifact,
            source=source,
            document=document,
            chunks=chunks,
            max_retries=1,
        )

        self.assertTrue(result.committed)
        self.assertTrue(result.partial_commit_rolled_back)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(repository.document_write_attempts, 2)
        self.assertEqual(tuple(repository.raw_artifacts), (raw_artifact.raw_artifact_id,))
        self.assertEqual(tuple(repository.documents), (document.document_id,))
        self.assertEqual(sorted(repository.chunks), sorted(chunk.chunk_id for chunk in chunks))
        self.assertIn("storage_commit_retry", [log.details.get("event_name") for log in result.logs])
        self.assertIn("storage_bundle_committed", [log.details.get("event_name") for log in repository.logs.values()])

    def test_storage_recovery_restores_snapshot_after_non_retryable_partial_commit(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        repository = AlwaysFailingStorageRepository()

        result = commit_storage_bundle_with_recovery(
            repository,
            raw_artifact=raw_artifact,
            source=source,
            document=document,
            chunks=chunks,
            max_retries=2,
        )

        self.assertFalse(result.committed)
        self.assertEqual(result.attempts, 1)
        self.assertTrue(result.partial_commit_rolled_back)
        self.assertEqual(repository.raw_artifacts, {})
        self.assertEqual(repository.sources, {})
        self.assertEqual(repository.documents, {})
        self.assertEqual(repository.chunks, {})
        self.assertEqual(result.errors[0].retryable, False)
        self.assertIn("storage_commit_failed", [log.details.get("event_name") for log in repository.logs.values()])

    def test_source_refresh_monitor_marks_scheduled_sources_due_and_current(self) -> None:
        registry = SourceRegistry()
        now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
        current = registry.register_source(
            source_name="Current scheduled source",
            source_type=SourceType.WEB,
            owner="ops",
            access_method=AccessMethod.URL,
            freshness_policy=FreshnessPolicy.SCHEDULED,
            freshness_sla="2d",
        )
        stale = registry.register_source(
            source_name="Stale scheduled source",
            source_type=SourceType.WEB,
            owner="ops",
            access_method=AccessMethod.URL,
            freshness_policy=FreshnessPolicy.SCHEDULED,
            freshness_sla="12h",
        )
        registry.repository.save(replace(current, last_checked_at=now - timedelta(hours=6)))
        registry.repository.save(replace(stale, last_checked_at=now - timedelta(days=2)))

        checks = {check.source_id: check for check in registry.monitor_source_refreshes(now=now)}

        self.assertFalse(checks[current.source_id].refresh_due)
        self.assertFalse(checks[current.source_id].stale)
        self.assertTrue(checks[stale.source_id].refresh_due)
        self.assertTrue(checks[stale.source_id].stale)
        self.assertEqual(checks[stale.source_id].interval_seconds, 12 * 60 * 60)

    def test_registered_refresh_interval_takes_precedence_over_freshness_sla(self) -> None:
        registry = SourceRegistry()
        now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
        source = registry.register_source(
            source_name="Explicit interval source",
            source_type=SourceType.WEB,
            owner="ops",
            access_method=AccessMethod.URL,
            freshness_policy=FreshnessPolicy.SCHEDULED,
            freshness_sla="1d",
            refresh_interval="P30D",
        )
        registry.repository.save(replace(source, last_checked_at=now - timedelta(days=2)))

        check = registry.check_source_refresh(source.source_id, now=now)

        self.assertFalse(check.refresh_due)
        self.assertFalse(check.stale)
        self.assertEqual(check.interval_seconds, 30 * 24 * 60 * 60)

    def test_iso_style_refresh_interval_prevents_policy_default_fallback(self) -> None:
        registry = SourceRegistry()
        now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
        source = registry.register_source(
            source_name="ISO interval source",
            source_type=SourceType.WEB,
            owner="ops",
            access_method=AccessMethod.URL,
            freshness_policy=FreshnessPolicy.SCHEDULED,
            refresh_interval="PT12H",
        )
        registry.repository.save(replace(source, last_checked_at=now - timedelta(hours=13)))

        check = registry.check_source_refresh(source.source_id, now=now)

        self.assertTrue(check.refresh_due)
        self.assertTrue(check.stale)
        self.assertEqual(check.interval_seconds, 12 * 60 * 60)

    def test_stale_source_status_update_deprecates_active_source_without_policy_mutation(self) -> None:
        registry = SourceRegistry()
        now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
        source = registry.register_source(
            source_name="Operational source",
            source_type=SourceType.API,
            owner="ops",
            access_method=AccessMethod.API,
            access_level=AccessLevel.INTERNAL,
            allowed_principals=["role:ops"],
            freshness_policy=FreshnessPolicy.REAL_TIME,
            status=SourceStatus.ACTIVE,
        )
        registry.repository.save(replace(source, last_checked_at=now - timedelta(hours=1)))

        updated, check = registry.update_stale_source_status(source.source_id, now=now)

        self.assertTrue(check.stale)
        self.assertEqual(updated.status, SourceStatus.DEPRECATED)
        self.assertEqual(updated.access_policy_id, source.access_policy_id)
        self.assertEqual(updated.allowed_principals, source.allowed_principals)

    def test_check_source_refresh_flags_never_checked_scheduled_source(self) -> None:
        registry = SourceRegistry()
        source = registry.register_source(
            source_name="Never checked source",
            source_type=SourceType.WEB,
            owner="ops",
            access_method=AccessMethod.URL,
            freshness_policy=FreshnessPolicy.SCHEDULED,
        )

        check = check_source_refresh(source, now=datetime(2026, 5, 22, tzinfo=UTC))

        self.assertTrue(check.refresh_due)
        self.assertTrue(check.stale)
        self.assertIsNotNone(check.error)

    def test_retrieval_and_ranking_load_path_stays_under_local_latency_target(self) -> None:
        repository = InMemoryStorageRepository()
        registry = SourceRegistry()
        source = registry.register_source(
            source_name="Load source",
            source_type=SourceType.DOCUMENT,
            owner="ops",
            access_method=AccessMethod.UPLOAD,
            license_policy=LicensePolicy.ALLOWED,
        )
        for index in range(120):
            document_id = f"doc_load_{index}"
            chunk = replace(
                split_document_into_chunks(
                    NormalizedDocument(
                        source_id=source.source_id,
                        text=f"Graph retrieval hardening evidence section {index} keeps citations and access policies intact.",
                    ),
                    document=replace(
                        create_document_record(
                            source,
                            NormalizedDocument(source_id=source.source_id, text="placeholder"),
                            RawArtifact(source.source_id, b"placeholder", "memory://placeholder"),
                        ),
                        document_id=document_id,
                    ),
                    source=source,
                    max_chars=120,
                )[0],
                chunk_id=f"chunk_load_{index}",
            )
            repository.save_source(source)
            repository.save_document(
                replace(
                    create_document_record(
                        source,
                        NormalizedDocument(source_id=source.source_id, text="placeholder"),
                        RawArtifact(source.source_id, b"placeholder", "memory://placeholder"),
                    ),
                    document_id=document_id,
                )
            )
            repository.save_chunk(chunk)
        commit_vectors(repository, repository.chunks.values())
        commit_sparse_index(repository, repository.chunks.values())

        started = time.perf_counter()
        retrieval = run_hybrid_search("graph retrieval hardening citations", repository, top_k=20)
        ranking = select_ranked_evidence("graph retrieval hardening citations", retrieval.candidates, top_k=10)
        elapsed_ms = (time.perf_counter() - started) * 1000

        self.assertLess(elapsed_ms, 750)
        self.assertEqual(len(retrieval.candidates), 20)
        self.assertEqual(len(ranking.candidates), 10)


if __name__ == "__main__":
    unittest.main()
