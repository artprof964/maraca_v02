from datetime import date
import unittest

from shared import (
    AccessDecision,
    ConfidenceLevel,
    EvidenceCandidate,
    LogEventType,
    RankedEvidence,
    ReliabilityLevel,
    RetrievalMode,
    SupportStatus,
)
from storage import InMemoryStorageRepository
from synthesis import attach_citations, create_claim_records, generate_answer


def _evidence(
    *,
    evidence_id: str,
    text: str,
    access_decision: AccessDecision = AccessDecision.ALLOWED,
    citation_link: str | None = "https://example.test/source#chunk-0",
    normalized_score: float = 0.8,
    reliability: ReliabilityLevel = ReliabilityLevel.MEDIUM,
    published_at: date | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id="req_synthesis",
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=f"src_{evidence_id}",
        document_id=f"doc_{evidence_id}",
        chunk_id=f"chunk_{evidence_id}",
        text_snippet=text,
        score=normalized_score,
        normalized_score=normalized_score,
        source_reliability=reliability,
        published_at=published_at,
        citation_link=citation_link,
        access_decision=access_decision,
        evidence_id=evidence_id,
    )


class SynthesisTests(unittest.TestCase):
    def test_generate_answer_uses_only_approved_evidence(self) -> None:
        approved = _evidence(
            evidence_id="ev_public",
            text="Hybrid retrieval keeps cited evidence attached to the answer.",
        )
        restricted = _evidence(
            evidence_id="ev_secret",
            text="SECRET_INTERNAL_PLAN should never be present in the answer.",
            access_decision=AccessDecision.DENIED,
            citation_link="https://example.test/secret#chunk-0",
        )

        result = generate_answer("How does hybrid retrieval handle citations?", [restricted, approved])

        self.assertIn("Hybrid retrieval keeps cited evidence", result.answer.answer_text)
        self.assertNotIn("SECRET_INTERNAL_PLAN", result.answer.answer_text)
        self.assertEqual([evidence.evidence_id for evidence in result.used_evidence], ["ev_public"])
        self.assertEqual(result.claims[0].support_status, SupportStatus.SUPPORTED)

    def test_attach_citations_maps_claims_to_evidence_ids_and_links(self) -> None:
        evidence = _evidence(
            evidence_id="ev_cited",
            text="Answers cite the evidence used for each important claim.",
            citation_link="https://example.test/cited#chunk-1",
        )
        claims = create_claim_records("important claim citations", [evidence], answer_id="answer_1")

        citation_map = attach_citations(claims, [evidence])

        self.assertEqual(citation_map[claims[0].claim_id], ["ev_cited", "https://example.test/cited#chunk-1"])
        self.assertEqual(claims[0].evidence_id, "ev_cited")
        self.assertEqual(claims[0].answer_id, "answer_1")

    def test_create_claim_records_skips_unapproved_evidence(self) -> None:
        denied = _evidence(
            evidence_id="ev_denied_direct",
            text="Denied evidence must not become a supported claim.",
            access_decision=AccessDecision.DENIED,
        )

        claims = create_claim_records("denied evidence", [denied], answer_id="answer_1")

        self.assertEqual(claims, ())

    def test_create_claim_records_for_important_claims(self) -> None:
        evidence = _evidence(
            evidence_id="ev_ranked",
            text="The best evidence says graph retrieval preserves provenance. Less relevant sentence.",
        )

        result = generate_answer(
            "graph retrieval provenance",
            [evidence],
            ranked_evidence=[RankedEvidence(evidence_id="ev_ranked", rank=1, rerank_score=0.9)],
        )

        self.assertEqual(len(result.claims), 1)
        self.assertEqual(result.claims[0].claim_text, "The best evidence says graph retrieval preserves provenance.")
        self.assertEqual(result.answer.citation_map[result.claims[0].claim_id][0], "ev_ranked")

    def test_state_limitations_includes_stale_or_missing_evidence(self) -> None:
        stale = _evidence(
            evidence_id="ev_stale",
            text="Older evidence can still support a narrow claim.",
            published_at=date(2021, 1, 1),
        )
        missing_link = _evidence(
            evidence_id="ev_missing_link",
            text="Evidence without a direct link can still be tracked by evidence id.",
            citation_link=None,
        )

        result = generate_answer(
            "What does the evidence say?",
            [stale, missing_link],
            current_date=date(2026, 5, 21),
        )

        self.assertIn("Some supporting evidence may be stale.", result.answer.limitations)
        self.assertIn("Some supporting evidence lacked direct citation links.", result.answer.limitations)
        self.assertEqual(result.answer.confidence_level, ConfidenceLevel.MEDIUM)

    def test_synthesis_removes_unsupported_claims_when_evidence_is_empty(self) -> None:
        result = generate_answer("Invent a claim with no evidence", [])

        self.assertEqual(result.claims, ())
        self.assertEqual(result.answer.claim_records, [])
        self.assertEqual(result.answer.citation_map, {})
        self.assertIn("I do not have enough approved cited evidence", result.answer.answer_text)
        self.assertIn("No retrieved evidence was available for this query.", result.answer.limitations)
        self.assertEqual(result.answer.confidence_level, ConfidenceLevel.LOW)

    def test_synthesis_logs_answer_generated_and_citations_attached(self) -> None:
        repository = InMemoryStorageRepository()
        evidence = _evidence(
            evidence_id="ev_log",
            text="Synthesis emits logs when it creates cited claims.",
        )

        result = generate_answer("logs cited claims", [evidence], repository=repository)

        event_names = [log.details.get("event_name") for log in result.logs]
        self.assertIn("claim_records_created", event_names)
        self.assertIn("citations_attached", event_names)
        self.assertIn("answer_generated", event_names)
        self.assertIn("answer_generated", [log.details.get("event_name") for log in repository.logs.values()])
        self.assertEqual(result.logs[-1].event_type, LogEventType.SUCCESS)
        self.assertTrue(result.answer.citation_map)

    def test_synthesis_failure_creates_error_envelope_for_no_approved_evidence(self) -> None:
        repository = InMemoryStorageRepository()
        denied = _evidence(
            evidence_id="ev_denied",
            text="Denied evidence cannot support an answer.",
            access_decision=AccessDecision.DENIED,
        )

        result = generate_answer("denied evidence", [denied], repository=repository)

        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].details["event_name"], "insufficient_cited_evidence")
        self.assertEqual(result.logs[1].event_type, LogEventType.ERROR)
        self.assertIn(result.errors[0].error_id, repository.errors)


if __name__ == "__main__":
    unittest.main()
