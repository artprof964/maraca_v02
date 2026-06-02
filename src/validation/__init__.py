"""Dependency-free validator behavior for evidence and claim support."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
import re
from typing import Iterable, Mapping, Sequence

from shared.contracts import ErrorEnvelope, ErrorType, FallbackAction, LogEvent, Partition, new_correlation_id
from shared.policies import create_error_telemetry, create_success_log_event
from shared.repository_hooks import add_repository_log, call_repository_hook, save_repository_error
from shared.records import (
    AccessDecision,
    CitationStatus,
    ClaimRecord,
    ContradictionStatus,
    EvidenceCandidate,
    FreshnessStatus,
    ReliabilityLevel,
    RepairAction,
    RiskLevel,
    SupportStatus,
    SupportType,
    ValidationCriterion,
    ValidationRecord,
    ValidationStatus,
)

try:
    from storage import InMemoryStorageRepository
except ImportError:  # pragma: no cover - keeps validation importable by itself.
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]

PARTITION = "validation"
DEFAULT_STALE_AFTER_DAYS = 365
MIN_RELEVANCE_SCORE = 0.18
MIN_SUFFICIENCY_SCORE = 0.5
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
        "has",
        "have",
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
NEGATION_TERMS = frozenset({"no", "not", "never", "without", "cannot", "can't", "failed", "false"})
AFFIRMATION_TERMS = frozenset({"yes", "can", "does", "supports", "supported", "true", "confirmed"})


@dataclass(frozen=True, slots=True)
class EvidenceCheck:
    """Single validation criterion result."""

    criterion: ValidationCriterion
    passed: bool
    score: float | None = None
    status: str | None = None
    evidence_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


EvidenceValidationResult = EvidenceCheck


@dataclass(frozen=True, slots=True)
class ClaimSupportResult:
    """Updated claim records and support-check summary."""

    claims: tuple[ClaimRecord, ...]
    unsupported_claim_ids: tuple[str, ...] = ()
    contradicted_claim_ids: tuple[str, ...] = ()
    supported_claim_ids: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.unsupported_claim_ids and not self.contradicted_claim_ids


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validator output, updated claims, checks, logs, and errors."""

    validation: ValidationRecord
    approved_evidence: tuple[EvidenceCandidate, ...] = ()
    rejected_evidence: tuple[EvidenceCandidate, ...] = ()
    claims: tuple[ClaimRecord, ...] = ()
    checks: tuple[EvidenceCheck, ...] = ()
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[ErrorEnvelope, ...] = ()


def validate_answer_evidence(
    query: str,
    evidence: Iterable[EvidenceCandidate],
    *,
    claims: Iterable[ClaimRecord] = (),
    citation_map: Mapping[str, Sequence[str]] | None = None,
    required_validations: Iterable[ValidationCriterion] | None = None,
    required_freshness: bool = False,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    current_date: date | None = None,
    max_repair_attempts: int = 1,
    repair_attempt: int = 0,
    repository: InMemoryStorageRepository | None = None,
    correlation_id: str | None = None,
) -> ValidationResult:
    """Run access, relevance, sufficiency, freshness, contradiction, citation, and claim checks."""

    corr = correlation_id or new_correlation_id("validation")
    evidence_tuple = tuple(evidence)
    approved_evidence = tuple(candidate for candidate in evidence_tuple if _is_usable(candidate))
    rejected_evidence = tuple(candidate for candidate in evidence_tuple if candidate not in approved_evidence)
    required = (
        _default_required_validations(required_freshness)
        if required_validations is None
        else tuple(required_validations)
    )
    claim_support = check_claim_support(claims, approved_evidence)

    checks = (
        validate_access(evidence_tuple),
        validate_relevance(query, approved_evidence),
        validate_sufficiency(approved_evidence, claim_support=claim_support),
        validate_freshness(
            approved_evidence,
            required=required_freshness or ValidationCriterion.FRESHNESS in required,
            stale_after_days=stale_after_days,
            current_date=current_date,
            repository=repository,
        ),
        detect_contradictions(approved_evidence, claims=claim_support.claims, repository=repository),
        validate_citations(approved_evidence, claims=claim_support.claims, citation_map=citation_map),
    )
    checks_by_criterion = {check.criterion: check for check in checks}
    failed = [criterion for criterion in required if not checks_by_criterion[criterion].passed]
    if not claim_support.passed and ValidationCriterion.CITATION not in failed:
        failed.append(ValidationCriterion.CITATION)

    freshness_check = checks_by_criterion[ValidationCriterion.FRESHNESS]
    contradiction_check = checks_by_criterion[ValidationCriterion.CONTRADICTION]
    citation_check = checks_by_criterion[ValidationCriterion.CITATION]
    relevance_check = checks_by_criterion[ValidationCriterion.RELEVANCE]
    sufficiency_check = checks_by_criterion[ValidationCriterion.SUFFICIENCY]
    repair_action = choose_repair_action(
        failed,
        contradiction_status=ContradictionStatus(contradiction_check.status or ContradictionStatus.NONE.value),
        citation_status=CitationStatus(citation_check.status or CitationStatus.MISSING.value),
        repair_attempt=repair_attempt,
        max_repair_attempts=max_repair_attempts,
        query=query,
    )
    validation_status = _validation_status(failed, repair_action, claim_support)
    notes = _validator_notes(checks, claim_support)
    validation = ValidationRecord(
        request_id=_request_id(evidence_tuple, claim_support.claims),
        evidence_ids=[candidate.evidence_id for candidate in evidence_tuple],
        validation_status=validation_status,
        relevance_score=relevance_check.score,
        sufficiency_score=sufficiency_check.score,
        freshness_status=FreshnessStatus(freshness_check.status or FreshnessStatus.UNKNOWN.value),
        contradiction_status=ContradictionStatus(contradiction_check.status or ContradictionStatus.NONE.value),
        citation_status=CitationStatus(citation_check.status or CitationStatus.MISSING.value),
        unsupported_claim_risk=_unsupported_claim_risk(claim_support),
        repair_action=repair_action,
        failed_criteria=failed,
        stop_reason=_stop_reason(repair_action, failed),
        validator_notes=notes or None,
    )

    logs: list[LogEvent] = []
    errors: list[ErrorEnvelope] = []
    event_name = "validation_passed" if validation_status is ValidationStatus.PASS else "validation_repair_needed"
    if validation_status is ValidationStatus.FAIL:
        event_name = "validation_failed"
    logs.append(
        _add_log(
            repository,
            create_success_log_event(
                correlation_id=corr,
                partition=Partition.VALIDATION,
                operation_name="validate_answer_evidence",
                event_name=event_name,
                message="Validated answer evidence.",
                output_reference=validation.validation_id,
                details={
                    "query": query,
                    "evidence_count": len(evidence_tuple),
                    "claim_count": len(claim_support.claims),
                    "failed_criteria": [criterion.value for criterion in failed],
                    "repair_action": repair_action.value,
                },
            ),
        )
    )
    if failed:
        error_type = ErrorType.ACCESS if ValidationCriterion.ACCESS in failed else ErrorType.VALIDATION
        fallback = FallbackAction.STOP if repair_action is RepairAction.STOP else FallbackAction.REPAIR
        error, log = create_error_telemetry(
            correlation_id=corr,
            partition=Partition.VALIDATION,
            operation_name="validate_answer_evidence",
            error_type=error_type,
            error_message=f"Validation failed criteria: {', '.join(criterion.value for criterion in failed)}.",
            log_message="Validation requires repair before synthesis.",
            fallback_action=fallback,
            retryable=repair_action not in {RepairAction.STOP, RepairAction.NONE},
            event_name=event_name,
            error_details={
                "event_name": event_name,
                "validation_id": validation.validation_id,
                "repair_action": repair_action.value,
            },
            log_details={"validation_id": validation.validation_id, "repair_action": repair_action.value},
        )
        errors.append(_save_error(repository, error))
        logs.append(_add_log(repository, log))

    _save_validation(repository, validation)
    for claim in claim_support.claims:
        _save_claim(repository, claim)
    return ValidationResult(
        validation=validation,
        approved_evidence=approved_evidence,
        rejected_evidence=rejected_evidence,
        claims=claim_support.claims,
        checks=checks,
        logs=tuple(logs),
        errors=tuple(errors),
    )


def validate_evidence(
    query: str,
    evidence: Iterable[EvidenceCandidate],
    **kwargs: object,
) -> ValidationResult:
    """Alias for validating retrieved evidence before synthesis."""

    return validate_answer_evidence(query, evidence, **kwargs)


def validate_access(evidence: Iterable[EvidenceCandidate]) -> EvidenceCheck:
    """Fail closed unless every candidate is explicitly allowed."""

    denied: list[str] = []
    unknown: list[str] = []
    for candidate in evidence:
        if candidate.access_decision is AccessDecision.ALLOWED:
            continue
        if candidate.access_decision is AccessDecision.DENIED:
            denied.append(candidate.evidence_id)
        else:
            unknown.append(candidate.evidence_id)
    notes = []
    if denied:
        notes.append(f"denied={','.join(denied)}")
    if unknown:
        notes.append(f"unknown={','.join(unknown)}")
    return EvidenceCheck(
        criterion=ValidationCriterion.ACCESS,
        passed=not denied and not unknown,
        status="allowed" if not denied and not unknown else "blocked",
        evidence_ids=tuple([*denied, *unknown]),
        notes=tuple(notes),
    )


def validate_relevance(query: str, evidence: Iterable[EvidenceCandidate]) -> EvidenceCheck:
    """Score query/evidence lexical overlap with retrieval-score support."""

    candidates = tuple(evidence)
    if not candidates:
        return EvidenceCheck(ValidationCriterion.RELEVANCE, False, score=0.0, status="missing", notes=("no evidence",))
    scores = [_candidate_relevance(query, candidate) for candidate in candidates]
    score = round(sum(scores) / len(scores), 6)
    return EvidenceCheck(
        criterion=ValidationCriterion.RELEVANCE,
        passed=score >= MIN_RELEVANCE_SCORE,
        score=score,
        status="relevant" if score >= MIN_RELEVANCE_SCORE else "weak",
    )


def validate_sufficiency(
    evidence: Iterable[EvidenceCandidate],
    *,
    claim_support: ClaimSupportResult | None = None,
    min_score: float = MIN_SUFFICIENCY_SCORE,
) -> EvidenceCheck:
    """Check that enough accessible, citeable evidence exists to support the answer."""

    candidates = tuple(evidence)
    usable = [candidate for candidate in candidates if _is_usable(candidate)]
    reliability_bonus = max((_reliability_score(candidate) for candidate in usable), default=0.0) * 0.25
    count_score = min(1.0, len(usable) / 2)
    support_score = 1.0
    if claim_support is not None and claim_support.claims:
        support_score = len(claim_support.supported_claim_ids) / len(claim_support.claims)
    score = round(min(1.0, (count_score * 0.55) + (support_score * 0.2) + reliability_bonus), 6)
    return EvidenceCheck(
        criterion=ValidationCriterion.SUFFICIENCY,
        passed=score >= min_score,
        score=score,
        status="sufficient" if score >= min_score else "insufficient",
        evidence_ids=tuple(candidate.evidence_id for candidate in usable),
    )


def validate_freshness(
    evidence: Iterable[EvidenceCandidate],
    *,
    required: bool = False,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    current_date: date | None = None,
    repository: InMemoryStorageRepository | None = None,
) -> EvidenceCheck:
    """Flag stale evidence by published, retrieved, as-of, document, or chunk dates."""

    today = current_date or datetime.now(UTC).date()
    stale: list[str] = []
    unknown: list[str] = []
    fresh_count = 0
    for candidate in evidence:
        evidence_date = _evidence_date(candidate, repository)
        if evidence_date is None:
            unknown.append(candidate.evidence_id)
            continue
        if (today - evidence_date).days > stale_after_days:
            stale.append(candidate.evidence_id)
        else:
            fresh_count += 1
    if stale:
        status = FreshnessStatus.STALE
    elif unknown and required:
        status = FreshnessStatus.UNKNOWN
    elif unknown:
        status = FreshnessStatus.ACCEPTABLE
    else:
        status = FreshnessStatus.FRESH
    passed = not stale and not (required and unknown)
    total = fresh_count + len(stale) + len(unknown)
    score = round(fresh_count / total, 6) if total else 0.0
    return EvidenceCheck(
        criterion=ValidationCriterion.FRESHNESS,
        passed=passed,
        score=score,
        status=status.value,
        evidence_ids=tuple([*stale, *unknown]),
        notes=(f"stale_after_days={stale_after_days}",),
    )


def detect_contradictions(
    evidence: Iterable[EvidenceCandidate],
    *,
    claims: Iterable[ClaimRecord] = (),
    repository: InMemoryStorageRepository | None = None,
) -> EvidenceCheck:
    """Detect relation-level and text-level contradiction signals."""

    candidates = tuple(evidence)
    relation_conflicts = _relation_contradictions(candidates, repository)
    text_conflicts = _text_contradictions(candidates, tuple(claims))
    conflict_ids = tuple(dict.fromkeys([*relation_conflicts, *text_conflicts]))
    status = ContradictionStatus.NONE
    if relation_conflicts:
        status = ContradictionStatus.CONFIRMED
    elif text_conflicts:
        status = ContradictionStatus.POSSIBLE
    return EvidenceCheck(
        criterion=ValidationCriterion.CONTRADICTION,
        passed=status is ContradictionStatus.NONE,
        status=status.value,
        evidence_ids=conflict_ids,
    )


def validate_citations(
    evidence: Iterable[EvidenceCandidate],
    *,
    claims: Iterable[ClaimRecord] = (),
    citation_map: Mapping[str, Sequence[str]] | None = None,
) -> EvidenceCheck:
    """Require evidence identifiers and source-backed citation references."""

    candidates = tuple(evidence)
    candidate_by_id = {candidate.evidence_id: candidate for candidate in candidates}
    missing: list[str] = []
    weak: list[str] = []
    complete = 0
    for candidate in candidates:
        if not candidate.evidence_id:
            missing.append(candidate.evidence_id)
        elif candidate.citation_link:
            complete += 1
        elif candidate.source_id or candidate.document_id or candidate.chunk_id:
            weak.append(candidate.evidence_id)
        else:
            missing.append(candidate.evidence_id)
    for claim in claims:
        if not claim.evidence_id or claim.evidence_id not in candidate_by_id:
            missing.append(claim.claim_id)
            continue
        citations = tuple(citation_map.get(claim.claim_id, ())) if citation_map is not None else ()
        if citation_map is not None and claim.evidence_id not in citations:
            missing.append(claim.claim_id)
    if missing:
        status = CitationStatus.MISSING
    elif weak:
        status = CitationStatus.WEAK
    elif candidates or tuple(claims):
        status = CitationStatus.COMPLETE
    else:
        status = CitationStatus.MISSING
    passed = status in {CitationStatus.COMPLETE, CitationStatus.WEAK}
    score = round(complete / len(candidates), 6) if candidates else 0.0
    return EvidenceCheck(
        criterion=ValidationCriterion.CITATION,
        passed=passed,
        score=score,
        status=status.value,
        evidence_ids=tuple(dict.fromkeys([*missing, *weak])),
    )


def check_claim_support(
    claims: Iterable[ClaimRecord],
    evidence: Iterable[EvidenceCandidate],
) -> ClaimSupportResult:
    """Return claim records annotated with deterministic support status."""

    candidates = tuple(evidence)
    by_id = {candidate.evidence_id: candidate for candidate in candidates}
    supported: list[str] = []
    unsupported: list[str] = []
    contradicted: list[str] = []
    checked: list[ClaimRecord] = []
    for claim in claims:
        candidate = by_id.get(claim.evidence_id or "")
        status = SupportStatus.UNSUPPORTED
        support_type = SupportType.UNSUPPORTED
        confidence = 0.0
        notes = "No matching evidence was available."
        if candidate is not None:
            support = _support_score(claim, candidate)
            confidence = round(support, 6)
            if _claim_contradicted_by_evidence(claim.claim_text, candidate.text_snippet or ""):
                status = SupportStatus.CONTRADICTED
                notes = "Evidence contains a contradiction signal for the claim."
            elif support >= 0.72:
                status = SupportStatus.SUPPORTED
                support_type = SupportType.DIRECT_QUOTE if _quote_supported(claim, candidate) else SupportType.PARAPHRASE
                notes = "Claim is supported by the cited evidence."
            elif support >= 0.35:
                status = SupportStatus.PARTIALLY_SUPPORTED
                support_type = SupportType.PARAPHRASE
                notes = "Claim is partially supported by the cited evidence."
            else:
                notes = "Claim terms are not sufficiently present in the cited evidence."
        updated = replace(
            claim,
            support_status=status,
            support_type=support_type,
            confidence=confidence,
            validator_notes=notes,
        )
        checked.append(updated)
        if status is SupportStatus.CONTRADICTED:
            contradicted.append(updated.claim_id)
        elif status in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}:
            supported.append(updated.claim_id)
        else:
            unsupported.append(updated.claim_id)
    return ClaimSupportResult(
        claims=tuple(checked),
        unsupported_claim_ids=tuple(unsupported),
        contradicted_claim_ids=tuple(contradicted),
        supported_claim_ids=tuple(supported),
    )


validate_claim_support = check_claim_support


def choose_repair_action(
    failed_criteria: Iterable[ValidationCriterion],
    *,
    contradiction_status: ContradictionStatus = ContradictionStatus.NONE,
    citation_status: CitationStatus = CitationStatus.COMPLETE,
    repair_attempt: int = 0,
    max_repair_attempts: int = 1,
    query: str = "",
) -> RepairAction:
    """Select the next repair action from failed criteria and loop limits."""

    failed = set(failed_criteria)
    if not failed:
        return RepairAction.NONE
    if repair_attempt >= max_repair_attempts:
        return RepairAction.STOP
    if ValidationCriterion.ACCESS in failed:
        return RepairAction.STOP
    if contradiction_status is ContradictionStatus.CONFIRMED:
        return RepairAction.STOP
    if _underspecified(query):
        return RepairAction.CLARIFY
    if ValidationCriterion.FRESHNESS in failed:
        return RepairAction.EXTERNAL_LOOKUP
    if ValidationCriterion.CONTRADICTION in failed:
        return RepairAction.RETRIEVE_MORE
    if ValidationCriterion.SUFFICIENCY in failed:
        return RepairAction.RETRIEVE_MORE
    if ValidationCriterion.RELEVANCE in failed:
        return RepairAction.REWRITE
    if ValidationCriterion.CITATION in failed:
        return RepairAction.STOP if citation_status is CitationStatus.MISSING else RepairAction.RETRIEVE_MORE
    return RepairAction.RETRIEVE_MORE


select_repair_action = choose_repair_action


def persist_validation_result(
    repository: InMemoryStorageRepository,
    result: ValidationResult,
) -> ValidationResult:
    """Persist a validation result into repositories that expose save hooks."""

    _save_validation(repository, result.validation)
    for claim in result.claims:
        _save_claim(repository, claim)
    for log in result.logs:
        _add_log(repository, log)
    for error in result.errors:
        _save_error(repository, error)
    return result


store_validation_result = persist_validation_result
validate_contradictions = detect_contradictions
validate_citation_support = validate_citations


def _default_required_validations(required_freshness: bool) -> tuple[ValidationCriterion, ...]:
    criteria = [
        ValidationCriterion.ACCESS,
        ValidationCriterion.RELEVANCE,
        ValidationCriterion.SUFFICIENCY,
        ValidationCriterion.CITATION,
        ValidationCriterion.CONTRADICTION,
    ]
    if required_freshness:
        criteria.append(ValidationCriterion.FRESHNESS)
    return tuple(criteria)


def _candidate_relevance(query: str, candidate: EvidenceCandidate) -> float:
    lexical = _lexical_overlap(query, candidate.text_snippet or "")
    retrieval = candidate.normalized_score if candidate.normalized_score is not None else candidate.score
    retrieval_score = _clamp(retrieval or 0.0)
    return round((lexical * 0.7) + (retrieval_score * 0.3), 6)


def _lexical_overlap(left: str, right: str) -> float:
    left_terms = set(_terms(left))
    right_terms = set(_terms(right))
    if not left_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms)


def _support_score(claim: ClaimRecord, candidate: EvidenceCandidate) -> float:
    snippet = candidate.text_snippet or ""
    span = claim.evidence_span or ""
    quote = claim.source_quote or ""
    direct = 1.0 if (quote and quote.lower() in snippet.lower()) or (span and span == candidate.chunk_id) else 0.0
    lexical = _lexical_overlap(claim.claim_text, snippet)
    reliability = _reliability_score(candidate)
    return _clamp((direct * 0.35) + (lexical * 0.45) + (reliability * 0.2))


def _quote_supported(claim: ClaimRecord, candidate: EvidenceCandidate) -> bool:
    quote = (claim.source_quote or "").strip().lower()
    return bool(quote and quote in (candidate.text_snippet or "").lower())


def _is_usable(candidate: EvidenceCandidate) -> bool:
    return (
        candidate.access_decision is AccessDecision.ALLOWED
        and bool((candidate.text_snippet or "").strip())
        and bool(candidate.citation_link or candidate.source_id or candidate.document_id or candidate.chunk_id)
    )


def _reliability_score(candidate: EvidenceCandidate) -> float:
    return {
        ReliabilityLevel.HIGH: 1.0,
        ReliabilityLevel.MEDIUM: 0.7,
        ReliabilityLevel.LOW: 0.35,
        ReliabilityLevel.UNVERIFIED: 0.45,
    }[candidate.source_reliability]


def _evidence_date(candidate: EvidenceCandidate, repository: InMemoryStorageRepository | None) -> date | None:
    if candidate.published_at is not None:
        return candidate.published_at
    if candidate.retrieved_at is not None:
        return candidate.retrieved_at.date()
    if repository is not None and candidate.chunk_id:
        chunk = getattr(repository, "chunks", {}).get(candidate.chunk_id)
        if chunk is not None:
            if getattr(chunk, "as_of_date", None) is not None:
                return chunk.as_of_date
            if getattr(chunk, "created_at", None) is not None:
                return chunk.created_at.date()
    if repository is not None and candidate.document_id:
        document = getattr(repository, "documents", {}).get(candidate.document_id)
        if document is not None:
            return document.as_of_date or document.published_at or (
                document.retrieved_at.date() if document.retrieved_at else None
            )
    return None


def _relation_contradictions(
    candidates: tuple[EvidenceCandidate, ...],
    repository: InMemoryStorageRepository | None,
) -> tuple[str, ...]:
    if repository is None:
        return ()
    relations = getattr(repository, "relations", {})
    conflicts: list[str] = []
    for candidate in candidates:
        for relation_id in candidate.relation_ids:
            relation = relations.get(relation_id)
            relation_type = getattr(getattr(relation, "relation_type", None), "value", None)
            if relation_type == "contradicts":
                conflicts.append(candidate.evidence_id)
    return tuple(conflicts)


def _text_contradictions(
    candidates: tuple[EvidenceCandidate, ...],
    claims: tuple[ClaimRecord, ...],
) -> tuple[str, ...]:
    conflicts: list[str] = []
    for claim in claims:
        candidate = next((item for item in candidates if item.evidence_id == claim.evidence_id), None)
        if candidate is not None and _claim_contradicted_by_evidence(claim.claim_text, candidate.text_snippet or ""):
            conflicts.append(candidate.evidence_id)
    for first_index, first in enumerate(candidates):
        for second in candidates[first_index + 1 :]:
            overlap = _lexical_overlap(first.text_snippet or "", second.text_snippet or "")
            if overlap >= 0.45 and _opposite_polarity(first.text_snippet or "", second.text_snippet or ""):
                conflicts.extend([first.evidence_id, second.evidence_id])
    return tuple(dict.fromkeys(conflicts))


def _claim_contradicted_by_evidence(claim_text: str, evidence_text: str) -> bool:
    overlap = _lexical_overlap(claim_text, evidence_text)
    return overlap >= 0.35 and _opposite_polarity(claim_text, evidence_text)


def _opposite_polarity(left: str, right: str) -> bool:
    left_terms = set(_terms(left, include_stopwords=True))
    right_terms = set(_terms(right, include_stopwords=True))
    left_negative = bool(left_terms & NEGATION_TERMS)
    right_negative = bool(right_terms & NEGATION_TERMS)
    if left_negative != right_negative:
        return True
    left_affirmative = bool(left_terms & AFFIRMATION_TERMS)
    right_affirmative = bool(right_terms & AFFIRMATION_TERMS)
    return left_affirmative != right_affirmative and (left_negative or right_negative)


def _validation_status(
    failed: Sequence[ValidationCriterion],
    repair_action: RepairAction,
    claim_support: ClaimSupportResult,
) -> ValidationStatus:
    if not failed and claim_support.passed:
        return ValidationStatus.PASS
    if repair_action is RepairAction.CLARIFY:
        return ValidationStatus.CLARIFICATION_NEEDED
    if repair_action is RepairAction.STOP:
        return ValidationStatus.FAIL
    return ValidationStatus.REPAIR_NEEDED


def _unsupported_claim_risk(claim_support: ClaimSupportResult) -> RiskLevel:
    if claim_support.contradicted_claim_ids:
        return RiskLevel.HIGH
    if claim_support.unsupported_claim_ids:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _validator_notes(checks: Iterable[EvidenceCheck], claim_support: ClaimSupportResult) -> str:
    notes: list[str] = []
    for check in checks:
        if check.passed:
            continue
        detail = check.status or "failed"
        notes.append(f"{check.criterion.value}:{detail}")
    if claim_support.unsupported_claim_ids:
        notes.append("unsupported_claims:" + ",".join(claim_support.unsupported_claim_ids))
    if claim_support.contradicted_claim_ids:
        notes.append("contradicted_claims:" + ",".join(claim_support.contradicted_claim_ids))
    return "; ".join(notes)


def _stop_reason(repair_action: RepairAction, failed: Sequence[ValidationCriterion]) -> str | None:
    if repair_action is not RepairAction.STOP:
        return None
    if ValidationCriterion.ACCESS in failed:
        return "Access validation failed closed."
    if ValidationCriterion.CITATION in failed:
        return "Citation support is missing."
    if ValidationCriterion.CONTRADICTION in failed:
        return "Confirmed contradiction requires human-safe disclosure or more evidence."
    return "Repair attempts exhausted."


def _request_id(evidence: tuple[EvidenceCandidate, ...], claims: tuple[ClaimRecord, ...]) -> str:
    if evidence:
        return evidence[0].request_id
    if claims:
        return claims[0].request_id
    return new_correlation_id("request")


def _underspecified(query: str) -> bool:
    return len(_terms(query)) < 2


def _terms(text: str, *, include_stopwords: bool = False) -> list[str]:
    terms = [match.group(0).lower() for match in re.finditer(r"[A-Za-z0-9_']+", text)]
    if include_stopwords:
        return terms
    return [term for term in terms if term not in STOPWORDS]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _add_log(repository: InMemoryStorageRepository | None, log: LogEvent) -> LogEvent:
    return add_repository_log(repository, log)


def _save_error(repository: InMemoryStorageRepository | None, error: ErrorEnvelope) -> ErrorEnvelope:
    return save_repository_error(repository, error)


def _save_validation(repository: InMemoryStorageRepository | None, validation: ValidationRecord) -> ValidationRecord:
    call_repository_hook(repository, "save_validation_record", validation)
    return validation


def _save_claim(repository: InMemoryStorageRepository | None, claim: ClaimRecord) -> ClaimRecord:
    call_repository_hook(repository, "save_claim_record", claim)
    return claim


__all__ = [
    "PARTITION",
    "ClaimSupportResult",
    "EvidenceCheck",
    "EvidenceValidationResult",
    "ValidationResult",
    "check_claim_support",
    "choose_repair_action",
    "detect_contradictions",
    "persist_validation_result",
    "select_repair_action",
    "store_validation_result",
    "validate_access",
    "validate_answer_evidence",
    "validate_citation_support",
    "validate_citations",
    "validate_claim_support",
    "validate_contradictions",
    "validate_evidence",
    "validate_freshness",
    "validate_relevance",
    "validate_sufficiency",
]
