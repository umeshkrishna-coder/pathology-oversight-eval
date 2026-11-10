import json

import pytest
from conftest import rerender

from pathqc_eval.cli import main
from pathqc_eval.schema import Report
from pathqc_eval.taxonomy import REPO_ROOT
from pathqc_eval.validate import (
    check_cbc_indices,
    check_cbc_units,
    check_cbc_values_text,
    check_clean_control,
    check_error_ids,
    check_error_types,
    check_quoted_sentences,
    check_report,
    check_section_order,
    check_severity,
    validate_reports,
)


def _report(data: dict) -> Report:
    return Report.model_validate(data)


def _c2_error() -> dict:
    return {
        "error_id": "C-001-E1",
        "type": "C2",
        "section": "Values",
        "quoted_sentence": "MCH: 33.0 pg (ref 27.0–32.0)",
        "severity": "minor",
        "description": "MCH inconsistent with Hb and RBC.",
        "rationale": "MCH = Hb / RBC x 10.",
    }


def test_valid_examples_pass_every_rule(histo, cbc, taxonomy):
    assert check_report(_report(histo), taxonomy) == []
    assert check_report(_report(cbc), taxonomy) == []


# clean control <=> no errors


def test_clean_control_pass(cbc, histo, taxonomy):
    assert check_clean_control(_report(cbc), taxonomy) == []
    assert check_clean_control(_report(histo), taxonomy) == []


def test_clean_control_with_errors_fails(histo, taxonomy):
    histo["is_clean_control"] = True
    assert check_clean_control(_report(histo), taxonomy)


def test_planted_without_errors_fails(cbc, taxonomy):
    cbc["is_clean_control"] = False
    assert check_clean_control(_report(cbc), taxonomy)


# error ids


def test_error_id_pass(histo, taxonomy):
    assert check_error_ids(_report(histo), taxonomy) == []


def test_error_id_wrong_report_fails(histo, taxonomy):
    histo["errors"][0]["error_id"] = "H-002-E1"
    assert check_error_ids(_report(histo), taxonomy)


def test_error_id_duplicate_fails(histo, taxonomy):
    histo["errors"].append(dict(histo["errors"][0]))
    assert check_error_ids(_report(histo), taxonomy)


# error type known and modality matches


def test_error_type_pass(histo, taxonomy):
    assert check_error_types(_report(histo), taxonomy) == []


def test_error_type_wrong_modality_fails(histo, taxonomy):
    histo["errors"][0]["type"] = "C1"
    assert check_error_types(_report(histo), taxonomy)


def test_error_type_unknown_fails(histo, taxonomy):
    histo["errors"][0]["type"] = "H9"
    assert check_error_types(_report(histo), taxonomy)


# quoted sentence occurs verbatim in the named section


def test_quoted_sentence_pass(histo, taxonomy):
    assert check_quoted_sentences(_report(histo), taxonomy) == []


def test_quoted_sentence_not_verbatim_fails(histo, taxonomy):
    histo["errors"][0]["quoted_sentence"] = "Tumour measures 25mm."
    assert check_quoted_sentences(_report(histo), taxonomy)


def test_quoted_sentence_wrong_section_fails(histo, taxonomy):
    histo["errors"][0]["section"] = "Diagnosis"
    assert check_quoted_sentences(_report(histo), taxonomy)


def test_quoted_sentence_missing_section_fails(histo, taxonomy):
    histo["errors"][0]["section"] = "Comment"
    assert check_quoted_sentences(_report(histo), taxonomy)


# section order


def test_section_order_with_optional_sections_pass(histo, taxonomy):
    sections = histo["sections"]
    histo["sections"] = {
        **{k: sections[k] for k in list(sections)[:4]},
        "Immunohistochemistry": "Marker A positive.",
        **{k: sections[k] for k in list(sections)[4:]},
        "Comment": "None.",
    }
    assert check_section_order(_report(histo), taxonomy) == []


def test_section_order_swapped_fails(histo, taxonomy):
    histo["sections"] = dict(reversed(list(histo["sections"].items())))
    assert check_section_order(_report(histo), taxonomy)


def test_section_order_missing_required_fails(cbc, taxonomy):
    del cbc["sections"]["Interpretation"]
    assert check_section_order(_report(cbc), taxonomy)


def test_section_order_unknown_section_fails(histo, taxonomy):
    histo["sections"]["Addendum"] = "Extra text."
    assert check_section_order(_report(histo), taxonomy)


# CBC derived indices


def test_cbc_indices_consistent_pass(cbc, taxonomy):
    assert check_cbc_indices(_report(cbc), taxonomy) == []


@pytest.mark.parametrize(
    "analyte, value",
    [
        ("MCV", 92.0),  # expected 89.36 +/- 2
        ("MCH", 31.0),  # expected 29.79 +/- 1
        ("MCHC", 34.5),  # expected 33.33 +/- 1
        ("Monocytes_pct", 8.0),  # differential sums to 102
        ("Neutrophils_abs", 5.0),  # expected 4.8 +/- 0.1
    ],
)
def test_cbc_indices_inconsistent_fails(cbc, taxonomy, analyte, value):
    cbc["cbc_values"][analyte]["value"] = value
    reasons = check_cbc_indices(_report(cbc), taxonomy)
    assert reasons and all("derived index inconsistency" in r for r in reasons)


def test_cbc_indices_within_tolerance_pass(cbc, taxonomy):
    cbc["cbc_values"]["MCV"]["value"] = 91.3  # 89.36 + 1.94
    cbc["cbc_values"]["Neutrophils_abs"]["value"] = 4.9  # 4.8 + 0.1
    assert check_cbc_indices(_report(cbc), taxonomy) == []


def test_cbc_declared_c2_with_inconsistency_pass(cbc, taxonomy):
    cbc["cbc_values"]["MCH"]["value"] = 33.0
    rerender(cbc)
    cbc["is_clean_control"] = False
    cbc["errors"] = [_c2_error()]
    assert check_report(_report(cbc), taxonomy) == []


def test_cbc_declared_c2_without_inconsistency_fails(cbc, taxonomy):
    cbc["is_clean_control"] = False
    cbc["errors"] = [_c2_error()]
    assert check_cbc_indices(_report(cbc), taxonomy) == [
        "declares a C2 error but every derived index is consistent"
    ]


# folder-level rules, counts and CLI


def _write(folder, name, data):
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def test_folder_pass_and_summary(tmp_path, histo, cbc, taxonomy):
    _write(tmp_path, "H-001.json", histo)
    _write(tmp_path, "C-001.json", cbc)
    result = validate_reports(tmp_path, taxonomy)
    assert result.ok, result.failures
    assert result.summary == (
        "validate: 2 reports | histopathology 1, cbc 1 | dev 1, scored 1 | "
        "clean 1, planted 1 | errors by type: H1 1, H2 0, H3 0, H4 0, H5 0, H6 0, "
        "C1 0, C2 0, C3 0 | overrides 0 | OK"
    )


def test_folder_duplicate_ids_fail(tmp_path, histo, taxonomy):
    _write(tmp_path, "a.json", histo)
    _write(tmp_path, "b.json", histo)
    result = validate_reports(tmp_path, taxonomy)
    assert any("already used" in f for f in result.failures)


def test_folder_unparseable_file_fails(tmp_path, histo, taxonomy):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    histo["unexpected"] = 1
    _write(tmp_path, "extra.json", histo)
    result = validate_reports(tmp_path, taxonomy)
    assert len(result.failures) == 2
    assert all("does not parse" in f for f in result.failures)


def test_expect_counts_pass(tmp_path, histo, cbc, taxonomy):
    _write(tmp_path, "H-001.json", histo)
    _write(tmp_path, "C-001.json", cbc)
    result = validate_reports(tmp_path, taxonomy, expect=2, expect_clean=1, expect_dev=1)
    assert result.ok, result.failures


@pytest.mark.parametrize("kwargs", [{"expect": 34}, {"expect_clean": 9}, {"expect_dev": 4}])
def test_expect_counts_fail(tmp_path, histo, cbc, taxonomy, kwargs):
    _write(tmp_path, "H-001.json", histo)
    _write(tmp_path, "C-001.json", cbc)
    result = validate_reports(tmp_path, taxonomy, **kwargs)
    assert len(result.failures) == 1 and "expected" in result.failures[0]


def test_cli_empty_reports_folder_exits_zero(capsys):
    assert main(["validate", str(REPO_ROOT / "data" / "reports")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("validate: 0 reports | histopathology 0, cbc 0 | dev 0, scored 0")
    assert out.rstrip().endswith("| OK")


def test_cli_failure_exits_nonzero(tmp_path, histo, capsys):
    histo["errors"][0]["quoted_sentence"] = "Not in the report."
    _write(tmp_path, "H-001.json", histo)
    assert main(["validate", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL H-001.json:" in out and "FAILED (1)" in out


def test_cli_expect_flags(tmp_path, histo):
    _write(tmp_path, "H-001.json", histo)
    assert main(["validate", str(tmp_path), "--expect", "1", "--expect-dev", "1"]) == 0
    assert main(["validate", str(tmp_path), "--expect-clean", "1"]) == 1


# CBC units (decision 18)


def test_cbc_units_pass(cbc, taxonomy):
    assert check_cbc_units(_report(cbc), taxonomy) == []


def test_cbc_units_wrong_abs_unit_fails(cbc, taxonomy):
    cbc["cbc_values"]["Neutrophils_abs"]["unit"] = "10^9/L"
    assert check_cbc_units(_report(cbc), taxonomy) == [
        "Neutrophils_abs unit is '10^9/L', required 'x10^9/L'"
    ]


def test_cbc_units_wrong_hb_unit_fails(cbc, taxonomy):
    cbc["cbc_values"]["Hb"]["unit"] = "g/L"
    assert check_cbc_units(_report(cbc), taxonomy) == ["Hb unit is 'g/L', required 'g/dL'"]


# CBC Values text equals the rendered cbc_values (decision 17)


def test_cbc_values_text_pass(cbc, taxonomy):
    assert check_cbc_values_text(_report(cbc), taxonomy) == []


def test_cbc_values_text_one_character_changed_fails(cbc, taxonomy):
    cbc["sections"]["Values"] = cbc["sections"]["Values"].replace("Hb: 14.0", "Hb: 14.1", 1)
    reasons = check_cbc_values_text(_report(cbc), taxonomy)
    assert len(reasons) == 1
    assert reasons[0].endswith("run: uv run pathqc-eval render <file>")


def test_cbc_values_text_failure_names_the_file(tmp_path, cbc, taxonomy):
    cbc["sections"]["Values"] += " "
    _write(tmp_path, "C-001.json", cbc)
    result = validate_reports(tmp_path, taxonomy)
    path = tmp_path / "C-001.json"
    assert result.failures == [
        (
            "C-001.json: Values text does not equal the text rendered from cbc_values; "
            f"run: uv run pathqc-eval render {path}"
        )
    ]


# severity vs taxonomy defaults (decision 19)


def test_severity_default_pass(histo, cbc, taxonomy):
    assert check_severity(_report(histo), taxonomy) == []
    cbc["is_clean_control"] = False
    cbc["errors"] = [_c2_error() | {"severity": "major"}]  # C2 defaults: minor, major
    assert check_severity(_report(cbc), taxonomy) == []


def test_severity_override_without_reason_fails(histo, taxonomy):
    histo["errors"][0]["severity"] = "critical"
    assert check_severity(_report(histo), taxonomy) == [
        "H-001-E1: severity critical is not a default (major) and severity_reason is empty"
    ]


def test_severity_override_blank_reason_fails(histo, taxonomy):
    histo["errors"][0] |= {"severity": "critical", "severity_reason": "   "}
    assert check_severity(_report(histo), taxonomy)


def test_severity_override_with_reason_pass(histo, taxonomy):
    histo["errors"][0] |= {"severity": "critical", "severity_reason": "Size drives pT here."}
    assert check_severity(_report(histo), taxonomy) == []


def test_severity_default_with_reason_fails(histo, taxonomy):
    histo["errors"][0]["severity_reason"] = "Not needed."
    assert check_severity(_report(histo), taxonomy) == [
        "H-001-E1: severity major is a default (major); severity_reason must be null"
    ]


def test_summary_counts_overrides(tmp_path, histo, taxonomy):
    histo["errors"][0] |= {"severity": "critical", "severity_reason": "Size drives pT here."}
    _write(tmp_path, "H-001.json", histo)
    result = validate_reports(tmp_path, taxonomy)
    assert result.ok, result.failures
    assert "| overrides 1 | OK" in result.summary
