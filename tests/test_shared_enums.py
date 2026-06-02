from shared import (
    EnvironmentName,
    SourceType,
    coerce_str_enum,
    lookup_str_enum,
)
from source_registry import SourceRegistryError


def test_coerce_str_enum_accepts_member_and_string_values() -> None:
    assert coerce_str_enum(EnvironmentName, EnvironmentName.LOCAL) is EnvironmentName.LOCAL
    assert coerce_str_enum(EnvironmentName, "production") is EnvironmentName.PRODUCTION


def test_coerce_str_enum_preserves_native_value_error_without_factory() -> None:
    try:
        coerce_str_enum(EnvironmentName, "sandbox")
    except ValueError as exc:
        assert str(exc) == "'sandbox' is not a valid EnvironmentName"
        return

    raise AssertionError("Expected native ValueError for invalid EnvironmentName.")


def test_coerce_str_enum_wraps_errors_with_factory_and_cause() -> None:
    def source_registry_error(field_name: str, value: object) -> SourceRegistryError:
        return SourceRegistryError(f"invalid {field_name}: {value!r}")

    try:
        coerce_str_enum(
            SourceType,
            "not_a_source_type",
            field_name="source_type",
            error_factory=source_registry_error,
        )
    except SourceRegistryError as exc:
        assert str(exc) == "invalid source_type: 'not_a_source_type'"
        assert isinstance(exc.__cause__, ValueError)
        return

    raise AssertionError("Expected SourceRegistryError for invalid SourceType.")


def test_lookup_str_enum_coerces_key_and_preserves_mapping_keyerror() -> None:
    mapping = {EnvironmentName.LOCAL: "local-profile"}

    assert lookup_str_enum(mapping, EnvironmentName, "local") == "local-profile"

    try:
        lookup_str_enum(mapping, EnvironmentName, EnvironmentName.TEST)
    except KeyError as exc:
        assert exc.args == (EnvironmentName.TEST,)
        return

    raise AssertionError("Expected KeyError for missing coerced enum key.")
