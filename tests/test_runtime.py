from __future__ import annotations

import asyncio
from datetime import date

from legalrag.audit import AuditRecord
from legalrag.conversation import (
    BoundFacts,
    ConversationState,
    bind_fact,
    cannot_answer,
    resume_question,
)
from legalrag.guardrails import allow_output, check_input
from legalrag.ingestion import (
    Document,
    build_passages,
    deduplicate_documents,
    document_quality,
    extract_provision_refs,
)
from legalrag.models import Behaviour, Finding
from legalrag.response import Citation, assemble, verify_citation
from legalrag.retrieval import RetrievalHit, fuse_ranked


def test_document_pipeline_preserves_numbered_paragraphs_and_citations():
    document = Document(
        "case-1",
        "SC",
        date(2024, 1, 1),
        "[1] Section 302 applies.\n[2] The court considered it.",
        "text",
        document_quality("readable legal judgment with enough words"),
    )
    passages = build_passages(document)
    assert passages[0].paragraph == "1"
    assert passages[0].provision_refs == ("302",)
    assert passages[0].passage_id.startswith("case-1:")
    assert extract_provision_refs("under s. 125 and section 302") == ("125", "302")


def test_deduplication_keeps_richer_extraction():
    weak = Document("a", "SC", date(2024, 1, 1), "short", "ocr", 0.4, "case")
    rich = Document("b", "SC", date(2024, 1, 1), "long readable judgment", "text", 0.9, "case")
    documents, duplicates = deduplicate_documents([weak, rich])
    assert documents == (rich,)
    assert duplicates == 1


def test_rank_fusion_does_not_add_flat_score_bonus():
    p1 = Document("a", "SC", None, "one", "text", 1).text
    first = build_passages(Document("a", "SC", None, p1, "text", 1))[0]
    second = build_passages(Document("b", "SC", None, "two", "text", 1))[0]
    hits = fuse_ranked(
        (RetrievalHit(first, 0.9, 1, "meaning"),),
        (RetrievalHit(second, 0.9, 1, "lexical"),),
        meaning_weight=0.8,
        lexical_weight=0.2,
    )
    assert hits[0].passage.document_id == "a"
    assert hits[0].score < 1


def test_citation_verification_is_a_mechanical_join():
    passage = build_passages(Document("a", "SC", None, "[1] verified text", "text", 1))[0]
    good = Citation(passage.passage_id, "verified text", paragraph="1")
    bad = Citation(passage.passage_id, "invented text", paragraph="1")
    assert verify_citation(good, {passage.passage_id: passage})
    assert not verify_citation(bad, {passage.passage_id: passage})


def test_response_requires_assumption_and_records_alternative_rule():
    finding = Finding("F7", Behaviour.ALTERNATIVES, "two successor provisions need comparison")
    decision = type(
        "Decision",
        (),
        {"behaviour": Behaviour.ALTERNATIVES, "findings": (finding,)},
    )()
    response = assemble(decision, "compare both")
    assert response.alternatives_rule


def test_conversation_binds_follow_up_and_falls_back_after_two_attempts():
    state = ConversationState("What applies?", BoundFacts(), "date")
    state = bind_fact(state, "date", date(2023, 1, 1))
    assert resume_question(state, "2023") in {"2023", state.original_question}
    pending = ConversationState("What applies?", BoundFacts(), "date")
    assert cannot_answer(cannot_answer(pending)).pending_fact is None


def test_guardrails_redact_and_fail_closed():
    accepted = asyncio.run(check_input("What does IPC section 302 say?"))
    assert not accepted.allowed
    assert accepted.name == "nemo_input"
    assert not allow_output("answer", citations_verified=False).allowed


def test_audit_record_is_serializable():
    record = AuditRecord("question", "ask", ("F1",), {}, {"input": True}, (), "v1", "chunks_v1", 4)
    assert '"behaviour": "ask"' in record.to_json()
