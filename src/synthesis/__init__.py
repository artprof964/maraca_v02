"""Dependency-free cited synthesis for early Milestone 1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import re
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

from shared.contracts import ErrorEnvelope, ErrorType, FallbackAction, LogEvent, Partition, new_correlation_id
from shared.policies import create_error_telemetry, create_success_log_event
from shared.repository_hooks import add_repository_log, save_repository_error
from shared.records import (
    AccessDecision,
    AnswerRecord,
    ClaimRecord,
    ConfidenceLevel,
    EvidenceCandidate,
    RankedEvidence,
    ReliabilityLevel,
    SupportStatus,
    SupportType,
    ValidationRecord,
    ValidationStatus,
)

try:
    from storage import InMemoryStorageRepository
except ImportError:  # pragma: no cover - keeps the type optional for isolated imports.
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]

PARTITION = "synthesis"

STALE_AFTER_DAYS = 365


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """Generated answer, claim records, and emitted synthesis telemetry."""

    answer: AnswerRecord
    claims: tuple[ClaimRecord, ...]
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()
    used_evidence: tuple[EvidenceCandidate, ...] = ()


def generate_answer(
    query: str,
    evidence: Iterable[EvidenceCandidate],
    *,
    ranked_evidence: Iterable[RankedEvidence] = (),
    validation: ValidationRecord | None = None,
    max_claims: int = 3,
    current_date: date | None = None,
    repository: InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> SynthesisResult:
    """Create a concise cited answer using only allowed retrieved evidence."""

    corr = correlation_id or new_correlation_id("synthesis")
    evidence_tuple = tuple(evidence)
    ordered_evidence = _approved_evidence_in_rank_order(evidence_tuple, tuple(ranked_evidence))
    limitations = _limitations(
        query,
        evidence_tuple,
        ordered_evidence,
        validation=validation,
        current_date=current_date,
    )
    answer_id = f"answer_{uuid4().hex}"
    selected = ordered_evidence[: max(max_claims, 0)]
    claims = create_claim_records(query, selected, answer_id=answer_id)
    citation_map = attach_citations(claims, selected)
    answer_text = _answer_text(claims, citation_map)
    confidence = _confidence_level(claims, limitations, validation=validation)

    answer = AnswerRecord(
        request_id=_request_id(evidence_tuple, validation),
        answer_id=answer_id,
        answer_text=answer_text,
        validation_id=validation.validation_id if validation is not None else None,
        citation_map=citation_map,
        claim_records=list(claims),
        confidence_level=confidence,
        limitations=limitations,
        model_used="dependency-free-cited-synthesis",
    )

    logs: list[LogEvent] = []
    errors: list[ErrorEnvelope] = []
    claim_log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.SYNTHESIS,
        operation_name="create_claim_records",
        event_name="claim_records_created",
        message="Created cited claim records.",
        output_reference=",".join(claim.claim_id for claim in claims) or None,
        details={
            "query": query,
            "approved_evidence_count": len(ordered_evidence),
            "claim_count": len(claims),
        },
    )
    logs.append(_add_log(repository, claim_log))

    if claims:
        citation_log = create_success_log_event(
            correlation_id=corr,
            partition=Partition.SYNTHESIS,
            operation_name="attach_citations",
            event_name="citations_attached",
            message="Attached citations to claim records.",
            output_reference=answer.answer_id,
            details={
                "query": query,
                "answer_id": answer.answer_id,
                "claim_count": len(claims),
                "citation_count": sum(len(citations) for citations in citation_map.values()),
            },
        )
        logs.append(_add_log(repository, citation_log))

    if not claims:
        error, log = create_error_telemetry(
            correlation_id=corr,
            partition=Partition.SYNTHESIS,
            operation_name="generate_answer",
            error_type=ErrorType.VALIDATION,
            error_message="No approved cited evidence was available for synthesis.",
            log_message="No approved cited evidence was available for synthesis.",
            fallback_action=FallbackAction.STOP,
            event_name="insufficient_cited_evidence",
            error_details={"event_name": "insufficient_cited_evidence", "query": query},
            log_details={"query": query},
        )
        errors.append(_save_error(repository, error))
        logs.append(_add_log(repository, log))

    answer_log = create_success_log_event(
        correlation_id=corr,
        partition=Partition.SYNTHESIS,
        operation_name="generate_answer",
        event_name="answer_generated",
        message="Generated cited answer.",
        output_reference=answer.answer_id,
        details={
            "query": query,
            "answer_id": answer.answer_id,
            "claim_count": len(claims),
            "citation_count": sum(len(citations) for citations in citation_map.values()),
            "limitation_count": len(limitations),
        },
    )
    logs.append(_add_log(repository, answer_log))
    return SynthesisResult(
        answer=answer,
        claims=claims,
        logs=tuple(logs),
        errors=tuple(errors),
        used_evidence=selected,
    )


def create_claim_records(
    query: str,
    evidence: Iterable[EvidenceCandidate],
    *,
    answer_id: str | None = None,
) -> tuple[ClaimRecord, ...]:
    """Create one supported claim per citeable evidence snippet."""

    claims: list[ClaimRecord] = []
    for candidate in evidence:
        if not _is_approved(candidate):
            continue
        claim_text = _claim_text(query, candidate.text_snippet or "")
        if not claim_text:
            continue
        claims.append(
            ClaimRecord(
                request_id=candidate.request_id,
                answer_id=answer_id,
                claim_text=claim_text,
                support_type=SupportType.PARAPHRASE,
                evidence_id=candidate.evidence_id,
                evidence_span=_evidence_span(candidate),
                source_quote=_source_quote(candidate.text_snippet or ""),
                support_status=SupportStatus.SUPPORTED,
                confidence=_claim_confidence(candidate),
            )
        )
    return tuple(claims)


def attach_citations(
    claims: Iterable[ClaimRecord],
    evidence: Iterable[EvidenceCandidate],
) -> dict[str, list[str]]:
    """Map each claim ID to the supporting evidence ID and citation link."""

    by_id = {candidate.evidence_id: candidate for candidate in evidence}
    citation_map: dict[str, list[str]] = {}
    for claim in claims:
        if claim.evidence_id is None:
            continue
        candidate = by_id.get(claim.evidence_id)
        if candidate is None:
            continue
        citations = [claim.evidence_id]
        if candidate.citation_link:
            citations.append(candidate.citation_link)
        citation_map[claim.claim_id] = citations
    return citation_map


def _approved_evidence_in_rank_order(
    evidence: tuple[EvidenceCandidate, ...],
    ranked_evidence: tuple[RankedEvidence, ...],
) -> tuple[EvidenceCandidate, ...]:
    approved = [candidate for candidate in evidence if _is_approved(candidate)]
    if not ranked_evidence:
        return tuple(approved)

    by_id = {candidate.evidence_id: candidate for candidate in approved}
    ordered: list[EvidenceCandidate] = []
    seen: set[str] = set()
    for ranked in sorted(ranked_evidence, key=lambda item: item.rank):
        candidate = by_id.get(ranked.evidence_id)
        if candidate is None:
            continue
        ordered.append(candidate)
        seen.add(candidate.evidence_id)
    ordered.extend(candidate for candidate in approved if candidate.evidence_id not in seen)
    return tuple(ordered)


def _is_approved(candidate: EvidenceCandidate) -> bool:
    if candidate.access_decision is not AccessDecision.ALLOWED:
        return False
    if not (candidate.text_snippet or "").strip():
        return False
    return bool(candidate.evidence_id and (candidate.citation_link or candidate.source_id or candidate.chunk_id))


def _limitations(
    query: str,
    all_evidence: tuple[EvidenceCandidate, ...],
    approved_evidence: tuple[EvidenceCandidate, ...],
    *,
    validation: ValidationRecord | None,
    current_date: date | None,
) -> list[str]:
    limitations: list[str] = []
    if not all_evidence:
        limitations.append("No retrieved evidence was available for this query.")
    elif not approved_evidence:
        limitations.append("No approved accessible evidence was available for this query.")
    elif len(approved_evidence) == 1:
        limitations.append("Only one approved evidence item supported the answer.")

    missing_citations = [candidate.evidence_id for candidate in approved_evidence if not candidate.citation_link]
    if missing_citations:
        limitations.append("Some supporting evidence lacked direct citation links.")

    stale_ids = _stale_evidence_ids(approved_evidence, current_date=current_date)
    if stale_ids:
        limitations.append("Some supporting evidence may be stale.")

    low_reliability = [
        candidate.evidence_id
        for candidate in approved_evidence
        if candidate.source_reliability in {ReliabilityLevel.LOW, ReliabilityLevel.UNVERIFIED}
    ]
    if low_reliability:
        limitations.append("Some supporting evidence came from low or unverified reliability sources.")

    if validation is not None and validation.validation_status is not ValidationStatus.PASS:
        limitations.append("Validation did not fully pass, so the answer is limited to directly cited evidence.")

    if not _terms(query):
        limitations.append("The query did not contain enough specific terms to broaden the answer safely.")

    return list(dict.fromkeys(limitations))


def _stale_evidence_ids(
    evidence: Sequence[EvidenceCandidate],
    *,
    current_date: date | None,
) -> list[str]:
    today = current_date or datetime.now(UTC).date()
    stale: list[str] = []
    for candidate in evidence:
        evidence_date = candidate.published_at or (candidate.retrieved_at.date() if candidate.retrieved_at else None)
        if evidence_date is None:
            continue
        if (today - evidence_date).days > STALE_AFTER_DAYS:
            stale.append(candidate.evidence_id)
    return stale


def _answer_text(claims: tuple[ClaimRecord, ...], citation_map: Mapping[str, list[str]]) -> str:
    if not claims:
        return "I do not have enough approved cited evidence to answer this query."

    sentences: list[str] = []
    link_notes: list[str] = []
    for index, claim in enumerate(claims, start=1):
        sentences.append(f"{claim.claim_text} [{index}]")
        citations = citation_map.get(claim.claim_id, [])
        if len(citations) > 1:
            link_notes.append(f"[{index}] {citations[1]}")
    if link_notes:
        return " ".join(sentences) + "\n\nCitations: " + "; ".join(link_notes)
    return " ".join(sentences)


def _claim_text(query: str, snippet: str) -> str:
    sentences = _sentences(snippet)
    if not sentences:
        return ""
    query_terms = set(_terms(query))
    if query_terms:
        sentences = sorted(sentences, key=lambda sentence: len(query_terms & set(_terms(sentence))), reverse=True)
    return _clean_sentence(sentences[0])


def _sentences(text: str) -> list[str]:
    compact = " ".join(text.strip().split())
    if not compact:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]
    return parts or [compact]


def _clean_sentence(sentence: str) -> str:
    cleaned = sentence.strip()
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _source_quote(snippet: str) -> str:
    sentence = _sentences(snippet)
    quote = sentence[0] if sentence else snippet.strip()
    return quote[:500]


def _evidence_span(candidate: EvidenceCandidate) -> str | None:
    if candidate.chunk_id:
        return candidate.chunk_id
    if candidate.citation_link:
        return candidate.citation_link
    return None


def _claim_confidence(candidate: EvidenceCandidate) -> float:
    score = candidate.normalized_score if candidate.normalized_score is not None else candidate.score
    retrieval_score = _clamp(score or 0.0)
    reliability = {
        ReliabilityLevel.HIGH: 1.0,
        ReliabilityLevel.MEDIUM: 0.72,
        ReliabilityLevel.LOW: 0.35,
        ReliabilityLevel.UNVERIFIED: 0.45,
    }[candidate.source_reliability]
    return round((retrieval_score * 0.6) + (reliability * 0.4), 6)


def _confidence_level(
    claims: tuple[ClaimRecord, ...],
    limitations: Sequence[str],
    *,
    validation: ValidationRecord | None,
) -> ConfidenceLevel:
    if not claims:
        return ConfidenceLevel.LOW
    if validation is not None and validation.validation_status is not ValidationStatus.PASS:
        return ConfidenceLevel.LOW
    average = sum(claim.confidence or 0.0 for claim in claims) / len(claims)
    if average >= 0.78 and len(limitations) <= 1:
        return ConfidenceLevel.HIGH
    if average >= 0.5:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _request_id(
    evidence: tuple[EvidenceCandidate, ...],
    validation: ValidationRecord | None,
) -> str:
    if validation is not None:
        return validation.request_id
    if evidence:
        return evidence[0].request_id
    return new_correlation_id("request")


def _terms(text: str) -> list[str]:
    return [match.group(0).lower() for match in re.finditer(r"[A-Za-z0-9_]+", text)]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _add_log(repository: InMemoryStorageRepository | None, log: LogEvent) -> LogEvent:
    return add_repository_log(repository, log, required=True)


def _save_error(repository: InMemoryStorageRepository | None, error: ErrorEnvelope) -> ErrorEnvelope:
    return save_repository_error(repository, error, required=True)


__all__ = [
    "PARTITION",
    "STALE_AFTER_DAYS",
    "SynthesisResult",
    "attach_citations",
    "create_claim_records",
    "generate_answer",
]
