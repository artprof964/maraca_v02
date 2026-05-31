"""Lightweight shared data records for Milestone 0 and early Milestone 1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .contracts import _serialize_contract, _utc_now


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SourceType(StrEnum):
    DOCUMENT = "document"
    DATABASE = "database"
    API = "api"
    WEB = "web"
    TABLE = "table"
    LOG = "log"
    TICKET = "ticket"
    REPORT = "report"
    PAPER = "paper"
    REPOSITORY = "repository"
    OTHER = "other"


class AccessMethod(StrEnum):
    UPLOAD = "upload"
    CONNECTOR = "connector"
    URL = "url"
    API = "api"
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    MANUAL = "manual"


class LicensePolicy(StrEnum):
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    UNKNOWN = "unknown"


class ReliabilityLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


class FreshnessPolicy(StrEnum):
    STATIC = "static"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event-driven"
    REAL_TIME = "real-time"
    MANUAL = "manual"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"
    FAILED = "failed"


class IngestionTriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    DEPENDENCY = "dependency"
    REPAIR = "repair"


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentType(StrEnum):
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    DATABASE_ROW_SET = "database_row_set"
    API_RESPONSE = "api_response"
    TRANSCRIPT = "transcript"
    OTHER = "other"


class AccessLevel(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    CONCEPT = "concept"
    DATE = "date"
    LOCATION = "location"
    DATASET = "dataset"
    SYSTEM = "system"
    METHOD = "method"
    PAPER = "paper"
    OTHER = "other"


class RelationType(StrEnum):
    DEPENDS_ON = "depends_on"
    AUTHORED_BY = "authored_by"
    CITES = "cites"
    BELONGS_TO = "belongs_to"
    CAUSED_BY = "caused_by"
    UPDATES = "updates"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    SIMILAR_TO = "similar_to"
    OTHER = "other"


class RequiredFreshness(StrEnum):
    NONE = "none"
    RECENT = "recent"
    DATE_BOUNDED = "date-bounded"
    REAL_TIME = "real-time"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutputIntent(StrEnum):
    ANSWER = "answer"
    COMPARISON = "comparison"
    SUMMARY = "summary"
    AUDIT = "audit"
    EXTRACTION = "extraction"
    RECOMMENDATION = "recommendation"


class QueryType(StrEnum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    ENTITY = "entity"
    GRAPH = "graph"
    MULTI_HOP = "multi-hop"
    FRESH_DATA = "fresh-data"
    HIGH_RISK = "high-risk"
    MIXED = "mixed"


class RetrievalMode(StrEnum):
    NO_RETRIEVAL = "no_retrieval"
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"
    GRAPH = "graph"
    DATABASE = "database"
    API = "api"
    EXTERNAL = "external"
    ITERATIVE = "iterative"


class ValidationCriterion(StrEnum):
    RELEVANCE = "relevance"
    SUFFICIENCY = "sufficiency"
    FRESHNESS = "freshness"
    CITATION = "citation"
    CONTRADICTION = "contradiction"
    ACCESS = "access"


class PlanFallbackAction(StrEnum):
    REWRITE = "rewrite"
    EXPAND_GRAPH = "expand_graph"
    ADD_KEYWORD = "add_keyword"
    ADD_VECTOR = "add_vector"
    EXTERNAL_LOOKUP = "external_lookup"
    CLARIFY = "clarify"
    FAIL_WITH_UNCERTAINTY = "fail_with_uncertainty"


class AccessDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REDACTED = "redacted"
    UNKNOWN = "unknown"


class RelevanceLabel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationStatus(StrEnum):
    PASS = "pass"
    REPAIR_NEEDED = "repair_needed"
    CLARIFICATION_NEEDED = "clarification_needed"
    FAIL = "fail"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    ACCEPTABLE = "acceptable"
    STALE = "stale"
    UNKNOWN = "unknown"


class ContradictionStatus(StrEnum):
    NONE = "none"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"


class CitationStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    WEAK = "weak"


class RepairAction(StrEnum):
    NONE = "none"
    REWRITE = "rewrite"
    EXPAND_GRAPH = "expand_graph"
    RETRIEVE_MORE = "retrieve_more"
    EXTERNAL_LOOKUP = "external_lookup"
    CLARIFY = "clarify"
    STOP = "stop"


class SupportType(StrEnum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    TABLE_VALUE = "table_value"
    GRAPH_PATH = "graph_path"
    INFERENCE = "inference"
    UNSUPPORTED = "unsupported"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UserRating(StrEnum):
    USEFUL = "useful"
    PARTIALLY_USEFUL = "partially useful"
    NOT_USEFUL = "not useful"
    INCORRECT = "incorrect"


class FailureCategory(StrEnum):
    RETRIEVAL = "retrieval"
    RANKING = "ranking"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    FRESHNESS = "freshness"
    ACCESS = "access"
    UNCLEAR_QUERY = "unclear_query"


class ReviewerType(StrEnum):
    USER = "user"
    EVALUATOR = "evaluator"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_name: str
    source_type: SourceType = SourceType.OTHER
    owner: str | None = None
    access_method: AccessMethod = AccessMethod.MANUAL
    external_link: str | None = None
    internal_location: str | None = None
    license_policy: LicensePolicy = LicensePolicy.UNKNOWN
    license_constraints: list[str] = field(default_factory=list)
    access_policy_id: str | None = None
    allowed_principals: list[str] = field(default_factory=list)
    reliability_level: ReliabilityLevel = ReliabilityLevel.UNVERIFIED
    reliability_score: float | None = None
    freshness_policy: FreshnessPolicy = FreshnessPolicy.MANUAL
    freshness_sla: str | None = None
    refresh_interval: str | None = None
    last_checked_at: datetime | None = None
    last_ingested_at: datetime | None = None
    status: SourceStatus = SourceStatus.PENDING
    notes: str | None = None
    source_id: str = field(default_factory=lambda: _record_id("src"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class IngestionJob:
    source_id: str
    trigger_type: IngestionTriggerType = IngestionTriggerType.MANUAL
    correlation_id: str | None = None
    started_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None
    status: IngestionStatus = IngestionStatus.QUEUED
    input_version: str | None = None
    output_version: str | None = None
    error_summary: str | None = None
    error_ids: list[str] = field(default_factory=list)
    log_ids: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)
    ingestion_job_id: str = field(default_factory=lambda: _record_id("ingest"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    source_id: str
    title: str | None = None
    author_or_owner: str | None = None
    published_at: date | None = None
    retrieved_at: datetime | None = None
    document_type: DocumentType = DocumentType.OTHER
    language: str | None = None
    canonical_url: str | None = None
    checksum: str | None = None
    version: str | None = None
    access_level: AccessLevel = AccessLevel.UNKNOWN
    as_of_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    access_policy_id: str | None = None
    document_id: str = field(default_factory=lambda: _record_id("doc"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    document_id: str
    source_id: str
    chunk_index: int
    heading_path: list[str] = field(default_factory=list)
    text: str = ""
    token_count: int | None = None
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    created_at: datetime = field(default_factory=_utc_now)
    embedding_id: str | None = None
    sparse_terms_id: str | None = None
    quality_flags: list[str] = field(default_factory=list)
    access_policy_id: str | None = None
    allowed_principals: list[str] = field(default_factory=list)
    as_of_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    chunk_id: str = field(default_factory=lambda: _record_id("chunk"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class EntityRecord:
    entity_name: str
    entity_type: EntityType = EntityType.OTHER
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    confidence: float | None = None
    source_ids: list[str] = field(default_factory=list)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    entity_id: str = field(default_factory=lambda: _record_id("entity"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class RelationRecord:
    subject_entity_id: str
    object_entity_id: str
    relation_type: RelationType = RelationType.OTHER
    evidence_chunk_ids: list[str] = field(default_factory=list)
    confidence: float | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    extracted_at: datetime = field(default_factory=_utc_now)
    relation_id: str = field(default_factory=lambda: _record_id("rel"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    user_query: str
    normalized_query: str | None = None
    user_context: dict[str, Any] = field(default_factory=dict)
    required_freshness: RequiredFreshness = RequiredFreshness.NONE
    risk_level: RiskLevel = RiskLevel.LOW
    output_intent: OutputIntent = OutputIntent.ANSWER
    constraints: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: _record_id("req"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    request_id: str
    query_type: QueryType = QueryType.MIXED
    selected_modes: list[RetrievalMode] = field(default_factory=lambda: [RetrievalMode.HYBRID])
    retrieval_budget: dict[str, Any] = field(default_factory=dict)
    repair_attempt: int = 0
    max_repair_attempts: int = 0
    previous_actions: list[str] = field(default_factory=list)
    required_validations: list[ValidationCriterion] = field(
        default_factory=lambda: [
            ValidationCriterion.RELEVANCE,
            ValidationCriterion.SUFFICIENCY,
            ValidationCriterion.CITATION,
        ]
    )
    fallback_actions: list[PlanFallbackAction] = field(default_factory=list)
    plan_reason: str | None = None
    plan_id: str = field(default_factory=lambda: _record_id("plan"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    request_id: str
    retrieval_mode: RetrievalMode
    source_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    text_snippet: str | None = None
    score: float | None = None
    normalized_score: float | None = None
    source_reliability: ReliabilityLevel = ReliabilityLevel.UNVERIFIED
    published_at: date | None = None
    retrieved_at: datetime | None = None
    citation_link: str | None = None
    access_scope: str | None = None
    access_decision: AccessDecision = AccessDecision.UNKNOWN
    exclusion_reason: str | None = None
    license_constraints: list[str] = field(default_factory=list)
    evidence_id: str = field(default_factory=lambda: _record_id("ev"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class RankedEvidence:
    evidence_id: str
    rank: int
    rerank_score: float | None = None
    relevance_label: RelevanceLabel | None = None
    diversity_group: str | None = None
    selection_reason: str | None = None
    ranked_evidence_id: str = field(default_factory=lambda: _record_id("ranked"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    request_id: str
    evidence_ids: list[str] = field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.PASS
    relevance_score: float | None = None
    sufficiency_score: float | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    contradiction_status: ContradictionStatus = ContradictionStatus.NONE
    citation_status: CitationStatus = CitationStatus.MISSING
    unsupported_claim_risk: RiskLevel = RiskLevel.LOW
    repair_action: RepairAction = RepairAction.NONE
    failed_criteria: list[ValidationCriterion] = field(default_factory=list)
    stop_reason: str | None = None
    validator_notes: str | None = None
    validation_id: str = field(default_factory=lambda: _record_id("validation"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    request_id: str
    claim_text: str
    answer_id: str | None = None
    support_type: SupportType = SupportType.UNSUPPORTED
    evidence_id: str | None = None
    evidence_span: str | None = None
    source_quote: str | None = None
    support_status: SupportStatus = SupportStatus.NOT_CHECKED
    confidence: float | None = None
    validator_notes: str | None = None
    claim_id: str = field(default_factory=lambda: _record_id("claim"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    request_id: str
    answer_text: str
    validation_id: str | None = None
    citation_map: dict[str, list[str]] = field(default_factory=dict)
    claim_records: list[ClaimRecord | dict[str, Any]] = field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    limitations: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_utc_now)
    model_used: str | None = None
    answer_id: str = field(default_factory=lambda: _record_id("answer"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    request_id: str
    answer_id: str
    user_rating: UserRating
    correction_text: str | None = None
    failure_category: FailureCategory | None = None
    reviewed_by: ReviewerType = ReviewerType.USER
    created_at: datetime = field(default_factory=_utc_now)
    feedback_id: str = field(default_factory=lambda: _record_id("feedback"))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_contract(asdict(self))
