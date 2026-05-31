"""Declarative stack selections for the initial retrieval-center baseline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .contracts import _serialize_contract


class StackComponentCategory(StrEnum):
    INGESTION_INDEXING = "ingestion_indexing"
    GRAPH_STORE = "graph_store"
    VECTOR_STORE = "vector_store"
    ORCHESTRATION = "orchestration"
    METADATA_STORE = "metadata_store"
    RAW_SOURCE_STORE = "raw_source_store"
    MODEL_SERVICES = "model_services"


class StackComponentType(StrEnum):
    FRAMEWORK = "framework"
    DATABASE = "database"
    STORE = "store"
    SERVICE = "service"
    MOCK = "mock"


@dataclass(frozen=True, slots=True)
class StackComponent:
    category: StackComponentCategory
    name: str
    component_type: StackComponentType
    purpose: str
    package_names: tuple[str, ...] = ()
    runtime_dependency_required: bool = False
    fallback_for: StackComponentCategory | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _serialize_contract(asdict(self))
        payload["package_names"] = list(self.package_names)
        return payload


REQUIRED_STACK_CATEGORIES: tuple[StackComponentCategory, ...] = tuple(
    StackComponentCategory
)

_BASELINE_STACK_COMPONENTS: tuple[StackComponent, ...] = (
    StackComponent(
        category=StackComponentCategory.INGESTION_INDEXING,
        name="LlamaIndex",
        component_type=StackComponentType.FRAMEWORK,
        purpose="Document ingestion, node abstractions, indexing, and retrieval adapters.",
        package_names=("llama-index",),
    ),
    StackComponent(
        category=StackComponentCategory.GRAPH_STORE,
        name="Neo4j",
        component_type=StackComponentType.DATABASE,
        purpose="Knowledge graph persistence, relationship traversal, and Cypher retrieval.",
        package_names=("neo4j",),
    ),
    StackComponent(
        category=StackComponentCategory.VECTOR_STORE,
        name="Qdrant",
        component_type=StackComponentType.DATABASE,
        purpose="Dense vector retrieval and hybrid dense/sparse search.",
        package_names=("qdrant-client",),
    ),
    StackComponent(
        category=StackComponentCategory.ORCHESTRATION,
        name="LangGraph",
        component_type=StackComponentType.FRAMEWORK,
        purpose="Planner workflows, conditional routing, validation loops, and repair loops.",
        package_names=("langgraph",),
    ),
    StackComponent(
        category=StackComponentCategory.METADATA_STORE,
        name="Relational metadata store",
        component_type=StackComponentType.STORE,
        purpose="Source registry, ingestion jobs, traces, evaluations, and feedback metadata.",
    ),
    StackComponent(
        category=StackComponentCategory.RAW_SOURCE_STORE,
        name="Object store or filesystem",
        component_type=StackComponentType.STORE,
        purpose="Raw source files, extracted text, snapshots, and audit artifacts.",
    ),
    StackComponent(
        category=StackComponentCategory.MODEL_SERVICES,
        name="Model services",
        component_type=StackComponentType.SERVICE,
        purpose="Embedding, reranking, validation, and answer synthesis model endpoints.",
    ),
)

BASELINE_STACK_COMPONENTS: tuple[StackComponent, ...] = _BASELINE_STACK_COMPONENTS
BASELINE_STACK_BY_CATEGORY: Mapping[StackComponentCategory, StackComponent] = (
    MappingProxyType({component.category: component for component in BASELINE_STACK_COMPONENTS})
)

_FALLBACK_STACK_COMPONENTS: tuple[StackComponent, ...] = tuple(
    StackComponent(
        category=category,
        name=f"Mock {baseline.name}",
        component_type=StackComponentType.MOCK,
        purpose=f"Dependency-free local/test substitute for {baseline.purpose[0].lower()}{baseline.purpose[1:]}",
        runtime_dependency_required=False,
        fallback_for=category,
    )
    for category, baseline in BASELINE_STACK_BY_CATEGORY.items()
)

FALLBACK_STACK_COMPONENTS: tuple[StackComponent, ...] = _FALLBACK_STACK_COMPONENTS
FALLBACK_STACK_BY_CATEGORY: Mapping[StackComponentCategory, StackComponent] = (
    MappingProxyType({component.category: component for component in FALLBACK_STACK_COMPONENTS})
)


def get_baseline_stack() -> tuple[StackComponent, ...]:
    return BASELINE_STACK_COMPONENTS


def get_baseline_component(
    category: StackComponentCategory | str,
) -> StackComponent:
    return BASELINE_STACK_BY_CATEGORY[StackComponentCategory(category)]


def get_fallback_stack() -> tuple[StackComponent, ...]:
    return FALLBACK_STACK_COMPONENTS


def get_fallback_component(
    category: StackComponentCategory | str,
) -> StackComponent:
    return FALLBACK_STACK_BY_CATEGORY[StackComponentCategory(category)]


def serialize_stack_component(component: StackComponent) -> dict[str, Any]:
    return component.to_dict()


def serialize_stack_components(
    components: Iterable[StackComponent],
) -> list[dict[str, Any]]:
    return [component.to_dict() for component in components]


def validate_stack_selections(
    baseline: Mapping[StackComponentCategory, StackComponent] = BASELINE_STACK_BY_CATEGORY,
    fallbacks: Mapping[StackComponentCategory, StackComponent] = FALLBACK_STACK_BY_CATEGORY,
) -> tuple[str, ...]:
    errors: list[str] = []

    for category in REQUIRED_STACK_CATEGORIES:
        baseline_component = baseline.get(category)
        fallback_component = fallbacks.get(category)

        if baseline_component is None:
            errors.append(f"Missing baseline component for {category.value}.")
        elif baseline_component.component_type is StackComponentType.MOCK:
            errors.append(f"Baseline component for {category.value} cannot be a mock.")

        if fallback_component is None:
            errors.append(f"Missing fallback component for {category.value}.")
        elif fallback_component.component_type is not StackComponentType.MOCK:
            errors.append(f"Fallback component for {category.value} must be a mock.")
        elif fallback_component.fallback_for is not category:
            errors.append(f"Fallback component for {category.value} must reference its category.")

    return tuple(errors)
