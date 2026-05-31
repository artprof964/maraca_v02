"""Small executable backend manual for keyword-first smoke checks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from ingestion import run_ingestion_job, split_document_into_chunks
from planning import run_planned_query
from retrieval import commit_sparse_index, commit_vectors, run_keyword_retrieval
from shared import (
    AccessLevel,
    AccessMethod,
    FreshnessPolicy,
    LicensePolicy,
    ReliabilityLevel,
    SourceStatus,
    SourceType,
    load_fixture_catalog,
)
from source_registry import SourceRegistry
from storage import InMemoryStorageRepository, commit_storage_bundle


DEFAULT_QUERY = '"alpha evidence bridge"'
DEFAULT_FIXTURE_ID = "fixture_a_public_document"


@dataclass(frozen=True, slots=True)
class ManualRun:
    repository: InMemoryStorageRepository
    query: str
    keyword_candidate_count: int
    executed_modes: tuple[str, ...]
    answer_text: str | None
    citation_count: int
    log_count: int


def build_demo_repository(
    *,
    fixture_id: str = DEFAULT_FIXTURE_ID,
) -> InMemoryStorageRepository:
    """Ingest the public fixture and build local keyword/vector indexes."""

    repository = InMemoryStorageRepository()
    registry = SourceRegistry()
    fixture = _fixture(fixture_id)
    source = registry.register_source(
        source_name=str(fixture["source_name"]),
        source_type=SourceType(str(fixture["source_type"])),
        owner="backend-manual",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel(str(fixture["access"])),
        external_link=fixture["external_link"] if isinstance(fixture["external_link"], str) else None,
        internal_location=str(fixture["path"]),
        license_policy=LicensePolicy(str(fixture["license"])),
        reliability_level=ReliabilityLevel(str(fixture["reliability"])),
        freshness_policy=FreshnessPolicy(str(fixture["freshness"]["policy"])),
        status=SourceStatus(str(fixture["status"])),
    )
    ingestion = run_ingestion_job(source, fixture_entry=fixture)
    if ingestion.document_record is None or ingestion.normalized_document is None:
        raise RuntimeError(f"{fixture_id} did not produce an indexed document")
    chunks = split_document_into_chunks(ingestion.normalized_document, ingestion.document_record, source=source)
    commit_storage_bundle(
        repository,
        raw_artifact=ingestion.raw_artifact,
        source=source,
        document=ingestion.document_record,
        chunks=chunks,
        job=ingestion.job,
        logs=ingestion.logs,
        errors=ingestion.errors,
    )
    commit_vectors(repository, repository.chunks.values())
    commit_sparse_index(repository, repository.chunks.values())
    return repository


def run_keyword_manual(
    query: str = DEFAULT_QUERY,
    *,
    principal: str = "reader",
    current_date: date | None = date(2026, 5, 29),
) -> ManualRun:
    """Run the shortest useful keyword-to-answer backend path."""

    repository = build_demo_repository()
    keyword_candidates = run_keyword_retrieval(query, repository, top_k=3)
    planned = run_planned_query(query, repository, principal=principal, current_date=current_date)
    synthesis = planned.synthesis
    answer = synthesis.answer if synthesis is not None else None
    return ManualRun(
        repository=repository,
        query=query,
        keyword_candidate_count=len(keyword_candidates),
        executed_modes=tuple(mode.value for mode in planned.executed_modes),
        answer_text=answer.answer_text if answer is not None else None,
        citation_count=len(answer.citation_map) if answer is not None else 0,
        log_count=len(repository.logs),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the backend keyword smoke manual.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Keyword or exact phrase query to run.")
    parser.add_argument("--principal", default="reader", help="Principal used for access filtering.")
    args = parser.parse_args(argv)

    result = run_keyword_manual(args.query, principal=args.principal)
    print(f"query: {result.query}")
    print(f"keyword_candidates: {result.keyword_candidate_count}")
    print(f"executed_modes: {', '.join(result.executed_modes) or 'none'}")
    print(f"citations: {result.citation_count}")
    print(f"logs: {result.log_count}")
    if result.answer_text:
        print("answer:")
        print(result.answer_text)
    return 0 if result.keyword_candidate_count and result.answer_text else 1


def _fixture(fixture_id: str) -> dict[str, object]:
    catalog = load_fixture_catalog()
    return next(entry for entry in catalog["fixtures"] if entry["id"] == fixture_id)


if __name__ == "__main__":
    raise SystemExit(main())
