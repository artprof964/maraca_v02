"""Environment profile defaults for local, test, staging, and production."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from .enums import lookup_str_enum
from .serialization import serialize_dataclass


class EnvironmentName(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class EnvironmentProfile:
    name: EnvironmentName
    debug: bool
    storage_root: str
    vector_store_url: str
    graph_store_url: str
    model_profile_name: str
    external_access_enabled: bool
    graph_enabled: bool
    strict_access: bool
    max_retries: int
    default_top_k: int
    default_budget_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return serialize_dataclass(self)


_DEFAULT_ENVIRONMENT_PROFILES: dict[EnvironmentName, EnvironmentProfile] = {
    EnvironmentName.LOCAL: EnvironmentProfile(
        name=EnvironmentName.LOCAL,
        debug=True,
        storage_root=".local/storage",
        vector_store_url="file://.local/vector-store",
        graph_store_url="file://.local/graph-store",
        model_profile_name="local-dev",
        external_access_enabled=False,
        graph_enabled=True,
        strict_access=False,
        max_retries=1,
        default_top_k=8,
        default_budget_tokens=4096,
    ),
    EnvironmentName.TEST: EnvironmentProfile(
        name=EnvironmentName.TEST,
        debug=True,
        storage_root="memory://test/storage",
        vector_store_url="mock://test/vector-store",
        graph_store_url="mock://test/graph-store",
        model_profile_name="test-mock",
        external_access_enabled=False,
        graph_enabled=False,
        strict_access=True,
        max_retries=0,
        default_top_k=3,
        default_budget_tokens=1024,
    ),
    EnvironmentName.STAGING: EnvironmentProfile(
        name=EnvironmentName.STAGING,
        debug=False,
        storage_root="placeholder://staging/storage",
        vector_store_url="placeholder://staging/vector-store",
        graph_store_url="placeholder://staging/graph-store",
        model_profile_name="staging-balanced",
        external_access_enabled=True,
        graph_enabled=True,
        strict_access=True,
        max_retries=2,
        default_top_k=6,
        default_budget_tokens=3072,
    ),
    EnvironmentName.PRODUCTION: EnvironmentProfile(
        name=EnvironmentName.PRODUCTION,
        debug=False,
        storage_root="placeholder://production/storage",
        vector_store_url="placeholder://production/vector-store",
        graph_store_url="placeholder://production/graph-store",
        model_profile_name="production-conservative",
        external_access_enabled=True,
        graph_enabled=True,
        strict_access=True,
        max_retries=2,
        default_top_k=5,
        default_budget_tokens=2048,
    ),
}

DEFAULT_ENVIRONMENT_PROFILES: Mapping[EnvironmentName, EnvironmentProfile] = MappingProxyType(
    _DEFAULT_ENVIRONMENT_PROFILES
)


def get_environment_profile(name: EnvironmentName | str) -> EnvironmentProfile:
    return lookup_str_enum(DEFAULT_ENVIRONMENT_PROFILES, EnvironmentName, name)


def serialize_environment_profile(profile: EnvironmentProfile) -> dict[str, Any]:
    return profile.to_dict()


def serialize_environment_profiles(
    profiles: Mapping[EnvironmentName, EnvironmentProfile] = DEFAULT_ENVIRONMENT_PROFILES,
) -> dict[str, dict[str, Any]]:
    return {
        environment_name.value: profiles[environment_name].to_dict()
        for environment_name in EnvironmentName
    }
