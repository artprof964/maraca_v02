"""Shared fixture catalog helpers for deterministic source tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_FIXTURE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "fixture_catalog.json"

REQUIRED_FIXTURE_FIELDS = {
    "id",
    "fixture_set",
    "source_name",
    "source_type",
    "access",
    "license",
    "reliability",
    "freshness",
    "status",
    "path",
    "external_link",
    "citation",
    "expected_behavior",
}

REQUIRED_FIXTURE_SETS = {"A", "B", "C", "D", "E", "F", "G"}


class FixtureCatalogError(ValueError):
    """Raised when the fixture catalog is missing required metadata."""


def load_fixture_catalog(catalog_path: str | Path | None = None) -> dict[str, Any]:
    """Load the fixture catalog JSON and validate its lightweight contract."""

    path = Path(catalog_path) if catalog_path is not None else DEFAULT_FIXTURE_CATALOG_PATH
    with path.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)
    validate_fixture_catalog(catalog, catalog_path=path)
    return catalog


def fixture_catalog_base(catalog_path: str | Path | None = None) -> Path:
    """Return the directory used to resolve relative fixture paths."""

    path = Path(catalog_path) if catalog_path is not None else DEFAULT_FIXTURE_CATALOG_PATH
    return path.resolve().parent


def fixture_sources_base(catalog_path: str | Path | None = None) -> Path:
    """Return the only directory catalog fixture paths may reference."""

    return fixture_catalog_base(catalog_path) / "sources"


def resolve_fixture_path(entry: dict[str, Any], catalog_path: str | Path | None = None) -> Path:
    """Resolve a fixture path relative to the catalog file."""

    relative_path = Path(entry["path"])
    if relative_path.is_absolute():
        raise FixtureCatalogError(f"{entry.get('id', '<unknown>')} path must be relative: {entry['path']}")

    candidate = (fixture_catalog_base(catalog_path) / relative_path).resolve()
    allowed_base = fixture_sources_base(catalog_path).resolve()
    try:
        candidate.relative_to(allowed_base)
    except ValueError as exc:
        fixture_id = entry.get("id", "<unknown>")
        raise FixtureCatalogError(f"{fixture_id} path escapes fixture sources: {entry['path']}") from exc

    return candidate


def fixtures_by_set(catalog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group catalog entries by project_tests.md fixture set label."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in catalog.get("fixtures", []):
        grouped.setdefault(entry["fixture_set"], []).append(entry)
    return grouped


def validate_fixture_catalog(catalog: dict[str, Any], catalog_path: str | Path | None = None) -> None:
    """Validate required metadata and referenced files without parsing ingestion content."""

    fixtures = catalog.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise FixtureCatalogError("fixture catalog must contain a non-empty fixtures list")

    seen_ids: set[str] = set()
    seen_sets: set[str] = set()
    for entry in fixtures:
        if not isinstance(entry, dict):
            raise FixtureCatalogError("fixture entries must be JSON objects")

        missing = REQUIRED_FIXTURE_FIELDS - set(entry)
        if missing:
            fixture_id = entry.get("id", "<unknown>")
            raise FixtureCatalogError(f"{fixture_id} missing required fields: {sorted(missing)}")

        fixture_id = entry["id"]
        if fixture_id in seen_ids:
            raise FixtureCatalogError(f"duplicate fixture id: {fixture_id}")
        seen_ids.add(fixture_id)
        seen_sets.add(entry["fixture_set"])

        freshness = entry["freshness"]
        if not isinstance(freshness, dict) or "as_of_date" not in freshness or "note" not in freshness:
            raise FixtureCatalogError(f"{fixture_id} freshness must include as_of_date and note")

        if not resolve_fixture_path(entry, catalog_path).is_file():
            raise FixtureCatalogError(f"{fixture_id} path does not exist: {entry['path']}")

    missing_sets = REQUIRED_FIXTURE_SETS - seen_sets
    if missing_sets:
        raise FixtureCatalogError(f"missing fixture sets: {sorted(missing_sets)}")
