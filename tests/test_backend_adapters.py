from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace

from ingestion import NormalizedDocument, RawArtifact, create_document_record, split_document_into_chunks
from enrichment import extract_graph_records
from storage import (
    BackendAdapterConfig,
    BackendAdapterRegistry,
    BackendCapability,
    BackendHealthCheck,
    BackendStatus,
    BackendType,
    DurableStorageRepository,
    InMemoryStorageRepository,
    InMemoryVectorBackendAdapter,
    LocalDurableStorageBackendAdapter,
    Neo4jGraphBackendAdapter,
    QdrantVectorBackendAdapter,
    create_local_backend_registry,
    validate_backend_plan,
)
from shared import AccessLevel, AccessMethod, DocumentType, LicensePolicy, SourceType
from source_registry import SourceRegistry


def _source_bundle() -> tuple[object, RawArtifact, object, tuple[object, ...]]:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Backend adapter source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.INTERNAL,
        allowed_principals=["role:analyst"],
        license_policy=LicensePolicy.ALLOWED,
    )
    raw_artifact = RawArtifact(
        source_id=source.source_id,
        content_bytes=b"# Backend\nAdapter Runtime supports Governed Source. Adapter runtime persists governed source data.",
        location="memory://backend.md",
        content_type="text/markdown",
    )
    normalized = NormalizedDocument(
        source_id=source.source_id,
        text=raw_artifact.text,
        title="Backend adapter source",
        document_type=DocumentType.MARKDOWN,
    )
    document = create_document_record(source, normalized, raw_artifact)
    chunks = split_document_into_chunks(normalized, document, source=source, max_chars=160)
    return source, raw_artifact, document, chunks


class FakeQdrantClient:
    def __init__(self, *, fail_health: bool = False, fail_upsert: bool = False) -> None:
        self.fail_health = fail_health
        self.fail_upsert = fail_upsert
        self.points: list[dict[str, object]] = []

    def count(self, *, collection_name: str) -> dict[str, int]:
        if self.fail_health:
            raise RuntimeError(f"{collection_name} unavailable")
        return {"count": len(self.points)}

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        if self.fail_upsert:
            raise RuntimeError(f"{collection_name} upsert failed")
        self.points.extend(points)

    def search(
        self,
        *,
        collection_name: str,
        query_vector: tuple[float, ...],
        limit: int,
        with_payload: bool,
        with_vectors: bool,
    ) -> tuple[SimpleNamespace, ...]:
        del collection_name, with_payload, with_vectors
        scored = []
        for point in self.points:
            vector = point["vector"]
            score = sum(left * right for left, right in zip(query_vector, vector))
            scored.append(SimpleNamespace(score=score, payload=point["payload"]))
        return tuple(sorted(scored, key=lambda item: -item.score)[:limit])


class FakeNeo4jClient:
    def __init__(self, *, fail_health: bool = False, fail_write: bool = False) -> None:
        self.fail_health = fail_health
        self.fail_write = fail_write
        self.entities: dict[str, dict[str, object]] = {}
        self.relations: dict[str, dict[str, object]] = {}
        self.chunks: dict[str, dict[str, object]] = {}

    def execute_query(
        self,
        query: str,
        parameters: dict[str, object],
        *,
        database_: str,
    ) -> tuple[list[dict[str, object]], None, None]:
        del database_
        if "RETURN 1 AS ok" in query:
            if self.fail_health:
                raise RuntimeError("neo4j unavailable")
            return ([{"ok": 1}], None, None)
        if "UNWIND $entities" in query:
            if self.fail_write:
                raise RuntimeError("graph write failed")
            self.entities.update({entity["entity_id"]: dict(entity) for entity in parameters["entities"]})
            self.relations.update({relation["relation_id"]: dict(relation) for relation in parameters["relations"]})
            self.chunks.update({chunk["chunk_id"]: dict(chunk) for chunk in parameters["chunks"]})
            return ([{"indexed": len(self.entities) + len(self.relations)}], None, None)
        query_text = parameters["query"]
        matches = []
        for relation in self.relations.values():
            subject = self.entities[relation["subject_entity_id"]]
            object_ = self.entities[relation["object_entity_id"]]
            aliases = (
                subject["normalized_name"],
                *subject["normalized_aliases"],
                object_["normalized_name"],
                *object_["normalized_aliases"],
            )
            if not any(query_text in alias for alias in aliases):
                continue
            for chunk_id in relation["evidence_chunk_ids"]:
                chunk = self.chunks[chunk_id]
                matches.append(
                    {
                        "chunk_id": chunk_id,
                        "score": relation["confidence"] or 0.5,
                        "entity_ids": (relation["subject_entity_id"], relation["object_entity_id"]),
                        "relation_ids": (relation["relation_id"],),
                        "source_id": chunk["source_id"],
                        "document_id": chunk["document_id"],
                        "access_policy_id": chunk["access_policy_id"],
                        "allowed_principals": chunk["allowed_principals"],
                    }
                )
        return (matches[: parameters["top_k"]], None, None)


class BackendAdapterTests(unittest.TestCase):
    def test_local_backend_registry_satisfies_dependency_free_baseline_plan(self) -> None:
        registry = create_local_backend_registry()

        selections = validate_backend_plan(
            registry,
            {
                BackendType.METADATA: (BackendCapability.READ, BackendCapability.WRITE, BackendCapability.SNAPSHOT),
                BackendType.RAW_SOURCE: (BackendCapability.READ, BackendCapability.WRITE),
                BackendType.TELEMETRY: (BackendCapability.APPEND_ONLY,),
                BackendType.VECTOR: (BackendCapability.VECTOR_SEARCH, BackendCapability.ACCESS_FILTER),
                BackendType.GRAPH: (BackendCapability.GRAPH_TRAVERSAL, BackendCapability.ACCESS_FILTER),
            },
        )

        self.assertTrue(all(selection.ok for selection in selections))
        self.assertEqual(
            [selection.primary.adapter_name for selection in selections if selection.primary],
            [
                "local_json_metadata",
                "local_raw_snapshot",
                "local_jsonl_telemetry",
                "in_memory_vector_index",
                "in_memory_graph_index",
            ],
        )

    def test_backend_selection_reports_missing_capabilities_with_error_envelope(self) -> None:
        registry = BackendAdapterRegistry(
            [
                BackendAdapterConfig(
                    adapter_name="metadata_without_transactions",
                    backend_type=BackendType.METADATA,
                    capabilities=(BackendCapability.READ, BackendCapability.WRITE),
                )
            ]
        )

        selection = registry.select(
            BackendType.METADATA,
            required_capabilities=(BackendCapability.READ, BackendCapability.TRANSACTIONAL_WRITE),
            correlation_id="corr_missing_capability",
        )

        self.assertFalse(selection.ok)
        self.assertIsNone(selection.primary)
        self.assertEqual(selection.missing_capabilities, (BackendCapability.TRANSACTIONAL_WRITE,))
        self.assertIsNotNone(selection.error)
        self.assertEqual(selection.error.correlation_id, "corr_missing_capability")
        self.assertEqual(selection.error.details["missing_capabilities"], ("transactional_write",))

    def test_unavailable_primary_is_skipped_for_healthy_fallback_candidate(self) -> None:
        registry = BackendAdapterRegistry(
            [
                BackendAdapterConfig(
                    adapter_name="neo4j_graph",
                    backend_type=BackendType.GRAPH,
                    capabilities=(BackendCapability.READ, BackendCapability.WRITE, BackendCapability.GRAPH_TRAVERSAL),
                    priority=5,
                    fallback_adapter="local_graph",
                ),
                BackendAdapterConfig(
                    adapter_name="local_graph",
                    backend_type=BackendType.GRAPH,
                    capabilities=(BackendCapability.READ, BackendCapability.WRITE, BackendCapability.GRAPH_TRAVERSAL),
                    priority=10,
                ),
            ]
        )
        registry.record_health(
            BackendHealthCheck(
                adapter_name="neo4j_graph",
                backend_type=BackendType.GRAPH,
                status=BackendStatus.UNAVAILABLE,
            )
        )
        registry.record_health(
            BackendHealthCheck(
                adapter_name="local_graph",
                backend_type=BackendType.GRAPH,
                status=BackendStatus.READY,
            )
        )

        selection = registry.select(
            BackendType.GRAPH,
            required_capabilities=(BackendCapability.GRAPH_TRAVERSAL,),
        )

        self.assertTrue(selection.ok)
        self.assertEqual(selection.primary.adapter_name, "local_graph")
        self.assertIsNone(selection.fallback)

    def test_adapter_summary_serializes_enums_without_mutating_connection_settings(self) -> None:
        adapter = BackendAdapterConfig(
            adapter_name="qdrant_vector",
            backend_type=BackendType.VECTOR,
            capabilities=(BackendCapability.READ, BackendCapability.VECTOR_SEARCH),
            endpoint_reference="env://QDRANT_URL",
            connection_settings={
                "api_key_env": "QDRANT_API_KEY",
                "collection": "evidence",
                "password": "do-not-serialize",
            },
        )
        registry = BackendAdapterRegistry([adapter])

        summary = registry.to_dict()

        self.assertEqual(summary["adapters"][0]["backend_type"], "vector")
        self.assertEqual(summary["adapters"][0]["capabilities"], ("read", "vector_search"))
        self.assertEqual(summary["adapters"][0]["connection_settings"]["password"], "<redacted>")
        self.assertEqual(adapter.connection_settings["api_key_env"], "QDRANT_API_KEY")
        self.assertEqual(adapter.connection_settings["password"], "do-not-serialize")
        self.assertNotIn("do-not-serialize", str(summary))

    def test_local_durable_backend_adapter_executes_health_and_recovery_commit(self) -> None:
        source, raw_artifact, document, chunks = _source_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            adapter = LocalDurableStorageBackendAdapter(temporary)
            registry = BackendAdapterRegistry([adapter.to_config()])
            registry.record_health(
                adapter.health_check(
                    required_capabilities=(BackendCapability.WRITE, BackendCapability.TRANSACTIONAL_WRITE),
                    correlation_id="corr_adapter_health",
                )
            )

            selection = registry.select(
                BackendType.METADATA,
                required_capabilities=(BackendCapability.WRITE, BackendCapability.TRANSACTIONAL_WRITE),
            )
            result = adapter.commit_storage_bundle(
                raw_artifact=raw_artifact,
                source=source,
                document=document,
                chunks=chunks,
                correlation_id="corr_adapter_commit",
            )
            recovered = DurableStorageRepository(temporary)

        self.assertTrue(selection.ok)
        self.assertTrue(result.ok)
        self.assertEqual(result.details["attempts"], 1)
        self.assertIn(raw_artifact.raw_artifact_id, recovered.raw_artifacts)
        self.assertIn(source.source_id, recovered.sources)
        self.assertIn(document.document_id, recovered.documents)
        self.assertIn(chunks[0].chunk_id, recovered.chunks)
        self.assertEqual(recovered.chunks[chunks[0].chunk_id].allowed_principals, ["role:analyst"])
        self.assertEqual(result.to_dict()["backend_type"], "metadata")

    def test_in_memory_vector_backend_adapter_indexes_and_searches_without_text_leakage(self) -> None:
        source, _raw_artifact, document, chunks = _source_bundle()
        repository = InMemoryStorageRepository()
        repository.save_source(source)
        repository.save_document(document)
        for chunk in chunks:
            repository.save_chunk(chunk)
        adapter = InMemoryVectorBackendAdapter(repository)
        registry = BackendAdapterRegistry([adapter.to_config()])
        registry.record_health(
            adapter.health_check(
                required_capabilities=(BackendCapability.READ, BackendCapability.WRITE, BackendCapability.VECTOR_SEARCH),
                correlation_id="corr_vector_health",
            )
        )

        selection = registry.select(
            BackendType.VECTOR,
            required_capabilities=(BackendCapability.VECTOR_SEARCH, BackendCapability.ACCESS_FILTER),
        )
        index_result = adapter.index_chunks(chunks, correlation_id="corr_vector_index")
        search_result = adapter.search("adapter runtime governed source data", top_k=2, correlation_id="corr_vector_search")

        self.assertTrue(selection.ok)
        self.assertTrue(index_result.ok)
        self.assertEqual(index_result.details["embedding_count"], len(chunks))
        self.assertTrue(search_result.ok)
        self.assertEqual(search_result.details["candidate_count"], 1)
        self.assertEqual(search_result.details["candidates"][0]["chunk_id"], chunks[0].chunk_id)
        self.assertNotIn("text", search_result.details["candidates"][0])
        self.assertEqual(repository.chunks[chunks[0].chunk_id].allowed_principals, ["role:analyst"])
        self.assertIn("adapter", search_result.to_dict()["details"]["candidates"][0]["matched_terms"])
        self.assertIn("runtime", search_result.to_dict()["details"]["candidates"][0]["matched_terms"])

    def test_in_memory_vector_backend_adapter_reports_empty_index_failures(self) -> None:
        adapter = InMemoryVectorBackendAdapter(InMemoryStorageRepository())
        blank_chunk = _source_bundle()[3][0].__class__(
            document_id="doc_blank",
            source_id="src_blank",
            chunk_index=0,
            text="   ",
            access_policy_id="access:public",
        )

        result = adapter.index_chunks((blank_chunk,), correlation_id="corr_vector_empty")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.details["skipped_chunk_ids"], (blank_chunk.chunk_id,))

    def test_qdrant_vector_backend_adapter_indexes_and_searches_governed_payloads(self) -> None:
        _source, _raw_artifact, _document, chunks = _source_bundle()
        client = FakeQdrantClient()
        adapter = QdrantVectorBackendAdapter(client=client, collection_name="evidence_test")
        registry = BackendAdapterRegistry([adapter.to_config()])
        registry.record_health(
            adapter.health_check(
                required_capabilities=(BackendCapability.READ, BackendCapability.WRITE, BackendCapability.VECTOR_SEARCH),
                correlation_id="corr_qdrant_health",
            )
        )

        selection = registry.select(
            BackendType.VECTOR,
            required_capabilities=(BackendCapability.VECTOR_SEARCH, BackendCapability.ACCESS_FILTER),
        )
        index_result = adapter.index_chunks(chunks, correlation_id="corr_qdrant_index")
        search_result = adapter.search("adapter runtime governed source data", top_k=2, correlation_id="corr_qdrant_search")

        self.assertTrue(selection.ok)
        self.assertTrue(index_result.ok)
        self.assertEqual(index_result.details["point_count"], len(chunks))
        self.assertTrue(search_result.ok)
        self.assertEqual(search_result.details["candidate_count"], 1)
        candidate = search_result.details["candidates"][0]
        self.assertEqual(candidate["chunk_id"], chunks[0].chunk_id)
        self.assertEqual(candidate["allowed_principals"], ("role:analyst",))
        self.assertIn("adapter", candidate["matched_terms"])
        self.assertNotIn("text", candidate)
        self.assertEqual(adapter.to_config().fallback_adapter, "in_memory_vector_index")

    def test_qdrant_vector_backend_adapter_reports_unavailable_client_without_secret_leakage(self) -> None:
        adapter = QdrantVectorBackendAdapter(client=None, collection_name="evidence_test")

        health = adapter.health_check(correlation_id="corr_qdrant_missing")
        summary = adapter.to_config().to_dict()

        self.assertEqual(health.status, BackendStatus.UNAVAILABLE)
        self.assertIsNotNone(health.error)
        self.assertEqual(summary["connection_settings"]["api_key_env"], "QDRANT_API_KEY")
        self.assertNotIn("api_key", str(health.details).lower())

    def test_qdrant_vector_backend_adapter_surfaces_write_failure_as_operation_error(self) -> None:
        _source, _raw_artifact, _document, chunks = _source_bundle()
        adapter = QdrantVectorBackendAdapter(client=FakeQdrantClient(fail_upsert=True), collection_name="evidence_test")

        result = adapter.index_chunks(chunks, correlation_id="corr_qdrant_write_failed")

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.details["collection_name"], "evidence_test")

    def test_neo4j_graph_backend_adapter_indexes_and_traverses_governed_payloads(self) -> None:
        _source, _raw_artifact, _document, chunks = _source_bundle()
        extraction = extract_graph_records(chunks, correlation_id="corr_graph_extract")
        client = FakeNeo4jClient()
        adapter = Neo4jGraphBackendAdapter(client=client, database="evidence")
        registry = BackendAdapterRegistry([adapter.to_config()])
        registry.record_health(
            adapter.health_check(
                required_capabilities=(BackendCapability.READ, BackendCapability.WRITE, BackendCapability.GRAPH_TRAVERSAL),
                correlation_id="corr_neo4j_health",
            )
        )

        selection = registry.select(
            BackendType.GRAPH,
            required_capabilities=(BackendCapability.GRAPH_TRAVERSAL, BackendCapability.ACCESS_FILTER),
        )
        index_result = adapter.index_graph_records(
            entities=extraction.entities,
            relations=extraction.relations,
            chunks=extraction.chunks,
            correlation_id="corr_neo4j_index",
        )
        traverse_result = adapter.traverse("Adapter Runtime", top_k=2, correlation_id="corr_neo4j_traverse")

        self.assertTrue(selection.ok)
        self.assertTrue(index_result.ok)
        self.assertGreater(index_result.details["entity_count"], 0)
        self.assertTrue(traverse_result.ok)
        self.assertEqual(traverse_result.details["candidate_count"], 1)
        candidate = traverse_result.details["candidates"][0]
        self.assertEqual(candidate["chunk_id"], chunks[0].chunk_id)
        self.assertEqual(candidate["allowed_principals"], ("role:analyst",))
        self.assertNotIn("text", candidate)
        self.assertEqual(adapter.to_config().fallback_adapter, "in_memory_graph_index")

    def test_neo4j_graph_backend_adapter_reports_unavailable_client_without_secret_leakage(self) -> None:
        adapter = Neo4jGraphBackendAdapter(client=None, database="evidence")

        health = adapter.health_check(correlation_id="corr_neo4j_missing")
        summary = adapter.to_config().to_dict()

        self.assertEqual(health.status, BackendStatus.UNAVAILABLE)
        self.assertIsNotNone(health.error)
        self.assertEqual(summary["connection_settings"]["password_env"], "NEO4J_PASSWORD")
        self.assertNotIn("password", str(health.details).lower())

    def test_neo4j_graph_backend_adapter_surfaces_write_failure_as_operation_error(self) -> None:
        _source, _raw_artifact, _document, chunks = _source_bundle()
        extraction = extract_graph_records(chunks, correlation_id="corr_graph_extract")
        adapter = Neo4jGraphBackendAdapter(client=FakeNeo4jClient(fail_write=True), database="evidence")

        result = adapter.index_graph_records(
            entities=extraction.entities,
            relations=extraction.relations,
            chunks=extraction.chunks,
            correlation_id="corr_neo4j_write_failed",
        )

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.details["database"], "evidence")


if __name__ == "__main__":
    unittest.main()
