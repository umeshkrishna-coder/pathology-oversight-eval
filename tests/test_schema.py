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
        "sampling": "default",
        "repeats": 3,
        "dataset_hash": "a" * 64,
        "prompt_hash": "b" * 64,
        "taxonomy_hash": "c" * 64,
        "created_at": "2026-11-04T12:00:00Z",
        "cost_gate_usd": 5.0,
        # EVAL-04 fields
        "effort": "default",
        "max_tokens": 16000,
        "sdk_version": "2.4.0",
        "lock_created_at": None,
    }
    return data | overrides


def test_run_config_round_trip():
    config = RunConfig.model_validate(_run_config())
    assert RunConfig.model_validate_json(config.model_dump_json()) == config


@pytest.mark.parametrize(
    "overrides",
    [
        {"temperature": 0},
        {"temperature": 0.5},
        {"sampling": "zero"},
        {"repeats": 2},
        {"condition": "other"},
        {"dataset_hash": "not-a-hash"},
        {"cost_gate_usd": 0},
        {"effort": "high"},
        {"effort": None},
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
        # EVAL-05 fields
        "candidate_error_id": "H-001-E1",
        "review_reason": "unmapped_category",
    }
    return data | overrides


def test_adjudication_item_starts_without_verdict():
    item = AdjudicationItem.model_validate(_adjudication_item())
    assert item.verdict is None and item.verdict_reason is None
    assert AdjudicationItem.model_validate_json(item.model_dump_json()) == item


def test_adjudication_item_is_blind():
    for hidden in ("condition", "repeat", "model", "run_id"):
        assert hidden not in AdjudicationItem.model_fields
        with pytest.raises(ValidationError):
            AdjudicationItem.model_validate(_adjudication_item(**{hidden: "x"}))


def test_adjudication_item_verdict_values():
    with pytest.raises(ValidationError):
        AdjudicationItem.model_validate(_adjudication_item(verdict="maybe"))


def test_adjudication_hidden_round_trip():
    hidden = AdjudicationHidden(
        run_id="r1", condition="structured", repeat=2, finding_index=1, model="claude-sonnet-5-5"
    )
    assert AdjudicationHidden.model_validate_json(hidden.model_dump_json()) == hidden
    with pytest.raises(ValidationError):
        AdjudicationHidden(
            run_id="r1", condition="plain", repeat=4, finding_index=1, model="claude-sonnet-5-5"
        )
    with pytest.raises(ValidationError):
        AdjudicationHidden(
            run_id="r1", condition="plain", repeat=1, finding_index=0, model="claude-sonnet-5-5"
        )


def test_adjudication_item_review_reason_values():
    with pytest.raises(ValidationError):
        AdjudicationItem.model_validate(_adjudication_item(review_reason="other"))


def test_run_config_sampling_defaults_to_default():
    data = _run_config()
    del data["sampling"]
    config = RunConfig.model_validate(data)
    assert config.sampling == "default"
    assert "temperature" not in config.model_dump()


def test_run_config_effort_defaults_to_default():
    data = _run_config()
    del data["effort"]
    assert RunConfig.model_validate(data).effort == "default"


@pytest.mark.parametrize("field", ["max_tokens", "sdk_version", "lock_created_at"])
def test_run_config_requires_the_eval04_fields(field):
    data = _run_config()
    del data[field]
    with pytest.raises(ValidationError):
        RunConfig.model_validate(data)


def test_run_config_holds_the_lock_time_for_a_scored_run():
    config = RunConfig.model_validate(
        _run_config(dataset="scored", lock_created_at="2026-11-15T08:00:00Z")
    )
    assert config.lock_created_at == "2026-11-15T08:00:00Z"


def test_planted_error_kind_defaults_to_statement(histo):
    report = Report.model_validate(histo)
    assert report.errors[0].kind == "statement"


@pytest.mark.parametrize("kind", ["statement", "omission"])
def test_planted_error_kind_values(histo, kind):
    histo["errors"][0]["kind"] = kind
    assert Report.model_validate(histo).errors[0].kind == kind


def test_planted_error_kind_rejects_other(histo):
    histo["errors"][0]["kind"] = "absence"
    with pytest.raises(ValidationError):
        Report.model_validate(histo)
