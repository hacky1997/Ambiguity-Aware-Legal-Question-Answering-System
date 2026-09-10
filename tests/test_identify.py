"""Identification tests. Requirements criteria 9 and 13."""

from __future__ import annotations

from datetime import date

import pytest

from legalrag.identify import identify, resolve_date
from legalrag.models import Code, Confidence, Method
from tests.fakes import FakeIndex, FakeVocabulary


def run(q, **kw):
    return identify(q, vocabulary=FakeVocabulary(), index=FakeIndex(), **kw)


# --- explicit citation -----------------------------------------------------


@pytest.mark.parametrize(
    "q,code,section",
    [
        ("What does Section 302 IPC say?", Code.IPC, "302"),
        ("punishment u/s 420 of the Indian Penal Code", Code.IPC, "420"),
        ("BNS 103 explanation", Code.BNS, "103"),
        ("bharatiya nyaya sanhita section 125", Code.BNS, "125"),
        ("s. 154 CrPC", Code.CRPC, "154"),
    ],
)
def test_explicit_citation(q, code, section):
    r = run(q)
    assert r.candidates[0].ref.code is code
    assert r.candidates[0].ref.section == section
    assert r.candidates[0].confidence is Confidence.HIGH


def test_subsection_captured():
    r = run("BNS section 125(2)")
    assert r.candidates[0].ref.subsection == "2"


# --- the bare number trap: criterion 13 ------------------------------------


def test_bare_number_returns_both_codes():
    """The highest-consequence case. A number with no code named means
    different things in each era and must never resolve to one."""
    r = run("What is section 302?")
    codes = {c.ref.code for c in r.candidates}
    assert codes == {Code.IPC, Code.BNS}
    assert all(c.method is Method.BARE_NUMBER for c in r.candidates)


def test_bare_number_never_defaults_to_current_code():
    r = run("what does section 302 cover")
    assert Code.IPC in {c.ref.code for c in r.candidates}


def test_bare_number_unknown_section_returns_nothing():
    r = run("What is section 999?")
    assert r.is_empty


# --- vocabulary ------------------------------------------------------------


def test_ambiguous_term_returns_every_offence():
    r = run("what is the punishment for assault")
    assert len(r.sections()) == 2
    assert r.best_confidence is Confidence.MEDIUM


def test_unambiguous_term_is_high_confidence():
    r = run("punishment for theft")
    assert r.best_confidence is Confidence.HIGH


def test_longest_term_wins_over_substring():
    r = run("penalty for a rash and negligent act")
    assert {c.ref.section for c in r.candidates} == {"336", "125"}


# --- date resolution -------------------------------------------------------


@pytest.mark.parametrize(
    "q,expected",
    [
        ("offence on 2023-05-14", date(2023, 5, 14)),
        ("committed 14/05/2023", date(2023, 5, 14)),
        ("in March 2023", date(2023, 3, 1)),
        ("on 14th May 2023", date(2023, 5, 14)),
        ("back in 2019", date(2019, 1, 1)),
    ],
)
def test_dates_resolve(q, expected):
    resolved, ambiguous, _ = resolve_date(q)
    assert resolved == expected and not ambiguous


def test_year_spanning_commencement_is_ambiguous():
    """2024 straddles the changeover, so the year alone cannot settle it."""
    resolved, ambiguous, evidence = resolve_date("the offence happened in 2024")
    assert resolved is None and ambiguous and evidence == "2024"


def test_no_date_is_not_ambiguous():
    resolved, ambiguous, _ = resolve_date("punishment for theft")
    assert resolved is None and not ambiguous


def test_invalid_date_reports_ambiguous_not_crash():
    resolved, ambiguous, _ = resolve_date("on 2023-02-30")
    assert resolved is None and ambiguous


# --- bound facts -----------------------------------------------------------


def test_bound_date_counts_as_given():
    r = run("punishment for theft", bound_date=date(2023, 1, 1))
    assert r.resolved_date == date(2023, 1, 1)


def test_bound_code_narrows_candidates():
    r = run("What is section 302?", bound_code=Code.IPC)
    assert {c.ref.code for c in r.candidates} == {Code.IPC}


def test_bound_code_never_invents_a_candidate():
    r = run("what is section 999?", bound_code=Code.BNS)
    assert r.is_empty


# --- intent flags and edges ------------------------------------------------


def test_punishment_and_procedure_detected():
    r = run("how is an FIR registered and what is the sentence for theft")
    assert r.asks_punishment and r.asks_procedure


def test_empty_and_whitespace():
    assert run("").is_empty
    assert run("    ").is_empty
