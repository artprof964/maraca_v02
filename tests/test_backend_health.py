from backend_app.health import main, run_health_checks


def test_health_checks_report_optional_backend_imports() -> None:
    checks = run_health_checks(env_file=None)
    by_name = {check.name: check for check in checks}

    assert by_name["qdrant-client"].ok
    assert by_name["neo4j"].ok
    assert by_name["langgraph"].ok
    assert by_name["llama-index-core"].ok
    assert "qdrant-service" in by_name
    assert "neo4j-service" in by_name
    assert by_name["langgraph-runtime"].ok
    assert by_name["langgraph-runtime"].status == "ready"


def test_health_cli_is_lenient_by_default(capsys) -> None:
    exit_code = main(["--env-file", ""])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "qdrant-client" in output
    assert "neo4j-service" in output
    assert "langgraph-runtime" in output


def test_health_cli_strict_services_reports_unavailable_services(capsys) -> None:
    exit_code = main(["--strict-services", "--env-file", ""])
    output = capsys.readouterr().out

    assert exit_code in {0, 1}
    assert "qdrant-service" in output
    assert "neo4j-service" in output


def test_health_checks_load_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "QDRANT_URL=http://example.test:6333",
                "QDRANT_COLLECTION=env_chunks",
                "NEO4J_URI=bolt://example.test:7687",
                "NEO4J_USER=neo4j",
                "NEO4J_PASSWORD=secret",
                "NEO4J_DATABASE=env_graph",
            )
        ),
        encoding="utf-8",
    )
    for key in ("QDRANT_URL", "QDRANT_COLLECTION", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"):
        monkeypatch.delenv(key, raising=False)

    checks = run_health_checks(env_file=str(env_file))
    by_name = {check.name: check for check in checks}

    assert by_name["QDRANT_URL"].ok
    assert by_name["QDRANT_COLLECTION"].ok
    assert by_name["QDRANT_COLLECTION"].detail == "env_chunks"
    assert by_name["NEO4J_URI"].ok
    assert by_name["NEO4J_USER"].ok
    assert by_name["NEO4J_PASSWORD"].ok
    assert by_name["NEO4J_PASSWORD"].detail == "<set>"
    assert by_name["NEO4J_DATABASE"].ok
    assert by_name["NEO4J_DATABASE"].detail == "env_graph"


def test_health_checks_report_backend_name_defaults_when_env_values_are_absent(monkeypatch) -> None:
    for key in ("QDRANT_COLLECTION", "NEO4J_DATABASE"):
        monkeypatch.delenv(key, raising=False)

    checks = run_health_checks(env_file=None)
    by_name = {check.name: check for check in checks}

    assert by_name["QDRANT_COLLECTION"].ok
    assert by_name["QDRANT_COLLECTION"].status == "default"
    assert by_name["QDRANT_COLLECTION"].detail == "evidence_chunks"
    assert by_name["NEO4J_DATABASE"].ok
    assert by_name["NEO4J_DATABASE"].status == "default"
    assert by_name["NEO4J_DATABASE"].detail == "neo4j"
