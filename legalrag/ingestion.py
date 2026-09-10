"""Minimal ingestion helpers for the legal data build contract.

This module is intentionally small and deterministic: it provides the versioned
index naming convention and the manifest selection logic that the runtime and
scripts rely on.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "Document",
    "IngestionReport",
    "Passage",
    "Source",
    "build_index_name",
    "build_passages",
    "deduplicate_documents",
    "document_quality",
    "extract_provision_refs",
    "load_manifest",
    "paragraphs",
    "select_sources",
]


@dataclass(frozen=True, slots=True)
class Source:
    """One manifest entry describing an upstream data source."""

    id: str
    tier: str
    name: str
    fetch: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        missing = {"id", "tier", "name", "fetch"} - data.keys()
        if missing:
            raise ValueError(f"manifest entry missing keys: {sorted(missing)}")
        return cls(
            id=str(data["id"]),
            tier=str(data["tier"]),
            name=str(data["name"]),
            fetch=str(data["fetch"]),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Document:
    """A normalized judgment document before passage indexing."""

    document_id: str
    court: str
    decision_date: date | None
    text: str
    extraction_method: str
    quality: float
    case_identifier: str | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class Passage:
    """A stable, citable unit in the judgment index."""

    passage_id: str
    document_id: str
    text: str
    paragraph: str | None
    start: int
    end: int
    provision_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IngestionReport:
    accepted: int
    excluded: int
    duplicates: int


_PARAGRAPH_RE = re.compile(r"(?m)^(?:\s*\[(?P<bracket>\d+)\]|\s*(?P<plain>\d+)\.)\s+")
_PROVISION_RE = re.compile(
    r"\b(?:section|sections|s\.|sec\.)\s*(\d+[A-Za-z]?(?:\(\w+\))?)\b",
    re.IGNORECASE,
)


def document_quality(text: str) -> float:
    """Return a conservative readability score in the range 0..1."""
    if not text.strip():
        return 0.0
    visible = sum(
        character.isalnum() or character.isspace() or character in ".,;:!?()[]-"
        for character in text
    )
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.0
    return round(min(1.0, (visible / len(text)) * min(1.0, len(words) / 20)), 4)


def paragraphs(text: str) -> tuple[tuple[str | None, str, int, int], ...]:
    """Split numbered paragraphs, falling back to non-empty lines."""
    matches = list(_PARAGRAPH_RE.finditer(text))
    if not matches:
        out: list[tuple[str | None, str, int, int]] = []
        for line in text.splitlines(keepends=True):
            value = line.strip()
            if value:
                start = text.find(value, out[-1][3] if out else 0)
                out.append((None, value, start, start + len(value)))
        return tuple(out)

    out = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        if value:
            value_start = text.find(value, start, end)
            number = match.group("bracket") or match.group("plain")
            out.append((number, value, value_start, value_start + len(value)))
    return tuple(out)


def extract_provision_refs(text: str) -> tuple[str, ...]:
    """Extract section strings for metadata without claiming their act."""
    return tuple(dict.fromkeys(match.group(1) for match in _PROVISION_RE.finditer(text)))


def build_passages(document: Document) -> tuple[Passage, ...]:
    """Build stable passages and retain source offsets for citation checks."""
    result = []
    for paragraph, text, start, end in paragraphs(document.text):
        digest = hashlib.sha256(f"{document.document_id}:{start}:{end}".encode()).hexdigest()[:16]
        result.append(
            Passage(
                passage_id=f"{document.document_id}:{digest}",
                document_id=document.document_id,
                text=text,
                paragraph=paragraph,
                start=start,
                end=end,
                provision_refs=extract_provision_refs(text),
            )
        )
    return tuple(result)


def deduplicate_documents(documents: Iterable[Document]) -> tuple[tuple[Document, ...], int]:
    """Keep the richest extraction for each case/court/date identity."""
    selected: dict[tuple[str, str, date | None], Document] = {}
    duplicates = 0
    for document in documents:
        key = (
            document.case_identifier or document.document_id,
            document.court,
            document.decision_date,
        )
        previous = selected.get(key)
        if previous is None:
            selected[key] = document
        else:
            duplicates += 1
            if (document.quality, len(document.text)) > (previous.quality, len(previous.text)):
                selected[key] = document
    return tuple(selected.values()), duplicates


def build_index_name(version: int, model_name: str, date_stamp: str) -> str:
    """Return the canonical versioned index artifact name."""
    return f"chunks_v{version}_{model_name}_{date_stamp}"


def load_manifest(path: str | Path) -> list[Source]:
    """Load a YAML source manifest and return the declared sources."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"manifest root must be a mapping: {manifest_path}")

    entries = payload.get("sources")
    if not isinstance(entries, list):
        raise ValueError(f"manifest missing 'sources' list: {manifest_path}")

    return [Source.from_dict(entry) for entry in entries]


def select_sources(
    sources: Iterable[Source],
    tiers: set[str] | None = None,
    only: set[str] | None = None,
) -> list[Source]:
    """Filter source entries by tier and/or explicit id subset."""
    chosen = list(sources)
    if only:
        unknown = only - {source.id for source in chosen}
        if unknown:
            raise ValueError(f"unknown source id(s): {sorted(unknown)}")
        chosen = [source for source in chosen if source.id in only]
    if tiers:
        chosen = [source for source in chosen if source.tier in tiers]
    return chosen
