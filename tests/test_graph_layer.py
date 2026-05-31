import unittest

from enrichment import extract_graph_records
from planning import create_retrieval_request, run_planned_query
from shared import (
    AccessLevel,
    AccessMethod,
    ChunkRecord,
    DocumentRecord,
    EvidenceCandidate,
    LicensePolicy,
    ReliabilityLevel,
    RetrievalMode,
    QueryType,
    SourceType,
)
from source_registry import SourceRegistry
from storage import (
    InMemoryStorageRepository,
    commit_chunks,
    commit_document,
    commit_graph_records,
    commit_storage_bundle,
    verify_graph_storage,
)
from retrieval import merge_evidence_candidates, run_graph_retrieval


def _chunk_bundle(texts: tuple[str, ...]) -> tuple[InMemoryStorageRepository, tuple[ChunkRecord, ...]]:
    repository = InMemoryStorageRepository()
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Graph fixture",
        source_type=SourceType.DOCUMENT,
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.PUBLIC,
        license_policy=LicensePolicy.ALLOWED,
        reliability_level=ReliabilityLevel.HIGH,
    )
    document = DocumentRecord(
        source_id=source.source_id,
        title="Graph fixture",
        canonical_url="https://example.test/graph",
        access_level=AccessLevel.PUBLIC,
        access_policy_id=source.access_policy_id,
        document_id="doc_graph",
    )
    chunks = tuple(
        ChunkRecord(
            document_id=document.document_id,
            source_id=source.source_id,
            chunk_index=index,
            text=text,
            access_policy_id=source.access_policy_id,
            chunk_id=f"chunk_graph_{index}",
        )
        for index, text in enumerate(texts)
    )
    commit_document(repository, document, source=source)
    commit_chunks(repository, chunks)
    return repository, chunks


class GraphLayerTests(unittest.TestCase):
    def test_extract_graph_records_creates_deterministic_entities_with_provenance(self) -> None:
        _, chunks = _chunk_bundle(("A depends on B. B supports C.",))

        first = extract_graph_records(chunks)
        second = extract_graph_records(chunks)

        self.assertEqual([entity.entity_id for entity in first.entities], [entity.entity_id for entity in second.entities])
        self.assertEqual({entity.entity_name for entity in first.entities}, {"A", "B", "C"})
        self.assertTrue(all(entity.source_ids == [chunks[0].source_id] for entity in first.entities))
        self.assertTrue(all(entity.confidence is not None for entity in first.entities))
        self.assertIn("graph:entity:", " ".join(first.chunks[0].quality_flags))

    def test_extract_graph_records_creates_fixture_relations(self) -> None:
        _, chunks = _chunk_bundle(("A depends on B. B supports C. C updates D.",))

        result = extract_graph_records(chunks)
        relation_types = [relation.relation_type.value for relation in result.relations]

        self.assertEqual(relation_types, ["depends_on", "supports", "updates"])
        self.assertTrue(all(relation.evidence_chunk_ids == [chunks[0].chunk_id] for relation in result.relations))
        self.assertTrue(all(relation.confidence is not None for relation in result.relations))
        self.assertIn("graph:relation:", " ".join(result.chunks[0].quality_flags))

    def test_commit_and_verify_graph_records_indexes_entities_relations_and_chunks(self) -> None:
        repository, chunks = _chunk_bundle(("A depends on B.",))
        extraction = extract_graph_records(chunks)

        commit = commit_graph_records(
            repository,
            entities=extraction.entities,
            relations=extraction.relations,
            chunks=extraction.chunks,
        )
        verification = verify_graph_storage(repository, entities=extraction.entities, relations=extraction.relations)

        self.assertEqual(set(commit.entity_ids), {entity.entity_id for entity in extraction.entities})
        self.assertEqual(commit.relation_ids, tuple(relation.relation_id for relation in extraction.relations))
        self.assertTrue(verification.ok)
        self.assertEqual(verification.log.details["event_name"], "graph_verified")
        self.assertTrue(repository.entity_ids_by_alias["a"])
        self.assertTrue(repository.relation_ids_by_chunk_id[chunks[0].chunk_id])

    def test_entity_resolution_matches_aliases_for_graph_traversal(self) -> None:
        repository, chunks = _chunk_bundle(("Alpha Service depends on Beta API.",))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)

        result = run_graph_retrieval("How does Alpha Service connect?", repository)

        self.assertFalse(result.degraded)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].retrieval_mode, RetrievalMode.GRAPH)
        self.assertEqual(result.candidates[0].source_id, chunks[0].source_id)
        self.assertEqual(result.candidates[0].document_id, chunks[0].document_id)
        self.assertEqual(result.candidates[0].chunk_id, chunks[0].chunk_id)
        self.assertEqual(result.candidates[0].citation_link, "https://example.test/graph#chunk-0")
        self.assertTrue(result.candidates[0].entity_ids)
        self.assertTrue(result.candidates[0].relation_ids)

    def test_graph_traversal_can_return_multi_hop_candidates(self) -> None:
        repository, chunks = _chunk_bundle(("A depends on B.", "B supports C."))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)

        result = run_graph_retrieval("A", repository, max_depth=1, top_k=5)

        self.assertEqual({candidate.chunk_id for candidate in result.candidates}, {"chunk_graph_0", "chunk_graph_1"})
        self.assertIn("graph_traversal_completed", [log.details.get("event_name") for log in result.logs])

    def test_graph_entity_resolution_does_not_match_one_character_alias_inside_words(self) -> None:
        repository, chunks = _chunk_bundle(("A depends on B.",))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)

        result = run_graph_retrieval("relationship between catalog and payment", repository)

        self.assertTrue(result.degraded)
        self.assertEqual(result.candidates, ())

    def test_storage_bundle_can_optionally_commit_graph_records(self) -> None:
        repository = InMemoryStorageRepository()
        source_repository, chunks = _chunk_bundle(("Acme Retrieval Center depends on Hybrid Planner.",))
        source = next(iter(source_repository.sources.values()))
        document = next(iter(source_repository.documents.values()))

        commit_storage_bundle(repository, source=source, document=document, chunks=chunks, enrich_graph=True)
        verification = verify_graph_storage(repository)

        self.assertTrue(repository.entities)
        self.assertTrue(repository.relations)
        self.assertTrue(verification.ok)
        self.assertIn("graph_extraction_completed", [log.details.get("event_name") for log in repository.logs.values()])
        self.assertIn("graph_records_committed", [log.details.get("event_name") for log in repository.logs.values()])

    def test_verify_graph_storage_detects_corrupt_graph_indexes(self) -> None:
        repository, chunks = _chunk_bundle(("Acme Retrieval Center depends on Hybrid Planner.",))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)

        repository.entity_ids_by_alias.clear()
        repository.entity_ids_by_chunk_id.clear()
        repository.chunk_ids_by_entity_id.clear()
        repository.relation_ids_by_chunk_id.clear()
        repository.relation_ids_by_entity_id.clear()
        verification = verify_graph_storage(repository, entities=extraction.entities, relations=extraction.relations)

        self.assertFalse(verification.ok)
        self.assertTrue(verification.missing_entities)
        self.assertTrue(verification.missing_relations)

    def test_degraded_graph_extraction_handles_empty_chunks(self) -> None:
        repository, chunks = _chunk_bundle(("",))

        extraction = extract_graph_records(chunks)
        commit = commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)
        traversal = run_graph_retrieval("A", repository)

        self.assertEqual(extraction.entities, ())
        self.assertEqual(extraction.relations, ())
        self.assertEqual(extraction.skipped_chunk_ids, (chunks[0].chunk_id,))
        self.assertEqual(extraction.log.details["event_name"], "graph_extraction_skipped")
        self.assertEqual(commit.log.details["event_name"], "graph_commit_degraded")
        self.assertTrue(traversal.degraded)
        self.assertEqual(traversal.logs[0].details["event_name"], "graph_traversal_degraded")

    def test_graph_text_merge_preserves_entity_and_relation_ids(self) -> None:
        graph = EvidenceCandidate(
            request_id="req_graph_merge",
            retrieval_mode=RetrievalMode.GRAPH,
            source_id="src_merge",
            document_id="doc_merge",
            chunk_id="chunk_merge",
            entity_ids=["entity_a"],
            relation_ids=["rel_a_b"],
            score=0.8,
        )
        keyword = EvidenceCandidate(
            request_id="req_graph_merge",
            retrieval_mode=RetrievalMode.KEYWORD,
            source_id="src_merge",
            document_id="doc_merge",
            chunk_id="chunk_merge",
            score=10.0,
        )

        merged = merge_evidence_candidates([graph, keyword])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].retrieval_mode, RetrievalMode.HYBRID)
        self.assertEqual(merged[0].entity_ids, ["entity_a"])
        self.assertEqual(merged[0].relation_ids, ["rel_a_b"])

    def test_planned_graph_query_executes_graph_retrieval_full_flow(self) -> None:
        repository, chunks = _chunk_bundle(("Acme Retrieval Center depends on Hybrid Planner.",))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)
        request = create_retrieval_request(
            "How is Acme Retrieval Center connected?",
            constraints={"graph_required": True},
        )

        result = run_planned_query(request, repository, principal="reader")

        self.assertEqual(result.planning.plan.query_type, QueryType.GRAPH)
        self.assertEqual(result.executed_modes, (RetrievalMode.GRAPH,))
        self.assertIsNotNone(result.retrieval)
        assert result.retrieval is not None
        self.assertTrue(result.retrieval.candidates)
        self.assertTrue(all(candidate.retrieval_mode is RetrievalMode.GRAPH for candidate in result.retrieval.candidates))
        self.assertTrue(result.retrieval.candidates[0].entity_ids)
        self.assertTrue(result.retrieval.candidates[0].relation_ids)
        self.assertIsNotNone(result.ranking)
        self.assertIsNotNone(result.synthesis)
        self.assertIn("graph_traversal_completed", [log.details.get("event_name") for log in result.logs])

    def test_planned_graph_query_with_unmatched_alias_falls_back_without_unrelated_graph_evidence(self) -> None:
        repository, chunks = _chunk_bundle(("A depends on B.",))
        extraction = extract_graph_records(chunks)
        commit_graph_records(repository, entities=extraction.entities, relations=extraction.relations, chunks=extraction.chunks)
        request = create_retrieval_request(
            "relationship between catalog and payment",
            constraints={"graph_required": True},
        )

        result = run_planned_query(request, repository, principal="reader")

        self.assertEqual(result.planning.plan.query_type, QueryType.GRAPH)
        self.assertEqual(result.executed_modes, (RetrievalMode.GRAPH, RetrievalMode.HYBRID))
        self.assertIsNotNone(result.retrieval)
        assert result.retrieval is not None
        self.assertFalse(
            any(candidate.retrieval_mode is RetrievalMode.GRAPH for candidate in result.retrieval.candidates)
        )


if __name__ == "__main__":
    unittest.main()
