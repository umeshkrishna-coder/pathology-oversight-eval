"""Validator for report files in data/reports/.

Each rule takes a parsed Report and the Taxonomy and returns a list of failure reasons
(empty when the rule passes). validate_reports() runs every rule on every file and builds
the summary line.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from pathqc_eval.schema import DIFFERENTIAL_CELLS, SECTION_CONVENTIONS, CBCValues, Report
from pathqc_eval.taxonomy import Taxonomy

_EPS = 1e-9


def derived_index_inconsistencies(v: CBCValues) -> list[str]:
    """CBC derived-index checks with the tolerances from EVAL-01."""
    found: list[str] = []

    def check(name: str, actual: float, expected: float, tolerance: float, unit: str) -> None:
        if abs(actual - expected) > tolerance + _EPS:
            found.append(
                f"{name} is {actual:g} {unit}, expected {expected:.2f} {unit} (±{tolerance:g})"
            )

    if v.RBC.value <= 0 or v.Hct.value <= 0:
        return ["RBC and Hct must be positive to check derived indices"]
    check("MCV", v.MCV.value, v.Hct.value / v.RBC.value * 10, 2, "fL")
    check("MCH", v.MCH.value, v.Hb.value / v.RBC.value * 10, 1, "pg")
    check("MCHC", v.MCHC.value, v.Hb.value / v.Hct.value * 100, 1, "g/dL")
    pct_sum = sum(getattr(v, f"{cell}_pct").value for cell in DIFFERENTIAL_CELLS)
    check("differential % sum", pct_sum, 100, 1, "%")
    for cell in DIFFERENTIAL_CELLS:
        pct = getattr(v, f"{cell}_pct").value
        absolute = getattr(v, f"{cell}_abs").value
        check(f"{cell} absolute", absolute, v.WBC.value * pct / 100, 0.1, "x10^9/L")
    return found


def check_clean_control(report: Report, taxonomy: Taxonomy) -> list[str]:
    if report.is_clean_control and report.errors:
        return [f"is_clean_control is true but {len(report.errors)} planted error(s) are listed"]
    if not report.is_clean_control and not report.errors:
        return ["is_clean_control is false but no planted errors are listed"]
    return []


def check_error_ids(report: Report, taxonomy: Taxonomy) -> list[str]:
    reasons = []
    for err in report.errors:
        if not err.error_id.startswith(f"{report.id}-E"):
            reasons.append(f"error_id {err.error_id} does not start with {report.id}-E")
    counts = Counter(err.error_id for err in report.errors)
    reasons += [f"error_id {eid} appears {n} times" for eid, n in counts.items() if n > 1]
    return reasons


def check_error_types(report: Report, taxonomy: Taxonomy) -> list[str]:
    reasons = []
    types = taxonomy.by_id()
    for err in report.errors:
        if err.type not in types:
            reasons.append(f"{err.error_id}: type {err.type} is not in the taxonomy")
        elif types[err.type].modality != report.modality:
            reasons.append(
                f"{err.error_id}: type {err.type} is {types[err.type].modality}, "
                f"report is {report.modality}"
            )
    return reasons


def check_quoted_sentences(report: Report, taxonomy: Taxonomy) -> list[str]:
    reasons = []
    for err in report.errors:
        if err.section not in report.sections:
            reasons.append(f"{err.error_id}: section '{err.section}' is not in the report")
        elif err.quoted_sentence not in report.sections[err.section]:
            reasons.append(
                f"{err.error_id}: quoted_sentence does not occur verbatim in '{err.section}'"
            )
    return reasons


def check_section_order(report: Report, taxonomy: Taxonomy) -> list[str]:
    convention = SECTION_CONVENTIONS[report.modality]
    order = {name: i for i, (name, _) in enumerate(convention)}
    present = list(report.sections)
    reasons = [f"unknown section '{name}'" for name in present if name not in order]
    reasons += [
        f"required section '{name}' is missing"
        for name, required in convention
        if required and name not in report.sections
    ]
    known = [name for name in present if name in order]
    if [order[name] for name in known] != sorted(order[name] for name in known):
        expected = [name for name, _ in convention if name in report.sections]
        reasons.append(f"sections out of order: got {known}, expected {expected}")
    return reasons


def check_cbc_indices(report: Report, taxonomy: Taxonomy) -> list[str]:
    if report.modality != "cbc" or report.cbc_values is None:
        return []
    inconsistencies = derived_index_inconsistencies(report.cbc_values)
    if any(err.type == "C2" for err in report.errors):
        if not inconsistencies:
            return ["declares a C2 error but every derived index is consistent"]
        return []
    return [f"derived index inconsistency: {item}" for item in inconsistencies]


RULES: tuple[Callable[[Report, Taxonomy], list[str]], ...] = (
    check_clean_control,
    check_error_ids,
    check_error_types,
    check_quoted_sentences,
    check_section_order,
    check_cbc_indices,
)


def check_report(report: Report, taxonomy: Taxonomy) -> list[str]:
    """Run every per-report rule; return all failure reasons."""
    return [reason for rule in RULES for reason in rule(report, taxonomy)]


@dataclass
class ValidationResult:
    reports: list[Report] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def ok(self) -> bool:
        return not self.failures


def _pydantic_reason(exc: ValidationError) -> str:
    parts = [f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()]
    return "; ".join(parts)


def summarize(reports: list[Report], taxonomy: Taxonomy, failures: int) -> str:
    modality = Counter(r.modality for r in reports)
    split = Counter(r.split for r in reports)
    clean = sum(r.is_clean_control for r in reports)
    by_type = Counter(err.type for r in reports for err in r.errors)
    type_counts = ", ".join(f"{tid} {by_type.get(tid, 0)}" for tid in taxonomy.type_ids())
    status = "OK" if failures == 0 else f"FAILED ({failures})"
    return (
        f"validate: {len(reports)} reports | "
        f"histopathology {modality['histopathology']}, cbc {modality['cbc']} | "
        f"dev {split['dev']}, scored {split['scored']} | "
        f"clean {clean}, planted {len(reports) - clean} | "
        f"errors by type: {type_counts} | {status}"
    )


def validate_reports(
    directory: Path | str,
    taxonomy: Taxonomy,
    expect: int | None = None,
    expect_clean: int | None = None,
    expect_dev: int | None = None,
) -> ValidationResult:
    """Validate every *.json report in directory; counts are enforced only when given."""
    directory = Path(directory)
    result = ValidationResult()
    if not directory.is_dir():
        result.failures.append(f"{directory}: folder not found")
        result.summary = summarize([], taxonomy, len(result.failures))
        return result

    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            report = Report.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            result.failures.append(f"{path.name}: does not parse: invalid JSON ({exc})")
            continue
        except ValidationError as exc:
            result.failures.append(f"{path.name}: does not parse: {_pydantic_reason(exc)}")
            continue
        if report.id in seen:
            result.failures.append(f"{path.name}: id {report.id} already used in {seen[report.id]}")
        else:
            seen[report.id] = path.name
        result.failures += [f"{path.name}: {reason}" for reason in check_report(report, taxonomy)]
        result.reports.append(report)

    counts = (
        ("reports", expect, len(result.reports)),
        ("clean controls", expect_clean, sum(r.is_clean_control for r in result.reports)),
        ("dev reports", expect_dev, sum(r.split == "dev" for r in result.reports)),
    )
    for label, expected, actual in counts:
        if expected is not None and actual != expected:
            result.failures.append(f"{directory}: expected {expected} {label}, found {actual}")

    result.summary = summarize(result.reports, taxonomy, len(result.failures))
    return result
