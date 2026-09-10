"""Run the evaluation and gate a release on it.

Thin on purpose. All the logic lives in legalrag.evals; this file only wires
a golden set to a system under test, writes the report, and decides the exit
code. Exit 1 means a regression and is intended to fail CI.

    python scripts/run_eval.py --golden data/golden.jsonl --system mypkg:build_system
    python scripts/run_eval.py --golden data/golden.jsonl --system mypkg:build_system \
        --baseline data/baseline.json --report out/report.json
    python scripts/run_eval.py ... --update-baseline
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from legalrag.evals import SystemOutput, compare_to_baseline, load_golden, run_eval

LOGGER = logging.getLogger("run_eval")


def load_system(spec: str) -> Callable[[str], SystemOutput]:
    """Import a factory given as ``package.module:factory``.

    The factory takes no arguments and returns a callable that maps a question
    to a SystemOutput. Keeping construction behind a factory means model
    versions and configuration are captured by the system itself rather than
    smuggled in through this script.
    """
    if ":" not in spec:
        raise ValueError(f"--system must be 'module:factory', got {spec!r}")
    module_name, factory_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    return factory()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--system", required=True, help="module:factory")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="write this run as the new baseline; use only on a deliberate accepted change",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s | %(message)s",
    )

    golden = load_golden(args.golden)
    system = load_system(args.system)
    report = run_eval(golden, system)

    print(report.render())

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict() | {"golden_set": str(args.golden), "system": args.system}
        args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("report written to %s", args.report)

    if args.update_baseline:
        if not args.baseline:
            LOGGER.error("--update-baseline needs --baseline")
            return 2
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        LOGGER.info("baseline updated: %s", args.baseline)
        return 0

    if not args.baseline:
        LOGGER.warning("no baseline given, nothing gated")
        return 0
    if not args.baseline.is_file():
        LOGGER.warning("baseline %s not found, nothing gated", args.baseline)
        return 0

    passed, messages = compare_to_baseline(
        report, json.loads(args.baseline.read_text(encoding="utf-8"))
    )
    print()
    for message in messages:
        print(f"  {message}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
