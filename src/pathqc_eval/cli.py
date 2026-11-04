"""Command-line entry point: `pathqc-eval <command>`."""

from __future__ import annotations

import argparse
from pathlib import Path

from pathqc_eval.taxonomy import load_taxonomy
from pathqc_eval.validate import validate_reports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pathqc-eval", description="pathology-oversight-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate every report file in a folder")
    validate.add_argument("path", nargs="?", type=Path, default=Path("data/reports"))
    validate.add_argument("--expect", type=int, help="required total number of reports")
    validate.add_argument("--expect-clean", type=int, help="required number of clean controls")
    validate.add_argument("--expect-dev", type=int, help="required number of dev reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        result = validate_reports(
            args.path,
            load_taxonomy(),
            expect=args.expect,
            expect_clean=args.expect_clean,
            expect_dev=args.expect_dev,
        )
        for failure in result.failures:
            print(f"FAIL {failure}")
        print(result.summary)
        return 0 if result.ok else 1
    return 2
