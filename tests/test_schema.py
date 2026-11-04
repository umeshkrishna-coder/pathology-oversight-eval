import pytest
from pydantic import ValidationError

from pathqc_eval.schema import (
    AdjudicationHidden,
    AdjudicationItem,
    Finding,
    Report,
    RunConfig,
)


@pytest.mark.parametrize("name", ["histo", "cbc"])
def test_report_round_trip(name, request):
    data = request.getfixturevalue(name)
    report = Report.model_validate(data)
    again = Report.model_validate_json(report.model_dump_json())
    assert again == report
    assert list(again.sections) == list(data["sections"])


def test_report_forbids_extra_fields(histo):
    histo["extra"] = "x"
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


def test_planted_error_forbids_extra_fields(histo):
    histo["errors"][0]["extra"] = "x"
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


@pytest.mark.parametrize("bad_id", ["H-01", "X-001", "H-0001", "h-001"])
def test_report_id_pattern(histo, bad_id):
    histo["id"] = bad_id
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


def test_report_id_prefix_matches_modality(histo):
    histo["id"] = "C-001"
    with pytest.raises(ValidationError, match="start with 'H-'"):
        Report.model_validate(histo)


def test_histopathology_takes_no_cbc_values(histo, cbc):
    histo["cbc_values"] = cbc["cbc_values"]
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


def test_cbc_needs_cbc_values(cbc):
    cbc["cbc_values"] = None
    with pytest.raises(ValidationError):
        Report.model_validate(cbc)


def test_cbc_values_need_every_analyte(cbc):
    del cbc["cbc_values"]["MPV"]
    with pytest.raises(ValidationError):
        Report.model_validate(cbc)


def test_error_id_pattern(histo):
    histo["errors"][0]["error_id"] = "H-001-1"
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


def test_provenance_edited_by_owner_only(histo):
    histo["provenance"]["edited_by"] = "model"
    with pytest.raises(ValidationError):
        Report.model_validate(histo)


def _finding(**overrides) -> dict:
    data = {
        "quoted_sentence": "Tumour measures 25 mm.",
        "section": "Microscopic description",
        "category": "size mismatch",
        "severity": "major",
        "confidence": 0.8,
        "rationale": "Differs from the gross size.",
    }
    return data | overrides


def test_finding_round_trip():
    finding = Finding.model_validate(_finding())
    assert Finding.model_validate_json(finding.model_dump_json()) == finding


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_finding_confidence_range(confidence):
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(confidence=confidence))


def test_finding_severity_values():
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(severity="moderate"))


def _run_config(**overrides) -> dict:
    data = {
        "run_id": "dev-plain-001",
        "dataset": "dev",
        "condition": "plain",
        "model": "claude-sonnet-5-5",
        "temperature": 0,
        "repeats": 3,
        "dataset_hash": "a" * 64,
        "prompt_hash": "b" * 64,
        "taxonomy_hash": "c" * 64,
        "created_at": "2026-11-04T12:00:00Z",
        "cost_gate_usd": 5.0,
    }
    return data | overrides


def test_run_config_round_trip():
    config = RunConfig.model_validate(_run_config())
    assert RunConfig.model_validate_json(config.model_dump_json()) == config


@pytest.mark.parametrize(
    "overrides",
    [
        {"temperature": 0.5},
        {"repeats": 2},
        {"condition": "other"},
        {"dataset_hash": "not-a-hash"},
        {"cost_gate_usd": 0},
    ],
)
def test_run_config_rejects(overrides):
    with pytest.raises(ValidationError):
        RunConfig.model_validate(_run_config(**overrides))


def _adjudication_item(**overrides) -> dict:
    data = {
        "item_id": "A-0001",
        "report_id": "H-001",
        "section": "Microscopic description",
        "quoted_sentence": "Tumour measures 25 mm.",
        "category": "size mismatch",
        "rationale": "Differs from the gross size.",
    }
    return data | overrides


def test_adjudication_item_starts_without_verdict():
    item = AdjudicationItem.model_validate(_adjudication_item())
    assert item.verdict is None and item.verdict_reason is None
    assert AdjudicationItem.model_validate_json(item.model_dump_json()) == item


def test_adjudication_item_is_blind():
    for hidden in ("condition", "repeat", "model"):
        assert hidden not in AdjudicationItem.model_fields
        with pytest.raises(ValidationError):
            AdjudicationItem.model_validate(_adjudication_item(**{hidden: "x"}))


def test_adjudication_item_verdict_values():
    with pytest.raises(ValidationError):
        AdjudicationItem.model_validate(_adjudication_item(verdict="maybe"))


def test_adjudication_hidden_round_trip():
    hidden = AdjudicationHidden(condition="structured", repeat=2, model="claude-sonnet-5-5")
    assert AdjudicationHidden.model_validate_json(hidden.model_dump_json()) == hidden
    with pytest.raises(ValidationError):
        AdjudicationHidden(condition="plain", repeat=4, model="claude-sonnet-5-5")
