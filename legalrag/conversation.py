"""Small deterministic conversation state for resolving missing facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from legalrag.models import Code


@dataclass(frozen=True, slots=True)
class BoundFacts:
    date: date | None = None
    court: str | None = None
    offence: str | None = None
    code: Code | None = None


@dataclass(frozen=True, slots=True)
class ConversationState:
    original_question: str
    facts: BoundFacts = field(default_factory=BoundFacts)
    pending_fact: str | None = None
    attempts: int = 0


def bind_fact(state: ConversationState, fact: str, value: object) -> ConversationState:
    if fact == "date":
        if not isinstance(value, date):
            raise TypeError("date fact must be a date")
        facts = BoundFacts(value, state.facts.court, state.facts.offence, state.facts.code)
    elif fact == "court":
        if not isinstance(value, str):
            raise TypeError("court fact must be a string")
        facts = BoundFacts(state.facts.date, value, state.facts.offence, state.facts.code)
    elif fact == "offence":
        if not isinstance(value, str):
            raise TypeError("offence fact must be a string")
        facts = BoundFacts(state.facts.date, state.facts.court, value, state.facts.code)
    elif fact == "code":
        if not isinstance(value, Code):
            raise TypeError("code fact must be a Code")
        facts = BoundFacts(state.facts.date, state.facts.court, state.facts.offence, value)
    else:
        raise ValueError(f"unsupported fact: {fact}")
    return ConversationState(state.original_question, facts, None, state.attempts)


def cannot_answer(state: ConversationState) -> ConversationState:
    """After two unanswered attempts, clear the ask and let alternatives render."""
    attempts = state.attempts + 1
    return ConversationState(
        state.original_question,
        state.facts,
        None if attempts >= 2 else state.pending_fact,
        attempts,
    )


def resume_question(state: ConversationState, reply: str, *, subject_changed: bool = False) -> str:
    if subject_changed:
        return reply
    if state.pending_fact is None:
        return reply
    return state.original_question
