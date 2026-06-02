"""Serialization helpers for MARACA contract payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any


def serialize_value(value: Any, *, tuple_as_list: bool = False) -> Any:
    """Convert common contract values into JSON-ready primitives."""
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_value(item, tuple_as_list=tuple_as_list) for item in value]
    if isinstance(value, tuple):
        items = [serialize_value(item, tuple_as_list=tuple_as_list) for item in value]
        return items if tuple_as_list else tuple(items)
    if isinstance(value, Mapping):
        return {
            key: serialize_value(item, tuple_as_list=tuple_as_list)
            for key, item in value.items()
        }
    return value


def serialize_mapping(
    data: Mapping[str, Any],
    *,
    tuple_as_list: bool = False,
) -> dict[str, Any]:
    """Serialize a mapping while preserving existing tuple behavior by default."""
    return {
        key: serialize_value(value, tuple_as_list=tuple_as_list)
        for key, value in data.items()
    }


def serialize_dataclass(instance: Any, *, tuple_as_list: bool = False) -> dict[str, Any]:
    """Serialize a dataclass instance using the existing asdict-based shape."""
    if not is_dataclass(instance) or isinstance(instance, type):
        raise TypeError("serialize_dataclass expects a dataclass instance.")
    return serialize_mapping(asdict(instance), tuple_as_list=tuple_as_list)


def serialize_contract(
    data: Mapping[str, Any] | object,
    *,
    tuple_as_list: bool = False,
) -> dict[str, Any]:
    """Serialize a dataclass instance or mapping into contract payload values."""
    if is_dataclass(data) and not isinstance(data, type):
        return serialize_dataclass(data, tuple_as_list=tuple_as_list)
    if isinstance(data, Mapping):
        return serialize_mapping(data, tuple_as_list=tuple_as_list)
    raise TypeError("serialize_contract expects a dataclass instance or mapping.")


__all__ = [
    "serialize_contract",
    "serialize_dataclass",
    "serialize_mapping",
    "serialize_value",
]
