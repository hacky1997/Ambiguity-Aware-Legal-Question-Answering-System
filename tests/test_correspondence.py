from __future__ import annotations

import pytest

from scripts.build_correspondence import SourceError, fetch_pair


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def get(self, url, *, timeout):
        self.url = url
        return Response(self.payload)


def test_fetch_pair_reads_structured_mapping_without_scraping():
    session = Session(
        {
            "old_text": "old provision",
            "best_match": {"ref": "125", "text": "new provision", "similarity": 95},
            "alternates": [{"ref": "126", "score": 70}],
        }
    )
    pair = fetch_pair("IPC 336", session=session, timeout=2.0)
    assert session.url.endswith("/ipc-to-bns/336/")
    assert pair.best_new_ref == "125"
    assert pair.alternates == [("126", 70.0)]


def test_fetch_pair_rejects_unknown_shape():
    with pytest.raises(SourceError):
        fetch_pair("IPC 336", session=Session({"answer": "guess"}), timeout=2.0)
