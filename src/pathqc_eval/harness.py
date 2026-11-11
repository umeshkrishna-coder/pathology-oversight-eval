"""Evaluation harness (EVAL-04): the evaluated model over one dataset in one condition.

A run covers one dataset (dev or scored) and one condition (plain or structured). Each report is
reviewed in 3 repeats; a (report, repeat) pair is a unit. Every attempt is one line in
runs/<run_id>/calls.jsonl (kept local until release); results.json is rebuilt from it at the end
of every invocation. Owner decisions: claude-sonnet-5-5 at the API's default effort and
sampling, max_tokens 16,000, the same in both conditions; an output that cannot be read as
findings (or a call that does not end its turn normally) is repeated once; findings are read
leniently (findings.py).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, ValidationError

from pathqc_eval.cost import cost_usd
from pathqc_eval.draft import MissingAPIKeyError
from pathqc_eval.findings import DroppedFinding, ParsedFinding, parse_findings, writable_text
from pathqc_eval.freeze import LOCK_FILE, PROMPT_FILES, TAXONOMY_FILE, check_lock, compute_lock
from pathqc_eval.freeze import dataset_hash as combined_hash
from pathqc_eval.io import append_jsonl, read_report_json, write_report_json
from pathqc_eval.prompting import (
    OWNER_TEXT_PLACEHOLDER,
    STRUCTURED_OWNER_PROMPTS,
    build_eval_messages,
    check_eval_isolation,
)
from pathqc_eval.schema import Condition, Report, StrictModel
from pathqc_eval.taxonomy import Taxonomy
from pathqc_eval.validate import check_report

EVAL_MODEL = "claude-sonnet-5-5"
EVAL_MAX_TOKENS = 16000
REPEATS = 3
MAX_ATTEMPTS = 2  # attempt 2 only after an unreadable output or an abnormal stop
NORMAL_STOP_REASON = "end_turn"
FIRST_CALL_ASSUMED_USD = 0.06  # assumed cost of a call before any call has been made
TRANSPORT_RETRIES = 3
BACKOFF_SECONDS = (2.0, 8.0, 30.0)  # waits before transport retries 1, 2 and 3
# Dry-run estimate per call (S8, EVAL-04b): the four plain calls of the smoke test averaged
# 1,167.5 input and 776.25 output tokens; plus 50%, rounded up. A projection from four calls.
EST_INPUT_TOKENS = 1752
EST_OUTPUT_TOKENS = 1165
# The fake client's default token counts (tests), kept apart from the estimate.
FAKE_INPUT_TOKENS = 2500
FAKE_OUTPUT_TOKENS = 4000
RUNS_DIR = Path("runs")
REPORTS_DIR = Path("data/reports")
# The prompt files each condition's system message is built from (hashed into prompt_hash).
CONDITION_PROMPTS: dict[str, tuple[str, ...]] = {
    "plain": (PROMPT_FILES["plain"],),
    "structured": (
        PROMPT_FILES["structured_output"],
        PROMPT_FILES["structured_histopathology"],
        PROMPT_FILES["structured_cbc"],
    ),
}
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_DEVICE_NAME = re.compile(r"(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?", re.IGNORECASE)
_EPS = 1e-12


# Clients


@dataclass(frozen=True)
class EvalResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None


class EvalClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int) -> EvalResponse: ...


class TransportError(Exception):
    """The stage's transport failures: a connection error or timeout, a request timeout
    (HTTP 408), a rate limit (429) or a server error (5xx)."""

    def __init__(self, error_class: str, message: str) -> None:
        super().__init__(f"{error_class}: {message}")
        self.error_class = error_class
        self.message = message


def eval_request_args(model: str, system: str, user: str, max_tokens: int) -> dict:
    """Keyword arguments for one evaluation messages.create call: model, system, one user
    message and max_tokens only (no effort, no sampling parameter, no tools)."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def is_transport_status(status: int) -> bool:
    """Stage step 4: rate limit (429), server error (5xx) and timeout (408) are transport
    failures, retried by the harness (the SDK's own retries are off, so that each one is
    logged). The API's x-should-retry header is not consulted."""
    return status in (408, 429) or 500 <= status <= 599


def call_messages_api(
    create: Callable, errors, model: str, system: str, user: str, max_tokens: int
) -> EvalResponse:
    """One messages.create call (`create`, with `errors` the SDK module that defines its
    exceptions): exactly eval_request_args, retryable failures raised as TransportError, and
    the text blocks of the response joined."""
    try:
        message = create(**eval_request_args(model, system, user, max_tokens))
    except errors.APIConnectionError as exc:  # includes APITimeoutError
        raise TransportError(type(exc).__name__, str(exc)) from exc
    except errors.APIStatusError as exc:
        if is_transport_status(exc.status_code):
            raise TransportError(type(exc).__name__, str(exc)) from exc
        raise
    return EvalResponse(
        text="".join(block.text for block in message.content if block.type == "text"),
        model=message.model,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        stop_reason=message.stop_reason,
    )


class AnthropicEvalClient:
    """Real client; constructed only when a real run is requested. It refuses an empty or
    missing ANTHROPIC_API_KEY before the SDK client is built (the SDK alone would look for
    other credentials)."""

    def __init__(self, model: str = EVAL_MODEL) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise MissingAPIKeyError(
                "ANTHROPIC_API_KEY is not set; the owner adds it to .env before a real run"
            )
        import anthropic

        self.model = model
        self._errors = anthropic
        # The harness retries transport failures itself, so that each one is logged.
        self._client = anthropic.Anthropic(max_retries=0)

    def complete(self, system: str, user: str, max_tokens: int) -> EvalResponse:
        return call_messages_api(
            self._client.messages.create, self._errors, self.model, system, user, max_tokens
        )


Scripted = EvalResponse | str | BaseException


class FakeEvalClient:
    """Test double. `script` is a list consumed in call order, or a function of (system, user)
    returning the next item. A str is returned as a normal end of turn, an EvalResponse as it
    is, and an exception is raised."""

    def __init__(
        self,
        script: list[Scripted] | Callable[[str, str], Scripted],
        model: str = EVAL_MODEL,
        input_tokens: int = FAKE_INPUT_TOKENS,
        output_tokens: int = FAKE_OUTPUT_TOKENS,
    ) -> None:
        self._script = script if callable(script) else list(script)
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[tuple[str, str, int]] = []
        self._lock = threading.Lock()

    def complete(self, system: str, user: str, max_tokens: int) -> EvalResponse:
        with self._lock:
            self.calls.append((system, user, max_tokens))
            item = None if callable(self._script) else self._script.pop(0)
        if item is None:  # outside the lock, so that scripted calls can run at the same time
            item = self._script(system, user)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, EvalResponse):
            return item
        return EvalResponse(item, self.model, self.input_tokens, self.output_tokens, "end_turn")


# Selecting a run's reports and building its messages


@dataclass
class Selection:
    reports: list[Report] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def select_reports(root: Path, dataset: str, condition: str, taxonomy: Taxonomy) -> Selection:
    """The reports a run covers, or the reasons it must refuse.

    scored: refuses unless `freeze --check` passes (the same check_lock call). dev: the reports
    in data/reports/ whose split is dev; refuses if there are none, if any fails the per-report
    validator rules, or (structured) if an owner text in scope still holds the placeholder."""
    selection = Selection()
    if dataset == "scored":
        outcome = check_lock(root)
        if not outcome.ok:
            selection.problems += outcome.lines
            return selection
    folder = root / REPORTS_DIR
    paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
    seen: dict[str, str] = {}  # report id -> the file it was first read from
    for path in paths:
        try:
            report = Report.model_validate(read_report_json(path))
        except (ValueError, OSError, RecursionError) as exc:  # ValidationError is a ValueError
            reason = "nested too deeply" if isinstance(exc, RecursionError) else str(exc)
            selection.problems.append(f"{path.name} cannot be read as a report ({reason[:200]})")
            continue
        if report.id in seen:  # e.g. "H-001 - Copy.json": one of the two would be dropped
            selection.problems.append(
                f"report id {report.id} is in both {seen[report.id]} and {path.name}"
            )
            continue
        seen[report.id] = path.name
        if report.split != dataset:
            continue
        if dataset == "dev":
            selection.problems += [f"{path.name}: {r}" for r in check_report(report, taxonomy)]
        selection.reports.append(report)
    if not selection.reports and not selection.problems:
        selection.problems.append(f"no {dataset} reports in {REPORTS_DIR.as_posix()}/")
    modalities = sorted({r.modality for r in selection.reports})
    for rel in run_prompt_files(condition, modalities):
        path = root / rel
        if not path.is_file():
            selection.problems.append(f"{rel} is missing")
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            selection.problems.append(f"{rel} is not UTF-8 text; save it as UTF-8")
            continue
        except OSError as exc:
            selection.problems.append(f"{rel} cannot be read ({exc})")
            continue
        if "\x00" in text:  # UTF-16 without a byte order mark decodes with a NUL in every pair
            selection.problems.append(f"{rel} is not UTF-8 text; save it as UTF-8")
            continue
        owner_text = rel != PROMPT_FILES["plain"] and rel != PROMPT_FILES["structured_output"]
        if dataset == "dev" and owner_text and OWNER_TEXT_PLACEHOLDER in text:
            selection.problems.append(f"{rel} still holds {OWNER_TEXT_PLACEHOLDER}")
    selection.reports.sort(key=lambda r: r.id)
    return selection


def run_prompt_files(condition: str, modalities: list[str]) -> list[str]:
    """The prompt files a run's system messages are built from: plain.md, or
    structured_output.md and the owner text of each modality in scope."""
    if condition == "plain":
        return [PROMPT_FILES["plain"]]
    owner = [f"prompts/{STRUCTURED_OWNER_PROMPTS[m]}" for m in modalities]
    return [PROMPT_FILES["structured_output"], *owner]


def build_run_messages(
    reports: list[Report], condition: str, taxonomy: Taxonomy, prompts_dir: Path
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """(system, user) for each report, and every isolation breach (empty when isolated)."""
    messages: dict[str, tuple[str, str]] = {}
    breaches: list[str] = []
    for report in reports:
        try:
            system, user = build_eval_messages(report, condition, taxonomy, prompts_dir)
        except (OSError, ValueError) as exc:  # UnicodeDecodeError is a ValueError
            breaches.append(f"{report.id} ({condition}): a prompt file cannot be read ({exc})")
            continue
        breaches += [
            f"{report.id} ({condition}): {breach}"
            for breach in check_eval_isolation(report, condition, system, user, taxonomy)
        ]
        messages[report.id] = (system, user)
    return messages, breaches


def run_hashes(root: Path, dataset: str, condition: str) -> dict:
    """dataset_hash, prompt_hash, taxonomy_hash and lock_created_at for the run config.

    A scored run takes them from the lock (whose check has passed); a dev run computes them
    live with the freeze's own functions (lock_created_at null). prompt_hash combines the hashes
    of the condition's prompt files the same way the dataset hash combines the reports."""
    if dataset == "scored":
        lock = read_report_json(root / LOCK_FILE)
        files, data_hash, created = lock["files"], lock["dataset"]["hash"], lock["created_at"]
    else:
        current = compute_lock(root)
        files, data_hash, created = current["files"], current["dataset"]["hash"], None
    prompts = {rel: files.get(rel) or "missing" for rel in CONDITION_PROMPTS[condition]}
    return {
        "dataset_hash": data_hash,
        "prompt_hash": combined_hash(prompts),
        "taxonomy_hash": files[TAXONOMY_FILE],
        "lock_created_at": created,
    }


def dry_run_lines(
    dataset: str,
    condition: str,
    reports: list[Report],
    messages: Mapping[str, tuple[str, str]],
    repeats: int = REPEATS,
) -> list[str]:
    units = len(reports) * repeats
    most = units * MAX_ATTEMPTS
    lines = [
        "DRY RUN: no client is constructed and no API call is made.",
        f"dataset {dataset} | condition {condition} | {len(reports)} reports | {units} units "
        f"({repeats} repeats each) | at most {most} calls ({MAX_ATTEMPTS} attempts per unit)",
    ]
    for modality in ("histopathology", "cbc"):
        first = next((r for r in reports if r.modality == modality), None)
        if first is None:
            continue
        system, user = messages[first.id]
        lines += [
            f"===== {first.id} system message ({condition}) =====",
            system,
            f"===== {first.id} user message =====",
            user,
        ]
    per_call = cost_usd(EVAL_MODEL, EST_INPUT_TOKENS, EST_OUTPUT_TOKENS)
    lines.append(
        "Estimate (a projection from the four calls of the S8 smoke test, plain condition: their "
        f"average plus 50%): {EST_INPUT_TOKENS:,} input + {EST_OUTPUT_TOKENS:,} output tokens "
        f"per call at Sonnet prices = ${per_call:.4f} per "
        f"call; {units} calls (one per unit) = ${per_call * units:.4f}; at most {most} calls = "
        f"${per_call * most:.4f}"
    )
    return lines


# Run state, read back from calls.jsonl


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def valid_run_id(run_id: str) -> bool:
    """Letters, digits, '.', '_' and '-', at most 100, starting with a letter or digit; not a
    name Windows cannot use for a folder (a device name such as NUL or COM1, with or without
    an extension, or a trailing dot, which Windows drops)."""
    return (
        _RUN_ID.fullmatch(run_id) is not None
        and not run_id.endswith(".")
        and _DEVICE_NAME.fullmatch(run_id) is None
    )


def default_run_id(now: datetime, dataset: str, condition: str) -> str:
    return f"{now.astimezone(UTC):%Y%m%d-%H%M%S}-{dataset}-{condition}"


def attempt_ok(line: Mapping) -> bool:
    return line.get("stop_reason") == NORMAL_STOP_REASON and line.get("parse_status") == "valid"


def unit_status(attempts: list[Mapping]) -> str:
    if any(attempt_ok(a) for a in attempts):
        return "valid"
    if len(attempts) >= MAX_ATTEMPTS:
        return "invalid"
    return "pending"


class CallsFileError(ValueError):
    pass


class AttemptLine(StrictModel):
    """One attempt in calls.jsonl, as run_units writes it."""

    run_id: str
    report_id: str
    condition: Condition
    repeat: int = Field(ge=1)
    attempt: int = Field(ge=1)
    started_at: str
    duration_s: float
    model_requested: str
    model_returned: str
    system_sha256: str
    user_sha256: str
    raw_text: str
    stop_reason: str | None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    parse_status: Literal["valid", "invalid"]
    findings: list[ParsedFinding]
    dropped: list[DroppedFinding]
    notes: list[str]


class FailureLine(StrictModel):
    """A transport failure, or a failure that stopped the run ("fatal": true)."""

    run_id: str
    report_id: str
    condition: Condition
    repeat: int = Field(ge=1)
    error_class: str
    error_message: str
    fatal: bool = False


def _first_problem(exc: ValidationError) -> str:
    errors = exc.errors()
    where = ".".join(str(part) for part in errors[0]["loc"]) or "the line"
    more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"{where}: {errors[0]['msg']}{more}"


def read_attempts(
    path: Path, run_id: str | None = None, condition: str | None = None
) -> dict[tuple[str, int], list[dict]]:
    """Attempt lines of calls.jsonl by (report_id, repeat), in attempt order. Every line must
    be an attempt or failure line of this run (when run_id and condition are given)."""
    attempts: dict[tuple[str, int], list[dict]] = {}
    if not path.is_file():
        return attempts
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CallsFileError(f"{path} cannot be read ({exc})") from exc
    # Lines end at "\n" only (as append_jsonl writes them): str.splitlines would also break a
    # line at U+2028, U+2029 or U+0085, which a model's output may hold and JSON keeps as is.
    for n, raw in enumerate(text.split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except (ValueError, RecursionError) as exc:
            raise CallsFileError(f"{path}: line {n} does not parse ({exc})") from exc
        model = AttemptLine if isinstance(line, dict) and "attempt" in line else FailureLine
        try:
            model.model_validate(line, strict=True)  # a number written as text is refused
        except ValidationError as exc:
            raise CallsFileError(
                f"{path}: line {n} is not a call line this run can read ({_first_problem(exc)})"
            ) from exc
        if (run_id is not None and line["run_id"] != run_id) or (
            condition is not None and line["condition"] != condition
        ):
            raise CallsFileError(
                f"{path}: line {n} is from run '{line['run_id']}', condition "
                f"'{line['condition']}', not from this run"
            )
        if model is AttemptLine:
            attempts.setdefault((line["report_id"], line["repeat"]), []).append(line)
    for (report_id, repeat), lines in attempts.items():
        lines.sort(key=lambda a: a["attempt"])
        # An interrupt between writing a line and noting it was written can make the run write
        # the same line twice; an identical copy is read once, a different one is refused.
        unique: list[dict] = []
        for line in lines:
            if unique and unique[-1]["attempt"] == line["attempt"]:
                if unique[-1] != line:
                    raise CallsFileError(
                        f"{path}: two different lines for {report_id} repeat {repeat} "
                        f"attempt {line['attempt']}"
                    )
                continue
            unique.append(line)
        lines[:] = unique
    return attempts


def build_results(
    run_id: str,
    dataset: str,
    condition: str,
    report_ids: list[str],
    attempts: Mapping[tuple[str, int], list[Mapping]],
    repeats: int = REPEATS,
) -> dict:
    """results.json: one entry per unit in report id, then repeat order, then the totals."""
    units = []
    used: list[Mapping] = []
    for report_id in sorted(report_ids):
        for repeat in range(1, repeats + 1):
            lines = list(attempts.get((report_id, repeat), []))
            used += lines
            status = unit_status(lines)
            final = next((a for a in lines if attempt_ok(a)), lines[-1] if lines else None)
            units.append(
                {
                    "report_id": report_id,
                    "repeat": repeat,
                    "status": status,
                    "attempts": len(lines),
                    "findings": final["findings"] if status == "valid" else [],
                    "dropped_count": len(final["dropped"]) if status == "valid" else 0,
                    "model_returned": final["model_returned"] if final else None,
                    "input_tokens": sum(a["input_tokens"] for a in lines),
                    "output_tokens": sum(a["output_tokens"] for a in lines),
                    "cost_usd": round(sum(a["cost_usd"] for a in lines), 6),
                }
            )
    totals = {
        "units": len(units),
        "valid": sum(u["status"] == "valid" for u in units),
        "invalid": sum(u["status"] == "invalid" for u in units),
        "pending": sum(u["status"] == "pending" for u in units),
        "calls": len(used),
        "input_tokens": sum(a["input_tokens"] for a in used),
        "output_tokens": sum(a["output_tokens"] for a in used),
        "cost_usd": round(sum(a["cost_usd"] for a in used), 6),
        "models_returned": sorted({a["model_returned"] for a in used}),
    }
    return {
        "run_id": run_id,
        "dataset": dataset,
        "condition": condition,
        "units": units,
        "totals": totals,
    }


# Running


@dataclass
class _CallResult:
    response: EvalResponse | None
    transport: list[tuple[str, str]]
    fatal: tuple[str, str] | None
    duration_s: float


def _call(
    client: EvalClient,
    system: str,
    user: str,
    max_tokens: int,
    sleep: Callable[[float], None],
    retries: int = TRANSPORT_RETRIES,
) -> _CallResult:
    """One attempt, with up to `retries` transport retries; never raises."""
    transport: list[tuple[str, str]] = []
    for retry in range(retries + 1):
        started = time.perf_counter()
        try:
            response = client.complete(system, user, max_tokens)
        except TransportError as exc:
            transport.append((exc.error_class, exc.message))
            if retry < retries:
                sleep(BACKOFF_SECONDS[retry])
            continue
        except Exception as exc:  # a rejected request or anything unexpected stops the run
            return _CallResult(None, transport, (type(exc).__name__, str(exc)), 0.0)
        return _CallResult(response, transport, None, time.perf_counter() - started)
    return _CallResult(None, transport, None, 0.0)


def _cost(response: EvalResponse, requested: str) -> float:
    """Priced at the dearer of the model requested and the model the API names, so that the
    cost gate never under-counts (an unknown model string is priced as the one requested)."""
    as_requested = cost_usd(requested, response.input_tokens, response.output_tokens)
    try:
        return max(
            as_requested, cost_usd(response.model, response.input_tokens, response.output_tokens)
        )
    except ValueError:
        return as_requested


@dataclass
class RunOutcome:
    complete: bool  # every unit is valid or invalid
    stopped: str | None  # why scheduling stopped early (gate or --max-calls), if it did
    failure: str | None  # a call that failed and stopped the run, if one did
    results: dict
    lines: list[str] = field(default_factory=list)


def _stamp(now: datetime) -> str:
    return now.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def usd(amount: float) -> str:
    """Dollars to the cent, or the amount exactly as given when the cent would hide it."""
    cents = f"{amount:.2f}"
    return f"${cents}" if float(cents) == amount else f"${amount!r}"


class RunInUse(Exception):
    pass


LOCK_NAME = ".run.lock"


@contextmanager
def run_lock(run_dir: Path):
    """Hold an exclusive lock on runs/<run_id>/.run.lock while a run goes on, so that a second
    invocation on the same run id refuses instead of repeating the calls in flight. The
    operating system drops the lock when the process ends, so a crash leaves no stale lock."""
    run_dir.mkdir(parents=True, exist_ok=True)
    handle = open(run_dir / LOCK_NAME, "a+b")  # held open for the whole run
    try:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RunInUse(f"{run_dir.as_posix()} is locked ({exc})") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


def run_is_busy(run_dir: Path) -> bool:
    """Whether another invocation holds this run's lock (the folder exists)."""
    try:
        with run_lock(run_dir):
            return False
    except RunInUse:
        return True


def _append_line(path: Path, record: dict) -> None:
    """Append one line to calls.jsonl. A last line left without its newline (an outside
    edit) gets one first. If the write fails part-way (a full disk, Ctrl+C), the file is cut
    back to its size before the write, so it never holds a fragment of a line."""
    size = path.stat().st_size if path.exists() else 0
    try:
        if size:
            with path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                last = handle.read(1)
            if last != b"\n":
                with path.open("ab") as handle:
                    handle.write(b"\n")
        append_jsonl(path, record)
    except BaseException:
        try:
            if path.exists() and path.stat().st_size > size:
                os.truncate(path, size)
        except OSError:
            pass
        raise


def run_units(
    *,
    run_dir: Path,
    run_id: str,
    dataset: str,
    condition: str,
    model: str,
    messages: Mapping[str, tuple[str, str]],
    client: EvalClient,
    cost_gate: float,
    workers: int = 4,
    max_calls: int | None = None,
    repeats: int = REPEATS,
    max_tokens: int = EVAL_MAX_TOKENS,
    out: Callable[[str], None] = print,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
    transport_retries: int = TRANSPORT_RETRIES,
    min_assumed_usd: float = 0.0,
) -> RunOutcome:
    """Run every unit not yet finished in calls.jsonl. Calls go out on `workers` threads; this
    thread is the only writer of calls.jsonl and results.json.

    If the run is interrupted (Ctrl+C) or a line cannot be written, no new call starts, the
    calls already in flight are waited for and logged (they are billed; a second Ctrl+C
    abandons them), results.json is rebuilt from calls.jsonl, and the error is raised again.

    For the smoke test (EVAL-04b): `transport_retries` 0 makes every call a single request,
    and `min_assumed_usd` makes each call count at least its ceiling before it starts."""
    calls_path = run_dir / "calls.jsonl"
    attempts = read_attempts(calls_path, run_id, condition)
    done = [a for lines in attempts.values() for a in lines]
    spent = sum(a["cost_usd"] for a in done)
    dearest = max((a["cost_usd"] for a in done), default=None)
    queue: deque[tuple[tuple[str, int], int]] = deque()
    for report_id in sorted(messages):
        for repeat in range(1, repeats + 1):
            lines = attempts.get((report_id, repeat), [])
            if unit_status(lines) == "pending":
                queue.append(((report_id, repeat), len(lines) + 1))

    def base(unit: tuple[str, int]) -> dict:
        return {"run_id": run_id, "report_id": unit[0], "condition": condition, "repeat": unit[1]}

    in_flight: dict[Future, tuple[tuple[str, int], int, str]] = {}
    written: dict[Future, int] = {}  # lines of a finished call already appended to calls.jsonl
    started_calls = 0
    stopped: str | None = None
    failure: str | None = None

    def record(future: Future) -> None:
        """Log one finished call (its transport lines, then its attempt or failure line) and
        update the run. A call stays in flight until its lines are written, and lines already
        written are not written again, so an interrupted record can be repeated."""
        nonlocal spent, dearest, failure
        unit, attempt, started_at = in_flight[future]
        result: _CallResult = future.result()
        lines = [
            base(unit) | {"error_class": error_class, "error_message": writable_text(text)[0]}
            for error_class, text in result.transport
        ]
        attempt_line = None
        if result.fatal is not None:
            error_class, text = result.fatal
            lines.append(
                base(unit)
                | {"error_class": error_class, "error_message": writable_text(text)[0]}
                | {"fatal": True}
            )
        elif result.response is not None:
            response = result.response
            system, user = messages[unit[0]]
            parsed = parse_findings(response.text)
            raw_text, replaced = writable_text(response.text)
            notes = parsed.notes
            if replaced:  # the writer must never fail on a call's content
                notes = [*notes, "raw_text held unpaired surrogates; replaced with U+FFFD"]
            attempt_line = base(unit) | {
                "attempt": attempt,
                "started_at": started_at,
                "duration_s": round(result.duration_s, 2),
                "model_requested": model,
                "model_returned": response.model,
                "system_sha256": sha256_text(system),
                "user_sha256": sha256_text(user),
                "raw_text": raw_text,
                "stop_reason": response.stop_reason,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": round(_cost(response, model), 6),
                "parse_status": parsed.status,
                "findings": [f.model_dump(mode="json") for f in parsed.findings],
                "dropped": [d.model_dump(mode="json") for d in parsed.dropped],
                "notes": notes,
            }
            lines.append(attempt_line)
        for line in lines[written.get(future, 0) :]:
            _append_line(calls_path, line)
            written[future] = written.get(future, 0) + 1
        del in_flight[future]
        if result.fatal is not None:
            error_class, text = result.fatal
            out(f"FAIL {unit[0]} repeat {unit[1]}: {error_class}: {writable_text(text)[0]}")
            failure = failure or f"the API refused a call ({error_class})"
            return
        if attempt_line is None:
            out(
                f"FAIL {unit[0]} repeat {unit[1]}: the API could not be reached "
                f"({len(result.transport)} tries)"
            )
            failure = failure or "transport failures after every retry"
            return
        attempts.setdefault(unit, []).append(attempt_line)
        spent += attempt_line["cost_usd"]
        dearest = max(dearest or 0.0, attempt_line["cost_usd"])
        status = unit_status(attempts[unit])
        if status == "pending":
            queue.appendleft((unit, attempt + 1))
            return
        unit_lines = attempts[unit]
        findings = len(attempt_line["findings"]) if status == "valid" else 0
        out(
            f"{unit[0]} repeat {unit[1]}: {status} | {findings} finding(s) | "
            f"{sum(a['input_tokens'] for a in unit_lines)} in + "
            f"{sum(a['output_tokens'] for a in unit_lines)} out tokens | "
            f"${sum(a['cost_usd'] for a in unit_lines):.4f} | running ${spent:.4f}"
        )

    def key(future: Future) -> tuple:
        return in_flight[future][:2]

    pool = ThreadPoolExecutor(max_workers=workers)
    error: BaseException | None = None
    try:
        while True:
            while queue and stopped is None and failure is None and len(in_flight) < workers:
                if max_calls is not None and started_calls >= max_calls:
                    stopped = f"--max-calls {max_calls} reached"
                    break
                assumed = FIRST_CALL_ASSUMED_USD if dearest is None else dearest
                assumed = max(assumed, min_assumed_usd)  # the smoke test: each call's ceiling
                if spent + assumed * (len(in_flight) + 1) > cost_gate + _EPS:
                    if not in_flight:
                        stopped = (
                            f"cost gate: the next call could cross {usd(cost_gate)} "
                            f"(spent ${spent:.4f}, next call assumed ${assumed:.4f})"
                        )
                    break
                unit, attempt = queue[0]
                system, user = messages[unit[0]]
                started_at = _stamp(clock())  # before the call starts, so nothing can come
                queue.popleft()  # between starting it and noting it as in flight
                call = (_call, client, system, user, max_tokens, sleep, transport_retries)
                in_flight[pool.submit(*call)] = (
                    unit, attempt, started_at,
                )  # fmt: skip
                started_calls += 1
            if not in_flight:
                break
            finished, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
            for future in sorted(finished, key=key):
                record(future)
    except BaseException as exc:  # Ctrl+C, or a line that cannot be written
        error = exc
        try:
            if in_flight:
                reason = "interrupted" if isinstance(exc, KeyboardInterrupt) else type(exc).__name__
                out(
                    f"stopping ({reason}): waiting for {len(in_flight)} call(s) in flight to "
                    "log them; Ctrl+C again abandons them"
                )
            for future in sorted(in_flight, key=key):
                try:
                    record(future)
                except Exception:  # keep logging the other calls
                    continue
        except KeyboardInterrupt:  # pressed again: the calls in flight are abandoned
            pass
    finally:
        pool.shutdown(wait=error is None, cancel_futures=True)
    try:
        attempts = read_attempts(calls_path, run_id, condition)
        results = build_results(run_id, dataset, condition, list(messages), attempts, repeats)
        write_report_json(run_dir / "results.json", results)
    except Exception:
        if error is None:
            raise
        error.results_written = False  # type: ignore[attr-defined]
        raise error from None
    if error is not None:
        error.results_written = True  # type: ignore[attr-defined]
        raise error
    t = results["totals"]
    lines = [
        f"totals: {t['units']} units ({t['valid']} valid, {t['invalid']} invalid, "
        f"{t['pending']} pending) | {t['calls']} calls | {t['input_tokens']} input + "
        f"{t['output_tokens']} output tokens | ${t['cost_usd']:.4f} | models returned: "
        f"{', '.join(t['models_returned']) or 'none'}"
    ]
    reasons = [reason for reason in (failure, stopped) if reason]
    if reasons:
        lines.append(f"stopped early: {'; '.join(reasons)}")
    try:
        for text in lines:
            out(text)
    except KeyboardInterrupt as exc:  # results.json is already written
        exc.results_written = True  # type: ignore[attr-defined]
        raise
    return RunOutcome(
        complete=t["pending"] == 0, stopped=stopped, failure=failure, results=results, lines=lines
    )
