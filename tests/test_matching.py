"""Text handling, category mapping and the classification rules (EVAL-05 6.2 to 6.4)."""

import pytest

from pathqc_eval.matching import (
    Outcome,
    classify,
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


# 6.3 Categories (EVAL-12: no category map; categories are normalised only to be listed and
# for type agreement)


def test_normalise_category_drops_trailing_punctuation():
    """6.3: casefold, strip, collapse whitespace, drop trailing punctuation: every Unicode
    punctuation character at the end goes, closing brackets and quotes included; a symbol
    such as + is not punctuation."""
    assert normalise_category("  Size   Mismatch?!  ") == "size mismatch"
    assert normalise_category("C2 (indices).") == "c2 (indices"
    assert normalise_category("“Size mismatch”") == "“size mismatch"
    assert normalise_category("H1) -") == "h1"
    assert normalise_category("H1 +") == "h1 +"


# 6.4 Classification by place (decision 61, EVAL-12): no category is read


STATEMENT = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm.")
OMISSION = _error(2, "H5", "Synoptic summary", "LVI absent; PNI absent.", kind="omission")


@pytest.mark.parametrize(
    ("section", "quote", "expected"),
    [
        ("Microscopic description", "Tumour measures 25 mm.", ("hit", None)),
        ("Microscopic description", "Tumour size given as 25 cm",
         ("review", "borderline_overlap")),
        ("Diagnosis", "Tumour measures 25 mm.", ("review", "section_mismatch")),
        ("Microscopic description", "Grade is two.", ("false_alarm", None)),
        ("Diagnosis", "Grade is two.", ("false_alarm", None)),
    ],
)  # fmt: skip
def test_statement_rules(section, quote, expected):
    result = classify(section, quote, [STATEMENT])
    assert (result.outcome, result.reason) == expected
    if expected[0] != "false_alarm":
        assert result.error_id == "H-001-E1"


BOUNDARY = _error(1, "H1", "Microscopic description", "alpha beta gamma delta epsilon")


@pytest.mark.parametrize(
    ("section", "quote", "expected"),
    [
        # 3 of 5 tokens shared: ov 0.6 exactly, the threshold
        ("Microscopic description", "alpha beta gamma zeta eta", ("hit", None)),
        ("Diagnosis", "alpha beta gamma zeta eta", ("review", "section_mismatch")),
        # 2 of 5: ov 0.4 exactly, the low end of the borderline band
        ("Microscopic description", "alpha beta zeta eta theta",
         ("review", "borderline_overlap")),
        ("Diagnosis", "alpha beta zeta eta theta", ("false_alarm", None)),
        # 1 of 5: ov 0.2, below the band
        ("Microscopic description", "alpha zeta eta theta iota", ("false_alarm", None)),
        ("Microscopic description", "zeta eta theta iota kappa", ("false_alarm", None)),
    ],
)  # fmt: skip
def test_statement_rules_at_the_boundaries(section, quote, expected):
    result = classify(section, quote, [BOUNDARY])
    assert (result.outcome, result.reason) == expected


def test_a_point_between_a_letter_and_a_digit_splits_tokens():
    assert tokens("Fig.5") == {"fig", "5"}
    assert tokens("5.a") == {"5", "a"}
    assert tokens("6.2.1") == {"6.2.1"}


@pytest.mark.parametrize(
    ("section", "quote"),
    [
        ("Synoptic summary", "LVI absent; PNI absent."),  # the anchor itself: no automatic hit
        ("Synoptic summary", "Anything at all"),
        ("Microscopic description", "LVI absent; PNI absent."),
        ("Diagnosis", "Something unrelated"),
    ],
)
def test_every_finding_in_a_report_with_an_omission_is_a_candidate_for_it(section, quote):
    """Decision 62 (EVAL-12): an omission is never an automatic hit; every finding that is not
    a hit for another error is a candidate for it."""
    result = classify(section, quote, [OMISSION])
    assert (result.outcome, result.reason, result.error_ids) == (
        "review", "omission_candidate", ("H-001-E2",)
    )  # fmt: skip


def test_a_hit_comes_before_any_review():
    review = _error(1, "H1", "Diagnosis", "Tumour measures 25 mm.")
    hit = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm. Margins clear.")
    found = classify("Microscopic description", "Tumour measures 25 mm.", [review, hit])
    assert (found.outcome, found.error_id) == ("hit", "H-001-E2")
    found = classify("Microscopic description", "Tumour measures 25 mm.", [review])
    assert (found.outcome, found.reason, found.error_id) == (
        "review", "section_mismatch", "H-001-E1",
    )  # fmt: skip


def test_among_hits_the_highest_overlap_then_the_lowest_error_id_wins():
    partial = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm in total size.")
    exact = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm.")
    found = classify("Microscopic description", "Tumour measures 25 mm.", [partial, exact])
    # E1: 4 shared of the finding's 4 -> 1.0 as well; E2: 1.0: a tie, so the lowest id, E1
    assert found.error_id == "H-001-E1"
    other = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm and more mm.")
    tenth = _error(10, "H1", "Microscopic description", "Tumour measures 25 mm.")
    found = classify("Microscopic description", "Tumour measures 25 mm.", [tenth, other])
    assert found.error_id == "H-001-E2"  # E2 before E10: numbers, not text, are compared


def test_highest_overlap_wins_over_a_lower_error_id():
    weaker = _error(1, "H1", "Microscopic description", "Grade two tumour, 25 mm, said the report.")
    stronger = _error(2, "H1", "Microscopic description", "Tumour measures 25 mm.")
    quote = "Tumour measures 25 mm."
    assert overlap(quote, weaker.quoted_sentence) < overlap(quote, stronger.quoted_sentence)
    assert classify("Microscopic description", quote, [weaker, stronger]).error_id == "H-001-E2"


def test_every_finding_in_a_clean_report_is_a_false_alarm():
    assert classify("Interpretation", "All values within range.", []) == Outcome("false_alarm")


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
        Outcome("review", "H-001-E1", "omission_candidate", 1.0),
        Outcome("review", "H-001-E2", "section_mismatch", 1.0),
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


# Omission candidates (decision 62; replaces EVAL-09 C, decision 50's combination kept)

OMISSION_E2 = _error(2, "H5", "Diagnosis", "Invasive tumour, grade 2.", kind="omission")
OMISSION_E3 = _error(3, "H5", "Synoptic summary", "pT1c pN0.", kind="omission")
STATEMENT_E1 = _error(1, "H1", "Microscopic description", "Tumour measures 25 mm.")


def test_a_finding_beside_an_omission_is_a_candidate_for_it_whatever_its_label():
    outcome = classify("Gross description", "Fatty tissue.", [STATEMENT_E1, OMISSION_E2])
    assert outcome == Outcome(
        "review", "H-001-E2", "omission_candidate", 0.0, ("H-001-E2",), ("omission_candidate",)
    )


def test_a_finding_beside_two_omissions_is_a_candidate_for_each():
    errors = [STATEMENT_E1, OMISSION_E2, OMISSION_E3]
    outcome = classify("Gross description", "Fatty tissue.", errors)
    assert (outcome.outcome, outcome.reason) == ("review", "omission_candidate")
    assert outcome.error_ids == ("H-001-E2", "H-001-E3")


def test_a_finding_in_review_for_a_statement_error_is_also_an_omission_candidate():
    errors = [STATEMENT_E1, OMISSION_E2]
    outcome = classify("Diagnosis", "Tumour measures 25 mm.", errors)
    assert (outcome.error_ids, outcome.reasons) == (
        ("H-001-E1", "H-001-E2"), ("section_mismatch", "omission_candidate")
    )  # fmt: skip


def test_a_hit_beside_an_omission_is_no_candidate():
    outcome = classify(
        "Microscopic description", "Tumour measures 25 mm.", [STATEMENT_E1, OMISSION_E2]
    )
    assert (outcome.outcome, outcome.error_id, outcome.error_ids) == ("hit", "H-001-E1", ())


def test_a_finding_without_an_omission_or_a_place_is_a_false_alarm():
    assert classify("Gross description", "Fatty tissue.", [STATEMENT_E1]) == Outcome("false_alarm")


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
    review = Outcome(
        "review", "H-001-E2", "omission_candidate", None, ("H-001-E2", "H-001-E3"),
        ("omission_candidate", "omission_candidate"),
    )  # fmt: skip
    (resolved,) = resolve([review], lambda i, o: verdicts[o.error_id])
    assert (resolved.outcome, resolved.ids) == expected


def test_a_finding_hitting_two_omissions_is_a_duplicate_only_where_both_were_hit():
    review = Outcome(
        "review", "H-001-E2", "omission_candidate", None, ("H-001-E2", "H-001-E3"),
        ("omission_candidate", "omission_candidate"),
    )  # fmt: skip
    base = [Outcome("hit", "H-001-E2", None, 1.0), review, review]
    resolved = resolve(base, lambda i, o: "detected")
    assert [(o.outcome, o.ids) for o in resolved] == [
        ("hit", ("H-001-E2",)),
        ("hit", ("H-001-E3",)),  # E2 was already hit: only E3 is new
        ("duplicate", ("H-001-E2", "H-001-E3")),
    ]


# Other places (decision 56, EVAL-10), by place only since EVAL-12

SYN_PT = "pT: pT3"
DIAG_PT = "Invasive tumour, pT3, grade 2."
GROSS = "Fatty tissue 40 x 30 x 20 mm with a firm lesion."


def _with_places(err: PlantedError, *places: tuple[str, str]) -> PlantedError:
    data = err.model_dump() | {
        "other_places": [{"section": s, "quoted_sentence": q} for s, q in places]
    }
    return PlantedError.model_validate(data)


def _stage() -> PlantedError:
    return _with_places(_error(1, "H3", "Synoptic summary", SYN_PT), ("Diagnosis", DIAG_PT))


@pytest.mark.parametrize(
    ("section", "quote", "expected"),
    [
        ("Diagnosis", DIAG_PT, ("hit", None, 1.0)),
        ("Diagnosis", "Invasive tumour with deep margin unusual today here.",
         ("review", "borderline_overlap", 0.4)),
        ("Microscopic description", DIAG_PT, ("review", "section_mismatch", 1.0)),
        ("Synoptic summary", SYN_PT, ("hit", None, 1.0)),  # the main place still counts
    ],
)  # fmt: skip
def test_a_finding_quoting_an_other_place_follows_the_same_rules(section, quote, expected):
    result = classify(section, quote, [_stage()])
    assert (result.outcome, result.reason, round(result.overlap, 3)) == expected
    assert result.error_id == "H-001-E1"


def test_the_best_matching_place_wins_over_a_closer_sentence_elsewhere():
    """Main place: the same section, the finding contained in it (a hit); the other place:
    the exact sentence in another section (a section mismatch). The hit wins."""
    err = _with_places(
        _error(1, "H3", "Diagnosis", "Invasive tumour, pT3, grade 2 of 3 here."),
        ("Synoptic summary", "Invasive tumour, pT3, grade 2."),
    )
    result = classify("Diagnosis", "Invasive tumour, pT3, grade 2.", [err])
    assert (result.outcome, result.reason) == ("hit", None)


def test_without_other_places_the_other_sentence_is_a_false_alarm():
    plain = _error(1, "H3", "Synoptic summary", SYN_PT)
    assert classify("Diagnosis", DIAG_PT, [plain]) == Outcome("false_alarm")


def test_an_omission_with_other_places_is_still_only_a_candidate():
    omission = _with_places(
        _error(2, "H5", "Synoptic summary", "LVI absent", kind="omission"),
        ("Microscopic description", "Margins are clear."),
    )
    result = classify("Microscopic description", "Margins are clear.", [omission])
    assert (result.outcome, result.reason, result.error_id, result.overlap) == (
        "review", "omission_candidate", "H-001-E2", 1.0
    )  # fmt: skip


def test_a_finding_on_two_errors_places_gets_one_outcome_by_the_existing_precedence():
    """E1 names the Diagnosis sentence as an other place; E3 has it as its main sentence.
    Both overlap 1.0, so the lowest error id, E1, has the one hit."""
    e1 = _with_places(_error(1, "H1", "Gross description", GROSS), ("Diagnosis", DIAG_PT))
    e3 = _error(3, "H3", "Diagnosis", DIAG_PT)
    result = classify("Diagnosis", DIAG_PT, [e1, e3])
    assert (result.outcome, result.error_id, result.error_ids) == ("hit", "H-001-E1", ())
