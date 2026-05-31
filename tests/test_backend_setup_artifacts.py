from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_backend_entry_points_and_full_extra_are_declared() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    scripts = pyproject["project"]["scripts"]
    assert scripts["rag-center-health"] == "backend_app.health:main"
    assert scripts["rag-center-smoke"] == "backend_app.manual:main"

    optional = pyproject["project"]["optional-dependencies"]
    full_dependencies = "\n".join(optional["full"])
    backend_dependencies = "\n".join(optional["backend"])

    for dependency in ("langgraph", "llama-index-core", "neo4j", "qdrant-client"):
        assert dependency in backend_dependencies
        assert dependency in full_dependencies
    assert "pytest" in full_dependencies


def test_env_example_contains_local_service_contract() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    expected_lines = {
        "QDRANT_URL=http://localhost:6333",
        "QDRANT_COLLECTION=evidence_chunks",
        "NEO4J_URI=bolt://localhost:7687",
        "NEO4J_USER=neo4j",
        "NEO4J_PASSWORD=localdevpassword",
        "NEO4J_DATABASE=neo4j",
        "RAG_STORAGE_ROOT=.local/storage",
        "RAG_MODEL_PROFILE=local-dev",
    }
    for line in expected_lines:
        assert line in env_example


def test_compose_file_declares_qdrant_and_neo4j_services() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    for expected in (
        "qdrant/qdrant:v1.18.0",
        "neo4j:5.26-community",
        '"6333:6333"',
        '"6334:6334"',
        '"7474:7474"',
        '"7687:7687"',
        "NEO4J_AUTH:",
        "qdrant_data:",
        "neo4j_data:",
    ):
        assert expected in compose


def test_setup_scripts_wire_health_smoke_and_service_startup() -> None:
    setup_script = (ROOT / "scripts" / "setup_full_backend.ps1").read_text(
        encoding="utf-8"
    )
    test_script = (ROOT / "scripts" / "test_full_backend.ps1").read_text(
        encoding="utf-8"
    )

    assert 'pip install -e ".[full]"' in setup_script
    assert "winget install --id Docker.DockerDesktop --exact" in setup_script
    assert "docker compose up -d qdrant neo4j" in setup_script
    assert "rag-center-health.exe --env-file $EnvFile" in setup_script
    assert "rag-center-smoke.exe" in setup_script

    assert "python.exe -m pip check" in test_script
    assert "rag-center-health.exe --strict-services --env-file $EnvFile" in test_script
    assert "rag-center-smoke.exe" in test_script
    assert "python.exe -m unittest discover -s tests" in test_script
    assert "python.exe -m pytest" in test_script
