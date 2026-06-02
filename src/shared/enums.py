"""Enum coercion and enum-keyed lookup helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import TypeVar


EnumT = TypeVar("EnumT", bound=StrEnum)
ValueT = TypeVar("ValueT")


def coerce_str_enum(
    enum_type: type[EnumT],
    value: object,
    *,
    field_name: str | None = None,
    error_factory: Callable[[str, object], Exception] | None = None,
) -> EnumT:
    """Return a string enum member from an enum-or-string input."""
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        if error_factory is not None:
            label = field_name or enum_type.__name__
            raise error_factory(label, value) from exc
        raise


def lookup_str_enum(
    mapping: Mapping[EnumT, ValueT],
    enum_type: type[EnumT],
    key: EnumT | object,
    *,
    field_name: str | None = None,
    error_factory: Callable[[str, object], Exception] | None = None,
) -> ValueT:
    """Look up a mapping value using an enum member or its raw value."""
    resolved_key = coerce_str_enum(
        enum_type,
        key,
        field_name=field_name,
        error_factory=error_factory,
    )
    return mapping[resolved_key]


coerce_enum = coerce_str_enum
lookup_enum_key = lookup_str_enum


__all__ = [
    "coerce_enum",
    "coerce_str_enum",
    "lookup_enum_key",
    "lookup_str_enum",
]
