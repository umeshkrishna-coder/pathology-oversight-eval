"""Command-line entry point: `pathqc-eval <command>`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues
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

    render = sub.add_parser(
        "render", help="rewrite the CBC Values text from the stored cbc_values (no recalculation)"
    )
    render.add_argument("path", type=Path, help="a report file or a folder of report files")
    return parser


def _render(path: Path) -> int:
    """Re-render Values text for every cbc report; no validation, so drafts work too."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    failed = False
    for file in files:
        try:
            data = read_report_json(file)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL {file}: does not parse as JSON ({exc})")
            failed = True
            continue
        if not isinstance(data, dict) or data.get("modality") != "cbc":
            continue
        if not data.get("cbc_values"):
            print(f"FAIL {file}: lacks cbc_values")
            failed = True
            continue
        try:
            text = render_cbc_values(CBCValues.model_validate(data["cbc_values"]))
        except ValidationError as exc:
            print(f"FAIL {file}: cbc_values cannot be rendered ({exc.error_count()} problem(s))")
            failed = True
            continue
        sections = data.get("sections")
        if not isinstance(sections, dict):
            sections = {}
        if sections.get("Values") == text:
            print(f"unchanged {file}")
            continue
        if "Values" in sections:
            sections["Values"] = text
        else:
            sections = {"Values": text, **sections}
        data["sections"] = sections
        write_report_json(file, data)
        print(f"rendered {file}")
    return 1 if failed else 0


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
    if args.command == "render":
        return _render(args.path)
    return 2
