"""Lenient reading of the evaluated model's output into findings (EVAL-04 step 3).

Owner decision (lenient reading): extra keys are ignored and recorded; an unusable severity or
confidence becomes null (excluded from calibration, counted); a finding without a usable
quoted_sentence, section or category is dropped and counted. The harness keeps the raw output
of every call. The strict schema.Finding model is unchanged; runs store ParsedFinding.
"""

from __future__ import annotations

import json
import math
import re
from typing import Literal

from pydantic import Field

from pathqc_eval.schema import Severity, StrictModel

REQUIRED_STRINGS = ("quoted_sentence", "section", "category")
KNOWN_KEYS = (*REQUIRED_STRINGS, "severity", "confidence", "rationale")
SEVERITIES = ("critical", "major", "minor")
_SHOWN = 60  # characters of an unusable value quoted in a note
# json.loads joins every valid surrogate pair, so a surrogate left in a str is unpaired.
_SURROGATE = re.compile("[\ud800-\udfff]")


class ParsedFinding(StrictModel):
    """One finding as a run stores it; severity and confidence may be null."""

    quoted_sentence: str = Field(min_length=1)
    section: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: Severity | None
    confidence: float | None = Field(ge=0.0, le=1.0)
    rationale: str


class DroppedFinding(StrictModel):
    index: int  # 1-based position in the model's list of findings
    reason: str


class ParseResult(StrictModel):
    status: Literal["valid", "invalid"]
    findings: list[ParsedFinding] = Field(default_factory=list)
    dropped: list[DroppedFinding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _shown(value: object) -> str:
    text = repr(value)
    return text if len(text) <= _SHOWN else text[: _SHOWN - 3] + "..."


def writable_text(text: str) -> tuple[str, bool]:
    """The text with every unpaired surrogate replaced by U+FFFD, and whether one was.

    An escaped unpaired surrogate (\\ud800) in the model's JSON parses to a str that cannot be
    written as UTF-8, so the call could not be logged."""
    cleaned = _SURROGATE.sub("�", text)
    return cleaned, cleaned != text


def _strip_fence(text: str) -> str:
    """The content of a surrounding code fence, or the text itself. A fence is a run of 3 or
    more backticks or tildes (CommonMark); the closing run is at least as long as the opening
    one, and the rest of the opening line is an info string such as json. Linear in the
    length of the text: an output that is one long run of fence characters is simply read as
    not JSON."""
    stripped = text.strip()
    for char in "`~":
        opening = len(stripped) - len(stripped.lstrip(char))
        if opening < 3:
            continue
        closing = len(stripped) - len(stripped.rstrip(char))
        if closing < opening or opening + closing >= len(stripped):
            return stripped
        body = stripped[opening : len(stripped) - closing]
        first, newline, rest = body.partition("\n")
        starts = [i for i in (first.find("{"), first.find("[")) if i >= 0]
        if starts:  # the content begins on the opening line, after any info string
            return (first[min(starts) :] + newline + rest).strip()
        return (rest if newline else body).strip()
    return stripped


def _severity(value: object) -> str | None:
    if isinstance(value, str) and value.strip().lower() in SEVERITIES:
        return value.strip().lower()
    return None


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None


def _invalid(reason: str) -> ParseResult:
    return ParseResult(status="invalid", notes=[reason])


def parse_findings(text: str) -> ParseResult:
    """Read one output: `{"findings": [...]}` or a bare list, optionally in a code fence.

    Anything else, or JSON that does not parse, is invalid; an empty list is valid.
    """
    try:
        data = json.loads(_strip_fence(text))
    except (ValueError, RecursionError) as exc:  # json.JSONDecodeError is a ValueError
        return _invalid(f"output is not JSON ({type(exc).__name__})")
    notes: list[str] = []
    if isinstance(data, dict):
        if not isinstance(data.get("findings"), list):
            return _invalid('output is a JSON object without a "findings" list')
        extra = sorted(writable_text(key)[0] for key in data if key != "findings")
        if extra:
            notes.append(f"top level: extra keys ignored: {', '.join(extra)}")
        items = data["findings"]
    elif isinstance(data, list):
        items = data
    else:
        return _invalid("output is JSON but neither an object with a findings list nor a list")

    findings: list[ParsedFinding] = []
    dropped: list[DroppedFinding] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            dropped.append(DroppedFinding(index=i, reason=f"not an object ({type(item).__name__})"))
            continue
        # Extra keys are noted for dropped findings too: a renamed key explains the drop.
        extra = sorted(writable_text(key)[0] for key in item if key not in KNOWN_KEYS)
        if extra:
            notes.append(f"finding {i}: extra keys ignored: {', '.join(extra)}")
        unusable = [
            key
            for key in REQUIRED_STRINGS
            if not (isinstance(item.get(key), str) and item[key].strip())
        ]
        if unusable:
            dropped.append(DroppedFinding(index=i, reason=f"no usable {', '.join(unusable)}"))
            continue
        severity = _severity(item.get("severity"))
        if severity is None:
            shown = _shown(item["severity"]) if "severity" in item else "missing"
            notes.append(f"finding {i}: severity {shown} is not critical, major or minor; null")
        confidence = _confidence(item.get("confidence"))
        if confidence is None:
            shown = _shown(item["confidence"]) if "confidence" in item else "missing"
            notes.append(f"finding {i}: confidence {shown} is not a number from 0 to 1; null")
        rationale = item.get("rationale")
        if not isinstance(rationale, str):
            if "rationale" in item:
                notes.append(f"finding {i}: rationale {_shown(rationale)} is not text; empty")
            rationale = ""
        texts: dict[str, str] = {}
        for key in (*REQUIRED_STRINGS, "rationale"):
            value = rationale if key == "rationale" else item[key]
            texts[key], replaced = writable_text(value.strip())
            if replaced:
                notes.append(f"finding {i}: {key} held unpaired surrogates; replaced with U+FFFD")
        findings.append(ParsedFinding(**texts, severity=severity, confidence=confidence))
    return ParseResult(status="valid", findings=findings, dropped=dropped, notes=notes)
