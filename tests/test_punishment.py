"""Extractor tests. Requirements criteria 4 and 18.

These exist because the full suite once passed while this module was
syntactically broken: nothing imported it. A module with no test is a module
that can rot silently.
"""

from __future__ import annotations

import pytest

from legalrag.materiality import Materiality, compare_texts
from legalrag.punishment import extract_punishment, words_to_number

IPC336 = (
    "Whoever does any act so rashly or negligently as to endanger human life, shall be "
    "punished with imprisonment of either description for a term which may extend to "
    "three months or with fine which may extend to two hundred and fifty rupees, or with both."
)
BNS125 = (
    "Whoever does any act so rashly or negligently as to endanger human life, shall be "
    "punished with imprisonment of either description for a term which may extend to three "
    "months or with fine which may extend to two thousand five hundred rupees, or with both, but-\n"
    "(a) where hurt is caused, shall be punished with imprisonment of either description for a "
    "term which may extend to six months, or with fine which may extend to five thousand rupees, "
    "or with both;\n(b) where grievous hurt is caused, shall be punished with imprisonment of "
    "either description for a term which may extend to three years, or with fine which may "
    "extend to ten thousand rupees, or with both."
)


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("three", 3),
        ("two hundred and fifty", 250),
        ("two thousand five hundred", 2500),
        ("ten thousand", 10000),
        ("ten lakh", 1_000_000),
        ("one crore", 10_000_000),
        ("2,500", 2500),
        ("1,00,000", 100_000),  # Indian grouping; this once parsed as 1
        ("50000", 50000),
    ],
)
def test_number_words(phrase, expected):
    assert words_to_number(phrase) == expected


def test_number_words_rejects_nonsense():
    assert words_to_number("banana") is None
    assert words_to_number("") is None


def test_extracts_the_worked_case():
    old, new = extract_punishment(IPC336), extract_punishment(BNS125)
    assert (old.max_imprisonment_months, old.max_fine_rupees, old.limb_count) == (3, 250, 1)
    assert (new.max_imprisonment_months, new.max_fine_rupees, new.limb_count) == (36, 10000, 3)


def test_every_value_carries_a_verified_span():
    """Criterion 4. This is what turns 'trust the parser' into 'check the quote'."""
    for text in (IPC336, BNS125):
        p = extract_punishment(text)
        for item in (*p.imprisonments, *p.fines):
            assert item.evidence.verify(text), item.evidence


def test_similarity_would_have_been_wrong():
    """These two texts are ~95% alike and are labelled almost unchanged by the
    published mapping. The extractor disagrees, and the extractor is right."""
    v = compare_texts(IPC336, BNS125)
    assert v.materiality is Materiality.MATERIAL
    assert v.finding == "F10"
    assert len(v.reasons) >= 3


def test_identical_text_is_immaterial():
    v = compare_texts(IPC336, IPC336)
    assert v.materiality is Materiality.IMMATERIAL and v.finding == "F11"


def test_missing_successor():
    assert compare_texts(IPC336, None).materiality is Materiality.NO_SUCCESSOR


def test_non_sentencing_provision_is_undetermined():
    """Definitions carry no punishment, so materiality does not apply and the
    rules depending on it must not fire."""
    v = compare_texts('"Court" means a Civil Court.', '"Court" means a Civil Court or Tribunal.')
    assert v.materiality is Materiality.UNDETERMINED and v.needs_review


def test_empty_text_does_not_crash():
    p = extract_punishment("")
    assert p.parse_confidence == "none"
