"""Dataset spec: the 34 planned reports, their briefs and the owner's planned error types.

Planned error types are the owner's plan for planting; they are never shown to the drafting
model (decision 24).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, model_validator

from pathqc_eval.io import read_report_json
from pathqc_eval.schema import Modality, Split, StrictModel
from pathqc_eval.taxonomy import REPO_ROOT, Taxonomy, load_taxonomy

DEFAULT_SPEC_PATH = REPO_ROOT / "data" / "specs" / "dataset.json"

Sex = Literal["female", "male"]

# Decision 22: (modality, split, is_clean_control) -> number of reports.
DATASET_SHAPE: dict[tuple[Modality, Split, bool], int] = {
    ("histopathology", "scored", False): 15,
    ("histopathology", "scored", True): 5,
    ("cbc", "scored", False): 7,
    ("cbc", "scored", True): 3,
    ("histopathology", "dev", False): 2,
    ("histopathology", "dev", True): 1,
    ("cbc", "dev", False): 1,
    ("cbc", "dev", True): 0,
}
TOTAL_REPORTS = sum(DATASET_SHAPE.values())  # 34
MODALITY_TOTALS = {
    modality: sum(n for (m, _, _), n in DATASET_SHAPE.items() if m == modality)
    for modality in ("histopathology", "cbc")
}  # histopathology 23, cbc 11
CLEAN_TOTAL = sum(n for (_, _, clean), n in DATASET_SHAPE.items() if clean)  # 9
MAX_PLANNED_TYPES = 3


class SpecRow(StrictModel):
    id: str = Field(pattern=r"^(H|C)-\d{3}$")
    modality: Modality
    split: Split
    specimen_type: str | None = None
    scenario: str | None = None
    sex: Sex
    age: int = Field(ge=18, le=90)
    is_clean_control: bool
    planned_error_types: list[str]
    brief: str = Field(min_length=40)
    brief_status: Literal["proposed", "approved"]

    @model_validator(mode="after")
    def _check_row(self) -> SpecRow:
        prefix = "H-" if self.modality == "histopathology" else "C-"
        if not self.id.startswith(prefix):
            raise ValueError(f"{self.modality} row ids start with '{prefix}'")
        if self.modality == "histopathology" and (not self.specimen_type or self.scenario):
            raise ValueError("histopathology rows need specimen_type and no scenario")
        if self.modality == "cbc" and (not self.scenario or self.specimen_type):
            raise ValueError("cbc rows need scenario and no specimen_type")
        n = len(self.planned_error_types)
        if self.is_clean_control and n:
            raise ValueError("clean control rows take no planned_error_types")
        if not self.is_clean_control and not 1 <= n <= MAX_PLANNED_TYPES:
            raise ValueError(f"planted rows need 1 to {MAX_PLANNED_TYPES} planned_error_types")
        if len(set(self.planned_error_types)) != n:
            raise ValueError("planned_error_types contains a duplicate")
        return self

    @property
    def subject(self) -> str:
        """specimen_type for histopathology, scenario for cbc."""
        return self.specimen_type or self.scenario or ""


class DatasetSpec(StrictModel):
    version: str
    reports: list[SpecRow]

    @model_validator(mode="after")
    def _check_dataset(self, info: ValidationInfo) -> DatasetSpec:
        taxonomy = (info.context or {}).get("taxonomy") or load_taxonomy()
        problems = _dataset_problems(self, taxonomy)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def row(self, row_id: str) -> SpecRow:
        for r in self.reports:
            if r.id == row_id:
                return r
        raise KeyError(row_id)


def _dataset_problems(spec: DatasetSpec, taxonomy: Taxonomy) -> list[str]:
    problems = []
    ids = [r.id for r in spec.reports]
    duplicates = sorted(i for i, n in Counter(ids).items() if n > 1)
    if duplicates:
        problems.append(f"duplicate ids: {duplicates}")
    for modality, prefix in (("histopathology", "H"), ("cbc", "C")):
        expected = {f"{prefix}-{i:03d}" for i in range(1, MODALITY_TOTALS[modality] + 1)}
        present = {r.id for r in spec.reports if r.modality == modality}
        if present != expected:
            missing = sorted(expected - present)
            extra = sorted(present - expected)
            problems.append(
                f"{modality} ids must be {prefix}-001…{prefix}-{MODALITY_TOTALS[modality]:03d}"
                f" (missing {missing}, unexpected {extra})"
            )
    cells = Counter((r.modality, r.split, r.is_clean_control) for r in spec.reports)
    for cell, expected_n in DATASET_SHAPE.items():
        if cells.get(cell, 0) != expected_n:
            modality, split, clean = cell
            kind = "clean" if clean else "planted"
            problems.append(
                f"expected {expected_n} {modality} {split} {kind}, found {cells.get(cell, 0)}"
            )
    types = taxonomy.by_id()
    for r in spec.reports:
        for tid in r.planned_error_types:
            if tid not in types:
                problems.append(f"{r.id}: planned type {tid} is not in the taxonomy")
            elif types[tid].modality != r.modality:
                problems.append(
                    f"{r.id}: planned type {tid} is {types[tid].modality}, row is {r.modality}"
                )
    return problems


def load_spec(
    path: Path | str = DEFAULT_SPEC_PATH, taxonomy: Taxonomy | None = None
) -> DatasetSpec:
    context = {"taxonomy": taxonomy} if taxonomy else None
    return DatasetSpec.model_validate(read_report_json(path), context=context)


def spec_summary(spec: DatasetSpec, taxonomy: Taxonomy) -> list[str]:
    """Lines printed by `pathqc-eval spec-check`."""
    rows = spec.reports
    clean = sum(r.is_clean_control for r in rows)
    lines = [
        f"spec-check: version {spec.version} | {len(rows)} reports | "
        f"histopathology {sum(r.modality == 'histopathology' for r in rows)}, "
        f"cbc {sum(r.modality == 'cbc' for r in rows)} | "
        f"dev {sum(r.split == 'dev' for r in rows)}, "
        f"scored {sum(r.split == 'scored' for r in rows)} | "
        f"clean {clean}, planted {len(rows) - clean}",
        "by modality / split:",
    ]
    for modality in ("histopathology", "cbc"):
        for split in ("scored", "dev"):
            planted = sum(
                1
                for r in rows
                if (r.modality, r.split, r.is_clean_control) == (modality, split, False)
            )
            clean_n = sum(
                1
                for r in rows
                if (r.modality, r.split, r.is_clean_control) == (modality, split, True)
            )
            lines.append(f"  {modality:<14} {split:<6} planted {planted:>2}, clean {clean_n:>2}")
    lines.append("planned error types (scored / dev / total):")
    scored = Counter(t for r in rows if r.split == "scored" for t in r.planned_error_types)
    dev = Counter(t for r in rows if r.split == "dev" for t in r.planned_error_types)
    for tid in taxonomy.type_ids():
        lines.append(f"  {tid:<3} {scored[tid]:>2} / {dev[tid]:>2} / {scored[tid] + dev[tid]:>2}")
    s_total, d_total = sum(scored.values()), sum(dev.values())
    lines.append(f"  all {s_total:>2} / {d_total:>2} / {s_total + d_total:>2}")
    status = Counter(r.brief_status for r in rows)
    lines.append(f"brief_status: proposed {status['proposed']}, approved {status['approved']}")
    return lines
