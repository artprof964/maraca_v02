"""In-memory source registry behavior for Milestone 1."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Iterable

from shared.contracts import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorType,
    FallbackAction,
    LogEvent,
    LogEventType,
    Partition,
    new_correlation_id,
    _utc_now,
)
from shared.policies import create_error_envelope, create_error_log_event, create_success_log_event
from shared.records import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    FreshnessPolicy,
    LicensePolicy,
    ReliabilityLevel,
    SourceRecord,
    SourceStatus,
    SourceType,
)


HIGH_RISK_USE_CASES = frozenset({"high-risk", "restricted-use", "regulated", "external-answer"})
ACCESS_POLICY_PREFIX = "access:"
DEFAULT_REFRESH_INTERVALS: dict[FreshnessPolicy, timedelta | None] = {
    FreshnessPolicy.STATIC: None,
    FreshnessPolicy.MANUAL: None,
    FreshnessPolicy.SCHEDULED: timedelta(days=1),
    FreshnessPolicy.EVENT_DRIVEN: timedelta(days=1),
    FreshnessPolicy.REAL_TIME: timedelta(minutes=15),
}


class SourceRegistryError(ValueError):
    """Raised when source registry input cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class SourceAccessResult:
    """Result of evaluating source-level access policy."""

    source_id: str
    decision: AccessDecision
    allowed: bool
    reason: str
    principal: str | None = None
    error: ErrorEnvelope | None = None
    log: LogEvent | None = None


@dataclass(frozen=True, slots=True)
class SourcePolicyDecision:
    """Decision emitted by source policy evaluation."""

    source_id: str
    allowed: bool
    policy_name: str
    reason: str
    access_decision: AccessDecision = AccessDecision.UNKNOWN
    error: ErrorEnvelope | None = None
    log: LogEvent | None = None


@dataclass(frozen=True, slots=True)
class SourceRefreshCheck:
    """Operational freshness check for source refresh monitoring."""

    source_id: str
    refresh_due: bool
    stale: bool
    reason: str
    checked_at: datetime
    last_observed_at: datetime | None = None
    next_refresh_at: datetime | None = None
    interval_seconds: int | None = None
    log: LogEvent | None = None
    error: ErrorEnvelope | None = None


def _coerce_enum(enum_type: type, value: object, field_name: str):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        raise SourceRegistryError(f"invalid {field_name}: {value!r}") from exc


def _access_policy_id(access_level: AccessLevel) -> str:
    return f"{ACCESS_POLICY_PREFIX}{access_level.value}"


def access_level_from_source(source: SourceRecord) -> AccessLevel:
    """Read the source access level from the shared source policy fields."""
    if not source.access_policy_id:
        return AccessLevel.UNKNOWN
    if source.access_policy_id.startswith(ACCESS_POLICY_PREFIX):
        value = source.access_policy_id.removeprefix(ACCESS_POLICY_PREFIX)
    else:
        value = source.access_policy_id
    try:
        return AccessLevel(value)
    except ValueError:
        return AccessLevel.UNKNOWN


def create_source_access_error(
    *,
    source: SourceRecord,
    principal: str | None,
    reason: str,
    correlation_id: str | None = None,
) -> ErrorEnvelope:
    """Create a structured access error for source registry callers."""
    return create_error_envelope(
        correlation_id=correlation_id or new_correlation_id("source_registry"),
        partition=Partition.SOURCE_REGISTRY,
        operation_name="check_source_access",
        error_type=ErrorType.ACCESS,
        error_message=reason,
        severity=ErrorSeverity.RECOVERABLE,
        fallback_action=FallbackAction.STOP,
        details={"source_id": source.source_id, "principal": principal},
    )


def create_source_policy_log(
    *,
    decision: SourcePolicyDecision,
    correlation_id: str | None = None,
) -> LogEvent:
    """Create a structured policy decision log for source registry callers."""
    return LogEvent(
        correlation_id=correlation_id or new_correlation_id("source_registry"),
        partition=Partition.SOURCE_REGISTRY,
        event_type=LogEventType.DECISION,
        operation_name="apply_source_policy",
        message=decision.reason,
        output_reference=decision.source_id,
        details={
            "event_name": "source_policy_decision",
            "policy_name": decision.policy_name,
            "allowed": decision.allowed,
            "access_decision": decision.access_decision.value,
        },
    )


class InMemorySourceRepository:
    """Tiny in-memory repository suitable for unit tests and local smoke checks."""

    def __init__(self, initial_sources: Iterable[SourceRecord] | None = None) -> None:
        self._sources: dict[str, SourceRecord] = {}
        for source in initial_sources or ():
            self.save(source)

    def save(self, source: SourceRecord) -> SourceRecord:
        self._sources[source.source_id] = source
        return source

    def get(self, source_id: str) -> SourceRecord:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise SourceRegistryError(f"unknown source_id: {source_id}") from exc

    def all(self) -> tuple[SourceRecord, ...]:
        return tuple(self._sources.values())


class SourceRegistry:
    """Register sources and evaluate source-level governance rules."""

    def __init__(self, repository: InMemorySourceRepository | None = None) -> None:
        self.repository = repository or InMemorySourceRepository()

    def register_source(
        self,
        *,
        source_name: str,
        source_type: SourceType | str,
        access_method: AccessMethod | str,
        owner: str | None = None,
        access_level: AccessLevel | str = AccessLevel.PUBLIC,
        external_link: str | None = None,
        internal_location: str | None = None,
        license_policy: LicensePolicy | str = LicensePolicy.UNKNOWN,
        license_constraints: Iterable[str] = (),
        allowed_principals: Iterable[str] = (),
        reliability_level: ReliabilityLevel | str = ReliabilityLevel.UNVERIFIED,
        reliability_score: float | None = None,
        freshness_policy: FreshnessPolicy | str = FreshnessPolicy.MANUAL,
        freshness_sla: str | None = None,
        refresh_interval: str | None = None,
        status: SourceStatus | str | None = None,
        notes: str | None = None,
    ) -> SourceRecord:
        """Register a source while preserving governance metadata separately."""
        if not source_name.strip():
            raise SourceRegistryError("source_name is required")

        resolved_type = _coerce_enum(SourceType, source_type, "source_type")
        resolved_access_method = _coerce_enum(AccessMethod, access_method, "access_method")
        resolved_access_level = _coerce_enum(AccessLevel, access_level, "access_level")
        resolved_license = _coerce_enum(LicensePolicy, license_policy, "license_policy")
        resolved_reliability = _coerce_enum(
            ReliabilityLevel,
            reliability_level,
            "reliability_level",
        )
        resolved_freshness = _coerce_enum(FreshnessPolicy, freshness_policy, "freshness_policy")
        resolved_status = (
            _coerce_enum(SourceStatus, status, "status")
            if status is not None
            else (SourceStatus.PENDING if owner is None else SourceStatus.ACTIVE)
        )

        if reliability_score is not None and not 0 <= reliability_score <= 1:
            raise SourceRegistryError("reliability_score must be between 0 and 1")

        source = SourceRecord(
            source_name=source_name,
            source_type=resolved_type,
            owner=owner,
            access_method=resolved_access_method,
            external_link=external_link,
            internal_location=internal_location,
            license_policy=resolved_license,
            license_constraints=list(license_constraints),
            access_policy_id=_access_policy_id(resolved_access_level),
            allowed_principals=list(allowed_principals),
            reliability_level=resolved_reliability,
            reliability_score=reliability_score,
            freshness_policy=resolved_freshness,
            freshness_sla=freshness_sla,
            refresh_interval=refresh_interval,
            status=resolved_status,
            notes=notes,
        )
        return self.repository.save(source)

    def update_source_status(
        self,
        source_id: str,
        status: SourceStatus | str,
        *,
        correlation_id: str | None = None,
    ) -> tuple[SourceRecord, LogEvent | None]:
        """Update status, allowing only shared source status values."""
        resolved_status = _coerce_enum(SourceStatus, status, "status")
        source = self.repository.get(source_id)
        updated = replace(source, status=resolved_status)
        self.repository.save(updated)

        if resolved_status is not SourceStatus.BLOCKED:
            return updated, None

        log = create_error_log_event(
            correlation_id=correlation_id or new_correlation_id("source_registry"),
            partition=Partition.SOURCE_REGISTRY,
            operation_name="update_source_status",
            error_type=ErrorType.POLICY,
            message="Source was blocked by registry policy.",
            event_name="source_blocked",
            fallback_action=FallbackAction.STOP,
            details={"source_id": source_id, "status": resolved_status.value},
        )
        return updated, log

    def check_source_access(
        self,
        source_id: str,
        *,
        principal: str | None = None,
        principal_scopes: Iterable[str] = (),
        correlation_id: str | None = None,
    ) -> SourceAccessResult:
        """Evaluate source access and fail closed when required metadata is absent."""
        source = self.repository.get(source_id)
        access_level = access_level_from_source(source)
        scopes = set(principal_scopes)
        corr = correlation_id or new_correlation_id("source_registry")

        if access_level is AccessLevel.PUBLIC:
            return self._access_result(source, principal, True, "public source", corr)

        if access_level is AccessLevel.INTERNAL and (
            "internal" in scopes or (principal is not None and principal in source.allowed_principals)
        ):
            return self._access_result(source, principal, True, "internal principal allowed", corr)

        if access_level in {AccessLevel.RESTRICTED, AccessLevel.CONFIDENTIAL}:
            if not source.allowed_principals:
                return self._access_result(
                    source,
                    principal,
                    False,
                    "non-public source is missing allowed principals",
                    corr,
                )
            if principal and principal in source.allowed_principals:
                return self._access_result(
                    source,
                    principal,
                    True,
                    "matching principal allowed",
                    corr,
                )

        reason = f"{access_level.value} source denied for principal"
        return self._access_result(source, principal, False, reason, corr)

    def apply_source_policy(
        self,
        source_id: str,
        *,
        use_case: str = "general",
        principal: str | None = None,
        principal_scopes: Iterable[str] = (),
        correlation_id: str | None = None,
    ) -> SourcePolicyDecision:
        """Apply source access and license policy and return a structured decision."""
        source = self.repository.get(source_id)
        corr = correlation_id or new_correlation_id("source_registry")
        access = self.check_source_access(
            source_id,
            principal=principal,
            principal_scopes=principal_scopes,
            correlation_id=corr,
        )
        if not access.allowed:
            return self._policy_decision(
                source,
                False,
                "access",
                access.reason,
                access.decision,
                corr,
                access.error,
            )

        if source.status in {SourceStatus.BLOCKED, SourceStatus.FAILED}:
            error = create_error_envelope(
                correlation_id=corr,
                partition=Partition.SOURCE_REGISTRY,
                operation_name="apply_source_policy",
                error_type=ErrorType.POLICY,
                error_message=f"source status is {source.status.value}",
                fallback_action=FallbackAction.STOP,
                details={"source_id": source.source_id, "status": source.status.value},
            )
            return self._policy_decision(
                source,
                False,
                "source_status",
                error.error_message,
                access.decision,
                corr,
                error,
            )

        high_risk = use_case in HIGH_RISK_USE_CASES
        if source.license_policy is LicensePolicy.UNKNOWN and high_risk:
            error = create_error_envelope(
                correlation_id=corr,
                partition=Partition.SOURCE_REGISTRY,
                operation_name="apply_source_policy",
                error_type=ErrorType.POLICY,
                error_message="unknown license blocked for restricted or high-risk use",
                fallback_action=FallbackAction.STOP,
                details={"source_id": source.source_id, "use_case": use_case},
            )
            return self._policy_decision(
                source,
                False,
                "license",
                error.error_message,
                access.decision,
                corr,
                error,
            )

        if source.license_policy in {LicensePolicy.RESTRICTED, LicensePolicy.CONFIDENTIAL} and high_risk:
            error = create_error_envelope(
                correlation_id=corr,
                partition=Partition.SOURCE_REGISTRY,
                operation_name="apply_source_policy",
                error_type=ErrorType.POLICY,
                error_message=f"{source.license_policy.value} license blocked for {use_case}",
                fallback_action=FallbackAction.STOP,
                details={"source_id": source.source_id, "use_case": use_case},
            )
            return self._policy_decision(
                source,
                False,
                "license",
                error.error_message,
                access.decision,
                corr,
                error,
            )

        return self._policy_decision(
            source,
            True,
            "source_policy",
            "source allowed by access, status, and license policy",
            access.decision,
            corr,
        )

    def check_source_refresh(
        self,
        source_id: str,
        *,
        now: datetime | None = None,
        correlation_id: str | None = None,
    ) -> SourceRefreshCheck:
        """Check whether a source should be refreshed or marked stale."""

        source = self.repository.get(source_id)
        checked_at = now or _utc_now()
        corr = correlation_id or new_correlation_id("source_registry")
        interval = _source_refresh_interval(source)
        observed_at = source.last_checked_at or source.last_ingested_at

        if source.status in {SourceStatus.BLOCKED, SourceStatus.FAILED}:
            return _source_refresh_check(
                source=source,
                refresh_due=False,
                stale=True,
                reason=f"source status is {source.status.value}",
                checked_at=checked_at,
                observed_at=observed_at,
                interval=interval,
                correlation_id=corr,
                error_type=ErrorType.POLICY,
            )

        if interval is None:
            return _source_refresh_check(
                source=source,
                refresh_due=False,
                stale=False,
                reason="source has manual or static freshness policy",
                checked_at=checked_at,
                observed_at=observed_at,
                interval=interval,
                correlation_id=corr,
            )

        if observed_at is None:
            return _source_refresh_check(
                source=source,
                refresh_due=True,
                stale=True,
                reason="source has never been checked or ingested",
                checked_at=checked_at,
                observed_at=None,
                interval=interval,
                correlation_id=corr,
                error_type=ErrorType.VALIDATION,
            )

        next_refresh_at = observed_at + interval
        refresh_due = checked_at >= next_refresh_at
        return _source_refresh_check(
            source=source,
            refresh_due=refresh_due,
            stale=refresh_due,
            reason="source refresh is due" if refresh_due else "source refresh is current",
            checked_at=checked_at,
            observed_at=observed_at,
            interval=interval,
            correlation_id=corr,
        )

    def monitor_source_refreshes(
        self,
        *,
        now: datetime | None = None,
        correlation_id: str | None = None,
    ) -> tuple[SourceRefreshCheck, ...]:
        """Check all registered sources for refresh and stale-source status."""

        checked_at = now or _utc_now()
        corr = correlation_id or new_correlation_id("source_registry")
        return tuple(
            self.check_source_refresh(source.source_id, now=checked_at, correlation_id=corr)
            for source in self.repository.all()
        )

    def update_stale_source_status(
        self,
        source_id: str,
        *,
        now: datetime | None = None,
        correlation_id: str | None = None,
    ) -> tuple[SourceRecord, SourceRefreshCheck]:
        """Mark stale active sources as deprecated while preserving governance fields."""

        corr = correlation_id or new_correlation_id("source_registry")
        check = self.check_source_refresh(source_id, now=now, correlation_id=corr)
        source = self.repository.get(source_id)
        if check.stale and source.status is SourceStatus.ACTIVE:
            source = self.repository.save(replace(source, status=SourceStatus.DEPRECATED))
        return source, check

    def _access_result(
        self,
        source: SourceRecord,
        principal: str | None,
        allowed: bool,
        reason: str,
        correlation_id: str,
    ) -> SourceAccessResult:
        decision = AccessDecision.ALLOWED if allowed else AccessDecision.DENIED
        error = None
        if not allowed:
            error = create_source_access_error(
                source=source,
                principal=principal,
                reason=reason,
                correlation_id=correlation_id,
            )

        log = create_success_log_event(
            correlation_id=correlation_id,
            partition=Partition.SOURCE_REGISTRY,
            operation_name="check_source_access",
            event_name="source_access_checked",
            message=reason,
            output_reference=source.source_id,
            details={"source_id": source.source_id, "allowed": allowed, "principal": principal},
        )
        return SourceAccessResult(
            source_id=source.source_id,
            decision=decision,
            allowed=allowed,
            reason=reason,
            principal=principal,
            error=error,
            log=log,
        )

    def _policy_decision(
        self,
        source: SourceRecord,
        allowed: bool,
        policy_name: str,
        reason: str,
        access_decision: AccessDecision,
        correlation_id: str,
        error: ErrorEnvelope | None = None,
    ) -> SourcePolicyDecision:
        decision = SourcePolicyDecision(
            source_id=source.source_id,
            allowed=allowed,
            policy_name=policy_name,
            reason=reason,
            access_decision=access_decision,
            error=error,
        )
        return replace(
            decision,
            log=create_source_policy_log(decision=decision, correlation_id=correlation_id),
        )


def _source_refresh_interval(source: SourceRecord) -> timedelta | None:
    explicit = _parse_duration(source.refresh_interval) or _parse_duration(source.freshness_sla)
    if explicit is not None:
        return explicit
    return DEFAULT_REFRESH_INTERVALS[source.freshness_policy]


def _parse_duration(value: str | None) -> timedelta | None:
    if not value:
        return None
    stripped = value.strip().lower()
    if stripped.startswith("pt"):
        return _parse_duration_suffix(stripped[2:])
    if stripped.startswith("p"):
        return _parse_duration_suffix(stripped[1:])
    return _parse_duration_suffix(stripped)


def _parse_duration_suffix(value: str) -> timedelta | None:
    stripped = value.strip().lower()
    if len(stripped) < 2:
        return None
    amount_text, unit = stripped[:-1], stripped[-1]
    try:
        amount = int(amount_text)
    except ValueError:
        return None
    if amount <= 0:
        return None
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return None


def _source_refresh_check(
    *,
    source: SourceRecord,
    refresh_due: bool,
    stale: bool,
    reason: str,
    checked_at: datetime,
    observed_at: datetime | None,
    interval: timedelta | None,
    correlation_id: str,
    error_type: ErrorType | None = None,
) -> SourceRefreshCheck:
    interval_seconds = int(interval.total_seconds()) if interval is not None else None
    next_refresh_at = observed_at + interval if observed_at is not None and interval is not None else None
    details = {
        "event_name": "source_refresh_checked",
        "source_id": source.source_id,
        "refresh_due": refresh_due,
        "stale": stale,
        "freshness_policy": source.freshness_policy.value,
        "interval_seconds": interval_seconds,
        "last_observed_at": observed_at.isoformat() if observed_at is not None else None,
        "next_refresh_at": next_refresh_at.isoformat() if next_refresh_at is not None else None,
    }
    log = LogEvent(
        correlation_id=correlation_id,
        partition=Partition.SOURCE_REGISTRY,
        event_type=LogEventType.WARNING if stale else LogEventType.SUCCESS,
        operation_name="check_source_refresh",
        message=reason,
        output_reference=source.source_id,
        details=details,
    )
    error = None
    if error_type is not None:
        error = create_error_envelope(
            correlation_id=correlation_id,
            partition=Partition.SOURCE_REGISTRY,
            operation_name="check_source_refresh",
            error_type=error_type,
            error_message=reason,
            severity=ErrorSeverity.RECOVERABLE,
            retryable=refresh_due,
            fallback_action=FallbackAction.ESCALATE if stale else FallbackAction.STOP,
            details={"source_id": source.source_id, "refresh_due": refresh_due, "stale": stale},
        )
    return SourceRefreshCheck(
        source_id=source.source_id,
        refresh_due=refresh_due,
        stale=stale,
        reason=reason,
        checked_at=checked_at,
        last_observed_at=observed_at,
        next_refresh_at=next_refresh_at,
        interval_seconds=interval_seconds,
        log=log,
        error=error,
    )


def register_source(**kwargs: object) -> SourceRecord:
    """Convenience function for one-off registration in tests."""
    return SourceRegistry().register_source(**kwargs)


def check_source_access(
    source: SourceRecord,
    *,
    principal: str | None = None,
    principal_scopes: Iterable[str] = (),
    correlation_id: str | None = None,
) -> SourceAccessResult:
    """Convenience function for checking a single source without a long-lived registry."""
    registry = SourceRegistry(InMemorySourceRepository([source]))
    return registry.check_source_access(
        source.source_id,
        principal=principal,
        principal_scopes=principal_scopes,
        correlation_id=correlation_id,
    )


def apply_source_policy(
    source: SourceRecord,
    *,
    use_case: str = "general",
    principal: str | None = None,
    principal_scopes: Iterable[str] = (),
    correlation_id: str | None = None,
) -> SourcePolicyDecision:
    """Convenience function for applying policy to a single source."""
    registry = SourceRegistry(InMemorySourceRepository([source]))
    return registry.apply_source_policy(
        source.source_id,
        use_case=use_case,
        principal=principal,
        principal_scopes=principal_scopes,
        correlation_id=correlation_id,
    )


def check_source_refresh(
    source: SourceRecord,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
) -> SourceRefreshCheck:
    """Convenience function for checking one source's refresh state."""
    registry = SourceRegistry(InMemorySourceRepository([source]))
    return registry.check_source_refresh(source.source_id, now=now, correlation_id=correlation_id)
