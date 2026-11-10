"""Command-line entry point: `pathqc-eval <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from pathqc_eval.cbc import load_reference_ranges
from pathqc_eval.draft import (
    DEFAULT_DRAFTS_DIR,
    AnthropicDraftClient,
    MissingAPIKeyError,
    dry_run_lines,
    run_drafts,
)
from pathqc_eval.freeze import check_lock, freeze
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues
from pathqc_eval.spec import DEFAULT_SPEC_PATH, DatasetSpec, load_spec, spec_summary
from pathqc_eval.taxonomy import REPO_ROOT, load_taxonomy
from pathqc_eval.validate import validate_reports

# Replaced in tests to prove the real client is never constructed.
CLIENT_FACTORY = AnthropicDraftClient
# Replaced in tests with a temporary fixture tree.
FREEZE_ROOT = REPO_ROOT
# Replaced in tests with a temporary spec, so tests never depend on the owner's approvals.
SPEC_PATH = DEFAULT_SPEC_PATH


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pathqc-eval", description="pathology-oversight-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate every report file in a folder")
    validate.add_argument(
        "path", nargs="?", type=Path, help="folder (default data/reports, or data/drafts)"
    )
    validate.add_argument("--drafts", action="store_true", help="drafts mode (errors may be [])")
    validate.add_argument("--expect", type=int, help="required total number of reports")
    validate.add_argument("--expect-clean", type=int, help="required number of clean controls")
    validate.add_argument("--expect-dev", type=int, help="required number of dev reports")

    render = sub.add_parser(
        "render", help="rewrite the CBC Values text from the stored cbc_values (no recalculation)"
    )
    render.add_argument("path", type=Path, help="a report file or a folder of report files")

    spec_check = sub.add_parser("spec-check", help="validate the dataset spec and print counts")
    spec_check.add_argument("path", nargs="?", type=Path, default=DEFAULT_SPEC_PATH)

    draft = sub.add_parser("draft", help="draft approved spec rows with claude-haiku-5-5")
    draft.add_argument("--ids", help="comma-separated row ids, e.g. H-001,C-003")
    draft.add_argument("--dry-run", action="store_true", help="print prompts and estimate only")
    draft.add_argument("--force", action="store_true", help="redraft rows that already exist")
    draft.add_argument("--cost-gate", type=float, default=0.25, help="USD cap per run")

    freeze_cmd = sub.add_parser(
        "freeze", help="hash taxonomy, prompts and dataset into data/prompts.lock.json"
    )
    mode = freeze_cmd.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify every hash against the lock")
    mode.add_argument("--replace", action="store_true", help="overwrite an existing lock")
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


def _spec_check(path: Path) -> int:
    taxonomy = load_taxonomy()
    try:
        raw = read_report_json(path)
        spec = DatasetSpec.model_validate(raw, context={"taxonomy": taxonomy})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {path}: cannot read spec ({exc})")
        return 1
    except ValidationError as exc:
        rows = raw.get("reports", []) if isinstance(raw, dict) else []
        for err in exc.errors():
            loc = list(err["loc"])
            where = "spec"
            if len(loc) >= 2 and loc[0] == "reports" and isinstance(loc[1], int):
                row = rows[loc[1]] if loc[1] < len(rows) else {}
                where = row.get("id", f"reports[{loc[1]}]") if isinstance(row, dict) else where
                if loc[2:]:
                    where += "." + ".".join(str(p) for p in loc[2:])
            for reason in err["msg"].removeprefix("Value error, ").split("; "):
                print(f"FAIL {where}: {reason}")
        return 1
    for line in spec_summary(spec, taxonomy):
        print(line)
    print("OK")
    return 0


def _draft(args: argparse.Namespace) -> int:
    spec = load_spec(SPEC_PATH)
    rows = spec.reports
    if args.ids:
        wanted = [i.strip() for i in args.ids.split(",") if i.strip()]
        known = {r.id for r in rows}
        unknown = [i for i in wanted if i not in known]
        if unknown:
            print(f"FAIL unknown ids: {', '.join(unknown)}")
            return 1
        rows = [spec.row(i) for i in wanted]
    if args.dry_run:
        for line in dry_run_lines(rows):
            print(line)
        return 0
    unapproved = [r.id for r in rows if r.brief_status != "approved"]
    if unapproved:
        print(f"FAIL draft refused: {len(unapproved)} row(s) not approved:")
        for row_id in unapproved:
            print(f"  {row_id}")
        return 1
    try:
        client = CLIENT_FACTORY()
    except MissingAPIKeyError as exc:
        print(f"FAIL {exc}")
        return 1
    summary = run_drafts(
        rows,
        client,
        drafts_dir=DEFAULT_DRAFTS_DIR,
        ranges=load_reference_ranges(),
        today=date.today(),
        cost_gate=args.cost_gate,
        force=args.force,
    )
    return 1 if summary.failed or summary.stopped_before else 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        path = args.path or Path("data/drafts" if args.drafts else "data/reports")
        result = validate_reports(
            path,
            load_taxonomy(),
            expect=args.expect,
            expect_clean=args.expect_clean,
            expect_dev=args.expect_dev,
            drafts=args.drafts,
        )
        for failure in result.failures:
            print(f"FAIL {failure}")
        print(result.summary)
        return 0 if result.ok else 1
    if args.command == "render":
        return _render(args.path)
    if args.command == "spec-check":
        return _spec_check(args.path)
    if args.command == "draft":
        return _draft(args)
    if args.command == "freeze":
        outcome = check_lock(FREEZE_ROOT) if args.check else freeze(FREEZE_ROOT, args.replace)
        for line in outcome.lines:
            print(line)
        return 0 if outcome.ok else 1
    return 2
