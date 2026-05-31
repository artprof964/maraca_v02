from datetime import date
import unittest

from evaluation import store_evaluation_trace
from feedback import capture_feedback
from ingestion import IngestionError, run_ingestion_job, split_document_into_chunks
from ranking import RankingConfig, select_ranked_evidence
from retrieval import commit_sparse_index, commit_vectors, run_hybrid_search
from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    ErrorType,
    FailureCategory,
    FreshnessPolicy,
    IngestionStatus,
    LicensePolicy,
    Partition,
    ReliabilityLevel,
    SourceStatus,
    SourceType,
    UserRating,
    load_fixture_catalog,
    new_correlation_id,
)
from source_registry import SourceRegistry
from storage import InMemoryStorageRepository, commit_storage_bundle, verify_storage_commit
from synthesis import generate_answer


def _fixture(fixture_id: str) -> dict[str, object]:
    catalog = load_fixture_catalog()
    return next(entry for entry in catalog["fixtures"] if entry["id"] == fixture_id)


def _register_fixture(
    registry: SourceRegistry,
    fixture_id: str,
    *,
    allowed_principals: tuple[str, ...] = (),
):
    entry = _fixture(fixture_id)
    source = registry.register_source(
        source_name=str(entry["source_name"]),
        source_type=SourceType(str(entry["source_type"])),
        owner="milestone1-smoke",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel(str(entry["access"])),
        external_link=entry["external_link"] if isinstance(entry["external_link"], str) else None,
        internal_location=str(entry["path"]),
        license_policy=LicensePolicy(str(entry["license"])),
        allowed_principals=allowed_principals,
        reliability_level=ReliabilityLevel(str(entry["reliability"])),
        freshness_policy=FreshnessPolicy(str(entry["freshness"]["policy"])),
        status=SourceStatus(str(entry["status"])),
    )
    return source, entry


def _store_ingested_fixture(
    storage: InMemoryStorageRepository,
    registry: SourceRegistry,
    fixture_id: str,
    *,
    allowed_principals: tuple[str, ...] = (),
):
    source, entry = _register_fixture(registry, fixture_id, allowed_principals=allowed_principals)
    result = run_ingestion_job(source, fixture_entry=entry)
    if result.document_record is None or result.normalized_document is None:
        raise AssertionError(f"{fixture_id} did not produce a document")
    chunks = split_document_into_chunks(result.normalized_document, result.document_record, source=source)
    commit_storage_bundle(
        storage,
        raw_artifact=result.raw_artifact,
        source=source,
        document=result.document_record,
        chunks=chunks,
        job=result.job,
        logs=result.logs,
        errors=result.errors,
    )
    return source, result, chunks


class Milestone1SmokeTests(unittest.TestCase):
    def test_happy_path_retrieves_reranks_synthesizes_feedback_and_evaluation_trace(self) -> None:
        storage = InMemoryStorageRepository()
        registry = SourceRegistry()
        request_id = new_correlation_id("req_smoke")
        query = "How does the alpha evidence bridge use hybrid retrieval before answers?"
        source, ingestion, chunks = _store_ingested_fixture(storage, registry, "fixture_a_public_document")
        policy = registry.apply_source_policy(source.source_id, principal="reader")
        if policy.log is not None:
            storage.add_log(policy.log)

        verification = verify_storage_commit(
            storage,
            raw_artifacts=(ingestion.raw_artifact,),
            documents=(ingestion.document_record,),
            chunks=chunks,
        )
        vector_commit = commit_vectors(storage, storage.chunks.values())
        sparse_commit = commit_sparse_index(storage, storage.chunks.values())
        retrieval = run_hybrid_search(query, storage, request_id=request_id, principal="reader", top_k=3)
        ranking = select_ranked_evidence(
            query,
            retrieval.candidates,
            top_k=2,
            config=RankingConfig(current_date=date(2026, 5, 21)),
            repository=storage,
        )
        synthesis = generate_answer(
            query,
            ranking.candidates,
            ranked_evidence=ranking.ranked_evidence,
            repository=storage,
            current_date=date(2026, 5, 21),
        )
        feedback = capture_feedback(
            request_id=request_id,
            answer=synthesis.answer,
            evidence=synthesis.used_evidence,
            user_rating=UserRating.USEFUL,
            repository=storage,
        )
        evaluation = store_evaluation_trace(
            request_id=request_id,
            answer=synthesis.answer,
            evidence=synthesis.used_evidence,
            feedback=(feedback.feedback,),
            metrics={"retrieved_evidence": len(retrieval.candidates), "claims": len(synthesis.claims)},
            repository=storage,
        )

        self.assertEqual(ingestion.job.status, IngestionStatus.COMPLETED)
        self.assertTrue(verification.ok)
        self.assertTrue(vector_commit.record_ids)
        self.assertTrue(sparse_commit.record_ids)
        self.assertTrue(retrieval.candidates)
        self.assertTrue(ranking.ranked_evidence)
        self.assertTrue(all(candidate.access_decision is AccessDecision.ALLOWED for candidate in ranking.candidates))
        self.assertEqual(
            tuple(candidate.evidence_id for candidate in ranking.candidates),
            tuple(ranked.evidence_id for ranked in ranking.ranked_evidence),
        )
        self.assertEqual(
            tuple(candidate.evidence_id for candidate in synthesis.used_evidence),
            tuple(candidate.evidence_id for candidate in ranking.candidates),
        )
        self.assertIn("alpha evidence bridge", synthesis.answer.answer_text)
        self.assertTrue(synthesis.answer.citation_map)
        self.assertTrue(all(claim.evidence_id for claim in synthesis.claims))
        self.assertIn(feedback.feedback.feedback_id, storage.feedback)
        self.assertIn(feedback.feedback.feedback_id, storage.feedback_trace_references)
        self.assertEqual(
            feedback.trace_reference.claim_ids,
            tuple(claim.claim_id for claim in synthesis.claims),
        )
        self.assertEqual(
            feedback.trace_reference.citation_links,
            tuple(candidate.citation_link for candidate in synthesis.used_evidence if candidate.citation_link),
        )
        self.assertIn(evaluation.trace.trace_id, storage.evaluation_traces)
        self.assertEqual(evaluation.trace.evidence_ids, tuple(candidate.evidence_id for candidate in synthesis.used_evidence))
        self.assertEqual(evaluation.trace.feedback_ids, (feedback.feedback.feedback_id,))
        self.assertEqual(evaluation.trace.claim_ids, tuple(claim.claim_id for claim in synthesis.claims))
        self.assertEqual(
            evaluation.trace.citation_links,
            tuple(candidate.citation_link for candidate in synthesis.used_evidence if candidate.citation_link),
        )

    def test_restricted_source_is_excluded_before_ranking_and_synthesis(self) -> None:
        storage = InMemoryStorageRepository()
        registry = SourceRegistry()
        _store_ingested_fixture(storage, registry, "fixture_a_public_document")
        restricted_source, _restricted_ingestion, _restricted_chunks = _store_ingested_fixture(
            storage,
            registry,
            "fixture_b_restricted_source",
            allowed_principals=("alice",),
        )
        commit_vectors(storage, storage.chunks.values())
        commit_sparse_index(storage, storage.chunks.values())

        retrieval = run_hybrid_search(
            "restricted beta launch date alpha evidence bridge",
            storage,
            principal="bob",
            top_k=5,
        )
        ranking = select_ranked_evidence("restricted beta launch date", retrieval.candidates, top_k=5, repository=storage)
        synthesis = generate_answer("restricted beta launch date", ranking.candidates, repository=storage)

        self.assertGreaterEqual(retrieval.excluded_count, 1)
        self.assertNotIn(restricted_source.source_id, [candidate.source_id for candidate in retrieval.candidates])
        self.assertNotIn(restricted_source.source_id, [candidate.source_id for candidate in ranking.candidates])
        self.assertNotIn(restricted_source.source_id, [candidate.source_id for candidate in synthesis.used_evidence])
        self.assertTrue(all(candidate.access_decision is AccessDecision.ALLOWED for candidate in ranking.candidates))
        self.assertNotIn("restricted beta launch date", synthesis.answer.answer_text)
        self.assertNotIn("2026-07-15", synthesis.answer.answer_text)
        self.assertIn("access_filter_failed_closed", _event_names(storage.logs.values()))

    def test_malformed_source_records_partial_ingestion_error_and_failed_extractor_path(self) -> None:
        storage = InMemoryStorageRepository()
        registry = SourceRegistry()
        source, entry = _register_fixture(registry, "fixture_f_malformed_source")

        partial = run_ingestion_job(source, fixture_entry=entry)
        commit_storage_bundle(storage, job=partial.job, logs=partial.logs, errors=partial.errors)

        self.assertEqual(partial.job.status, IngestionStatus.PARTIAL)
        self.assertTrue(partial.errors)
        self.assertEqual(partial.errors[0].error_type, ErrorType.PARSING)
        self.assertIn("ingestion_partial", _event_names(partial.logs))

        def failing_extractor(*_args: object, **_kwargs: object):
            raise IngestionError(
                "malformed source could not be extracted",
                error_type=ErrorType.EXTRACTION,
                retryable=False,
            )

        failed = run_ingestion_job(source, fixture_entry=entry, extractor=failing_extractor)

        self.assertEqual(failed.job.status, IngestionStatus.FAILED)
        self.assertEqual(failed.errors[0].error_type, ErrorType.EXTRACTION)
        self.assertIn("ingestion_failed", _event_names(failed.logs))

    def test_logs_and_errors_cover_expected_milestone_partitions(self) -> None:
        storage = InMemoryStorageRepository()
        registry = SourceRegistry()
        public_source, _public_ingestion, _public_chunks = _store_ingested_fixture(
            storage,
            registry,
            "fixture_a_public_document",
        )
        restricted_source, _restricted_ingestion, _restricted_chunks = _store_ingested_fixture(
            storage,
            registry,
            "fixture_b_restricted_source",
            allowed_principals=("alice",),
        )
        denied_policy = registry.apply_source_policy(restricted_source.source_id, principal="bob")
        if denied_policy.log is not None:
            storage.add_log(denied_policy.log)
        if denied_policy.error is not None:
            storage.save_error(denied_policy.error)
        commit_vectors(storage, storage.chunks.values())
        commit_sparse_index(storage, storage.chunks.values())
        retrieval = run_hybrid_search("alpha evidence bridge restricted beta launch date", storage, principal="bob")
        ranking = select_ranked_evidence("alpha evidence bridge", retrieval.candidates, repository=storage)
        synthesis = generate_answer("alpha evidence bridge", ranking.candidates, repository=storage)
        feedback = capture_feedback(
            request_id=synthesis.answer.request_id,
            answer=synthesis.answer,
            evidence=synthesis.used_evidence,
            user_rating=UserRating.PARTIALLY_USEFUL,
            correction_text="The answer is useful but ranking could be clearer.",
            repository=storage,
        )
        evaluation = store_evaluation_trace(
            request_id=synthesis.answer.request_id,
            answer=synthesis.answer,
            evidence=synthesis.used_evidence,
            feedback=(feedback.feedback,),
            repository=storage,
        )
        malformed_source, malformed_entry = _register_fixture(registry, "fixture_f_malformed_source")
        malformed = run_ingestion_job(malformed_source, fixture_entry=malformed_entry)
        commit_storage_bundle(storage, job=malformed.job, logs=malformed.logs, errors=malformed.errors)

        log_partitions = {log.partition for log in storage.logs.values()}
        error_partitions = {error.partition for error in storage.errors.values()}

        self.assertEqual(feedback.feedback.failure_category, FailureCategory.RANKING)
        self.assertIn(evaluation.trace.trace_id, storage.evaluation_traces)
        self.assertIn(Partition.SOURCE_REGISTRY, log_partitions)
        self.assertIn(Partition.INGESTION, log_partitions)
        self.assertIn(Partition.STORAGE, log_partitions)
        self.assertIn(Partition.RETRIEVAL, log_partitions)
        self.assertIn(Partition.RANKING, log_partitions)
        self.assertIn(Partition.SYNTHESIS, log_partitions)
        self.assertIn(Partition.FEEDBACK, log_partitions)
        self.assertIn(Partition.EVALUATION, log_partitions)
        self.assertIn(Partition.SOURCE_REGISTRY, error_partitions)
        self.assertIn(Partition.RETRIEVAL, error_partitions)
        self.assertIn(Partition.INGESTION, error_partitions)


def _event_names(logs) -> list[str]:
    return [log.details.get("event_name") for log in logs]


if __name__ == "__main__":
    unittest.main()
