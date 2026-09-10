"""Evaluation harness.

An evaluation you cannot run twice and get the same answer is not an
evaluation. Everything here is deterministic given the same golden set and the
same system under test, and every run records what it ran against so a number
can be traced back to the thing that produced it.

Deliberately small. One module, no framework, no plugin system. The harness
exists to answer four questions and gets no bigger than that:

  1. Did the system choose the right behaviour.
  2. When it was wrong, was it wrong in the dangerous direction.
  3. Did it identify the right provision.
  4. Which rule regressed.

Every rate is reported with a Wilson score interval and the count it was
computed on, because a rate over eleven items is not a measurement and should
not be allowed to look like one.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legalrag.models import Behaviour

__all__ = [
    "BEHAVIOURS",
    "EvalReport",
    "GoldenItem",
    "Rate",
    "SystemOutput",
    "compare_to_baseline",
    "load_golden",
    "run_eval",
]

# The four behaviours. Single source of truth is legalrag.models.
BEHAVIOURS: tuple[str, ...] = tuple(b.value for b in Behaviour)

# Ordered least to most cautious. Used to decide which direction an error went.
_CAUTION: dict[str, int] = {
    Behaviour.ANSWER.value: 0,
    Behaviour.ANSWER_WITH_ASSUMPTION.value: 1,
    Behaviour.ASK.value: 2,
    Behaviour.ALTERNATIVES.value: 2,
}

# Below this, a rate is reported as insufficient data rather than as a number.
MIN_ITEMS_FOR_RATE = 20


class GoldenSetError(ValueError):
    """Raised when the golden set is malformed. Never silently repaired."""


@dataclass(frozen=True, slots=True)
class GoldenItem:
    """One evaluated question and what the right response was.

    ``label_source`` records where the expected values came from. It exists so
    that a metric derived from the same signal the system uses can be spotted
    rather than quietly reported as accuracy.
    """

    id: str
    question: str
    expected_behaviour: str
    expected_provisions: tuple[str, ...] = ()
    expected_assumption: str | None = None
    label_source: str = "unspecified"
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.expected_behaviour not in BEHAVIOURS:
            raise GoldenSetError(
                f"{self.id}: expected_behaviour {self.expected_behaviour!r} not one of {BEHAVIOURS}"
            )
        if self.expected_behaviour == "answer_with_assumption" and not self.expected_assumption:
            raise GoldenSetError(
                f"{self.id}: expected_behaviour is answer_with_assumption but no "
                "expected_assumption given"
            )


@dataclass(frozen=True, slots=True)
class SystemOutput:
    """What the system under test returned for one item."""

    behaviour: str
    provisions: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    assumption: str | None = None
    provision_confidence: str = "unknown"  # high | low | none

    def __post_init__(self) -> None:
        if self.behaviour not in BEHAVIOURS:
            raise GoldenSetError(f"system returned invalid behaviour {self.behaviour!r}")


@dataclass(frozen=True, slots=True)
class Rate:
    """A proportion with its Wilson score interval and its denominator."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def sufficient(self) -> bool:
        return self.denominator >= MIN_ITEMS_FOR_RATE

    def interval(self, z: float = 1.96) -> tuple[float, float] | None:
        """Wilson score interval. Correct near 0 and 1, unlike the normal
        approximation, which matters because the rates that decide a release
        are the ones close to zero."""
        n = self.denominator
        if n == 0:
            return None
        p = self.numerator / n
        denom = 1 + z * z / n
        centre = (p + z * z / (2 * n)) / denom
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        return (max(0.0, centre - margin), min(1.0, centre + margin))

    def render(self) -> str:
        if self.denominator == 0:
            return "no items"
        if not self.sufficient:
            return f"insufficient data (n={self.denominator}, need {MIN_ITEMS_FOR_RATE})"
        lo, hi = self.interval()  # type: ignore[misc]
        return f"{self.value:.1%} [{lo:.1%}, {hi:.1%}] (n={self.denominator})"

    def to_dict(self) -> dict[str, Any]:
        iv = self.interval()
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "ci_low": iv[0] if iv else None,
            "ci_high": iv[1] if iv else None,
            "sufficient": self.sufficient,
        }


@dataclass(slots=True)
class EvalReport:
    behaviour_correct: Rate
    unsafe_confidence: Rate
    unnecessary_asking: Rate
    provision_top1: Rate
    provision_recall: Rate
    wrong_and_confident: Rate
    assumption_correct: Rate
    per_finding: dict[str, dict[str, Any]] = field(default_factory=dict)
    label_sources: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    total_items: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "metrics": {
                name: getattr(self, name).to_dict()
                for name in (
                    "behaviour_correct",
                    "unsafe_confidence",
                    "unnecessary_asking",
                    "provision_top1",
                    "provision_recall",
                    "wrong_and_confident",
                    "assumption_correct",
                )
            },
            "per_finding": self.per_finding,
            "label_sources": self.label_sources,
            "failures": self.failures,
        }

    def render(self) -> str:
        lines = [f"items: {self.total_items}", ""]
        for label, rate in (
            ("behaviour correct", self.behaviour_correct),
            ("UNSAFE CONFIDENCE", self.unsafe_confidence),
            ("unnecessary asking", self.unnecessary_asking),
            ("provision top-1", self.provision_top1),
            ("provision recall", self.provision_recall),
            ("wrong and confident", self.wrong_and_confident),
            ("assumption correct", self.assumption_correct),
        ):
            lines.append(f"  {label:22} {rate.render()}")
        if self.per_finding:
            lines += ["", "  per finding:"]
            for finding, stats in sorted(self.per_finding.items()):
                lines.append(
                    f"    {finding:8} fired={stats['fired']:4}  correct={stats['correct_rate']}"
                )
        if self.label_sources:
            lines += [
                "",
                "  label sources: "
                + ", ".join(f"{k}={v}" for k, v in sorted(self.label_sources.items())),
            ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------


def load_golden(path: Path) -> list[GoldenItem]:
    """Read a golden set. Malformed rows raise; they are never skipped."""
    items: list[GoldenItem] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GoldenSetError(f"{path}:{line_no}: {exc}") from exc
            item = GoldenItem(
                id=raw["id"],
                question=raw["question"],
                expected_behaviour=raw["expected_behaviour"],
                expected_provisions=tuple(raw.get("expected_provisions", ())),
                expected_assumption=raw.get("expected_assumption"),
                label_source=raw.get("label_source", "unspecified"),
                notes=raw.get("notes"),
            )
            if item.id in seen:
                raise GoldenSetError(f"{path}:{line_no}: duplicate id {item.id!r}")
            seen.add(item.id)
            items.append(item)
    if not items:
        raise GoldenSetError(f"{path}: no items")
    return items


def _is_unsafe(expected: str, actual: str) -> bool:
    """Answered, or answered on an assumption, when caution was required.

    The failure that puts a wrong sentence in front of someone who cannot tell
    it is wrong. Tracked on its own because averaging it into overall accuracy
    hides it.
    """
    return _CAUTION[actual] < _CAUTION[expected]


def run_eval(
    golden: Sequence[GoldenItem],
    system: Callable[[str], SystemOutput],
    *,
    max_failures_recorded: int = 50,
) -> EvalReport:
    """Run the system over the golden set and compute every metric."""
    n = len(golden)
    behaviour_hits = 0
    unsafe = 0
    unnecessary = 0
    prov_top1_hits = prov_top1_n = 0
    prov_recall_hits = prov_recall_n = 0
    wrong_confident = wrong_confident_n = 0
    assumption_hits = assumption_n = 0

    per_finding: dict[str, dict[str, int]] = defaultdict(lambda: {"fired": 0, "correct": 0})
    label_sources: dict[str, int] = defaultdict(int)
    failures: list[dict[str, Any]] = []

    for item in golden:
        label_sources[item.label_source] += 1
        out = system(item.question)
        correct = out.behaviour == item.expected_behaviour

        if correct:
            behaviour_hits += 1
        else:
            if _is_unsafe(item.expected_behaviour, out.behaviour):
                unsafe += 1
            elif item.expected_behaviour == "answer" and out.behaviour == "ask":
                unnecessary += 1
            if len(failures) < max_failures_recorded:
                failures.append(
                    {
                        "id": item.id,
                        "question": item.question,
                        "expected": item.expected_behaviour,
                        "actual": out.behaviour,
                        "unsafe": _is_unsafe(item.expected_behaviour, out.behaviour),
                        "findings": list(out.findings),
                        "expected_provisions": list(item.expected_provisions),
                        "actual_provisions": list(out.provisions),
                    }
                )

        for finding in out.findings:
            per_finding[finding]["fired"] += 1
            if correct:
                per_finding[finding]["correct"] += 1

        if item.expected_provisions:
            prov_top1_n += 1
            prov_recall_n += 1
            if out.provisions and out.provisions[0] in item.expected_provisions:
                prov_top1_hits += 1
            if set(item.expected_provisions) & set(out.provisions):
                prov_recall_hits += 1
            else:
                wrong_confident_n += 1
                if out.provisions and out.provision_confidence == "high":
                    wrong_confident += 1

        if item.expected_behaviour == "answer_with_assumption":
            assumption_n += 1
            if (
                out.assumption
                and item.expected_assumption
                and item.expected_assumption.lower() in out.assumption.lower()
            ):
                assumption_hits += 1

    return EvalReport(
        behaviour_correct=Rate(behaviour_hits, n),
        unsafe_confidence=Rate(unsafe, n),
        unnecessary_asking=Rate(unnecessary, n),
        provision_top1=Rate(prov_top1_hits, prov_top1_n),
        provision_recall=Rate(prov_recall_hits, prov_recall_n),
        wrong_and_confident=Rate(wrong_confident, wrong_confident_n),
        assumption_correct=Rate(assumption_hits, assumption_n),
        per_finding={
            k: {"fired": v["fired"], "correct_rate": Rate(v["correct"], v["fired"]).render()}
            for k, v in per_finding.items()
        },
        label_sources=dict(label_sources),
        failures=failures,
        total_items=n,
    )


# ---------------------------------------------------------------------------


# Metrics where an increase is a regression, with how much movement is tolerated.
_LOWER_IS_BETTER = {
    "unsafe_confidence": 0.0,
    "unnecessary_asking": 0.02,
    "wrong_and_confident": 0.0,
}
_HIGHER_IS_BETTER = {"behaviour_correct": 0.02, "provision_top1": 0.02, "provision_recall": 0.02}


def compare_to_baseline(report: EvalReport, baseline: dict[str, Any]) -> tuple[bool, list[str]]:
    """Compare against a stored baseline. Returns (passed, messages).

    Tolerances are deliberately asymmetric. Unsafe confidence and wrong and
    confident have zero tolerance: any increase blocks. The others allow small
    movement so that ordinary noise does not block a release.
    """
    messages: list[str] = []
    passed = True
    current = report.to_dict()["metrics"]
    previous = baseline.get("metrics", {})

    for name, tolerance in _LOWER_IS_BETTER.items():
        now, before = current.get(name, {}).get("value"), previous.get(name, {}).get("value")
        if now is None or before is None:
            continue
        if now > before + tolerance:
            passed = False
            messages.append(
                f"REGRESSION {name}: {before:.1%} -> {now:.1%} (tolerance {tolerance:.1%})"
            )

    for name, tolerance in _HIGHER_IS_BETTER.items():
        now, before = current.get(name, {}).get("value"), previous.get(name, {}).get("value")
        if now is None or before is None:
            continue
        if now < before - tolerance:
            passed = False
            messages.append(
                f"REGRESSION {name}: {before:.1%} -> {now:.1%} (tolerance {tolerance:.1%})"
            )

    if not messages:
        messages.append("no regression against baseline")
    return passed, messages
