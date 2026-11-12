"""Blind adjudication of review findings (EVAL-05 6.7; decision 9).

`prepare` collects every review finding of the two runs and merges identical ones into items.
The owner sees only adjudication_sheet.md (and adjudication.json): the finding's report,
section, quoted sentence and rationale, the candidate planted error with its other places, and
the reason it needs review; never a category, condition, repeat, model or run (decisions 9 and
63). A finding in review for several errors gives one item per error (decision 61).
adjudication_hidden.json maps each item to its findings; only the scorer reads it, and only
once every verdict is filled; it then writes adjudication_log.json. It is gitignored, with
results/*/provisional/, until the reveal (EVAL-09 A).

A provisional score shows ranges by condition, so every one made before the last verdict is
recorded in results/<dataset>/provisional/provisional_log.json and copied into
adjudication_log.json at the reveal.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import Field

from pathqc_eval import scoring_config as cfg
from pathqc_eval.io import read_report_json, unique_keys, write_report_json
from pathqc_eval.matching import (
    VERDICTS,
    normalise_quote,
    normalise_section,
)
from pathqc_eval.schema import AdjudicationHidden, AdjudicationItem, StrictModel

ITEMS_FILE = "adjudication.json"
HIDDEN_FILE = "adjudication_hidden.json"
SHEET_FILE = "adjudication_sheet.md"
LOG_FILE = "adjudication_log.json"
PROVISIONAL_LOG_FILE = "provisional_log.json"
_BLOCK_LINE = re.compile(r"^==\s*(.*?)\s*==$")
SHEET_KEYS = ("verdict", "reason")
_LINE_END = re.compile(r"\r\n|\r|\n")


def sheet_lines(text: str) -> list[str]:
    """The sheet's lines, whatever the line ends (LF, CRLF or CR), without a leading BOM."""
    return _LINE_END.split(text.removeprefix("\ufeff"))


REASON_WORDS = {
    "section_mismatch": "the quoted sentence matches this planted error (or one of its other "
    "places), but the finding names another section",
    "omission_candidate": "this report has an omission error, and the finding is not a "
    "detection of another error; it may be reporting what is missing (the finding has one item "
    "for each omission error of the report)",
}


def reason_words(reason: str) -> str:
    """A review reason in plain words; the borderline band comes from the scorer settings."""
    if reason == "borderline_overlap":
        return (
            "the section is right, but the quoted sentence only partly matches this planted "
            f"error (overlap of at least {cfg.BORDERLINE_LOW:g} and below "
            f"{cfg.OVERLAP_THRESHOLD:g})"
        )
    return REASON_WORDS[reason]


def adjudication_dir(root: Path, dataset: str) -> Path:
    return root / "results" / dataset / "adjudication"


def stamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds").replace("+00:00", "Z")


class AdjudicationFile(StrictModel):
    """adjudication.json: the items, and when they were prepared and completed."""

    prepared_at: str
    completed_at: str | None = None
    items: list[AdjudicationItem] = Field(default_factory=list)

    def filled(self) -> int:
        return sum(item.verdict is not None for item in self.items)


class ProvisionalScore(StrictModel):
    """One `score --provisional` made while a verdict was missing."""

    scored_at: str
    review_findings: int
    adjudication: str  # "not prepared" or "<k> of <n> verdicts filled"


class ProvisionalLog(StrictModel):
    """results/<dataset>/provisional/provisional_log.json."""

    provisional_scores: list[ProvisionalScore] = Field(default_factory=list)


class AdjudicationLog(StrictModel):
    """adjudication_log.json, written once at the reveal."""

    prepared_at: str
    completed_at: str | None = None
    joined_at: str
    items: int
    adjudication_sha256: str
    provisional_scores_before_completion: list[ProvisionalScore] = Field(default_factory=list)


def _strict(model, raw: bytes):
    """A log file read strictly: no key given twice in an object (a later copy could hide
    entries), and no type coercion (a number written as text is refused)."""
    json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
    return model.model_validate_json(raw, strict=True)


def read_log(folder: Path) -> tuple[AdjudicationLog | None, str | None]:
    """adjudication_log.json, or why it cannot be read (strict: a number written as text, or
    any other type that differs, is refused)."""
    try:
        return _strict(AdjudicationLog, (folder / LOG_FILE).read_bytes()), None
    except (OSError, ValueError, RecursionError) as exc:
        return None, f"{LOG_FILE} cannot be read ({str(exc)[:200]})"


def provisional_log_path(root: Path, dataset: str) -> Path:
    return root / "results" / dataset / "provisional" / PROVISIONAL_LOG_FILE


def read_provisional_log(root: Path, dataset: str) -> tuple[list[ProvisionalScore] | None, str]:
    """The provisional scores logged so far ([] without a log), or why the log cannot be read."""
    path = provisional_log_path(root, dataset)
    if not path.exists():
        return [], ""
    try:
        return _strict(ProvisionalLog, path.read_bytes()).provisional_scores, ""
    except (OSError, ValueError, RecursionError) as exc:
        where = f"results/{dataset}/provisional/{PROVISIONAL_LOG_FILE}"
        return None, f"{where} cannot be read ({str(exc)[:200]})"


def record_provisional(root: Path, dataset: str, entry: ProvisionalScore) -> str:
    """Add one provisional score to the log; the problem in plain words, or "" when done."""
    entries, problem = read_provisional_log(root, dataset)
    if entries is None:
        return problem
    path = provisional_log_path(root, dataset)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        log = ProvisionalLog(provisional_scores=[*entries, entry])
        write_report_json(path, log.model_dump(mode="json"))
    except OSError as exc:
        return f"results/{dataset}/provisional/{PROVISIONAL_LOG_FILE} cannot be written ({exc})"
    return ""


# prepare


@dataclass
class Prepared:
    items: list[AdjudicationItem]
    hidden: dict[str, list[AdjudicationHidden]]


def build_items(found: list, reports: dict) -> Prepared:
    """Merge review findings identical in report, normalised section, normalised quote,
    rationale and candidate error into one item (decision 63: the category plays no part);
    ids in a seeded shuffled order."""
    groups: dict[tuple, list] = {}
    for review in found:
        f = review.finding
        key = (
            review.unit.report_id,
            normalise_section(f.section),
            normalise_quote(f.quoted_sentence),
            f.rationale or "",
            review.outcome.error_id,
        )
        groups.setdefault(key, []).append(review)
    order = sorted(groups)
    random.Random(cfg.BOOTSTRAP_SEED).shuffle(order)
    items: list[AdjudicationItem] = []
    hidden: dict[str, list[AdjudicationHidden]] = {}
    for n, key in enumerate(order, start=1):
        members = groups[key]
        item_id = f"A{n:03d}"
        findings = [m.finding for m in members]
        items.append(
            AdjudicationItem(
                item_id=item_id,
                report_id=key[0],
                section=min(f.section for f in findings),
                quoted_sentence=min(f.quoted_sentence for f in findings),
                rationale=key[3],
                candidate_error_id=key[4],
                review_reason=members[0].outcome.reason,
            )
        )
        hidden[item_id] = [
            AdjudicationHidden(
                run_id=m.unit.run_id,
                condition=m.unit.condition,
                repeat=m.unit.repeat,
                finding_index=m.index,
                model=m.unit.model or "unknown",
            )
            for m in sorted(members, key=lambda m: (m.unit.run_id, m.unit.repeat, m.index))
        ]
    return Prepared(items, hidden)


def _comment(label: str, text: str) -> list[str]:
    """Comment lines; every line break of any kind starts a new comment line, so no text
    from a finding can ever be read as a sheet line."""
    lines = text.splitlines() or [""]
    return [f"# {label}: {lines[0]}"] + [f"#   {line}" for line in lines[1:]]


SHEET_HEADER = """\
# Blind adjudication sheet. Lines starting with # are comments.
# For each item, fill in two lines:
#   verdict: detected | miss | near_miss | false_alarm
#   reason: your reason in a few words (required with a verdict)
# detected: the finding is the candidate planted error; near_miss: right sentence, wrong kind
# of error; false_alarm: the finding is not a real error; miss: set the finding aside (neither
# a detection nor a false alarm). Then run `pathqc-eval adjudicate apply --dataset {dataset}`.
"""


def sheet_text(dataset: str, items: list[AdjudicationItem], reports: dict) -> str:
    out = [SHEET_HEADER.format(dataset=dataset).rstrip("\n")]
    for item in items:
        error = next(
            e for e in reports[item.report_id].errors if e.error_id == item.candidate_error_id
        )
        out += ["", f"== {item.item_id} =="]
        out += _comment("report", item.report_id)
        out += _comment("section", item.section)
        out += _comment("quoted sentence", item.quoted_sentence)
        out += _comment("rationale", item.rationale)
        out += _comment(
            "candidate planted error",
            f"{error.error_id} ({error.type}, {error.kind}) in {error.section}",
        )
        out += _comment("  its quoted sentence", error.quoted_sentence)
        for n, place in enumerate(error.other_places, start=1):  # decision 56 (EVAL-10)
            out += _comment(f"  its other place {n}", f"{place.section}: {place.quoted_sentence}")
        out += _comment("  its description", error.description)
        out += _comment("why it needs you", reason_words(item.review_reason))
        out += ["verdict:", "reason:"]
    return "\n".join(out) + "\n"


@dataclass
class Outcome:
    lines: list[str]
    ok: bool


def _entered(folder: Path) -> bool:
    """Whether the owner may have written anything: a verdict or reason in adjudication.json,
    or in the sheet any line other than comments, block lines and the empty `verdict:` and
    `reason:` lines it was prepared with (a second block for an item included). A file that
    cannot be read counts as written in."""
    data, _ = load_items(folder)
    if data is None and (folder / ITEMS_FILE).exists():
        return True
    if data is not None and any(i.verdict or i.verdict_reason for i in data.items):
        return True
    sheet = folder / SHEET_FILE
    if not sheet.exists():
        return False
    try:
        text = sheet.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return True
    for raw in sheet_lines(text):
        line = raw.strip()
        if not line or line.startswith("#") or _BLOCK_LINE.match(line):
            continue
        key, sep, value = line.partition(":")
        if not (sep and key.strip().lower() in SHEET_KEYS and not value.strip()):
            return True
    return False


def prepare(
    root: Path,
    dataset: str,
    found: list,
    reports: dict,
    clock: Callable[[], datetime],
    replace: bool = False,
) -> Outcome:
    """Write adjudication.json, adjudication_hidden.json and adjudication_sheet.md."""
    folder = adjudication_dir(root, dataset)
    existing = [name for name in (ITEMS_FILE, HIDDEN_FILE, SHEET_FILE) if (folder / name).exists()]
    if existing:
        if (folder / LOG_FILE).exists():
            return Outcome(
                ["FAIL this adjudication has been revealed to the scorer; it cannot be replaced"],
                False,
            )
        if not replace:
            return Outcome(
                [
                    f"FAIL an adjudication is already prepared in {folder.as_posix()}; "
                    "--replace starts again, and only while no verdict has been entered"
                ],
                False,
            )
        if _entered(folder):
            return Outcome(
                [
                    "FAIL verdicts have been entered (or other text was written into the sheet); "
                    "the preparation is not replaced"
                ],
                False,
            )
    prepared = build_items(found, reports)
    folder.mkdir(parents=True, exist_ok=True)
    items = AdjudicationFile(prepared_at=stamp(clock()), items=prepared.items)
    hidden = {
        item_id: [ref.model_dump(mode="json") for ref in refs]
        for item_id, refs in prepared.hidden.items()
    }
    write_report_json(folder / ITEMS_FILE, items.model_dump(mode="json"))
    write_report_json(folder / HIDDEN_FILE, hidden)
    (folder / SHEET_FILE).write_bytes(sheet_text(dataset, prepared.items, reports).encode("utf-8"))
    return Outcome(
        [
            f"adjudication ({dataset}): {len(prepared.items)} item(s) from "
            f"{_finding_count(found)} review finding(s); fill in {(folder / SHEET_FILE).as_posix()}"
        ],
        True,
    )


# run id, report id, repeat, finding index, candidate error id (a finding in review for
# several omission errors has one item, and one verdict, per error: EVAL-09 C)
FindingKey = tuple[str, str, int, int, str]


def _finding_count(found: list) -> int:
    return len({(r.unit.run_id, r.unit.report_id, r.unit.repeat, r.index) for r in found})


def stale_message(folder: Path) -> str:
    return (
        f"the adjudication in {folder.as_posix()} was prepared from other review findings "
        "than these runs give now (the runs, the reports or the scorer settings "
        "changed); move that folder aside and prepare again"
    )


@dataclass
class Joined:
    verdicts: dict[FindingKey, str | None]
    provisional_scores: int  # provisional scores made before every verdict was entered


def join(
    root: Path, dataset: str, found: list, clock: Callable[[], datetime]
) -> tuple[Joined | None, list[str]]:
    """The reveal: once every verdict is filled, read adjudication_hidden.json, check that it
    covers exactly the current review findings, and write adjudication_log.json (once), with
    the provisional scores logged before completion. Returns the verdict of each review
    finding by (run id, report id, repeat, finding index, candidate error id)."""
    folder = adjudication_dir(root, dataset)
    data, problem = load_items(folder)
    if data is None:
        return None, [problem]
    if not data.items or data.filled() < len(data.items):
        return None, [f"adjudication incomplete: {data.filled()} of {len(data.items)} verdicts"]
    try:
        raw = read_report_json(folder / HIDDEN_FILE)
        hidden = {
            item_id: [AdjudicationHidden.model_validate(ref) for ref in refs]
            for item_id, refs in raw.items()
        }
    except (OSError, ValueError, RecursionError, AttributeError, TypeError) as exc:
        return None, [f"{HIDDEN_FILE} cannot be read ({str(exc)[:200]})"]
    expected = {
        (r.unit.run_id, r.unit.report_id, r.unit.repeat, r.index, r.outcome.error_id): r
        for r in found
    }
    by_ref: dict[FindingKey, AdjudicationItem] = {}
    items = {item.item_id: item for item in data.items}
    stale = set(hidden) != set(items)
    for item_id, refs in hidden.items():
        item = items.get(item_id)
        if item is None:
            continue
        for ref in refs:
            key = (ref.run_id, item.report_id, ref.repeat, ref.finding_index)
            key += (item.candidate_error_id,)
            stale = stale or key in by_ref  # one finding and error in two items
            by_ref[key] = item
    stale = stale or set(by_ref) != set(expected)
    for key, review in expected.items():
        item = by_ref.get(key)
        if item is not None and (
            item.candidate_error_id != review.outcome.error_id
            or item.review_reason != review.outcome.reason
        ):
            stale = True  # the verdict answered another question
    if stale:
        return None, [stale_message(folder)]
    digest = file_sha256(folder / ITEMS_FILE)
    if (folder / LOG_FILE).exists():
        log, problem = read_log(folder)
        if log is None:
            return None, [problem]
        if log.adjudication_sha256 != digest:
            return None, [f"{ITEMS_FILE} has changed since the reveal at {log.joined_at}"]
    else:
        before, problem = read_provisional_log(root, dataset)
        if before is None:
            return None, [problem]
        log = AdjudicationLog(
            prepared_at=data.prepared_at,
            completed_at=data.completed_at,
            joined_at=stamp(clock()),
            items=len(data.items),
            adjudication_sha256=digest,
            provisional_scores_before_completion=before,
        )
        write_report_json(folder / LOG_FILE, log.model_dump(mode="json"))
    verdicts = {key: item.verdict for key, item in by_ref.items()}
    return Joined(verdicts, len(log.provisional_scores_before_completion)), []


# apply and status


@dataclass
class SheetBlock:
    item_id: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)


def parse_sheet(text: str) -> tuple[dict[str, SheetBlock], list[str]]:
    """`== A017 ==` blocks of `verdict:` and `reason:` lines, read like the planting sheet:
    '#' comments and blank lines are ignored, a line splits at its first colon, values are
    trimmed. An empty value means not filled in."""
    blocks: dict[str, SheetBlock] = {}
    problems: list[str] = []
    current: SheetBlock | None = None
    for n, raw in enumerate(sheet_lines(text), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _BLOCK_LINE.match(line)
        if match:
            item_id = match.group(1)
            current = SheetBlock(item_id, n)
            if item_id in blocks:
                problems.append(
                    f"{item_id}: line {n}: a second block for this item (the first is at line "
                    f"{blocks[item_id].line}); each item has exactly one block"
                )
            else:
                blocks[item_id] = current
            continue
        if current is None:
            problems.append(f"line {n}: text before the first '== <item id> ==' line")
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not sep or key not in SHEET_KEYS:
            problems.append(
                f"{current.item_id}: line {n}: expected 'verdict: ...' or 'reason: ...', got "
                f"'{line[:80]}'"
            )
            continue
        if current.fields.get(key):
            problems.append(f"{current.item_id}: line {n}: '{key}' is given twice")
            continue
        current.fields[key] = value
    return blocks, problems


def read_verdicts(text: str, item_ids: list[str]) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Each filled item's (verdict, reason), or every problem in plain words."""
    blocks, problems = parse_sheet(text)
    filled: dict[str, tuple[str, str]] = {}
    for item_id in sorted(set(blocks) - set(item_ids)):
        problems.append(f"{item_id}: no such item in {ITEMS_FILE}")
    for item_id in item_ids:
        block = blocks.get(item_id)
        if block is None:
            problems.append(f"{item_id}: its block is missing from the sheet")
            continue
        verdict = block.fields.get("verdict", "").lower()
        reason = block.fields.get("reason", "")
        if not verdict and not reason:
            continue
        if not verdict:
            problems.append(f"{item_id}: a reason is given but no verdict")
        elif verdict not in VERDICTS:
            problems.append(
                f"{item_id}: verdict '{block.fields['verdict'][:40]}' is not one of "
                f"{', '.join(VERDICTS)}"
            )
        elif not reason:
            problems.append(f"{item_id}: the verdict '{verdict}' needs a reason")
        else:
            filled[item_id] = (verdict, reason)
    return filled, problems


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_items(folder: Path) -> tuple[AdjudicationFile | None, str | None]:
    path = folder / ITEMS_FILE
    if not path.exists():
        return None, f"{path.as_posix()} does not exist; run `pathqc-eval adjudicate prepare` first"
    try:
        return AdjudicationFile.model_validate(read_report_json(path)), None
    except (OSError, ValueError, RecursionError) as exc:
        return None, f"{ITEMS_FILE} cannot be read ({str(exc)[:200]})"


def apply(root: Path, dataset: str, clock: Callable[[], datetime]) -> Outcome:
    folder = adjudication_dir(root, dataset)
    data, problem = load_items(folder)
    if data is None:
        return Outcome([f"FAIL {problem}"], False)
    if (folder / LOG_FILE).exists():
        log, problem = read_log(folder)
        if log is None:
            return Outcome([f"FAIL {problem}; while it exists the verdicts cannot change"], False)
        return Outcome(
            [
                f"FAIL the verdicts were revealed to the scorer at {log.joined_at}; they "
                "cannot change after the reveal"
            ],
            False,
        )
    sheet = folder / SHEET_FILE
    if not sheet.is_file():
        return Outcome([f"FAIL {SHEET_FILE} does not exist"], False)
    try:
        text = sheet.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Outcome([f"FAIL {SHEET_FILE} cannot be read as UTF-8 text ({exc})"], False)
    filled, problems = read_verdicts(text, [item.item_id for item in data.items])
    if problems:
        return Outcome(
            [f"FAIL {SHEET_FILE}: {len(problems)} problem(s); nothing was written:"]
            + [f"  - {p}" for p in problems],
            False,
        )
    items = [
        item.model_copy(
            update={
                "verdict": filled.get(item.item_id, (None, None))[0],
                "verdict_reason": filled.get(item.item_id, (None, None))[1],
            }
        )
        for item in data.items
    ]
    complete = bool(items) and all(item.verdict is not None for item in items)
    completed_at = (data.completed_at or stamp(clock())) if complete else None
    updated = AdjudicationFile(prepared_at=data.prepared_at, completed_at=completed_at, items=items)
    write_report_json(folder / ITEMS_FILE, updated.model_dump(mode="json"))
    return Outcome(
        [f"adjudication ({dataset}): {updated.filled()} of {len(items)} verdicts filled"], True
    )


def status(root: Path, dataset: str) -> Outcome:
    folder = adjudication_dir(root, dataset)
    data, problem = load_items(folder)
    if data is None:
        return Outcome([f"FAIL {problem}"], False)
    lines = [f"adjudication ({dataset}): {data.filled()} of {len(data.items)} verdicts filled"]
    if (folder / LOG_FILE).exists():
        log, problem = read_log(folder)
        if log is None:
            return Outcome([*lines, f"FAIL {problem}"], False)
        lines.append(f"revealed to the scorer at {log.joined_at}")
    return Outcome(lines, True)
