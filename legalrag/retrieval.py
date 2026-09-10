"""Deterministic judgment retrieval contracts.

The module intentionally does not depend on a vector database or model SDK. A
store supplies meaning and lexical result lists; this module filters, fuses,
and optionally reorders them without allowing a flat score bonus to dominate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from legalrag.ingestion import Passage


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    passage: Passage
    score: float
    rank: int
    source: str


class Reorderer(Protocol):
    def __call__(self, question: str, passages: tuple[Passage, ...]) -> tuple[Passage, ...]: ...


def reciprocal_rank(rank: int, *, constant: int = 60) -> float:
    if rank < 1:
        raise ValueError("rank must be positive")
    if constant < 0:
        raise ValueError("constant must not be negative")
    return 1.0 / (constant + rank)


def fuse_ranked(
    meaning: tuple[RetrievalHit, ...],
    lexical: tuple[RetrievalHit, ...],
    *,
    meaning_weight: float = 0.5,
    lexical_weight: float = 0.5,
    limit: int = 10,
    rank_constant: int = 60,
) -> tuple[RetrievalHit, ...]:
    """Fuse two ranked lists using weighted reciprocal rank fusion."""
    if meaning_weight < 0 or lexical_weight < 0 or meaning_weight + lexical_weight == 0:
        raise ValueError("search weights must be non-negative and not both zero")
    if limit < 1:
        raise ValueError("limit must be positive")

    scores: dict[str, float] = {}
    passages: dict[str, Passage] = {}
    for weight, hits in ((meaning_weight, meaning), (lexical_weight, lexical)):
        for hit in hits:
            passage_id = hit.passage.passage_id
            scores[passage_id] = scores.get(passage_id, 0.0) + weight * reciprocal_rank(
                hit.rank, constant=rank_constant
            )
            passages[passage_id] = hit.passage

    ordered = sorted(scores, key=lambda passage_id: (-scores[passage_id], passage_id))[:limit]
    return tuple(
        RetrievalHit(passages[passage_id], scores[passage_id], index, "fused")
        for index, passage_id in enumerate(ordered, start=1)
    )


def retrieve(
    question: str,
    meaning: tuple[RetrievalHit, ...],
    lexical: tuple[RetrievalHit, ...],
    *,
    reorder: Reorderer | None = None,
    limit: int = 10,
    meaning_weight: float = 0.5,
    lexical_weight: float = 0.5,
) -> tuple[RetrievalHit, ...]:
    """Fuse a shortlist, then let the explicit reorder pass decide final order."""
    fused = fuse_ranked(
        meaning,
        lexical,
        meaning_weight=meaning_weight,
        lexical_weight=lexical_weight,
        limit=limit,
    )
    if reorder is None:
        return fused
    reordered = reorder(question, tuple(hit.passage for hit in fused))
    by_id = {hit.passage.passage_id: hit for hit in fused}
    return tuple(by_id[passage.passage_id] for passage in reordered if passage.passage_id in by_id)
