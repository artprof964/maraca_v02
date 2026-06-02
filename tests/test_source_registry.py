from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    ErrorType,
    FreshnessPolicy,
    LicensePolicy,
    LogEventType,
    Partition,
    ReliabilityLevel,
    SourceRecord,
    SourceStatus,
    SourceType,
)
from source_registry import (
    SourceRegistry,
    SourceRegistryError,
    access_level_from_source,
    create_source_access_error,
)


def test_register_source_requires_name_type_owner_access_method() -> None:
    registry = SourceRegistry()

    source = registry.register_source(
        source_name="Public paper",
        source_type=SourceType.PAPER,
        owner="research",
        access_method=AccessMethod.URL,
    )

    assert source.source_name == "Public paper"
    assert source.source_type is SourceType.PAPER
    assert source.owner == "research"
    assert source.access_method is AccessMethod.URL


def test_register_source_rejects_missing_required_name() -> None:
    registry = SourceRegistry()

    try:
        registry.register_source(
            source_name=" ",
            source_type=SourceType.PAPER,
            access_method=AccessMethod.URL,
        )
    except SourceRegistryError:
        return

    raise AssertionError("Expected SourceRegistryError for missing source_name.")


def test_register_source_preserves_external_link() -> None:
    registry = SourceRegistry()
    external_link = "https://example.test/public-paper"

    source = registry.register_source(
        source_name="Public paper",
        source_type="paper",
        owner="research",
        access_method="url",
        external_link=external_link,
    )

    assert source.external_link == external_link


def test_register_source_accepts_enum_and_string_governance_inputs() -> None:
    registry = SourceRegistry()

    source = registry.register_source(
        source_name="String governance source",
        source_type="web",
        owner="research",
        access_method=AccessMethod.URL,
        access_level="internal",
        license_policy="allowed",
        reliability_level="high",
        freshness_policy="scheduled",
        status="active",
    )

    assert source.source_type is SourceType.WEB
    assert source.access_method is AccessMethod.URL
    assert source.access_policy_id == "access:internal"
    assert source.license_policy is LicensePolicy.ALLOWED
    assert source.reliability_level is ReliabilityLevel.HIGH
    assert source.freshness_policy is FreshnessPolicy.SCHEDULED
    assert source.status is SourceStatus.ACTIVE


def test_register_source_wraps_invalid_enum_strings() -> None:
    registry = SourceRegistry()

    try:
        registry.register_source(
            source_name="Invalid source",
            source_type="not_a_source_type",
            access_method=AccessMethod.URL,
        )
    except SourceRegistryError as exc:
        assert str(exc) == "invalid source_type: 'not_a_source_type'"
        assert isinstance(exc.__cause__, ValueError)
        return

    raise AssertionError("Expected SourceRegistryError for invalid source_type.")


def test_update_source_status_accepts_string_and_wraps_invalid_status() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Status source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
    )

    updated, _ = registry.update_source_status(source.source_id, "deprecated")

    assert updated.status is SourceStatus.DEPRECATED

    try:
        registry.update_source_status(source.source_id, "archived")
    except SourceRegistryError as exc:
        assert str(exc) == "invalid status: 'archived'"
        assert isinstance(exc.__cause__, ValueError)
        return

    raise AssertionError("Expected SourceRegistryError for invalid status.")


def test_register_source_sets_default_status_pending_when_owner_missing() -> None:
    registry = SourceRegistry()

    source = registry.register_source(
        source_name="Unowned source",
        source_type=SourceType.DOCUMENT,
        access_method=AccessMethod.UPLOAD,
    )

    assert source.owner is None
    assert source.status is SourceStatus.PENDING


def test_update_source_status_allows_active_deprecated_blocked_failed() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Status source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
    )

    for status in (
        SourceStatus.ACTIVE,
        SourceStatus.DEPRECATED,
        SourceStatus.BLOCKED,
        SourceStatus.FAILED,
    ):
        updated, log = registry.update_source_status(source.source_id, status)
        assert updated.status is status
        if status is SourceStatus.BLOCKED:
            assert log is not None
            assert log.event_type is LogEventType.ERROR
            assert log.details["event_name"] == "source_blocked"


def test_check_source_access_allows_authorized_principal() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Restricted runbook",
        source_type=SourceType.DOCUMENT,
        owner="security",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.RESTRICTED,
        allowed_principals=["alice"],
    )

    result = registry.check_source_access(source.source_id, principal="alice")

    assert result.allowed is True
    assert result.decision is AccessDecision.ALLOWED
    assert result.error is None
    assert result.log is not None
    assert result.log.details["event_name"] == "source_access_checked"


def test_check_source_access_denies_unauthorized_principal() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Confidential runbook",
        source_type=SourceType.DOCUMENT,
        owner="security",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.CONFIDENTIAL,
        allowed_principals=["alice"],
    )

    result = registry.check_source_access(source.source_id, principal="bob")

    assert result.allowed is False
    assert result.decision is AccessDecision.DENIED
    assert result.error is not None
    assert result.error.error_type is ErrorType.ACCESS


def test_non_public_source_without_principals_fails_closed() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Restricted metadata gap",
        source_type=SourceType.DOCUMENT,
        owner="security",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.RESTRICTED,
    )

    result = registry.check_source_access(source.source_id, principal="alice")

    assert result.allowed is False
    assert "missing allowed principals" in result.reason


def test_raw_source_record_missing_access_metadata_fails_closed() -> None:
    registry = SourceRegistry()
    source = registry.repository.save(SourceRecord(source_name="Raw source"))

    result = registry.check_source_access(source.source_id, principal="alice")

    assert access_level_from_source(source) is AccessLevel.UNKNOWN
    assert result.allowed is False
    assert result.decision is AccessDecision.DENIED


def test_internal_access_allows_internal_scope() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Internal note",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.INTERNAL,
    )

    result = registry.check_source_access(source.source_id, principal_scopes=["internal"])

    assert result.allowed is True


def test_internal_source_denies_named_principal_without_scope_or_allow_list() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Internal note",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.INTERNAL,
    )

    result = registry.check_source_access(source.source_id, principal="alice")

    assert result.allowed is False
    assert result.decision is AccessDecision.DENIED


def test_apply_source_policy_blocks_unknown_license_for_restricted_use() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Unknown license source",
        source_type=SourceType.WEB,
        owner="research",
        access_method=AccessMethod.URL,
        access_level=AccessLevel.PUBLIC,
        license_policy=LicensePolicy.UNKNOWN,
    )

    decision = registry.apply_source_policy(source.source_id, use_case="high-risk")

    assert decision.allowed is False
    assert decision.policy_name == "license"
    assert decision.error is not None
    assert decision.error.error_type is ErrorType.POLICY
    assert decision.log is not None
    assert decision.log.event_type is LogEventType.DECISION


def test_reliability_score_is_separate_from_freshness_sla() -> None:
    registry = SourceRegistry()

    source = registry.register_source(
        source_name="External source",
        source_type=SourceType.WEB,
        owner="research",
        access_method=AccessMethod.URL,
        reliability_level=ReliabilityLevel.HIGH,
        reliability_score=0.91,
        freshness_policy=FreshnessPolicy.SCHEDULED,
        freshness_sla="7d",
    )

    assert source.reliability_level is ReliabilityLevel.HIGH
    assert source.reliability_score == 0.91
    assert source.freshness_policy is FreshnessPolicy.SCHEDULED
    assert source.freshness_sla == "7d"
    assert source.to_dict()["reliability_score"] != source.to_dict()["freshness_sla"]


def test_source_access_failure_creates_error_envelope() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Restricted runbook",
        source_type=SourceType.DOCUMENT,
        owner="security",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.RESTRICTED,
        allowed_principals=["alice"],
    )

    error = create_source_access_error(
        source=source,
        principal="bob",
        reason="restricted source denied for principal",
    )

    assert error.partition is Partition.SOURCE_REGISTRY
    assert error.error_type is ErrorType.ACCESS
    assert error.details["source_id"] == source.source_id
    assert error.details["principal"] == "bob"


def test_source_policy_application_logs_decision() -> None:
    registry = SourceRegistry()
    source = registry.register_source(
        source_name="Allowed public source",
        source_type=SourceType.WEB,
        owner="research",
        access_method=AccessMethod.URL,
        license_policy=LicensePolicy.ALLOWED,
    )

    decision = registry.apply_source_policy(source.source_id)

    assert decision.allowed is True
    assert decision.log is not None
    assert decision.log.details["event_name"] == "source_policy_decision"
    assert decision.log.details["allowed"] is True


def test_access_level_round_trips_through_source_policy_field() -> None:
    registry = SourceRegistry()

    source = registry.register_source(
        source_name="Internal source",
        source_type=SourceType.DOCUMENT,
        owner="ops",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel.INTERNAL,
    )

    assert access_level_from_source(source) is AccessLevel.INTERNAL
