"""Command-line entry point: `pathqc-eval <command>`."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from pathqc_eval import adjudication
from pathqc_eval.cbc import load_reference_ranges
from pathqc_eval.cost import cost_usd
from pathqc_eval.draft import (
    DEFAULT_DRAFTS_DIR,
    AnthropicDraftClient,
    MissingAPIKeyError,
    dry_run_lines,
    run_drafts,
)
from pathqc_eval.freeze import check_lock, freeze
from pathqc_eval.harness import (
    EVAL_MAX_TOKENS,
    EVAL_MODEL,
    RUNS_DIR,
    WRAPPING_TOKENS,
    AnthropicEvalClient,
    CallsFileError,
    RunInUse,
    build_run_messages,
    default_run_id,
    eval_request_args,
    read_attempts,
    run_hashes,
    run_is_busy,
    run_lock,
    run_units,
    select_reports,
    usd,
    valid_run_id,
)
from pathqc_eval.harness import dry_run_lines as run_dry_run_lines
from pathqc_eval.io import read_report_json, unique_keys, write_report_json
from pathqc_eval.plant import (
    REPORTS_DIR,
    SHEET_FILE,
    check_lines,
    plan,
    template,
    write_outputs,
)
from pathqc_eval.readable import write_readable
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues, Report, RunConfig, SmokeConfig
from pathqc_eval.score_output import map_list, run_score
from pathqc_eval.scoring import classify_runs, load_inputs, review_findings
from pathqc_eval.spec import DEFAULT_SPEC_PATH, DatasetSpec, load_spec, spec_summary
from pathqc_eval.taxonomy import REPO_ROOT, load_taxonomy
from pathqc_eval.validate import validate_reports

# Replaced in tests to prove the real client is never constructed.
CLIENT_FACTORY = AnthropicDraftClient
# Replaced in tests with a temporary fixture tree.
FREEZE_ROOT = REPO_ROOT
# Replaced in tests with a temporary spec, so tests never depend on the owner's approvals.
SPEC_PATH = DEFAULT_SPEC_PATH
# Replaced in tests with a temporary tree (spec, taxonomy, drafts, sheet, reports).
PLANT_ROOT = REPO_ROOT


def _utc_now() -> datetime:
    return datetime.now(UTC)


# `run` (EVAL-04). Replaced in tests: a temporary tree, a fake client factory (the real client is
# never constructed in a test), a fixed clock and no waiting between transport retries.
RUN_ROOT = REPO_ROOT
EVAL_CLIENT_FACTORY = AnthropicEvalClient
RUN_CLOCK = _utc_now
RUN_SLEEP = time.sleep


def _scorer_commit() -> str:
    """The git commit of the scorer's code, with "-dirty" when src/ has uncommitted
    changes, or "unknown"."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "src"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if head.returncode != 0 or dirty.returncode != 0:
        return "unknown"
    return head.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


# `map-list`, `adjudicate` and `score` (EVAL-05). Replaced in tests: a temporary tree, a
# clock, and a fixed scorer commit.
SCORE_ROOT = REPO_ROOT
SCORE_CLOCK = _utc_now
SCORER_COMMIT = _scorer_commit


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
    draft.add_argument("--cost-gate", type=float, default=0.50, help="USD cap per run")

    freeze_cmd = sub.add_parser(
        "freeze", help="hash taxonomy, prompts and dataset into data/prompts.lock.json"
    )
    mode = freeze_cmd.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify every hash against the lock")
    mode.add_argument("--replace", action="store_true", help="overwrite an existing lock")

    readable = sub.add_parser(
        "readable", help="write <folder>/_readable/<id>.md for each report JSON in a folder"
    )
    readable.add_argument("path", type=Path, help="folder of report files, e.g. data/drafts")

    plant = sub.add_parser(
        "plant", help="apply data/specs/planting.md to the drafts and write data/reports/"
    )
    plant_mode = plant.add_mutually_exclusive_group()
    plant_mode.add_argument("--init", action="store_true", help="write the empty template sheet")
    plant_mode.add_argument(
        "--check", action="store_true", help="parse and apply in memory; write nothing"
    )

    run = sub.add_parser(
        "run", help="run the evaluated model over one dataset in one condition (EVAL-04)"
    )
    run.add_argument("--dataset", required=True, choices=["dev", "scored"])
    run.add_argument("--condition", required=True, choices=["plain", "structured"])
    run.add_argument(
        "--cost-gate", type=float, help="USD limit for the whole run; required for a real run"
    )
    run.add_argument("--run-id", help="default: <YYYYMMDD-HHMMSS>-<dataset>-<condition> (UTC)")
    run.add_argument("--workers", type=int, default=4, help="calls in parallel (default 4)")
    run.add_argument("--max-calls", type=int, help="stop cleanly after this many attempts")
    run.add_argument(
        "--dry-run", action="store_true", help="print the messages and an estimate; no client"
    )

    smoke_text = (
        "live smoke test (EVAL-04b): dev drafts, plain condition, one unit each, at most two "
        "calls per report; 8 calls and $1.00 for every smoke run together; not evaluation data"
    )
    smoke = sub.add_parser("smoke", help=smoke_text, description=smoke_text)
    smoke.add_argument("--ids", required=True, help="comma-separated dev draft ids")
    smoke.add_argument("--cost-gate", type=float, help="USD limit; required")
    smoke.add_argument("--condition", default="plain", help="plain only (structured is refused)")

    two_runs = {"nargs": 2, "required": True, "metavar": ("PLAIN_RUN_ID", "STRUCTURED_RUN_ID")}
    map_cmd = sub.add_parser(
        "map-list", help="list the runs' distinct categories and whether each is mapped"
    )
    map_cmd.add_argument("--runs", nargs="+", required=True, metavar="RUN_ID")
    adjudicate = sub.add_parser("adjudicate", help="blind adjudication of review findings")
    action = adjudicate.add_subparsers(dest="action", required=True)
    prepare = action.add_parser("prepare", help="write the items, the hidden map and the sheet")
    prepare.add_argument("--dataset", required=True, choices=["dev", "scored"])
    prepare.add_argument("--runs", **two_runs)
    prepare.add_argument(
        "--replace", action="store_true", help="start again (only while no verdict is entered)"
    )
    for name, text in (
        ("apply", "read the sheet's verdicts into adjudication.json"),
        ("status", "how many verdicts are filled"),
    ):
        action.add_parser(name, help=text).add_argument(
            "--dataset", required=True, choices=["dev", "scored"]
        )
    score = sub.add_parser("score", help="score a plain and a structured run of one dataset")
    score.add_argument("--dataset", required=True, choices=["dev", "scored"])
    score.add_argument("--runs", **two_runs)
    score.add_argument(
        "--provisional",
        action="store_true",
        help="score before the adjudication is complete; affected numbers become ranges",
    )
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


def _plant(args: argparse.Namespace) -> int:
    root = PLANT_ROOT
    taxonomy = load_taxonomy(root / "data" / "taxonomy.json")
    spec = load_spec(root / "data" / "specs" / "dataset.json", taxonomy)
    sheet = root / SHEET_FILE
    if args.init:
        if sheet.exists():
            print(f"plant --init refused: {SHEET_FILE.as_posix()} already exists")
            return 1
        sheet.write_text(template(spec.reports), encoding="utf-8", newline="\n")
        print(f"wrote {SHEET_FILE.as_posix()} | {len(spec.reports)} blocks, all verified: no")
        return 0
    if not sheet.is_file():
        print(f"FAIL {SHEET_FILE.as_posix()} not found; run: uv run pathqc-eval plant --init")
        return 1
    if not args.check and taxonomy.status != "final":
        print(
            f"plant refused: taxonomy status is '{taxonomy.status}', not 'final' "
            "(plant --check works with a draft taxonomy)"
        )
        return 1
    try:
        sheet_text = sheet.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        not_utf8 = f"{exc.reason} at byte {exc.start}"
    else:
        # UTF-16 text without a byte-order mark decodes as UTF-8 with NUL characters.
        not_utf8 = "it contains NUL characters, as UTF-16 text does" if "\0" in sheet_text else ""
    if not_utf8:
        print(
            f"FAIL {SHEET_FILE.as_posix()} is not UTF-8 text ({not_utf8}); "
            "save it as UTF-8 and run the command again"
        )
        return 1
    run = plan(spec.reports, sheet_text, root, taxonomy)
    ok_count = sum(r.ok for r in run.results)
    if args.check:
        for line in check_lines(run):
            print(line)
        print("notices:" if run.notices else "notices: none")
        for notice in run.notices:
            print(f"  {notice}")
        print(
            f"plant --check: {ok_count} OK, {len(run.results) - ok_count} with problems, "
            f"{len(run.problems)} sheet problem(s); nothing written"
        )
        return 0 if run.ok else 1
    lines, not_written = write_outputs(run, root)
    for line in lines:
        print(line)
    result = validate_reports(root / REPORTS_DIR, taxonomy)
    print(result.summary)
    print("planted error types (scored / dev / total):")
    scored = Counter(e.type for r in result.reports if r.split == "scored" for e in r.errors)
    dev = Counter(e.type for r in result.reports if r.split == "dev" for e in r.errors)
    for tid in taxonomy.type_ids():
        print(f"  {tid:<3} {scored[tid]:>2} / {dev[tid]:>2} / {scored[tid] + dev[tid]:>2}")
    s_total, d_total = sum(scored.values()), sum(dev.values())
    print(f"  all {s_total:>2} / {d_total:>2} / {s_total + d_total:>2}")
    print("notices:" if run.notices else "notices: none")
    for notice in run.notices:
        print(f"  {notice}")
    verified = sum(r.provenance.verified for r in result.reports)
    print(f"verified: {verified} of {len(result.reports)} reports in {REPORTS_DIR.as_posix()}")
    if not_written:
        print(f"NOT WRITTEN: {', '.join(not_written)} (see above)")
    return 0 if run.ok and not not_written else 1


def _refuse(problems: list[str], what: str = "run") -> int:
    print(f"{what} refused:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


def _print_refusal(lines: list[str]) -> int:
    for line in lines:
        print(line)
    return 1


def _resume_check(run_dir: Path, run_id: str, config: RunConfig, condition: str) -> list[str]:
    """The lines to refuse a start or a resume with, or [] when the run may go on: the
    config must be identical apart from created_at, calls.jsonl needs a config.json, and
    every line of calls.jsonl must be a call line of this run."""
    config_path = run_dir / "config.json"
    refused = "run refused:"
    if config_path.is_file():
        try:
            existing = RunConfig.model_validate(read_report_json(config_path))
        except (OSError, ValueError) as exc:
            return [refused, f"  - runs/{run_id}/config.json cannot be read ({str(exc)[:200]})"]
        changed = [
            name
            for name in RunConfig.model_fields
            if name != "created_at" and getattr(existing, name) != getattr(config, name)
        ]
        if changed:
            return [
                refused,
                f"  - runs/{run_id} exists with a different config ({', '.join(changed)}); "
                "resuming needs the identical config, or start a new --run-id",
            ]
    elif (run_dir / "calls.jsonl").exists():
        return [
            refused,
            f"  - runs/{run_id} holds calls.jsonl but no config.json, so it cannot be resumed "
            "safely; start a new --run-id",
        ]
    try:
        read_attempts(run_dir / "calls.jsonl", run_id, condition)  # every line must be this run's
    except CallsFileError as exc:
        return [f"FAIL {exc}"]
    return []


def _run(args: argparse.Namespace) -> int:
    """`pathqc-eval run`: checks, isolation, then the units (or the dry run)."""
    root = RUN_ROOT
    if args.workers < 1:
        return _refuse(["--workers must be 1 or more"])
    if args.max_calls is not None and args.max_calls < 1:
        return _refuse(["--max-calls must be 1 or more"])
    if args.run_id is not None and not valid_run_id(args.run_id):
        return _refuse(
            [
                "--run-id must be letters, digits, '.', '_' or '-' (at most 100 characters, "
                "starting with a letter or digit, not ending in '.', and not a Windows device "
                "name such as NUL or COM1)"
            ]
        )
    try:
        taxonomy = load_taxonomy(root / "data" / "taxonomy.json")
    except (OSError, ValueError) as exc:
        return _refuse([f"data/taxonomy.json cannot be loaded ({exc})"])
    selection = select_reports(root, args.dataset, args.condition, taxonomy)
    if selection.problems:
        return _refuse(selection.problems)
    messages, breaches = build_run_messages(
        selection.reports, args.condition, taxonomy, root / "prompts"
    )
    if breaches:
        return _refuse([f"isolation: {breach}" for breach in breaches])
    if args.dry_run:
        for line in run_dry_run_lines(args.dataset, args.condition, selection.reports, messages):
            print(line)
        return 0
    gate = args.cost_gate
    if gate is None:
        return _refuse(["--cost-gate is required for a real run (there is no default)"])
    if not math.isfinite(gate) or gate <= 0:
        return _refuse(["--cost-gate must be a positive number of US dollars"])
    now = RUN_CLOCK()
    run_id = args.run_id or default_run_id(now, args.dataset, args.condition)
    config = RunConfig(
        run_id=run_id,
        dataset=args.dataset,
        condition=args.condition,
        model=EVAL_MODEL,
        max_tokens=EVAL_MAX_TOKENS,
        created_at=now,
        cost_gate_usd=gate,
        sdk_version=package_version("anthropic"),
        **run_hashes(root, args.dataset, args.condition),
    )
    run_dir = root / RUNS_DIR / run_id
    config_path = run_dir / "config.json"
    busy = [
        f"runs/{run_id} is being run by another invocation; wait for it to finish, or use "
        "another --run-id"
    ]
    if run_dir.is_dir():  # before its files are read
        try:
            if run_is_busy(run_dir):
                return _refuse(busy)
        except OSError as exc:  # the lock file is a folder, or cannot be opened
            return _refuse(
                [
                    f"runs/{run_id}/.run.lock cannot be used ({exc}); remove or repair it, or "
                    "use another --run-id"
                ]
            )
    lines = _resume_check(run_dir, run_id, config, args.condition)
    if lines:
        return _print_refusal(lines)
    try:
        client = EVAL_CLIENT_FACTORY()
    except MissingAPIKeyError as exc:
        print(f"FAIL {exc}")
        return 1
    try:
        with run_lock(run_dir):  # a second invocation on this run id refuses
            # Again under the lock: another invocation may have created the run meanwhile.
            lines = _resume_check(run_dir, run_id, config, args.condition)
            if lines:
                return _print_refusal(lines)
            if not config_path.is_file():
                write_report_json(config_path, config.model_dump(mode="json"))
            print(
                f"run {run_id}: {len(selection.reports)} reports x 3 repeats, {args.dataset}, "
                f"{args.condition}, gate {usd(gate)}"
            )
            outcome = run_units(
                run_dir=run_dir,
                run_id=run_id,
                dataset=args.dataset,
                condition=args.condition,
                model=EVAL_MODEL,
                messages=messages,
                client=client,
                cost_gate=gate,
                workers=args.workers,
                max_calls=args.max_calls,
                clock=RUN_CLOCK,
                sleep=RUN_SLEEP,
            )
    except RunInUse:
        return _refuse(busy)
    except CallsFileError as exc:
        print(f"FAIL {exc}")
        return 1
    except KeyboardInterrupt as exc:
        rebuilt = getattr(exc, "results_written", False)
        print(
            f"interrupted: the calls made are in runs/{run_id}/calls.jsonl; results.json "
            + ("was rebuilt" if rebuilt else "was not rebuilt (the next invocation rebuilds it)")
            + f"; resume with --run-id {run_id}"
        )
        return 130
    except OSError as exc:
        print(f"FAIL the run's files could not be written ({exc}); resume with --run-id {run_id}")
        return 1
    if outcome.failure is not None:
        return 1
    stopped_cleanly = (outcome.stopped or "").startswith("--max-calls")
    return 0 if outcome.complete or stopped_cleanly else 1


SMOKE_MAX_CALLS = 8  # section B, for the whole stage
SMOKE_HARD_STOP_USD = 1.00  # section B, for the whole stage
SMOKE_WRAPPING_TOKENS = WRAPPING_TOKENS  # room for the message wrapping (100 tokens)
SMOKE_STAGE_DIR = "_smoke_stage"  # runs/_smoke_stage/.run.lock: one smoke run at a time


def _earlier_smoke_spend(root: Path) -> tuple[int, float, str]:
    """Calls made and dollars spent by every earlier smoke run (each line of a calls.jsonl is
    one request: an attempt, a transport failure or a refused call), or why they cannot be
    read."""
    calls, spent = 0, 0.0
    for path in sorted((root / RUNS_DIR).glob("smoke-*/calls.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").split("\n"):
                if line.strip():
                    calls += 1
                    cost = json.loads(line).get("cost_usd", 0.0)
                    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
                        raise ValueError(f"cost_usd {cost!r} is not a number")
                    if not math.isfinite(cost) or cost < 0:
                        raise ValueError(f"cost_usd {cost!r} is not a finite amount of 0 or more")
                    spent += cost
        except (OSError, ValueError, AttributeError, TypeError, OverflowError) as exc:
            rel = path.relative_to(root).as_posix()
            return 0, 0.0, f"{rel} cannot be read to count earlier calls ({str(exc)[:200]})"
    return calls, spent, ""


def _smoke(args: argparse.Namespace) -> int:
    """`pathqc-eval smoke` (EVAL-04b): the first live contact between the harness and the API.

    Dev drafts from data/drafts/ are read as reports in memory (nothing is written under
    data/); plain condition only; one unit per report; the same client, request arguments,
    isolation check and parsing as `run`. Section B limits the whole stage, over every
    invocation, to 8 calls and $1.00, so the retry rule and the gate are stricter than `run`'s:
    a transport failure is not retried (a retry would be another call); at most two calls are
    made per report (one call and one retry after an unreadable answer); the calls and spend
    of every earlier smoke run count against the 8 calls and the $1.00; and every call is
    assumed to cost its ceiling before it starts (input no larger than the texts' UTF-8 bytes
    plus 100 tokens of wrapping, output the whole max_tokens), one call at a time, so the total
    cannot pass the gate. ANTHROPIC_INFERENCE_GEO must be unset (checked by name). Writes
    runs/smoke-<UTC timestamp>/config.json, calls.jsonl and results.json, both JSON files
    marked "smoke test; not evaluation data"; the output is never scored."""
    root = RUN_ROOT

    def refuse(problems: list[str]) -> int:
        return _refuse(problems, "smoke")

    if args.condition != "plain":
        return refuse(["the smoke test runs the plain condition only"])
    gate = args.cost_gate
    if gate is None:
        return refuse(["--cost-gate is required for the smoke test (there is no default)"])
    if not math.isfinite(gate) or gate <= 0:
        return refuse(["--cost-gate must be a positive number of US dollars"])
    if round(gate, 6) <= 0:
        return refuse([f"--cost-gate {gate!r} is below $0.000001, the smallest amount recorded"])
    if gate > SMOKE_HARD_STOP_USD + 1e-9:
        stop = usd(SMOKE_HARD_STOP_USD)
        return refuse([f"--cost-gate {usd(gate)} is above section B's hard stop of {stop}"])
    if "ANTHROPIC_INFERENCE_GEO" in os.environ:  # the name only; the value is never shown
        return refuse(["ANTHROPIC_INFERENCE_GEO is set; section B requires it unset"])
    ids = [part.strip() for part in args.ids.split(",") if part.strip()]
    problems: list[str] = []
    if not ids:
        problems.append("--ids names no report")
    if len(set(ids)) != len(ids):
        problems.append("--ids names a report twice")
    reports = []
    for report_id in dict.fromkeys(ids):
        if not re.fullmatch(r"[HC]-\d{3}", report_id):
            problems.append(f"'{report_id[:40]}' is not a report id")
            continue
        path = root / "data" / "drafts" / f"{report_id}.json"
        try:
            text = path.read_text(encoding="utf-8")
            report = Report.model_validate(json.loads(text, object_pairs_hook=unique_keys))
        except (OSError, ValueError, RecursionError) as exc:
            problems.append(
                f"data/drafts/{report_id}.json cannot be read as a draft ({str(exc)[:200]})"
            )
            continue
        if report.id != report_id:
            problems.append(f"data/drafts/{report_id}.json holds report {report.id}")
            continue
        if report.split != "dev":
            problems.append(
                f"{report_id} is a {report.split} report; the smoke test uses dev drafts only"
            )
            continue
        reports.append(report)
    if problems:
        return refuse(problems)
    try:
        taxonomy = load_taxonomy(root / "data" / "taxonomy.json")
    except (OSError, ValueError) as exc:
        return refuse([f"data/taxonomy.json cannot be loaded ({exc})"])
    try:
        messages, breaches = build_run_messages(reports, "plain", taxonomy, root / "prompts")
    except (OSError, ValueError) as exc:
        return refuse([f"the prompts cannot be read ({exc})"])
    if breaches:
        return refuse([f"isolation: {breach}" for breach in breaches])
    for report in reports:
        system, user = messages[report.id]
        shape = eval_request_args(EVAL_MODEL, f"<{len(system)} characters>", "", EVAL_MAX_TOKENS)
        shape["messages"][0]["content"] = f"<{len(user)} characters>"
        print(f"request {report.id}: {json.dumps(shape)}")
    # The dearest a call can be: no more input tokens than the texts' UTF-8 bytes (a token covers
    # at least one byte) plus the message wrapping, and the whole max_tokens of output.
    longest = max(len(s.encode("utf-8")) + len(u.encode("utf-8")) for s, u in messages.values())
    ceiling = cost_usd(EVAL_MODEL, longest + SMOKE_WRAPPING_TOKENS, EVAL_MAX_TOKENS)
    stage = root / RUNS_DIR / SMOKE_STAGE_DIR
    with contextlib.ExitStack() as held:
        try:  # one smoke run at a time: the stage's limits cover them all
            held.enter_context(run_lock(stage))
        except RunInUse:
            busy = "another smoke run is going on; section B's limits cover every invocation"
            return refuse([f"{busy}, so wait"])
        except OSError as exc:
            return refuse([f"runs/{SMOKE_STAGE_DIR}/.run.lock cannot be used ({exc})"])
        return _smoke_in_stage(root, reports, messages, ceiling, gate, refuse)


def _mark_smoke_results(path: Path, purpose: str) -> None:
    """Put the purpose line first in a smoke run's results.json, if one was written."""
    try:
        results = read_report_json(path)
    except (OSError, ValueError):
        return  # not written (the run stopped before it) or not readable: nothing to mark
    write_report_json(path, {"purpose": purpose} | results)


def _smoke_in_stage(root, reports, messages, ceiling: float, gate: float, refuse) -> int:
    """The part of `smoke` that runs under the stage lock: the earlier smoke runs' calls and
    spend, the limits left, and the run itself."""
    earlier_calls, earlier_usd, problem = _earlier_smoke_spend(root)
    if problem:
        return refuse([problem])
    calls_left = SMOKE_MAX_CALLS - earlier_calls
    if calls_left <= 0:
        return refuse(
            [
                f"section B's {SMOKE_MAX_CALLS} calls are used up ({earlier_calls} made in "
                "earlier smoke runs)"
            ]
        )
    gate = min(gate, SMOKE_HARD_STOP_USD - earlier_usd)
    if round(gate, 6) <= 0:
        stop = usd(SMOKE_HARD_STOP_USD)
        return refuse([f"section B's hard stop of {stop} is used up by earlier smoke runs"])
    max_calls = min(2 * len(reports), calls_left)
    now = RUN_CLOCK()
    run_id = f"smoke-{now.astimezone(UTC):%Y%m%d-%H%M%S}"
    run_dir = root / RUNS_DIR / run_id
    if run_dir.exists():
        return refuse([f"runs/{run_id} exists already; start the smoke test again"])
    try:
        hashes = run_hashes(root, "dev", "plain")
    except OSError as exc:
        return refuse([f"the prompts, taxonomy or reports cannot be hashed ({exc})"])
    config = SmokeConfig(
        run_id=run_id,
        report_ids=[r.id for r in reports],
        model=EVAL_MODEL,
        max_tokens=EVAL_MAX_TOKENS,
        prompt_hash=hashes["prompt_hash"],
        taxonomy_hash=hashes["taxonomy_hash"],
        created_at=now,
        cost_gate_usd=round(gate, 6),
        max_calls=max_calls,
        assumed_call_usd=round(ceiling, 6),
        sdk_version=package_version("anthropic"),
    )
    try:
        client = EVAL_CLIENT_FACTORY()
    except MissingAPIKeyError as exc:
        print(f"FAIL {exc}")
        return 1
    try:
        with run_lock(run_dir):
            write_report_json(run_dir / "config.json", config.model_dump(mode="json"))
            print(
                f"smoke {run_id}: {len(reports)} report(s) x 1, plain, gate {usd(round(gate, 6))}"
                f" (earlier smoke runs: {earlier_calls} calls, ${earlier_usd:.4f}), at most "
                f"{max_calls} calls, each assumed to cost {usd(round(ceiling, 4))} before it starts"
            )
            try:
                outcome = run_units(
                    run_dir=run_dir,
                    run_id=run_id,
                    dataset="dev",
                    condition="plain",
                    model=EVAL_MODEL,
                    messages=messages,
                    client=client,
                    cost_gate=gate,
                    workers=1,
                    max_calls=max_calls,
                    repeats=1,
                    clock=RUN_CLOCK,
                    sleep=RUN_SLEEP,
                    transport_retries=0,
                    min_assumed_usd=ceiling,
                )
            finally:  # however the run ends, its results.json says what it is
                _mark_smoke_results(run_dir / "results.json", config.purpose)
    except RunInUse:
        return refuse([f"runs/{run_id} is being run by another invocation"])
    except CallsFileError as exc:
        print(f"FAIL {exc}")
        return 1
    except KeyboardInterrupt:
        print(f"interrupted: the calls made are in runs/{run_id}/calls.jsonl")
        return 130
    except OSError as exc:
        print(f"FAIL the run's files could not be written ({exc})")
        return 1
    others = [m for m in outcome.results["totals"]["models_returned"] if m != EVAL_MODEL]
    if others:
        print(f"FAIL the API returned {', '.join(others)}, not {EVAL_MODEL} (section B)")
        return 1
    return 0 if outcome.complete and outcome.failure is None else 1


def _adjudicate(args: argparse.Namespace) -> int:
    root = SCORE_ROOT
    if args.action == "prepare":
        inputs, problems = load_inputs(root, args.dataset, args.runs)
        if inputs is None:
            print("adjudicate prepare refused:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        found = review_findings(classify_runs(inputs))
        outcome = adjudication.prepare(
            root, args.dataset, found, inputs.reports, SCORE_CLOCK, args.replace
        )
    elif args.action == "apply":
        outcome = adjudication.apply(root, args.dataset, SCORE_CLOCK)
    else:
        outcome = adjudication.status(root, args.dataset)
    for line in outcome.lines:
        print(line)
    return 0 if outcome.ok else 1


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
    if args.command == "readable":
        lines, ok = write_readable(args.path)
        for line in lines:
            print(line)
        return 0 if ok else 1
    if args.command == "plant":
        return _plant(args)
    if args.command == "run":
        return _run(args)
    if args.command == "smoke":
        return _smoke(args)
    if args.command in ("map-list", "score"):
        if args.command == "map-list":
            outcome = map_list(SCORE_ROOT, args.runs)
        else:
            outcome = run_score(
                SCORE_ROOT, args.dataset, args.runs, args.provisional, SCORE_CLOCK, SCORER_COMMIT()
            )
        for line in outcome.lines:
            print(line)
        return 0 if outcome.ok else 1
    if args.command == "adjudicate":
        return _adjudicate(args)
    if args.command == "freeze":
        outcome = check_lock(FREEZE_ROOT) if args.check else freeze(FREEZE_ROOT, args.replace)
        for line in outcome.lines:
            print(line)
        return 0 if outcome.ok else 1
    return 2
