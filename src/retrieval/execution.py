"""Retrieval execution helpers for keyword/vector evidence lookup."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Iterable

from shared.contracts import ErrorEnvelope, ErrorType, FallbackAction, LogEvent, Partition, new_correlation_id
from shared.policies import create_error_envelope, create_error_log_event, create_success_log_event
from shared.records import AccessDecision, AccessLevel, EvidenceCandidate, ReliabilityLevel, RetrievalMode
from source_registry import InMemorySourceRepository, SourceRegistry, SourceRegistryError
from storage import InMemoryStorageRepository

from .indexing import (
    IndexCandidate,
    InMemoryKeywordIndex,
    InMemoryVectorIndex,
    keyword_index_from_repository,
    run_keyword_search,
    run_vector_search,
    vector_index_from_repository,
)


@dataclass(frozen=True, slots=True)
class AccessFilterResult:
    """Allowed evidence plus redaction-free metadata about exclusions."""

    candidates: tuple[EvidenceCandidate, ...]
    excluded_count: int = 0
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


@dataclass(frozen=True, slots=True)
class HybridSearchResult:
    """Merged hybrid retrieval evidence and emitted retrieval/access logs."""

    candidates: tuple[EvidenceCandidate, ...]
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()
    excluded_count: int = 0


@dataclass(frozen=True, slots=True)
class GraphTraversalResult:
    """Graph retrieval evidence and traversal diagnostics."""

    candidates: tuple[EvidenceCandidate, ...]
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()
    degraded: bool = False


def run_vector_retrieval(
    query: str,
    repository: InMemoryStorageRepository,
    *,
    vector_index: InMemoryVectorIndex | None = None,
    request_id: str | None = None,
    top_k: int = 5,
) -> tuple[EvidenceCandidate, ...]:
    """Search vector candidates and hydrate them into shared evidence records."""

    index = vector_index or vector_index_from_repository(repository)
    candidates = run_vector_search(query, index, top_k=top_k)
    return _hydrate_index_candidates(
        candidates,
        repository,
        request_id=request_id,
        retrieval_mode=RetrievalMode.VECTOR,
    )


def run_keyword_retrieval(
    query: str,
    repository: InMemoryStorageRepository,
    *,
    keyword_index: InMemoryKeywordIndex | None = None,
    request_id: str | None = None,
    top_k: int = 5,
) -> tuple[EvidenceCandidate, ...]:
    """Search keyword candidates and hydrate them into shared evidence records."""

    index = keyword_index or keyword_index_from_repository(repository)
    candidates = run_keyword_search(query, index, top_k=top_k)
    return _hydrate_index_candidates(
        candidates,
        repository,
        request_id=request_id,
        retrieval_mode=RetrievalMode.KEYWORD,
    )


def run_graph_retrieval(
    query: str,
    repository: InMemoryStorageRepository,
    *,
    request_id: str | None = None,
    top_k: int = 5,
    max_depth: int = 1,
    correlation_id: str | None = None,
) -> GraphTraversalResult:
    """Traverse committed graph relations from query-matched entities."""

    corr = correlation_id or new_correlation_id("retrieval")
    resolved_request_id = request_id or new_correlation_id("request")
    seed_entity_ids = _resolve_query_entity_ids(query, repository)
    if not query.strip() or not seed_entity_ids or not repository.relations:
        log = create_success_log_event(
            correlation_id=corr,
            partition=Partition.RETRIEVAL,
            operation_name="run_graph_retrieval",
            event_name="graph_traversal_degraded",
            message="Graph retrieval skipped because no traversable query entities were found.",
            details={
                "query": query,
                "seed_entity_ids": sorted(seed_entity_ids),
                "relation_count": len(repository.relations),
                "candidate_count": 0,
            },
        )
        repository.add_log(log)
        return GraphTraversalResult(candidates=(), logs=(log,), degraded=True)

    relation_distances = _traverse_relation_ids(seed_entity_ids, repository, max_depth=max_depth)
    candidates = _hydrate_graph_candidates(
        relation_distances,
        seed_entity_ids=seed_entity_ids,
        repository=repository,
        request_id=resolved_request_id,
    )
    ordered = tuple(
        sorted(
            candidates,
            key=lambda candidate: (candidate.score or 0.0, candidate.chunk_id or "", ",".join(candidate.relation_ids)),
            reverse=True,
        )[: max(top_k, 0)]
    )
    log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.RETRIEVAL,
        operation_name="run_graph_retrieval",
        event_name="graph_traversal_completed",
        message="Completed graph traversal retrieval.",
        output_reference=",".join(candidate.evidence_id for candidate in ordered) or None,
        details={
            "query": query,
            "seed_entity_ids": sorted(seed_entity_ids),
            "relation_count": len(relation_distances),
            "candidate_count": len(ordered),
        },
    )
    repository.add_log(log)
    return GraphTraversalResult(candidates=ordered, logs=(log,), degraded=False)


def apply_access_filter(
    candidates: Iterable[EvidenceCandidate],
    repository: InMemoryStorageRepository,
    *,
    registry: SourceRegistry | None = None,
    principal: str | None = None,
    principal_scopes: Iterable[str] = (),
    use_case: str = "general",
    correlation_id: str | None = None,
) -> AccessFilterResult:
    """Exclude evidence that lacks access metadata or fails source policy checks."""

    corr = correlation_id or new_correlation_id("retrieval")
    source_registry = registry or SourceRegistry(InMemorySourceRepository(repository.sources.values()))
    scopes = tuple(principal_scopes)
    candidate_tuple = tuple(candidates)
    allowed: list[EvidenceCandidate] = []
    logs: list[LogEvent] = []
    errors: list[ErrorEnvelope] = []
    excluded_count = 0

    for candidate in candidate_tuple:
        missing_reason = _missing_access_reason(candidate, repository)
        if missing_reason is not None:
            excluded_count += 1
            logs.append(repository.add_log(_access_failure_log(candidate, missing_reason, corr)))
            error = _access_error(candidate, missing_reason, corr)
            errors.append(error)
            repository.save_error(error)
            continue

        try:
            decision = source_registry.apply_source_policy(
                candidate.source_id or "",
                use_case=use_case,
                principal=principal,
                principal_scopes=scopes,
                correlation_id=corr,
            )
        except SourceRegistryError as exc:
            excluded_count += 1
            logs.append(repository.add_log(_access_failure_log(candidate, str(exc), corr)))
            error = _access_error(candidate, str(exc), corr)
            errors.append(error)
            repository.save_error(error)
            continue

        record_denial = _record_access_denial(candidate, repository, principal=principal, principal_scopes=scopes)
        if record_denial is not None:
            excluded_count += 1
            logs.append(repository.add_log(_access_failure_log(candidate, record_denial, corr)))
            error = _access_error(candidate, record_denial, corr)
            errors.append(error)
            repository.save_error(error)
            continue

        if decision.log is not None:
            logs.append(repository.add_log(decision.log))
        if not decision.allowed:
            excluded_count += 1
            logs.append(repository.add_log(_access_failure_log(candidate, decision.reason, corr)))
            if decision.error is not None:
                errors.append(decision.error)
                repository.save_error(decision.error)
            continue

        allowed.append(
            replace(
                candidate,
                access_decision=AccessDecision.ALLOWED,
                exclusion_reason=None,
            )
        )

    summary_log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.RETRIEVAL,
        operation_name="apply_access_filter",
        event_name="access_filter_applied",
        message="Applied retrieval access filter.",
        details={
            "input_count": len(candidate_tuple),
            "allowed_count": len(allowed),
            "excluded_count": excluded_count,
            "error_count": len(errors),
        },
    )
    logs.append(repository.add_log(summary_log))
    return AccessFilterResult(tuple(allowed), excluded_count, tuple(logs), tuple(errors))


def merge_evidence_candidates(
    candidates: Iterable[EvidenceCandidate],
    *,
    top_k: int | None = None,
) -> tuple[EvidenceCandidate, ...]:
    """Normalize scores, deduplicate by source/chunk, and sort before reranking."""

    normalized = _normalize_by_mode(tuple(candidates))
    merged: dict[tuple[str | None, str | None], EvidenceCandidate] = {}
    modes_by_key: dict[tuple[str | None, str | None], set[RetrievalMode]] = {}

    for candidate in normalized:
        key = (candidate.source_id, candidate.chunk_id or candidate.evidence_id)
        modes_by_key.setdefault(key, set()).add(candidate.retrieval_mode)
        current = merged.get(key)
        if current is None or (candidate.normalized_score or 0.0) > (current.normalized_score or 0.0):
            merged[key] = _merge_graph_ids(candidate, current)
            continue
        if current.score is None or (candidate.score is not None and candidate.score > current.score):
            merged[key] = _merge_graph_ids(replace(current, score=candidate.score), candidate)
            continue
        merged[key] = _merge_graph_ids(current, candidate)

    deduped: list[EvidenceCandidate] = []
    for key, candidate in merged.items():
        modes = modes_by_key[key]
        retrieval_mode = RetrievalMode.HYBRID if len(modes) > 1 else candidate.retrieval_mode
        deduped.append(
            replace(
                candidate,
                retrieval_mode=retrieval_mode,
                normalized_score=round(candidate.normalized_score or 0.0, 6),
            )
        )

    ordered = tuple(
        sorted(
            deduped,
            key=lambda candidate: (
                candidate.normalized_score or 0.0,
                candidate.score or 0.0,
                candidate.chunk_id or "",
            ),
            reverse=True,
        )
    )
    return ordered[:top_k] if top_k is not None else ordered


def run_hybrid_search(
    query: str,
    repository: InMemoryStorageRepository,
    *,
    vector_index: InMemoryVectorIndex | None = None,
    keyword_index: InMemoryKeywordIndex | None = None,
    request_id: str | None = None,
    principal: str | None = None,
    principal_scopes: Iterable[str] = (),
    use_case: str = "general",
    top_k: int = 5,
    correlation_id: str | None = None,
) -> HybridSearchResult:
    """Run keyword and vector lookup, filter access, merge, and log retrieval."""

    corr = correlation_id or new_correlation_id("retrieval")
    vector_candidates = run_vector_retrieval(
        query,
        repository,
        vector_index=vector_index,
        request_id=request_id,
        top_k=top_k,
    )
    keyword_candidates = run_keyword_retrieval(
        query,
        repository,
        keyword_index=keyword_index,
        request_id=request_id,
        top_k=top_k,
    )
    access = apply_access_filter(
        (*keyword_candidates, *vector_candidates),
        repository,
        principal=principal,
        principal_scopes=principal_scopes,
        use_case=use_case,
        correlation_id=corr,
    )
    merged = merge_evidence_candidates(access.candidates, top_k=top_k)
    log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_completed",
        message="Completed hybrid keyword/vector retrieval.",
        output_reference=",".join(candidate.evidence_id for candidate in merged) or None,
        details={
            "query": query,
            "keyword_count": len(keyword_candidates),
            "vector_count": len(vector_candidates),
            "allowed_count": len(access.candidates),
            "merged_count": len(merged),
            "excluded_count": access.excluded_count,
            "modes": ["keyword", "vector"],
        },
    )
    repository.add_log(log)
    return HybridSearchResult(
        candidates=merged,
        logs=(*access.logs, log),
        errors=access.errors,
        excluded_count=access.excluded_count,
    )


def _hydrate_index_candidates(
    candidates: Iterable[IndexCandidate],
    repository: InMemoryStorageRepository,
    *,
    request_id: str | None,
    retrieval_mode: RetrievalMode,
) -> tuple[EvidenceCandidate, ...]:
    evidence: list[EvidenceCandidate] = []
    resolved_request_id = request_id or new_correlation_id("request")
    for candidate in candidates:
        chunk = repository.chunks.get(candidate.chunk_id)
        if chunk is None:
            continue
        document = repository.documents.get(chunk.document_id)
        source = repository.sources.get(chunk.source_id)
        citation_link = _citation_link(document.canonical_url if document else None, chunk.chunk_index)
        evidence.append(
            EvidenceCandidate(
                request_id=resolved_request_id,
                retrieval_mode=retrieval_mode,
                source_id=chunk.source_id,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                text_snippet=chunk.text,
                score=candidate.score,
                source_reliability=source.reliability_level if source else ReliabilityLevel.UNVERIFIED,
                published_at=document.published_at if document else None,
                retrieved_at=document.retrieved_at if document else None,
                citation_link=citation_link,
                access_scope=chunk.access_policy_id,
                access_decision=AccessDecision.UNKNOWN,
                license_constraints=list(source.license_constraints) if source else [],
            )
        )
    return tuple(evidence)


def _hydrate_graph_candidates(
    relation_distances: dict[str, int],
    *,
    seed_entity_ids: set[str],
    repository: InMemoryStorageRepository,
    request_id: str,
) -> tuple[EvidenceCandidate, ...]:
    evidence: list[EvidenceCandidate] = []
    seen: set[tuple[str, str]] = set()
    for relation_id, distance in relation_distances.items():
        relation = repository.relations.get(relation_id)
        if relation is None:
            continue
        relation_entity_ids = [relation.subject_entity_id, relation.object_entity_id]
        for chunk_id in relation.evidence_chunk_ids:
            chunk = repository.chunks.get(chunk_id)
            if chunk is None:
                continue
            key = (relation_id, chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            document = repository.documents.get(chunk.document_id)
            source = repository.sources.get(chunk.source_id)
            citation_link = _citation_link(document.canonical_url if document else None, chunk.chunk_index)
            seed_bonus = 0.1 if seed_entity_ids.intersection(relation_entity_ids) else 0.0
            evidence.append(
                EvidenceCandidate(
                    request_id=request_id,
                    retrieval_mode=RetrievalMode.GRAPH,
                    source_id=chunk.source_id,
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    entity_ids=sorted(set(relation_entity_ids)),
                    relation_ids=[relation.relation_id],
                    text_snippet=chunk.text,
                    score=round((relation.confidence or 0.5) + seed_bonus - (0.05 * distance), 6),
                    source_reliability=source.reliability_level if source else ReliabilityLevel.UNVERIFIED,
                    published_at=document.published_at if document else None,
                    retrieved_at=document.retrieved_at if document else None,
                    citation_link=citation_link,
                    access_scope=chunk.access_policy_id,
                    access_decision=AccessDecision.UNKNOWN,
                    license_constraints=list(source.license_constraints) if source else [],
                )
            )
    return tuple(evidence)


def _resolve_query_entity_ids(query: str, repository: InMemoryStorageRepository) -> set[str]:
    normalized_query = _alias_key(query)
    matched: set[str] = set()
    for alias, entity_ids in repository.entity_ids_by_alias.items():
        if alias and _alias_matches_query(alias, normalized_query):
            matched.update(entity_ids)
    return matched


def _alias_matches_query(alias: str, normalized_query: str) -> bool:
    if len(alias) <= 1:
        return normalized_query == alias
    pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(part) for part in alias.split()) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_query) is not None


def _traverse_relation_ids(
    seed_entity_ids: set[str],
    repository: InMemoryStorageRepository,
    *,
    max_depth: int,
) -> dict[str, int]:
    relation_distances: dict[str, int] = {}
    frontier = set(seed_entity_ids)
    visited_entities = set(seed_entity_ids)
    for depth in range(max(max_depth, 0) + 1):
        next_frontier: set[str] = set()
        for entity_id in sorted(frontier):
            for relation_id in sorted(repository.relation_ids_by_entity_id.get(entity_id, ())):
                relation_distances.setdefault(relation_id, depth)
                relation = repository.relations.get(relation_id)
                if relation is None:
                    continue
                neighbors = {relation.subject_entity_id, relation.object_entity_id}
                next_frontier.update(neighbor for neighbor in neighbors if neighbor not in visited_entities)
        visited_entities.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return relation_distances


def _merge_graph_ids(candidate: EvidenceCandidate, other: EvidenceCandidate | None) -> EvidenceCandidate:
    if other is None:
        return candidate
    entity_ids = sorted(set(candidate.entity_ids).union(other.entity_ids))
    relation_ids = sorted(set(candidate.relation_ids).union(other.relation_ids))
    return replace(candidate, entity_ids=entity_ids, relation_ids=relation_ids)


def _normalize_by_mode(candidates: tuple[EvidenceCandidate, ...]) -> tuple[EvidenceCandidate, ...]:
    by_mode: dict[RetrievalMode, list[EvidenceCandidate]] = {}
    for candidate in candidates:
        by_mode.setdefault(candidate.retrieval_mode, []).append(candidate)

    normalized: list[EvidenceCandidate] = []
    for mode_candidates in by_mode.values():
        scores = [candidate.score or 0.0 for candidate in mode_candidates]
        low = min(scores)
        high = max(scores)
        for candidate in mode_candidates:
            raw = candidate.score or 0.0
            if high == low:
                norm = 1.0 if raw > 0 else 0.0
            else:
                norm = (raw - low) / (high - low)
            normalized.append(replace(candidate, normalized_score=round(norm, 6)))
    return tuple(normalized)


def _alias_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _missing_access_reason(candidate: EvidenceCandidate, repository: InMemoryStorageRepository) -> str | None:
    if not candidate.source_id:
        return "candidate missing source_id"
    if not candidate.document_id:
        return "candidate missing document_id"
    if not candidate.chunk_id:
        return "candidate missing chunk_id"
    source = repository.sources.get(candidate.source_id)
    document = repository.documents.get(candidate.document_id)
    chunk = repository.chunks.get(candidate.chunk_id)
    if source is None:
        return "source metadata missing"
    if document is None:
        return "document metadata missing"
    if chunk is None:
        return "chunk metadata missing"
    if not source.access_policy_id:
        return "source access metadata missing"
    if not document.access_policy_id:
        return "document access metadata missing"
    if not chunk.access_policy_id:
        return "chunk access metadata missing"
    return None


def _record_access_denial(
    candidate: EvidenceCandidate,
    repository: InMemoryStorageRepository,
    *,
    principal: str | None,
    principal_scopes: Iterable[str],
) -> str | None:
    document = repository.documents[candidate.document_id or ""]
    chunk = repository.chunks[candidate.chunk_id or ""]
    source = repository.sources[candidate.source_id or ""]
    scopes = set(principal_scopes)

    document_denial = _access_policy_denial(
        document.access_policy_id,
        principal=principal,
        principal_scopes=scopes,
        allowed_principals=source.allowed_principals,
        label="document",
    )
    if document_denial is not None:
        return document_denial

    return _access_policy_denial(
        chunk.access_policy_id,
        principal=principal,
        principal_scopes=scopes,
        allowed_principals=chunk.allowed_principals or source.allowed_principals,
        label="chunk",
    )


def _access_policy_denial(
    access_policy_id: str | None,
    *,
    principal: str | None,
    principal_scopes: set[str],
    allowed_principals: Iterable[str],
    label: str,
) -> str | None:
    access_level = _access_level_from_policy(access_policy_id)
    if access_level is AccessLevel.PUBLIC:
        return None
    if access_level is AccessLevel.INTERNAL:
        if "internal" in principal_scopes or (principal is not None and principal in set(allowed_principals)):
            return None
        return f"{label} internal access denied for principal"
    if access_level in {AccessLevel.CONFIDENTIAL, AccessLevel.RESTRICTED}:
        principals = set(allowed_principals)
        if principal is not None and principal in principals:
            return None
        return f"{label} {access_level.value} access denied for principal"
    return f"{label} access metadata unknown"


def _access_level_from_policy(access_policy_id: str | None) -> AccessLevel:
    if not access_policy_id:
        return AccessLevel.UNKNOWN
    value = access_policy_id.removeprefix("access:")
    try:
        return AccessLevel(value)
    except ValueError:
        return AccessLevel.UNKNOWN


def _access_error(candidate: EvidenceCandidate, reason: str, correlation_id: str) -> ErrorEnvelope:
    return create_error_envelope(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="apply_access_filter",
        error_type=ErrorType.ACCESS,
        error_message=reason,
        fallback_action=FallbackAction.SKIP,
        details={
            "event_name": "access_filter_failed_closed",
            "source_id": candidate.source_id,
            "document_id": candidate.document_id,
            "chunk_id": candidate.chunk_id,
        },
    )


def _access_failure_log(candidate: EvidenceCandidate, reason: str, correlation_id: str) -> LogEvent:
    return create_error_log_event(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="apply_access_filter",
        error_type=ErrorType.ACCESS,
        event_name="access_filter_failed_closed",
        message=reason,
        fallback_action=FallbackAction.SKIP,
        details={
            "source_id": candidate.source_id,
            "document_id": candidate.document_id,
            "chunk_id": candidate.chunk_id,
        },
    )


def _citation_link(canonical_url: str | None, chunk_index: int) -> str | None:
    if not canonical_url:
        return None
    separator = "&" if "#" in canonical_url else "#"
    return f"{canonical_url}{separator}chunk-{chunk_index}"
