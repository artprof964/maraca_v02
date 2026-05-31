from importlib import import_module

from shared import Partition


PARTITION_PACKAGES = [
    "source_registry",
    "ingestion",
    "enrichment",
    "storage",
    "planning",
    "retrieval",
    "ranking",
    "validation",
    "synthesis",
    "feedback",
    "evaluation",
    "shared",
]


def test_partition_packages_are_importable() -> None:
    for package_name in PARTITION_PACKAGES:
        assert import_module(package_name)


def test_partition_constants_match_shared_contract_values() -> None:
    for package_name in PARTITION_PACKAGES:
        if package_name == "shared":
            continue

        package = import_module(package_name)
        assert package.PARTITION == Partition(package_name).value
