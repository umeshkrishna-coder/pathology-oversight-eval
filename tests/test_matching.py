"""Text handling, category mapping and the classification rules (EVAL-05 6.2 to 6.4)."""

import pytest

from pathqc_eval.matching import (
    Outcome,
    classify,
    map_category,
    normalise_category,
    normalise_section,
    overlap,
    resolve,
    tokens,
)
from pathqc_eval.schema import PlantedError

IDS = ["H1", "H2", "H3", "H4", "H5", "H6", "C1", "C2", "C3"]


def _error(n: int, type_: str, section: str, quote: str, kind: str = "statement"):
    return PlantedError(
        error_id=f"H-001-E{n}",
        type=type_,
        section=section,
        quoted_sentence=quote,
        severity="major",
        description="d",
        rationale="r",
        kind=kind,
    )


# 6.2 Text handling


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Diagnosis", "diagnosis"),
        ("  Synoptic   summary:", "synoptic summary"),
        ("DIAGNOSIS.", "diagnosis"),
        ("Comment/recommendation", "comment/recommendation"),
        ("Gross\tdescription :", "gross description"),
    ],
)
def test_normalise_section(text, expected):
    assert normalise_section(text) == expected


def test_tokens_keep_a_decimal_point_between_digits():
    assert tokens("Hb 6.2 g/dL; MCV 101.") == {"hb", "6.2", "g", "dl", "mcv", "101"}
    assert tokens("pT1c pN0, grade 2.") == {"pt1c", "pn0", "grade", "2"}
    assert tokens("x10^9/L") == {"x10", "9", "l"}
    assert tokens("") == set() and tokens("—, .") == set()


def test_overlap_takes_the_larger_direction():
    planted = "Tumour measures 25 mm."  # tumour, measures, 25, mm
    # The finding quotes more: all 4 planted tokens of its 8 -> max(4/8, 4/4) = 1.0
    assert overlap("Sections show that the tumour measures 25 mm.", planted) == 1.0
    assert overlap(planted, "Sections show that the tumour measures 25 mm.") == 1.0
    # The finding quotes less: 2 of its 2, 2 of the planted 4 -> max(2/2, 2/4) = 1.0
    assert overlap("25 mm", planted) == 1.0
    # tumour, size, given, as, 25, cm: shared tumour and 25 -> max(2/6, 2/4) = 0.5
    assert overlap("Tumour size given as 25 cm", planted) == 0.5
    assert overlap("", planted) == 0.0 and overlap(planted, "...") == 0.0


def test_overlap_treats_a_decimal_as_one_token():
    # {hb, 6.2} against {hb, 6, 2}: only hb is shared -> max(1/2, 1/3) = 0.5
    assert overlap("Hb 6.2", "Hb 6 2") == 0.5
    assert overlap("Hb 6.2", "Hb 6.2") == 1.0
    assert overlap("Hb 6.2", "Hb 6.20") == 0.5  # 6.2 and 6.20 are different tokens


# 6.3 Mapping


def test_a_category_equal_to_a_taxonomy_id_maps_to_it():
    assert map_category("H1", IDS, {}) == "H1"
    assert map_category(" h1. ", IDS, {"h1": "H2"}) == "H1"


def test_other_maps_to_other_and_the_map_decides_the_rest():
    mapping = {"size mismatch": "H1", "style": "other"}
    assert map_category("Other", IDS, {}) == "other"
    assert map_category("Size  MISMATCH!", IDS, mapping) == "H1"
    assert map_category("style", IDS, mapping) == "other"
    assert map_category("something odd", IDS, mapping) == "unmapped"


def test_the_same_string_always_maps_the_same_way():
    mapping = {"size mismatch": "H1"}
    results = {map_category(text, IDS, mapping) for text in ("Size mismatch", "size mismatch.")}
    assert results == {"H1"}


def test_normalise_category_drops_trailing_punctuation():
    """6.3: casefold, strip, collapse whitespace, drop trailing punctuation: every Unicode
    punctuation character at the end goes, closing brackets and quotes included; a symbol
    such as + is not punctuation."""
    assert normalise_category("  Size   Mismatch?!  ") == "size mismatch"
    assert normalise_category("C2 (indices).") == "c2 (indices"
    assert normalise_category("“Size mismatch”") == "“size mismatch"
    assert normalise_category("H1) -") == "h1"
    assert normalise_category("H1 +") == "h1 +"


# 6.4 Classification


STATEMENT = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm.")
OMISSION = _error(2, "H5", "Synoptic summary", "LVI absent; PNI absent.", kind="omission")


@pytest.mark.parametrize(
    ("mapped", "section", "quote", "expected"),
    [
        ("H1", "Microscopic description", "Tumour measures 25 mm.", ("hit", None)),
        ("H2", "Microscopic description", "Tumour measures 25 mm.", ("near_miss", None)),
        ("other", "Microscopic description", "Tumour measures 25 mm.", ("near_miss", None)),
        ("unmapped", "Microscopic description", "Tumour measures 25 mm.",
         ("review", "unmapped_category")),
        ("H1", "Microscopic description", "Tumour size given as 25 cm",
         ("review", "borderline_overlap")),
        ("H1", "Diagnosis", "Tumour measures 25 mm.", ("review", "section_mismatch")),
        ("H1", "Microscopic description", "Grade is two.", ("false_alarm", None)),
        ("H2", "Diagnosis", "Tumour measures 25 mm.", ("false_alarm", None)),
    ],
)  # fmt: skip
def test_statement_rules(mapped, section, quote, expected):
    result = classify(section, quote, mapped, [STATEMENT])
    assert (result.outcome, result.reason) == expected
    if expected[0] != "false_alarm":
        assert result.error_id == "H-001-E1"


BOUNDARY = _error(1, "H1", "Microscopic description", "alpha beta gamma delta epsilon")


@pytest.mark.parametrize(
    ("mapped", "section", "quote", "expected"),
    [
        # 3 of 5 tokens shared: ov 0.6 exactly, the threshold
        ("H1", "Microscopic description", "alpha beta gamma zeta eta", ("hit", None)),
        ("unmapped", "Microscopic description", "alpha beta gamma zeta eta",
         ("review", "unmapped_category")),
        ("H1", "Diagnosis", "alpha beta gamma zeta eta", ("review", "section_mismatch")),
        # 2 of 5: ov 0.4 exactly, the low end of the borderline band
        ("H1", "Microscopic description", "alpha beta zeta eta theta",
         ("review", "borderline_overlap")),
        ("unmapped", "Microscopic description", "alpha beta zeta eta theta", ("false_alarm", None)),
        # 1 of 5: ov 0.2, below the band
        ("H1", "Microscopic description", "alpha zeta eta theta iota", ("false_alarm", None)),
        ("unmapped", "Microscopic description", "zeta eta theta iota kappa", ("false_alarm", None)),
    ],
)  # fmt: skip
def test_statement_rules_at_the_boundaries(mapped, section, quote, expected):
    result = classify(section, quote, mapped, [BOUNDARY])
    assert (result.outcome, result.reason) == expected


def test_a_point_between_a_letter_and_a_digit_splits_tokens():
    assert tokens("Fig.5") == {"fig", "5"}
    assert tokens("5.a") == {"5", "a"}
    assert tokens("6.2.1") == {"6.2.1"}


@pytest.mark.parametrize(
    ("mapped", "section", "quote", "expected"),
    [
        ("H5", "Synoptic summary", "Anything at all", ("hit", None)),
        ("H5", "Microscopic description", "LVI absent; PNI absent.",
         ("review", "omission_other_section")),
        ("unmapped", "Synoptic summary", "LVI absent; PNI absent.",
         ("review", "unmapped_category")),
        ("unmapped", "Synoptic summary", "Something unrelated",
         ("review", "unmapped_omission")),  # EVAL-09 C; a false alarm before
        ("H4", "Synoptic summary", "LVI absent; PNI absent.", ("false_alarm", None)),
    ],
)  # fmt: skip
def test_omission_rules(mapped, section, quote, expected):
    result = classify(section, quote, mapped, [OMISSION])
    assert (result.outcome, result.reason) == expected


def test_hit_comes_before_review_before_near_miss():
    near = _error(1, "H2", "Microscopic description", "Tumour measures 25 mm.")
    review = _error(2, "H1", "Diagnosis", "Tumour measures 25 mm.")
    hit = _error(3, "H1", "Microscopic description", "Tumour measures 25 mm. Margins clear.")
    # E1 would be a near_miss (H2), E2 a review (section_mismatch), E3 a hit.
    found = classify("Microscopic description", "Tumour measures 25 mm.", "H1", [near, review, hit])
    assert (found.outcome, found.error_id) == ("hit", "H-001-E3")
    found = classify("Microscopic description", "Tumour measures 25 mm.", "H1", [near, review])
    assert (found.outcome, found.reason, found.error_id) == (
        "review", "section_mismatch", "H-001-E2",
    )  # fmt: skip
    found = classify("Microscopic description", "Tumour measures 25 mm.", "H1", [near])
    assert (found.outcome, found.error_id) == ("near_miss", "H-001-E1")


def test_within_a_level_the_highest_overlap_then_the_lowest_error_id_wins():
    partial = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm in total size.")
    exact = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm.")
    found = classify("Microscopic description", "Tumour measures 25 mm.", "H1", [partial, exact])
    # E1: 4 shared of the finding's 4 -> 1.0 as well; E2: 1.0: a tie, so the lowest id, E1
    assert found.error_id == "H-001-E1"
    other = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm and more mm.")
    tenth = _error(10, "H1", "Microscopic description", "Tumour measures 25 mm.")
    found = classify("Microscopic description", "Tumour measures 25 mm.", "H1", [tenth, other])
    assert found.error_id == "H-001-E2"  # E2 before E10: numbers, not text, are compared


def test_highest_overlap_wins_over_a_lower_error_id():
    weaker = _error(1, "H1", "Microscopic description", "Grade two tumour, 25 mm, said the report.")
    stronger = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm.")
    quote = "Tumour measures 25 mm."
    assert overlap(quote, weaker.quoted_sentence) < overlap(quote, stronger.quoted_sentence)
    assert classify("Microscopic description", quote, "H1", [weaker, stronger]).error_id == (
        "H-001-E2"
    )


def test_every_finding_in_a_clean_report_is_a_false_alarm():
    assert classify("Interpretation", "All values within range.", "C1", []) == Outcome(
        "false_alarm"
    )


def test_further_hits_on_the_same_error_are_duplicates():
    base = [
        Outcome("hit", "H-001-E1", None, 1.0),
        Outcome("false_alarm"),
        Outcome("hit", "H-001-E1", None, 0.8),
        Outcome("hit", "H-001-E2", None, 1.0),
    ]
    resolved = resolve(base, lambda i, o: None)
    assert [o.outcome for o in resolved] == ["hit", "false_alarm", "duplicate", "hit"]


def test_verdicts_resolve_review_findings():
    base = [
        Outcome("review", "H-001-E1", "section_mismatch", 1.0),
        Outcome("review", "H-001-E2", "borderline_overlap", 0.5),
        Outcome("review", "H-001-E1", "unmapped_category", 1.0),
        Outcome("review", "H-001-E2", "unmapped_category", 1.0),
        Outcome("review", "H-001-E1", "section_mismatch", 0.9),
    ]
    verdicts = {1: "detected", 2: "near_miss", 3: "false_alarm", 4: "miss", 5: "detected"}
    resolved = resolve(base, lambda i, o: verdicts[i])
    assert [(o.outcome, o.error_id) for o in resolved] == [
        ("hit", "H-001-E1"),
        ("near_miss", "H-001-E2"),
        ("false_alarm", None),
        ("miss", "H-001-E2"),
        ("duplicate", "H-001-E1"),  # a second detected verdict on E1 in the same unit
    ]
    assert resolve(base, lambda i, o: None) == base  # undecided findings stay in review


# EVAL-09 C (owner decision, 2026-11-11): in a report with an omission error, an unmapped
# finding that is not already a hit or a review item becomes a review item for each omission.

OMISSION_E2 = _error(2, "H5", "Diagnosis", "Invasive tumour, grade 2.", kind="omission")
OMISSION_E3 = _error(3, "H5", "Synoptic summary", "pT1c pN0.", kind="omission")
STATEMENT_E1 = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm.")


def test_an_unmapped_finding_beside_an_omission_is_reviewed_for_it():
    errors = [STATEMENT_E1, OMISSION_E2]
    outcome = classify("Gross description", "Fatty tissue.", "unmapped", errors)
    assert outcome == Outcome("review", "H-001-E2", "unmapped_omission", None, ("H-001-E2",))


def test_an_unmapped_finding_beside_two_omissions_is_reviewed_for_each():
    errors = [STATEMENT_E1, OMISSION_E2, OMISSION_E3]
    outcome = classify("Gross description", "Fatty tissue.", "unmapped", errors)
    assert (outcome.outcome, outcome.reason) == ("review", "unmapped_omission")
    assert outcome.error_ids == ("H-001-E2", "H-001-E3")


def test_an_unmapped_finding_already_in_review_for_another_error_keeps_that_item():
    errors = [STATEMENT_E1, OMISSION_E2]
    outcome = classify("Microscopic description", "Tumour measures 25 mm.", "unmapped", errors)
    assert (outcome.outcome, outcome.error_id, outcome.reason) == (
        "review", "H-001-E1", "unmapped_category"
    )  # fmt: skip


@pytest.mark.parametrize("mapped", ["H2", "other"])
def test_a_mapped_finding_beside_an_omission_stays_a_false_alarm(mapped):
    errors = [STATEMENT_E1, OMISSION_E2]
    assert classify("Gross description", "Fatty tissue.", mapped, errors) == Outcome("false_alarm")


def test_an_unmapped_finding_without_an_omission_stays_a_false_alarm():
    assert classify("Gross description", "Fatty tissue.", "unmapped", [STATEMENT_E1]) == Outcome(
        "false_alarm"
    )


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ({"H-001-E2": "detected", "H-001-E3": "false_alarm"}, ("hit", ("H-001-E2",))),
        ({"H-001-E2": "detected", "H-001-E3": "detected"}, ("hit", ("H-001-E2", "H-001-E3"))),
        ({"H-001-E2": "false_alarm", "H-001-E3": "false_alarm"}, ("false_alarm", ())),
        ({"H-001-E2": "miss", "H-001-E3": "near_miss"}, ("near_miss", ("H-001-E3",))),
        ({"H-001-E2": "miss", "H-001-E3": "false_alarm"}, ("miss", ("H-001-E2",))),
    ],
)
def test_one_verdict_per_omission_resolves_the_finding(verdicts, expected):
    review = Outcome("review", "H-001-E2", "unmapped_omission", None, ("H-001-E2", "H-001-E3"))
    (resolved,) = resolve([review], lambda i, o: verdicts[o.error_id])
    assert (resolved.outcome, resolved.ids) == expected


def test_a_finding_hitting_two_omissions_is_a_duplicate_only_where_both_were_hit():
    review = Outcome("review", "H-001-E2", "unmapped_omission", None, ("H-001-E2", "H-001-E3"))
    base = [Outcome("hit", "H-001-E2", None, 1.0), review, review]
    resolved = resolve(base, lambda i, o: "detected")
    assert [(o.outcome, o.ids) for o in resolved] == [
        ("hit", ("H-001-E2",)),
        ("hit", ("H-001-E3",)),  # E2 was already hit: only E3 is new
        ("duplicate", ("H-001-E2", "H-001-E3")),
    ]
