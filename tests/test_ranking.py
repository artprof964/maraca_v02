from datetime import date
import unittest

from ranking import RankingConfig, RankingWeights, select_ranked_evidence
from shared import EvidenceCandidate, LogEventType, Partition, ReliabilityLevel, RetrievalMode
from storage import InMemoryStorageRepository


def _candidate(
    *,
    evidence_id: str,
    source_id: str,
    chunk_id: str,
    text: str,
    normalized_score: float,
    reliability: ReliabilityLevel = ReliabilityLevel.MEDIUM,
    published_at: date | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id="req_rank",
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=source_id,
        document_id=f"doc_{source_id}",
        chunk_id=chunk_id,
        text_snippet=text,
        score=normalized_score,
        normalized_score=normalized_score,
        source_reliability=reliability,
        published_at=published_at,
        evidence_id=evidence_id,
    )


class RankingTests(unittest.TestCase):
    def test_select_ranked_evidence_prefers_query_relevant_candidate(self) -> None:
        relevant = _candidate(
            evidence_id="ev_relevant",
            source_id="src_a",
            chunk_id="chunk_a",
            text="Hybrid graph retrieval keeps cited evidence attached to answers.",
            normalized_score=0.35,
        )
        high_retrieval_noise = _candidate(
            evidence_id="ev_noise",
            source_id="src_b",
            chunk_id="chunk_b",
            text="Billing exports and invoice archive settings.",
            normalized_score=1.0,
            reliability=ReliabilityLevel.HIGH,
        )

        result = select_ranked_evidence(
            "graph retrieval cited evidence",
            [high_retrieval_noise, relevant],
            top_k=2,
        )

        self.assertEqual([candidate.evidence_id for candidate in result.candidates], ["ev_relevant", "ev_noise"])
        self.assertEqual(result.ranked_evidence[0].rank, 1)
        self.assertEqual(result.ranked_evidence[0].evidence_id, "ev_relevant")
        self.assertIn("evidence_selected", [log.details.get("event_name") for log in result.logs])

    def test_select_ranked_evidence_deduplicates_by_source_and_chunk(self) -> None:
        weaker = _candidate(
            evidence_id="ev_weaker",
            source_id="src_dup",
            chunk_id="chunk_dup",
            text="Graph retrieval evidence.",
            normalized_score=0.4,
        )
        stronger = _candidate(
            evidence_id="ev_stronger",
            source_id="src_dup",
            chunk_id="chunk_dup",
            text="Graph retrieval evidence.",
            normalized_score=0.9,
        )

        result = select_ranked_evidence("graph retrieval", [weaker, stronger])

        self.assertEqual([candidate.evidence_id for candidate in result.candidates], ["ev_stronger"])
        self.assertEqual(result.deduplicated_count, 1)

    def test_select_ranked_evidence_preserves_source_diversity(self) -> None:
        first_same_source = _candidate(
            evidence_id="ev_a1",
            source_id="src_a",
            chunk_id="chunk_a1",
            text="Graph retrieval evidence alpha.",
            normalized_score=1.0,
        )
        second_same_source = _candidate(
            evidence_id="ev_a2",
            source_id="src_a",
            chunk_id="chunk_a2",
            text="Graph retrieval evidence beta.",
            normalized_score=0.95,
        )
        other_source = _candidate(
            evidence_id="ev_b1",
            source_id="src_b",
            chunk_id="chunk_b1",
            text="Graph retrieval evidence gamma.",
            normalized_score=0.6,
        )
        config = RankingConfig(max_per_source=1)

        result = select_ranked_evidence(
            "graph retrieval evidence",
            [first_same_source, second_same_source, other_source],
            top_k=3,
            config=config,
        )

        self.assertEqual([candidate.evidence_id for candidate in result.candidates], ["ev_a1", "ev_b1", "ev_a2"])
        self.assertEqual(result.ranked_evidence[1].diversity_group, "src_b")

    def test_select_ranked_evidence_respects_reliability_and_freshness_weights(self) -> None:
        trusted_fresh = _candidate(
            evidence_id="ev_trusted",
            source_id="src_trusted",
            chunk_id="chunk_trusted",
            text="Graph retrieval evidence comparison.",
            normalized_score=0.3,
            reliability=ReliabilityLevel.HIGH,
            published_at=date(2026, 5, 1),
        )
        low_old = _candidate(
            evidence_id="ev_old",
            source_id="src_old",
            chunk_id="chunk_old",
            text="Graph retrieval evidence comparison.",
            normalized_score=1.0,
            reliability=ReliabilityLevel.LOW,
            published_at=date(2021, 1, 1),
        )
        config = RankingConfig(
            weights=RankingWeights(
                query_relevance=0.4,
                retrieval_score=0.2,
                source_reliability=0.3,
                freshness=0.1,
            ),
            current_date=date(2026, 5, 21),
        )

        result = select_ranked_evidence(
            "graph retrieval evidence",
            [low_old, trusted_fresh],
            top_k=2,
            config=config,
        )

        self.assertEqual(result.candidates[0].evidence_id, "ev_trusted")
        self.assertGreater(result.ranked_evidence[0].rerank_score, result.ranked_evidence[1].rerank_score)

    def test_select_ranked_evidence_falls_back_to_retrieval_scores_on_reranker_failure(self) -> None:
        repository = InMemoryStorageRepository()
        low = _candidate(
            evidence_id="ev_low",
            source_id="src_low",
            chunk_id="chunk_low",
            text="Relevant graph retrieval evidence.",
            normalized_score=0.2,
        )
        high = _candidate(
            evidence_id="ev_high",
            source_id="src_high",
            chunk_id="chunk_high",
            text="Less relevant text.",
            normalized_score=0.9,
        )

        def failing_reranker(_query: str, _candidates: object) -> dict[str, float]:
            raise RuntimeError("model unavailable")

        result = select_ranked_evidence(
            "graph retrieval evidence",
            [low, high],
            reranker=failing_reranker,
            repository=repository,
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual([candidate.evidence_id for candidate in result.candidates], ["ev_high", "ev_low"])
        self.assertEqual(result.errors[0].partition, Partition.RANKING)
        self.assertEqual(result.logs[0].event_type, LogEventType.ERROR)
        self.assertIn(result.errors[0].error_id, repository.errors)
        self.assertIn("evidence_selected", [log.details.get("event_name") for log in repository.logs.values()])

    def test_select_ranked_evidence_treats_non_finite_reranker_scores_as_zero(self) -> None:
        relevant = _candidate(
            evidence_id="ev_relevant",
            source_id="src_relevant",
            chunk_id="chunk_relevant",
            text="Graph retrieval evidence.",
            normalized_score=0.4,
        )
        invalid_score = _candidate(
            evidence_id="ev_invalid",
            source_id="src_invalid",
            chunk_id="chunk_invalid",
            text="Unrelated billing export.",
            normalized_score=1.0,
            reliability=ReliabilityLevel.HIGH,
        )

        result = select_ranked_evidence(
            "graph retrieval evidence",
            [invalid_score, relevant],
            reranker=lambda _query, _candidates: {"ev_invalid": float("nan"), "ev_relevant": 0.9},
        )

        self.assertEqual(result.candidates[0].evidence_id, "ev_relevant")


if __name__ == "__main__":
    unittest.main()
