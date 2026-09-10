"""Concrete Qdrant and BM25 retrieval adapters.

Both adapters return the repository's provider-neutral RetrievalHit type. The
embedding provider is injected so model selection remains an evaluation choice,
not a hidden dependency in the store.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from legalrag.ingestion import Passage
from legalrag.retrieval import RetrievalHit

Embedder = Callable[[str], list[float]]


class RetrievalBackendUnavailableError(RuntimeError):
    """Raised when an optional retrieval backend is not installed."""


@dataclass(frozen=True, slots=True)
class PassageRecord:
    passage: Passage
    vector: list[float] | None = None


class BM25Backend:
    """Exact lexical retrieval over passage text using rank_bm25."""

    def __init__(self, passages: Iterable[Passage]) -> None:
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RetrievalBackendUnavailableError(
                "BM25 requires the project's retrieval extra"
            ) from exc
        self._passages = tuple(passages)
        self._engine = BM25Okapi([passage.text.lower().split() for passage in self._passages])

    def search(self, query: str, *, limit: int = 10) -> tuple[RetrievalHit, ...]:
        scores = self._engine.get_scores(query.lower().split())
        ranked = sorted(
            range(len(self._passages)),
            key=lambda index: (-float(scores[index]), self._passages[index].passage_id),
        )[:limit]
        return tuple(
            RetrievalHit(self._passages[index], float(scores[index]), rank, "lexical")
            for rank, index in enumerate(ranked, start=1)
        )


class QdrantBackend:
    """Vector retrieval with payload filters applied by Qdrant before ranking."""

    def __init__(self, client: Any, collection: str, embed: Embedder) -> None:
        self._client = client
        self._collection = collection
        self._embed = embed

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        provision_refs: tuple[str, ...] = (),
        court: str | None = None,
    ) -> tuple[RetrievalHit, ...]:
        try:
            from qdrant_client.models import (  # type: ignore[import-not-found]
                FieldCondition,
                Filter,
                MatchAny,
                MatchValue,
            )
        except ImportError as exc:
            raise RetrievalBackendUnavailableError(
                "Qdrant requires the project's retrieval extra"
            ) from exc

        conditions: list[Any] = []
        if provision_refs:
            conditions.append(
                FieldCondition(key="provision_refs", match=MatchAny(any=list(provision_refs)))
            )
        if court:
            conditions.append(FieldCondition(key="court", match=MatchValue(value=court)))
        query_filter = Filter(must=conditions) if conditions else None
        points = self._client.query_points(
            collection_name=self._collection,
            query=self._embed(query),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        ).points
        hits = []
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            passage = Passage(
                passage_id=str(payload["passage_id"]),
                document_id=str(payload["document_id"]),
                text=str(payload["text"]),
                paragraph=payload.get("paragraph"),
                start=int(payload.get("start", 0)),
                end=int(payload.get("end", 0)),
                provision_refs=tuple(payload.get("provision_refs", ())),
            )
            hits.append(RetrievalHit(passage, float(point.score), rank, "meaning"))
        return tuple(hits)
