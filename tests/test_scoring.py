"""Units, majority and every metric against a small invented example (EVAL-05 6.5, 6.6)."""

import pytest
from scoring_fixtures import (
    DIAGNOSIS,
    INVALID,
    SYNOPTIC,
    all_units,
    finding,
    standard_reports,
    write_run,
    write_tree,
)

from pathqc_eval.scoring import classify_runs, load_inputs, score_body

MICRO = "Microscopic description"
TUMOUR = "Tumour measures 25 mm."
IDS = ("H-001", "H-002", "C-001")


def approx(value: float, abs: float = 1e-6):
    """Metrics are rounded to 6 decimals in the output."""
    return pytest.approx(value, abs=abs)


def _plain_units() -> dict:
    """The plain run of the worked example (see test_metrics_of_the_worked_example)."""
    units = all_units(IDS)
    units[("H-001", 1)] = [finding("H1", MICRO, TUMOUR, 0.9)]
    units[("H-001", 3)] = [
        finding("H1", MICRO, TUMOUR, 0.85),
        finding("H2", "Diagnosis", DIAGNOSIS, 0.3),
    ]
    units[("H-002", 1)] = [finding("H3", "Synoptic summary", SYNOPTIC, 0.7)]
    units[("H-002", 2)] = [finding("H5", "Diagnosis", DIAGNOSIS, 0.65)]
    units[("H-002", 3)] = INVALID
    units[("C-001", 2)] = [
        finding("C1", "Interpretation", "All values within reference ranges.", 0.45)
    ]
    return units


def _structured_units() -> dict:
    units = all_units(IDS)
    for rep in (1, 2, 3):
        units[("H-001", rep)] = [finding("H1", MICRO, TUMOUR, 0.95)]
        units[("H-002", rep)] = [
            finding("H3", "Synoptic summary", SYNOPTIC, 0.9),
            finding("H5", "Diagnosis", DIAGNOSIS, 0.8),
        ]
    return units


def _score(root, plain_units, structured_units):
    write_run(root, "p1", "plain", plain_units)
    write_run(root, "s1", "structured", structured_units)
    inputs, problems = load_inputs(root, "dev", ["p1", "s1"])
    assert problems == []
    views = classify_runs(inputs)
    return score_body(inputs, views, lambda unit, i, o: None)


@pytest.fixture
def tree(tmp_path, histo, cbc):
    return write_tree(tmp_path, standard_reports(histo, cbc))


def test_metrics_of_the_worked_example(tree):
    """Plain run. H-001 (E1 H1 major): r1 hits E1; r2 finds nothing; r3 hits E1 and adds one
    false alarm. E1 is detected in 2 of 3 valid units: detected by majority. FA mean 1/3.
    H-002 (E1 H3 critical; E2 H5 minor omission on the Diagnosis line): r1 hits E1, r2 hits E2
    (type and the anchor's section match), r3 is invalid. Two valid units, so each error must
    be detected in both: neither is. FA mean 0. C-001 (clean): one false alarm in r2; it passes
    in r1 and r3, so it passes by majority. FA mean 1/3.

    Recall: H1 1/1, H3 0/1, H5 0/1, overall 1/3 (Wilson 95%: 0.0615 to 0.7923).
    Severity-weighted recall: detected 2 (major) of 2 + 3 + 1 = 6 -> 1/3.
    False alarms per report: planted (1/3 + 0) / 2 = 1/6; clean 1/3; all (1/3 + 0 + 1/3) / 3 =
    2/9. Specificity: by majority 1/1; per unit 2 of 3 clean units.
    Calibration pairs (confidence, outcome): (0.9, 1), (0.85, 1), (0.3, 0), (0.7, 1),
    (0.65, 1), (0.45, 0). Brier = (0.01 + 0.0225 + 0.09 + 0.09 + 0.1225 + 0.2025) / 6 =
    0.5375 / 6 = 0.089583. ECE, bins of 0.2: 0.3 alone (gap 0.3); 0.45 alone (gap 0.45);
    0.65 and 0.7 (mean 0.675, outcome 1, gap 0.325); 0.85 and 0.9 (mean 0.875, gap 0.125):
    (0.3 + 0.45 + 2 x 0.325 + 2 x 0.125) / 6 = 1.65 / 6 = 0.275.
    Consistency, planted errors: H-001 E1 (yes, no, yes) agrees in 1 of 3 pairs; H-002 E1
    (yes, no) and E2 (no, yes) in 0 of 1: mean (1/3 + 0 + 0) / 3 = 1/9; none is the same in
    every unit. Clean controls, any false alarm (no, yes, no): 1/3; share 0.
    Structured: every error hit in every unit, no false alarm: recall 3/3, FA 0.
    Structured minus plain over all 3 reports: recall 1 - 1/3 = +2/3; FA 0 - 2/9 = -2/9;
    specificity 1 - 1 = 0."""
    body = _score(tree, _plain_units(), _structured_units())
    m = body["conditions"]["plain"]
    assert {t: (p["k"], p["n"]) for t, p in m["per_type_recall"].items() if p["n"]} == {
        "H1": (1, 1),
        "H3": (0, 1),
        "H5": (0, 1),
    }
    assert m["per_type_recall"]["H2"] == {"k": 0, "n": 0, "value": None, "interval": None}
    assert m["overall_recall"]["k"] == 1 and m["overall_recall"]["n"] == 3
    assert [round(x, 4) for x in m["overall_recall"]["interval"]] == [0.0615, 0.7923]
    assert m["severity_weighted_recall"] == {
        "detected_weight": 2,
        "planted_weight": 6,
        "value": approx(1 / 3),
    }
    fa = m["false_alarms_per_report"]
    assert fa["planted"] == {"reports": 2, "mean": approx(1 / 6)}
    assert fa["clean"] == {"reports": 1, "mean": approx(1 / 3)}
    assert fa["all"] == {"reports": 3, "mean": approx(2 / 9)}
    assert m["specificity"]["by_majority"] == {"k": 1, "n": 1, "value": 1.0}
    assert m["specificity"]["per_unit"] == {"k": 2, "n": 3, "value": approx(2 / 3)}
    cal = m["calibration"]
    assert cal["brier"] == approx(0.5375 / 6, abs=1e-6)
    assert cal["ece"] == approx(0.275, abs=1e-6)
    assert (cal["findings"], cal["left_out_miss_or_in_review"], cal["left_out_no_confidence"]) == (
        6, 0, 0,
    )  # fmt: skip
    cons = m["repeat_consistency"]
    assert cons["planted_errors"] == {
        "n": 3,
        "mean_pairwise_agreement": approx(1 / 9),
        "share_same_in_every_unit": 0.0,
    }
    assert cons["clean_controls_any_false_alarm"] == {
        "n": 1,
        "mean_pairwise_agreement": approx(1 / 3),
        "share_same_in_every_unit": 0.0,
    }
    s = body["conditions"]["structured"]
    assert (s["overall_recall"]["k"], s["overall_recall"]["n"]) == (3, 3)
    assert s["false_alarms_per_report"]["all"]["mean"] == 0.0
    comp = body["comparison"]
    assert comp["reports"] == 3 and comp["left_out"] == []
    assert comp["overall_recall"]["difference"] == approx(2 / 3, abs=1e-6)
    assert comp["false_alarms_per_report"]["difference"] == approx(-2 / 9, abs=1e-6)
    assert comp["specificity"]["difference"] == 0.0
    counts = body["counts"]["plain"]
    assert (counts["invalid_units"], counts["findings"], counts["false_alarms"]) == (1, 6, 2)


def test_consistency_when_every_unit_gives_the_same_result(tree):
    """The structured run of the worked example: each of the three planted errors is hit in
    all three units (agreement 1 in every pair; the same in every unit: 3 of 3), and C-001 has
    no false alarm in any unit (agreement 1; 1 of 1)."""
    body = _score(tree, _plain_units(), _structured_units())
    cons = body["conditions"]["structured"]["repeat_consistency"]
    assert cons["planted_errors"] == {
        "n": 3,
        "mean_pairwise_agreement": 1.0,
        "share_same_in_every_unit": 1.0,
    }
    assert cons["clean_controls_any_false_alarm"] == {
        "n": 1,
        "mean_pairwise_agreement": 1.0,
        "share_same_in_every_unit": 1.0,
    }


def test_majority_with_three_valid_units_is_two_of_three(tree):
    """H-001 E1 hit in r1 and r2 only: 2 of 3 -> detected. In r1 only: 1 of 3 -> not."""
    units = all_units(IDS)
    units[("H-001", 1)] = units[("H-001", 2)] = [finding("H1", MICRO, TUMOUR)]
    body = _score(tree, units, all_units(IDS))
    assert body["facts"]["plain"].detected["H-001-E1"] is True
    assert body["facts"]["structured"].detected["H-001-E1"] is False


def test_majority_with_two_valid_units_needs_both(tree):
    """r3 invalid: hit in r1 only -> not detected (1 of 2); hit in r1 and r2 -> detected."""
    one = all_units(IDS)
    one[("H-001", 3)] = INVALID
    one[("H-001", 1)] = [finding("H1", MICRO, TUMOUR)]
    both = all_units(IDS)
    both[("H-001", 3)] = INVALID
    both[("H-001", 1)] = both[("H-001", 2)] = [finding("H1", MICRO, TUMOUR)]
    body = _score(tree, one, both)
    assert body["facts"]["plain"].detected["H-001-E1"] is False
    assert body["facts"]["structured"].detected["H-001-E1"] is True


def test_one_valid_unit_gives_no_majority_result_and_is_listed(tree):
    """H-001 has one valid unit in plain: left out of plain's majority metrics (recall counts
    only H-002's two errors), listed, and left out of the paired comparison; its false alarms
    still count in the per-report mean (one valid unit)."""
    units = all_units(IDS)
    units[("H-001", 1)] = INVALID
    units[("H-001", 2)] = INVALID
    units[("H-001", 3)] = [finding("H2", "Diagnosis", DIAGNOSIS)]
    body = _score(tree, units, all_units(IDS))
    plain = body["conditions"]["plain"]
    assert plain["overall_recall"]["n"] == 2
    assert plain["per_type_recall"]["H1"]["n"] == 0
    assert body["counts"]["plain"]["reports_with_no_majority_result"] == ["H-001"]
    assert body["comparison"]["left_out"] == ["H-001"] and body["comparison"]["reports"] == 2
    assert plain["false_alarms_per_report"]["planted"] == {"reports": 2, "mean": 0.5}
    assert "H-001-E1" not in body["facts"]["plain"].detected


def test_duplicates_are_neither_hits_nor_false_alarms(tree):
    units = all_units(IDS)
    for rep in (1, 2):
        units[("H-001", rep)] = [finding("H1", MICRO, TUMOUR), finding("H1", MICRO, TUMOUR)]
    body = _score(tree, units, all_units(IDS))
    assert body["counts"]["plain"]["duplicates"] == 2
    assert body["counts"]["plain"]["false_alarms"] == 0
    assert body["facts"]["plain"].detected["H-001-E1"] is True
    m = body["conditions"]["plain"]
    assert m["calibration"]["findings"] == 4  # hits and duplicates both count as 1


def test_a_duplicate_counts_as_one_in_calibration(tree):
    """H-001 r1 and r2: two H1 findings each, confidence 0.8: a hit and a duplicate, both
    outcome 1. Brier = 4 x (0.8 - 1)^2 / 4 = 0.04."""
    units = all_units(IDS)
    for rep in (1, 2):
        units[("H-001", rep)] = [finding("H1", MICRO, TUMOUR), finding("H1", MICRO, TUMOUR)]
    body = _score(tree, units, all_units(IDS))
    assert body["conditions"]["plain"]["calibration"]["brier"] == approx(0.04)


def test_a_clean_report_counts_every_finding_as_a_false_alarm(tree):
    units = all_units(IDS)
    units[("C-001", 1)] = [finding("C1", "Values", "Hb: 14.0 g/dL (ref 13.0–17.0)")]
    units[("C-001", 2)] = [finding("C2", "Values", "Hb: 14.0 g/dL (ref 13.0–17.0)")]
    body = _score(tree, units, all_units(IDS))
    m = body["conditions"]["plain"]
    assert m["specificity"]["by_majority"] == {"k": 0, "n": 1, "value": 0.0}
    assert m["false_alarms_per_report"]["clean"]["mean"] == approx(2 / 3)


def test_near_misses_count_for_calibration_and_not_as_false_alarms(tree):
    units = all_units(IDS)
    units[("H-001", 1)] = [finding("H2", MICRO, TUMOUR, confidence=0.4)]
    body = _score(tree, units, all_units(IDS))
    counts = body["counts"]["plain"]
    assert (counts["near_misses"], counts["false_alarms"]) == (1, 0)
    assert body["conditions"]["plain"]["calibration"]["brier"] == approx(0.36)


def test_null_confidence_and_severity_are_counted_and_left_out(tree):
    units = all_units(IDS)
    units[("H-001", 1)] = [finding("H1", MICRO, TUMOUR, confidence=None, severity=None)]
    body = _score(tree, units, all_units(IDS))
    assert body["counts"]["plain"]["null_confidence"] == 1
    assert body["counts"]["plain"]["null_severity"] == 1
    cal = body["conditions"]["plain"]["calibration"]
    assert (cal["findings"], cal["left_out_no_confidence"], cal["brier"]) == (0, 1, None)


def test_dropped_findings_are_counted(tree):
    write_run(tree, "p1", "plain", all_units(IDS), dropped={("H-001", 1): 2})
    write_run(tree, "s1", "structured", all_units(IDS))
    inputs, _ = load_inputs(tree, "dev", ["p1", "s1"])
    body = score_body(inputs, classify_runs(inputs), lambda unit, i, o: None)
    assert body["counts"]["plain"]["dropped_findings"] == 2


def test_severity_weights_use_each_errors_own_severity(tree):
    """Structured detects H-002 E1 (critical, 3) and E2 (minor, 1), not H-001 E1 (major,
    2): 4 of 6."""
    units = all_units(IDS)
    for rep in (1, 2, 3):
        units[("H-002", rep)] = [
            finding("H3", "Synoptic summary", SYNOPTIC),
            finding("H5", "Diagnosis", DIAGNOSIS),
        ]
    body = _score(tree, all_units(IDS), units)
    weighted = body["conditions"]["structured"]["severity_weighted_recall"]
    assert (weighted["detected_weight"], weighted["planted_weight"]) == (4, 6)


def test_identical_conditions_give_a_zero_difference_with_a_zero_interval(tree):
    body = _score(tree, _plain_units(), _plain_units())
    for name in ("overall_recall", "false_alarms_per_report", "specificity"):
        assert body["comparison"][name]["difference"] == 0.0
        assert body["comparison"][name]["interval"] == [0.0, 0.0]


def test_review_findings_count_as_in_review_until_resolved(tree):
    units = all_units(IDS)
    units[("H-001", 1)] = [finding("odd wording", MICRO, TUMOUR)]  # unmapped: review
    body = _score(tree, units, all_units(IDS))
    counts = body["counts"]["plain"]
    assert (counts["review_findings"], counts["still_in_review"]) == (1, 1)
    assert body["conditions"]["plain"]["calibration"]["left_out_miss_or_in_review"] == 1
