"""Neo4j-compatible graph backend adapter.

The adapter keeps Neo4j optional for local development by accepting an injected
client with an ``execute_query`` method. Production can pass a real driver, and
tests can use a small fake client with the same boundary.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable

from shared.records import ChunkRecord, EntityRecord, RelationRecord

from .adapters import (
    BackendAdapterConfig,
    BackendCapability,
    BackendHealthCheck,
    BackendOperationResult,
    BackendStatus,
    BackendType,
)
from .vector_runtime import _operation_result, _vector_backend_error


_CLIENT_UNSET = object()


class Neo4jGraphBackendAdapter:
    """Executable graph adapter for Neo4j-compatible clients."""

    def __init__(
        self,
        *,
        client: object | None = _CLIENT_UNSET,
        database: str | None = None,
        adapter_name: str = "neo4j_graph_runtime",
        priority: int = 5,
        uri_env: str = "NEO4J_URI",
        user_env: str = "NEO4J_USER",
        password_env: str = "NEO4J_PASSWORD",
        database_env: str = "NEO4J_DATABASE",
    ) -> None:
        resolved_database = database if database is not None else os.getenv(database_env) or "neo4j"
        self.client = _load_neo4j_client(uri_env, user_env, password_env) if client is _CLIENT_UNSET else client
        self.database = resolved_database
        self.config = BackendAdapterConfig(
            adapter_name=adapter_name,
            backend_type=BackendType.GRAPH,
            capabilities=(
                BackendCapability.READ,
                BackendCapability.WRITE,
                BackendCapability.GRAPH_TRAVERSAL,
                BackendCapability.ACCESS_FILTER,
                BackendCapability.HEALTH_CHECK,
            ),
            priority=priority,
            endpoint_reference=f"env://{uri_env}",
            fallback_adapter="in_memory_graph_index",
            connection_settings={
                "uri_env": uri_env,
                "user_env": user_env,
                "password_env": password_env,
                "database_env": database_env,
                "database": resolved_database,
            },
        )

    def to_config(self) -> BackendAdapterConfig:
        return self.config

    def health_check(
        self,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_neo4j_backend_health",
    ) -> BackendHealthCheck:
        started = time.perf_counter()
        required = tuple(dict.fromkeys(required_capabilities))
        missing = tuple(capability for capability in required if capability not in self.config.capabilities)
        details: dict[str, object] = {
            "database": self.database,
            "missing_capabilities": tuple(capability.value for capability in missing),
        }
        if self.client is None:
            error = _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message="neo4j client is unavailable",
                retryable=True,
                details={"database": self.database},
            )
            return BackendHealthCheck(
                adapter_name=self.config.adapter_name,
                backend_type=self.config.backend_type,
                status=BackendStatus.UNAVAILABLE,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="neo4j client is unavailable",
                checked_capabilities=required or self.config.capabilities,
                error=error,
                details=details,
            )

        try:
            _client_execute(self.client, "RETURN 1 AS ok", {}, database=self.database)
            details["reachable"] = True
            status = BackendStatus.DEGRADED if missing else BackendStatus.READY
            message = "missing required capabilities" if missing else "neo4j graph backend is reachable"
            error = None
            if missing:
                error = _graph_backend_error(
                    correlation_id=correlation_id,
                    operation_name="health_check",
                    message=message,
                    retryable=False,
                    details={"missing_capabilities": tuple(capability.value for capability in missing)},
                )
        except Exception as exc:
            status = BackendStatus.UNAVAILABLE
            message = str(exc)
            details["reachable"] = False
            error = _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=True,
                details={"database": self.database, "exception_type": type(exc).__name__},
            )

        return BackendHealthCheck(
            adapter_name=self.config.adapter_name,
            backend_type=self.config.backend_type,
            status=status,
            latency_ms=(time.perf_counter() - started) * 1000,
            message=message,
            checked_capabilities=required or self.config.capabilities,
            error=error,
            details=details,
        )

    def index_graph_records(
        self,
        *,
        entities: Iterable[EntityRecord] = (),
        relations: Iterable[RelationRecord] = (),
        chunks: Iterable[ChunkRecord] = (),
        correlation_id: str = "corr_neo4j_backend_index",
    ) -> BackendOperationResult:
        entity_payloads = tuple(_entity_payload(entity) for entity in entities)
        relation_payloads = tuple(_relation_payload(relation) for relation in relations)
        chunk_payloads = tuple(_chunk_payload(chunk) for chunk in chunks)
        health = self.health_check(required_capabilities=(BackendCapability.WRITE,), correlation_id=correlation_id)
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="index_graph_records",
                message="neo4j graph backend is unavailable",
                retryable=True,
                details={"database": self.database},
            )
            return _operation_result(self.config, "index_graph_records", False, correlation_id, health, error=error)
        if not entity_payloads and not relation_payloads:
            error = _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="index_graph_records",
                message="no graph records were provided",
                retryable=False,
                details={"entity_count": 0, "relation_count": 0},
            )
            return _operation_result(
                self.config,
                "index_graph_records",
                False,
                correlation_id,
                health,
                error=error,
                details={"entity_count": 0, "relation_count": 0, "chunk_count": len(chunk_payloads)},
            )

        try:
            _client_execute(
                self.client,
                _UPSERT_GRAPH_CYPHER,
                {"entities": entity_payloads, "relations": relation_payloads, "chunks": chunk_payloads},
                database=self.database,
            )
        except Exception as exc:
            error = _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="index_graph_records",
                message=str(exc),
                retryable=True,
                details={"database": self.database, "exception_type": type(exc).__name__},
            )
            return _operation_result(self.config, "index_graph_records", False, correlation_id, health, error=error)

        output_ids = [*(payload["entity_id"] for payload in entity_payloads), *(payload["relation_id"] for payload in relation_payloads)]
        return _operation_result(
            self.config,
            "index_graph_records",
            True,
            correlation_id,
            health,
            output_reference=",".join(output_ids) or None,
            details={
                "entity_count": len(entity_payloads),
                "relation_count": len(relation_payloads),
                "chunk_count": len(chunk_payloads),
                "entity_ids": tuple(payload["entity_id"] for payload in entity_payloads),
                "relation_ids": tuple(payload["relation_id"] for payload in relation_payloads),
            },
        )

    def traverse(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_depth: int = 1,
        correlation_id: str = "corr_neo4j_backend_traverse",
    ) -> BackendOperationResult:
        health = self.health_check(
            required_capabilities=(BackendCapability.READ, BackendCapability.GRAPH_TRAVERSAL),
            correlation_id=correlation_id,
        )
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="traverse",
                message="neo4j graph backend is unavailable",
                retryable=True,
                details={"database": self.database},
            )
            return _operation_result(self.config, "traverse", False, correlation_id, health, error=error)
        if not query.strip():
            return _operation_result(
                self.config,
                "traverse",
                True,
                correlation_id,
                health,
                details={"query": query, "top_k": top_k, "max_depth": max_depth, "candidate_count": 0, "candidates": ()},
            )

        try:
            raw_hits = _client_execute(
                self.client,
                _TRAVERSE_GRAPH_CYPHER,
                {
                    "query": _normalize_query(query),
                    "top_k": max(top_k, 0),
                    "max_depth": max(max_depth, 0),
                },
                database=self.database,
            )
        except Exception as exc:
            error = _graph_backend_error(
                correlation_id=correlation_id,
                operation_name="traverse",
                message=str(exc),
                retryable=True,
                details={"database": self.database, "exception_type": type(exc).__name__},
            )
            return _operation_result(self.config, "traverse", False, correlation_id, health, error=error)

        candidates = tuple(_hit_to_candidate(hit) for hit in raw_hits)
        return _operation_result(
            self.config,
            "traverse",
            True,
            correlation_id,
            health,
            output_reference=",".join(candidate["chunk_id"] for candidate in candidates if candidate.get("chunk_id")) or None,
            details={
                "query": query,
                "top_k": top_k,
                "max_depth": max_depth,
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
        )


_UPSERT_GRAPH_CYPHER = """
UNWIND $entities AS entity
MERGE (:GraphEntity {entity_id: entity.entity_id})
WITH count(*) AS _
UNWIND $chunks AS chunk
MERGE (:GraphChunk {chunk_id: chunk.chunk_id})
WITH count(*) AS _
UNWIND $relations AS relation
MERGE (:GraphRelation {relation_id: relation.relation_id})
RETURN count(*) AS indexed
"""

_TRAVERSE_GRAPH_CYPHER = """
MATCH (entity:GraphEntity)
WHERE entity.normalized_name CONTAINS $query
RETURN entity
LIMIT $top_k
"""


def _load_neo4j_client(uri_env: str, user_env: str, password_env: str) -> object | None:
    uri = os.getenv(uri_env)
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase  # type: ignore
    except Exception:
        return None
    user = os.getenv(user_env)
    password = os.getenv(password_env)
    auth = (user, password) if user and password else None
    return GraphDatabase.driver(uri, auth=auth)


def _client_execute(client: object | None, query: str, parameters: dict[str, object], *, database: str) -> tuple[object, ...]:
    if client is None:
        raise RuntimeError("neo4j client is unavailable")
    if hasattr(client, "execute_query"):
        result = client.execute_query(query, parameters, database_=database)
        if isinstance(result, tuple):
            return tuple(result[0])
        return tuple(result)
    if hasattr(client, "session"):
        with client.session(database=database) as session:
            return tuple(session.run(query, parameters))
    raise RuntimeError("neo4j client does not expose execute_query or session")


def _entity_payload(entity: EntityRecord) -> dict[str, object]:
    return {
        "entity_id": entity.entity_id,
        "entity_name": entity.entity_name,
        "normalized_name": _normalize_query(entity.entity_name),
        "entity_type": entity.entity_type.value,
        "aliases": tuple(entity.aliases),
        "normalized_aliases": tuple(_normalize_query(alias) for alias in entity.aliases),
        "source_ids": tuple(entity.source_ids),
        "confidence": entity.confidence,
    }


def _relation_payload(relation: RelationRecord) -> dict[str, object]:
    return {
        "relation_id": relation.relation_id,
        "subject_entity_id": relation.subject_entity_id,
        "object_entity_id": relation.object_entity_id,
        "relation_type": relation.relation_type.value,
        "evidence_chunk_ids": tuple(relation.evidence_chunk_ids),
        "confidence": relation.confidence,
    }


def _chunk_payload(chunk: ChunkRecord) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "source_id": chunk.source_id,
        "access_policy_id": chunk.access_policy_id,
        "allowed_principals": tuple(chunk.allowed_principals),
        "quality_flags": tuple(chunk.quality_flags),
    }


def _hit_to_candidate(hit: object) -> dict[str, object]:
    data = dict(hit) if isinstance(hit, dict) else dict(getattr(hit, "data", lambda: {})())
    return {
        "chunk_id": data.get("chunk_id"),
        "score": round(float(data.get("score") or 0.0), 6),
        "entity_ids": tuple(data.get("entity_ids", ())),
        "relation_ids": tuple(data.get("relation_ids", ())),
        "source_id": data.get("source_id"),
        "document_id": data.get("document_id"),
        "access_policy_id": data.get("access_policy_id"),
        "allowed_principals": tuple(data.get("allowed_principals", ())),
    }


def _normalize_query(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _graph_backend_error(
    *,
    correlation_id: str,
    operation_name: str,
    message: str,
    retryable: bool,
    details: dict[str, object],
):
    return _vector_backend_error(
        correlation_id=correlation_id,
        operation_name=operation_name,
        message=message,
        retryable=retryable,
        details=details,
    )


__all__ = ["Neo4jGraphBackendAdapter"]
