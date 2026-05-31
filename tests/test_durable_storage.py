from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from ingestion import NormalizedDocument, RawArtifact, create_document_record, split_document_into_chunks
from shared import AccessLevel, AccessMethod, DocumentType, ErrorType, LicensePolicy, Partition, SourceType
from shared.policies import create_error_envelope, create_success_log_event
from storage import DurableStorageRepository, StorageOperationError, commit_storage_bundle, commit_storage_bundle_with_recovery


def _source_bundle() -> tuple[object, RawArtifact, object, tuple[object, ...]]:
    from source_registry import SourceRegistry

    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Durable source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.INTERNAL,
        allowed_principals=["role:analyst"],
        license_policy=LicensePolicy.ALLOWED,
    )
    raw_artifact = RawArtifact(
        source_id=source.source_id,
        content_bytes=b"# Durable\nJSON persistence keeps governed records recoverable.",
        location="memory://durable.md",
        content_type="text/markdown",
        metadata={"fixture": "durable"},
    )
    normalized = NormalizedDocument(
        source_id=source.source_id,
        text=raw_artifact.text,
        title="Durable source",
        published_at=date(2026, 5, 22),
        document_type=DocumentType.MARKDOWN,
    )
    document = create_document_record(source, normalized, raw_artifact)
    chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)
    return source, raw_artifact, document, chunks


class DurableStorageTests(unittest.TestCase):
    def test_round_trip_persists_core_records_without_changing_public_commit_api(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            repository = DurableStorageRepository(temporary)

            results = commit_storage_bundle(
                repository,
                raw_artifact=raw_artifact,
                source=source,
                document=document,
                chunks=chunks,
            )
            recovered = DurableStorageRepository(temporary)

        self.assertEqual([result.log.details["event_name"] for result in results if result.log], [
            "raw_artifact_committed",
            "document_committed",
            "chunks_committed",
        ])
        self.assertEqual(recovered.raw_artifacts[raw_artifact.raw_artifact_id].content_bytes, raw_artifact.content_bytes)
        self.assertEqual(recovered.sources[source.source_id], source)
        self.assertEqual(recovered.documents[document.document_id], document)
        self.assertEqual(recovered.chunks[chunks[0].chunk_id], chunks[0])
        self.assertEqual(len(recovered.logs), 3)

    def test_logs_and_errors_are_append_only_jsonl_streams(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = DurableStorageRepository(temporary)
            first_log = create_success_log_event(
                correlation_id="corr_append",
                partition=Partition.STORAGE,
                operation_name="first",
                event_name="first_append",
            )
            second_log = create_success_log_event(
                correlation_id="corr_append",
                partition=Partition.STORAGE,
                operation_name="second",
                event_name="second_append",
            )
            error = create_error_envelope(
                correlation_id="corr_append",
                partition=Partition.STORAGE,
                operation_name="append_error",
                error_type=ErrorType.STORAGE,
                error_message="durable append check",
            )

            repository.add_log(first_log)
            repository.add_log(second_log)
            repository.save_error(error)
            recovered = DurableStorageRepository(temporary)

            log_lines = Path(temporary, "logs.jsonl").read_text(encoding="utf-8").splitlines()
            error_lines = Path(temporary, "errors.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(log_lines), 2)
        self.assertEqual(len(error_lines), 1)
        self.assertEqual(tuple(recovered.logs), (first_log.log_id, second_log.log_id))
        self.assertIn(error.error_id, recovered.errors)

    def test_recovery_skips_malformed_snapshots_and_jsonl_rows(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            repository = DurableStorageRepository(temporary)
            commit_storage_bundle(repository, raw_artifact=raw_artifact, source=source, document=document, chunks=chunks)

            chunk_snapshot = json.loads(Path(temporary, "chunks.json").read_text(encoding="utf-8"))
            malformed_chunk = dict(chunks[0].to_dict())
            malformed_chunk["created_at"] = "not-a-date"
            malformed_chunk["chunk_id"] = "chunk_malformed"
            chunk_snapshot["records"].append(malformed_chunk)
            Path(temporary, "chunks.json").write_text(json.dumps(chunk_snapshot), encoding="utf-8")
            with Path(temporary, "logs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write("{not json}\n")

            recovered = DurableStorageRepository(temporary)

        self.assertIn(chunks[0].chunk_id, recovered.chunks)
        self.assertNotIn("chunk_malformed", recovered.chunks)
        self.assertEqual(len(recovered.logs), 3)
        self.assertTrue(any("chunks.json" in warning for warning in recovered.recovery_warnings))
        self.assertTrue(any("logs.jsonl" in warning for warning in recovered.recovery_warnings))

    def test_persistence_does_not_mutate_access_or_governance_fields(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        governed_chunk = replace(
            chunks[0],
            allowed_principals=["role:analyst", "user:fred"],
            access_policy_id=source.access_policy_id,
        )
        with tempfile.TemporaryDirectory() as temporary:
            repository = DurableStorageRepository(temporary)

            commit_storage_bundle(
                repository,
                raw_artifact=raw_artifact,
                source=source,
                document=document,
                chunks=[governed_chunk],
            )
            recovered = DurableStorageRepository(temporary)

        self.assertEqual(source.access_policy_id, recovered.sources[source.source_id].access_policy_id)
        self.assertEqual(source.allowed_principals, recovered.sources[source.source_id].allowed_principals)
        self.assertEqual(governed_chunk.access_policy_id, recovered.chunks[governed_chunk.chunk_id].access_policy_id)
        self.assertEqual(governed_chunk.allowed_principals, recovered.chunks[governed_chunk.chunk_id].allowed_principals)
        self.assertEqual(governed_chunk.allowed_principals, ["role:analyst", "user:fred"])

    def test_failed_recovery_restores_durable_files_not_only_memory(self) -> None:
        class FailingDurableStorageRepository(DurableStorageRepository):
            def save_chunk(self, chunk: object) -> object:
                raise StorageOperationError("durable chunk write failed", retryable=False)

        source, raw_artifact, document, chunks = _source_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            repository = FailingDurableStorageRepository(temporary)

            result = commit_storage_bundle_with_recovery(
                repository,
                raw_artifact=raw_artifact,
                source=source,
                document=document,
                chunks=chunks,
            )
            recovered = DurableStorageRepository(temporary)

        self.assertFalse(result.committed)
        self.assertTrue(result.partial_commit_rolled_back)
        self.assertEqual(repository.raw_artifacts, {})
        self.assertEqual(repository.sources, {})
        self.assertEqual(repository.documents, {})
        self.assertEqual(repository.chunks, {})
        self.assertEqual(recovered.raw_artifacts, {})
        self.assertEqual(recovered.sources, {})
        self.assertEqual(recovered.documents, {})
        self.assertEqual(recovered.chunks, {})
        self.assertEqual(len(recovered.errors), 1)
        self.assertIn("storage_commit_failed", [log.details.get("event_name") for log in recovered.logs.values()])


if __name__ == "__main__":
    unittest.main()
