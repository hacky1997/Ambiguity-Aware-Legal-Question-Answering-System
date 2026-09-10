"""Response and citation contracts for the ambiguity-aware system."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from legalrag.findings import Decision
from legalrag.ingestion import Passage
from legalrag.models import Behaviour, Finding, ProvisionRef

ATTRIBUTION = "Statute text and computed mappings: IndiaCode by eCourtsIndia, CC BY 4.0."
ADVICE_NOTICE = "This is a text-based research aid, not legal advice."


@dataclass(frozen=True, slots=True)
class Citation:
    passage_id: str
    quoted_text: str
    act: str | None = None
    section: str | None = None
    subsection: str | None = None
    paragraph: str | None = None
    in_force_from: date | None = None
    in_force_to: date | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class Response:
    behaviour: Behaviour
    findings: tuple[Finding, ...]
    content: str
    citations: tuple[Citation, ...] = ()
    assumption: str | None = None
    alternatives_rule: str | None = None
    provenance: str = ATTRIBUTION
    advice_notice: str = ADVICE_NOTICE
    bound_facts: dict[str, str] = field(default_factory=dict)


def verify_citation(citation: Citation, passages: dict[str, Passage]) -> bool:
    passage = passages.get(citation.passage_id)
    return passage is not None and citation.quoted_text in passage.text


def verify_citations(response: Response, passages: dict[str, Passage]) -> tuple[Citation, ...]:
    """Return only mechanically verified citations; callers fail closed if any drop."""
    return tuple(citation for citation in response.citations if verify_citation(citation, passages))


def order_alternatives(provisions: Iterable[ProvisionRef]) -> tuple[ProvisionRef, ...]:
    """Stable ordering rule: current-code alternatives follow older-code ones."""
    return tuple(
        sorted(provisions, key=lambda ref: (ref.code.is_current, ref.code.value, ref.section))
    )


def assemble(
    decision: Decision,
    content: str,
    *,
    citations: tuple[Citation, ...] = (),
    assumption: str | None = None,
    bound_facts: dict[str, str] | None = None,
) -> Response:
    if decision.behaviour is Behaviour.ANSWER_WITH_ASSUMPTION and not assumption:
        raise ValueError("answer_with_assumption requires an assumption")
    rule = None
    if decision.behaviour is Behaviour.ALTERNATIVES:
        rule = "Alternatives are ordered by the governing act's commencement order."
    return Response(
        behaviour=decision.behaviour,
        findings=decision.findings,
        content=content,
        citations=citations,
        assumption=assumption,
        alternatives_rule=rule,
        bound_facts=dict(bound_facts or {}),
    )
