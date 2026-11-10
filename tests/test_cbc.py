import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pathqc_eval import render, validate
from pathqc_eval.cbc import CBCPrimary, ReferenceRanges, derive_cbc, load_reference_ranges
from pathqc_eval.schema import CBC_UNITS
from pathqc_eval.taxonomy import REPO_ROOT
from pathqc_eval.validate import derived_index_inconsistencies


def _primary(**overrides) -> CBCPrimary:
    data = {
        "Hb": 9.8,
        "RBC": 4.10,
        "Hct": 31.0,
        "RDW": 16.2,
        "WBC": 7.40,
        "Neutrophils_pct": 62.0,
        "Lymphocytes_pct": 28.0,
        "Monocytes_pct": 6.0,
        "Eosinophils_pct": 3.0,
        "Basophils_pct": 1.0,
        "Platelets": 310.0,
        "MPV": 9.6,
    }
    return CBCPrimary.model_validate(data | overrides)


@pytest.fixture(scope="module")
def ranges():
    return load_reference_ranges()


def test_derive_cbc_golden(ranges):
    values, notes = derive_cbc(_primary(), "female", ranges)
    assert notes == []
    got = {name: getattr(values, name).value for name in ("MCV", "MCH", "MCHC")}
    assert got == {"MCV": 75.6, "MCH": 23.9, "MCHC": 31.6}
    absolutes = {
        cell: getattr(values, f"{cell}_abs").value
        for cell in ("Neutrophils", "Lymphocytes", "Monocytes", "Eosinophils", "Basophils")
    }
    assert absolutes == {
        "Neutrophils": 4.59,
        "Lymphocytes": 2.07,
        "Monocytes": 0.44,
        "Eosinophils": 0.22,
        "Basophils": 0.07,
    }
    assert all(getattr(values, name).unit == unit for name, unit in CBC_UNITS.items())
    assert (values.Hb.ref_low, values.Hb.ref_high) == (12.0, 15.0)
    assert (values.MCV.ref_low, values.MCV.ref_high) == (83.0, 101.0)


def test_reference_ranges_by_sex(ranges):
    female, _ = derive_cbc(_primary(), "female", ranges)
    male, _ = derive_cbc(_primary(), "male", ranges)
    assert (male.Hb.ref_low, male.Hb.ref_high) == (13.0, 17.0)
    assert (male.Hct.ref_low, male.Hct.ref_high) == (40.0, 50.0)
    assert (female.RBC.ref_low, female.RBC.ref_high) == (3.8, 4.8)
    assert male.Platelets.ref_low == female.Platelets.ref_low


def test_differential_within_half_percent_is_kept(ranges):
    values, notes = derive_cbc(_primary(Basophils_pct=1.4), "female", ranges)  # sums to 100.4
    assert notes == []
    assert values.Lymphocytes_pct.value == 28.0


def test_differential_adjusts_lymphocytes(ranges):
    values, notes = derive_cbc(_primary(Basophils_pct=1.6), "female", ranges)  # sums to 100.6
    assert values.Lymphocytes_pct.value == 27.4
    assert notes == ["differential summed to 100.6%; Lymphocytes_pct set to 27.4% (was 28%)"]
    assert derived_index_inconsistencies(values) == []


def test_differential_adjustment_out_of_range_raises(ranges):
    with pytest.raises(ValueError, match="Lymphocytes_pct would become"):
        derive_cbc(_primary(Neutrophils_pct=90.0, Monocytes_pct=10.0), "female", ranges)


def test_plausibility_notes(ranges):
    _, notes = derive_cbc(_primary(Hct=20.0, RBC=4.5), "female", ranges)  # MCV 44.4, MCHC 49
    assert any(n.startswith("implausible MCV") for n in notes)
    assert any(n.startswith("implausible MCHC") for n in notes)


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"Hb": 6.2, "RBC": 3.30, "Hct": 21.0, "WBC": 6.10},
        {"Hb": 20.4, "RBC": 6.90, "Hct": 61.0, "WBC": 12.30},
        {"Hb": 7.8, "RBC": 2.10, "Hct": 24.8, "WBC": 3.20, "Platelets": 110.0},
        {
            "WBC": 0.90,
            "Neutrophils_pct": 22.0,
            "Lymphocytes_pct": 70.0,
            "Monocytes_pct": 7.0,
            "Eosinophils_pct": 0.7,
            "Basophils_pct": 0.3,
        },
        {
            "WBC": 48.0,
            "Neutrophils_pct": 12.0,
            "Lymphocytes_pct": 82.3,
            "Monocytes_pct": 4.0,
            "Eosinophils_pct": 1.0,
            "Basophils_pct": 1.0,
        },
    ],
)
def test_derived_values_are_consistent_by_construction(ranges, overrides):
    values, _ = derive_cbc(_primary(**overrides), "male", ranges)
    assert derived_index_inconsistencies(values) == []


def _imported_modules(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", [render, validate])
def test_render_and_validate_do_not_import_cbc(module):
    assert "pathqc_eval.cbc" not in _imported_modules(module.__file__)


def test_derive_cbc_is_called_only_from_draft():
    callers = [
        path.name
        for path in (REPO_ROOT / "src" / "pathqc_eval").glob("*.py")
        if path.name != "cbc.py" and "derive_cbc(" in path.read_text(encoding="utf-8")
    ]
    assert callers == ["draft.py"]


@pytest.mark.parametrize(
    ("analyte", "end", "bad"),
    [
        ("Platelets", "low", float("nan")),
        ("Platelets", "low", float("-inf")),
        ("Platelets", "low", False),
        ("Platelets", "low", "150"),
        ("Platelets", "low", -(10**400)),
        ("Platelets", "high", float("nan")),
        ("Platelets", "high", float("inf")),
        ("Platelets", "high", "410"),
        ("Platelets", "high", 10**400),
        ("Basophils_pct", "high", True),
    ],
    ids=lambda v: v if isinstance(v, str) else repr(v)[:12],
)
def test_reference_ranges_refuse_a_bound_that_is_not_a_finite_number(ranges, analyte, end, bad):
    """EVAL-02d (S3 review): a range bound that is NaN, infinite, true/false, text or an integer
    too large for a float would reach the drafting model as a reference range; the file is
    refused instead. Each value here keeps low <= high, so only the finite-number rule can
    refuse it."""
    data = ranges.model_dump()
    data["shared"][analyte][end] = bad
    with pytest.raises(ValidationError, match="a range bound must be a finite number"):
        ReferenceRanges.model_validate(data)


def test_reference_ranges_refuse_an_integer_too_long_to_print(ranges):
    """EVAL-02d (S3 review round 3): an integer longer than Python will print (over 4300
    digits) is refused with the same message, not with Python's own limit message."""
    data = ranges.model_dump()
    data["shared"]["Platelets"]["high"] = 10**4300
    with pytest.raises(ValidationError) as caught:
        ReferenceRanges.model_validate(data)
    messages = [error["msg"] for error in caught.value.errors()]
    assert messages == [
        "Value error, a range bound must be a finite number, not an integer too long to print"
    ]


def test_reference_ranges_file_with_nan_is_refused(tmp_path, ranges):
    path = tmp_path / "ranges.json"
    text = json.dumps(ranges.model_dump()).replace('"low": 150.0', '"low": NaN', 1)
    assert "NaN" in text
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_reference_ranges(path)
