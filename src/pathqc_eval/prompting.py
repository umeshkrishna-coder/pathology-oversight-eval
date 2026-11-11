"""Message assembly for the evaluated model, in both conditions (decisions 4, 13 and 35).

The user message is the report text alone, identical in both conditions. The plain system
prompt never mentions the taxonomy; the structured system prompt is the owner's text for the
report's modality, then that modality's taxonomy, then the output block.
"""

from __future__ import annotations

import re
from pathlib import Path

from pathqc_eval.schema import Condition, Modality, Report
from pathqc_eval.taxonomy import REPO_ROOT, Taxonomy, load_taxonomy

DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts"
PLAIN_PROMPT = "plain.md"
STRUCTURED_OUTPUT_PROMPT = "structured_output.md"
STRUCTURED_OWNER_PROMPTS: dict[str, str] = {
    "histopathology": "structured_histopathology.md",
    "cbc": "structured_cbc.md",
}
OWNER_TEXT_PLACEHOLDER = "<<OWNER TEXT REQUIRED>>"
TAXONOMY_HEADING = "## Error taxonomy"
# Owner decision (EVAL-04): only label forms of the split are refused: `split:` followed by dev
# or scored, or the quoted key "split". The bare words occur in ordinary report text ("HER2
# scored 2+", a core received 'split'). Any case; spaces, quotes (straight or typographic) and
# markdown emphasis may stand around the colon ("**Split:** scored", {'split': 'dev'}); a
# prefix joined to the label ("data_split: dev") is still a label. The key is "split" in
# double quotes, or 'split' in any quotes followed by a colon.
_QUOTES = "\"'“”‘’"
_AROUND = rf"[\s*_`{_QUOTES}]*"
# After the value no letter or digit may follow; "_" may (underscore emphasis: "_dev_").
_SPLIT_LABEL = re.compile(rf"split{_AROUND}:{_AROUND}(dev|scored)(?![^\W_])", re.IGNORECASE)
_SPLIT_KEY = re.compile(rf'"split"|[{_QUOTES}]split[{_QUOTES}]\s*:', re.IGNORECASE)


def read_prompt(path: Path | str) -> str:
    """A prompt file's text with CRLF normalised to LF and surrounding whitespace stripped."""
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def render_report_text(report: Report) -> str:
    """`## {section}` then the section text, for each section in stored order.

    Sections are separated by one blank line. Nothing else from the report is included.
    """
    return "\n\n".join(f"## {name}\n{text}" for name, text in report.sections.items())


def _severity_text(default: str | list[str]) -> str:
    return default if isinstance(default, str) else " or ".join(default)


def taxonomy_block(taxonomy: Taxonomy, modality: Modality) -> str:
    """The three severity definitions, then one line per error type of this modality."""
    lines = ["Severity levels:"]
    lines += [f"{level.id}: {level.definition}." for level in taxonomy.severity_levels]
    lines += ["", "Error types:"]
    lines += [
        f"{t.id} — {t.name}: {t.definition} Default severity: {_severity_text(t.default_severity)}."
        for t in taxonomy.types
        if t.modality == modality
    ]
    return "\n".join(lines)


def build_eval_messages(
    report: Report,
    condition: Condition,
    taxonomy: Taxonomy,
    prompts_dir: Path | str = DEFAULT_PROMPTS_DIR,
) -> tuple[str, str]:
    """(system, user) for one report in one condition."""
    prompts_dir = Path(prompts_dir)
    if condition == "plain":
        system = read_prompt(prompts_dir / PLAIN_PROMPT)
    elif condition == "structured":
        owner = read_prompt(prompts_dir / STRUCTURED_OWNER_PROMPTS[report.modality])
        output = read_prompt(prompts_dir / STRUCTURED_OUTPUT_PROMPT)
        block = taxonomy_block(taxonomy, report.modality)
        system = f"{owner}\n\n{TAXONOMY_HEADING}\n{block}\n\n{output}"
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return system, render_report_text(report)


def _has_word(token: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text) is not None


def check_eval_isolation(
    report: Report,
    condition: Condition,
    system: str,
    user: str,
    taxonomy: Taxonomy | None = None,
) -> list[str]:
    """Return every isolation breach in one condition's messages (empty when isolated)."""
    if taxonomy is None:
        taxonomy = load_taxonomy()
    problems: list[str] = []
    messages = (("system", system), ("user", user))
    for label, text in messages:
        if report.id in text:
            problems.append(f"{label} message contains the report id {report.id}")
        for value in sorted({match.group(1).lower() for match in _SPLIT_LABEL.finditer(text)}):
            problems.append(f"{label} message contains the split '{value}'")
        if _SPLIT_KEY.search(text):
            problems.append(f'{label} message contains the quoted key "split"')
        for field_name in ("is_clean_control", "provenance", "error_id"):
            if field_name in text:
                problems.append(f"{label} message contains '{field_name}'")
        for err in report.errors:
            for attr in ("description", "rationale", "severity_reason"):
                value = (getattr(err, attr) or "").strip()
                if value and value in text:
                    problems.append(f"{label} message contains the {attr} of {err.error_id}")

    if condition == "plain":
        lowered = system.lower()
        for t in taxonomy.types:
            if _has_word(t.id, system):
                problems.append(f"plain system message contains the type id {t.id}")
            if t.name.lower() in lowered:
                problems.append(f"plain system message contains the type name '{t.name}'")
        for level in taxonomy.severity_levels:
            if level.definition.lower() in lowered:
                problems.append(f"plain system message contains the {level.id} severity definition")
    else:
        block = taxonomy_block(taxonomy, report.modality)
        if block not in system:
            problems.append(f"structured system message lacks the {report.modality} taxonomy")
        lowered = system.lower()
        for t in taxonomy.types:
            if t.modality == report.modality:
                continue
            if _has_word(t.id, system) or t.name.lower() in lowered:
                problems.append(
                    f"structured system message contains {t.modality} type {t.id} "
                    f"in a {report.modality} report"
                )

    if user != render_report_text(report):
        problems.append("user message is not the report text (it must be the same in both)")
    return problems
