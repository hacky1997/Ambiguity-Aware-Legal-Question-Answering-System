"""The findings engine. Requirements section 11.

Rules do not race to fire first. Every rule that applies records a finding, all
findings are collected, and behaviour is the most cautious that any of them
requires. Every contributing finding is reported, not only the deciding one.

First-match-wins was tried and discarded. A question can concern a provision
that both changed materially and is subject to a known court disagreement, and
first-match reported one and hid the other with no signal that anything was
hidden. See docs/DECISIONS.md D6.

No model is called anywhere in this module. That is the point of it. Everything
here is a pure function over identification output and derived data, so the same
question yields the same findings with the same recorded reasons every time.
"""

from __future__ import annotations

from functools import reduce
from typing import Protocol

from legalrag.models import (
    COMMENCEMENT,
    Behaviour,
    Candidate,
    Confidence,
    Finding,
    IdentificationResult,
    Method,
    ProvisionRef,
    Relationship,
    more_cautious,
)

__all__ = ["Correspondence", "Decision", "KnownSplits", "combine", "evaluate"]


class Correspondence(Protocol):
    """The derived correspondence file. Section 5."""

    def relationship(self, ref: ProvisionRef) -> Relationship | None:
        """How this provision relates to its counterpart era. None if unknown."""

    def successors(self, ref: ProvisionRef) -> tuple[ProvisionRef, ...]:
        """Corresponding provisions in the other era. Empty for no successor."""

    def is_material(self, ref: ProvisionRef) -> bool | None:
        """Whether the change is material. None where the provision carries no
        sentencing language, in which case the distinction does not apply and
        the rules that depend on it do not fire."""

    def are_correspondents(self, a: ProvisionRef, b: ProvisionRef) -> bool:
        """Whether two provisions are the same offence in two eras. This is what
        separates the bare-number trap from an ambiguous term."""


class KnownSplits(Protocol):
    """Points where courts are known to differ. Unpopulated and switched off."""

    def enabled(self) -> bool: ...

    def matches(self, ref: ProvisionRef) -> tuple[str, ...]: ...


class Decision:
    """Result of evaluating the rules."""

    __slots__ = ("behaviour", "findings")

    def __init__(self, behaviour: Behaviour, findings: tuple[Finding, ...]) -> None:
        self.behaviour = behaviour
        self.findings = findings

    @property
    def finding_ids(self) -> tuple[str, ...]:
        return tuple(f.id for f in self.findings)

    def __repr__(self) -> str:
        return f"Decision({self.behaviour.value}, {list(self.finding_ids)})"


# --------------------------------------------------------------------------
# combination
# --------------------------------------------------------------------------


def combine(findings: tuple[Finding, ...]) -> Behaviour:
    """The most cautious behaviour any finding requires.

    Empty findings cannot happen in normal operation, because F1 or F14 always
    applies, but defaulting to ASK rather than ANSWER keeps the failure safe.
    """
    if not findings:
        return Behaviour.ASK
    return reduce(more_cautious, (f.behaviour for f in findings))


# --------------------------------------------------------------------------
# individual rules
# --------------------------------------------------------------------------


def _f1_no_candidate(ident: IdentificationResult) -> Finding | None:
    if ident.is_empty:
        return Finding(
            "F1",
            Behaviour.ASK,
            "no provision could be identified from the question",
        )
    return None


def _f2_f3_two_candidates(ident: IdentificationResult, corr: Correspondence) -> Finding | None:
    """Two candidates need different treatment depending on how they arose.

    The discriminator is the method, checked against the correspondence file.

    A bare number produces the same section number in both eras. If those two
    are *not* correspondents of each other, they are unrelated offences sharing
    a number, which is the trap: answering under one produces a fluent, well
    formatted, completely wrong answer with nothing in it that looks unusual.
    Show both readings.

    A vocabulary term producing several offences is a different problem. The
    offences are unrelated to each other and no display of both helps, because
    the user meant one of them. Ask which.

    A bare number whose two candidates *are* correspondents is not ambiguous at
    all. It is one offence in two eras, so this returns nothing and the
    materiality rules govern.
    """
    sections = ident.sections()
    if len(sections) < 2:
        return None

    from_bare_number = any(c.method is Method.BARE_NUMBER for c in ident.candidates)
    all_correspondents = all(
        corr.are_correspondents(a, b) for i, a in enumerate(sections) for b in sections[i + 1 :]
    )

    if from_bare_number:
        if all_correspondents:
            return None
        return Finding(
            "F2",
            Behaviour.ALTERNATIVES,
            "this number exists in both codes and refers to different offences in "
            "each, so both readings are shown",
            sections,
        )

    if not all_correspondents:
        return Finding(
            "F3",
            Behaviour.ASK,
            "the question could refer to more than one distinct offence",
            sections,
        )
    return None


def _f4_code_named(ident: IdentificationResult) -> Finding | None:
    if not ident.named_codes or ident.is_empty:
        return None
    if len(ident.sections()) != 1:
        return None
    return Finding(
        "F4",
        Behaviour.ANSWER,
        "the question names the act, so which law applies is not in doubt",
        ident.sections(),
    )


def _f5_date_given(ident: IdentificationResult, corr: Correspondence) -> tuple[Finding, ...]:
    """A resolved date settles which era governs.

    F5b checks the correspondence before answering. An earlier version let the
    date rule fire ahead of that check, which swallowed the ambiguity whenever a
    post-commencement date landed on a disputed provision. See DECISIONS.md D6.
    """
    if ident.resolved_date is None or ident.is_empty:
        return ()

    if ident.resolved_date < COMMENCEMENT:
        return (
            Finding(
                "F5a",
                Behaviour.ANSWER,
                f"the offence date given is before {COMMENCEMENT:%d %B %Y}, "
                "so the earlier code governs",
                ident.sections(),
            ),
        )

    out: list[Finding] = [
        Finding(
            "F5b",
            Behaviour.ANSWER,
            f"the offence date given is on or after {COMMENCEMENT:%d %B %Y}, "
            "so the current code governs",
            ident.sections(),
        )
    ]
    for ref in ident.sections():
        if corr.relationship(ref) is Relationship.DISPUTED:
            out.append(_disputed_finding(ref))
    return tuple(out)


def _disputed_finding(ref: ProvisionRef) -> Finding:
    return Finding(
        "F6",
        Behaviour.ALTERNATIVES,
        f"published sources do not agree on what {ref} corresponds to in the "
        "other code, so the correspondence is not settled",
        (ref,),
    )


def _f6_f7_f8_correspondence(
    ident: IdentificationResult, corr: Correspondence, seen: set[str]
) -> tuple[Finding, ...]:
    out: list[Finding] = []
    for ref in ident.sections():
        relationship = corr.relationship(ref)
        if relationship is Relationship.DISPUTED and "F6" not in seen:
            out.append(_disputed_finding(ref))
        elif relationship is Relationship.SPLIT:
            successors = corr.successors(ref)
            out.append(
                Finding(
                    "F7",
                    Behaviour.ALTERNATIVES,
                    f"{ref} corresponds to more than one provision in the other "
                    "code, each applying in different circumstances",
                    (ref, *successors),
                )
            )
        elif relationship is Relationship.NO_SUCCESSOR:
            out.append(
                Finding(
                    "F8",
                    Behaviour.ANSWER,
                    f"{ref} has no corresponding provision in the other code",
                    (ref,),
                )
            )
    return tuple(out)


def _f9_court_split(ident: IdentificationResult, splits: KnownSplits) -> tuple[Finding, ...]:
    """Unpopulated and switched off. Defined so the shape exists and so turning
    it on later is a data change rather than a code change."""
    if not splits.enabled():
        return ()
    out: list[Finding] = []
    for ref in ident.sections():
        for point in splits.matches(ref):
            out.append(
                Finding(
                    "F9",
                    Behaviour.ALTERNATIVES,
                    f"courts have reached different conclusions on {point} and "
                    "the matter is not settled",
                    (ref,),
                )
            )
    return tuple(out)


def _collapse_correspondents(
    sections: tuple[ProvisionRef, ...], corr: Correspondence
) -> tuple[ProvisionRef, ...]:
    """Collapse a provision and its counterpart into one.

    A vocabulary term commonly matches the same offence in both eras. Reporting
    a finding once per era says the same thing twice and makes the response read
    as though two separate issues were found. The earlier-era provision is kept,
    because the correspondence file is keyed from it.
    """
    kept: list[ProvisionRef] = []
    for ref in sections:
        replaced = False
        for i, existing in enumerate(kept):
            if corr.are_correspondents(ref, existing):
                if not existing.code.is_current:
                    replaced = True
                    break
                kept[i] = ref if not ref.code.is_current else existing
                replaced = True
                break
        if not replaced:
            kept.append(ref)
    return tuple(kept)


def _f10_f11_materiality(ident: IdentificationResult, corr: Correspondence) -> tuple[Finding, ...]:
    """Whether to ask for a date, or answer on a stated assumption.

    Materiality is None for provisions carrying no sentencing language, such as
    definitions and general exceptions. Neither rule fires there, and something
    else governs.
    """
    if ident.resolved_date is not None or ident.is_empty:
        return ()

    out: list[Finding] = []
    for ref in _collapse_correspondents(ident.sections(), corr):
        relationship = corr.relationship(ref)
        if relationship in (Relationship.NO_SUCCESSOR, Relationship.DISPUTED, Relationship.SPLIT):
            continue
        material = corr.is_material(ref)
        if material is None:
            continue
        if material:
            out.append(
                Finding(
                    "F10",
                    Behaviour.ASK,
                    "the punishment differs between the two codes, so the answer "
                    "depends on when the offence took place",
                    (ref,),
                )
            )
        else:
            counterpart = corr.successors(ref)
            out.append(
                Finding(
                    "F11",
                    Behaviour.ANSWER_WITH_ASSUMPTION,
                    "the provision carried across with the same substance and the "
                    "same punishment, so only the number changed",
                    (ref, *counterpart),
                )
            )
    return tuple(out)


def _f12_offence_not_identified(ident: IdentificationResult) -> Finding | None:
    """Asking about punishment or procedure without saying for what."""
    if not ident.is_empty:
        return None
    if ident.asks_punishment or ident.asks_procedure:
        return Finding(
            "F12",
            Behaviour.ASK,
            "the question asks about consequences without saying which offence",
        )
    return None


def _f13_low_confidence(ident: IdentificationResult) -> Finding | None:
    if ident.is_empty or ident.best_confidence is not Confidence.LOW:
        return None
    behaviour = Behaviour.ALTERNATIVES if len(ident.sections()) > 1 else Behaviour.ASK
    return Finding(
        "F13",
        behaviour,
        "the provision could not be identified with confidence, so the system "
        "will not answer as though it had been",
        ident.sections(),
    )


def _f14_retrieval_led(ident: IdentificationResult, others: tuple[Finding, ...]) -> Finding | None:
    """Nothing provision-based applied. Retrieval decides, and where retrieval is
    weak the honest response is to say so rather than assemble something."""
    if others or not ident.is_empty:
        return None
    return Finding(
        "F14",
        Behaviour.ASK,
        "the library does not contain a reliable answer to this question",
    )


def _f15_procedure_and_substance(ident: IdentificationResult) -> Finding | None:
    """Which act governs an offence and which governs how a case is investigated
    and tried are separate questions that can point at different codes for the
    same matter. The system does not determine how they interact, because that
    is a legal conclusion and section 3.1 forbids asserting one."""
    if not (ident.asks_punishment and ident.asks_procedure):
        return None
    return Finding(
        "F15",
        Behaviour.ALTERNATIVES,
        "the question touches both the offence itself and how a case is handled, "
        "which are governed separately and may point to different codes; how they "
        "interact is a matter of legal judgement this system does not make",
        ident.sections(),
    )


def _f16_several_provisions(ident: IdentificationResult, corr: Correspondence) -> Finding | None:
    """Two provisions named explicitly is a comparison, not ambiguity."""
    explicit = [c for c in ident.candidates if c.method is Method.EXPLICIT_CITATION]
    sections = _distinct_sections(explicit)
    if len(sections) < 2:
        return None
    if all(
        corr.are_correspondents(a, b) for i, a in enumerate(sections) for b in sections[i + 1 :]
    ):
        return None
    return Finding(
        "F16",
        Behaviour.ANSWER,
        "the question names more than one provision, so each is covered separately",
        sections,
    )


def _distinct_sections(candidates: list[Candidate]) -> tuple[ProvisionRef, ...]:
    seen: list[ProvisionRef] = []
    for candidate in candidates:
        ref = candidate.ref.section_ref
        if ref not in seen:
            seen.append(ref)
    return tuple(seen)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def evaluate(
    ident: IdentificationResult,
    *,
    correspondence: Correspondence,
    splits: KnownSplits,
) -> Decision:
    """Run every rule, collect every finding, decide the behaviour.

    Order of evaluation does not decide the outcome; it only decides the order
    findings are reported in. That is the whole difference from first-match-wins.
    """
    findings: list[Finding] = []
    seen: set[str] = set()

    def add(finding: Finding | None) -> None:
        if finding is not None:
            findings.append(finding)
            seen.add(finding.id)

    def add_all(items: tuple[Finding, ...]) -> None:
        for item in items:
            add(item)

    add(_f1_no_candidate(ident))
    add(_f12_offence_not_identified(ident))

    if not ident.is_empty:
        add(_f16_several_provisions(ident, correspondence))
        if "F16" not in seen:
            add(_f2_f3_two_candidates(ident, correspondence))
        add_all(_f5_date_given(ident, correspondence))
        add_all(_f6_f7_f8_correspondence(ident, correspondence, seen))
        add_all(_f9_court_split(ident, splits))
        # Materiality answers 'did the punishment change for this offence'.
        # That question is premature while it is still unclear which offence
        # the user means, so F2 and F3 suppress it.
        if not (seen & {"F2", "F3"}):
            add_all(_f10_f11_materiality(ident, correspondence))
        add(_f13_low_confidence(ident))
        add(_f15_procedure_and_substance(ident))
        # F4 only where nothing else raised a concern about which law applies.
        if not seen:
            add(_f4_code_named(ident))

    add(_f14_retrieval_led(ident, tuple(findings)))

    # A date the question could not resolve is itself a reason to ask.
    if ident.date_ambiguous and Behaviour.ASK not in {f.behaviour for f in findings}:
        add(
            Finding(
                "F10",
                Behaviour.ASK,
                f"the date given ({ident.date_evidence}) spans the change of code, "
                "so it does not settle which law applies",
                ident.sections(),
            )
        )

    ordered = tuple(findings)
    return Decision(combine(ordered), ordered)
