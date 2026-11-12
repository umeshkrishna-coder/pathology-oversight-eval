"""Isolation of the evaluated model (EVAL-03 step 5): every rule passes on clean messages and
each rule has a failing case. Uses the agent-written plain and output prompts with stand-in
owner texts; never the owner's own texts."""

import pytest

from pathqc_eval.prompting import (
    build_eval_messages,
    check_eval_isolation,
    render_report_text,
    taxonomy_block,
)
from pathqc_eval.schema import Report


@pytest.fixture
def report(histo):
    histo["errors"][0] |= {"severity": "critical", "severity_reason": "Size drives pT here."}
    return Report.model_validate(histo)


def _messages(report, condition, taxonomy, prompts):
    return build_eval_messages(report, condition, taxonomy, prompts)


@pytest.mark.parametrize("name", ["histo", "cbc"])
@pytest.mark.parametrize("condition", ["plain", "structured"])
def test_isolated_messages_pass(request, name, condition, fixed_taxonomy, real_prompts):
    report = Report.model_validate(request.getfixturevalue(name))
    system, user = _messages(report, condition, fixed_taxonomy, real_prompts)
    assert check_eval_isolation(report, condition, system, user, fixed_taxonomy) == []


@pytest.mark.parametrize("condition", ["plain", "structured"])
@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        ("Case H-001.", "system message contains the report id H-001"),
        ("Split: dev.", "system message contains the split 'dev'"),
        ("is_clean_control", "system message contains 'is_clean_control'"),
        ("provenance", "system message contains 'provenance'"),
        ("error_id", "system message contains 'error_id'"),
        (
            "Microscopic size contradicts the 18 mm gross size.",
            "system message contains the description of H-001-E1",
        ),
        (
            "Gross, microscopy and synoptic must agree on size.",
            "system message contains the rationale of H-001-E1",
        ),
        ("Size drives pT here.", "system message contains the severity_reason of H-001-E1"),
    ],
)
def test_system_leaks_fail(report, condition, addition, expected, fixed_taxonomy, real_prompts):
    system, user = _messages(report, condition, fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(
        report, condition, f"{system}\n{addition}", user, fixed_taxonomy
    )
    assert problems == [expected]


@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        ("Case H-001.", "user message contains the report id H-001"),
        ("Split: dev.", "user message contains the split 'dev'"),
        ("error_id", "user message contains 'error_id'"),
        (
            "Microscopic size contradicts the 18 mm gross size.",
            "user message contains the description of H-001-E1",
        ),
    ],
)
def test_user_leaks_fail(report, addition, expected, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(report, "plain", system, f"{user}\n{addition}", fixed_taxonomy)
    assert expected in problems
    assert "user message is not the report text (it must be the same in both)" in problems


def test_split_matches_whole_words_only(report, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    system += "\nA developed and well-structured review."
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == []


@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        ("Look for H3 errors.", "plain system message contains the type id H3"),
        ("Check C2.", "plain system message contains the type id C2"),
        (
            "Look for any staging inconsistency.",
            "plain system message contains the type name 'Staging inconsistency'",
        ),
        (
            "Critical means it would change patient management.",
            "plain system message contains the critical severity definition",
        ),
        (
            "Minor: internal inconsistency without clinical consequence.",
            "plain system message contains the minor severity definition",
        ),
    ],
)
def test_plain_system_taxonomy_leaks_fail(report, addition, expected, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(report, "plain", f"{system}\n{addition}", user, fixed_taxonomy)
    assert problems == [expected]


def test_plain_type_id_is_whole_word(report, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    system += "\nIgnore codes such as XH1 or H10."
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == []


def test_structured_without_own_taxonomy_fails(report, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "structured", fixed_taxonomy, real_prompts)
    system = system.replace(taxonomy_block(fixed_taxonomy, "histopathology"), "")
    assert check_eval_isolation(report, "structured", system, user, fixed_taxonomy) == [
        "structured system message lacks the histopathology taxonomy"
    ]


@pytest.mark.parametrize("addition", ["C2", "Derived-index inconsistency"])
def test_structured_with_other_modality_fails(report, addition, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "structured", fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(
        report, "structured", f"{system}\n{addition}", user, fixed_taxonomy
    )
    assert problems == ["structured system message contains cbc type C2 in a histopathology report"]


def test_structured_cbc_with_histopathology_type_fails(cbc, fixed_taxonomy, real_prompts):
    report = Report.model_validate(cbc)
    system, user = _messages(report, "structured", fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(report, "structured", f"{system}\nH4", user, fixed_taxonomy)
    assert problems == ["structured system message contains histopathology type H4 in a cbc report"]


@pytest.mark.parametrize("condition", ["plain", "structured"])
def test_user_message_must_be_the_report_text(report, condition, fixed_taxonomy, real_prompts):
    system, user = _messages(report, condition, fixed_taxonomy, real_prompts)
    altered = user.replace("## Diagnosis", "## Final diagnosis")
    assert check_eval_isolation(report, condition, system, altered, fixed_taxonomy) == [
        "user message is not the report text (it must be the same in both)"
    ]


# EVAL-04 (owner decision): only label forms of the split are refused, not the bare words.


@pytest.mark.parametrize("condition", ["plain", "structured"])
@pytest.mark.parametrize(
    ("split", "words"),
    [("scored", "HER2 scored 2+ in the invasive tumour."), ("dev", "The dev slide was reviewed.")],
)
def test_the_split_as_an_ordinary_word_passes_in_both_messages(
    histo, fixed_taxonomy, real_prompts, condition, split, words
):
    histo["split"] = split
    histo["sections"]["Comment"] = words
    report = Report.model_validate(histo)
    system, user = _messages(report, condition, fixed_taxonomy, real_prompts)
    assert words in user
    system += f"\n{words}"
    assert check_eval_isolation(report, condition, system, user, fixed_taxonomy) == []


@pytest.mark.parametrize(
    ("label", "problem"),
    [
        ("split: scored", "contains the split 'scored'"),
        ("Split : dev", "contains the split 'dev'"),
        ("SPLIT:dev", "contains the split 'dev'"),
        ("split: 'scored'", "contains the split 'scored'"),
        ('"split"', 'contains the quoted key "split"'),
    ],
)
@pytest.mark.parametrize("where", ["system", "user"])
def test_split_label_forms_fail(histo, fixed_taxonomy, real_prompts, label, problem, where):
    if where == "user":
        histo["sections"]["Comment"] = f"Invented note, {label}."
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    if where == "system":
        system += f"\n{label}"
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == [
        f"{where} message {problem}"
    ]


@pytest.mark.parametrize(
    ("label", "problems"),
    [
        ("{'split': 'scored'}", ["contains the split 'scored'", 'contains the quoted key "split"']),
        ('"Split": "dev"', ["contains the split 'dev'", 'contains the quoted key "split"']),
        ("data_split: dev", ["contains the split 'dev'"]),
        ("**Split:** scored", ["contains the split 'scored'"]),
        ("**Split**: dev", ["contains the split 'dev'"]),
        ("split: “dev”", ["contains the split 'dev'"]),
        ("‘split’: dev", ["contains the split 'dev'", 'contains the quoted key "split"']),
        ("“Split” : x", ['contains the quoted key "split"']),
    ],
)
@pytest.mark.parametrize("where", ["system", "user"])
def test_decorated_split_labels_fail(histo, fixed_taxonomy, real_prompts, label, problems, where):
    """S5 review rounds 1 and 2: quotes and markdown around a split label, or a prefix joined
    to it by an underscore, are still label forms; 'split' in any quotes before a colon is a
    key."""
    if where == "user":
        histo["sections"]["Comment"] = f"Invented note, {label}."
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    if where == "system":
        system += f"\n{label}"
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == [
        f"{where} message {p}" for p in problems
    ]


@pytest.mark.parametrize(
    "prose",
    [
        "The core was received ‘split’ and both halves were embedded.",
        "The specimen was 'split' longitudinally.",
        "A “split” biopsy was sent.",
    ],
)
@pytest.mark.parametrize("where", ["system", "user"])
def test_split_in_quotes_in_prose_passes(histo, fixed_taxonomy, real_prompts, prose, where):
    """Decision 42: the bare words pass. Only the double-quoted key "split", or 'split' in
    any quotes before a colon, is a key form."""
    if where == "user":
        histo["sections"]["Comment"] = prose
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    if where == "system":
        system += f"\n{prose}"
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == []


@pytest.mark.parametrize("words", ["Split: developed nodes.", "split: scoreds", "The split dev"])
def test_words_after_a_split_label_must_be_the_split_itself(
    histo, fixed_taxonomy, real_prompts, words
):
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    assert check_eval_isolation(report, "plain", system + f"\n{words}", user, fixed_taxonomy) == []


@pytest.mark.parametrize("label", ["Split: _dev_", "**SPLIT** : _scored_", "split: __dev__"])
@pytest.mark.parametrize("where", ["system", "user"])
def test_split_labels_with_underscore_emphasis_fail(
    histo, fixed_taxonomy, real_prompts, label, where
):
    """Review round 3: '_' is a word character, so underscore emphasis after the value must
    not hide a label."""
    if where == "user":
        histo["sections"]["Comment"] = f"Invented note, {label}."
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    if where == "system":
        system += f"\n{label}"
    problems = check_eval_isolation(report, "plain", system, user, fixed_taxonomy)
    assert len(problems) == 1 and problems[0].startswith(f"{where} message contains the split")


# EVAL-09 H4 and H5 (owner decisions, 2026-11-11)


@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        (
            "Look for size, number, laterality or site in the gross contradicted in microscopy "
            "or synoptic.",
            "plain system message contains the type definition of H1",
        ),
        (
            "Flag any Interpretation Text Contradicts The Numbers",
            "plain system message contains the type definition of C1",
        ),
    ],
)
def test_plain_system_with_a_type_definition_fails(
    report, addition, expected, fixed_taxonomy, real_prompts
):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    problems = check_eval_isolation(report, "plain", f"{system}\n{addition}", user, fixed_taxonomy)
    assert problems == [expected]


def test_plain_system_with_a_severity_definition_still_fails(report, fixed_taxonomy, real_prompts):
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    system += "\nMajor: would need an amended report."
    problems = check_eval_isolation(report, "plain", system, user, fixed_taxonomy)
    assert problems == ["plain system message contains the major severity definition"]


@pytest.mark.parametrize(
    ("label", "problem"),
    [
        ("split = dev", "contains the split 'dev'"),
        ("split = scored", "contains the split 'scored'"),
        ("SPLIT=scored", "contains the split 'scored'"),
        ("**Split** = _dev_", "contains the split 'dev'"),
    ],
)
@pytest.mark.parametrize("where", ["system", "user"])
def test_split_equals_forms_fail(histo, fixed_taxonomy, real_prompts, label, problem, where):
    if where == "user":
        histo["sections"]["Comment"] = f"Invented note, {label}."
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    if where == "system":
        system += f"\n{label}"
    assert check_eval_isolation(report, "plain", system, user, fixed_taxonomy) == [
        f"{where} message {problem}"
    ]


@pytest.mark.parametrize("words", ["The split = developed", "split = scoreds", "split equals dev"])
def test_words_after_split_equals_must_be_the_split_itself(
    histo, fixed_taxonomy, real_prompts, words
):
    report = Report.model_validate(histo)
    system, user = _messages(report, "plain", fixed_taxonomy, real_prompts)
    assert check_eval_isolation(report, "plain", f"{system}\n{words}", user, fixed_taxonomy) == []


# EVAL-10 K: the model sees the report text only; an error's other places reach neither message
# except as part of that text.


@pytest.mark.parametrize("condition", ["plain", "structured"])
def test_other_places_reach_no_message_except_as_report_text(
    histo, fixed_taxonomy, real_prompts, condition
):
    gross = "a firm lesion 18 mm across"
    histo["errors"][0]["other_places"] = [
        {"section": "Gross description", "quoted_sentence": gross}
    ]
    report = Report.model_validate(histo)
    system, user = _messages(report, condition, fixed_taxonomy, real_prompts)
    assert check_eval_isolation(report, condition, system, user, fixed_taxonomy) == []
    for text in (system, user):
        for word in ("other_places", "other place", "also_section", "also_quote"):
            assert word not in text
    assert gross not in system
    assert user == render_report_text(report)  # the other place is there only as report text
    assert user.count(gross) == histo["sections"]["Gross description"].count(gross) == 1
