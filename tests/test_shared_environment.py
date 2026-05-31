from shared import (
    DEFAULT_ENVIRONMENT_PROFILES,
    EnvironmentName,
    EnvironmentProfile,
    get_environment_profile,
    serialize_environment_profile,
    serialize_environment_profiles,
)


def test_all_environment_profiles_exist() -> None:
    assert set(DEFAULT_ENVIRONMENT_PROFILES) == set(EnvironmentName)
    assert all(
        isinstance(profile, EnvironmentProfile)
        for profile in DEFAULT_ENVIRONMENT_PROFILES.values()
    )


def test_profile_lookup_accepts_enum_and_string_names() -> None:
    assert get_environment_profile(EnvironmentName.LOCAL).name is EnvironmentName.LOCAL
    assert get_environment_profile("production").name is EnvironmentName.PRODUCTION


def test_test_profile_is_isolated_and_mocked() -> None:
    profile = get_environment_profile(EnvironmentName.TEST)

    assert profile.external_access_enabled is False
    assert profile.graph_enabled is False
    assert profile.strict_access is True
    assert profile.max_retries == 0
    assert profile.storage_root.startswith("memory://")
    assert profile.vector_store_url.startswith("mock://")
    assert profile.graph_store_url.startswith("mock://")
    assert profile.model_profile_name == "test-mock"


def test_production_profile_is_strict_and_conservative() -> None:
    profile = get_environment_profile(EnvironmentName.PRODUCTION)

    assert profile.debug is False
    assert profile.strict_access is True
    assert profile.external_access_enabled is True
    assert profile.graph_enabled is True
    assert profile.max_retries <= 2
    assert profile.default_top_k <= get_environment_profile(EnvironmentName.LOCAL).default_top_k
    assert profile.default_budget_tokens <= get_environment_profile(
        EnvironmentName.LOCAL
    ).default_budget_tokens


def test_staging_profile_is_production_like_with_room_for_validation() -> None:
    profile = get_environment_profile(EnvironmentName.STAGING)
    local_profile = get_environment_profile(EnvironmentName.LOCAL)
    test_profile = get_environment_profile(EnvironmentName.TEST)
    production_profile = get_environment_profile(EnvironmentName.PRODUCTION)

    assert profile.debug is False
    assert profile.strict_access is True
    assert profile.external_access_enabled is True
    assert profile.graph_enabled is True
    assert test_profile.max_retries <= profile.max_retries <= local_profile.max_retries + 1
    assert profile.max_retries == production_profile.max_retries
    assert test_profile.default_top_k < profile.default_top_k <= local_profile.default_top_k
    assert production_profile.default_top_k <= profile.default_top_k
    assert (
        test_profile.default_budget_tokens
        < profile.default_budget_tokens
        <= local_profile.default_budget_tokens
    )
    assert production_profile.default_budget_tokens <= profile.default_budget_tokens


def test_local_profile_is_developer_friendly_without_external_access() -> None:
    profile = get_environment_profile(EnvironmentName.LOCAL)

    assert profile.debug is True
    assert profile.strict_access is False
    assert profile.external_access_enabled is False
    assert profile.graph_enabled is True
    assert profile.storage_root.startswith(".local/")
    assert profile.default_top_k > get_environment_profile(EnvironmentName.TEST).default_top_k


def test_environment_profile_serialization_is_stable() -> None:
    profile_payload = serialize_environment_profile(
        get_environment_profile(EnvironmentName.STAGING)
    )
    profiles_payload = serialize_environment_profiles()

    assert profile_payload == {
        "name": "staging",
        "debug": False,
        "storage_root": "placeholder://staging/storage",
        "vector_store_url": "placeholder://staging/vector-store",
        "graph_store_url": "placeholder://staging/graph-store",
        "model_profile_name": "staging-balanced",
        "external_access_enabled": True,
        "graph_enabled": True,
        "strict_access": True,
        "max_retries": 2,
        "default_top_k": 6,
        "default_budget_tokens": 3072,
    }
    assert list(profiles_payload) == ["local", "test", "staging", "production"]
    assert profiles_payload["test"]["vector_store_url"] == "mock://test/vector-store"
