"""Fetch the legal corpus described in data/sources.yaml.

Design notes
------------
* Metadata before payload. The eCourts S3 buckets ship parquet metadata
  alongside the PDFs. We read the parquet, filter to the slice we actually
  want, and only then pull documents. Pulling PDFs first is how people end
  up with 400 GB and no plan.
* Resumable. Every completed source writes a marker into ``_state/``.
  Re-running skips finished work. Kaggle sessions die; plan for it.
* No credentials. The S3 buckets are public (``--no-sign-request``).
  HuggingFace repos here are public too.
* Failures are loud. No bare ``except``. A source that fails is recorded
  and the run continues, but the exit code is non-zero.

Usage
-----
    python scripts/fetch_corpus.py --tier oracle --tier core --dry-run
    python scripts/fetch_corpus.py --tier core --out data/raw
    python scripts/fetch_corpus.py --only in_sc_judgments --limit 2000
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LOGGER = logging.getLogger("fetch_corpus")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "data" / "sources.yaml"
DEFAULT_OUT = REPO_ROOT / "data" / "raw"


class FetchError(RuntimeError):
    """Raised when a source cannot be retrieved."""


@dataclass(frozen=True, slots=True)
class Source:
    """One entry from the manifest."""

    id: str
    tier: str
    name: str
    fetch: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        missing = {"id", "tier", "name", "fetch"} - data.keys()
        if missing:
            raise ValueError(f"manifest entry missing keys {sorted(missing)}: {data!r}")
        return cls(
            id=data["id"],
            tier=data["tier"],
            name=data["name"],
            fetch=data["fetch"],
            raw=data,
        )


@dataclass(slots=True)
class FetchResult:
    source_id: str
    ok: bool
    detail: str


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------


def load_manifest(path: Path) -> list[Source]:
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = payload.get("sources")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: 'sources' must be a list")
    return [Source.from_dict(entry) for entry in entries]


def select(
    sources: Iterable[Source],
    tiers: set[str] | None,
    only: set[str] | None,
) -> list[Source]:
    chosen = list(sources)
    if only:
        unknown = only - {s.id for s in chosen}
        if unknown:
            raise ValueError(f"unknown source id(s): {sorted(unknown)}")
        chosen = [s for s in chosen if s.id in only]
    if tiers:
        chosen = [s for s in chosen if s.tier in tiers]
    return chosen


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------


def marker_path(out_dir: Path, source_id: str) -> Path:
    return out_dir / "_state" / f"{source_id}.done.json"


def already_done(out_dir: Path, source_id: str) -> bool:
    return marker_path(out_dir, source_id).is_file()


def mark_done(out_dir: Path, source_id: str, detail: str) -> None:
    path = marker_path(out_dir, source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source_id": source_id, "detail": detail}), encoding="utf-8")


# --------------------------------------------------------------------------
# fetchers
# --------------------------------------------------------------------------


def _require(binary: str) -> str:
    resolved = shutil.which(binary)
    if resolved is None:
        raise FetchError(f"required binary not on PATH: {binary}")
    return resolved


def _run(cmd: list[str], *, dry_run: bool) -> None:
    LOGGER.info("$ %s", " ".join(cmd))
    if dry_run:
        return
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise FetchError(f"command failed ({completed.returncode}): {' '.join(cmd)}")


def fetch_s3(source: Source, out_dir: Path, *, dry_run: bool, limit: int | None) -> str:
    """Sync a public S3 open-data bucket. Metadata first, always."""
    bucket = source.raw["bucket"]
    region = source.raw.get("region", "ap-south-1")
    dest = out_dir / source.id
    dest.mkdir(parents=True, exist_ok=True)

    aws = _require("aws")

    # Step 1: structured metadata only. Small, and it drives every later filter.
    _run(
        [
            aws,
            "s3",
            "sync",
            f"s3://{bucket}/metadata/",
            str(dest / "metadata"),
            "--no-sign-request",
            "--region",
            region,
            "--exclude",
            "*",
            "--include",
            "*.parquet",
        ],
        dry_run=dry_run,
    )

    if limit == 0:
        return "metadata only (limit=0)"

    # Step 2: document payload. Deliberately NOT a full sync by default -
    # filter with scripts/filter_judgments.py against the parquet, then
    # re-run this with an explicit prefix.
    prefix = source.raw.get("prefix", "data/")
    cmd = [
        aws,
        "s3",
        "sync",
        f"s3://{bucket}/{prefix}",
        str(dest / "documents"),
        "--no-sign-request",
        "--region",
        region,
    ]
    if limit is not None:
        LOGGER.warning(
            "S3 sync has no native row limit; pulling prefix %r in full. "
            "Filter via parquet metadata for a bounded pull.",
            prefix,
        )
    _run(cmd, dry_run=dry_run)
    return f"synced s3://{bucket}/{prefix}"


def fetch_hf(source: Source, out_dir: Path, *, dry_run: bool, limit: int | None) -> str:
    """Snapshot a HuggingFace dataset repo."""
    repo = source.raw["repo"]
    dest = out_dir / source.id
    LOGGER.info("huggingface snapshot %s -> %s", repo, dest)
    if dry_run:
        return f"would snapshot {repo}"

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise FetchError("huggingface_hub not installed: pip install huggingface_hub") from exc

    snapshot_download(
        repo_id=repo,
        repo_type="dataset",
        local_dir=str(dest),
        max_workers=4,
    )
    return f"snapshotted {repo}"


def fetch_git(source: Source, out_dir: Path, *, dry_run: bool, limit: int | None) -> str:
    url = source.raw["url"]
    dest = out_dir / source.id
    if dest.exists() and not dry_run:
        return f"already cloned at {dest}"
    git = _require("git")
    _run([git, "clone", "--depth", "1", url, str(dest)], dry_run=dry_run)
    return f"cloned {url}"


def fetch_manual(source: Source, out_dir: Path, *, dry_run: bool, limit: int | None) -> str:
    """Sources that require a human. Emit an instruction stub, do not fake it."""
    dest = out_dir / source.id
    dest.mkdir(parents=True, exist_ok=True)
    readme = dest / "FETCH_ME.md"
    body = [
        f"# {source.name}",
        "",
        f"- id: `{source.id}`",
        f"- fetch mode: `{source.fetch}` (manual)",
    ]
    if url := source.raw.get("url"):
        body.append(f"- url: {url}")
    if lic := source.raw.get("license"):
        body.append(f"- license: {lic}")
    if notes := source.raw.get("notes"):
        body += ["", "## Notes", "", notes.strip()]
    body += ["", f"Place the downloaded file(s) in `{dest}` and re-run."]
    if not dry_run:
        readme.write_text("\n".join(body) + "\n", encoding="utf-8")
    return f"manual step required; see {readme}"


FETCHERS = {
    "s3": fetch_s3,
    "hf": fetch_hf,
    "git": fetch_git,
    "manual_pdf": fetch_manual,
    "manual_csv": fetch_manual,
}


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def fetch_one(
    source: Source, out_dir: Path, *, dry_run: bool, limit: int | None, force: bool
) -> FetchResult:
    if already_done(out_dir, source.id) and not force:
        LOGGER.info("[skip] %s already fetched", source.id)
        return FetchResult(source.id, True, "skipped (already done)")

    fetcher = FETCHERS.get(source.fetch)
    if fetcher is None:
        return FetchResult(source.id, False, f"unknown fetch mode {source.fetch!r}")

    LOGGER.info("[%s] %s", source.id, source.name)
    try:
        detail = fetcher(source, out_dir, dry_run=dry_run, limit=limit)
    except (FetchError, OSError, KeyError) as exc:
        LOGGER.error("[%s] FAILED: %s", source.id, exc)
        return FetchResult(source.id, False, str(exc))

    if not dry_run and not source.fetch.startswith("manual_"):
        mark_done(out_dir, source.id, detail)
    return FetchResult(source.id, True, detail)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--tier",
        action="append",
        dest="tiers",
        default=None,
        help="repeatable: oracle | core | benchmark | pretrain",
    )
    parser.add_argument(
        "--only", action="append", dest="only", default=None, help="repeatable source id"
    )
    parser.add_argument("--limit", type=int, default=None, help="0 = metadata only for S3 sources")
    parser.add_argument("--force", action="store_true", help="ignore completion markers")
    parser.add_argument("--dry-run", action="store_true", help="print actions, change nothing")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    sources = load_manifest(args.manifest)
    selected = select(
        sources,
        tiers=set(args.tiers) if args.tiers else None,
        only=set(args.only) if args.only else None,
    )
    if not selected:
        LOGGER.error("no sources selected")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    results = [
        fetch_one(s, args.out, dry_run=args.dry_run, limit=args.limit, force=args.force)
        for s in selected
    ]

    failed = [r for r in results if not r.ok]
    LOGGER.info("--- %d ok, %d failed ---", len(results) - len(failed), len(failed))
    for r in failed:
        LOGGER.error("  %s: %s", r.source_id, r.detail)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
