"""Provision identification. Requirements section 7.

Every finding depends on this. Getting it wrong applies the rules correctly to
the wrong provision, which is worse than having no rules at all.

Three things this must never do, and each has a test:

* Never pick the most common reading of an ambiguous term. Returning several
  candidates is correct behaviour, not failure.
* Never treat a bare number as belonging to the current code. The same number
  means unrelated things in the two eras, and guessing produces a fluent,
  well-formatted, completely wrong answer with nothing in it that looks unusual.
* Never silently drop a low confidence candidate. It is passed on with its
  confidence attached, and the rules turn that uncertainty into visible caution.

Data sources are injected as protocols so the rules can be tested without a
corpus, a database, or a network.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Protocol

from legalrag.models import (
    Candidate,
    Code,
    Confidence,
    IdentificationResult,
    Method,
    ProvisionRef,
)

__all__ = ["SectionIndex", "Vocabulary", "identify", "resolve_date"]


# --------------------------------------------------------------------------
# injected data
# --------------------------------------------------------------------------


class Vocabulary(Protocol):
    """Maps the words people use to provisions. Section 5."""

    def lookup(self, term: str) -> tuple[ProvisionRef, ...]:
        """Every provision the term maps to, in every code. A term that could
        mean several offences returns all of them."""

    def terms(self) -> tuple[str, ...]:
        """All known terms, longest first, so multi-word terms match before
        their constituent words."""


class SectionIndex(Protocol):
    """Knows which sections exist and what their headings say."""

    def exists(self, ref: ProvisionRef) -> bool: ...

    def heading_matches(self, text: str, limit: int) -> tuple[ProvisionRef, ...]:
        """Provisions whose heading matches the text, best first."""


# --------------------------------------------------------------------------
# patterns
# --------------------------------------------------------------------------

# Written forms people actually use, including abbreviations and the older
# spellings that appear in filings.
_CODE_WORDS: dict[str, Code] = {
    "ipc": Code.IPC,
    "i.p.c": Code.IPC,
    "indian penal code": Code.IPC,
    "penal code": Code.IPC,
    "bns": Code.BNS,
    "bharatiya nyaya sanhita": Code.BNS,
    "nyaya sanhita": Code.BNS,
    "crpc": Code.CRPC,
    "cr.p.c": Code.CRPC,
    "code of criminal procedure": Code.CRPC,
    "criminal procedure code": Code.CRPC,
    "bnss": Code.BNSS,
    "bharatiya nagarik suraksha sanhita": Code.BNSS,
    "nagarik suraksha sanhita": Code.BNSS,
    "evidence act": Code.EVIDENCE,
    "indian evidence act": Code.EVIDENCE,
    "bsa": Code.BSA,
    "bharatiya sakshya adhiniyam": Code.BSA,
    "sakshya adhiniyam": Code.BSA,
}

_CODE_ALTERNATION = "|".join(
    sorted((re.escape(word) for word in _CODE_WORDS), key=len, reverse=True)
)

_SECTION_WORD = r"(?:section|sec\.?|s\.|u/s|under section)"
# The boundary sits after the section number, not after the optional
# sub-section. Placing it at the end makes the engine backtrack past a
# matched "(2)" to satisfy it, silently dropping the sub-section.
_NUMBER = r"(\d{1,3}[A-Z]{0,2})\b(?:\s*\(\s*([0-9a-z]{1,3})\s*\))?"

# "Section 302 IPC", "u/s 420 of the Indian Penal Code", "s.125(2) BNS"
_RE_SECTION_THEN_CODE = re.compile(
    rf"{_SECTION_WORD}\s*{_NUMBER}\s*(?:of\s+(?:the\s+)?)?(?:{_CODE_ALTERNATION})\b",
    re.IGNORECASE,
)
# "IPC 302", "BNS section 103"
_RE_CODE_THEN_SECTION = re.compile(
    rf"({_CODE_ALTERNATION})\s*(?:{_SECTION_WORD}\s*)?{_NUMBER}",
    re.IGNORECASE,
)
# "section 302" with no code anywhere near it
_RE_BARE_SECTION = re.compile(rf"{_SECTION_WORD}\s*{_NUMBER}", re.IGNORECASE)

_RE_CODE_MENTION = re.compile(rf"\b({_CODE_ALTERNATION})\b", re.IGNORECASE)

_RE_PUNISHMENT = re.compile(
    r"\b(punish\w*|sentence|imprison\w*|fine|penalty|jail|term)\b", re.IGNORECASE
)
_RE_PROCEDURE = re.compile(
    r"\b(fir|first information report|investigat\w*|arrest\w*|bail|charge\s?sheet|"
    r"summons|warrant|trial|cogniz\w*|remand|custody|prosecut\w*)\b",
    re.IGNORECASE,
)

_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
_RE_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_RE_MONTH_YEAR = re.compile(rf"\b({'|'.join(_MONTHS)})\.?\s+(\d{{4}})\b", re.IGNORECASE)
_RE_DAY_MONTH_YEAR = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({'|'.join(_MONTHS)})\.?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_RE_BARE_YEAR = re.compile(r"\b(19|20)(\d{2})\b")


def _code_of(text: str) -> Code | None:
    return _CODE_WORDS.get(text.lower().strip().rstrip("."))


def _ref(code: Code, section: str, subsection: str | None) -> ProvisionRef:
    return ProvisionRef(code, section.upper(), subsection.lower() if subsection else None)


# --------------------------------------------------------------------------
# date resolution
# --------------------------------------------------------------------------


def resolve_date(question: str) -> tuple[date | None, bool, str | None]:
    """Resolve any date in the question.

    Returns (resolved, ambiguous, evidence).

    A bare year that straddles the commencement is *not* resolved. It is
    reported ambiguous, so the rules ask which side of the changeover the
    offence falls on rather than silently picking one. This is the case that
    would otherwise produce a confident answer under the wrong code.
    """
    if m := _RE_ISO_DATE.search(question):
        year, month, day = (int(g) for g in m.groups())
        try:
            return date(year, month, day), False, m.group(0)
        except ValueError:
            return None, True, m.group(0)

    if m := _RE_DAY_MONTH_YEAR.search(question):
        day = int(m.group(1))
        month = _MONTHS.index(m.group(2).lower()) + 1
        try:
            return date(int(m.group(3)), month, day), False, m.group(0)
        except ValueError:
            return None, True, m.group(0)

    if m := _RE_DMY.search(question):
        day, month, year = (int(g) for g in m.groups())
        try:
            return date(year, month, day), False, m.group(0)
        except ValueError:
            return None, True, m.group(0)

    if m := _RE_MONTH_YEAR.search(question):
        month = _MONTHS.index(m.group(1).lower()) + 1
        year = int(m.group(2))
        # First of the month is unambiguous unless the month itself spans the
        # changeover, which no single month does.
        return date(year, month, 1), False, m.group(0)

    if m := _RE_BARE_YEAR.search(question):
        year = int(m.group(0))
        if year == 2024:
            # Straddles commencement. Genuinely unresolvable from the year alone.
            return None, True, m.group(0)
        return date(year, 1, 1), False, m.group(0)

    return None, False, None


# --------------------------------------------------------------------------
# identification
# --------------------------------------------------------------------------


def _explicit_citations(question: str) -> list[Candidate]:
    """Step 1. A provision named together with its code. Highest confidence."""
    found: list[Candidate] = []
    for pattern, code_group, section_group, sub_group in (
        (_RE_SECTION_THEN_CODE, 0, 1, 2),
        (_RE_CODE_THEN_SECTION, 1, 2, 3),
    ):
        for m in pattern.finditer(question):
            if code_group:
                code = _code_of(m.group(code_group))
            else:
                mention = _RE_CODE_MENTION.search(m.group(0))
                code = _code_of(mention.group(1)) if mention else None
            if code is None:
                continue
            found.append(
                Candidate(
                    ref=_ref(code, m.group(section_group), m.group(sub_group)),
                    method=Method.EXPLICIT_CITATION,
                    confidence=Confidence.HIGH,
                    evidence=m.group(0).strip(),
                )
            )
    return found


def _bare_numbers(question: str, index: SectionIndex) -> list[Candidate]:
    """Step 2. A number with no code named.

    Returns the provision in *both* eras. This is not one candidate with an
    unknown code; it is two candidates that mean different things, and the
    rules decide what to do about that.
    """
    found: list[Candidate] = []
    for m in _RE_BARE_SECTION.finditer(question):
        section, subsection = m.group(1), m.group(2)
        for code in (Code.IPC, Code.BNS):
            ref = _ref(code, section, subsection)
            if index.exists(ref):
                found.append(
                    Candidate(
                        ref=ref,
                        method=Method.BARE_NUMBER,
                        confidence=Confidence.MEDIUM,
                        evidence=m.group(0).strip(),
                    )
                )
    return found


def _vocabulary(question: str, vocabulary: Vocabulary) -> list[Candidate]:
    """Step 3. Terms people use, mapped to provisions.

    Longest term first, so a multi-word offence name is not shadowed by one of
    its own words.
    """
    found: list[Candidate] = []
    lowered = question.lower()
    matched_spans: list[tuple[int, int]] = []

    for term in vocabulary.terms():
        start = lowered.find(term.lower())
        if start < 0:
            continue
        end = start + len(term)
        if any(s <= start and end <= e for s, e in matched_spans):
            continue
        matched_spans.append((start, end))
        refs = vocabulary.lookup(term)
        # A term mapping to several offences is ambiguous by construction, so
        # every candidate it produces carries lower confidence.
        confidence = Confidence.HIGH if len(refs) == 1 else Confidence.MEDIUM
        for ref in refs:
            found.append(
                Candidate(
                    ref=ref,
                    method=Method.VOCABULARY,
                    confidence=confidence,
                    evidence=term,
                )
            )
    return found


def _headings(question: str, index: SectionIndex, limit: int) -> list[Candidate]:
    """Step 4. The statute's own description of what each provision covers."""
    return [
        Candidate(
            ref=ref,
            method=Method.HEADING,
            confidence=Confidence.LOW,
            evidence="matched provision heading",
        )
        for ref in index.heading_matches(question, limit)
    ]


def _dedupe(candidates: list[Candidate]) -> tuple[Candidate, ...]:
    """One candidate per provision, keeping the most confident, then the
    earliest method. Order of first appearance is preserved."""
    order = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
    best: dict[ProvisionRef, Candidate] = {}
    for candidate in candidates:
        existing = best.get(candidate.ref)
        if existing is None or order[candidate.confidence] > order[existing.confidence]:
            best[candidate.ref] = candidate
    return tuple(best.values())


def identify(
    question: str,
    *,
    vocabulary: Vocabulary,
    index: SectionIndex,
    bound_code: Code | None = None,
    bound_date: date | None = None,
    heading_limit: int = 3,
) -> IdentificationResult:
    """Resolve a question to candidate provisions.

    Steps run in order and stop as soon as a step produces candidates, because
    a lower-confidence step cannot improve on a higher-confidence one and would
    only add noise. The exception is that headings are only consulted when
    nothing earlier matched at all.

    ``bound_code`` and ``bound_date`` carry facts established earlier in the
    conversation, so a date given on turn two counts as a date given on turn
    three and the system does not ask twice.
    """
    if not question or not question.strip():
        return IdentificationResult()

    resolved, ambiguous, evidence = resolve_date(question)
    if bound_date is not None and resolved is None and not ambiguous:
        resolved, evidence = bound_date, "established earlier in the conversation"

    named = {
        code
        for m in _RE_CODE_MENTION.finditer(question)
        if (code := _code_of(m.group(1))) is not None
    }
    if bound_code is not None:
        named.add(bound_code)

    candidates = _explicit_citations(question)
    if not candidates:
        candidates = _bare_numbers(question, index)
    if not candidates:
        candidates = _vocabulary(question, vocabulary)
    if not candidates:
        candidates = _headings(question, index, heading_limit)

    # A code established earlier narrows candidates that are otherwise split
    # across eras, but never invents one where none was found.
    if bound_code is not None and candidates:
        narrowed = [c for c in candidates if c.ref.code == bound_code]
        if narrowed:
            candidates = narrowed

    return IdentificationResult(
        candidates=_dedupe(candidates),
        resolved_date=resolved,
        date_ambiguous=ambiguous,
        date_evidence=evidence,
        named_codes=frozenset(named),
        asks_punishment=bool(_RE_PUNISHMENT.search(question)),
        asks_procedure=bool(_RE_PROCEDURE.search(question)),
    )
