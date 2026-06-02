"""Dependency-free evidence reranking for early Milestone 1."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
import math
import re
from typing import Callable, Iterable, Mapping, Sequence

from shared.contracts import ErrorEnvelope, ErrorType, FallbackAction, LogEvent, Partition, new_correlation_id
from shared.policies import create_error_telemetry, create_success_log_event
from shared.records import EvidenceCandidate, RankedEvidence, RelevanceLabel, ReliabilityLevel
from shared.repository_hooks import add_repository_log, save_repository_error

try:
    from storage import InMemoryStorageRepository
except ImportError:  # pragma: no cover - keeps the type optional for isolated imports.
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]

PARTITION = "ranking"

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


Reranker = Callable[[str, Sequence[EvidenceCandidate]], Mapping[str, float] | Sequence[float]]


@dataclass(frozen=True, slots=True)
class RankingWeights:
    """Weights used by the built-in reranker or as modifiers for injected scores."""

    query_relevance: float = 0.55
    retrieval_score: float = 0.25
    source_reliability: float = 0.15
    freshness: float = 0.05


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Small configuration object for deterministic evidence selection."""

    weights: RankingWeights = RankingWeights()
    max_per_source: int = 2
    current_date: date | None = None


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Selected evidence, ranking metadata, and emitted ranking telemetry."""

    candidates: tuple[EvidenceCandidate, ...]
    ranked_evidence: tuple[RankedEvidence, ...]
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()
    deduplicated_count: int = 0
    used_fallback: bool = False


def select_ranked_evidence(
    query: str,
    candidates: Iterable[EvidenceCandidate],
    *,
    top_k: int = 5,
    config: RankingConfig | None = None,
    reranker: Reranker | None = None,
    repository: InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> RankingResult:
    """Deduplicate, rerank, diversify, and annotate evidence candidates."""

    corr = correlation_id or new_correlation_id("ranking")
    ranking_config = config or RankingConfig()
    candidate_tuple = tuple(candidates)
    deduped, deduplicated_count = _deduplicate_candidates(candidate_tuple)
    normalized = _ensure_normalized_scores(deduped)
    logs: list[LogEvent] = []
    errors: list[ErrorEnvelope] = []
    used_fallback = False

    try:
        scored = _score_candidates(query, normalized, ranking_config, reranker=reranker)
    except Exception as exc:  # noqa: BLE001 - fallback is a required safety behavior.
        used_fallback = True
        error, log = create_error_telemetry(
            correlation_id=corr,
            partition=Partition.RANKING,
            operation_name="select_ranked_evidence",
            error_type=ErrorType.MODEL,
            error_message=f"Reranker failed: {exc}",
            log_message="Reranker failed; using normalized retrieval scores.",
            fallback_action=FallbackAction.SKIP,
            event_name="reranker_fallback",
            error_details={"event_name": "reranker_fallback", "candidate_count": len(normalized)},
            log_details={"candidate_count": len(normalized)},
        )
        errors.append(error)
        _save_error(repository, error)
        logs.append(_add_log(repository, log))
        scored = _fallback_scores(normalized)

    ordered = _apply_source_diversity(scored, max_per_source=ranking_config.max_per_source)
    selected_scored = ordered[: max(top_k, 0)]
    selected_candidates = tuple(candidate for candidate, _score, _reason in selected_scored)
    ranked = tuple(
        RankedEvidence(
            evidence_id=candidate.evidence_id,
            rank=index,
            rerank_score=round(score, 6),
            relevance_label=_relevance_label(score),
            diversity_group=candidate.source_id,
            selection_reason=reason,
        )
        for index, (candidate, score, reason) in enumerate(selected_scored, start=1)
    )
    success = create_success_log_event(
        correlation_id=corr,
        partition=Partition.RANKING,
        operation_name="select_ranked_evidence",
        event_name="evidence_selected",
        message="Selected ranked evidence.",
        output_reference=",".join(candidate.evidence_id for candidate in selected_candidates) or None,
        details={
            "query": query,
            "input_count": len(candidate_tuple),
            "deduplicated_count": deduplicated_count,
            "candidate_count": len(normalized),
            "selected_count": len(selected_candidates),
            "used_fallback": used_fallback,
            "source_ids": [candidate.source_id for candidate in selected_candidates],
        },
    )
    logs.append(_add_log(repository, success))
    return RankingResult(
        candidates=selected_candidates,
        ranked_evidence=ranked,
        logs=tuple(logs),
        errors=tuple(errors),
        deduplicated_count=deduplicated_count,
        used_fallback=used_fallback,
    )


def _deduplicate_candidates(
    candidates: tuple[EvidenceCandidate, ...],
) -> tuple[tuple[EvidenceCandidate, ...], int]:
    best_by_key: dict[tuple[str | None, ...], EvidenceCandidate] = {}
    for candidate in candidates:
        key = _dedupe_key(candidate)
        current = best_by_key.get(key)
        if current is None or _retrieval_score(candidate) > _retrieval_score(current):
            best_by_key[key] = candidate
    return tuple(best_by_key.values()), len(candidates) - len(best_by_key)


def _dedupe_key(candidate: EvidenceCandidate) -> tuple[str | None, ...]:
    if candidate.source_id or candidate.chunk_id:
        return ("source_chunk", candidate.source_id, candidate.chunk_id or candidate.evidence_id)
    if candidate.citation_link:
        return ("citation", candidate.citation_link)
    snippet = (candidate.text_snippet or "").strip().lower()
    return ("snippet", snippet[:240] or candidate.evidence_id)


def _ensure_normalized_scores(candidates: tuple[EvidenceCandidate, ...]) -> tuple[EvidenceCandidate, ...]:
    missing = [candidate for candidate in candidates if candidate.normalized_score is None]
    if not missing:
        return candidates
    raw_scores = [candidate.score or 0.0 for candidate in candidates]
    low = min(raw_scores, default=0.0)
    high = max(raw_scores, default=0.0)
    normalized: list[EvidenceCandidate] = []
    for candidate in candidates:
        if candidate.normalized_score is not None:
            normalized.append(candidate)
            continue
        raw = candidate.score or 0.0
        if high == low:
            score = 1.0 if raw > 0 else 0.0
        else:
            score = (raw - low) / (high - low)
        normalized.append(replace(candidate, normalized_score=round(_clamp(score), 6)))
    return tuple(normalized)


def _score_candidates(
    query: str,
    candidates: tuple[EvidenceCandidate, ...],
    config: RankingConfig,
    *,
    reranker: Reranker | None,
) -> list[tuple[EvidenceCandidate, float, str]]:
    external_scores = _external_scores(query, candidates, reranker) if reranker is not None else None
    scored: list[tuple[EvidenceCandidate, float, str]] = []
    for candidate in candidates:
        relevance = (
            external_scores[candidate.evidence_id]
            if external_scores is not None
            else _lexical_relevance(query, candidate.text_snippet or "")
        )
        score = _weighted_score(candidate, relevance, config)
        reason = "reranker relevance with retrieval/source modifiers" if external_scores is not None else "query relevance with retrieval/source modifiers"
        scored.append((candidate, score, reason))
    return sorted(scored, key=_scored_sort_key, reverse=True)


def _external_scores(
    query: str,
    candidates: tuple[EvidenceCandidate, ...],
    reranker: Reranker,
) -> dict[str, float]:
    raw = reranker(query, candidates)
    if isinstance(raw, Mapping):
        return {candidate.evidence_id: _clamp(float(raw.get(candidate.evidence_id, 0.0))) for candidate in candidates}
    raw_sequence = list(raw)
    return {
        candidate.evidence_id: _clamp(float(raw_sequence[index])) if index < len(raw_sequence) else 0.0
        for index, candidate in enumerate(candidates)
    }


def _weighted_score(candidate: EvidenceCandidate, relevance: float, config: RankingConfig) -> float:
    weights = config.weights
    weighted_parts = (
        (_clamp(relevance), weights.query_relevance),
        (_retrieval_score(candidate), weights.retrieval_score),
        (_reliability_score(candidate.source_reliability), weights.source_reliability),
        (_freshness_score(candidate, config.current_date), weights.freshness),
    )
    weight_total = sum(weight for _value, weight in weighted_parts if weight > 0)
    if weight_total <= 0:
        return _retrieval_score(candidate)
    return sum(value * weight for value, weight in weighted_parts if weight > 0) / weight_total


def _fallback_scores(candidates: tuple[EvidenceCandidate, ...]) -> list[tuple[EvidenceCandidate, float, str]]:
    return sorted(
        ((candidate, _retrieval_score(candidate), "fallback normalized retrieval score") for candidate in candidates),
        key=_scored_sort_key,
        reverse=True,
    )


def _apply_source_diversity(
    scored: list[tuple[EvidenceCandidate, float, str]],
    *,
    max_per_source: int,
) -> list[tuple[EvidenceCandidate, float, str]]:
    if max_per_source <= 0:
        return scored

    selected: list[tuple[EvidenceCandidate, float, str]] = []
    deferred: list[tuple[EvidenceCandidate, float, str]] = []
    counts: dict[str, int] = {}
    for item in scored:
        source_id = item[0].source_id or item[0].evidence_id
        if counts.get(source_id, 0) < max_per_source:
            selected.append(item)
            counts[source_id] = counts.get(source_id, 0) + 1
        else:
            deferred.append(item)
    return [*selected, *deferred]


def _lexical_relevance(query: str, text: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    text_terms = set(_terms(text, keep_stopwords=True))
    if not text_terms:
        return 0.0
    overlap = len(set(query_terms) & text_terms) / len(set(query_terms))
    phrase_bonus = 0.15 if query.strip().lower() in text.lower() else 0.0
    return _clamp(overlap + phrase_bonus)


def _terms(text: str, *, keep_stopwords: bool = False) -> list[str]:
    terms = [match.group(0).lower() for match in re.finditer(r"[A-Za-z0-9_]+", text)]
    if keep_stopwords:
        return terms
    return [term for term in terms if term not in STOPWORDS]


def _retrieval_score(candidate: EvidenceCandidate) -> float:
    if candidate.normalized_score is not None:
        return _clamp(candidate.normalized_score)
    return _clamp(candidate.score or 0.0)


def _reliability_score(reliability: ReliabilityLevel) -> float:
    return {
        ReliabilityLevel.HIGH: 1.0,
        ReliabilityLevel.MEDIUM: 0.72,
        ReliabilityLevel.LOW: 0.35,
        ReliabilityLevel.UNVERIFIED: 0.45,
    }[reliability]


def _freshness_score(candidate: EvidenceCandidate, current_date: date | None) -> float:
    evidence_date = candidate.published_at or _datetime_date(candidate.retrieved_at)
    if evidence_date is None:
        return 0.5
    today = current_date or datetime.now(UTC).date()
    age_days = max((today - evidence_date).days, 0)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.82
    if age_days <= 365:
        return 0.62
    if age_days <= 1095:
        return 0.38
    return 0.18


def _datetime_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    return value.date()


def _relevance_label(score: float) -> RelevanceLabel:
    if score >= 0.7:
        return RelevanceLabel.HIGH
    if score >= 0.4:
        return RelevanceLabel.MEDIUM
    return RelevanceLabel.LOW


def _scored_sort_key(item: tuple[EvidenceCandidate, float, str]) -> tuple[float, float, str]:
    candidate, score, _reason = item
    return (score, _retrieval_score(candidate), candidate.evidence_id)


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _add_log(repository: InMemoryStorageRepository | None, log: LogEvent) -> LogEvent:
    return add_repository_log(repository, log, required=True)


def _save_error(repository: InMemoryStorageRepository | None, error: ErrorEnvelope) -> ErrorEnvelope:
    return save_repository_error(repository, error, required=True)


__all__ = [
    "PARTITION",
    "RankingConfig",
    "RankingResult",
    "RankingWeights",
    "Reranker",
    "select_ranked_evidence",
]
