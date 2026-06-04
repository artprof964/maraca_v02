import ast
from pathlib import Path

from shared.connection_settings import (
    CONNECTION_ENV_VAR_ALIASES,
    CONNECTION_ENV_VARS,
    CONNECTION_SETTING_NAME_BY_ENV_VAR,
    CONNECTION_SETTING_NAMES,
    DEEPSEEK_API_KEY_ENV_VAR,
    DEEPSEEK_OPEN_ART_ENV_VAR,
    DEFAULT_LLM_API_URL,
    DEFAULT_LLM_CLASSIFIER_MODEL,
    DEFAULT_LLM_EMBEDDING_MODEL,
    DEFAULT_LLM_FALLBACK_MODEL,
    DEFAULT_LLM_PRIMARY_MODEL,
    REDACTED_CONNECTION_VALUE,
    STANDARD_LLM_API_KEY_ENV_VAR,
    ConnectionSettings,
    connection_endpoint_url,
    env_example_values,
    load_connection_settings,
    parse_env_text,
    redact_connection_settings,
)


ROOT = Path(__file__).resolve().parents[1]


def test_standard_llm_key_and_explicit_alias_policy() -> None:
    standard_spec = CONNECTION_ENV_VARS[0]

    assert STANDARD_LLM_API_KEY_ENV_VAR == "deepseek-open-art"
    assert STANDARD_LLM_API_KEY_ENV_VAR == DEEPSEEK_OPEN_ART_ENV_VAR
    assert standard_spec.name == DEEPSEEK_OPEN_ART_ENV_VAR
    assert standard_spec.setting_name == "llm_api_key"
    assert standard_spec.secret is True
    assert standard_spec.aliases == (DEEPSEEK_API_KEY_ENV_VAR,)
    assert dict(CONNECTION_ENV_VAR_ALIASES) == {
        DEEPSEEK_OPEN_ART_ENV_VAR: (DEEPSEEK_API_KEY_ENV_VAR,)
    }
    assert CONNECTION_SETTING_NAME_BY_ENV_VAR[DEEPSEEK_OPEN_ART_ENV_VAR] == "llm_api_key"
    assert CONNECTION_SETTING_NAME_BY_ENV_VAR[DEEPSEEK_API_KEY_ENV_VAR] == "llm_api_key"
    assert DEEPSEEK_API_KEY_ENV_VAR not in env_example_values()


def test_connection_settings_loads_standard_key_and_defaults_from_mapping() -> None:
    settings = load_connection_settings({DEEPSEEK_OPEN_ART_ENV_VAR: "standard-secret"})

    assert isinstance(settings, ConnectionSettings)
    assert settings.llm_api_key == "standard-secret"
    assert settings.llm_api_url == DEFAULT_LLM_API_URL
    assert settings.llm_primary_model == DEFAULT_LLM_PRIMARY_MODEL
    assert settings.llm_fallback_model == DEFAULT_LLM_FALLBACK_MODEL
    assert settings.llm_classifier_model == DEFAULT_LLM_CLASSIFIER_MODEL
    assert settings.llm_embedding_model == DEFAULT_LLM_EMBEDDING_MODEL
    assert settings.to_dict()["llm_api_key"] == "standard-secret"
    assert settings.to_redacted_dict()["llm_api_key"] == REDACTED_CONNECTION_VALUE


def test_connection_settings_supports_alias_and_standard_precedence() -> None:
    alias_settings = load_connection_settings({DEEPSEEK_API_KEY_ENV_VAR: "legacy-secret"})
    both_settings = load_connection_settings(
        {
            DEEPSEEK_OPEN_ART_ENV_VAR: "standard-secret",
            DEEPSEEK_API_KEY_ENV_VAR: "legacy-secret",
        }
    )

    assert alias_settings.llm_api_key == "legacy-secret"
    assert both_settings.llm_api_key == "standard-secret"


def test_connection_settings_use_pure_injected_mappings_for_overrides() -> None:
    settings = load_connection_settings(
        {
            DEEPSEEK_OPEN_ART_ENV_VAR: "standard-secret",
            "LLM_API_URL": "https://llm.example.test/v1",
            "LLM_PRIMARY_MODEL": "primary-test",
            "LLM_FALLBACK_MODEL": "fallback-test",
            "LLM_CLASSIFIER_MODEL": "classifier-test",
            "LLM_EMBEDDING_MODEL": "embedding-test",
        }
    )

    assert settings.to_dict() == {
        "llm_api_key": "standard-secret",
        "llm_api_url": "https://llm.example.test/v1",
        "llm_primary_model": "primary-test",
        "llm_fallback_model": "fallback-test",
        "llm_classifier_model": "classifier-test",
        "llm_embedding_model": "embedding-test",
    }
    assert set(settings.to_dict()) == CONNECTION_SETTING_NAMES


def test_redaction_covers_secrets_tokens_api_keys_and_standard_key_names() -> None:
    payload = {
        DEEPSEEK_OPEN_ART_ENV_VAR: "standard-secret",
        DEEPSEEK_API_KEY_ENV_VAR: "legacy-secret",
        "service_token": "token-secret",
        "nested": {
            "clientSecret": "client-secret",
            "plain": "visible",
            "items": [
                {"api-key": "api-secret", "api_key_env": "SERVICE_API_KEY"},
                ("kept", {"api_key": "nested-api-secret"}),
            ],
        },
    }

    redacted = redact_connection_settings(payload)

    assert redacted[DEEPSEEK_OPEN_ART_ENV_VAR] == REDACTED_CONNECTION_VALUE
    assert redacted[DEEPSEEK_API_KEY_ENV_VAR] == REDACTED_CONNECTION_VALUE
    assert redacted["service_token"] == REDACTED_CONNECTION_VALUE
    assert redacted["nested"]["clientSecret"] == REDACTED_CONNECTION_VALUE
    assert redacted["nested"]["plain"] == "visible"
    assert redacted["nested"]["items"][0]["api-key"] == REDACTED_CONNECTION_VALUE
    assert redacted["nested"]["items"][0]["api_key_env"] == "SERVICE_API_KEY"
    assert redacted["nested"]["items"][1][1]["api_key"] == REDACTED_CONNECTION_VALUE
    assert payload["nested"]["items"][0]["api-key"] == "api-secret"


def test_env_example_adds_llm_registry_without_changing_backend_defaults() -> None:
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    parsed = parse_env_text(env_text)

    assert parsed[DEEPSEEK_OPEN_ART_ENV_VAR] == ""
    assert parsed["LLM_API_URL"] == DEFAULT_LLM_API_URL
    assert parsed["LLM_PRIMARY_MODEL"] == DEFAULT_LLM_PRIMARY_MODEL
    assert parsed["LLM_FALLBACK_MODEL"] == DEFAULT_LLM_FALLBACK_MODEL
    assert parsed["LLM_CLASSIFIER_MODEL"] == DEFAULT_LLM_CLASSIFIER_MODEL
    assert parsed["LLM_EMBEDDING_MODEL"] == DEFAULT_LLM_EMBEDDING_MODEL
    assert "DEEPSEEK_API_KEY=" not in env_text
    assert "DEEPSEEK_API_KEY" in env_text
    assert parsed["QDRANT_URL"] == "http://localhost:6333"
    assert parsed["QDRANT_API_KEY"] == ""
    assert parsed["QDRANT_COLLECTION"] == "evidence_chunks"
    assert parsed["NEO4J_URI"] == "bolt://localhost:7687"
    assert parsed["NEO4J_USER"] == "neo4j"
    assert parsed["NEO4J_PASSWORD"] == "localdevpassword"
    assert parsed["NEO4J_DATABASE"] == "neo4j"
    assert parsed["RAG_STORAGE_ROOT"] == ".local/storage"
    assert parsed["RAG_MODEL_PROFILE"] == "local-dev"


def test_connection_endpoint_url_normalizes_base_and_path_slashes() -> None:
    assert connection_endpoint_url("https://llm.example.test/", "/chat/completions") == (
        "https://llm.example.test/chat/completions"
    )


def test_connection_settings_implementation_uses_injected_mappings_only() -> None:
    source = (ROOT / "src" / "shared" / "connection_settings.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    banned_modules = {"os", "dotenv", "requests", "httpx", "urllib", "socket", "subprocess"}
    imported_modules = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert imported_modules.isdisjoint(banned_modules)
    assert "os.environ" not in source
    assert "sleep(" not in source
