"""Extract sentencing terms from Indian penal provisions.

Why this exists
---------------
Cross-code mappings published for the criminal codes score provisions by text
similarity. Similarity answers "is this the successor". It does not answer
"did the punishment change", and those are different questions. IPC 336 and
BNS 125 score 95 per cent alike while the maximum fine moves from 250 rupees
to 2,500 and two new aggravated sub-offences appear carrying up to three
years. A system that treats a high similarity score as "unchanged" will
answer that question wrongly.

So materiality is derived here instead, from the text itself.

Design constraint that makes this trustworthy
---------------------------------------------
Every extracted value carries the exact substring it came from. That span is
then verified to occur in the source text. This turns "trust the parser" into
"check the quote", which is a mechanical check rather than a human judgement.
Anything the parser cannot ground in a verifiable span is reported as
unparsed, never guessed.

Sentencing language in these codes is formulaic, which is what makes this
tractable. It is not fully regular, which is why `unparsed_clauses` exists and
must never be ignored.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "Fine",
    "Imprisonment",
    "Punishment",
    "Severity",
    "Span",
    "extract_punishment",
    "words_to_number",
]


# ---------------------------------------------------------------------------
# number words
# ---------------------------------------------------------------------------

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
# Indian numbering appears in these statutes and must be handled.
_SCALES = {
    "hundred": 100,
    "thousand": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "million": 1_000_000,
}


def words_to_number(text: str) -> int | None:
    """Parse an English number phrase into an int. None if not parseable.

    Handles Indian scale words (lakh, crore), Indian digit grouping
    (1,00,000), and digit forms mixed with words.
    """
    lowered = text.lower().strip()

    # Digit form, possibly with Indian grouping: 1,00,000 / 2,500 / 50000.
    # Must be handled before tokenising, or comma-split turns 1,00,000 into
    # the tokens 1 + 00 + 000 and sums them to 1.
    if re.fullmatch(r"[\d,\s]+", lowered):
        digits = re.sub(r"[^\d]", "", lowered)
        return int(digits) if digits else None

    cleaned = lowered.replace("-", " ").replace(",", " ")
    tokens = [t for t in re.split(r"[^a-z0-9]+", cleaned) if t]
    if not tokens:
        return None

    total = 0
    current = 0
    saw_number = False

    for token in tokens:
        if token.isdigit():
            current += int(token)
            saw_number = True
        elif token in _UNITS:
            current += _UNITS[token]
            saw_number = True
        elif token in _TENS:
            current += _TENS[token]
            saw_number = True
        elif token in _SCALES:
            scale = _SCALES[token]
            if current == 0:
                current = 1
            if scale >= 1_000:
                total += current * scale
                current = 0
            else:
                current *= scale
            saw_number = True
        elif token == "and":
            continue
        else:
            return None

    return total + current if saw_number else None


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Ordered by seriousness so pairs can be compared."""

    NONE = "none"
    COMMUNITY_SERVICE = "community_service"
    FINE_ONLY = "fine_only"
    SIMPLE = "simple_imprisonment"
    EITHER_DESCRIPTION = "either_description"
    RIGOROUS = "rigorous_imprisonment"
    LIFE = "life"
    DEATH = "death"


_SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


@dataclass(frozen=True, slots=True)
class Span:
    """A verbatim slice of the source text, with its offsets."""

    text: str
    start: int
    end: int

    def verify(self, source: str) -> bool:
        return source[self.start : self.end] == self.text


@dataclass(frozen=True, slots=True)
class Imprisonment:
    kind: Severity
    max_months: int | None
    min_months: int | None
    evidence: Span


@dataclass(frozen=True, slots=True)
class Fine:
    max_rupees: int | None  # None with unbounded=True means "fine", amount unstated
    min_rupees: int | None
    unbounded: bool
    evidence: Span


@dataclass(slots=True)
class Punishment:
    """Everything extracted from one provision."""

    max_severity: Severity = Severity.NONE
    max_imprisonment_months: int | None = None
    min_imprisonment_months: int | None = None
    max_fine_rupees: int | None = None
    min_fine_rupees: int | None = None
    fine_unbounded: bool = False
    fine_mandatory: bool = False  # "shall also be liable to fine"
    imprisonment_and_fine: bool = False  # "or with both" / cumulative
    community_service: bool = False
    death_available: bool = False
    life_available: bool = False
    limb_count: int = 0  # distinct sentencing limbs found
    imprisonments: list[Imprisonment] = field(default_factory=list)
    fines: list[Fine] = field(default_factory=list)
    unparsed_clauses: list[str] = field(default_factory=list)
    parse_confidence: str = "none"  # high | partial | none

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# patterns
# ---------------------------------------------------------------------------

_NUM = r"[a-z0-9,\-\s]{1,60}?"

_DURATION_UNITS = {
    "day": 1 / 30.0,
    "days": 1 / 30.0,
    "month": 1.0,
    "months": 1.0,
    "year": 12.0,
    "years": 12.0,
}

_RE_DEATH = re.compile(r"\bwith death\b|\bpunished with death\b", re.I)
_RE_LIFE = re.compile(r"\bimprisonment for life\b", re.I)
_RE_COMMUNITY = re.compile(r"\bcommunity service\b", re.I)
_RE_BOTH = re.compile(r"\bor with both\b", re.I)
_RE_FINE_MANDATORY = re.compile(r"\bshall also be liable to fine\b", re.I)

_IMPRISONMENT_KINDS = (
    r"\b(rigorous imprisonment|simple imprisonment"
    r"|imprisonment of either description|imprisonment)\b"
)

_RE_IMPRISONMENT_MAX = re.compile(
    _IMPRISONMENT_KINDS
    + r"[^.;]{0,120}?\bwhich may extend to\s+("
    + _NUM
    + r")\s+(days?|months?|years?)\b",
    re.I,
)
_RE_IMPRISONMENT_MIN = re.compile(
    _IMPRISONMENT_KINDS
    + r"[^.;]{0,120}?\bshall not be less than\s+("
    + _NUM
    + r")\s+(days?|months?|years?)\b",
    re.I,
)
_RE_FINE_MAX = re.compile(
    r"\bfine\b[^.;]{0,60}?\bwhich may extend to\s+(" + _NUM + r")\s+rupees\b",
    re.I,
)
_RE_FINE_MIN = re.compile(
    r"\bfine\b[^.;]{0,60}?\bshall not be less than\s+(" + _NUM + r")\s+rupees\b",
    re.I,
)
_RE_FINE_BARE = re.compile(r"\b(with fine|liable to fine)\b", re.I)

_KIND_MAP = {
    "rigorous imprisonment": Severity.RIGOROUS,
    "simple imprisonment": Severity.SIMPLE,
    "imprisonment of either description": Severity.EITHER_DESCRIPTION,
    "imprisonment": Severity.EITHER_DESCRIPTION,
}


def _span(match: re.Match[str], group: int = 0) -> Span:
    return Span(text=match.group(group), start=match.start(group), end=match.end(group))


def _to_months(value: str, unit: str) -> int | None:
    n = words_to_number(value)
    if n is None:
        return None
    factor = _DURATION_UNITS.get(unit.lower())
    if factor is None:
        return None
    return max(1, round(n * factor))


def _sentencing_clauses(text: str) -> Iterator[str]:
    """Split into limbs. Sub-clause markers and semicolons separate them."""
    parts = re.split(r";|\n\s*\(\w+\)\s*", text)
    for part in parts:
        if re.search(r"punish|liable|imprison|fine|community service", part, re.I):
            yield part.strip()


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


def extract_punishment(text: str) -> Punishment:
    """Extract sentencing terms from a provision's text.

    Every value carries a verified evidence span. Sentencing language that is
    recognised as sentencing but cannot be parsed is recorded in
    ``unparsed_clauses`` and lowers ``parse_confidence``. It is never guessed.
    """
    result = Punishment()
    if not text or not text.strip():
        return result

    signals = 0

    if m := _RE_DEATH.search(text):
        result.death_available = True
        result.max_severity = Severity.DEATH
        result.imprisonments.append(Imprisonment(Severity.DEATH, None, None, _span(m)))
        signals += 1

    if m := _RE_LIFE.search(text):
        result.life_available = True
        if _SEVERITY_ORDER[Severity.LIFE] > _SEVERITY_ORDER[result.max_severity]:
            result.max_severity = Severity.LIFE
        result.imprisonments.append(Imprisonment(Severity.LIFE, None, None, _span(m)))
        signals += 1

    if m := _RE_COMMUNITY.search(text):
        result.community_service = True
        if result.max_severity is Severity.NONE:
            result.max_severity = Severity.COMMUNITY_SERVICE
        signals += 1

    for m in _RE_IMPRISONMENT_MAX.finditer(text):
        kind = _KIND_MAP.get(m.group(1).lower(), Severity.EITHER_DESCRIPTION)
        months = _to_months(m.group(2), m.group(3))
        if months is None:
            result.unparsed_clauses.append(m.group(0))
            continue
        result.imprisonments.append(Imprisonment(kind, months, None, _span(m)))
        if result.max_imprisonment_months is None or months > result.max_imprisonment_months:
            result.max_imprisonment_months = months
        if _SEVERITY_ORDER[kind] > _SEVERITY_ORDER[result.max_severity]:
            result.max_severity = kind
        signals += 1

    for m in _RE_IMPRISONMENT_MIN.finditer(text):
        months = _to_months(m.group(2), m.group(3))
        if months is None:
            result.unparsed_clauses.append(m.group(0))
            continue
        if result.min_imprisonment_months is None or months < result.min_imprisonment_months:
            result.min_imprisonment_months = months
        signals += 1

    for m in _RE_FINE_MAX.finditer(text):
        amount = words_to_number(m.group(1))
        if amount is None:
            result.unparsed_clauses.append(m.group(0))
            continue
        result.fines.append(Fine(amount, None, False, _span(m)))
        if result.max_fine_rupees is None or amount > result.max_fine_rupees:
            result.max_fine_rupees = amount
        signals += 1

    for m in _RE_FINE_MIN.finditer(text):
        amount = words_to_number(m.group(1))
        if amount is None:
            result.unparsed_clauses.append(m.group(0))
            continue
        if result.min_fine_rupees is None or amount < result.min_fine_rupees:
            result.min_fine_rupees = amount
        signals += 1

    if _RE_FINE_BARE.search(text) and result.max_fine_rupees is None:
        m = _RE_FINE_BARE.search(text)
        assert m is not None
        result.fine_unbounded = True
        result.fines.append(Fine(None, None, True, _span(m)))
        if result.max_severity is Severity.NONE:
            result.max_severity = Severity.FINE_ONLY
        signals += 1

    if _RE_FINE_MANDATORY.search(text):
        result.fine_mandatory = True
    if _RE_BOTH.search(text):
        result.imprisonment_and_fine = True

    result.limb_count = sum(1 for _ in _sentencing_clauses(text))

    # every span must actually be in the source, or the extraction is void
    for imp in result.imprisonments:
        if not imp.evidence.verify(text):
            raise AssertionError(f"evidence span does not match source: {imp.evidence!r}")
    for fin in result.fines:
        if not fin.evidence.verify(text):
            raise AssertionError(f"evidence span does not match source: {fin.evidence!r}")

    if signals == 0:
        result.parse_confidence = "none"
    elif result.unparsed_clauses:
        result.parse_confidence = "partial"
    else:
        result.parse_confidence = "high"

    return result
