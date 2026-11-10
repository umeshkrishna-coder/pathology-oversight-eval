import copy

import pytest
from pydantic import ValidationError

from pathqc_eval.cli import main
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.spec import (
    CLEAN_TOTAL,
    DATASET_SHAPE,
    DEFAULT_SPEC_PATH,
    MODALITY_TOTALS,
    TOTAL_REPORTS,
    DatasetSpec,
    load_spec,
)


@pytest.fixture
def raw_spec() -> dict:
    return copy.deepcopy(read_report_json(DEFAULT_SPEC_PATH))


def _row(raw: dict, row_id: str) -> dict:
    return next(r for r in raw["reports"] if r["id"] == row_id)


def test_dataset_shape_constants():
    assert TOTAL_REPORTS == 34
    assert MODALITY_TOTALS == {"histopathology": 23, "cbc": 11}
    assert CLEAN_TOTAL == 9
    scored = sum(n for (_, split, _), n in DATASET_SHAPE.items() if split == "scored")
    assert scored == 30


def test_committed_spec_loads_and_spec_check_passes(capsys):
    spec = load_spec()
    assert len(spec.reports) == 34
    assert main(["spec-check"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("spec-check: version 0.1 | 34 reports")
    assert out.rstrip().endswith("OK")


def test_wrong_count_fails(raw_spec):
    row = _row(raw_spec, "H-016")
    row |= {"is_clean_control": False, "planned_error_types": ["H1"]}
    with pytest.raises(ValidationError, match="expected 15 histopathology scored planted"):
        DatasetSpec.model_validate(raw_spec)


def test_duplicate_id_fails(raw_spec):
    _row(raw_spec, "C-011")["id"] = "C-010"
    with pytest.raises(ValidationError, match="duplicate ids"):
        DatasetSpec.model_validate(raw_spec)


def test_non_contiguous_ids_fail(raw_spec):
    _row(raw_spec, "C-011")["id"] = "C-012"
    with pytest.raises(ValidationError, match="cbc ids must be"):
        DatasetSpec.model_validate(raw_spec)


def test_planned_type_of_wrong_modality_fails(raw_spec):
    _row(raw_spec, "H-001")["planned_error_types"] = ["C1"]
    with pytest.raises(ValidationError, match="planned type C1 is cbc"):
        DatasetSpec.model_validate(raw_spec)


def test_unknown_planned_type_fails(raw_spec):
    _row(raw_spec, "H-001")["planned_error_types"] = ["H9"]
    with pytest.raises(ValidationError, match="not in the taxonomy"):
        DatasetSpec.model_validate(raw_spec)


def test_four_planned_types_fail(raw_spec):
    _row(raw_spec, "H-004")["planned_error_types"] = ["H1", "H2", "H3", "H4"]
    with pytest.raises(ValidationError, match="1 to 3 planned_error_types"):
        DatasetSpec.model_validate(raw_spec)


def test_clean_row_with_planned_types_fails(raw_spec):
    _row(raw_spec, "H-016")["planned_error_types"] = ["H1"]
    with pytest.raises(ValidationError, match="clean control rows take no planned_error_types"):
        DatasetSpec.model_validate(raw_spec)


@pytest.mark.parametrize(
    "field, value",
    [("age", 17), ("age", 91), ("sex", "other"), ("brief", "Too short."), ("extra", 1)],
)
def test_row_field_rules(raw_spec, field, value):
    _row(raw_spec, "H-001")[field] = value
    with pytest.raises(ValidationError):
        DatasetSpec.model_validate(raw_spec)


def test_spec_check_reports_failures(tmp_path, raw_spec, capsys):
    _row(raw_spec, "H-004")["planned_error_types"] = ["H1", "H2", "H3", "H4"]
    path = tmp_path / "dataset.json"
    write_report_json(path, raw_spec)
    assert main(["spec-check", str(path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL H-004: planted rows need 1 to 3 planned_error_types" in out
