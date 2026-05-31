from datetime import date

from shared.fixtures import (
    FixtureCatalogError,
    fixtures_by_set,
    load_fixture_catalog,
    resolve_fixture_path,
    validate_fixture_catalog,
)
from shared.records import SourceType


def test_fixture_catalog_loads_and_paths_exist() -> None:
    catalog = load_fixture_catalog()

    assert catalog["catalog_version"] == "0.1"
    assert catalog["fixtures"]
    for entry in catalog["fixtures"]:
        assert resolve_fixture_path(entry).is_file()


def test_fixture_catalog_covers_shared_fixture_sets_a_through_g() -> None:
    catalog = load_fixture_catalog()
    grouped = fixtures_by_set(catalog)

    assert set(grouped) >= {"A", "B", "C", "D", "E", "F", "G"}
    assert {entry["access"] for entry in catalog["fixtures"]} >= {"public", "internal", "restricted"}
    assert any(entry["source_type"] == "document" for entry in catalog["fixtures"])
    assert any(entry["source_type"] == "web" for entry in catalog["fixtures"])
    assert any(entry["source_type"] == "table" for entry in catalog["fixtures"])
    assert any(entry["source_type"] == "api" for entry in catalog["fixtures"])
    assert all(SourceType(entry["source_type"]) for entry in catalog["fixtures"])


def test_restricted_fixture_is_marked_restricted() -> None:
    catalog = load_fixture_catalog()
    restricted = next(entry for entry in catalog["fixtures"] if entry["fixture_set"] == "B")

    assert restricted["access"] == "restricted"
    assert restricted["license"] == "restricted"
    assert "filter_before_ranking" in restricted["expected_behavior"]


def test_stale_fixture_has_old_as_of_date_and_freshness_note() -> None:
    catalog = load_fixture_catalog()
    stale = next(entry for entry in catalog["fixtures"] if entry["fixture_set"] == "C")

    assert date.fromisoformat(stale["freshness"]["as_of_date"]) < date(2024, 1, 1)
    assert "stale" in stale["freshness"]["note"].lower()
    assert stale["status"] == "deprecated"


def test_malformed_fixture_is_expected_to_fail_or_partial() -> None:
    catalog = load_fixture_catalog()
    malformed = next(entry for entry in catalog["fixtures"] if entry["fixture_set"] == "F")

    assert malformed["status"] == "failed"
    assert "fail_or_partial" in malformed["expected_behavior"]


def test_conflict_fixture_set_has_two_contradiction_sources() -> None:
    catalog = load_fixture_catalog()
    conflict_entries = fixtures_by_set(catalog)["D"]

    assert len(conflict_entries) == 2
    assert all("contradiction" in entry["expected_behavior"] for entry in conflict_entries)


def test_graph_fixture_mentions_entities_and_relations() -> None:
    catalog = load_fixture_catalog()
    graph = fixtures_by_set(catalog)["E"][0]

    assert "entities" in graph["expected_behavior"]
    assert "relations" in graph["expected_behavior"]
    assert "relation" in graph["freshness"]["note"].lower()


def test_external_fixture_set_has_url_retrieval_reliability_and_license_metadata() -> None:
    catalog = load_fixture_catalog()

    for entry in fixtures_by_set(catalog)["G"]:
        assert entry["external_link"]
        assert entry["freshness"]["retrieved_at"]
        assert entry["reliability"] in {"high", "medium", "low", "unverified"}
        assert entry["license"]


def test_external_link_and_citation_fields_are_present_for_citable_fixtures() -> None:
    catalog = load_fixture_catalog()

    for entry in catalog["fixtures"]:
        assert "external_link" in entry
        assert "citation" in entry
        if entry["status"] != "failed" and entry["access"] == "public":
            assert entry["external_link"]
            assert entry["citation"]


def test_catalog_validation_rejects_missing_required_metadata() -> None:
    catalog = load_fixture_catalog()
    broken = {
        **catalog,
        "fixtures": [
            {key: value for key, value in catalog["fixtures"][0].items() if key != "expected_behavior"}
        ],
    }

    try:
        validate_fixture_catalog(broken)
    except FixtureCatalogError:
        return

    raise AssertionError("Expected FixtureCatalogError for missing required metadata.")


def test_catalog_validation_rejects_path_traversal_outside_fixture_sources() -> None:
    catalog = load_fixture_catalog()
    broken = {
        **catalog,
        "fixtures": [
            {
                **catalog["fixtures"][0],
                "id": "fixture_escape_attempt",
                "path": "../project_milestones.md",
            },
            *catalog["fixtures"][1:],
        ],
    }

    try:
        validate_fixture_catalog(broken)
    except FixtureCatalogError:
        return

    raise AssertionError("Expected FixtureCatalogError for fixture path traversal.")
