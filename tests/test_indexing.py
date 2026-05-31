import unittest

from shared import ChunkRecord
from storage import InMemoryStorageRepository, commit_chunks
from retrieval import (
    InMemoryKeywordIndex,
    InMemoryVectorIndex,
    commit_sparse_index,
    commit_vectors,
    extract_sparse_terms,
    generate_embeddings,
    keyword_index_from_repository,
    run_keyword_search,
    run_vector_search,
    vector_index_from_repository,
)


def _chunk(index: int, text: str) -> ChunkRecord:
    return ChunkRecord(
        document_id="doc_indexing",
        source_id="src_indexing",
        chunk_index=index,
        text=text,
        access_policy_id="access:public",
        chunk_id=f"chunk_indexing_{index}",
    )


class IndexingTests(unittest.TestCase):
    def test_generate_embeddings_creates_embedding_for_each_valid_chunk(self) -> None:
        chunks = [
            _chunk(0, "Graph retrieval uses semantic chunk evidence."),
            _chunk(1, "Keyword indexing keeps exact identifiers."),
        ]

        embeddings = generate_embeddings(chunks)

        self.assertEqual(len(embeddings), 2)
        self.assertEqual({embedding.chunk_id for embedding in embeddings}, {chunk.chunk_id for chunk in chunks})
        self.assertTrue(all(embedding.embedding_id.startswith("emb_") for embedding in embeddings))
        self.assertTrue(all(len(embedding.vector) == 32 for embedding in embeddings))

    def test_extract_sparse_terms_preserves_exact_identifiers_and_quoted_phrases(self) -> None:
        chunk = _chunk(
            0,
            'GraphRAG_v2 resolves RFC-3986 links for API_KEY_42 and "quoted phrase".',
        )

        sparse = extract_sparse_terms(chunk)

        self.assertIsNotNone(sparse)
        assert sparse is not None
        self.assertIn("GraphRAG_v2", sparse.terms)
        self.assertIn("RFC-3986", sparse.terms)
        self.assertIn("API_KEY_42", sparse.terms)
        self.assertIn("quoted phrase", sparse.terms)

    def test_commit_vectors_links_embedding_id_to_chunk_id(self) -> None:
        repository = InMemoryStorageRepository()
        chunks = [_chunk(0, "Vector retrieval finds semantic graph evidence.")]
        commit_chunks(repository, chunks)

        result = commit_vectors(repository, chunks)
        updated = result.chunks[0]
        embedding = repository.vector_embeddings[updated.embedding_id]

        self.assertEqual(updated.chunk_id, chunks[0].chunk_id)
        self.assertEqual(embedding.chunk_id, chunks[0].chunk_id)
        self.assertEqual(repository.chunks[chunks[0].chunk_id].embedding_id, updated.embedding_id)
        self.assertEqual(result.log.details["event_name"], "vectors_committed")

    def test_commit_sparse_index_links_terms_to_chunk_id(self) -> None:
        repository = InMemoryStorageRepository()
        keyword_index = InMemoryKeywordIndex()
        chunks = [_chunk(0, "Exact identifier API_KEY_42 belongs in sparse index.")]
        commit_chunks(repository, chunks)

        result = commit_sparse_index(repository, chunks, keyword_index=keyword_index)
        updated = result.chunks[0]
        sparse = repository.sparse_terms[updated.sparse_terms_id]

        self.assertEqual(sparse.chunk_id, chunks[0].chunk_id)
        self.assertIn("API_KEY_42", keyword_index.chunk_ids_by_term)
        self.assertIn(chunks[0].chunk_id, keyword_index.chunk_ids_by_term["API_KEY_42"])
        self.assertEqual(repository.chunks[chunks[0].chunk_id].sparse_terms_id, updated.sparse_terms_id)
        self.assertEqual(result.log.details["event_name"], "sparse_index_committed")

    def test_index_commits_preserve_existing_chunk_pointers_when_called_with_original_chunk(self) -> None:
        sparse_first_repository = InMemoryStorageRepository()
        sparse_first_chunk = _chunk(0, "GraphRAG_v2 keeps exact sparse and vector pointers.")
        commit_chunks(sparse_first_repository, [sparse_first_chunk])

        sparse_first_sparse = commit_sparse_index(sparse_first_repository, [sparse_first_chunk]).chunks[0]
        sparse_first_vector = commit_vectors(sparse_first_repository, [sparse_first_chunk]).chunks[0]
        sparse_first_stored = sparse_first_repository.chunks[sparse_first_chunk.chunk_id]

        self.assertEqual(sparse_first_stored.sparse_terms_id, sparse_first_sparse.sparse_terms_id)
        self.assertEqual(sparse_first_stored.embedding_id, sparse_first_vector.embedding_id)

        vector_first_repository = InMemoryStorageRepository()
        vector_first_chunk = _chunk(1, "API_KEY_42 keeps vector and sparse index pointers.")
        commit_chunks(vector_first_repository, [vector_first_chunk])

        vector_first_vector = commit_vectors(vector_first_repository, [vector_first_chunk]).chunks[0]
        vector_first_sparse = commit_sparse_index(vector_first_repository, [vector_first_chunk]).chunks[0]
        vector_first_stored = vector_first_repository.chunks[vector_first_chunk.chunk_id]

        self.assertEqual(vector_first_stored.embedding_id, vector_first_vector.embedding_id)
        self.assertEqual(vector_first_stored.sparse_terms_id, vector_first_sparse.sparse_terms_id)

    def test_run_vector_search_returns_semantic_candidates(self) -> None:
        vector_index = InMemoryVectorIndex()
        chunks = [
            _chunk(0, "Graph retrieval ranks semantic evidence from chunk vectors."),
            _chunk(1, "Release notes describe billing export formats."),
        ]
        for updated in commit_vectors(InMemoryStorageRepository(), chunks, vector_index=vector_index).chunks:
            self.assertIsNotNone(updated.embedding_id)

        candidates = run_vector_search("semantic graph evidence", vector_index, top_k=1)

        self.assertEqual(candidates[0].chunk_id, chunks[0].chunk_id)
        self.assertGreater(candidates[0].score, 0)

    def test_run_keyword_search_returns_exact_phrase_candidates(self) -> None:
        keyword_index = InMemoryKeywordIndex()
        chunks = [
            _chunk(0, 'The source contains "quoted phrase" and API_KEY_42.'),
            _chunk(1, "The source contains approximate phrase and API key guidance."),
        ]
        commit_sparse_index(InMemoryStorageRepository(), chunks, keyword_index=keyword_index)

        phrase_candidates = run_keyword_search('"quoted phrase"', keyword_index, top_k=1)
        identifier_candidates = run_keyword_search("API_KEY_42", keyword_index, top_k=1)

        self.assertEqual(phrase_candidates[0].chunk_id, chunks[0].chunk_id)
        self.assertIn("quoted phrase", phrase_candidates[0].matched_terms)
        self.assertEqual(identifier_candidates[0].chunk_id, chunks[0].chunk_id)
        self.assertIn("API_KEY_42", identifier_candidates[0].matched_terms)

    def test_run_keyword_search_matches_unquoted_exact_phrase(self) -> None:
        keyword_index = InMemoryKeywordIndex()
        chunks = [
            _chunk(0, "The graph retrieval pipeline keeps citations attached."),
            _chunk(1, "The graph planner uses retrieval only later."),
        ]
        commit_sparse_index(InMemoryStorageRepository(), chunks, keyword_index=keyword_index)

        candidates = run_keyword_search("graph retrieval pipeline", keyword_index, top_k=1)

        self.assertEqual(candidates[0].chunk_id, chunks[0].chunk_id)
        self.assertIn("graph retrieval pipeline", candidates[0].matched_terms)

    def test_empty_chunk_degrades_index_commits_without_candidates(self) -> None:
        repository = InMemoryStorageRepository()
        empty = _chunk(0, "   ")
        commit_chunks(repository, [empty])

        vector_result = commit_vectors(repository, [empty])
        sparse_result = commit_sparse_index(repository, [empty])

        self.assertEqual(vector_result.chunks, ())
        self.assertEqual(sparse_result.chunks, ())
        self.assertEqual(vector_result.skipped_chunk_ids, (empty.chunk_id,))
        self.assertEqual(sparse_result.skipped_chunk_ids, (empty.chunk_id,))
        self.assertEqual(vector_result.log.details["event_name"], "vectors_degraded")
        self.assertEqual(sparse_result.log.details["event_name"], "sparse_index_degraded")
        self.assertEqual(run_vector_search("anything", vector_index_from_repository(repository)), ())
        self.assertEqual(run_keyword_search("anything", keyword_index_from_repository(repository)), ())


if __name__ == "__main__":
    unittest.main()
