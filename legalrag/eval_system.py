"""Deterministic local system adapter used by the evaluation command.

This is a corpus-free smoke system for the checked-in golden contract. A
production factory must inject the real vocabulary, index and correspondence
stores; this module makes the evaluation path executable without pretending the
external corpus is present.
"""

from __future__ import annotations

from collections.abc import Callable

from legalrag.evals import SystemOutput
from legalrag.findings import evaluate
from legalrag.identify import identify
from legalrag.models import Behaviour
from tests.fakes import FakeCorrespondence, FakeIndex, FakeSplits, FakeVocabulary


def build_system() -> Callable[[str], SystemOutput]:
    """Build the deterministic local adapter for evaluation smoke runs."""
    vocabulary = FakeVocabulary()
    index = FakeIndex()
    correspondence = FakeCorrespondence()
    splits = FakeSplits()

    def run(question: str) -> SystemOutput:
        identification = identify(question, vocabulary=vocabulary, index=index)
        decision = evaluate(identification, correspondence=correspondence, splits=splits)
        provisions = tuple(str(candidate.ref) for candidate in identification.candidates)
        assumption = (
            "the earlier code applies"
            if decision.behaviour is Behaviour.ANSWER_WITH_ASSUMPTION
            else None
        )
        return SystemOutput(
            behaviour=decision.behaviour.value,
            provisions=provisions,
            findings=decision.finding_ids,
            assumption=assumption,
            provision_confidence=(
                identification.best_confidence.value
                if identification.best_confidence
                else "none"
            ),
        )

    return run
