"""Pure mapping from watch-style candidate payloads to MARACA records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, TypeVar

from shared.records import (
    AccessMethod,
    FreshnessPolicy,
    IngestionJob,
    IngestionStatus,
    IngestionTriggerType,
    LicensePolicy,
    ReliabilityLevel,
    SourceRecord,
    SourceStatus,
    SourceType,
)
from shared.serialization import serialize_contract


Record = Mapping[str, Any]
EnumValue = TypeVar("EnumValue", bound=StrEnum)
DEFAULT_JOB_STARTED_AT = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SocialSourceCandidate:
    """Plain candidate data accepted from inert watch boundaries."""

    candidate_id: str
    work_id: str
    source_name: str
    title: str = ""
    summary: str = ""
    reference: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Record = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_contract(asdict(self), tuple_as_list=True)


@dataclass(frozen=True, slots=True)
class SocialSourceCandidateMapping:
    """Mapped MARACA records without registering or ingesting anything."""

    candidate: SocialSourceCandidate
    source: SourceRecord
    ingestion_job: IngestionJob

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "source": self.source.to_dict(),
            "ingestion_job": self.ingestion_job.to_dict(),
        }


def map_social_source_candidate(
    candidate: SocialSourceCandidate | Record | object,
    *,
    default_source_type: SourceType | str = SourceType.WEB,
    default_freshness_policy: FreshnessPolicy | str = FreshnessPolicy.EVENT_DRIVEN,
    default_license_policy: LicensePolicy | str = LicensePolicy.UNKNOWN,
    default_reliability_level: ReliabilityLevel | str = ReliabilityLevel.UNVERIFIED,
    default_source_status: SourceStatus | str = SourceStatus.PENDING,
    default_trigger_type: IngestionTriggerType | str = IngestionTriggerType.MANUAL,
    default_ingestion_status: IngestionStatus | str = IngestionStatus.QUEUED,
    started_at: datetime = DEFAULT_JOB_STARTED_AT,
) -> SocialSourceCandidateMapping:
    """Return deterministic MARACA source and ingestion records for a candidate."""

    normalized = normalize_social_source_candidate(candidate)
    metadata = _plain_mapping(normalized.metadata)

    source_type = _coerce_enum(
        SourceType,
        _first_present(metadata, "source_type", "type"),
        _coerce_enum(SourceType, default_source_type, SourceType.WEB),
        aliases={
            "social": SourceType.WEB,
            "watch": SourceType.WEB,
            "url": SourceType.WEB,
        },
    )
    access_method = _coerce_enum(
        AccessMethod,
        _first_present(metadata, "access_method"),
        AccessMethod.URL if normalized.reference else AccessMethod.MANUAL,
        aliases={
            "web": AccessMethod.URL,
            "social": AccessMethod.URL,
            "watch": AccessMethod.URL,
        },
    )
    freshness_policy = _coerce_enum(
        FreshnessPolicy,
        _first_present(metadata, "freshness_policy", "freshness"),
        _coerce_enum(
            FreshnessPolicy,
            default_freshness_policy,
            FreshnessPolicy.EVENT_DRIVEN,
        ),
        aliases={"event_driven": FreshnessPolicy.EVENT_DRIVEN},
    )

    source_id = _stable_id(
        "src_social",
        normalized.work_id,
        normalized.candidate_id,
        normalized.reference or normalized.source_name,
    )
    job_id = _stable_id("ingest_social", source_id, normalized.candidate_id)

    source = SourceRecord(
        source_name=_source_name(normalized),
        source_type=source_type,
        owner=_optional_text(_first_present(metadata, "owner", "source_owner")),
        access_method=access_method,
        external_link=normalized.reference,
        internal_location=f"social-watch:{normalized.work_id}:{normalized.candidate_id}",
        license_policy=_coerce_enum(
            LicensePolicy,
            _first_present(metadata, "license_policy", "license"),
            _coerce_enum(
                LicensePolicy,
                default_license_policy,
                LicensePolicy.UNKNOWN,
            ),
        ),
        license_constraints=_strings(_first_present(metadata, "license_constraints")),
        access_policy_id=_optional_text(_first_present(metadata, "access_policy_id")),
        allowed_principals=list(_strings(_first_present(metadata, "allowed_principals"))),
        reliability_level=_coerce_enum(
            ReliabilityLevel,
            _first_present(metadata, "reliability_level", "reliability"),
            _coerce_enum(
                ReliabilityLevel,
                default_reliability_level,
                ReliabilityLevel.UNVERIFIED,
            ),
        ),
        reliability_score=_optional_float(_first_present(metadata, "reliability_score")),
        freshness_policy=freshness_policy,
        freshness_sla=_optional_text(_first_present(metadata, "freshness_sla")),
        refresh_interval=_optional_text(_first_present(metadata, "refresh_interval")),
        status=_coerce_enum(
            SourceStatus,
            _first_present(metadata, "status", "source_status"),
            _coerce_enum(SourceStatus, default_source_status, SourceStatus.PENDING),
        ),
        notes=_notes(normalized),
        source_id=source_id,
    )
    ingestion_job = IngestionJob(
        source_id=source.source_id,
        trigger_type=_coerce_enum(
            IngestionTriggerType,
            _first_present(metadata, "trigger_type", "ingestion_trigger_type"),
            _coerce_enum(
                IngestionTriggerType,
                default_trigger_type,
                IngestionTriggerType.MANUAL,
            ),
        ),
        correlation_id=_optional_text(_first_present(metadata, "correlation_id")),
        started_at=started_at,
        status=_coerce_enum(
            IngestionStatus,
            _first_present(metadata, "ingestion_status"),
            _coerce_enum(
                IngestionStatus,
                default_ingestion_status,
                IngestionStatus.QUEUED,
            ),
        ),
        input_version=_optional_text(_first_present(metadata, "input_version")),
        quality_flags=list(_strings(_first_present(metadata, "quality_flags"))),
        ingestion_job_id=job_id,
    )
    return SocialSourceCandidateMapping(
        candidate=normalized,
        source=source,
        ingestion_job=ingestion_job,
    )


def map_social_source_candidates(
    candidates: Iterable[SocialSourceCandidate | Record | object],
    **kwargs: Any,
) -> tuple[SocialSourceCandidateMapping, ...]:
    """Map many candidate records without calling connectors or repositories."""

    return tuple(map_social_source_candidate(candidate, **kwargs) for candidate in candidates)


def normalize_social_source_candidate(
    candidate: SocialSourceCandidate | Record | object,
) -> SocialSourceCandidate:
    """Normalize Harness watch-style records and dict-like payloads."""

    if isinstance(candidate, SocialSourceCandidate):
        return SocialSourceCandidate(
            candidate_id=candidate.candidate_id,
            work_id=candidate.work_id,
            source_name=candidate.source_name,
            title=candidate.title,
            summary=candidate.summary,
            reference=candidate.reference,
            tags=tuple(candidate.tags),
            metadata=_plain_mapping(candidate.metadata),
        )

    record = _record(candidate)
    metadata = _plain_mapping(record.get("metadata"))
    return SocialSourceCandidate(
        candidate_id=_text(
            _first_present(record, "candidate_id", "id", "source_key"),
            "candidate",
        ),
        work_id=_text(_first_present(record, "work_id"), "manual"),
        source_name=_text(_first_present(record, "source_name", "source"), "manual"),
        title=_text(_first_present(record, "title"), ""),
        summary=_text(_first_present(record, "summary", "body", "text"), ""),
        reference=_optional_text(_first_present(record, "reference", "url", "uri")),
        tags=_strings(_first_present(record, "tags")),
        metadata=metadata,
    )


def social_source_candidate_payload(
    candidate: SocialSourceCandidate | Record | object,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return a plain serialized mapping payload for handoff or tests."""

    return map_social_source_candidate(candidate, **kwargs).to_dict()


def _record(value: SocialSourceCandidate | Record | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return _plain_mapping(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return _plain_mapping(mapped)
    return {}


def _plain_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _plain_value(item)
        for key, item in value.items()
        if not _sensitive_key(str(key))
    }


def _plain_value(value: object) -> Any:
    if isinstance(value, Mapping):
        return _plain_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_plain_value(item) for item in value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _source_name(candidate: SocialSourceCandidate) -> str:
    if candidate.title.strip():
        return candidate.title
    if candidate.source_name.strip():
        return candidate.source_name
    return candidate.candidate_id


def _notes(candidate: SocialSourceCandidate) -> str:
    parts = [
        f"candidate_id={candidate.candidate_id}",
        f"work_id={candidate.work_id}",
        f"source_name={candidate.source_name}",
    ]
    if candidate.tags:
        parts.append(f"tags={','.join(candidate.tags)}")
    if candidate.summary:
        parts.append(f"summary={candidate.summary}")
    return "; ".join(parts)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _coerce_enum(
    enum_type: type[EnumValue],
    value: object,
    default: EnumValue,
    *,
    aliases: Mapping[str, EnumValue] | None = None,
) -> EnumValue:
    if isinstance(value, enum_type):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if aliases and normalized in aliases:
        return aliases[normalized]
    try:
        return enum_type(normalized)
    except ValueError:
        return default


def _first_present(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None


def _strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return ()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text(value: object, fallback: str) -> str:
    text = _optional_text(value)
    return text if text is not None else fallback


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in ("secret", "token", "api_key"))


__all__ = [
    "DEFAULT_JOB_STARTED_AT",
    "SocialSourceCandidate",
    "SocialSourceCandidateMapping",
    "map_social_source_candidate",
    "map_social_source_candidates",
    "normalize_social_source_candidate",
    "social_source_candidate_payload",
]
