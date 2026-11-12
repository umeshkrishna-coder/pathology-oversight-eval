"""EVAL-12 (owner decisions P, Q and R, 2026-11-12): detection by place.

A finding detects a planted error when its section matches and its quoted sentence overlaps one
of the error's places at or above the threshold, whatever its category; omissions go to the
owner as candidates; no category map is used; the sheet shows no category; type agreement is
reported for the structured condition. Invented trees only.
"""

import json

import pytest
from scoring_fixtures import (
    DIAGNOSIS,
    SYNOPTIC,
    Clock,
    all_units,
    error,
    finding,
    report,
    standard_reports,
    write_map,
    write_run,
    write_tree,
)

from pathqc_eval import cli
from pathqc_eval.io import read_report_json
from pathqc_eval.matching import Outcome, classify, resolve
from pathqc_eval.schema import PlantedError

MICRO = "Microscopic description"
TUMOUR = "Tumour measures 25 mm."
IDS = ("H-001", "H-002", "C-001")
PLAIN, STRUCTURED = "dev-plain-run", "dev-structured-run"
ADJ = "results/dev/adjudication"


def _err(n: int, type_: str, section: str, quote: str, kind: str = "statement", places=()):
    return PlantedError(
        error_id=f"H-001-E{n}",
        type=type_,
        section=section,
        quoted_sentence=quote,
        severity="major",
        description="d",
        rationale="r",
        kind=kind,
        other_places=[{"section": s, "quoted_sentence": q} for s, q in places],
    )


STATEMENT = _err(1, "H1", MICRO, "Tumour measures 25 mm in the sections.")
OMISSION = _err(2, "H5", "Diagnosis", "Invasive tumour, grade 2.", kind="omission")


# The rules, one minimal example each (matching)


def test_a_finding_at_the_place_is_a_hit_whatever_its_category():
    result = classify(MICRO, "Tumour measures 25 mm in the sections.", [STATEMENT])
    assert (result.outcome, result.error_id, result.overlap) == ("hit", "H-001-E1", 1.0)


def test_a_finding_at_an_other_place_is_a_hit():
    err = _err(1, "H1", MICRO, "Tumour measures 25 mm.", places=[("Gross description", "18 mm")])
    result = classify("Gross description", "A firm lesion 18 mm across.", [err])
    assert (result.outcome, result.error_id) == ("hit", "H-001-E1")


def test_a_partial_overlap_in_the_right_section_is_a_borderline_review():
    result = classify(MICRO, "Tumour measures twenty five.", [STATEMENT])  # 2 of 4 tokens: 0.5
    assert (result.outcome, result.reason, result.error_ids) == (
        "review", "borderline_overlap", ("H-001-E1",)
    )  # fmt: skip


def test_the_right_sentence_in_another_section_is_a_section_mismatch_review():
    result = classify("Diagnosis", "Tumour measures 25 mm in the sections.", [STATEMENT])
    assert (result.outcome, result.reason) == ("review", "section_mismatch")


def test_there_is_no_automatic_near_miss():
    result = classify(MICRO, "Tumour measures 25 mm in the sections.", [STATEMENT])
    assert result.outcome == "hit"  # the category is not even an argument any more


def test_an_omission_is_never_an_automatic_hit():
    result = classify("Diagnosis", "Invasive tumour, grade 2.", [OMISSION])
    assert (result.outcome, result.reason, result.error_ids) == (
        "review", "omission_candidate", ("H-001-E2",)
    )  # fmt: skip


def test_any_finding_in_a_report_with_an_omission_is_a_candidate_for_it():
    result = classify("Clinical details", "Nothing related at all.", [STATEMENT, OMISSION])
    assert (result.outcome, result.error_ids, result.reasons) == (
        "review", ("H-001-E2",), ("omission_candidate",)
    )  # fmt: skip


def test_a_hit_for_one_error_is_not_a_review_item_for_any_other():
    result = classify(MICRO, "Tumour measures 25 mm in the sections.", [STATEMENT, OMISSION])
    assert (result.outcome, result.error_id, result.error_ids) == ("hit", "H-001-E1", ())


def test_a_finding_that_is_not_a_hit_may_be_a_review_item_for_several_errors():
    result = classify(MICRO, "Tumour measures twenty five.", [STATEMENT, OMISSION])
    assert (result.outcome, result.error_ids, result.reasons) == (
        "review",
        ("H-001-E1", "H-001-E2"),
        ("borderline_overlap", "omission_candidate"),
    )


def test_a_finding_related_to_no_error_is_a_false_alarm():
    assert classify("Clinical details", "Nothing related.", [STATEMENT]) == Outcome("false_alarm")
    assert classify(MICRO, "Tumour measures 25 mm.", []) == Outcome("false_alarm")  # clean


def test_a_finding_at_two_errors_places_is_one_hit_by_the_existing_precedence():
    """EVAL-10's rule is kept: one outcome per finding; the highest overlap, then the lowest
    error id."""
    e1 = _err(1, "H1", "Gross description", "Fatty tissue.", places=[("Diagnosis", "pT3 here.")])
    e3 = _err(3, "H3", "Diagnosis", "pT3 here.")
    result = classify("Diagnosis", "pT3 here.", [e1, e3])
    assert (result.outcome, result.error_id) == ("hit", "H-001-E1")


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ({"H-001-E1": "detected", "H-001-E2": "false_alarm"}, ("hit", ("H-001-E1",))),
        ({"H-001-E1": "false_alarm", "H-001-E2": "detected"}, ("hit", ("H-001-E2",))),
        ({"H-001-E1": "near_miss", "H-001-E2": "miss"}, ("near_miss", ("H-001-E1",))),
        ({"H-001-E1": "false_alarm", "H-001-E2": "miss"}, ("miss", ("H-001-E2",))),
        ({"H-001-E1": "false_alarm", "H-001-E2": "false_alarm"}, ("false_alarm", ())),
    ],
)
def test_verdicts_on_mixed_review_items_combine_as_decision_50(verdicts, expected):
    review = classify(MICRO, "Tumour measures twenty five.", [STATEMENT, OMISSION])
    (resolved,) = resolve([review], lambda i, o: verdicts[o.error_id])
    assert (resolved.outcome, resolved.ids) == expected


def test_each_review_item_is_asked_with_its_own_reason():
    review = classify(MICRO, "Tumour measures twenty five.", [STATEMENT, OMISSION])
    asked = []
    resolve([review], lambda i, o: asked.append((o.error_id, o.reason)) or "false_alarm")
    assert asked == [("H-001-E1", "borderline_overlap"), ("H-001-E2", "omission_candidate")]


# Scoring through the CLI


@pytest.fixture
def tree(tmp_path, histo, cbc, monkeypatch):
    root = write_tree(tmp_path, standard_reports(histo, cbc))
    monkeypatch.setattr(cli, "SCORE_ROOT", root)
    monkeypatch.setattr(cli, "SCORE_CLOCK", Clock())
    monkeypatch.setattr(cli, "SCORER_COMMIT", lambda: "0123abc")
    return root


def _main(*args: str) -> int:
    return cli.main(list(args))


def _score(root) -> dict:
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    return read_report_json(root / "results" / "dev" / "score.json")


def test_any_label_at_a_planted_place_is_a_hit_in_both_conditions(tree):
    plain, structured = all_units(IDS), all_units(IDS)
    for rep, label in zip((1, 2, 3), ("weird label", "size thing", "nonsense"), strict=True):
        plain[("H-001", rep)] = [finding(label, MICRO, TUMOUR)]
    for rep, label in zip((1, 2, 3), ("other", "H6", "H1"), strict=True):
        structured[("H-001", rep)] = [finding(label, MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    assert not (tree / "data" / "category_map.json").exists()
    score = _score(tree)
    for cond in ("plain", "structured"):
        assert score["metrics"][cond]["per_type_recall"]["H1"]["k"] == 1
        assert score["counts"]["by_condition"][cond]["false_alarms"] == 0
    assert {f["outcome"] for f in score["findings"]} == {"hit"}
    assert score["counts"]["review_findings"] == 0
    assert "category_map" not in score["inputs"]


def test_a_category_map_if_present_is_ignored(tree):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("size problem", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    first = _score(tree)
    write_map(tree, {"size problem": "H6"}, status="approved", version="9.9")
    assert _score(tree) == first
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert "Category map" not in summary


def test_omission_candidates_go_to_the_owner_one_item_per_omission(tree, histo):
    """H-003 has two omissions; one finding in it gives two items."""
    data = report(
        histo,
        "H-003",
        "dev",
        [
            error("H5", "Diagnosis", DIAGNOSIS, "minor", kind="omission"),
            error("H5", "Synoptic summary", SYNOPTIC, "major", kind="omission"),
        ],
    )
    (tree / "data" / "reports" / "H-003.json").write_text(json.dumps(data), encoding="utf-8")
    ids = (*IDS, "H-003")
    plain = all_units(ids)
    plain[("H-003", 1)] = [finding("H5", "Diagnosis", DIAGNOSIS)]  # even at the anchor
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(ids))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    items = read_report_json(tree / ADJ / "adjudication.json")["items"]
    assert sorted((i["candidate_error_id"], i["review_reason"]) for i in items) == [
        ("H-003-E1", "omission_candidate"),
        ("H-003-E2", "omission_candidate"),
    ]


def test_the_sheet_and_adjudication_json_show_no_category(tree):
    """H-001 E1 is H1; the finding's category is the taxonomy id H6, which must not reach the
    owner. H-002 has an omission, so any finding there is a candidate."""
    plain = all_units(IDS)
    neutral = {"rationale": "Invented rationale."}  # the fixture's own names the label
    plain[("H-002", 1)] = [finding("ZZ-LABEL-QX", MICRO, TUMOUR) | neutral]
    structured = all_units(IDS)
    structured[("H-002", 2)] = [finding("H6", "Clinical details", "Synthetic test case.") | neutral]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    data = read_report_json(tree / ADJ / "adjudication.json")
    assert data["items"] and all("category" not in item for item in data["items"])
    for name in ("adjudication.json", "adjudication_sheet.md"):
        text = (tree / ADJ / name).read_text(encoding="utf-8")
        assert "ZZ-LABEL-QX" not in text and "H6" not in text and "category:" not in text
    sheet = (tree / ADJ / "adjudication_sheet.md").read_text(encoding="utf-8")
    assert "# rationale:" in sheet and "# why it needs you:" in sheet


def test_items_merge_only_when_report_section_quote_rationale_and_error_agree(tree):
    same = finding("one label", MICRO, TUMOUR)
    relabelled = same | {"category": "another label"}  # the category does not separate them
    reworded = same | {"rationale": "Another rationale."}
    plain = all_units(IDS)
    plain[("H-002", 1)] = [same]
    plain[("H-002", 2)] = [relabelled]
    structured = all_units(IDS)
    structured[("H-002", 1)] = [reworded]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    hidden = read_report_json(tree / ADJ / "adjudication_hidden.json")
    groups = sorted(sorted((r["run_id"], r["repeat"]) for r in refs) for refs in hidden.values())
    assert groups == [[(PLAIN, 1), (PLAIN, 2)], [(STRUCTURED, 1)]]


def test_type_agreement_is_reported_for_the_structured_condition(tree):
    """Structured hits and duplicates: H-001-E1 (H1) r1 'H1' and a duplicate 'other', r2
    'h1.', r3 'H6' -> 2 of 4; H-002-E1 (H3) r1 'H3', r2 'other' -> 1 of 2; overall 3 of 6.
    Plain labels: 'weird label' and 'size thing' (twice) -> 2 distinct."""
    structured = all_units(IDS)
    structured[("H-001", 1)] = [finding("H1", MICRO, TUMOUR), finding("other", MICRO, TUMOUR)]
    structured[("H-001", 2)] = [finding("h1.", MICRO, TUMOUR)]
    structured[("H-001", 3)] = [finding("H6", MICRO, TUMOUR)]
    structured[("H-002", 1)] = [finding("H3", "Synoptic summary", SYNOPTIC)]
    structured[("H-002", 2)] = [finding("other", "Synoptic summary", SYNOPTIC)]
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("weird label", MICRO, TUMOUR)]
    plain[("H-001", 2)] = [finding("Size thing", MICRO, TUMOUR)]
    plain[("H-001", 3)] = [finding("size thing.", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    score = _score(tree)
    agreement = score["metrics"]["structured"]["type_agreement"]
    assert (agreement["overall"]["k"], agreement["overall"]["n"]) == (3, 6)
    per = {t: (v["k"], v["n"]) for t, v in agreement["per_type"].items() if v["n"]}
    assert per == {"H1": (2, 4), "H3": (1, 2)}
    plain_labels = score["metrics"]["plain"]["type_agreement"]
    assert plain_labels == {"labels_scored": False, "distinct_labels": 2}
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    section = summary.split("## Type agreement")[1].split("\n## ")[0]
    assert "| Overall | 3/6 = 50.0% |" in section
    assert "| H1 | 2/4 = 50.0% |" in section
    assert (
        "Plain condition: labels were free text and were not scored (2 distinct labels)." in section
    )


def test_the_disclosure_says_what_a_detection_is_and_what_the_sheet_hid(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    _score(tree)
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    for words in (
        "A detection means the finding quoted the planted sentence or one of its named other "
        "places, in the right section",
        "Labels (categories) were not used to decide detections.",
        "The adjudication sheet showed no category, condition, repeat, model or run.",
    ):
        assert words in summary, words


def test_map_list_lists_categories_and_no_longer_speaks_of_mapping(tree, capsys):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("Size mismatch", MICRO, TUMOUR), finding("H1", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    write_map(tree, {"size mismatch": "H1"})
    assert _main("map-list", "--runs", PLAIN) == 0
    out = capsys.readouterr().out.lower()
    assert "maps to" not in out and "unmapped" not in out and "category map" not in out
    data = read_report_json(tree / "results" / "dev" / "category_strings.json")
    assert "category_map" not in data
    assert data["categories"] == [
        {"category": "h1", "count": {"plain": 1, "structured": 0}},
        {"category": "size mismatch", "count": {"plain": 1, "structured": 0}},
    ]
