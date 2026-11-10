"""CBC derivation at draft time: primary values in, full CBCValues out.

derive_cbc is called from draft.draft_report and nowhere else. render.py and validate.py
never import this module, so a planted C2 inconsistency survives a re-render (decision 26).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator

from pathqc_eval.io import read_report_json
from pathqc_eval.schema import CBC_UNITS, DIFFERENTIAL_CELLS, CBCValues, StrictModel
from pathqc_eval.spec import Sex
from pathqc_eval.taxonomy import REPO_ROOT

DEFAULT_RANGES_PATH = REPO_ROOT / "data" / "specs" / "cbc_reference_ranges.json"

SEX_SPECIFIC = ("Hb", "RBC", "Hct")
_PCT_TOLERANCE = 0.5
_EPS = 1e-9


class CBCPrimary(StrictModel):
    """Measured values only, in the fixed units of CBC_UNITS; derived indices are computed."""

    Hb: float
    RBC: float
    Hct: float
    RDW: float
    WBC: float
    Neutrophils_pct: float
    Lymphocytes_pct: float
    Monocytes_pct: float
    Eosinophils_pct: float
    Basophils_pct: float
    Platelets: float
    MPV: float


class Range(StrictModel):
    low: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> Range:
        if self.low > self.high:
            raise ValueError(f"low {self.low} is above high {self.high}")
        return self


class ReferenceRanges(StrictModel):
    version: str
    source: str
    by_sex: dict[Sex, dict[str, Range]]
    shared: dict[str, Range]

    @model_validator(mode="after")
    def _complete(self) -> ReferenceRanges:
        for sex in ("female", "male"):
            if set(self.by_sex.get(sex, {})) != set(SEX_SPECIFIC):
                raise ValueError(f"by_sex.{sex} must give exactly {list(SEX_SPECIFIC)}")
        expected_shared = set(CBC_UNITS) - set(SEX_SPECIFIC)
        if set(self.shared) != expected_shared:
            missing = sorted(expected_shared - set(self.shared))
            extra = sorted(set(self.shared) - expected_shared)
            raise ValueError(f"shared ranges: missing {missing}, unexpected {extra}")
        return self

    def for_field(self, field_name: str, sex: Sex) -> Range:
        if field_name in SEX_SPECIFIC:
            return self.by_sex[sex][field_name]
        return self.shared[field_name]


def load_reference_ranges(path: Path | str = DEFAULT_RANGES_PATH) -> ReferenceRanges:
    return ReferenceRanges.model_validate(read_report_json(path))


def derive_cbc(
    primary: CBCPrimary, sex: Sex, ranges: ReferenceRanges
) -> tuple[CBCValues, list[str]]:
    """Compute MCV, MCH, MCHC and absolute counts; attach units and ranges; return notes."""
    notes: list[str] = []
    pct = {cell: getattr(primary, f"{cell}_pct") for cell in DIFFERENTIAL_CELLS}
    total = sum(pct.values())
    if abs(total - 100) > _PCT_TOLERANCE + _EPS:
        others = sum(v for cell, v in pct.items() if cell != "Lymphocytes")
        adjusted = round(100 - others, 1)
        if adjusted < 0 or adjusted > 100:
            raise ValueError(
                f"differential sums to {total:g}%; Lymphocytes_pct would become {adjusted:g}%"
            )
        notes.append(
            f"differential summed to {total:g}%; Lymphocytes_pct set to {adjusted:g}% "
            f"(was {pct['Lymphocytes']:g}%)"
        )
        pct["Lymphocytes"] = adjusted
    if primary.RBC <= 0 or primary.Hct <= 0:
        raise ValueError("RBC and Hct must be positive to derive red-cell indices")

    values: dict[str, float] = {
        "Hb": primary.Hb,
        "RBC": primary.RBC,
        "Hct": primary.Hct,
        "MCV": round(primary.Hct / primary.RBC * 10, 1),
        "MCH": round(primary.Hb / primary.RBC * 10, 1),
        "MCHC": round(primary.Hb / primary.Hct * 100, 1),
        "RDW": primary.RDW,
        "WBC": primary.WBC,
        "Platelets": primary.Platelets,
        "MPV": primary.MPV,
    }
    for cell in DIFFERENTIAL_CELLS:
        values[f"{cell}_pct"] = pct[cell]
        values[f"{cell}_abs"] = round(primary.WBC * pct[cell] / 100, 2)

    if not 50 <= values["MCV"] <= 130:
        notes.append(f"implausible MCV {values['MCV']:g} fL (outside 50-130)")
    if not 28 <= values["MCHC"] <= 38:
        notes.append(f"implausible MCHC {values['MCHC']:g} g/dL (outside 28-38)")
    for cell in DIFFERENTIAL_CELLS:
        if not 0 <= pct[cell] <= 100:
            notes.append(f"implausible {cell}_pct {pct[cell]:g}% (outside 0-100)")

    analytes = {}
    for field_name in CBCValues.model_fields:
        rng = ranges.for_field(field_name, sex)
        analytes[field_name] = {
            "value": values[field_name],
            "unit": CBC_UNITS[field_name],
            "ref_low": rng.low,
            "ref_high": rng.high,
        }
    return CBCValues.model_validate(analytes), notes
