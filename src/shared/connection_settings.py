"""Connection setting registry for optional LLM adapter configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .serialization import serialize_dataclass


DEEPSEEK_OPEN_ART_ENV_VAR = "deepseek-open-art"
DEEPSEEK_API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"
STANDARD_LLM_API_KEY_ENV_VAR = DEEPSEEK_OPEN_ART_ENV_VAR

DEFAULT_LLM_API_URL = "https://api.deepseek.com"
DEFAULT_LLM_PRIMARY_MODEL = "deepseek-v4-pro"
DEFAULT_LLM_FALLBACK_MODEL = "provider-fallback-model"
DEFAULT_LLM_CLASSIFIER_MODEL = "provider-classifier-model"
DEFAULT_LLM_EMBEDDING_MODEL = "provider-embedding-model"
REDACTED_CONNECTION_VALUE = "<redacted>"


@dataclass(frozen=True, slots=True)
class ConnectionEnvVar:
    name: str
    setting_name: str
    purpose: str
    secret: bool = False
    default: str = ""
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return serialize_dataclass(self)


@dataclass(frozen=True, slots=True)
class ConnectionSettings:
    llm_api_key: str
    llm_api_url: str
    llm_primary_model: str
    llm_fallback_model: str
    llm_classifier_model: str
    llm_embedding_model: str

    def to_dict(self) -> dict[str, Any]:
        return serialize_dataclass(self)

    def to_redacted_dict(self) -> dict[str, Any]:
        return redact_connection_settings(self.to_dict())


CONNECTION_ENV_VARS: tuple[ConnectionEnvVar, ...] = (
    ConnectionEnvVar(
        STANDARD_LLM_API_KEY_ENV_VAR,
        "llm_api_key",
        "DeepSeek LLM API access",
        secret=True,
        aliases=(DEEPSEEK_API_KEY_ENV_VAR,),
    ),
    ConnectionEnvVar(
        "LLM_API_URL",
        "llm_api_url",
        "Provider-neutral LLM API endpoint",
        default=DEFAULT_LLM_API_URL,
    ),
    ConnectionEnvVar(
        "LLM_PRIMARY_MODEL",
        "llm_primary_model",
        "Primary LLM model selection",
        default=DEFAULT_LLM_PRIMARY_MODEL,
    ),
    ConnectionEnvVar(
        "LLM_FALLBACK_MODEL",
        "llm_fallback_model",
        "Fallback LLM model selection",
        default=DEFAULT_LLM_FALLBACK_MODEL,
    ),
    ConnectionEnvVar(
        "LLM_CLASSIFIER_MODEL",
        "llm_classifier_model",
        "Request classifier model selection",
        default=DEFAULT_LLM_CLASSIFIER_MODEL,
    ),
    ConnectionEnvVar(
        "LLM_EMBEDDING_MODEL",
        "llm_embedding_model",
        "Embedding model selection",
        default=DEFAULT_LLM_EMBEDDING_MODEL,
    ),
)

CONNECTION_SETTING_NAMES: frozenset[str] = frozenset(ConnectionSettings.__dataclass_fields__)
CONNECTION_SETTING_NAME_BY_ENV_VAR: Mapping[str, str] = MappingProxyType(
    {
        name: spec.setting_name
        for spec in CONNECTION_ENV_VARS
        for name in (spec.name, *spec.aliases)
    }
)
CONNECTION_ENV_VAR_ALIASES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {spec.name: spec.aliases for spec in CONNECTION_ENV_VARS if spec.aliases}
)
EMPTY_CONNECTION_ENV: Mapping[str, str] = MappingProxyType({})

_SECRET_KEY_MARKERS = ("secret", "token", "api_key", "apikey")


def _normalized_key(key: str) -> str:
    return key.lower().replace("-", "_").replace(" ", "_")


_SECRET_CONNECTION_KEYS: frozenset[str] = frozenset(
    _normalized_key(name)
    for spec in CONNECTION_ENV_VARS
    if spec.secret
    for name in (spec.name, spec.setting_name, *spec.aliases)
)


def env_value(
    env: Mapping[str, str],
    name: str,
    *,
    default: str = "",
    aliases: tuple[str, ...] = (),
) -> str:
    for key in (name, *aliases):
        value = env.get(key, "")
        if value:
            return value
    return default


def load_connection_settings(
    env: Mapping[str, str] = EMPTY_CONNECTION_ENV,
) -> ConnectionSettings:
    values = {
        spec.setting_name: env_value(
            env,
            spec.name,
            default=spec.default,
            aliases=spec.aliases,
        )
        for spec in CONNECTION_ENV_VARS
    }
    return ConnectionSettings(**values)


def env_example_values() -> dict[str, str]:
    return {spec.name: "" if spec.secret else spec.default for spec in CONNECTION_ENV_VARS}


def parse_env_text(env_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def redact_connection_settings(value: Any) -> Any:
    if isinstance(value, ConnectionSettings):
        return redact_connection_settings(value.to_dict())
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _sensitive_connection_key(str(key)):
                redacted[key] = REDACTED_CONNECTION_VALUE
            else:
                redacted[key] = redact_connection_settings(item)
        return redacted
    if isinstance(value, list):
        return [redact_connection_settings(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_connection_settings(item) for item in value)
    return value


def connection_endpoint_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _sensitive_connection_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized.endswith("_env"):
        return False
    return normalized in _SECRET_CONNECTION_KEYS or any(
        marker in normalized for marker in _SECRET_KEY_MARKERS
    )


__all__ = [
    "CONNECTION_ENV_VAR_ALIASES",
    "CONNECTION_ENV_VARS",
    "CONNECTION_SETTING_NAME_BY_ENV_VAR",
    "CONNECTION_SETTING_NAMES",
    "ConnectionEnvVar",
    "ConnectionSettings",
    "DEEPSEEK_API_KEY_ENV_VAR",
    "DEEPSEEK_OPEN_ART_ENV_VAR",
    "DEFAULT_LLM_API_URL",
    "DEFAULT_LLM_CLASSIFIER_MODEL",
    "DEFAULT_LLM_EMBEDDING_MODEL",
    "DEFAULT_LLM_FALLBACK_MODEL",
    "DEFAULT_LLM_PRIMARY_MODEL",
    "EMPTY_CONNECTION_ENV",
    "REDACTED_CONNECTION_VALUE",
    "STANDARD_LLM_API_KEY_ENV_VAR",
    "connection_endpoint_url",
    "env_example_values",
    "env_value",
    "load_connection_settings",
    "parse_env_text",
    "redact_connection_settings",
]
