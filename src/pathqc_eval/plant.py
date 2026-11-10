"""Planting: apply the owner's sheet (data/specs/planting.md) to the untouched drafts.

The sheet is the only place planted errors and corrections are written (decision 37).
`pathqc-eval plant` applies it deterministically: drafts are read and never written,
data/reports/<id>.json is generated and never edited by hand, and no model takes part.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.readable import READABLE_DIR
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import SECTION_CONVENTIONS, CBCValues, Report
from pathqc_eval.spec import SpecRow
from pathqc_eval.taxonomy import Taxonomy
from pathqc_eval.validate import FILE_PLACEHOLDER, check_report

SHEET_FILE = Path("data/specs/planting.md")
DRAFTS_DIR = Path("data/drafts")
REPORTS_DIR = Path("data/reports")
REVIEW_DIR = "_review"

SEVERITIES = ("critical", "major", "minor")
KINDS = ("statement", "omission")
ANALYTES: tuple[str, ...] = tuple(CBCValues.model_fields)
DEFAULT_ANCHOR_SECTION = {"histopathology": "Synoptic summary", "cbc": "Values"}
MIN_QUOTE_WORDS = 5

REPORT_KEYS = ("verified", "verified_on")
FIX_KEYS = ("section", "find", "replace", "note")
ERROR_REQUIRED = ("type", "severity", "description", "rationale")
ERROR_OPTIONAL = ("severity_reason", "kind")
TEXT_KEYS = ("section", "find", "replace", "quote")
NUMBER_KEYS = ("set", "quote_analyte")
OMISSION_KEYS = (
    "remove_from",
    "remove",
    "remove_section",
    "anchor_section",
    "anchor",
    "anchor_analyte",
)
ERROR_KEYS = tuple(
    dict.fromkeys(ERROR_REQUIRED + ERROR_OPTIONAL + TEXT_KEYS + NUMBER_KEYS + OMISSION_KEYS)
)
VARIANT_KEYS = {"text": TEXT_KEYS, "number": NUMBER_KEYS, "omission": OMISSION_KEYS}
VARIANT_NAMES = {
    "text": "a text change",
    "number": "a CBC number change",
    "omission": "an omission",
}

_BLOCK_LINE = re.compile(r"^==\s*(.*?)\s*==$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# Parsing


@dataclass
class RawEntry:
    tag: str  # "fix" or "error"
    number: int  # 1-based among the block's entries with the same tag
    line: int
    fields: dict[str, str] = field(default_factory=dict)
    sets: list[tuple[str, int]] = field(default_factory=list)  # raw `set:` values, line numbers

    @property
    def label(self) -> str:
        return f"[{self.tag}] {self.number} (line {self.line})"


@dataclass
class RawBlock:
    report_id: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)
    entries: list[RawEntry] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class ParsedSheet:
    blocks: dict[str, RawBlock] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)  # lines outside any block


def parse_sheet(text: str) -> ParsedSheet:
    """Split the sheet into report blocks and entries; problems are kept, never raised."""
    sheet = ParsedSheet()
    current: RawBlock | None = None
    entry: RawEntry | None = None
    for n, raw in enumerate(text.replace("\r\n", "\n").lstrip("﻿").split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        block_match = _BLOCK_LINE.match(line)
        if block_match:
            report_id = block_match.group(1)
            current, entry = RawBlock(report_id, n), None
            if report_id in sheet.blocks:
                first = sheet.blocks[report_id]
                first.problems.append(
                    f"line {n}: a second block for {report_id} starts here (the first is at "
                    f"line {first.line}); each report has exactly one block"
                )
            else:
                sheet.blocks[report_id] = current
            continue
        if current is None:
            sheet.problems.append(f"line {n}: text before the first '== <id> ==' line")
            continue
        if line in ("[fix]", "[error]"):
            tag = line[1:-1]
            number = 1 + sum(e.tag == tag for e in current.entries)
            entry = RawEntry(tag, number, n)
            current.entries.append(entry)
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        where = entry.label if entry else "the report-level lines"
        if not sep or not key:
            current.problems.append(
                f"line {n}: expected 'key: value', '[fix]', '[error]' or '== <id> ==', got '{line}'"
            )
            continue
        allowed = REPORT_KEYS if entry is None else FIX_KEYS if entry.tag == "fix" else ERROR_KEYS
        if key not in allowed:
            hint = f"allowed keys: {', '.join(allowed)}"
            if entry is None and key in ERROR_KEYS + FIX_KEYS:
                hint += "; entry keys go after an [error] or [fix] line"
            elif entry is not None and key in REPORT_KEYS:
                hint = "report-level lines go before the first [fix] or [error] line"
            current.problems.append(f"line {n}: unknown key '{key}' in {where} ({hint})")
            continue
        if not value:
            current.problems.append(f"line {n}: '{key}' has an empty value in {where}")
            continue
        if entry is not None and key == "set":
            entry.sets.append((value, n))
            continue
        target = entry.fields if entry is not None else current.fields
        if key in target:
            current.problems.append(f"line {n}: '{key}' is given twice in {where}")
            continue
        target[key] = value
    return sheet


# Interpretation of entries


@dataclass
class Fix:
    label: str
    section: str
    find: str
    replace: str
    note: str


@dataclass
class ErrorEntry:
    label: str
    type: str
    severity: str
    description: str
    rationale: str
    severity_reason: str | None
    kind: str
    variant: str  # "text", "number" or "omission"
    section: str | None = None
    find: str | None = None
    replace: str | None = None
    quote: str | None = None
    sets: list[tuple[str, float]] = field(default_factory=list)
    quote_analyte: str | None = None
    remove_from: str | None = None
    remove: str | None = None
    remove_section: str | None = None
    anchor_section: str | None = None
    anchor: str | None = None
    anchor_analyte: str | None = None


def _missing(entry: RawEntry, keys: tuple[str, ...]) -> list[str]:
    return [f"{entry.label}: missing key '{k}'" for k in keys if k not in entry.fields]


def _analyte_problem(entry: RawEntry, key: str, name: str) -> list[str]:
    if name in ANALYTES:
        return []
    return [
        f"{entry.label}: {key} '{name}' is not an analyte; use the names in cbc_values "
        f"({', '.join(ANALYTES)})"
    ]


def interpret_fix(entry: RawEntry) -> tuple[Fix | None, list[str]]:
    problems = _missing(entry, FIX_KEYS)
    if problems:
        return None, problems
    f = entry.fields
    return Fix(entry.label, f["section"], f["find"], f["replace"], f["note"]), []


def _parse_sets(entry: RawEntry) -> tuple[list[tuple[str, float]], list[str]]:
    sets: list[tuple[str, float]] = []
    problems: list[str] = []
    for raw, line in entry.sets:
        name, eq, number = (part.strip() for part in raw.partition("="))
        if not eq or not name or not number:
            problems.append(f"line {line}: set must read '<analyte> = <number>', got '{raw}'")
            continue
        if name not in ANALYTES:
            problems += _analyte_problem(entry, "set", name)
            continue
        try:
            value = float(number)
        except ValueError:
            problems.append(f"line {line}: '{number}' is not a number")
            continue
        if not math.isfinite(value):
            problems.append(f"line {line}: '{number}' is not a finite number")
            continue
        if any(name == done for done, _ in sets):
            problems.append(f"line {line}: {name} is set twice in {entry.label}")
            continue
        sets.append((name, value))
    return sets, problems


def interpret_error(
    entry: RawEntry, modality: str, type_ids: tuple[str, ...]
) -> tuple[ErrorEntry | None, list[str]]:
    f = entry.fields
    problems = _missing(entry, ERROR_REQUIRED)
    if "type" in f and f["type"] not in type_ids:
        problems.append(
            f"{entry.label}: type '{f['type']}' is not a taxonomy id ({', '.join(type_ids)})"
        )
    if "severity" in f and f["severity"] not in SEVERITIES:
        problems.append(
            f"{entry.label}: severity '{f['severity']}' is not one of {', '.join(SEVERITIES)}"
        )
    kind = f.get("kind", "statement")
    if kind not in KINDS:
        problems.append(f"{entry.label}: kind '{kind}' is not statement or omission")
    present = set(f) | ({"set"} if entry.sets else set())
    variant: str | None
    if kind == "omission":
        variant = "omission"
        if "remove_section" in f and ("remove_from" in f or "remove" in f):
            problems.append(
                f"{entry.label}: give either remove_from with remove, or remove_section, not both"
            )
        elif "remove_section" not in f:
            problems += _missing(entry, ("remove_from", "remove"))
        if ("anchor" in f) == ("anchor_analyte" in f):
            problems.append(
                f"{entry.label}: an omission needs exactly one of anchor or anchor_analyte"
            )
        if "anchor_analyte" in f:
            if modality != "cbc":
                problems.append(f"{entry.label}: anchor_analyte applies only to CBC reports")
            else:
                problems += _analyte_problem(entry, "anchor_analyte", f["anchor_analyte"])
    elif present & set(NUMBER_KEYS):
        variant = "number"
        if modality != "cbc":
            problems.append(f"{entry.label}: set lines apply only to CBC reports")
        if not entry.sets:
            problems.append(f"{entry.label}: missing key 'set'")
        if "quote_analyte" in f:
            problems += _analyte_problem(entry, "quote_analyte", f["quote_analyte"])
    elif present & set(TEXT_KEYS):
        variant = "text"
        problems += _missing(entry, ("section", "find", "replace"))
    else:
        variant = None
        problems.append(
            f"{entry.label}: a statement error needs section, find and replace (a text change) "
            "or set lines (a CBC number change)"
        )
    if variant is not None:
        extra = present - set(ERROR_REQUIRED + ERROR_OPTIONAL) - set(VARIANT_KEYS[variant])
        problems += [
            f"{entry.label}: key '{k}' does not apply to {VARIANT_NAMES[variant]}"
            for k in sorted(extra)
        ]
    sets, set_problems = _parse_sets(entry) if variant == "number" else ([], [])
    problems += set_problems
    if problems or variant is None:
        return None, problems
    return (
        ErrorEntry(
            label=entry.label,
            type=f["type"],
            severity=f["severity"],
            description=f["description"],
            rationale=f["rationale"],
            severity_reason=f.get("severity_reason"),
            kind=kind,
            variant=variant,
            section=f.get("section"),
            find=f.get("find"),
            replace=f.get("replace"),
            quote=f.get("quote"),
            sets=sets,
            quote_analyte=f.get("quote_analyte"),
            remove_from=f.get("remove_from"),
            remove=f.get("remove"),
            remove_section=f.get("remove_section"),
            anchor_section=f.get("anchor_section"),
            anchor=f.get("anchor"),
            anchor_analyte=f.get("anchor_analyte"),
        ),
        [],
    )


# Text operations


def occurrences(text: str, needle: str) -> int:
    """Number of (possibly overlapping) occurrences of needle in text."""
    count, start = 0, 0
    while (i := text.find(needle, start)) >= 0:
        count += 1
        start = i + 1
    return count


def remove_span(text: str, start: int, end: int) -> str:
    """Delete text[start:end]; a whole line goes with its line break, and the join is tidied
    so that no double space, leading or trailing space, or empty line is left behind."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    if not text[line_start:start].strip() and not text[end:line_end].strip():
        lines = text.split("\n")
        index = text.count("\n", 0, line_start)
        del lines[index]

        def blank(i: int) -> bool:
            return not lines[i].strip()

        # Blank lines beside the removed line must not be left leading, trailing or doubled: a
        # first or last line takes the blank lines after or before it with it, and a line
        # between two runs of blank lines takes the run after it.
        if index == 0:
            while lines and blank(0):
                del lines[0]
        elif index == len(lines):
            while lines and blank(-1):
                del lines[-1]
        elif blank(index - 1):
            while index < len(lines) and blank(index):
                del lines[index]
        return "\n".join(lines)
    left, right = text[:start], text[end:]
    if left == "" or left.endswith("\n"):
        right = right.lstrip(" \t")
    elif right == "" or right.startswith("\n"):
        left = left.rstrip(" \t")
    elif left.endswith((" ", "\t")) and right.startswith((" ", "\t")):
        right = right.lstrip(" \t")
    elif left.endswith((" ", "\t")) and right[:1] in ".,;:)":
        left = left.rstrip(" \t")
    return left + right


def values_line(values_text: str, analyte: str) -> str:
    return values_text.split("\n")[ANALYTES.index(analyte)]


def word_count(text: str) -> int:
    """Whitespace-separated tokens that contain a letter or a digit (lone punctuation is not a
    word)."""
    return sum(any(ch.isalnum() for ch in token) for token in text.split())


# Applying one block


@dataclass
class BlockResult:
    report_id: str
    report: dict | None = None
    problems: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    verified: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems and self.report is not None


class _Planter:
    """Applies one block's entries to a working copy of one draft."""

    def __init__(self, row: SpecRow, draft: dict, readable: str) -> None:
        self.row = row
        self.readable = readable
        self.sections: dict[str, str] = dict(draft["sections"])
        self.cbc: dict | None = copy.deepcopy(draft.get("cbc_values"))
        self.problems: list[str] = []
        self.required = {name for name, req in SECTION_CONVENTIONS[row.modality] if req}

    def _text_section(self, label: str, key: str, name: str) -> str | None:
        if name not in self.sections:
            self.problems.append(
                f"{label}: {key} '{name}' is not a section of this report "
                f"(sections: {', '.join(self.sections)})"
            )
            return None
        if self.row.modality == "cbc" and name == "Values":
            self.problems.append(
                f"{label}: the Values text is generated from cbc_values and cannot be edited; "
                "change a number with set lines in an [error] entry"
            )
            return None
        return self.sections[name]

    def _locate(self, label: str, key: str, name: str, text: str, needle: str) -> int | None:
        count = occurrences(text, needle)
        if count == 1:
            return text.find(needle)
        advice = (
            f"add surrounding words from {self.readable} so that it is unique"
            if count
            else f"copy it exactly from {self.readable}"
        )
        self.problems.append(
            f"{label}: the {key} text occurs {count} times in '{name}' (it must occur exactly "
            f"once); {advice}"
        )
        return None

    def replace(self, label: str, name: str, find: str, replace: str) -> tuple[str, int] | None:
        """Replace the single occurrence; return the new section text and the start index."""
        text = self._text_section(label, "section", name)
        if text is None:
            return None
        if replace == find:
            self.problems.append(f"{label}: replace is the same as find")
            return None
        start = self._locate(label, "find", name, text, find)
        if start is None:
            return None
        new = text[:start] + replace + text[start + len(find) :]
        self.sections[name] = new
        return new, start

    def remove_text(self, label: str, name: str, needle: str) -> None:
        text = self._text_section(label, "remove_from", name)
        if text is None:
            return
        start = self._locate(label, "remove", name, text, needle)
        if start is None:
            return
        new = remove_span(text, start, start + len(needle))
        if new.strip():
            self.sections[name] = new
        elif name in self.required:
            self.problems.append(
                f"{label}: removing it would leave the required section '{name}' empty"
            )
        else:
            del self.sections[name]  # an optional section left empty is dropped

    def remove_section(self, label: str, name: str) -> None:
        if name not in self.sections:
            self.problems.append(
                f"{label}: remove_section '{name}' is not a section of this report"
            )
        elif name in self.required:
            self.problems.append(
                f"{label}: '{name}' is a required section and cannot be removed; "
                "use remove_from with remove to delete text from it"
            )
        else:
            del self.sections[name]

    def rendered_values(self) -> str:
        return render_cbc_values(CBCValues.model_validate(self.cbc))

    def apply_fix(self, fix: Fix) -> None:
        self.replace(fix.label, fix.section, fix.find, fix.replace)

    def apply_error(self, err: ErrorEntry, number: int) -> dict | None:
        before = len(self.problems)
        section, quote = "", ""
        if err.variant == "text":
            assert err.section and err.find and err.replace
            done = self.replace(err.label, err.section, err.find, err.replace)
            section = err.section
            if done is not None:
                new, start = done
                if err.quote:
                    quote = err.quote
                elif section == "Synoptic summary":
                    line_start = new.rfind("\n", 0, start) + 1
                    line_end = new.find("\n", start + len(err.replace))
                    quote = new[line_start : None if line_end == -1 else line_end]
                elif word_count(err.replace) >= MIN_QUOTE_WORDS:
                    quote = err.replace
                else:
                    self.problems.append(
                        f"{err.label}: the replace text has fewer than {MIN_QUOTE_WORDS} words, "
                        "so it cannot serve as the quoted sentence; add a quote: line with the "
                        "full sentence as it reads after the change"
                    )
        elif err.variant == "number":
            assert self.cbc is not None
            for name, value in err.sets:
                self.cbc[name]["value"] = value  # the stored number only; nothing is re-derived
            self.sections["Values"] = self.rendered_values()
            section = "Values"
            quote = values_line(self.sections["Values"], err.quote_analyte or err.sets[0][0])
        else:
            if err.remove_section:
                self.remove_section(err.label, err.remove_section)
            else:
                assert err.remove_from and err.remove
                self.remove_text(err.label, err.remove_from, err.remove)
            section = err.anchor_section or DEFAULT_ANCHOR_SECTION[self.row.modality]
            if err.anchor_analyte:
                if section != "Values" or self.cbc is None:
                    self.problems.append(f"{err.label}: anchor_analyte needs anchor_section Values")
                else:
                    quote = values_line(self.rendered_values(), err.anchor_analyte)
            else:
                quote = err.anchor or ""
        if len(self.problems) > before:
            return None
        return {
            "error_id": f"{self.row.id}-E{number}",
            "type": err.type,
            "section": section,
            "quoted_sentence": quote,
            "severity": err.severity,
            "severity_reason": err.severity_reason,
            "description": err.description,
            "rationale": err.rationale,
            "kind": err.kind,
        }


def _report_level(block: RawBlock) -> tuple[bool, str | None, list[str]]:
    problems = []
    verified_raw = block.fields.get("verified")
    verified = verified_raw == "yes"
    if verified_raw is None:
        problems.append("missing key 'verified' (yes or no)")
    elif verified_raw not in ("yes", "no"):
        problems.append(f"verified must be yes or no, not '{verified_raw}'")
    verified_on = block.fields.get("verified_on")
    if verified_on is not None:
        try:
            if not _DATE.match(verified_on):
                raise ValueError
            date.fromisoformat(verified_on)
        except ValueError:
            problems.append(f"verified_on '{verified_on}' is not a date written YYYY-MM-DD")
        if verified_raw == "no":
            problems.append("verified_on is given but verified is no")
    elif verified:
        problems.append("verified is yes, so verified_on (YYYY-MM-DD) is required")
    return verified, verified_on, problems


def apply_block(
    row: SpecRow,
    draft: dict | None,
    block: RawBlock | None,
    taxonomy: Taxonomy,
    readable: str = "the readable draft",
    report_path: str = FILE_PLACEHOLDER,
    draft_path: str = "the draft file",
    draft_problem: str | None = None,
) -> BlockResult:
    """Apply one block (None: no block, so no changes and verified no) to one draft.

    draft None means no draft: draft_problem says why (a file that could not be read), and
    without it the draft file was not found."""
    result = BlockResult(row.id)
    if block is None:
        block = RawBlock(row.id, 0, {"verified": "no"})
    # Structural problems stop the block before anything is applied.
    verified, verified_on, structural = _report_level(block)
    structural = list(block.problems) + structural
    fixes: list[Fix] = []
    errors: list[ErrorEntry] = []
    for entry in block.entries:
        if entry.tag == "fix":
            fix, entry_problems = interpret_fix(entry)
            if fix:
                fixes.append(fix)
        else:
            err, entry_problems = interpret_error(entry, row.modality, tuple(taxonomy.type_ids()))
            if err:
                errors.append(err)
        structural += entry_problems
    if draft is None:
        structural.append(draft_problem or f"draft not found: {draft_path}")
    else:
        try:
            parsed = Report.model_validate(draft)
        except ValidationError as exc:
            structural.append(
                f"{draft_path} does not parse as a report ({exc.error_count()} problem(s))"
            )
        else:
            for attr in ("id", "modality", "split"):
                if getattr(parsed, attr) != getattr(row, attr):
                    structural.append(
                        f"the draft's {attr} is {getattr(parsed, attr)}, "
                        f"the spec says {getattr(row, attr)}"
                    )
    planting: list[str] = []
    n_errors = sum(e.tag == "error" for e in block.entries)
    if row.is_clean_control and n_errors:
        planting.append(
            f"{row.id} is a clean control in the spec, but the block has {n_errors} [error] "
            f"entr{'y' if n_errors == 1 else 'ies'}"
        )
    if not row.is_clean_control and n_errors == 0:
        planting.append(
            "no planted errors yet (the spec marks this report as planted; add at least one "
            "[error] entry)"
        )
    if structural or draft is None:
        result.problems = structural + planting
        return result

    planter = _Planter(row, draft, readable)
    for fix in fixes:
        planter.apply_fix(fix)
    planted = [planter.apply_error(err, i) for i, err in enumerate(errors, start=1)]
    problems = planting + planter.problems
    if problems:
        result.problems = problems
        return result

    report = copy.deepcopy(draft)
    report["sections"] = planter.sections
    if planter.cbc is not None:
        report["cbc_values"] = planter.cbc
    report["is_clean_control"] = row.is_clean_control
    report["errors"] = planted
    report["provenance"] = {
        "drafted_by": draft["provenance"]["drafted_by"],
        "drafted_at": draft["provenance"]["drafted_at"],
        "edited_by": "owner",
        "verified": verified,
        "verified_at": verified_on if verified else None,
    }
    try:
        model = Report.model_validate(report)
    except ValidationError as exc:
        reasons = [
            f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()
        ]
        result.problems = [f"validation: {r}" for r in reasons]
        return result
    # A built report is a final report: every validator rule runs on it, check_clean_control
    # included (its condition is also checked above, in plain words, before anything applies).
    reasons = check_report(model, taxonomy)
    if reasons:
        result.problems = [
            f"validation: {r.replace(FILE_PLACEHOLDER, report_path)}" for r in reasons
        ]
        return result
    result.report = report
    result.fixes = fixes
    result.verified = verified
    if not row.is_clean_control:
        planted_types = sorted({e["type"] for e in report["errors"]})
        planned = sorted(set(row.planned_error_types))
        if planted_types != planned:
            result.notices.append(
                f"{row.id}: planted types {', '.join(planted_types)} differ from the spec's "
                f"planned types {', '.join(planned)}"
            )
    return result


# A whole sheet


@dataclass
class PlantRun:
    results: list[BlockResult]
    problems: list[str]  # sheet-level: lines outside blocks, blocks for ids not in the spec

    @property
    def ok(self) -> bool:
        return not self.problems and all(r.ok for r in self.results)

    @property
    def notices(self) -> list[str]:
        return [n for r in self.results for n in r.notices]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def plan(rows: list[SpecRow], sheet_text: str, root: Path, taxonomy: Taxonomy) -> PlantRun:
    """Parse the sheet and apply every block in memory, in spec order. Writes nothing."""
    sheet = parse_sheet(sheet_text)
    known = {row.id for row in rows}
    problems = list(sheet.problems)
    problems += [
        f"line {block.line}: block '== {rid} ==' is for an id that is not in the spec"
        for rid, block in sheet.blocks.items()
        if rid not in known
    ]
    drafts = root / DRAFTS_DIR
    results = []
    for row in rows:
        draft_path = drafts / f"{row.id}.json"
        draft, draft_problem = load_draft(draft_path, _rel(draft_path, root))
        results.append(
            apply_block(
                row,
                draft,
                sheet.blocks.get(row.id),
                taxonomy,
                readable=_rel(drafts / READABLE_DIR / f"{row.id}.md", root),
                report_path=_rel(root / REPORTS_DIR / f"{row.id}.json", root),
                draft_path=_rel(draft_path, root),
                draft_problem=draft_problem,
            )
        )
    return PlantRun(results, problems)


_JSON_KINDS = {
    "list": "an array",
    "str": "a string",
    "int": "a number",
    "float": "a number",
    "bool": "true or false",
    "NoneType": "null",
}


def load_draft(path: Path, shown: str) -> tuple[dict | None, str | None]:
    """(the draft, None); or (None, a problem in plain words) when the file cannot be read as a
    JSON object; or (None, None) when there is no file."""
    if not path.is_file():
        return None, None
    try:
        data = read_report_json(path)
    except json.JSONDecodeError as exc:
        where = f"at line {exc.lineno}, column {exc.colno}"
        return None, f"{shown} does not parse as JSON ({exc.msg} {where})"
    except UnicodeDecodeError as exc:
        return None, f"{shown} is not UTF-8 text ({exc.reason} at byte {exc.start})"
    except ValueError as exc:  # any other refusal by the JSON reader, e.g. a too-long integer
        return None, f"{shown} does not parse as JSON ({exc})"
    except RecursionError:
        return None, f"{shown} does not parse as JSON (nested too deeply)"
    except OSError as exc:
        return None, f"{shown} cannot be read ({exc.strerror or exc})"
    if not isinstance(data, dict):
        kind = _JSON_KINDS.get(type(data).__name__, type(data).__name__)
        return None, f"{shown} is not a JSON object (it holds {kind})"
    try:  # a \ud83d-style escape decodes to a lone surrogate, which no file can hold
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as exc:
        return None, f"{shown} holds text that cannot be written as UTF-8 ({exc.reason})"
    return data, None


def check_lines(run: PlantRun) -> list[str]:
    lines = [f"sheet {p}" for p in run.problems]
    for r in run.results:
        lines += [f"{r.report_id} OK"] if r.ok else [f"{r.report_id} {p}" for p in r.problems]
    return lines


# Outputs


def review_markdown(result: BlockResult) -> str:
    """Proofreading view of one built report: final text, then fixes and planted errors."""
    assert result.report is not None
    report = result.report
    prov = report["provenance"]
    verified = f"yes, on {prov['verified_at']}" if prov["verified"] else "no"
    lines = [
        f"# {report['id']} (review)",
        "",
        f"Generated by `pathqc-eval plant` from {SHEET_FILE.as_posix()}. To change anything, "
        "edit the sheet, never this file or the report.",
        "",
        f"Verified: {verified}",
        "",
    ]
    for name, text in report["sections"].items():
        lines += [f"## {name}", text, ""]
    lines += ["## Fixes", ""]
    if not result.fixes:
        lines += ["None.", ""]
    for i, fix in enumerate(result.fixes, start=1):
        lines += [
            f"{i}. {fix.section}",
            f"   find: {fix.find}",
            f"   replace: {fix.replace}",
            f"   note: {fix.note}",
            "",
        ]
    lines += ["## Planted errors", ""]
    if not report["errors"]:
        lines += ["None.", ""]
    for err in report["errors"]:
        lines += [
            f"{err['error_id']} | {err['type']} | {err['severity']} | {err['kind']} | "
            f"{err['section']}",
            f"   quote: {err['quoted_sentence']}",
            f"   description: {err['description']}",
            f"   rationale: {err['rationale']}",
        ]
        if err["severity_reason"]:
            lines.append(f"   severity_reason: {err['severity_reason']}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_outputs(run: PlantRun, root: Path) -> list[str]:
    """Write each block without problems; leave every other report file untouched."""
    reports = root / REPORTS_DIR
    review = reports / REVIEW_DIR
    reports.mkdir(parents=True, exist_ok=True)
    review.mkdir(exist_ok=True)
    lines = [f"sheet {p}" for p in run.problems]
    for r in run.results:
        if r.ok:
            assert r.report is not None
            write_report_json(reports / f"{r.report_id}.json", r.report)
            (review / f"{r.report_id}.md").write_text(
                review_markdown(r), encoding="utf-8", newline="\n"
            )
            lines.append(
                f"{r.report_id} built | {len(r.report['errors'])} planted error(s), "
                f"{len(r.fixes)} fix(es) | verified {'yes' if r.verified else 'no'}"
            )
        else:
            lines.append(f"{r.report_id} NOT UPDATED")
            lines += [f"  {p}" for p in r.problems]
    return lines


TEMPLATE_HEADER = """\
# Planting sheet (decision 37). Written by the owner only; no model writes planting content.
# `uv run pathqc-eval plant --check` checks it; `uv run pathqc-eval plant` applies it to the
# drafts in data/drafts/ (never modified) and writes data/reports/ (never edited by hand).
#
# Format
# - Lines starting with '#' are comments; blank lines are ignored.
# - '== H-001 ==' starts a report block: report-level lines, then [fix] and [error] entries.
# - Every other line is 'key: value', split at the first colon (values may contain colons).
# - Report level: verified: yes|no (required); verified_on: YYYY-MM-DD (required when yes).
# - [fix] corrects the draft without planting an error (text sections only, never Values):
#     section, find, replace, note
# - [error] needs type, severity, description, rationale; optional severity_reason and
#   kind (statement, the default, or omission). Then one of:
#     text change:        section, find, replace; optional quote
#     CBC number change:  set: <analyte> = <number> (one line per analyte, names as in
#                         cbc_values, e.g. MCHC, Neutrophils_pct); optional quote_analyte
#     omission:           remove_from + remove, or remove_section (an optional section);
#                         then anchor (text) or, for CBC, anchor_analyte; optional
#                         anchor_section (default Values for CBC, Synoptic summary otherwise)
# - find and remove must occur exactly once in the section; copy them from
#   data/drafts/_readable/<id>.md (made by `uv run pathqc-eval readable data/drafts`).
# - Quoted sentence: quote if given; in Synoptic summary the whole changed line; otherwise
#   the replace text, which then needs at least five words. Number change: the rendered
#   Values line. Omission: the anchor.
# - Entries apply in sheet order, fixes first, then errors (error ids E1, E2, ... in order).
"""


def template(rows: list[SpecRow]) -> str:
    """The empty sheet: format notes, then one block per spec row with verified: no."""
    parts = [TEMPLATE_HEADER]
    for row in rows:
        kind = "clean control" if row.is_clean_control else "planted"
        planned = ", ".join(row.planned_error_types) or "none"
        lines = [
            f"== {row.id} ==",
            f"# {row.split} | {kind} | planned types: {planned}",
            "verified: no",
        ]
        if not row.is_clean_control:
            lines += [
                "# Example (delete the leading '# ' on each line to use it):",
                "# [error]",
                f"# type: {row.planned_error_types[0]}",
                "# severity: <critical, major or minor>",
                "# section: <section name>",
                f"# find: <text copied exactly from data/drafts/_readable/{row.id}.md>",
                "# replace: <the text as it should read with the error>",
                "# description: <what is wrong>",
                "# rationale: <why it is an error>",
            ]
        parts.append("\n".join(lines) + "\n")
    return "\n".join(parts)
