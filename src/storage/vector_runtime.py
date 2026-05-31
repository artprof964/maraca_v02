"""Executable dependency-free vector backend adapter."""

from __future__ import annotations

import time
from typing import Iterable

from shared.contracts import ErrorEnvelope, ErrorSeverity, ErrorType, FallbackAction, Partition
from shared.policies import create_error_envelope
from shared.records import ChunkRecord

from . import InMemoryStorageRepository
from .adapters import (
    BackendAdapterConfig,
    BackendCapability,
    BackendHealthCheck,
    BackendOperationResult,
    BackendStatus,
    BackendType,
)


class InMemoryVectorBackendAdapter:
    """Executable vector adapter for the current dependency-free index."""

    def __init__(
        self,
        repository: InMemoryStorageRepository,
        *,
        adapter_name: str = "in_memory_vector_runtime",
        priority: int = 20,
    ) -> None:
        from retrieval.indexing import InMemoryVectorIndex

        self.repository = repository
        self.vector_index = InMemoryVectorIndex()
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
            endpoint_reference="memory://vector_runtime",
            connection_settings={"repository": "in_memory"},
        )

    def to_config(self) -> BackendAdapterConfig:
        return self.config

    def health_check(
        self,
        *,
        required_capabilities: Iterable[BackendCapability] = (),
        correlation_id: str = "corr_vector_backend_health",
    ) -> BackendHealthCheck:
        started = time.perf_counter()
        required = tuple(dict.fromkeys(required_capabilities))
        missing = tuple(capability for capability in required if capability not in self.config.capabilities)
        status = BackendStatus.DEGRADED if missing else BackendStatus.READY
        message = "missing required capabilities" if missing else "in-memory vector backend is available"
        error = None
        if missing:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="health_check",
                message=message,
                retryable=False,
                details={"missing_capabilities": tuple(capability.value for capability in missing)},
            )
        return BackendHealthCheck(
            adapter_name=self.config.adapter_name,
            backend_type=self.config.backend_type,
            status=status,
            latency_ms=(time.perf_counter() - started) * 1000,
            message=message,
            checked_capabilities=required or self.config.capabilities,
            error=error,
            details={
                "embedding_count": len(self.repository.vector_embeddings),
                "indexed_chunk_count": len(self.vector_index.embeddings_by_chunk_id),
                "missing_capabilities": tuple(capability.value for capability in missing),
            },
        )

    def index_chunks(
        self,
        chunks: Iterable[ChunkRecord],
        *,
        correlation_id: str = "corr_vector_backend_index",
    ) -> BackendOperationResult:
        from retrieval.indexing import commit_vectors

        chunk_tuple = tuple(chunks)
        health = self.health_check(
            required_capabilities=(BackendCapability.WRITE,),
            correlation_id=correlation_id,
        )
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="index_chunks",
                message="vector backend is unavailable",
                retryable=True,
                details={},
            )
            return _operation_result(self.config, "index_chunks", False, correlation_id, health, error=error)

        result = commit_vectors(
            self.repository,
            chunk_tuple,
            vector_index=self.vector_index,
            correlation_id=correlation_id,
        )
        ok = bool(result.record_ids) or not chunk_tuple
        error = None
        if not ok:
            error = _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="index_chunks",
                message="no vector embeddings were created",
                retryable=False,
                details={"skipped_chunk_ids": result.skipped_chunk_ids},
            )
        return _operation_result(
            self.config,
            "index_chunks",
            ok,
            correlation_id,
            health,
            output_reference=",".join(result.record_ids) or None,
            error=error,
            details={
                "chunk_count": len(chunk_tuple),
                "embedding_count": len(result.record_ids),
                "skipped_chunk_ids": result.skipped_chunk_ids,
            },
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        correlation_id: str = "corr_vector_backend_search",
    ) -> BackendOperationResult:
        from retrieval.indexing import run_vector_search

        health = self.health_check(
            required_capabilities=(BackendCapability.READ, BackendCapability.VECTOR_SEARCH),
            correlation_id=correlation_id,
        )
        if health.status is BackendStatus.UNAVAILABLE:
            error = health.error or _vector_backend_error(
                correlation_id=correlation_id,
                operation_name="search",
                message="vector backend is unavailable",
                retryable=True,
                details={},
            )
            return _operation_result(self.config, "search", False, correlation_id, health, error=error)

        candidates = run_vector_search(query, self.vector_index, top_k=top_k)
        return _operation_result(
            self.config,
            "search",
            True,
            correlation_id,
            health,
            output_reference=",".join(candidate.chunk_id for candidate in candidates) or None,
            details={
                "query": query,
                "top_k": top_k,
                "candidate_count": len(candidates),
                "candidates": tuple(
                    {
                        "chunk_id": candidate.chunk_id,
                        "score": candidate.score,
                        "matched_terms": candidate.matched_terms,
                        "index_record_id": candidate.index_record_id,
                    }
                    for candidate in candidates
                ),
            },
        )


def _operation_result(
    config: BackendAdapterConfig,
    operation_name: str,
    ok: bool,
    correlation_id: str,
    health: BackendHealthCheck,
    *,
    output_reference: str | None = None,
    error: ErrorEnvelope | None = None,
    details: dict[str, object] | None = None,
) -> BackendOperationResult:
    return BackendOperationResult(
        adapter_name=config.adapter_name,
        backend_type=config.backend_type,
        operation_name=operation_name,
        ok=ok,
        correlation_id=correlation_id,
        output_reference=output_reference,
        health=health,
        error=error,
        details=details or {},
    )


def _vector_backend_error(
    *,
    correlation_id: str,
    operation_name: str,
    message: str,
    retryable: bool,
    details: dict[str, object],
) -> ErrorEnvelope:
    return create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.STORAGE,
        operation_name=operation_name,
        error_type=ErrorType.STORAGE,
        error_message=message,
        severity=ErrorSeverity.RECOVERABLE if retryable else ErrorSeverity.CRITICAL,
        retryable=retryable,
        fallback_action=FallbackAction.RETRY if retryable else FallbackAction.STOP,
        details=details,
    )


__all__ = ["InMemoryVectorBackendAdapter"]
