import json

import pytest
from conftest import rerender

from pathqc_eval.cli import main
from pathqc_eval.schema import Report
from pathqc_eval.validate import (
    check_cbc_indices,
    check_cbc_units,
    check_cbc_values_text,
    check_clean_control,
    check_error_ids,
    check_error_types,
    check_omission_anchor,
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
        "C1 0, C2 0, C3 0 | overrides 0 | omissions 0 | OK"
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


def test_cli_empty_reports_folder_exits_zero(tmp_path, capsys):
    """An empty reports folder (only .gitkeep, as data/reports/ is before `plant`). It is a
    temporary folder: the repository's data/reports/ fills up once the owner plants (S9)."""
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    assert main(["validate", str(tmp_path)]) == 0
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
    assert "| overrides 1 | omissions 0 | OK" in result.summary


def test_summary_override_without_reason_counts_zero_and_fails(tmp_path, histo, taxonomy):
    histo["errors"][0]["severity"] = "critical"  # H1 default is major; no severity_reason
    _write(tmp_path, "H-001.json", histo)
    result = validate_reports(tmp_path, taxonomy)
    assert len(result.failures) == 1 and "severity_reason is empty" in result.failures[0]
    assert "| overrides 0 | omissions 0 | FAILED (1)" in result.summary


# drafts mode relaxes exactly one rule


def test_drafts_mode_skips_only_clean_control(histo, taxonomy):
    histo["errors"] = []  # planted row before the owner plants anything
    report = _report(histo)
    assert check_clean_control(report, taxonomy)
    assert check_report(report, taxonomy, drafts=True) == []
    histo["sections"]["Addendum"] = "Extra."
    assert check_report(_report(histo), taxonomy, drafts=True) == ["unknown section 'Addendum'"]


def test_drafts_mode_summary_label(tmp_path, histo, taxonomy):
    histo["errors"] = []
    _write(tmp_path, "H-001.json", histo)
    result = validate_reports(tmp_path, taxonomy, drafts=True)
    assert result.ok, result.failures
    assert result.summary.startswith("validate (drafts): 1 reports")


# omission errors (decision 34)


def _omission(histo: dict) -> dict:
    """H5 omission: PNI is missing; the anchor is the Synoptic line next to where it belongs."""
    histo["sections"]["Synoptic summary"] = (
        "Tumour size: 18 mm\nHistologic grade: 2\nMargins: Clear\n"
        "Lymphovascular invasion: Absent\nLymph nodes (positive/total): 0/3\npT: pT1c\npN: pN0\n"
        "Staging edition: AJCC 8th edition"  # decision 27, checked since EVAL-09 H8
    )
    histo["errors"][0] |= {
        "type": "H5",
        "kind": "omission",
        "section": "Synoptic summary",
        "quoted_sentence": "Lymphovascular invasion: Absent",
        "description": "Perineural invasion is not reported.",
        "rationale": "PNI is a required synoptic element.",
    }
    return histo


def test_omission_anchor_passes(histo, taxonomy):
    assert check_report(_report(_omission(histo)), taxonomy) == []


def test_omission_anchor_must_be_verbatim(histo, taxonomy):
    data = _omission(histo)
    data["errors"][0]["quoted_sentence"] = "Perineural invasion: Absent"
    assert check_quoted_sentences(_report(data), taxonomy) == [
        "H-001-E1: anchor (omission) does not occur verbatim in 'Synoptic summary'"
    ]


def test_omission_anchor_must_be_in_its_section(histo, taxonomy):
    data = _omission(histo)
    data["errors"][0]["section"] = "Diagnosis"
    assert check_quoted_sentences(_report(data), taxonomy) == [
        "H-001-E1: anchor (omission) does not occur verbatim in 'Diagnosis'"
    ]


def test_cbc_omission_anchor_is_a_values_line(cbc, taxonomy):
    line = next(x for x in cbc["sections"]["Values"].splitlines() if x.startswith("Hb:"))
    cbc |= {"is_clean_control": False}
    cbc["errors"] = [
        {
            "error_id": "C-001-E1",
            "type": "C3",
            "kind": "omission",
            "section": "Values",
            "quoted_sentence": line,
            "severity": "critical",
            "description": "No flag or comment for the haemoglobin value.",
            "rationale": "A critical value needs a flag and a recommendation.",
        }
    ]
    assert check_report(_report(cbc), taxonomy) == []


def test_summary_counts_omissions(tmp_path, histo, cbc, taxonomy):
    _write(tmp_path, "H-001.json", _omission(histo))
    _write(tmp_path, "C-001.json", cbc)
    result = validate_reports(tmp_path, taxonomy)
    assert result.ok, result.failures
    assert result.summary.endswith("| overrides 0 | omissions 1 | OK")


# EVAL-04 (owner decision, amends 34): an omission's anchor is in Values (CBC) or in the
# Synoptic summary or the Diagnosis (histopathology).


def _anchored_in(histo: dict, section: str, anchor: str) -> Report:
    data = _omission(histo)
    data["errors"][0] |= {"section": section, "quoted_sentence": anchor}
    return _report(data)


@pytest.mark.parametrize(
    ("section", "anchor"),
    [
        ("Synoptic summary", "Lymphovascular invasion: Absent"),
        ("Diagnosis", "Invasive tumour, grade 2."),
    ],
)
def test_histopathology_omission_anchor_in_an_allowed_section_passes(
    histo, taxonomy, section, anchor
):
    report = _anchored_in(histo, section, anchor)
    assert check_omission_anchor(report, taxonomy) == []
    assert check_report(report, taxonomy) == []


def test_histopathology_omission_anchor_elsewhere_fails(histo, taxonomy):
    report = _anchored_in(histo, "Microscopic description", "Tumour measures 25 mm.")
    assert check_quoted_sentences(report, taxonomy) == []  # the anchor itself is verbatim
    assert check_omission_anchor(report, taxonomy) == [
        "H-001-E1: an omission's anchor must be in 'Synoptic summary' or 'Diagnosis', "
        "not in 'Microscopic description'"
    ]


def _cbc_omission(cbc: dict, section: str, anchor: str) -> Report:
    cbc |= {"is_clean_control": False}
    cbc["errors"] = [
        {
            "error_id": "C-001-E1",
            "type": "C3",
            "kind": "omission",
            "section": section,
            "quoted_sentence": anchor,
            "severity": "critical",
            "description": "No flag or comment for the value.",
            "rationale": "A critical value needs a flag and a recommendation.",
        }
    ]
    return _report(cbc)


def test_cbc_omission_anchor_in_values_passes(cbc, taxonomy):
    line = next(x for x in cbc["sections"]["Values"].splitlines() if x.startswith("Hb:"))
    report = _cbc_omission(cbc, "Values", line)
    assert check_omission_anchor(report, taxonomy) == []


def test_cbc_omission_anchor_elsewhere_fails(cbc, taxonomy):
    report = _cbc_omission(cbc, "Interpretation", "All values within reference ranges.")
    assert check_quoted_sentences(report, taxonomy) == []
    assert check_omission_anchor(report, taxonomy) == [
        "C-001-E1: an omission's anchor must be in 'Values', not in 'Interpretation'"
    ]
    assert check_report(report, taxonomy) == [
        "C-001-E1: an omission's anchor must be in 'Values', not in 'Interpretation'"
    ]


def test_a_statement_error_is_not_held_to_the_anchor_sections(histo, taxonomy):
    assert check_omission_anchor(_report(histo), taxonomy) == []  # H1 in Microscopic description


# EVAL-09 H7 and H8 (owner decisions, 2026-11-11; decisions 23 and 27)

STAGING = "Staging edition: AJCC 8th edition"
NO_STAGING = "Size 18 mm; grade 2; margins clear; LVI absent; PNI absent; nodes 0/3; pT1c pN0."
STAGING_PROBLEM = f"the last line of 'Synoptic summary' must be '{STAGING}' (decision 27)"


def _with_synoptic(histo: dict, text: str) -> dict:
    histo["sections"]["Synoptic summary"] = text
    return histo


def _extra_errors(histo: dict, count: int) -> dict:
    first = histo["errors"][0]
    histo["errors"] = [first | {"error_id": f"H-001-E{i}"} for i in range(1, count + 1)]
    return histo


@pytest.mark.parametrize("count", [1, 2, 3])
def test_one_to_three_planted_errors_pass(histo, taxonomy, count):
    _with_synoptic(histo, f"{NO_STAGING}\n{STAGING}")
    assert check_report(_report(_extra_errors(histo, count)), taxonomy) == []


def test_four_planted_errors_fail(histo, taxonomy):
    _with_synoptic(histo, f"{NO_STAGING}\n{STAGING}")
    assert check_report(_report(_extra_errors(histo, 4)), taxonomy) == [
        "4 planted errors; a planted report carries at most 3 (decision 23)"
    ]


def test_the_staging_line_last_passes(histo, taxonomy):
    assert check_report(_report(_with_synoptic(histo, f"{NO_STAGING}\n{STAGING}")), taxonomy) == []


@pytest.mark.parametrize(
    "text",
    [NO_STAGING, f"{STAGING}\n{NO_STAGING}", f"{NO_STAGING}\nStaging edition: AJCC 7th edition"],
)
@pytest.mark.parametrize("drafts", [False, True])
def test_a_synoptic_summary_not_ending_with_the_staging_line_fails(histo, taxonomy, text, drafts):
    _with_synoptic(histo, text)
    assert check_report(_report(histo), taxonomy, drafts=drafts) == [STAGING_PROBLEM]


def test_a_clean_control_needs_the_staging_line_too(histo, taxonomy):
    histo |= {"is_clean_control": True, "errors": []}
    _with_synoptic(histo, NO_STAGING)
    assert check_report(_report(histo), taxonomy) == [STAGING_PROBLEM]


def test_trailing_blank_lines_after_the_staging_line_pass(histo, taxonomy):
    _with_synoptic(histo, f"{NO_STAGING}\n{STAGING}  \n\n")
    assert check_report(_report(histo), taxonomy) == []


def test_a_planted_error_quoting_the_last_line_allows_another_edition(histo, taxonomy):
    changed = "Staging edition: AJCC 7th edition"
    _with_synoptic(histo, f"{NO_STAGING}\n{changed}")
    histo["errors"] = [
        histo["errors"][0]
        | {
            "type": "H3",
            "section": "Synoptic summary",
            "quoted_sentence": changed,
            "severity": "critical",
        }
    ]
    assert check_report(_report(histo), taxonomy) == []


def test_an_omission_anchored_on_the_last_line_allows_the_staging_line_to_go(histo, taxonomy):
    _with_synoptic(histo, f"{NO_STAGING}\nnodes 0/3")
    histo["errors"] = [
        histo["errors"][0]
        | {
            "type": "H5",
            "section": "Synoptic summary",
            "quoted_sentence": "nodes 0/3",
            "severity": "minor",
            "kind": "omission",
        }
    ]
    assert check_report(_report(histo), taxonomy) == []


def test_a_planted_error_elsewhere_does_not_excuse_the_staging_line(histo, taxonomy):
    assert histo["errors"][0]["section"] == "Microscopic description"
    _with_synoptic(histo, NO_STAGING)
    assert check_report(_report(histo), taxonomy) == [STAGING_PROBLEM]


def test_cbc_reports_have_no_staging_line(cbc, taxonomy):
    assert check_report(_report(cbc), taxonomy) == []
