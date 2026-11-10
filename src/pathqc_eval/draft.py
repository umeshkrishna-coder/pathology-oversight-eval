"""Drafting: approved spec rows -> draft reports with claude-haiku-5-5 (decision 25).

The drafting model sees only the system prompt in prompts/drafting/ and a user message built
from the row's brief, specimen_type or scenario, sex and age; a CBC message also lists the
reference ranges for the row's sex from data/specs/cbc_reference_ranges.json (EVAL-02d). It
never sees the taxonomy or the planned error types and is never asked to include errors; the
owner plants every error later.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from pydantic import Field, ValidationError

from pathqc_eval.cbc import CBCPrimary, ReferenceRanges, derive_cbc, load_reference_ranges
from pathqc_eval.cost import cost_usd
from pathqc_eval.io import append_jsonl, write_report_json
from pathqc_eval.render import DECIMALS, analyte_label, render_cbc_values
from pathqc_eval.schema import (
    CBC_UNITS,
    SCHEMA_VERSION,
    SECTION_CONVENTIONS,
    CBCValues,
    Report,
    StrictModel,
)
from pathqc_eval.spec import Sex, SpecRow
from pathqc_eval.taxonomy import REPO_ROOT, load_taxonomy
from pathqc_eval.validate import check_report

DRAFT_MODEL = "claude-haiku-5-5"
DRAFT_MAX_TOKENS = 16000
# Reasoning effort (owner decision, EVAL-02b). Haiku 5.5 thinks adaptively by default; effort
# goes in output_config. No sampling parameter is sent.
DRAFT_EFFORT = "high"
PROMPTS_DIR = REPO_ROOT / "prompts" / "drafting"
DEFAULT_DRAFTS_DIR = REPO_ROOT / "data" / "drafts"
EST_INPUT_TOKENS = 1200
EST_OUTPUT_TOKENS = 8000  # including thinking at high effort
STAGING_EDITION_LINE = "Staging edition: AJCC 8th edition"
_EPS = 1e-12


@dataclass(frozen=True)
class DraftResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None


class DraftClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int) -> DraftResponse: ...


class MissingAPIKeyError(RuntimeError):
    pass


def draft_request_args(model: str, system: str, user: str, max_tokens: int) -> dict:
    """Keyword arguments for one drafting messages.create call."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": DRAFT_EFFORT},
    }


class AnthropicDraftClient:
    """Real client; constructed only when a real drafting run is requested (EVAL-02b)."""

    def __init__(self, model: str = DRAFT_MODEL) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise MissingAPIKeyError(
                "ANTHROPIC_API_KEY is not set; the owner adds it to .env before a real run"
            )
        import anthropic

        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    def complete(self, system: str, user: str, max_tokens: int) -> DraftResponse:
        message = self._client.messages.create(
            **draft_request_args(self.model, system, user, max_tokens)
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        return DraftResponse(
            text=text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            stop_reason=message.stop_reason,
        )


class FakeDraftClient:
    """Test double: returns canned texts in order and records every call."""

    def __init__(
        self,
        texts: list[str],
        model: str = DRAFT_MODEL,
        input_tokens: int = EST_INPUT_TOKENS,
        output_tokens: int = EST_OUTPUT_TOKENS,
    ) -> None:
        self._texts = list(texts)
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system: str, user: str, max_tokens: int) -> DraftResponse:
        self.calls.append((system, user, max_tokens))
        return DraftResponse(
            text=self._texts.pop(0),
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            stop_reason="end_turn",
        )


# Prompts


def system_prompt(modality: str) -> str:
    return (PROMPTS_DIR / f"{modality}.md").read_text(encoding="utf-8")


def _bound(value: float, decimals: int) -> str:
    """A stored range bound with the Values text's decimals, or in full when those decimals
    would round it (a rounded bound could show a wider range than the one stored)."""
    shown = f"{value:.{decimals}f}"
    return shown if float(shown) == value else repr(value)


def reference_ranges_block(sex: Sex, ranges: ReferenceRanges) -> str:
    """`Reference ranges (adult <sex>):`, then one `<label>: <low>–<high> <unit>` line per
    analyte in CBCValues order, with the labels, decimals and units of the Values text."""
    lines = [f"Reference ranges (adult {sex}):"]
    for name in CBCValues.model_fields:
        rng = ranges.for_field(name, sex)
        d = DECIMALS[name]
        low, high = _bound(rng.low, d), _bound(rng.high, d)
        lines.append(f"{analyte_label(name)}: {low}–{high} {CBC_UNITS[name]}")
    return "\n".join(lines)


def user_message(row: SpecRow, ranges: ReferenceRanges | None = None) -> str:
    """Built from brief, specimen_type or scenario, sex and age, and nothing else in the row.

    A CBC message ends with the reference ranges for the row's sex (EVAL-02d), from `ranges`
    or else from data/specs/cbc_reference_ranges.json. The histopathology message is unchanged.
    """
    subject = (
        f"Specimen type: {row.specimen_type}"
        if row.modality == "histopathology"
        else f"Scenario: {row.scenario}"
    )
    message = f"{subject}\nPatient: {row.sex}, {row.age} years\nBrief: {row.brief}"
    if row.modality == "cbc":
        ranges = ranges if ranges is not None else load_reference_ranges()
        message += "\n\n" + reference_ranges_block(row.sex, ranges)
    return message


def build_messages(row: SpecRow, ranges: ReferenceRanges | None = None) -> tuple[str, str]:
    return system_prompt(row.modality), user_message(row, ranges)


# Parsing and assembly


class DraftParseError(ValueError):
    pass


class CBCDraftOutput(StrictModel):
    primary: CBCPrimary
    interpretation: str = Field(min_length=1)
    comment: str | None = None


_FENCE = re.compile(r"^```[A-Za-z]*\s*\n?(.*?)\n?```$", re.DOTALL)


def _load_json_object(text: str) -> dict:
    stripped = text.strip()
    match = _FENCE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise DraftParseError(f"not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DraftParseError("JSON is not an object")
    return data


def _histopathology_sections(data: dict) -> dict[str, str]:
    convention = SECTION_CONVENTIONS["histopathology"]
    known = {name for name, _ in convention}
    unknown = sorted(set(data) - known)
    if unknown:
        raise DraftParseError(f"unknown sections {unknown}")
    sections: dict[str, str] = {}
    for name, required in convention:
        value = data.get(name)
        if value is not None and not isinstance(value, str):
            raise DraftParseError(f"section '{name}' is not text")
        if value is None or not value.strip():
            if required:
                raise DraftParseError(f"required section '{name}' is missing")
            continue
        sections[name] = value.strip()
    lines = [line.strip() for line in sections["Synoptic summary"].splitlines() if line.strip()]
    if not lines or lines[-1] != STAGING_EDITION_LINE:
        raise DraftParseError(f"Synoptic summary does not end with '{STAGING_EDITION_LINE}'")
    return sections


def _assemble(
    row: SpecRow, response: DraftResponse, today: date, ranges: ReferenceRanges
) -> tuple[dict, list[str]]:
    data = _load_json_object(response.text)
    notes: list[str] = []
    report: dict = {"id": row.id, "modality": row.modality, "split": row.split}
    if row.modality == "histopathology":
        report["specimen_type"] = row.specimen_type
        report["sections"] = _histopathology_sections(data)
    else:
        try:
            output = CBCDraftOutput.model_validate(data)
        except ValidationError as exc:
            raise DraftParseError(f"unexpected CBC shape ({exc.error_count()} problem(s))") from exc
        try:
            values, notes = derive_cbc(output.primary, row.sex, ranges)
        except ValueError as exc:
            raise DraftParseError(str(exc)) from exc
        report["scenario"] = row.scenario
        sections = {
            "Values": render_cbc_values(values),
            "Interpretation": output.interpretation.strip(),
        }
        if output.comment and output.comment.strip():
            sections["Comment/recommendation"] = output.comment.strip()
        report["sections"] = sections
        report["cbc_values"] = values.model_dump(mode="json")
    report |= {
        "is_clean_control": row.is_clean_control,
        "errors": [],
        "provenance": {
            "drafted_by": response.model,
            "drafted_at": today.isoformat(),
            "edited_by": "owner",
            "verified": False,
            "verified_at": None,
        },
        "schema_version": SCHEMA_VERSION,
    }
    try:
        problems = check_report(Report.model_validate(report), load_taxonomy(), drafts=True)
    except ValidationError as exc:
        raise DraftParseError(f"draft does not validate ({exc.error_count()} problem(s))") from exc
    if problems:
        raise DraftParseError(f"draft does not validate: {'; '.join(problems)}")
    return report, notes


def draft_report(
    row: SpecRow, response: DraftResponse, today: date, ranges: ReferenceRanges
) -> dict:
    """Parse one response and assemble a Report dict that validates as a draft."""
    return _assemble(row, response, today, ranges)[0]


# Running


def estimate_usd(n_rows: int) -> float:
    return cost_usd(DRAFT_MODEL, n_rows * EST_INPUT_TOKENS, n_rows * EST_OUTPUT_TOKENS)


def dry_run_lines(rows: list[SpecRow]) -> list[str]:
    lines = ["DRY RUN: no client is constructed and no API call is made."]
    for modality in ("histopathology", "cbc"):
        first = next((r for r in rows if r.modality == modality), None)
        if first is None:
            continue
        system, user = build_messages(first)
        lines += [
            f"===== {first.id} system prompt (prompts/drafting/{modality}.md) =====",
            system.rstrip("\n"),
            f"===== {first.id} user message =====",
            user,
        ]
    lines.append(
        f"Estimate: {len(rows)} rows × ~{EST_INPUT_TOKENS:,} input + ~{EST_OUTPUT_TOKENS:,} "
        f"output tokens at Haiku prices = ${estimate_usd(len(rows)):.4f}"
    )
    return lines


def summary_line(row: SpecRow, report: dict, notes: list[str]) -> str:
    words = sum(len(text.split()) for text in report["sections"].values())
    line = f"{row.id} | {row.subject} | {words} words"
    if row.modality == "cbc":
        v = report["cbc_values"]
        line += (
            f" | MCV {v['MCV']['value']:g} MCH {v['MCH']['value']:g} "
            f"MCHC {v['MCHC']['value']:g} | notes: {'; '.join(notes) or 'none'}"
        )
    return line


@dataclass
class RunSummary:
    drafted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    stopped_before: str | None = None
    total_usd: float = 0.0


def run_drafts(
    rows: list[SpecRow],
    client: DraftClient,
    *,
    drafts_dir: Path,
    ranges: ReferenceRanges,
    today: date,
    cost_gate: float,
    force: bool = False,
    out: Callable[[str], None] = print,
) -> RunSummary:
    """Draft each row: one retry on a parse failure, every call logged, cost-gated."""
    summary = RunSummary()
    drafts_dir.mkdir(parents=True, exist_ok=True)
    # Projected cost of the next call: the dearest call so far, or the estimate before any call.
    next_call = cost_usd(DRAFT_MODEL, EST_INPUT_TOKENS, EST_OUTPUT_TOKENS)
    for row in rows:
        target = drafts_dir / f"{row.id}.json"
        if target.exists() and not force:
            summary.skipped.append(row.id)
            out(f"skip {row.id}: {target.name} exists (use --force to redraft)")
            continue
        system, user = build_messages(row, ranges)
        assembled = None
        raw_text = ""
        for attempt in (1, 2):
            if summary.total_usd + next_call > cost_gate + _EPS:
                summary.stopped_before = row.id
                out(
                    f"cost gate: stopping before {row.id} (attempt {attempt}); "
                    f"spent ${summary.total_usd:.4f}, next call ~${next_call:.4f}, "
                    f"gate ${cost_gate:.2f}"
                )
                out(f"total cost ${summary.total_usd:.4f}")
                return summary
            started = time.perf_counter()
            response = client.complete(system, user, DRAFT_MAX_TOKENS)
            duration = time.perf_counter() - started
            call_usd = cost_usd(response.model, response.input_tokens, response.output_tokens)
            summary.total_usd += call_usd
            next_call = max(next_call, call_usd)
            append_jsonl(
                drafts_dir / "_calls.jsonl",
                {
                    "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
                    "id": row.id,
                    "model": response.model,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": round(call_usd, 6),
                    "stop_reason": response.stop_reason,
                    "duration_s": round(duration, 2),
                    "attempt": attempt,
                },
            )
            out(f"  {row.id} attempt {attempt}: ${call_usd:.4f}; running ${summary.total_usd:.4f}")
            try:
                assembled = _assemble(row, response, today, ranges)
                break
            except DraftParseError as exc:
                raw_text = response.text
                out(f"  {row.id} attempt {attempt}: unusable response ({exc})")
        if assembled is None:
            failed_dir = drafts_dir / "_failed"
            failed_dir.mkdir(exist_ok=True)
            failed_path = failed_dir / f"{row.id}.txt"
            failed_path.write_text(raw_text, encoding="utf-8", newline="\n")
            summary.failed.append(row.id)
            out(f"FAIL {row.id}: two unusable responses; raw text in {failed_path}")
            continue
        report, notes = assembled
        write_report_json(target, report)
        summary.drafted.append(row.id)
        out(summary_line(row, report, notes))
    out(f"total cost ${summary.total_usd:.4f}")
    return summary
