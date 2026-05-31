import unittest
from dataclasses import replace
from datetime import date

from ingestion import (
    NormalizedDocument,
    RawArtifact,
    assign_chunk_ids,
    create_document_record,
    split_document_into_chunks,
)
from shared import AccessMethod, ChunkRecord, DocumentType, SourceRecord, SourceType
from storage import (
    InMemoryStorageRepository,
    commit_storage_bundle,
    verify_access_metadata,
    verify_storage_commit,
)


def _source() -> SourceRecord:
    return SourceRecord(
        source_name="Chunk source",
        source_type=SourceType.DOCUMENT,
        access_method=AccessMethod.FILESYSTEM,
        access_policy_id="access:internal",
        allowed_principals=["role:analyst"],
    )


def _raw_artifact(source: SourceRecord, text: str) -> RawArtifact:
    return RawArtifact(
        source_id=source.source_id,
        content_bytes=text.encode("utf-8"),
        location="memory://chunk-source.md",
        content_type="text/markdown",
    )


def _document_fixture() -> tuple[SourceRecord, RawArtifact, NormalizedDocument]:
    source = _source()
    text = "# Intro\nAlpha beta gamma delta.\n\n## Details\nEpsilon zeta eta theta iota kappa."
    raw_artifact = _raw_artifact(source, text)
    normalized = NormalizedDocument(
        source_id=source.source_id,
        text=text,
        title="Chunk source",
        published_at=date(2026, 5, 20),
        document_type=DocumentType.MARKDOWN,
        metadata={"pages": [{"page_number": 1, "start_offset": 0, "end_offset": len(text)}]},
    )
    return source, raw_artifact, normalized


class ChunkingStorageTests(unittest.TestCase):
    def test_split_document_into_chunks_is_stable_and_preserves_offsets(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)

        first = split_document_into_chunks(normalized, document, source=source, max_chars=36)
        second = split_document_into_chunks(normalized, document, source=source, max_chars=36)

        self.assertEqual([chunk.chunk_id for chunk in first], [chunk.chunk_id for chunk in second])
        self.assertEqual(len(first), 3)
        self.assertEqual(first[0].start_offset, 0)
        self.assertEqual(first[0].text, normalized.text[first[0].start_offset : first[0].end_offset])
        self.assertEqual(first[1].text, normalized.text[first[1].start_offset : first[1].end_offset])
        self.assertEqual(first[2].heading_path, ["Intro", "Details"])
        self.assertEqual(first[0].page_number, 1)
        self.assertTrue(all(chunk.chunk_id.startswith("chunk_") for chunk in first))

    def test_equivalent_fresh_documents_produce_stable_chunk_ids(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        first_document = create_document_record(source, normalized, raw_artifact)
        second_document = create_document_record(source, normalized, raw_artifact)

        first_chunks = split_document_into_chunks(normalized, first_document, source=source, max_chars=36)
        second_chunks = split_document_into_chunks(normalized, second_document, source=source, max_chars=36)

        self.assertNotEqual(first_document.document_id, second_document.document_id)
        self.assertEqual([chunk.chunk_id for chunk in first_chunks], [chunk.chunk_id for chunk in second_chunks])

    def test_chunks_inherit_access_metadata_from_document_and_source(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)

        chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)

        self.assertEqual(chunks[0].access_policy_id, document.access_policy_id)
        self.assertEqual(chunks[0].allowed_principals, source.allowed_principals)
        self.assertEqual(chunks[0].as_of_date, document.as_of_date)

    def test_assign_chunk_ids_uses_offsets_and_index_as_deterministic_inputs(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)
        chunk = ChunkRecord(
            document_id=document.document_id,
            source_id=document.source_id,
            chunk_index=0,
            text="Alpha beta",
            start_offset=0,
            end_offset=10,
            access_policy_id=document.access_policy_id,
        )

        original = assign_chunk_ids([chunk], document=document)[0]
        moved = assign_chunk_ids([replace(chunk, start_offset=1, end_offset=11)], document=document)[0]

        self.assertNotEqual(original.chunk_id, moved.chunk_id)

    def test_commit_raw_document_chunks_and_verify_storage(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)
        chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)
        repository = InMemoryStorageRepository()

        results = commit_storage_bundle(
            repository,
            raw_artifact=raw_artifact,
            source=source,
            document=document,
            chunks=chunks,
        )
        verification = verify_storage_commit(
            repository,
            raw_artifacts=[raw_artifact],
            documents=[document],
            chunks=chunks,
        )

        self.assertIn(raw_artifact.raw_artifact_id, repository.raw_artifacts)
        self.assertIn(document.document_id, repository.documents)
        self.assertTrue(all(chunk.chunk_id in repository.chunks for chunk in chunks))
        self.assertEqual(
            [result.log.details["event_name"] for result in results if result.log],
            ["raw_artifact_committed", "document_committed", "chunks_committed"],
        )
        self.assertTrue(verification.ok)
        self.assertIsNotNone(verification.log)
        self.assertEqual(verification.log.details["event_name"], "storage_verified")
        self.assertEqual(verification.log.details["missing_raw_artifacts"], ())

    def test_verify_storage_commit_detects_missing_raw_artifact(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)
        chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)
        repository = InMemoryStorageRepository()

        commit_storage_bundle(repository, source=source, document=document, chunks=chunks)
        verification = verify_storage_commit(
            repository,
            raw_artifact_ids=[raw_artifact.raw_artifact_id],
            documents=[document],
            chunks=chunks,
        )

        self.assertFalse(verification.ok)
        self.assertEqual(verification.missing_raw_artifacts, (raw_artifact.raw_artifact_id,))
        self.assertEqual(verification.log.details["missing_raw_artifacts"], (raw_artifact.raw_artifact_id,))

    def test_verify_storage_commit_detects_missing_document_chunks_and_access_metadata(self) -> None:
        source, raw_artifact, normalized = _document_fixture()
        document = create_document_record(source, normalized, raw_artifact)
        chunks = split_document_into_chunks(normalized, document, source=source, max_chars=80)
        repository = InMemoryStorageRepository()

        commit_storage_bundle(repository, source=source, document=document)
        verification = verify_storage_commit(repository, documents=[document], chunks=chunks)

        self.assertFalse(verification.ok)
        self.assertEqual(verification.missing_chunks, tuple(chunk.chunk_id for chunk in chunks))

        missing_policy_document = replace(document, access_policy_id=None)
        missing_policy_chunk = replace(chunks[0], access_policy_id=None)

        missing_access = verify_access_metadata([source, missing_policy_document, missing_policy_chunk])

        self.assertIn(missing_policy_document.document_id, missing_access)
        self.assertIn(missing_policy_chunk.chunk_id, missing_access)


if __name__ == "__main__":
    unittest.main()
