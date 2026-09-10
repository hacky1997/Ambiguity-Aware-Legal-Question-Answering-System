"""Decide whether a change between two provisions is material.

The published cross-code mappings score provisions by text similarity. That
answers "is this the successor". It does not answer "did the punishment
change", which is what the finding rules actually need in order to choose
between answering on a stated assumption and asking for the offence date.

The worked case: IPC 336 and BNS 125 score 95 per cent alike and are labelled
carried over almost unchanged. Maximum imprisonment goes from 3 months to 36,
maximum fine from 250 rupees to 10,000, and the provision gains two aggravated
limbs. Material, plainly, and similarity cannot see it.

This module makes that call from the extracted sentencing terms, and reports
every reason so the decision can be read rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from legalrag.punishment import Punishment, Severity, extract_punishment

__all__ = ["Materiality", "MaterialityVerdict", "assess_materiality", "compare_texts"]

# Ordering used to say whether severity rose or fell.
_SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


class Materiality(StrEnum):
    MATERIAL = "material"  # punishment or structure changed -> F10, ask for date
    IMMATERIAL = "immaterial"  # renumbering only -> F11, answer on a stated assumption
    NO_SUCCESSOR = "no_successor"  # -> F8
    UNDETERMINED = "undetermined"  # parser could not decide -> human or judge review


@dataclass(slots=True)
class MaterialityVerdict:
    materiality: Materiality
    reasons: list[str] = field(default_factory=list)
    old: Punishment | None = None
    new: Punishment | None = None
    needs_review: bool = False
    review_cause: str | None = None

    @property
    def finding(self) -> str:
        return {
            Materiality.MATERIAL: "F10",
            Materiality.IMMATERIAL: "F11",
            Materiality.NO_SUCCESSOR: "F8",
            Materiality.UNDETERMINED: "review",
        }[self.materiality]


def _describe_months(months: int | None) -> str:
    if months is None:
        return "unspecified"
    if months % 12 == 0 and months >= 12:
        return f"{months // 12} year(s)"
    return f"{months} month(s)"


def assess_materiality(old: Punishment, new: Punishment | None) -> MaterialityVerdict:
    """Compare two extracted punishments.

    Errs towards MATERIAL. A wrongly material provision costs the user one
    follow-up question. A wrongly immaterial provision puts a wrong sentence
    in front of someone who cannot tell it is wrong.
    """
    if new is None:
        return MaterialityVerdict(
            Materiality.NO_SUCCESSOR,
            ["no successor provision in the corresponding code"],
            old=old,
        )

    verdict = MaterialityVerdict(Materiality.UNDETERMINED, old=old, new=new)

    # Neither side parsed as a sentencing provision. Many provisions are
    # definitions or general clauses and carry no punishment at all, so this
    # is normal, not a failure. It simply cannot be decided from sentencing.
    if old.parse_confidence == "none" and new.parse_confidence == "none":
        verdict.materiality = Materiality.UNDETERMINED
        verdict.reasons.append("no sentencing language found in either provision")
        verdict.needs_review = True
        verdict.review_cause = "not_a_sentencing_provision"
        return verdict

    if "partial" in {old.parse_confidence, new.parse_confidence}:
        verdict.needs_review = True
        verdict.review_cause = "partial_parse"
        verdict.reasons.append("sentencing language present that the parser could not fully read")

    reasons: list[str] = []

    if old.max_imprisonment_months != new.max_imprisonment_months:
        reasons.append(
            f"maximum imprisonment {_describe_months(old.max_imprisonment_months)} "
            f"to {_describe_months(new.max_imprisonment_months)}"
        )
    if old.min_imprisonment_months != new.min_imprisonment_months:
        reasons.append(
            f"minimum imprisonment {_describe_months(old.min_imprisonment_months)} "
            f"to {_describe_months(new.min_imprisonment_months)}"
        )
    if old.max_fine_rupees != new.max_fine_rupees:
        reasons.append(f"maximum fine {old.max_fine_rupees} to {new.max_fine_rupees} rupees")
    if old.min_fine_rupees != new.min_fine_rupees:
        reasons.append(f"minimum fine {old.min_fine_rupees} to {new.min_fine_rupees} rupees")
    if old.fine_unbounded != new.fine_unbounded:
        reasons.append("fine changed between a stated amount and an unstated one")
    if old.fine_mandatory != new.fine_mandatory:
        reasons.append("fine changed between mandatory and discretionary")
    if old.death_available != new.death_available:
        reasons.append("availability of the death penalty changed")
    if old.life_available != new.life_available:
        reasons.append("availability of life imprisonment changed")
    if old.community_service != new.community_service:
        reasons.append("community service availability changed")
    if old.imprisonment_and_fine != new.imprisonment_and_fine:
        reasons.append("combination of imprisonment and fine changed")
    if old.max_severity is not new.max_severity:
        direction = (
            "increased"
            if _SEVERITY_ORDER[new.max_severity] > _SEVERITY_ORDER[old.max_severity]
            else "decreased"
        )
        reasons.append(
            f"severity {direction}: {old.max_severity.value} to {new.max_severity.value}"
        )
    if old.limb_count != new.limb_count:
        reasons.append(
            f"number of sentencing limbs changed from {old.limb_count} to {new.limb_count}"
        )

    if reasons:
        verdict.materiality = Materiality.MATERIAL
        verdict.reasons.extend(reasons)
    else:
        verdict.materiality = Materiality.IMMATERIAL
        verdict.reasons.append("no difference detected in any extracted sentencing term")

    return verdict


def compare_texts(old_text: str, new_text: str | None) -> MaterialityVerdict:
    """Convenience wrapper over raw provision texts."""
    old = extract_punishment(old_text)
    new = extract_punishment(new_text) if new_text is not None else None
    return assess_materiality(old, new)
