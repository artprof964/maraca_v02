from shared import (
    BASELINE_STACK_BY_CATEGORY,
    FALLBACK_STACK_BY_CATEGORY,
    REQUIRED_STACK_CATEGORIES,
    StackComponent,
    StackComponentCategory,
    StackComponentType,
    get_baseline_component,
    get_baseline_stack,
    get_fallback_component,
    get_fallback_stack,
    serialize_stack_component,
    serialize_stack_components,
    validate_stack_selections,
)


def test_required_categories_have_baseline_and_fallback_components() -> None:
    assert set(REQUIRED_STACK_CATEGORIES) == set(StackComponentCategory)
    assert set(BASELINE_STACK_BY_CATEGORY) == set(StackComponentCategory)
    assert set(FALLBACK_STACK_BY_CATEGORY) == set(StackComponentCategory)
    assert validate_stack_selections() == ()


def test_baseline_selects_initial_project_stack() -> None:
    selected_names = {
        component.category: component.name for component in get_baseline_stack()
    }

    assert selected_names == {
        StackComponentCategory.INGESTION_INDEXING: "LlamaIndex",
        StackComponentCategory.GRAPH_STORE: "Neo4j",
        StackComponentCategory.VECTOR_STORE: "Qdrant",
        StackComponentCategory.ORCHESTRATION: "LangGraph",
        StackComponentCategory.METADATA_STORE: "Relational metadata store",
        StackComponentCategory.RAW_SOURCE_STORE: "Object store or filesystem",
        StackComponentCategory.MODEL_SERVICES: "Model services",
    }


def test_stack_selection_is_declarative_without_runtime_dependencies() -> None:
    for component in get_baseline_stack():
        assert component.runtime_dependency_required is False
        assert component.package_names or component.category in {
            StackComponentCategory.METADATA_STORE,
            StackComponentCategory.RAW_SOURCE_STORE,
            StackComponentCategory.MODEL_SERVICES,
        }


def test_fallback_mocks_exist_for_every_required_category() -> None:
    fallback_stack = get_fallback_stack()

    assert len(fallback_stack) == len(REQUIRED_STACK_CATEGORIES)
    assert all(component.component_type is StackComponentType.MOCK for component in fallback_stack)
    assert all(component.runtime_dependency_required is False for component in fallback_stack)
    assert all(component.fallback_for is component.category for component in fallback_stack)
    assert get_fallback_component("vector_store").name == "Mock Qdrant"


def test_component_lookup_accepts_enum_and_string_categories() -> None:
    assert get_baseline_component(StackComponentCategory.GRAPH_STORE).name == "Neo4j"
    assert get_baseline_component("orchestration").name == "LangGraph"


def test_serialization_is_stable_and_json_ready() -> None:
    component_payload = serialize_stack_component(
        get_baseline_component(StackComponentCategory.VECTOR_STORE)
    )
    stack_payload = serialize_stack_components(get_baseline_stack())

    assert component_payload == {
        "category": "vector_store",
        "name": "Qdrant",
        "component_type": "database",
        "purpose": "Dense vector retrieval and hybrid dense/sparse search.",
        "package_names": ["qdrant-client"],
        "runtime_dependency_required": False,
        "fallback_for": None,
    }
    assert [component["category"] for component in stack_payload] == [
        "ingestion_indexing",
        "graph_store",
        "vector_store",
        "orchestration",
        "metadata_store",
        "raw_source_store",
        "model_services",
    ]


def test_validation_reports_missing_or_invalid_fallbacks() -> None:
    invalid_fallback = StackComponent(
        category=StackComponentCategory.VECTOR_STORE,
        name="Real Qdrant fallback",
        component_type=StackComponentType.DATABASE,
        purpose="Invalid real fallback.",
    )

    errors = validate_stack_selections(
        fallbacks={
            **FALLBACK_STACK_BY_CATEGORY,
            StackComponentCategory.VECTOR_STORE: invalid_fallback,
        }
    )

    assert errors == ("Fallback component for vector_store must be a mock.",)
