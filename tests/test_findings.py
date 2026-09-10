"""Findings tests. Requirements criterion 12: every finding has a test case,
and combination reports every contributing finding."""

from __future__ import annotations

from legalrag.findings import combine, evaluate
from legalrag.identify import identify
from legalrag.models import Behaviour, Code, Finding, ProvisionRef
from tests.fakes import FakeCorrespondence, FakeIndex, FakeSplits, FakeVocabulary


def decide(q, *, splits_on=False, **kw):
    ident = identify(q, vocabulary=FakeVocabulary(), index=FakeIndex(), **kw)
    return evaluate(ident, correspondence=FakeCorrespondence(), splits=FakeSplits(on=splits_on))


# --- combination -----------------------------------------------------------


def test_most_cautious_wins():
    fs = (Finding("A", Behaviour.ANSWER, ""), Finding("B", Behaviour.ASK, ""))
    assert combine(fs) is Behaviour.ASK


def test_alternatives_beats_assumption():
    fs = (
        Finding("A", Behaviour.ANSWER_WITH_ASSUMPTION, ""),
        Finding("B", Behaviour.ALTERNATIVES, ""),
    )
    assert combine(fs) is Behaviour.ALTERNATIVES


def test_ask_and_alternatives_tie_goes_to_alternatives():
    """Showing what is known beats withholding it while asking for more."""
    fs = (Finding("A", Behaviour.ASK, ""), Finding("B", Behaviour.ALTERNATIVES, ""))
    assert combine(fs) is Behaviour.ALTERNATIVES


def test_empty_findings_default_to_ask_not_answer():
    assert combine(()) is Behaviour.ASK


# --- individual findings ---------------------------------------------------


def test_f1_nothing_identified():
    d = decide("what is the weather like")
    assert "F1" in d.finding_ids and d.behaviour is Behaviour.ASK


def test_f2_bare_number_shows_both():
    d = decide("What is section 302?")
    assert "F2" in d.finding_ids
    assert d.behaviour is Behaviour.ALTERNATIVES


def test_f3_distinct_offences_asks_which():
    d = decide("what is the punishment for assault")
    assert "F3" in d.finding_ids and d.behaviour is Behaviour.ASK


def test_f2_and_f3_are_distinguished_by_correspondence():
    """Both produce two candidates. Correspondents of each other means one
    offence in two eras; not correspondents means different offences."""
    assert "F2" in decide("What is section 302?").finding_ids
    assert "F3" in decide("punishment for assault").finding_ids


def test_f4_code_named_answers():
    d = decide("What does BNS 103 say?")
    assert "F4" in d.finding_ids and d.behaviour is Behaviour.ANSWER


def test_f5a_date_before_commencement():
    d = decide("punishment for theft committed in March 2023")
    assert "F5a" in d.finding_ids


def test_f5b_date_after_commencement():
    d = decide("punishment for theft on 2025-03-01")
    assert "F5b" in d.finding_ids


def test_f5b_still_reports_disputed_correspondence():
    """The ordering bug from an earlier version: a post-commencement date must
    not swallow a disputed correspondence."""
    d = decide("what does IPC 34 mean for an offence on 2025-03-01")
    assert "F5b" in d.finding_ids and "F6" in d.finding_ids
    assert d.behaviour is Behaviour.ALTERNATIVES


def test_f6_disputed():
    d = decide("explain IPC 34")
    assert "F6" in d.finding_ids and d.behaviour is Behaviour.ALTERNATIVES


def test_f7_split_shows_every_successor():
    d = decide("what does IPC 420 say")
    assert "F7" in d.finding_ids and d.behaviour is Behaviour.ALTERNATIVES
    f = next(f for f in d.findings if f.id == "F7")
    assert ProvisionRef(Code.BNS, "318") in f.provisions


def test_f8_no_successor_answers_plainly():
    d = decide("what does IPC 497 say")
    assert "F8" in d.finding_ids and d.behaviour is Behaviour.ANSWER


def test_f9_is_off_by_default():
    """Ships defined, unpopulated and switched off. Requirement criterion 8."""
    assert "F9" not in decide("punishment for theft").finding_ids


def test_f9_fires_when_enabled():
    d = decide("punishment for theft", splits_on=True)
    assert "F9" in d.finding_ids and d.behaviour is Behaviour.ALTERNATIVES


def test_f10_material_change_asks_for_date():
    """The worked case. Similarity says almost unchanged; sentencing says
    otherwise, so the system asks rather than assuming."""
    d = decide("penalty for a rash and negligent act")
    assert "F10" in d.finding_ids and d.behaviour is Behaviour.ASK


def test_f11_immaterial_answers_with_assumption():
    d = decide("punishment for theft")
    assert "F11" in d.finding_ids
    assert d.behaviour is Behaviour.ANSWER_WITH_ASSUMPTION


def test_f11_carries_both_numbers():
    d = decide("punishment for theft")
    f = next(f for f in d.findings if f.id == "F11")
    assert ProvisionRef(Code.IPC, "378") in f.provisions
    assert ProvisionRef(Code.BNS, "303") in f.provisions


def test_f12_no_offence_named():
    d = decide("what is the maximum sentence")
    assert "F12" in d.finding_ids and d.behaviour is Behaviour.ASK


def test_f13_low_confidence_never_plain_answers():
    d = decide("an act that endangers human life")
    assert "F13" in d.finding_ids
    assert d.behaviour is not Behaviour.ANSWER


def test_f14_no_reliable_answer():
    d = decide("who won the match yesterday")
    assert "F1" in d.finding_ids or "F14" in d.finding_ids
    assert d.behaviour is Behaviour.ASK


def test_f15_procedure_and_substance():
    d = decide("what is the sentence for theft and how is the FIR registered")
    assert "F15" in d.finding_ids and d.behaviour is Behaviour.ALTERNATIVES


def test_f16_two_provisions_named_is_a_comparison():
    d = decide("difference between IPC 302 and IPC 378")
    assert "F16" in d.finding_ids
    assert "F3" not in d.finding_ids


# --- properties that must always hold --------------------------------------


def test_findings_never_empty_for_any_input():
    for q in ["", "   ", "???", "hello", "section 302", "theft", "IPC 420"]:
        assert decide(q).findings, f"no finding for {q!r}"


def test_every_finding_has_a_plain_reason():
    for q in ["What is section 302?", "punishment for theft", "IPC 420", "IPC 34"]:
        for f in decide(q).findings:
            assert f.reason and len(f.reason.split()) >= 4


def test_no_finding_asserts_a_legal_conclusion():
    """Criterion 16. Section 3.1 forbids asserting legal conclusions."""
    banned = (
        "is equivalent to",
        "legally equivalent",
        "you should",
        "we advise",
        "is guilty",
        "will be convicted",
        "the court will",
    )
    for q in [
        "What is section 302?",
        "punishment for theft",
        "IPC 420",
        "IPC 497",
        "IPC 34",
        "difference between IPC 302 and IPC 378",
    ]:
        for f in decide(q).findings:
            low = f.reason.lower()
            assert not any(b in low for b in banned), f"{f.id}: {f.reason}"


def test_deterministic():
    """Same question, same findings, every time. No model is involved."""
    q = "penalty for a rash and negligent act"
    runs = [decide(q).finding_ids for _ in range(20)]
    assert len(set(runs)) == 1
