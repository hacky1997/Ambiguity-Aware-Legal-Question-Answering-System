"""Build the correspondence file from published sources, without hand annotation.

What this produces
------------------
One row per provision of the old code:

    old_ref, new_refs[], relationship, similarity, materiality, finding,
    reasons[], evidence_spans[], confidence, adjudication_cause

Two independent signals decide each row:

  1. Text similarity, from the published cross-code mapping. Answers "which
     provision is the successor".
  2. Sentencing extraction, from legalrag.punishment. Answers "did the
     punishment change".

They are independent because one compares whole-text word overlap and the
other reads specific sentencing fields out of the text. Where they agree the
row is settled automatically. Where they disagree the row goes to an
adjudication queue, and that queue is small and is where all the real
judgement lives. The IPC 336 case, 95 per cent similar with a fortyfold fine
increase, is exactly a disagreement row.

Nothing here guesses. A row the pipeline cannot settle is marked for
adjudication, never quietly resolved.

Usage
-----
    python scripts/build_correspondence.py --dry-run --limit 5
    python scripts/build_correspondence.py --out data/correspondence.jsonl
    python scripts/build_correspondence.py --report data/adjudication_queue.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legalrag.materiality import Materiality, assess_materiality
from legalrag.punishment import extract_punishment

LOGGER = logging.getLogger("build_correspondence")

# The statute layer is anonymous and published under CC BY 4.0. Attribution is
# a licence condition. The publisher asks that the HTML not be crawled and the
# structured endpoints be used instead; both requirements are honoured here.
SOURCE_BASE = "https://indiacode.ecourtsindia.com"
ATTRIBUTION = "Statute text and computed cross-code mappings: IndiaCode by eCourtsIndia, CC BY 4.0"

# Similarity bands as published. Confirm the exact thresholds against the
# source before relying on them; they are configurable for that reason.
SIM_NEAR_IDENTICAL = 90
SIM_CLOSE = 70
SIM_DISTANT = 50


class SourceError(RuntimeError):
    """Raised when a source cannot be read."""


@dataclass(slots=True)
class ProvisionPair:
    """One old provision and its candidate successors, as published."""

    old_ref: str
    old_text: str
    best_new_ref: str | None
    best_new_text: str | None
    similarity: float | None
    alternates: list[tuple[str, float]] = field(default_factory=list)
    no_close_match: bool = False


@dataclass(slots=True)
class Row:
    old_ref: str
    new_refs: list[str]
    relationship: str
    similarity: float | None
    materiality: str
    finding: str
    reasons: list[str]
    evidence: list[str]
    confidence: str
    adjudication_cause: str | None
    source: str = ATTRIBUTION

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "old_ref": self.old_ref,
            "new_refs": self.new_refs,
            "relationship": self.relationship,
            "similarity": self.similarity,
            "materiality": self.materiality,
            "finding": self.finding,
            "reasons": self.reasons,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "adjudication_cause": self.adjudication_cause,
            "source": self.source,
        }
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# source access
# ---------------------------------------------------------------------------


def fetch_pair(old_ref: str, *, session: Any, timeout: float) -> ProvisionPair:
    """Fetch one provision pair from the structured endpoints.

    Left as a single seam so the source can be swapped without touching the
    logic below. Confirm the exact response shape against the publisher's API
    documentation before first run and adjust the field names here only.
    """
    raise NotImplementedError(
        "Wire this to the structured statute endpoints. Confirm the JSON field "
        "names against the publisher's API docs first. Do not scrape the HTML: "
        "the publisher asks that the API be used instead."
    )


def load_pairs_from_file(path: Path) -> Iterable[ProvisionPair]:
    """Read pairs from a previously cached JSONL file.

    Fetch once, cache, then iterate offline. Re-fetching a public source on
    every run to debug a regular expression is rude and slow.
    """
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SourceError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            yield ProvisionPair(
                old_ref=raw["old_ref"],
                old_text=raw.get("old_text", ""),
                best_new_ref=raw.get("best_new_ref"),
                best_new_text=raw.get("best_new_text"),
                similarity=raw.get("similarity"),
                alternates=[tuple(a) for a in raw.get("alternates", [])],
                no_close_match=bool(raw.get("no_close_match", False)),
            )


# ---------------------------------------------------------------------------
# derivation
# ---------------------------------------------------------------------------


def derive_relationship(
    pair: ProvisionPair, *, split_margin: float = 15.0
) -> tuple[str, list[str]]:
    """Decide correspondence shape from the published scores alone.

    A split is signalled by an alternate scoring close behind the best match.
    The publisher notes that where a provision was split or merged the answer
    is often more than one of the next-closest entries, which is what this
    reads.
    """
    if pair.no_close_match or pair.best_new_ref is None:
        return "no_successor", []

    refs = [pair.best_new_ref]
    best = pair.similarity if pair.similarity is not None else 0.0

    close_alternates = [ref for ref, score in pair.alternates if best - score <= split_margin]
    if close_alternates:
        refs.extend(close_alternates)
        return "split", refs

    if pair.similarity is None:
        return "unknown", refs
    if pair.similarity >= SIM_NEAR_IDENTICAL:
        return "near_identical", refs
    if pair.similarity >= SIM_CLOSE:
        return "close", refs
    if pair.similarity >= SIM_DISTANT:
        return "distant", refs
    return "weak", refs


def build_row(pair: ProvisionPair, *, split_margin: float) -> Row:
    relationship, refs = derive_relationship(pair, split_margin=split_margin)

    old_p = extract_punishment(pair.old_text)
    new_p = extract_punishment(pair.best_new_text) if pair.best_new_text else None
    verdict = assess_materiality(old_p, new_p)

    evidence = [
        i.evidence.text for i in old_p.imprisonments + (new_p.imprisonments if new_p else [])
    ]
    evidence += [f.evidence.text for f in old_p.fines + (new_p.fines if new_p else [])]

    cause = verdict.review_cause
    confidence = "settled"

    # The disagreement that matters: text says unchanged, sentencing says
    # otherwise. This is the IPC 336 shape and it must never settle silently.
    if relationship == "near_identical" and verdict.materiality is Materiality.MATERIAL:
        cause = "similarity_says_unchanged_but_sentencing_changed"
        confidence = "adjudicate"
    # The mirror case: text diverged but sentencing is identical. Less
    # dangerous, still worth a look, because the elements may have changed
    # even where the sentence did not.
    elif relationship in {"distant", "weak"} and verdict.materiality is Materiality.IMMATERIAL:
        cause = "similarity_says_changed_but_sentencing_identical"
        confidence = "adjudicate"
    elif relationship == "split":
        cause = "split_candidate_needs_confirmation"
        confidence = "adjudicate"
    elif verdict.needs_review:
        confidence = "adjudicate"
    elif verdict.materiality is Materiality.UNDETERMINED:
        confidence = "adjudicate"
        cause = cause or "undetermined"

    finding = "F7" if relationship == "split" else verdict.finding

    return Row(
        old_ref=pair.old_ref,
        new_refs=refs,
        relationship=relationship,
        similarity=pair.similarity,
        materiality=verdict.materiality.value,
        finding=finding,
        reasons=verdict.reasons,
        evidence=evidence[:8],
        confidence=confidence,
        adjudication_cause=cause,
    )


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def summarise(rows: list[Row]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[f"relationship:{row.relationship}"] = (
            counts.get(f"relationship:{row.relationship}", 0) + 1
        )
        counts[f"materiality:{row.materiality}"] = (
            counts.get(f"materiality:{row.materiality}", 0) + 1
        )
        counts[f"confidence:{row.confidence}"] = counts.get(f"confidence:{row.confidence}", 0) + 1
        if row.adjudication_cause:
            key = f"cause:{row.adjudication_cause}"
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--cache", type=Path, help="JSONL of previously fetched pairs")
    p.add_argument("--out", type=Path, default=Path("data/correspondence.jsonl"))
    p.add_argument("--queue", type=Path, default=Path("data/adjudication_queue.jsonl"))
    p.add_argument(
        "--split-margin",
        type=float,
        default=15.0,
        help="alternate within this many points of the best match signals a split",
    )
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    if not args.cache:
        LOGGER.error("no --cache supplied and live fetching is not wired yet; see fetch_pair()")
        return 2
    if not args.cache.is_file():
        LOGGER.error("cache not found: %s", args.cache)
        return 2

    started = time.time()
    rows: list[Row] = []
    for i, pair in enumerate(load_pairs_from_file(args.cache)):
        if args.limit is not None and i >= args.limit:
            break
        rows.append(build_row(pair, split_margin=args.split_margin))

    queue = [r for r in rows if r.confidence == "adjudicate"]

    LOGGER.info("processed %d provisions in %.1fs", len(rows), time.time() - started)
    for key, count in summarise(rows).items():
        LOGGER.info("  %-58s %d", key, count)
    LOGGER.info(
        "adjudication queue: %d of %d (%.1f%%)",
        len(queue),
        len(rows),
        100.0 * len(queue) / max(len(rows), 1),
    )

    if args.dry_run:
        LOGGER.info("dry run, nothing written")
        return 0

    for path, subset in ((args.out, rows), (args.queue, queue)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(r.to_json() for r in subset) + "\n", encoding="utf-8")
        LOGGER.info("wrote %d rows to %s", len(subset), path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
