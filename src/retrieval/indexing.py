"""Dependency-free vector and sparse indexing for early Milestone 1."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
import hashlib
import math
import re
from typing import Iterable, Mapping

from shared.contracts import LogEvent, Partition, new_correlation_id
from shared.policies import create_success_log_event
from shared.records import ChunkRecord
from storage import InMemoryStorageRepository


VECTOR_DIMENSIONS = 32
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-_./:][A-Za-z0-9]+)*")
_QUOTED_PHRASE_RE = re.compile(r'"([^"\n]{2,120})"|\'([^\'\n]{2,120})\'')


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    """Deterministic hashed bag-of-terms vector linked to a chunk."""

    chunk_id: str
    vector: tuple[float, ...]
    terms: tuple[str, ...]
    embedding_id: str


@dataclass(frozen=True, slots=True)
class SparseTermsRecord:
    """Exact keyword/phrase terms linked to a chunk."""

    chunk_id: str
    terms: tuple[str, ...]
    term_weights: Mapping[str, float]
    sparse_terms_id: str


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    """Search hit emitted by the lightweight vector or keyword indexes."""

    chunk_id: str
    score: float
    matched_terms: tuple[str, ...] = ()
    index_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class IndexCommitResult:
    """Updated chunks plus the underlying storage commit result."""

    chunks: tuple[ChunkRecord, ...]
    record_ids: tuple[str, ...]
    skipped_chunk_ids: tuple[str, ...] = ()
    log: LogEvent | None = None


@dataclass(slots=True)
class InMemoryVectorIndex:
    """Small cosine-search index keyed by chunk_id."""

    embeddings_by_chunk_id: dict[str, EmbeddingRecord] = field(default_factory=dict)

    def upsert(self, embedding: EmbeddingRecord) -> None:
        self.embeddings_by_chunk_id[embedding.chunk_id] = embedding


@dataclass(slots=True)
class InMemoryKeywordIndex:
    """Small exact term/phrase index keyed by term and chunk_id."""

    sparse_terms_by_chunk_id: dict[str, SparseTermsRecord] = field(default_factory=dict)
    chunk_ids_by_term: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def upsert(self, sparse_terms: SparseTermsRecord) -> None:
        old = self.sparse_terms_by_chunk_id.get(sparse_terms.chunk_id)
        if old is not None:
            for term in old.terms:
                self.chunk_ids_by_term[term].discard(old.chunk_id)
        self.sparse_terms_by_chunk_id[sparse_terms.chunk_id] = sparse_terms
        for term in sparse_terms.terms:
            self.chunk_ids_by_term[term].add(sparse_terms.chunk_id)


def generate_embedding(chunk: ChunkRecord, *, dimensions: int = VECTOR_DIMENSIONS) -> EmbeddingRecord | None:
    """Generate a stable hashed term vector for a non-empty chunk."""

    terms = _embedding_terms(chunk.text)
    if not terms:
        return None
    counts = Counter(terms)
    vector = [0.0] * dimensions
    for term, count in counts.items():
        bucket = _stable_int(f"bucket:{term}") % dimensions
        sign = 1.0 if _stable_int(f"sign:{term}") % 2 == 0 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    normalized = tuple(round(value / norm, 6) for value in vector) if norm else tuple(vector)
    embedding_id = _stable_id("emb", chunk.chunk_id, "|".join(terms), str(dimensions))
    return EmbeddingRecord(
        chunk_id=chunk.chunk_id,
        vector=normalized,
        terms=tuple(sorted(counts)),
        embedding_id=embedding_id,
    )


def extract_sparse_terms(chunk: ChunkRecord) -> SparseTermsRecord | None:
    """Extract exact identifiers, quoted phrases, and normalized keyword terms."""

    terms = _sparse_terms(chunk.text)
    if not terms:
        return None
    counts = Counter(terms)
    weights = {term: _term_weight(term, count) for term, count in sorted(counts.items())}
    sparse_terms_id = _stable_id("sparse", chunk.chunk_id, "|".join(sorted(counts)))
    return SparseTermsRecord(
        chunk_id=chunk.chunk_id,
        terms=tuple(sorted(counts)),
        term_weights=weights,
        sparse_terms_id=sparse_terms_id,
    )


def generate_embeddings(chunks: Iterable[ChunkRecord]) -> tuple[EmbeddingRecord, ...]:
    """Generate embeddings for all valid chunks, skipping empty chunks."""

    records = [embedding for chunk in chunks if (embedding := generate_embedding(chunk)) is not None]
    return tuple(records)


def extract_sparse_terms_for_chunks(chunks: Iterable[ChunkRecord]) -> tuple[SparseTermsRecord, ...]:
    """Extract sparse terms for all valid chunks, skipping empty chunks."""

    records = [terms for chunk in chunks if (terms := extract_sparse_terms(chunk)) is not None]
    return tuple(records)


def commit_vectors(
    repository: InMemoryStorageRepository,
    chunks: Iterable[ChunkRecord],
    *,
    vector_index: InMemoryVectorIndex | None = None,
    correlation_id: str | None = None,
) -> IndexCommitResult:
    """Persist embedding records and update each chunk's embedding_id."""

    updated_chunks: list[ChunkRecord] = []
    embedding_ids: list[str] = []
    skipped_chunk_ids: list[str] = []
    index = vector_index or InMemoryVectorIndex()
    for chunk in chunks:
        embedding = generate_embedding(chunk)
        if embedding is None:
            skipped_chunk_ids.append(chunk.chunk_id)
            continue
        index.upsert(embedding)
        repository.vector_embeddings[embedding.embedding_id] = embedding
        base_chunk = repository.chunks.get(chunk.chunk_id, chunk)
        updated_chunk = replace(base_chunk, embedding_id=embedding.embedding_id)
        repository.save_chunk(updated_chunk)
        updated_chunks.append(updated_chunk)
        embedding_ids.append(embedding.embedding_id)
    log = _storage_log(
        correlation_id=correlation_id,
        operation_name="commit_vectors",
        event_name="vectors_degraded" if skipped_chunk_ids else "vectors_committed",
        output_reference=",".join(embedding_ids) if embedding_ids else None,
        details={
            "embedding_count": len(embedding_ids),
            "embedding_ids": embedding_ids,
            "skipped_chunk_ids": skipped_chunk_ids,
        },
    )
    repository.add_log(log)
    return IndexCommitResult(tuple(updated_chunks), tuple(embedding_ids), tuple(skipped_chunk_ids), log)


def commit_sparse_index(
    repository: InMemoryStorageRepository,
    chunks: Iterable[ChunkRecord],
    *,
    keyword_index: InMemoryKeywordIndex | None = None,
    correlation_id: str | None = None,
) -> IndexCommitResult:
    """Persist sparse term records and update each chunk's sparse_terms_id."""

    updated_chunks: list[ChunkRecord] = []
    sparse_ids: list[str] = []
    skipped_chunk_ids: list[str] = []
    index = keyword_index or InMemoryKeywordIndex()
    for chunk in chunks:
        sparse_terms = extract_sparse_terms(chunk)
        if sparse_terms is None:
            skipped_chunk_ids.append(chunk.chunk_id)
            continue
        index.upsert(sparse_terms)
        repository.sparse_terms[sparse_terms.sparse_terms_id] = sparse_terms
        base_chunk = repository.chunks.get(chunk.chunk_id, chunk)
        updated_chunk = replace(base_chunk, sparse_terms_id=sparse_terms.sparse_terms_id)
        repository.save_chunk(updated_chunk)
        updated_chunks.append(updated_chunk)
        sparse_ids.append(sparse_terms.sparse_terms_id)
    log = _storage_log(
        correlation_id=correlation_id,
        operation_name="commit_sparse_index",
        event_name="sparse_index_degraded" if skipped_chunk_ids else "sparse_index_committed",
        output_reference=",".join(sparse_ids) if sparse_ids else None,
        details={
            "sparse_record_count": len(sparse_ids),
            "sparse_terms_ids": sparse_ids,
            "skipped_chunk_ids": skipped_chunk_ids,
        },
    )
    repository.add_log(log)
    return IndexCommitResult(tuple(updated_chunks), tuple(sparse_ids), tuple(skipped_chunk_ids), log)


def build_vector_index(embeddings: Iterable[EmbeddingRecord]) -> InMemoryVectorIndex:
    index = InMemoryVectorIndex()
    for embedding in embeddings:
        index.upsert(embedding)
    return index


def build_keyword_index(sparse_records: Iterable[SparseTermsRecord]) -> InMemoryKeywordIndex:
    index = InMemoryKeywordIndex()
    for sparse_terms in sparse_records:
        index.upsert(sparse_terms)
    return index


def run_vector_search(
    query: str,
    vector_index: InMemoryVectorIndex,
    *,
    top_k: int = 5,
) -> tuple[IndexCandidate, ...]:
    """Return cosine-similar chunks from the deterministic vector index."""

    query_embedding = _embedding_for_text(query)
    if query_embedding is None:
        return ()
    candidates: list[IndexCandidate] = []
    for embedding in vector_index.embeddings_by_chunk_id.values():
        score = _cosine(query_embedding.vector, embedding.vector)
        overlap = tuple(sorted(set(query_embedding.terms).intersection(embedding.terms)))
        if score <= 0 and not overlap:
            continue
        candidates.append(
            IndexCandidate(
                chunk_id=embedding.chunk_id,
                score=round(score + (0.05 * len(overlap)), 6),
                matched_terms=overlap,
                index_record_id=embedding.embedding_id,
            )
        )
    return _top_candidates(candidates, top_k)


def run_keyword_search(
    query: str,
    keyword_index: InMemoryKeywordIndex,
    *,
    top_k: int = 5,
) -> tuple[IndexCandidate, ...]:
    """Return exact term and phrase candidates from the keyword index."""

    query_terms = _sparse_terms(query)
    if not query_terms:
        return ()
    scores: dict[str, float] = defaultdict(float)
    matches: dict[str, set[str]] = defaultdict(set)
    record_ids: dict[str, str] = {}
    for term in query_terms:
        for chunk_id in keyword_index.chunk_ids_by_term.get(term, ()):
            record = keyword_index.sparse_terms_by_chunk_id[chunk_id]
            scores[chunk_id] += record.term_weights.get(term, 1.0)
            matches[chunk_id].add(term)
            record_ids[chunk_id] = record.sparse_terms_id
    candidates = [
        IndexCandidate(
            chunk_id=chunk_id,
            score=round(score, 6),
            matched_terms=tuple(sorted(matches[chunk_id])),
            index_record_id=record_ids.get(chunk_id),
        )
        for chunk_id, score in scores.items()
    ]
    return _top_candidates(candidates, top_k)


def vector_index_from_repository(repository: InMemoryStorageRepository) -> InMemoryVectorIndex:
    return build_vector_index(
        record for record in repository.vector_embeddings.values() if isinstance(record, EmbeddingRecord)
    )


def keyword_index_from_repository(repository: InMemoryStorageRepository) -> InMemoryKeywordIndex:
    return build_keyword_index(
        record for record in repository.sparse_terms.values() if isinstance(record, SparseTermsRecord)
    )


def _embedding_for_text(text: str) -> EmbeddingRecord | None:
    chunk = ChunkRecord(document_id="query", source_id="query", chunk_index=0, text=text, chunk_id="query")
    return generate_embedding(chunk)


def _embedding_terms(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD_RE.finditer(text or ""))


def _sparse_terms(text: str) -> tuple[str, ...]:
    if not text or not text.strip():
        return ()
    terms: list[str] = []
    for match in _QUOTED_PHRASE_RE.finditer(text):
        phrase = next(group for group in match.groups() if group)
        normalized_phrase = " ".join(phrase.split())
        if normalized_phrase:
            terms.append(normalized_phrase)
            terms.append(normalized_phrase.lower())
    for match in _WORD_RE.finditer(text):
        token = match.group(0)
        lowered = token.lower()
        terms.append(lowered)
        if _looks_like_identifier(token):
            terms.append(token)
    lowered_words = [match.group(0).lower() for match in _WORD_RE.finditer(text)]
    for width in range(2, min(5, len(lowered_words)) + 1):
        for index in range(0, len(lowered_words) - width + 1):
            terms.append(" ".join(lowered_words[index : index + width]))
    return tuple(dict.fromkeys(terms))


def _looks_like_identifier(token: str) -> bool:
    return (
        any(separator in token for separator in ("_", "-", "/", ":", "."))
        or any(character.isdigit() for character in token)
        or (any(character.islower() for character in token) and any(character.isupper() for character in token))
        or token.isupper()
    )


def _term_weight(term: str, count: int) -> float:
    base = 1.0 + math.log(count)
    if " " in term:
        base += 3.0
    elif _looks_like_identifier(term):
        base += 2.0
    elif len(term) >= 10:
        base += 0.75
    return round(base, 6)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def _stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _top_candidates(candidates: Iterable[IndexCandidate], top_k: int) -> tuple[IndexCandidate, ...]:
    return tuple(
        sorted(candidates, key=lambda candidate: (-candidate.score, candidate.chunk_id))[: max(top_k, 0)]
    )


def _storage_log(
    *,
    correlation_id: str | None,
    operation_name: str,
    event_name: str,
    output_reference: str | None = None,
    details: dict[str, object] | None = None,
) -> LogEvent:
    return create_success_log_event(
        correlation_id=correlation_id or new_correlation_id("storage"),
        partition=Partition.STORAGE,
        operation_name=operation_name,
        event_name=event_name,
        output_reference=output_reference,
        details=details,
    )


__all__ = [
    "EmbeddingRecord",
    "IndexCandidate",
    "IndexCommitResult",
    "InMemoryKeywordIndex",
    "InMemoryVectorIndex",
    "SparseTermsRecord",
    "VECTOR_DIMENSIONS",
    "build_keyword_index",
    "build_vector_index",
    "commit_sparse_index",
    "commit_vectors",
    "extract_sparse_terms",
    "extract_sparse_terms_for_chunks",
    "generate_embedding",
    "generate_embeddings",
    "keyword_index_from_repository",
    "run_keyword_search",
    "run_vector_search",
    "vector_index_from_repository",
]
