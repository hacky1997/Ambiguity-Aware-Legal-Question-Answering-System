from __future__ import annotations

from pathlib import Path

from legalrag.ingestion import build_index_name, load_manifest, select_sources


def test_index_name_matches_the_versioned_contract():
    assert build_index_name(3, "text-embedding-3-small", "2025-01-15") == (
        "chunks_v3_text-embedding-3-small_2025-01-15"
    )


def test_manifest_loads_and_filters_sources(tmp_path: Path):
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        """
version: 2
sources:
  - id: a
    tier: primary
    name: Alpha
    fetch: s3
  - id: b
    tier: derived
    name: Beta
    fetch: git
  - id: c
    tier: primary
    name: Gamma
    fetch: hf
""".strip(),
        encoding="utf-8",
    )

    entries = load_manifest(manifest)
    assert {entry.id for entry in entries} == {"a", "b", "c"}
    selected = select_sources(entries, tiers={"primary"}, only={"a", "c"})
    assert [entry.id for entry in selected] == ["a", "c"]
