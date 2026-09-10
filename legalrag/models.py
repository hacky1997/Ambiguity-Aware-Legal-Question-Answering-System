"""Shared types.

Kept deliberately small and free of behaviour. Everything here is a value that
identification produces and the findings engine consumes, so both modules stay
pure functions over data rather than objects that do things to each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

__all__ = [
    "COMMENCEMENT",
    "Behaviour",
    "Candidate",
    "Code",
    "Confidence",
    "Finding",
    "IdentificationResult",
    "Method",
    "ProvisionRef",
    "Relationship",
    "more_cautious",
]

# The three new codes came into force on this date. Which law applies turns on
# when the offence was committed, not when the case was filed.
COMMENCEMENT = date(2024, 7, 1)


class Code(StrEnum):
    """The six acts in scope. `era` distinguishes old from new."""

    IPC = "IPC"
    CRPC = "CrPC"
    EVIDENCE = "Evidence Act"
    BNS = "BNS"
    BNSS = "BNSS"
    BSA = "BSA"

    @property
    def is_current(self) -> bool:
        return self in {Code.BNS, Code.BNSS, Code.BSA}

    @property
    def counterpart(self) -> Code:
        """The act in the other era covering the same subject matter."""
        return {
            Code.IPC: Code.BNS,
            Code.BNS: Code.IPC,
            Code.CRPC: Code.BNSS,
            Code.BNSS: Code.CRPC,
            Code.EVIDENCE: Code.BSA,
            Code.BSA: Code.EVIDENCE,
        }[self]


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Method(StrEnum):
    """How a candidate provision was found. Recorded so a wrong answer can be
    traced to the step that produced it."""

    EXPLICIT_CITATION = "explicit_citation"
    BARE_NUMBER = "bare_number"
    VOCABULARY = "vocabulary"
    HEADING = "heading"
    RETRIEVAL = "retrieval"
    BOUND_FACT = "bound_fact"


class Relationship(StrEnum):
    """How an old provision relates to its counterpart. From the correspondence
    file. `DISPUTED` includes rows queued for adjudication and not yet
    dispositioned, which is the cautious default."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    SPLIT = "split"
    MERGED = "merged"
    NO_SUCCESSOR = "no_successor"
    DISPUTED = "disputed"


class Behaviour(StrEnum):
    ANSWER = "answer"
    ANSWER_WITH_ASSUMPTION = "answer_with_assumption"
    ASK = "ask"
    ALTERNATIVES = "alternatives"


# Ordered least to most cautious. ASK and ALTERNATIVES are equally cautious;
# when both are required they combine rather than one winning.
_CAUTION: dict[Behaviour, int] = {
    Behaviour.ANSWER: 0,
    Behaviour.ANSWER_WITH_ASSUMPTION: 1,
    Behaviour.ASK: 2,
    Behaviour.ALTERNATIVES: 2,
}


def more_cautious(a: Behaviour, b: Behaviour) -> Behaviour:
    """Return whichever behaviour is more cautious.

    Ties go to ALTERNATIVES, because showing what is known beats withholding it
    while asking for more.
    """
    if _CAUTION[a] != _CAUTION[b]:
        return a if _CAUTION[a] > _CAUTION[b] else b
    if Behaviour.ALTERNATIVES in (a, b):
        return Behaviour.ALTERNATIVES
    return a


@dataclass(frozen=True, slots=True, order=True)
class ProvisionRef:
    """A section, optionally narrowed to a sub-section."""

    code: Code
    section: str
    subsection: str | None = None

    def __str__(self) -> str:
        base = f"{self.code.value} {self.section}"
        return f"{base}({self.subsection})" if self.subsection else base

    @property
    def section_ref(self) -> ProvisionRef:
        """The whole section. Materiality is assessed at section level, because a
        section that gained sub-clauses has changed even where none of the
        existing sub-clauses did."""
        return ProvisionRef(self.code, self.section)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One provision the question might concern."""

    ref: ProvisionRef
    method: Method
    confidence: Confidence
    evidence: str

    @property
    def is_confident(self) -> bool:
        return self.confidence is Confidence.HIGH


@dataclass(frozen=True, slots=True)
class Finding:
    """Something the rules established. Several apply at once."""

    id: str
    behaviour: Behaviour
    reason: str
    provisions: tuple[ProvisionRef, ...] = ()

    def __str__(self) -> str:
        return f"{self.id}: {self.reason}"


@dataclass(frozen=True, slots=True)
class IdentificationResult:
    """Output of Section 7. Zero candidates is a valid result."""

    candidates: tuple[Candidate, ...] = ()
    resolved_date: date | None = None
    date_ambiguous: bool = False
    date_evidence: str | None = None
    named_codes: frozenset[Code] = field(default_factory=frozenset)
    asks_punishment: bool = False
    asks_procedure: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.candidates

    @property
    def best_confidence(self) -> Confidence | None:
        if not self.candidates:
            return None
        order = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
        return max((c.confidence for c in self.candidates), key=lambda c: order[c])

    def sections(self) -> tuple[ProvisionRef, ...]:
        """Distinct sections among the candidates, order preserved."""
        seen: list[ProvisionRef] = []
        for candidate in self.candidates:
            ref = candidate.ref.section_ref
            if ref not in seen:
                seen.append(ref)
        return tuple(seen)
