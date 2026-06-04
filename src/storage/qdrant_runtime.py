"""Qdrant-compatible vector backend adapter.

The adapter is dependency-optional: production code can inject a real
qdrant-client instance, while tests can use a tiny fake with the same methods.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable

from shared.records import ChunkRecord

from retrieval.indexing import VECTOR_DIMENSIONS, generate_embedding

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


class QdrantVectorBackendAdapter:
    """Executable vector adapter for Qdrant-compatible clients."""

    def __init__(
        self,
        *,
        client: object | None = _CLIENT_UNSET,
        collection_name: str | None = None,
        adapter_name: str = "qdrant_vector_runtime",
        priority: int = 5,
        url_env: str = "QDRANT_URL",
        api_key_env: str = "QDRANT_API_KEY",
        collection_env: str = "QDRANT_COLLECTION",
        vector_size: int = VECTOR_DIMENSIONS,
    ) -> None:
        resolved_collection_name = collection_name if collection_name is not None else os.getenv(collection_env) or "evidence_chunks"
        self.client = _load_qdrant_client(url_env, api_key_env) if client is _CLIENT_UNSET else client
        self.collection_name = resolved_collection_name
        self.vector_size = vector_size
        self.config = BackendAdapterConfig(
            adapter_name=adapter_name,
            backend_type=BackendType.VECTOR,
            capabilities=(
                BackendCapability.READ,
                BackendCapability.WRITE,
                BackendCapability.VECTOR_SEARCH,
                BackendCapability.ACCESS_FILTER,
                BackendCapability.HEALTH_CHECK,
            ),
            priority=priority,
            endpoint_reference=f"env://{url_env}",
            fallback_adapter="in_memory_vector_index",
            connection_settings={
                "url_env": url_env,
                "api_key_env": api_key_env,
                "collection_env": collection_env,
                "collection_name": resolved_collection_name,
                "vector_size": vector_size,
            },
        )

    def to_config(self) -> BackendAdapterConfig:
        return self.config

    def health_check(
        self,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_qdrant_backend_health",
    ) -> BackendHealthCheck:
        started = time.perf_counter()
        required = tuple(dict.fromkeys(required_capabilities))
        missing = tuple(capability for capability in required if capability not in self.config.capabilities)
        details: dict[str, object] = {
            "collection_name": self.collection_name,
            "missing_capabilities": tuple(capability.value for capability in missing),
        }
        if self.client is None:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message="qdrant client is unavailable",
                retryable=True,
                details={"collection_name": self.collection_name},
            )
            return BackendHealthCheck(
                adapter_name=self.config.adapter_name,
                backend_type=self.config.backend_type,
                status=BackendStatus.UNAVAILABLE,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="qdrant client is unavailable",
                checked_capabilities=required or self.config.capabilities,
                error=error,
                details=details,
            )

        try:
            details["point_count"] = _client_count(self.client, self.collection_name)
            status = BackendStatus.DEGRADED if missing else BackendStatus.READY
            message = "missing required capabilities" if missing else "qdrant vector backend is reachable"
            error = None
            if missing:
                error = _vector_backend_error(
                    correlation_id=correlation_id,
                    operation_name="health_check",
                    message=message,
                    retryable=False,
                    details={"missing_capabilities": tuple(capability.value for capability in missing)},
                )
        except Exception as exc:
            status = BackendStatus.UNAVAILABLE
            message = str(exc)
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=True,
                details={"collection_name": self.collection_name, "exception_type": type(exc).__name__},
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

    def index_chunks(
        self,
        chunks: Iterable[ChunkRecord],
        *,
        correlation_id: str = "corr_qdrant_backend_index",
    ) -> BackendOperationResult:
        chunk_tuple = tuple(chunks)
        health = self.health_check(required_capabilities=(BackendCapability.WRITE,), correlation_id=correlation_id)
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="index_chunks",
                message="qdrant vector backend is unavailable",
                retryable=True,
                details={"collection_name": self.collection_name},
            )
            return _operation_result(self.config, "index_chunks", False, correlation_id, health, error=error)

        points: list[dict[str, object]] = []
        embedding_ids: list[str] = []
        skipped_chunk_ids: list[str] = []
        for chunk in chunk_tuple:
            embedding = generate_embedding(chunk, dimensions=self.vector_size)
            if embedding is None:
                skipped_chunk_ids.append(chunk.chunk_id)
                continue
            embedding_ids.append(embedding.embedding_id)
            points.append(
                {
                    "id": _point_id(embedding.embedding_id),
                    "vector": embedding.vector,
                    "payload": _chunk_payload(chunk, embedding.embedding_id, embedding.terms),
                }
            )

        if not points:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="index_chunks",
                message="no qdrant points were created",
                retryable=False,
                details={"skipped_chunk_ids": tuple(skipped_chunk_ids)},
            )
            return _operation_result(
                self.config,
                "index_chunks",
                False,
                correlation_id,
                health,
                error=error,
                details={"chunk_count": len(chunk_tuple), "point_count": 0, "skipped_chunk_ids": tuple(skipped_chunk_ids)},
            )

        try:
            _client_upsert(self.client, self.collection_name, points)
        except Exception as exc:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="index_chunks",
                message=str(exc),
                retryable=True,
                details={"collection_name": self.collection_name, "exception_type": type(exc).__name__},
            )
            return _operation_result(self.config, "index_chunks", False, correlation_id, health, error=error)

        return _operation_result(
            self.config,
            "index_chunks",
            True,
            correlation_id,
            health,
            output_reference=",".join(embedding_ids) or None,
            details={
                "chunk_count": len(chunk_tuple),
                "point_count": len(points),
                "embedding_ids": tuple(embedding_ids),
                "skipped_chunk_ids": tuple(skipped_chunk_ids),
            },
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        correlation_id: str = "corr_qdrant_backend_search",
    ) -> BackendOperationResult:
        health = self.health_check(
            required_capabilities=(BackendCapability.READ, BackendCapability.VECTOR_SEARCH),
            correlation_id=correlation_id,
        )
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="search",
                message="qdrant vector backend is unavailable",
                retryable=True,
                details={"collection_name": self.collection_name},
            )
            return _operation_result(self.config, "search", False, correlation_id, health, error=error)

        embedding = generate_embedding(
            ChunkRecord(document_id="query", source_id="query", chunk_index=0, text=query, chunk_id="query"),
            dimensions=self.vector_size,
        )
        if embedding is None:
            return _operation_result(
                self.config,
                "search",
                True,
                correlation_id,
                health,
                details={"query": query, "top_k": top_k, "candidate_count": 0, "candidates": ()},
            )

        try:
            raw_hits = _client_search(self.client, self.collection_name, embedding.vector, top_k)
        except Exception as exc:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="search",
                message=str(exc),
                retryable=True,
                details={"collection_name": self.collection_name, "exception_type": type(exc).__name__},
            )
            return _operation_result(self.config, "search", False, correlation_id, health, error=error)

        candidates = tuple(_hit_to_candidate(hit, embedding.terms) for hit in raw_hits)
        return _operation_result(
            self.config,
            "search",
            True,
            correlation_id,
            health,
            output_reference=",".join(candidate["chunk_id"] for candidate in candidates) or None,
            details={
                "query": query,
                "top_k": top_k,
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
        )


def _load_qdrant_client(url_env: str, api_key_env: str) -> object | None:
    url = os.getenv(url_env)
    if not url:
        return None
    try:
        from qdrant_client import QdrantClient  # type: ignore
    except Exception:
        return None
    api_key = os.getenv(api_key_env)
    kwargs = {"url": url}
    if api_key:
        kwargs["api_key"] = api_key
    return QdrantClient(**kwargs)


def _client_count(client: object | None, collection_name: str) -> int | None:
    if client is None:
        return None
    if hasattr(client, "count"):
        result = client.count(collection_name=collection_name)
        return int(getattr(result, "count", result.get("count") if isinstance(result, dict) else 0))
    if hasattr(client, "get_collection"):
        result = client.get_collection(collection_name)
        points_count = getattr(result, "points_count", None)
        if points_count is None and isinstance(result, dict):
            points_count = result.get("points_count")
        return int(points_count or 0)
    if hasattr(client, "get_collections"):
        client.get_collections()
    return None


def _client_upsert(client: object | None, collection_name: str, points: list[dict[str, object]]) -> None:
    if client is None:
        raise RuntimeError("qdrant client is unavailable")
    client.upsert(collection_name=collection_name, points=points)


def _client_search(
    client: object | None,
    collection_name: str,
    query_vector: tuple[float, ...],
    top_k: int,
) -> tuple[object, ...]:
    if client is None:
        raise RuntimeError("qdrant client is unavailable")
    limit = max(top_k, 0)
    if hasattr(client, "search"):
        return tuple(
            client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        )
    if hasattr(client, "query_points"):
        result = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return tuple(getattr(result, "points", result.get("points") if isinstance(result, dict) else ()))
    raise RuntimeError("qdrant client does not expose search or query_points")


def _chunk_payload(chunk: ChunkRecord, embedding_id: str, terms: tuple[str, ...]) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "source_id": chunk.source_id,
        "embedding_id": embedding_id,
        "access_policy_id": chunk.access_policy_id,
        "allowed_principals": tuple(chunk.allowed_principals),
        "terms": terms,
    }


def _hit_to_candidate(hit: object, query_terms: tuple[str, ...]) -> dict[str, object]:
    payload = _hit_payload(hit)
    terms = tuple(payload.get("terms", ())) if isinstance(payload.get("terms", ()), (list, tuple)) else ()
    return {
        "chunk_id": str(payload.get("chunk_id", "")),
        "score": _hit_score(hit),
        "matched_terms": tuple(sorted(set(query_terms).intersection(terms))),
        "index_record_id": payload.get("embedding_id"),
        "source_id": payload.get("source_id"),
        "document_id": payload.get("document_id"),
        "access_policy_id": payload.get("access_policy_id"),
        "allowed_principals": tuple(payload.get("allowed_principals", ())),
    }


def _hit_payload(hit: object) -> dict[str, Any]:
    payload = getattr(hit, "payload", None)
    if payload is None and isinstance(hit, dict):
        payload = hit.get("payload")
    return dict(payload or {})


def _hit_score(hit: object) -> float:
    score = getattr(hit, "score", None)
    if score is None and isinstance(hit, dict):
        score = hit.get("score")
    return round(float(score or 0.0), 6)


def _point_id(embedding_id: str) -> int:
    return int(embedding_id.rsplit("_", 1)[-1][:16], 16)


__all__ = ["QdrantVectorBackendAdapter"]
