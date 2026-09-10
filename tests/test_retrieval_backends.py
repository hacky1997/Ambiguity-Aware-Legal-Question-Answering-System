from __future__ import annotations

import pytest

from legalrag.ingestion import Passage
from legalrag.retrieval_backends import BM25Backend, RetrievalBackendUnavailableError


def test_bm25_returns_exact_term_matches():
    passages = (
        Passage("p1", "d1", "IPC section 302 murder", "1", 0, 24, ("302",)),
        Passage("p2", "d2", "BNS section 103 murder", "2", 0, 23, ("103",)),
    )
    try:
        hits = BM25Backend(passages).search("IPC section 302")
    except RetrievalBackendUnavailableError:
        pytest.skip("retrieval extra is not installed")
    assert hits[0].passage.passage_id == "p1"
