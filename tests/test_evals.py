"""Harness tests. The harness is the gate on everything else, so it needs to be
correct about the two things that matter: refusing to report a rate it cannot
support, and blocking a regression in the dangerous direction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalrag.evals import (
    MIN_ITEMS_FOR_RATE,
    GoldenItem,
    GoldenSetError,
    Rate,
    SystemOutput,
    compare_to_baseline,
    load_golden,
    run_eval,
)


def test_rate_suppresses_small_samples():
    """A rate over six items is not a measurement and must not look like one."""
    assert not Rate(4, 6).sufficient
    assert "insufficient data" in Rate(4, 6).render()
    assert Rate(15, MIN_ITEMS_FOR_RATE).sufficient


def test_interval_stays_inside_zero_and_one():
    for num, den in [(0, 30), (30, 30), (1, 30), (29, 30)]:
        lo, hi = Rate(num, den).interval()
        assert 0.0 <= lo <= hi <= 1.0


def test_zero_denominator_is_not_a_crash():
    r = Rate(0, 0)
    assert r.value is None and r.interval() is None and r.render() == "no items"


def test_invalid_behaviour_raises():
    with pytest.raises(GoldenSetError):
        GoldenItem(id="x", question="q", expected_behaviour="maybe")


def test_assumption_label_required():
    with pytest.raises(GoldenSetError):
        GoldenItem(id="x", question="q", expected_behaviour="answer_with_assumption")


def test_duplicate_ids_raise(tmp_path: Path):
    p = tmp_path / "g.jsonl"
    row = {"id": "a", "question": "q", "expected_behaviour": "answer"}
    p.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(GoldenSetError):
        load_golden(p)


def _golden(n: int, behaviour: str = "ask") -> list[GoldenItem]:
    return [
        GoldenItem(id=f"g{i}", question=f"q{i}", expected_behaviour=behaviour, label_source="hand")
        for i in range(n)
    ]


def test_unsafe_confidence_is_counted_separately():
    """Answering when caution was required is the damaging failure and must not
    be averaged into overall accuracy."""
    golden = _golden(25, "ask")
    report = run_eval(golden, lambda q: SystemOutput("answer"))
    assert report.unsafe_confidence.numerator == 25
    assert report.behaviour_correct.numerator == 0


def test_unnecessary_asking_is_not_unsafe():
    golden = _golden(25, "answer")
    report = run_eval(golden, lambda q: SystemOutput("ask"))
    assert report.unnecessary_asking.numerator == 25
    assert report.unsafe_confidence.numerator == 0


def test_gate_blocks_any_increase_in_unsafe_confidence():
    golden = _golden(25, "ask")
    report = run_eval(golden, lambda q: SystemOutput("answer"))
    passed, messages = compare_to_baseline(
        report, {"metrics": {"unsafe_confidence": {"value": 0.0}}}
    )
    assert not passed
    assert any("unsafe_confidence" in m for m in messages)


def test_gate_passes_when_nothing_regressed():
    golden = _golden(25, "ask")
    report = run_eval(golden, lambda q: SystemOutput("ask"))
    passed, _ = compare_to_baseline(
        report,
        {"metrics": {"unsafe_confidence": {"value": 0.0}, "behaviour_correct": {"value": 1.0}}},
    )
    assert passed


def test_label_sources_are_reported():
    """So a metric derived from the same signal the rules use stays visible."""
    golden = [
        *_golden(5),
        GoldenItem(
            id="x",
            question="q",
            expected_behaviour="ask",
            label_source="sentencing_extraction",
        ),
    ]
    report = run_eval(golden, lambda q: SystemOutput("ask"))
    assert report.label_sources == {"hand": 5, "sentencing_extraction": 1}
