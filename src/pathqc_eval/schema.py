"""Pydantic v2 models for reports, planted errors, findings, run configs and adjudication.

Every model forbids extra fields. Cross-field rules that need the taxonomy or span several
fields (verbatim quotes, section order, CBC derived indices) live in validate.py.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["critical", "major", "minor"]
Modality = Literal["histopathology", "cbc"]
Split = Literal["dev", "scored"]
Condition = Literal["plain", "structured"]
Verdict = Literal["detected", "miss", "near_miss", "false_alarm"]

SCHEMA_VERSION = "1.0"

# Section conventions from handoff.md, in order: (section name, required).
SECTION_CONVENTIONS: dict[str, list[tuple[str, bool]]] = {
    "histopathology": [
        ("Clinical details", True),
        ("Specimen", True),
        ("Gross description", True),
        ("Microscopic description", True),
        ("Immunohistochemistry", False),
        ("Diagnosis", True),
        ("Synoptic summary", True),
        ("Comment", False),
    ],
    "cbc": [
        ("Values", True),
        ("Interpretation", True),
        ("Comment/recommendation", False),
    ],
}

DIFFERENTIAL_CELLS = ("Neutrophils", "Lymphocytes", "Monocytes", "Eosinophils", "Basophils")

# Fixed unit for every CBCValues field (decision 18); validate.check_cbc_units enforces it.
CBC_UNITS: dict[str, str] = {
    "Hb": "g/dL",
    "RBC": "x10^12/L",
    "Hct": "%",
    "MCV": "fL",
    "MCH": "pg",
    "MCHC": "g/dL",
    "RDW": "%",
    "WBC": "x10^9/L",
    **{
        f"{cell}_{kind}": unit
        for cell in DIFFERENTIAL_CELLS
        for kind, unit in (("pct", "%"), ("abs", "x10^9/L"))
    },
    "Platelets": "x10^9/L",
    "MPV": "fL",
}

_SHA256 = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Analyte(StrictModel):
    value: float
    unit: str
    ref_low: float
    ref_high: float


class CBCValues(StrictModel):
    """Structured CBC values; each analyte's unit must equal its entry in CBC_UNITS."""

    Hb: Analyte
    RBC: Analyte
    Hct: Analyte
    MCV: Analyte
    MCH: Analyte
    MCHC: Analyte
    RDW: Analyte
    WBC: Analyte
    Neutrophils_pct: Analyte
    Neutrophils_abs: Analyte
    Lymphocytes_pct: Analyte
    Lymphocytes_abs: Analyte
    Monocytes_pct: Analyte
    Monocytes_abs: Analyte
    Eosinophils_pct: Analyte
    Eosinophils_abs: Analyte
    Basophils_pct: Analyte
    Basophils_abs: Analyte
    Platelets: Analyte
    MPV: Analyte


class PlantedError(StrictModel):
    error_id: str = Field(pattern=r"^(H|C)-\d{3}-E\d+$")
    type: str = Field(pattern=r"^[HC]\d+$")
    section: str
    quoted_sentence: str = Field(min_length=1)
    severity: Severity
    severity_reason: str | None = None
    description: str
    rationale: str
    # Decision 34: an omission quotes an anchor line that exists in the report.
    kind: Literal["statement", "omission"] = "statement"


class Provenance(StrictModel):
    drafted_by: str
    drafted_at: date
    edited_by: Literal["owner"]
    verified: bool
    verified_at: date | None


class Report(StrictModel):
    id: str = Field(pattern=r"^(H|C)-\d{3}$")
    modality: Modality
    split: Split
    specimen_type: str | None = None
    scenario: str | None = None
    sections: dict[str, str]
    cbc_values: CBCValues | None = None
    is_clean_control: bool
    errors: list[PlantedError]
    provenance: Provenance
    schema_version: Literal["1.0"]

    @model_validator(mode="after")
    def _check_modality_fields(self) -> Report:
        if self.modality == "histopathology":
            if not self.id.startswith("H-"):
                raise ValueError("histopathology report ids start with 'H-'")
            if self.specimen_type is None:
                raise ValueError("histopathology reports need specimen_type")
            if self.scenario is not None or self.cbc_values is not None:
                raise ValueError("histopathology reports take no scenario or cbc_values")
        else:
            if not self.id.startswith("C-"):
                raise ValueError("cbc report ids start with 'C-'")
            if self.scenario is None or self.cbc_values is None:
                raise ValueError("cbc reports need scenario and cbc_values")
            if self.specimen_type is not None:
                raise ValueError("cbc reports take no specimen_type")
        return self


class Finding(StrictModel):
    """One finding returned by the evaluated model (both conditions)."""

    quoted_sentence: str
    section: str
    category: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class RunConfig(StrictModel):
    """One run: one dataset (dev or scored) in one condition (EVAL-04)."""

    run_id: str
    dataset: Split
    condition: Condition
    model: str
    # Decision 32 (amends 3): the API takes no temperature; runs use default sampling.
    sampling: Literal["default"] = "default"
    # Owner decision (EVAL-04): the API's default reasoning effort; no effort setting is sent.
    effort: Literal["default"] = "default"
    max_tokens: int
    repeats: Literal[3] = 3
    dataset_hash: str = Field(pattern=_SHA256)
    prompt_hash: str = Field(pattern=_SHA256)
    taxonomy_hash: str = Field(pattern=_SHA256)
    created_at: datetime
    cost_gate_usd: float = Field(gt=0)
    sdk_version: str
    lock_created_at: str | None  # the lock's created_at for a scored run; null for a dev run


ReviewReason = Literal[
    "unmapped_category", "borderline_overlap", "section_mismatch", "omission_other_section"
]


class AdjudicationItem(StrictModel):
    """Blind adjudication view: no condition, repeat, model or run (EVAL-05)."""

    item_id: str
    report_id: str
    section: str
    quoted_sentence: str
    category: str
    rationale: str
    candidate_error_id: str
    review_reason: ReviewReason
    verdict: Verdict | None = None
    verdict_reason: str | None = None


class AdjudicationHidden(StrictModel):
    """One finding behind an item; adjudication_hidden.json maps each item_id to a list."""

    run_id: str
    condition: Condition
    repeat: int = Field(ge=1, le=3)
    finding_index: int = Field(ge=1)  # 1-based position of the finding in its unit
    model: str
