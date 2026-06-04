"""Additive EvidenceBundle export adapter for existing MARACA records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from shared.records import (
    AnswerRecord,
    ClaimRecord,
    EvidenceCandidate,
    RankedEvidence,
    ValidationRecord,
)
from shared.serialization import serialize_contract


BUNDLE_TYPE = "maraca.evidence_bundle"
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Serialized evidence export built only from already-created records."""

    bundle_type: str
    schema_version: str
    request_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    ranked_evidence: tuple[dict[str, Any], ...]
    validations: tuple[dict[str, Any], ...]
    answers: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    evidence_sources: tuple[dict[str, Any], ...]
    validation_statuses: tuple[dict[str, Any], ...]
    validation_notes: tuple[dict[str, Any], ...]
    answer_claims: tuple[dict[str, Any], ...]
    claim_evidence: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready data using MARACA serialization."""
        return serialize_contract(
            {
                "bundle_type": self.bundle_type,
                "schema_version": self.schema_version,
                "request_ids": self.request_ids,
                "source_ids": self.source_ids,
                "evidence": self.evidence,
                "ranked_evidence": self.ranked_evidence,
                "validations": self.validations,
                "answers": self.answers,
                "claims": self.claims,
                "evidence_sources": self.evidence_sources,
                "validation_statuses": self.validation_statuses,
                "validation_notes": self.validation_notes,
                "answer_claims": self.answer_claims,
                "claim_evidence": self.claim_evidence,
            },
            tuple_as_list=True,
        )


def create_evidence_bundle(
    *records: object,
    evidence: Iterable[EvidenceCandidate] = (),
    ranked_evidence: Iterable[RankedEvidence] = (),
    validations: Iterable[ValidationRecord] = (),
    answers: Iterable[AnswerRecord] = (),
    claims: Iterable[ClaimRecord] = (),
    synthesis_result: object | None = None,
) -> EvidenceBundle:
    """Create an EvidenceBundle from existing record objects or result shapes."""
    collected = _CollectedRecords()
    for value in records:
        _collect(value, collected)
    _collect(evidence, collected)
    _collect(ranked_evidence, collected)
    _collect(validations, collected)
    _collect(answers, collected)
    _collect(claims, collected)
    _collect(synthesis_result, collected)

    evidence_payloads = tuple(_record_payload(item) for item in collected.evidence)
    ranked_payloads = tuple(_record_payload(item) for item in collected.ranked_evidence)
    validation_payloads = tuple(_record_payload(item) for item in collected.validations)
    answer_payloads = tuple(_record_payload(item) for item in collected.answers)
    claim_payloads = tuple(_record_payload(item) for item in collected.claims)

    return EvidenceBundle(
        bundle_type=BUNDLE_TYPE,
        schema_version=SCHEMA_VERSION,
        request_ids=_request_ids(collected),
        source_ids=_source_ids(collected.evidence),
        evidence=evidence_payloads,
        ranked_evidence=ranked_payloads,
        validations=validation_payloads,
        answers=answer_payloads,
        claims=claim_payloads,
        evidence_sources=_evidence_sources(collected.evidence),
        validation_statuses=_validation_statuses(collected.validations),
        validation_notes=_validation_notes(collected.validations),
        answer_claims=_answer_claims(collected.answers),
        claim_evidence=_claim_evidence(collected.claims),
    )


def export_evidence_bundle(*records: object, **kwargs: object) -> dict[str, Any]:
    """Create and serialize an EvidenceBundle payload."""
    return create_evidence_bundle(*records, **kwargs).to_dict()


@dataclass(slots=True)
class _CollectedRecords:
    evidence: list[EvidenceCandidate]
    ranked_evidence: list[RankedEvidence]
    validations: list[ValidationRecord]
    answers: list[AnswerRecord]
    claims: list[ClaimRecord]

    def __init__(self) -> None:
        self.evidence = []
        self.ranked_evidence = []
        self.validations = []
        self.answers = []
        self.claims = []


def _collect(value: object, collected: _CollectedRecords) -> None:
    if value is None:
        return
    if isinstance(value, EvidenceCandidate):
        collected.evidence.append(value)
        return
    if isinstance(value, RankedEvidence):
        collected.ranked_evidence.append(value)
        return
    if isinstance(value, ValidationRecord):
        collected.validations.append(value)
        return
    if isinstance(value, AnswerRecord):
        collected.answers.append(value)
        for claim in value.claim_records:
            if isinstance(claim, ClaimRecord):
                _append_claim(claim, collected)
        return
    if isinstance(value, ClaimRecord):
        _append_claim(value, collected)
        return
    if _looks_like_synthesis_result(value):
        _collect(getattr(value, "used_evidence", ()), collected)
        _collect(getattr(value, "answer", None), collected)
        _collect(getattr(value, "claims", ()), collected)
        return
    if isinstance(value, Iterable) and not isinstance(value, str | bytes | Mapping):
        for item in value:
            _collect(item, collected)
        return
    raise TypeError(f"Unsupported EvidenceBundle input: {type(value).__name__}")


def _append_claim(claim: ClaimRecord, collected: _CollectedRecords) -> None:
    if any(existing.claim_id == claim.claim_id for existing in collected.claims):
        return
    collected.claims.append(claim)


def _looks_like_synthesis_result(value: object) -> bool:
    return (
        not isinstance(value, type)
        and hasattr(value, "answer")
        and hasattr(value, "claims")
        and hasattr(value, "used_evidence")
    )


def _record_payload(record: object) -> dict[str, Any]:
    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        return serialize_contract(to_dict(), tuple_as_list=True)
    raise TypeError(f"EvidenceBundle record lacks to_dict(): {type(record).__name__}")


def _request_ids(collected: _CollectedRecords) -> tuple[str, ...]:
    values: list[str | None] = []
    values.extend(item.request_id for item in collected.evidence)
    values.extend(item.request_id for item in collected.validations)
    values.extend(item.request_id for item in collected.answers)
    values.extend(item.request_id for item in collected.claims)
    return _unique_present(values)


def _source_ids(evidence: Iterable[EvidenceCandidate]) -> tuple[str, ...]:
    return _unique_present(item.source_id for item in evidence)


def _evidence_sources(evidence: Iterable[EvidenceCandidate]) -> tuple[dict[str, Any], ...]:
    return tuple(
        serialize_contract(
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source_id,
                "document_id": item.document_id,
                "chunk_id": item.chunk_id,
                "citation_link": item.citation_link,
            },
            tuple_as_list=True,
        )
        for item in evidence
    )


def _validation_statuses(validations: Iterable[ValidationRecord]) -> tuple[dict[str, Any], ...]:
    return tuple(
        serialize_contract(
            {
                "validation_id": item.validation_id,
                "request_id": item.request_id,
                "evidence_ids": item.evidence_ids,
                "validation_status": item.validation_status,
                "failed_criteria": item.failed_criteria,
                "repair_action": item.repair_action,
                "stop_reason": item.stop_reason,
            },
            tuple_as_list=True,
        )
        for item in validations
    )


def _validation_notes(validations: Iterable[ValidationRecord]) -> tuple[dict[str, Any], ...]:
    return tuple(
        serialize_contract(
            {
                "validation_id": item.validation_id,
                "request_id": item.request_id,
                "validator_notes": item.validator_notes,
            },
            tuple_as_list=True,
        )
        for item in validations
        if item.validator_notes is not None
    )


def _answer_claims(answers: Iterable[AnswerRecord]) -> tuple[dict[str, Any], ...]:
    return tuple(
        serialize_contract(
            {
                "answer_id": answer.answer_id,
                "request_id": answer.request_id,
                "validation_id": answer.validation_id,
                "claim_ids": tuple(_claim_id(claim) for claim in answer.claim_records if _claim_id(claim)),
                "citation_map": answer.citation_map,
            },
            tuple_as_list=True,
        )
        for answer in answers
    )


def _claim_evidence(claims: Iterable[ClaimRecord]) -> tuple[dict[str, Any], ...]:
    return tuple(
        serialize_contract(
            {
                "claim_id": item.claim_id,
                "answer_id": item.answer_id,
                "evidence_id": item.evidence_id,
                "support_status": item.support_status,
                "support_type": item.support_type,
            },
            tuple_as_list=True,
        )
        for item in claims
    )


def _claim_id(claim: ClaimRecord | Mapping[str, Any]) -> str | None:
    if isinstance(claim, ClaimRecord):
        return claim.claim_id
    if isinstance(claim, Mapping):
        value = claim.get("claim_id")
        return value if isinstance(value, str) else None
    return None


def _unique_present(values: Iterable[str | None]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return tuple(unique)


__all__ = [
    "BUNDLE_TYPE",
    "SCHEMA_VERSION",
    "EvidenceBundle",
    "create_evidence_bundle",
    "export_evidence_bundle",
]
