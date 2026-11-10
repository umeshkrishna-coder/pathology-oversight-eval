"""Deterministic rendering of the CBC Values section from the stored cbc_values.

The renderer prints the stored numbers exactly as stored. It never derives or recalculates
any index, so a planted C2 inconsistency in the numbers is preserved in the text.
"""

from __future__ import annotations

from pathqc_eval.schema import DIFFERENTIAL_CELLS, CBCValues

# Fixed decimals per field, used for value, ref_low and ref_high alike.
DECIMALS: dict[str, int] = {
    "Hb": 1,
    "RBC": 2,
    "Hct": 1,
    "MCV": 1,
    "MCH": 1,
    "MCHC": 1,
    "RDW": 1,
    "WBC": 2,
    **{f"{cell}_pct": 1 for cell in DIFFERENTIAL_CELLS},
    **{f"{cell}_abs": 2 for cell in DIFFERENTIAL_CELLS},
    "Platelets": 0,
    "MPV": 1,
}


def _label(field_name: str) -> str:
    cell, _, kind = field_name.partition("_")
    if kind == "pct":
        return f"{cell} %"
    if kind == "abs":
        return f"{cell} absolute"
    return field_name


def render_cbc_values(values: CBCValues) -> str:
    """One line per analyte in CBCValues field order, joined by newlines, no trailing newline."""
    lines = []
    for field_name in CBCValues.model_fields:
        analyte = getattr(values, field_name)
        d = DECIMALS[field_name]
        lines.append(
            f"{_label(field_name)}: {analyte.value:.{d}f} {analyte.unit} "
            f"(ref {analyte.ref_low:.{d}f}–{analyte.ref_high:.{d}f})"
        )
    return "\n".join(lines)
