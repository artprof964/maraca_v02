import unittest

from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    ChunkRecord,
    DocumentRecord,
    EvidenceCandidate,
    LicensePolicy,
    ReliabilityLevel,
    RetrievalMode,
    SourceType,
)
from source_registry import SourceRegistry
from storage import InMemoryStorageRepository, commit_chunks, commit_document
from retrieval import (
    apply_access_filter,
    commit_sparse_index,
    commit_vectors,
    merge_evidence_candidates,
    run_hybrid_search,
    run_keyword_retrieval,
    run_vector_retrieval,
)


def _add_source_bundle(
    repository: InMemoryStorageRepository,
    *,
    source_name: str,
    source_id_suffix: str,
    access_level: AccessLevel = AccessLevel.PUBLIC,
    allowed_principals: tuple[str, ...] = (),
    text: str,
    canonical_url: str = "https://example.test/source",
    reliability_level: ReliabilityLevel = ReliabilityLevel.MEDIUM,
) -> ChunkRecord:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name=source_name,
        source_type=SourceType.DOCUMENT,
        owner="research",
        access_method=AccessMethod.UPLOAD,
        access_level=access_level,
        allowed_principals=allowed_principals,
        license_policy=LicensePolicy.ALLOWED,
        reliability_level=reliability_level,
    )
    document = DocumentRecord(
        source_id=source.source_id,
        title=source_name,
        canonical_url=canonical_url,
        access_level=access_level,
        access_policy_id=source.access_policy_id,
        document_id=f"doc_{source_id_suffix}",
    )
    chunk = ChunkRecord(
        document_id=document.document_id,
        source_id=source.source_id,
        chunk_index=0,
        text=text,
        access_policy_id=source.access_policy_id,
        allowed_principals=list(allowed_principals),
        chunk_id=f"chunk_{source_id_suffix}",
    )
    commit_document(repository, document, source=source)
    commit_chunks(repository, [chunk])
    return chunk


class RetrievalExecutionTests(unittest.TestCase):
    def test_run_vector_retrieval_hydrates_semantic_evidence(self) -> None:
        repository = InMemoryStorageRepository()
        semantic = _add_source_bundle(
            repository,
            source_name="Semantic graph note",
            source_id_suffix="semantic",
            text="Graph retrieval ranks semantic evidence from chunk vectors.",
            reliability_level=ReliabilityLevel.HIGH,
        )
        _add_source_bundle(
            repository,
            source_name="Billing note",
            source_id_suffix="billing",
            text="Release notes describe billing export formats.",
        )
        commit_vectors(repository, repository.chunks.values())

        candidates = run_vector_retrieval("semantic graph evidence", repository, top_k=1)

        self.assertEqual(candidates[0].chunk_id, semantic.chunk_id)
        self.assertEqual(candidates[0].retrieval_mode, RetrievalMode.VECTOR)
        self.assertIn("semantic evidence", candidates[0].text_snippet)
        self.assertEqual(candidates[0].source_reliability, ReliabilityLevel.HIGH)
        self.assertEqual(candidates[0].citation_link, "https://example.test/source#chunk-0")

    def test_run_keyword_retrieval_hydrates_exact_evidence(self) -> None:
        repository = InMemoryStorageRepository()
        exact = _add_source_bundle(
            repository,
            source_name="Exact note",
            source_id_suffix="exact",
            text='The source contains "quoted phrase" and API_KEY_42.',
        )
        _add_source_bundle(
            repository,
            source_name="Approximate note",
            source_id_suffix="approx",
            text="The source contains approximate phrase and API key guidance.",
        )
        commit_sparse_index(repository, repository.chunks.values())

        candidates = run_keyword_retrieval('"quoted phrase"', repository, top_k=1)

        self.assertEqual(candidates[0].chunk_id, exact.chunk_id)
        self.assertEqual(candidates[0].retrieval_mode, RetrievalMode.KEYWORD)
        self.assertIn("API_KEY_42", candidates[0].text_snippet)

    def test_hybrid_search_filters_access_before_merge_and_dedupes(self) -> None:
        repository = InMemoryStorageRepository()
        public = _add_source_bundle(
            repository,
            source_name="Public graph note",
            source_id_suffix="public",
            text="Graph retrieval pipeline keeps exact graph citations attached.",
        )
        _add_source_bundle(
            repository,
            source_name="Restricted graph note",
            source_id_suffix="restricted",
            access_level=AccessLevel.RESTRICTED,
            allowed_principals=("alice",),
            text="Restricted SECRET_GRAPH_PLAN graph retrieval evidence.",
        )
        commit_vectors(repository, repository.chunks.values())
        commit_sparse_index(repository, repository.chunks.values())

        result = run_hybrid_search("graph retrieval pipeline", repository, principal="bob", top_k=5)

        self.assertEqual([candidate.chunk_id for candidate in result.candidates], [public.chunk_id])
        self.assertEqual(result.candidates[0].retrieval_mode, RetrievalMode.HYBRID)
        self.assertEqual(result.candidates[0].access_decision, AccessDecision.ALLOWED)
        self.assertGreaterEqual(result.excluded_count, 1)
        self.assertNotIn("SECRET_GRAPH_PLAN", [candidate.text_snippet for candidate in result.candidates])
        self.assertIn("retrieval_completed", [log.details.get("event_name") for log in result.logs])

    def test_apply_access_filter_fails_closed_when_metadata_is_missing(self) -> None:
        repository = InMemoryStorageRepository()
        chunk = _add_source_bundle(
            repository,
            source_name="Metadata gap",
            source_id_suffix="gap",
            text="Metadata gap should never pass filtering.",
        )
        repository.chunks[chunk.chunk_id] = ChunkRecord(
            document_id=chunk.document_id,
            source_id=chunk.source_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            access_policy_id=None,
            chunk_id=chunk.chunk_id,
        )
        candidate = EvidenceCandidate(
            request_id="req_gap",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id=chunk.source_id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            text_snippet=chunk.text,
            score=1.0,
        )

        result = apply_access_filter([candidate], repository)

        self.assertEqual(result.candidates, ())
        self.assertEqual(result.excluded_count, 1)
        self.assertEqual(result.errors[0].details["event_name"], "access_filter_failed_closed")
        self.assertIn(
            "access_filter_failed_closed",
            [log.details.get("event_name") for log in result.logs],
        )

    def test_apply_access_filter_respects_chunk_policy_stricter_than_source(self) -> None:
        repository = InMemoryStorageRepository()
        chunk = _add_source_bundle(
            repository,
            source_name="Public source restricted chunk",
            source_id_suffix="chunk_restricted",
            text="Chunk-only SECRET_CHUNK evidence should be filtered.",
        )
        repository.chunks[chunk.chunk_id] = ChunkRecord(
            document_id=chunk.document_id,
            source_id=chunk.source_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            access_policy_id="access:restricted",
            allowed_principals=["alice"],
            chunk_id=chunk.chunk_id,
        )
        candidate = EvidenceCandidate(
            request_id="req_chunk_policy",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id=chunk.source_id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            text_snippet=chunk.text,
            score=1.0,
        )

        result = apply_access_filter([candidate], repository, principal="bob")

        self.assertEqual(result.candidates, ())
        self.assertEqual(result.excluded_count, 1)
        self.assertNotIn("SECRET_CHUNK", [candidate.text_snippet for candidate in result.candidates])

    def test_merge_evidence_candidates_normalizes_and_dedupes_by_chunk_source(self) -> None:
        keyword = EvidenceCandidate(
            request_id="req_merge",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id="src_merge",
            document_id="doc_merge",
            chunk_id="chunk_merge",
            score=4.0,
            access_decision=AccessDecision.ALLOWED,
        )
        vector = EvidenceCandidate(
            request_id="req_merge",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id="src_merge",
            document_id="doc_merge",
            chunk_id="chunk_merge",
            score=0.7,
            access_decision=AccessDecision.ALLOWED,
        )

        merged = merge_evidence_candidates([keyword, vector])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].retrieval_mode, RetrievalMode.HYBRID)
        self.assertEqual(merged[0].normalized_score, 1.0)

    def test_hybrid_duplicate_does_not_overtake_stronger_single_mode_candidate(self) -> None:
        weaker_keyword_duplicate = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id="src_hybrid",
            document_id="doc_hybrid",
            chunk_id="chunk_hybrid",
            score=0.9,
            access_decision=AccessDecision.ALLOWED,
        )
        weaker_vector_duplicate = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id="src_hybrid",
            document_id="doc_hybrid",
            chunk_id="chunk_hybrid",
            score=0.9,
            access_decision=AccessDecision.ALLOWED,
        )
        stronger_vector = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id="src_vector",
            document_id="doc_vector",
            chunk_id="chunk_vector",
            score=0.96,
            access_decision=AccessDecision.ALLOWED,
        )
        vector_ceiling = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id="src_vector_ceiling",
            document_id="doc_vector_ceiling",
            chunk_id="chunk_vector_ceiling",
            score=1.0,
            access_decision=AccessDecision.ALLOWED,
        )
        vector_floor = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.VECTOR,
            source_id="src_floor",
            document_id="doc_floor",
            chunk_id="chunk_floor",
            score=0.0,
            access_decision=AccessDecision.ALLOWED,
        )
        keyword_ceiling = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id="src_keyword_ceiling",
            document_id="doc_keyword_ceiling",
            chunk_id="chunk_keyword_ceiling",
            score=0.95,
            access_decision=AccessDecision.ALLOWED,
        )
        keyword_floor = EvidenceCandidate(
            request_id="req_no_bonus",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id="src_keyword_floor",
            document_id="doc_keyword_floor",
            chunk_id="chunk_keyword_floor",
            score=0.0,
            access_decision=AccessDecision.ALLOWED,
        )

        merged = merge_evidence_candidates(
            [
                weaker_keyword_duplicate,
                weaker_vector_duplicate,
                stronger_vector,
                vector_ceiling,
                vector_floor,
                keyword_ceiling,
                keyword_floor,
            ]
        )
        chunk_order = [candidate.chunk_id for candidate in merged]

        self.assertLess(chunk_order.index("chunk_vector"), chunk_order.index("chunk_hybrid"))
        hybrid = next(candidate for candidate in merged if candidate.chunk_id == "chunk_hybrid")
        stronger = next(candidate for candidate in merged if candidate.chunk_id == "chunk_vector")
        self.assertEqual(hybrid.retrieval_mode, RetrievalMode.HYBRID)
        self.assertEqual(stronger.retrieval_mode, RetrievalMode.VECTOR)
        self.assertLess(hybrid.normalized_score, stronger.normalized_score)


if __name__ == "__main__":
    unittest.main()
