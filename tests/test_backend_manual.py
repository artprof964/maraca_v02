from backend_app import build_demo_repository, run_keyword_manual
from backend_app.manual import main


def test_demo_repository_builds_keyword_and_vector_indexes() -> None:
    repository = build_demo_repository()

    assert repository.sources
    assert repository.documents
    assert repository.chunks
    assert repository.vector_embeddings
    assert repository.sparse_terms


def test_keyword_manual_runs_short_exact_query_path() -> None:
    result = run_keyword_manual('"alpha evidence bridge"', principal="reader")

    assert result.keyword_candidate_count >= 1
    assert result.executed_modes == ("keyword",)
    assert result.answer_text is not None
    assert "alpha evidence bridge" in result.answer_text
    assert result.citation_count >= 1


def test_keyword_manual_cli_returns_success(capsys) -> None:
    exit_code = main(["--query", '"alpha evidence bridge"'])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "keyword_candidates:" in output
    assert "executed_modes: keyword" in output
