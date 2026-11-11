"""Lenient reading of the evaluated model's output (EVAL-04 step 3)."""

import json
import time

import pytest

from pathqc_eval.findings import ParsedFinding, parse_findings


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


PARSED = ParsedFinding(
    quoted_sentence="Tumour measures 25 mm.",
    section="Microscopic description",
    category="size mismatch",
    severity="major",
    confidence=0.8,
    rationale="Differs from the gross size.",
)


def test_valid_object():
    result = parse_findings(json.dumps({"findings": [_finding()]}))
    assert result.status == "valid"
    assert result.findings == [PARSED]
    assert result.dropped == [] and result.notes == []


def test_bare_list():
    result = parse_findings(json.dumps([_finding()]))
    assert (result.status, result.findings) == ("valid", [PARSED])


@pytest.mark.parametrize("fence", ["```json\n{}\n```", "```\n{}\n```", "  ```JSON\n{}\n```  \n"])
def test_code_fence_is_accepted(fence):
    body = json.dumps({"findings": [_finding()]})
    result = parse_findings(fence.replace("{}", body))
    assert (result.status, result.findings) == ("valid", [PARSED])


@pytest.mark.parametrize("text", ['{"findings": []}', "[]", "```json\n[]\n```"])
def test_empty_list_is_valid(text):
    result = parse_findings(text)
    assert (result.status, result.findings, result.dropped) == ("valid", [], [])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        '{"findings": [',
        'Here are the findings: {"findings": []}',
        '{"findings": []} trailing words',
    ],
)
def test_broken_json_is_invalid(text):
    result = parse_findings(text)
    assert result.status == "invalid"
    assert result.findings == []
    assert result.notes[0].startswith("output is not JSON")


@pytest.mark.parametrize(
    "value",
    [{}, {"findings": None}, {"findings": {}}, {"results": []}, "a string", 42, None, True],
)
def test_wrong_shape_is_invalid(value):
    result = parse_findings(json.dumps(value))
    assert result.status == "invalid"
    assert result.findings == []


def test_extra_keys_are_ignored_and_noted():
    payload = {"findings": [_finding(location="line 3", id=7)], "summary": "one error"}
    result = parse_findings(json.dumps(payload))
    assert result.status == "valid"
    assert result.findings == [PARSED]
    assert result.notes == [
        "top level: extra keys ignored: summary",
        "finding 1: extra keys ignored: id, location",
    ]


@pytest.mark.parametrize(
    ("severity", "expected"),
    [("Major", "major"), (" CRITICAL ", "critical"), ("moderate", None), (3, None), (None, None)],
)
def test_severity_is_lowercased_or_null(severity, expected):
    result = parse_findings(json.dumps([_finding(severity=severity)]))
    assert result.findings[0].severity == expected
    assert (expected is None) == any("severity" in note for note in result.notes)


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.8, 0.8),
        (0, 0.0),
        (1, 1.0),
        (85, None),
        ("high", None),
        ("0.8", None),
        (-0.1, None),
        (1.01, None),
        (True, None),
        (None, None),
    ],
)
def test_confidence_is_a_number_from_0_to_1_or_null(confidence, expected):
    result = parse_findings(json.dumps([_finding(confidence=confidence)]))
    assert result.status == "valid"
    assert result.findings[0].confidence == expected
    assert (expected is None) == any("confidence" in note for note in result.notes)


def test_missing_severity_and_confidence_become_null():
    finding = {k: v for k, v in _finding().items() if k not in ("severity", "confidence")}
    result = parse_findings(json.dumps([finding]))
    assert (result.findings[0].severity, result.findings[0].confidence) == (None, None)
    assert result.notes == [
        "finding 1: severity missing is not critical, major or minor; null",
        "finding 1: confidence missing is not a number from 0 to 1; null",
    ]


def test_non_finite_confidence_is_null():
    result = parse_findings(
        '[{"quoted_sentence": "q", "section": "s", "category": "c", '
        '"severity": "minor", "confidence": NaN, "rationale": "r"}]'
    )
    assert result.findings[0].confidence is None


def test_rationale_is_text_or_empty():
    result = parse_findings(json.dumps([_finding(rationale=None), _finding(rationale=["x"])]))
    assert [f.rationale for f in result.findings] == ["", ""]
    missing = {k: v for k, v in _finding().items() if k != "rationale"}
    assert parse_findings(json.dumps([missing])).findings[0].rationale == ""


def test_findings_without_required_strings_are_dropped_and_counted():
    findings = [
        _finding(),
        _finding(quoted_sentence="   "),
        {k: v for k, v in _finding().items() if k != "section"},
        _finding(category=12),
        "a string finding",
        _finding(quoted_sentence=None, section=""),
    ]
    result = parse_findings(json.dumps({"findings": findings}))
    assert result.status == "valid"
    assert result.findings == [PARSED]
    assert [(d.index, d.reason) for d in result.dropped] == [
        (2, "no usable quoted_sentence"),
        (3, "no usable section"),
        (4, "no usable category"),
        (5, "not an object (str)"),
        (6, "no usable quoted_sentence, section"),
    ]


def test_strings_are_stripped():
    result = parse_findings(
        json.dumps(
            [_finding(quoted_sentence="  Tumour measures 25 mm. ", category=" size mismatch\n")]
        )
    )
    assert result.findings == [PARSED]


def test_unpaired_surrogates_are_replaced_and_noted():
    """An escaped unpaired surrogate parses to a str that cannot be written as UTF-8 (the run
    would fail while logging the call); it is replaced with U+FFFD and noted."""
    item = _finding(category="size \ud800 mismatch", rationale="Gross \udfff size.")
    item["\udc00extra"] = 1
    text = json.dumps({"findings": [item], "\ud800top": 2})  # ensure_ascii: \u escapes
    result = parse_findings(text)
    assert result.status == "valid"
    (finding,) = result.findings
    assert finding.category == "size \ufffd mismatch"
    assert finding.rationale == "Gross \ufffd size."
    json.dumps(result.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")
    assert "finding 1: category held unpaired surrogates; replaced with U+FFFD" in result.notes
    assert "finding 1: rationale held unpaired surrogates; replaced with U+FFFD" in result.notes
    assert "finding 1: extra keys ignored: \ufffdextra" in result.notes
    assert "top level: extra keys ignored: \ufffdtop" in result.notes


# Review round 1 (S5)


@pytest.mark.parametrize("fence", ["~~~json\n{}\n~~~", "~~~\n{}\n~~~", "````json\n{}\n````"])
def test_tilde_and_longer_code_fences_are_accepted(fence):
    body = json.dumps({"findings": [_finding()]})
    result = parse_findings(fence.replace("{}", body))
    assert (result.status, result.findings) == ("valid", [PARSED])


def test_extra_keys_of_a_dropped_finding_are_noted():
    item = _finding(sentence="Tumour measures 25 mm.")
    del item["quoted_sentence"]
    result = parse_findings(json.dumps([item]))
    assert [(d.index, d.reason) for d in result.dropped] == [(1, "no usable quoted_sentence")]
    assert result.notes == ["finding 1: extra keys ignored: sentence"]


# Review round 2 (S5)


@pytest.mark.parametrize(
    "wrapped",
    ["```json\n{}\n````", "``` json\n{}\n```", "```json5\n{}\n```", "~~~ JSON\n{}\n~~~~~"],
)
def test_more_code_fence_forms_are_accepted(wrapped):
    body = json.dumps({"findings": [_finding()]})
    result = parse_findings(wrapped.replace("{}", body))
    assert (result.status, result.findings) == ("valid", [PARSED])


@pytest.mark.parametrize("char", ["`", "~"])
def test_a_long_run_of_fence_characters_is_read_quickly(char):
    """An output that degenerates into one run of fence characters is invalid, and reading it
    takes no longer than reading any other output (it runs on the run's only writer thread)."""
    started = time.perf_counter()
    assert parse_findings(char * 8000).status == "invalid"
    assert time.perf_counter() - started < 2.0


# Review round 3 (S5)


@pytest.mark.parametrize("wrapped", ["```json {}\n```", "```{}\n```", "``` json {}\n```"])
def test_json_that_starts_on_the_opening_fence_line_is_read(wrapped):
    body = json.dumps({"findings": [_finding()]})
    result = parse_findings(wrapped.replace("{}", body))
    assert (result.status, result.findings) == ("valid", [PARSED])
