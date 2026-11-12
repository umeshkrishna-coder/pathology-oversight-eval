"""Planting sheet tool (EVAL-02c): parser, apply rules, determinism and commands.

Temporary folders and invented reports and sheets only; never reads data/drafts/,
data/reports/ or data/specs/planting.md.
"""

import ast
import copy
import json
from pathlib import Path
from textwrap import dedent

import pytest
from conftest import FIXTURES, fixture_text, rerender

from pathqc_eval import cli, plant
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.plant import (
    SHEET_FILE,
    apply_block,
    parse_sheet,
    plan,
    remove_span,
)
from pathqc_eval.readable import readable_markdown
from pathqc_eval.spec import DATASET_SHAPE, SpecRow

SYNOPTIC = "\n".join(
    [
        "Tumour size: 18 mm",
        "Histologic grade: 2",
        "Margins: Clear",
        "Lymphovascular invasion: Absent",
        "Perineural invasion: Absent",
        "Lymph nodes (positive/total): 0/3",
        "pT: pT1c",
        "pN: pN0",
        "Staging edition: AJCC 8th edition",
    ]
)
ERROR_TEXT = "description: Invented description.\nrationale: Invented rationale.\n"
FIVE_WORD_MESSAGE = (
    "[error] 1 (line 3): the replace text has fewer than 5 words, so it cannot serve as the "
    "quoted sentence; add a quote: line with the full sentence as it reads after the change"
)


@pytest.fixture
def histo_draft(histo):
    """An invented histopathology draft (errors [] as drafted) with both optional sections."""
    draft = copy.deepcopy(histo)
    draft["sections"] = {
        "Clinical details": "Invented test case. Lump noted on examination.",
        "Specimen": "Wide local excision, left side.",
        "Gross description": "Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm across.",
        "Microscopic description": (
            "Sections show an invasive tumour of no special type. Tumour measures 18 mm. "
            "Margins are clear."
        ),
        "Immunohistochemistry": "ER: positive in tumour cells.\nPR: positive in tumour cells.",
        "Diagnosis": "Invasive tumour of no special type, grade 2, 18 mm.",
        "Synoptic summary": SYNOPTIC,
        "Comment": "Invented comment for a planting test.",
    }
    draft["errors"] = []
    draft["split"] = "scored"
    return draft


@pytest.fixture
def cbc_draft(cbc):
    """An invented CBC draft: Hb 10.0, Hct 33.0, RBC 3.70 with consistent derived indices."""
    draft = copy.deepcopy(cbc)
    values = draft["cbc_values"]
    for name, value in (
        ("Hb", 10.0),
        ("Hct", 33.0),
        ("RBC", 3.70),
        ("MCV", 89.2),
        ("MCH", 27.0),
        ("MCHC", 30.3),
    ):
        values[name]["value"] = value
    draft["sections"]["Interpretation"] = (
        "Mild anaemia with normal red cell indices. Platelets are within the reference range."
    )
    draft["is_clean_control"] = False
    return rerender(draft)


def _row(rid, clean=False, planned=None, split="scored"):
    histo = rid.startswith("H")
    data = {
        "id": rid,
        "modality": "histopathology" if histo else "cbc",
        "split": split,
        "sex": "male",
        "age": 50,
        "is_clean_control": clean,
        "planned_error_types": [] if clean else (planned or (["H1"] if histo else ["C1"])),
        "brief": "Invented brief for a planting test; it describes no patient.",
        "brief_status": "approved",
    }
    data["specimen_type" if histo else "scenario"] = "Invented subject"
    return SpecRow.model_validate(data)


def _apply(row, draft, body, taxonomy):
    sheet = parse_sheet(f"== {row.id} ==\n" + dedent(body).lstrip("\n"))
    assert sheet.problems == []
    if row.is_clean_control:
        draft = draft | {"is_clean_control": True}
    return apply_block(row, draft, sheet.blocks[row.id], taxonomy)


def _error(type_, severity, body):
    return f"[error]\ntype: {type_}\nseverity: {severity}\n{ERROR_TEXT}{dedent(body).lstrip()}"


# Parser


def test_parser_reads_comments_blocks_entries_and_colons():
    sheet = parse_sheet(
        dedent(
            """\
            # A comment before any block.
            == H-001 ==
              # An indented comment.
            verified: yes
            verified_on: 2026-11-12

            [fix]
            section: Synoptic summary
            find: Margins: Clear
            replace: Margins: Clear: closest 5 mm
            note: Invented note.
            [error]
            type: H1
            == C-001 ==
            verified: no
            """
        )
    )
    assert sheet.problems == []
    assert list(sheet.blocks) == ["H-001", "C-001"]
    block = sheet.blocks["H-001"]
    assert block.problems == []
    assert block.fields == {"verified": "yes", "verified_on": "2026-11-12"}
    assert [(e.tag, e.number, e.line) for e in block.entries] == [("fix", 1, 7), ("error", 1, 12)]
    assert block.entries[0].fields == {
        "section": "Synoptic summary",
        "find": "Margins: Clear",
        "replace": "Margins: Clear: closest 5 mm",
        "note": "Invented note.",
    }
    assert sheet.blocks["C-001"].fields == {"verified": "no"}


def test_parser_unknown_key():
    sheet = parse_sheet("== H-001 ==\nverified: no\n[fix]\nfnd: text\n")
    assert sheet.blocks["H-001"].problems == [
        "line 4: unknown key 'fnd' in [fix] 1 (line 3) (allowed keys: section, find, replace, note)"
    ]


def test_parser_report_key_inside_an_entry():
    sheet = parse_sheet("== H-001 ==\n[fix]\nverified: no\n")
    assert sheet.blocks["H-001"].problems == [
        "line 3: unknown key 'verified' in [fix] 1 (line 2) (report-level lines go before the "
        "first [fix] or [error] line)"
    ]


def test_parser_empty_value():
    sheet = parse_sheet("== H-001 ==\nverified: no\n[fix]\nfind:\n")
    assert sheet.blocks["H-001"].problems == [
        "line 4: 'find' has an empty value in [fix] 1 (line 3)"
    ]


def test_parser_line_without_key():
    sheet = parse_sheet("== H-001 ==\njust some words\n")
    assert sheet.blocks["H-001"].problems == [
        "line 2: expected 'key: value', '[fix]', '[error]' or '== <id> ==', got 'just some words'"
    ]


def test_parser_duplicate_block():
    sheet = parse_sheet("== H-001 ==\nverified: no\n== H-001 ==\nverified: yes\n")
    assert sheet.blocks["H-001"].problems == [
        "line 3: a second block for H-001 starts here (the first is at line 1); "
        "each report has exactly one block"
    ]
    assert sheet.blocks["H-001"].fields == {"verified": "no"}


def test_missing_key(histo_draft, fixed_taxonomy):
    body = "verified: no\n[error]\ntype: H1\nseverity: major\ndescription: Invented.\n"
    body += "section: Gross description\nfind: 18 mm across\nreplace: 25 mm across\n"
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.problems == ["[error] 1 (line 3): missing key 'rationale'"]


def _tree_drafts(root, drafts):
    folder = root / "data" / "drafts"
    folder.mkdir(parents=True, exist_ok=True)
    for draft in drafts:
        write_report_json(folder / f"{draft['id']}.json", draft)


def test_block_for_an_id_not_in_the_spec(tmp_path, histo_draft, fixed_taxonomy):
    _tree_drafts(tmp_path, [histo_draft | {"is_clean_control": True}])
    run = plan([_row("H-001", clean=True)], "== H-099 ==\nverified: no\n", tmp_path, fixed_taxonomy)
    assert run.problems == ["line 1: block '== H-099 ==' is for an id that is not in the spec"]
    assert not run.ok


def test_missing_block_builds_unchanged_and_unverified(tmp_path, histo_draft, fixed_taxonomy):
    draft = histo_draft | {"is_clean_control": True}
    _tree_drafts(tmp_path, [draft])
    run = plan([_row("H-001", clean=True)], "# no blocks yet\n", tmp_path, fixed_taxonomy)
    assert run.ok
    report = run.results[0].report
    assert report["sections"] == draft["sections"]
    assert report["errors"] == []
    assert report["is_clean_control"] is True
    assert report["provenance"] == {
        "drafted_by": "claude-haiku-5-5",
        "drafted_at": "2026-11-04",
        "edited_by": "owner",
        "verified": False,
        "verified_at": None,
    }


# Apply


def test_text_fix(histo_draft, fixed_taxonomy):
    body = """\
        verified: yes
        verified_on: 2026-11-12
        [fix]
        section: Gross description
        find: 18 mm across
        replace: 18 mm in greatest dimension
        note: Invented wording fix.
        """
    result = _apply(_row("H-001", clean=True), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    report = result.report
    assert report["sections"]["Gross description"] == (
        "Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm in greatest dimension."
    )
    assert report["errors"] == []
    assert report["provenance"]["verified"] is True
    assert report["provenance"]["verified_at"] == "2026-11-12"
    assert [f.note for f in result.fixes] == ["Invented wording fix."]


def test_text_error_with_given_quote(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        """
        section: Microscopic description
        find: Tumour measures 18 mm.
        replace: Tumour measures 25 mm.
        quote: Tumour measures 25 mm.
        """,
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"] == [
        {
            "error_id": "H-001-E1",
            "type": "H1",
            "section": "Microscopic description",
            "quoted_sentence": "Tumour measures 25 mm.",
            "severity": "major",
            "severity_reason": None,
            "description": "Invented description.",
            "rationale": "Invented rationale.",
            "kind": "statement",
        }
    ]
    assert result.report["is_clean_control"] is False


def test_text_error_in_synoptic_quotes_the_whole_line(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1", "major", "section: Synoptic summary\nfind: size: 18 mm\nreplace: size: 25 mm\n"
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == "Tumour size: 25 mm"
    assert result.report["sections"]["Synoptic summary"].startswith("Tumour size: 25 mm\n")


def test_text_error_quotes_a_replace_of_five_words_or_more(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        """
        section: Microscopic description
        find: Tumour measures 18 mm.
        replace: The tumour measures 25 mm across.
        """,
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == "The tumour measures 25 mm across."


def test_text_error_short_replace_without_quote_fails(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1", "major", "section: Microscopic description\nfind: 18 mm.\nreplace: 25 mm.\n"
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.problems == [FIVE_WORD_MESSAGE]
    assert result.report is None


@pytest.mark.parametrize(
    ("find", "section", "expected"),
    [
        (
            "invasive carcinoma",
            "Microscopic description",
            "[error] 1 (line 3): the find text occurs 0 times in 'Microscopic description' "
            "(it must occur exactly once); copy it exactly from the readable draft",
        ),
        (
            "Absent",
            "Synoptic summary",
            "[error] 1 (line 3): the find text occurs 2 times in 'Synoptic summary' "
            "(it must occur exactly once); add surrounding words from the readable draft so "
            "that it is unique",
        ),
    ],
)
def test_find_must_occur_exactly_once(histo_draft, fixed_taxonomy, find, section, expected):
    body = "verified: no\n" + _error(
        "H1", "major", f"section: {section}\nfind: {find}\nreplace: something else entirely\n"
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.problems == [expected]


def test_find_points_to_the_readable_draft(tmp_path, histo_draft, fixed_taxonomy):
    _tree_drafts(tmp_path, [histo_draft])
    sheet = "== H-001 ==\nverified: no\n" + _error(
        "H1", "major", "section: Diagnosis\nfind: grade 3\nreplace: grade 1\n"
    )
    run = plan([_row("H-001")], sheet, tmp_path, fixed_taxonomy)
    assert run.results[0].problems == [
        "[error] 1 (line 3): the find text occurs 0 times in 'Diagnosis' (it must occur "
        "exactly once); copy it exactly from data/drafts/_readable/H-001.md"
    ]


def test_whole_line_and_sentence_removal_leave_clean_text(histo_draft, fixed_taxonomy):
    body = (
        "verified: no\n"
        + _error(
            "H5",
            "major",
            """
            kind: omission
            remove_from: Synoptic summary
            remove: Perineural invasion: Absent
            anchor: Lymphovascular invasion: Absent
            """,
        )
        + _error(
            "H5",
            "minor",
            """
            kind: omission
            remove_from: Microscopic description
            remove: Tumour measures 18 mm.
            anchor_section: Diagnosis
            anchor: Invasive tumour of no special type, grade 2, 18 mm.
            """,
        )
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    sections = result.report["sections"]
    assert sections["Synoptic summary"] == SYNOPTIC.replace("Perineural invasion: Absent\n", "")
    assert sections["Microscopic description"] == (
        "Sections show an invasive tumour of no special type. Margins are clear."
    )
    first, second = result.report["errors"]
    assert (first["section"], first["quoted_sentence"], first["kind"]) == (
        "Synoptic summary",
        "Lymphovascular invasion: Absent",
        "omission",
    )
    assert (second["error_id"], second["section"]) == ("H-001-E2", "Diagnosis")
    assert result.notices == []


@pytest.mark.parametrize(
    ("text", "remove", "expected"),
    [
        ("One.\nTwo.\nThree.", "Two.", "One.\nThree."),
        ("One.\nTwo.\nThree.", "Three.", "One.\nTwo."),
        ("One.\nTwo.", "One.", "Two."),
        ("Only.", "Only.", ""),
        ("Alpha beta. Gamma delta. Epsilon.", "Gamma delta.", "Alpha beta. Epsilon."),
        ("Alpha beta. Gamma delta.", "Gamma delta.", "Alpha beta."),
        ("Tumour with invasion, grade 2.", "with invasion", "Tumour, grade 2."),
    ],
)
def test_remove_span_tidies_the_join(text, remove, expected):
    start = text.index(remove)
    assert remove_span(text, start, start + len(remove)) == expected


@pytest.mark.parametrize(
    "removal",
    [
        "remove_section: Comment\n",
        "remove_from: Comment\nremove: Invented comment for a planting test.\n",
    ],
)
def test_optional_section_removed_whole(histo_draft, fixed_taxonomy, removal):
    body = "verified: no\n" + _error(
        "H5", "major", f"kind: omission\n{removal}anchor: Staging edition: AJCC 8th edition\n"
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert "Comment" not in result.report["sections"]
    assert list(result.report["sections"])[-1] == "Synoptic summary"


def test_removing_a_required_section_fails(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H5", "major", "kind: omission\nremove_section: Diagnosis\nanchor: pT: pT1c\n"
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.problems == [
        "[error] 1 (line 3): 'Diagnosis' is a required section and cannot be removed; "
        "use remove_from with remove to delete text from it"
    ]


def test_number_change_rerenders_values_and_never_rederives(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error("C2", "minor", "set: MCHC = 41.0\n")
    result = _apply(_row("C-001", planned=["C2"]), cbc_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    report = result.report
    mchc_line = "MCHC: 41.0 g/dL (ref 31.5–34.5)"
    assert report["cbc_values"]["MCHC"]["value"] == 41.0
    unchanged = {k: v for k, v in cbc_draft["cbc_values"].items() if k != "MCHC"}
    assert {k: v for k, v in report["cbc_values"].items() if k != "MCHC"} == unchanged
    old_lines = cbc_draft["sections"]["Values"].split("\n")
    new_lines = report["sections"]["Values"].split("\n")
    changed = [(a, b) for a, b in zip(old_lines, new_lines, strict=True) if a != b]
    assert changed == [("MCHC: 30.3 g/dL (ref 31.5–34.5)", mchc_line)]
    assert report["sections"]["Interpretation"] == cbc_draft["sections"]["Interpretation"]
    error = report["errors"][0]
    assert (error["section"], error["quoted_sentence"]) == ("Values", mchc_line)


def test_number_change_without_c2_fails_validation(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error("C1", "major", "set: MCHC = 41.0\n")
    result = _apply(_row("C-001", planned=["C1"]), cbc_draft, body, fixed_taxonomy)
    assert result.problems == [
        "validation: derived index inconsistency: MCHC is 41 g/dL, expected 30.30 g/dL (±1)"
    ]


def test_number_change_quote_analyte(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "C1", "major", "set: Hb = 9.8\nset: Platelets = 90\nquote_analyte: Platelets\n"
    )
    result = _apply(_row("C-001", planned=["C1"]), cbc_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    values = result.report["cbc_values"]
    assert (values["Hb"]["value"], values["Platelets"]["value"]) == (9.8, 90.0)
    assert result.report["errors"][0]["quoted_sentence"] == "Platelets: 90 x10^9/L (ref 150–410)"


def test_omission_with_anchor_analyte(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "C3",
        "critical",
        """
        kind: omission
        remove_from: Interpretation
        remove: Platelets are within the reference range.
        anchor_analyte: Platelets
        """,
    )
    result = _apply(_row("C-001", planned=["C3"]), cbc_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    report = result.report
    assert report["sections"]["Interpretation"] == "Mild anaemia with normal red cell indices."
    error = report["errors"][0]
    assert (error["kind"], error["section"], error["quoted_sentence"]) == (
        "omission",
        "Values",
        "Platelets: 250 x10^9/L (ref 150–410)",
    )


def test_anchor_in_a_section_the_validator_does_not_allow_fails(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H5",
        "major",
        """
        kind: omission
        remove_from: Synoptic summary
        remove: Perineural invasion: Absent
        anchor_section: Final diagnosis
        anchor: Invasive tumour of no special type, grade 2, 18 mm.
        """,
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.problems == [
        "validation: H-001-E1: section 'Final diagnosis' is not in the report",
        # EVAL-04: the validator also restricts where an omission's anchor may be.
        "validation: H-001-E1: an omission's anchor must be in 'Synoptic summary' or "
        "'Diagnosis', not in 'Final diagnosis'",
    ]


def test_anchor_in_an_existing_section_the_validator_does_not_allow_fails(
    histo_draft, fixed_taxonomy
):
    """EVAL-04 (decision on omission anchors): the Microscopic description exists and holds
    the anchor verbatim, but an omission's anchor must be in Synoptic summary or Diagnosis."""
    body = "verified: no\n" + _error(
        "H5",
        "major",
        """
        kind: omission
        remove_from: Synoptic summary
        remove: Perineural invasion: Absent
        anchor_section: Microscopic description
        anchor: Margins are clear.
        """,
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.problems == [
        "validation: H-001-E1: an omission's anchor must be in 'Synoptic summary' or "
        "'Diagnosis', not in 'Microscopic description'"
    ]


def test_clean_report_with_an_error_fails(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1", "major", "section: Diagnosis\nfind: grade 2\nreplace: grade 3 of 3, invented here\n"
    )
    result = _apply(_row("H-001", clean=True), histo_draft, body, fixed_taxonomy)
    assert result.problems == [
        "H-001 is a clean control in the spec, but the block has 1 [error] entry"
    ]


def test_planted_report_without_errors_fails(histo_draft, fixed_taxonomy):
    result = _apply(_row("H-001"), histo_draft, "verified: no\n", fixed_taxonomy)
    assert result.problems == [
        "no planted errors yet (the spec marks this report as planted; add at least one "
        "[error] entry)"
    ]


def test_severity_outside_defaults_without_reason_fails(histo_draft, fixed_taxonomy):
    entry = "section: Diagnosis\nfind: grade 2\nreplace: grade 3 of 3, invented here\n"
    result = _apply(
        _row("H-001"),
        histo_draft,
        "verified: no\n" + _error("H1", "critical", entry),
        fixed_taxonomy,
    )
    assert result.problems == [
        "validation: H-001-E1: severity critical is not a default (major) and "
        "severity_reason is empty"
    ]
    with_reason = _error("H1", "critical", entry + "severity_reason: Invented reason.\n")
    assert _apply(_row("H-001"), histo_draft, "verified: no\n" + with_reason, fixed_taxonomy).ok


def test_verified_yes_without_verified_on_fails(histo_draft, fixed_taxonomy):
    result = _apply(_row("H-001", clean=True), histo_draft, "verified: yes\n", fixed_taxonomy)
    assert result.problems == ["verified is yes, so verified_on (YYYY-MM-DD) is required"]


def test_planted_types_that_differ_from_the_plan_are_a_notice(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1", "major", "section: Synoptic summary\nfind: size: 18 mm\nreplace: size: 25 mm\n"
    )
    result = _apply(_row("H-001", planned=["H3"]), histo_draft, body, fixed_taxonomy)
    assert result.ok
    assert result.notices == ["H-001: planted types H1 differ from the spec's planned types H3"]


def test_built_report_is_checked_with_the_full_rule_set(monkeypatch, histo_draft, fixed_taxonomy):
    """EVAL-02c-fix: a built report is a final report, so every validator rule runs on it.

    check_report(..., drafts=True) would skip check_clean_control; the plain-words check
    before it does not replace the validator rule.
    """
    calls = []
    real_check_report = plant.check_report

    def recording_check_report(report, taxonomy, drafts=False):
        calls.append(drafts)
        return real_check_report(report, taxonomy, drafts=drafts)

    monkeypatch.setattr(plant, "check_report", recording_check_report)
    body = "verified: no\n" + _error(
        "H1", "major", "section: Synoptic summary\nfind: size: 18 mm\nreplace: size: 25 mm\n"
    )
    assert _apply(_row("H-001"), histo_draft, body, fixed_taxonomy).ok
    assert calls == [False]


# Commands on a complete temporary tree


def _spec_rows():
    rows, counts = [], {"histopathology": 0, "cbc": 0}
    for (modality, split, clean), n in DATASET_SHAPE.items():
        for _ in range(n):
            counts[modality] += 1
            prefix = "H" if modality == "histopathology" else "C"
            rows.append(_row(f"{prefix}-{counts[modality]:03d}", clean=clean, split=split))
    return rows


@pytest.fixture
def tree(tmp_path, histo_draft, cbc_draft, monkeypatch):
    """34 invented rows and drafts, a final taxonomy; H-001 planted, H-016 clean."""
    root = tmp_path
    (root / "data" / "specs").mkdir(parents=True)
    taxonomy = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    write_report_json(root / "data" / "taxonomy.json", taxonomy | {"status": "final"})
    rows = _spec_rows()
    write_report_json(
        root / "data" / "specs" / "dataset.json",
        {"version": "0.1", "reports": [r.model_dump(mode="json") for r in rows]},
    )
    drafts = []
    for row in rows:
        base = histo_draft if row.modality == "histopathology" else cbc_draft
        drafts.append(
            copy.deepcopy(base)
            | {"id": row.id, "split": row.split, "is_clean_control": row.is_clean_control}
        )
    _tree_drafts(root, drafts)
    monkeypatch.setattr(cli, "PLANT_ROOT", root)
    return root


GOOD_SHEET = (
    "== H-001 ==\nverified: yes\nverified_on: 2026-11-12\n"
    + _error(
        "H1",
        "major",
        """
        section: Microscopic description
        find: Tumour measures 18 mm.
        replace: The tumour measures 25 mm across.
        """,
    )
    + "== H-016 ==\nverified: no\n[fix]\nsection: Specimen\nfind: left side\n"
    + "replace: left breast\nnote: Invented fix.\n"
)


def _snapshot(folder):
    return {p.relative_to(folder): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def test_init_writes_the_template_and_refuses_an_existing_sheet(tree, capsys):
    assert cli.main(["plant", "--init"]) == 0
    sheet = tree / SHEET_FILE
    text = sheet.read_text(encoding="utf-8")
    assert capsys.readouterr().out == "wrote data/specs/planting.md | 34 blocks, all verified: no\n"
    assert text.count("\nverified: no\n") == 34
    assert "== H-001 ==\n# scored | planted | planned types: H1\nverified: no\n" in text
    assert "== H-016 ==\n# scored | clean control | planned types: none\nverified: no\n" in text
    assert "\n[error]" not in text and "\n[fix]" not in text  # examples stay commented out
    assert text.count("# [error]\n") == 25
    before = sheet.read_bytes()
    assert cli.main(["plant", "--init"]) == 1
    assert (
        capsys.readouterr().out == "plant --init refused: data/specs/planting.md already exists\n"
    )
    assert sheet.read_bytes() == before


def test_check_on_the_template_reports_every_planted_report(tree, capsys):
    assert cli.main(["plant", "--init"]) == 0
    capsys.readouterr()
    assert cli.main(["plant", "--check"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == (
        "H-001 no planted errors yet (the spec marks this report as planted; add at least one "
        "[error] entry)"
    )
    assert "H-016 OK" in lines
    assert sum(line.endswith(" OK") for line in lines) == 9
    assert sum("no planted errors yet" in line for line in lines) == 25
    assert lines[-1] == "plant --check: 9 OK, 25 with problems, 0 sheet problem(s); nothing written"


def test_check_writes_nothing(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    before = _snapshot(tree)
    assert cli.main(["plant", "--check"]) == 1
    out = capsys.readouterr().out
    assert "H-001 OK" in out and "H-016 OK" in out
    assert _snapshot(tree) == before


def test_plant_refuses_on_a_draft_taxonomy(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    path = tree / "data" / "taxonomy.json"
    write_report_json(path, read_report_json(path) | {"status": "draft"})
    assert cli.main(["plant"]) == 1
    assert capsys.readouterr().out == (
        "plant refused: taxonomy status is 'draft', not 'final' "
        "(plant --check works with a draft taxonomy)\n"
    )
    assert not (tree / "data" / "reports").exists()


def test_plant_builds_reports_and_review_files(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    assert cli.main(["plant"]) == 1  # 24 planted reports still have no errors
    out = capsys.readouterr().out
    assert "H-001 built | 1 planted error(s), 0 fix(es) | verified yes" in out
    assert "H-016 built | 0 planted error(s), 1 fix(es) | verified no" in out
    assert "H-002 NOT UPDATED\n  no planted errors yet" in out
    assert "verified: 1 of 10 reports in data/reports" in out
    assert "  H1   1 /  0 /  1" in out
    report = read_report_json(tree / "data" / "reports" / "H-001.json")
    assert report["errors"][0]["quoted_sentence"] == "The tumour measures 25 mm across."
    review = (tree / "data" / "reports" / "_review" / "H-001.md").read_text(encoding="utf-8")
    assert "## Microscopic description\nSections show an invasive tumour" in review
    assert "   quote: The tumour measures 25 mm across." in review


def test_plant_is_deterministic_and_never_touches_drafts(tree):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    drafts = _snapshot(tree / "data" / "drafts")
    cli.main(["plant"])
    first = _snapshot(tree / "data" / "reports")
    cli.main(["plant"])
    assert _snapshot(tree / "data" / "reports") == first
    assert _snapshot(tree / "data" / "drafts") == drafts
    assert len(first) == 20  # 10 reports (H-001 and the 9 clean controls), 10 review files


def test_failing_block_leaves_the_existing_report_untouched(tree, capsys):
    sheet = tree / SHEET_FILE
    sheet.write_text(GOOD_SHEET, encoding="utf-8")
    cli.main(["plant"])
    report = tree / "data" / "reports" / "H-001.json"
    review = tree / "data" / "reports" / "_review" / "H-001.md"
    before = report.read_bytes(), review.read_bytes()
    sheet.write_text(GOOD_SHEET.replace("find: Tumour measures 18 mm.", "find: No such text."))
    capsys.readouterr()
    assert cli.main(["plant"]) == 1
    out = capsys.readouterr().out
    assert "H-001 NOT UPDATED\n  [error] 1 (line 4): the find text occurs 0 times" in out
    assert (report.read_bytes(), review.read_bytes()) == before


# readable


@pytest.mark.parametrize("name", ["histo", "cbc"])
def test_readable_golden(request, name):
    report = request.getfixturevalue(name)
    golden = "histopathology" if name == "histo" else "cbc"
    assert readable_markdown(report) == fixture_text(f"readable_{golden}.md")


def test_readable_command(tmp_path, histo, cbc, capsys):
    write_report_json(tmp_path / "H-001.json", histo)
    write_report_json(tmp_path / "C-001.json", cbc)
    assert cli.main(["readable", str(tmp_path)]) == 0
    out = tmp_path / "_readable"
    assert sorted(p.name for p in out.iterdir()) == ["C-001.md", "H-001.md"]
    assert (out / "H-001.md").read_text(encoding="utf-8") == fixture_text(
        "readable_histopathology.md"
    )
    assert capsys.readouterr().out.count("wrote ") == 2


@pytest.mark.parametrize("bad_id", ["../escaped", "..\\escaped", "sub/dir/deep", "H-001.json"])
def test_readable_refuses_an_id_that_is_not_a_report_id(tmp_path, histo, capsys, bad_id):
    """EVAL-02c-fix: the output file is named from the id inside the JSON, so an id with path
    parts must never place a file outside <folder>/_readable/ (or crash with a traceback)."""
    folder = tmp_path / "drafts"
    folder.mkdir()
    write_report_json(folder / "H-001.json", histo)
    write_report_json(folder / "bad.json", histo | {"id": bad_id})
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert f"FAIL {folder / 'bad.json'}: cannot make a readable file (id " in out
    assert "is not a report id such as H-001)" in out
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert files == ["drafts/H-001.json", "drafts/_readable/H-001.md", "drafts/bad.json"]


# EVAL-02c-fix: defects found by the S1 adversarial review (each test failed before its fix)


@pytest.mark.parametrize(
    "raw",
    [
        "# Owner note: Hb range 13.0–17.0\n== H-016 ==\nverified: no\n".encode("cp1252"),
        "== H-016 ==\r\nverified: no\r\n".encode("utf-16"),
    ],
    ids=["cp1252", "utf-16"],
)
@pytest.mark.parametrize("command", [["plant", "--check"], ["plant"]])
def test_a_sheet_that_is_not_utf8_is_refused_in_plain_words(tree, capsys, raw, command):
    (tree / SHEET_FILE).write_bytes(raw)
    assert cli.main(command) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL data/specs/planting.md is not UTF-8 text (")
    assert out.rstrip().endswith("save it as UTF-8 and run the command again")
    assert not (tree / "data" / "reports").exists()


@pytest.mark.parametrize(
    ("text", "remove", "expected"),
    [
        ("A one.\n\nB two.\n\nC three.", "B two.", "A one.\n\nC three."),
        ("A one.\n\nB two.", "A one.", "B two."),
        ("A one.\n\nB two.", "B two.", "A one."),
        ("A one.\nB two.\n\nC three.", "C three.", "A one.\nB two."),
    ],
)
def test_whole_line_removal_next_to_a_blank_line_leaves_no_empty_line(text, remove, expected):
    start = text.index(remove)
    assert remove_span(text, start, start + len(remove)) == expected


def test_omission_of_a_paragraph_leaves_one_blank_line(histo_draft, fixed_taxonomy):
    histo_draft["sections"]["Comment"] = (
        "First invented paragraph.\n\nSecond invented paragraph.\n\nThird invented paragraph."
    )
    body = "verified: no\n" + _error(
        "H5",
        "major",
        """
        kind: omission
        remove_from: Comment
        remove: Second invented paragraph.
        anchor: Staging edition: AJCC 8th edition
        """,
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["sections"]["Comment"] == (
        "First invented paragraph.\n\nThird invented paragraph."
    )


def test_five_word_minimum_counts_words_not_punctuation(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1", "major", "section: Diagnosis\nfind: 18 mm.\nreplace: 25 mm - - -\n"
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.problems == [FIVE_WORD_MESSAGE]


@pytest.mark.parametrize("bad_type", ["h1", "H9", "X1", "H1."])
def test_a_type_that_is_not_a_taxonomy_id_is_reported_in_plain_words(
    histo_draft, fixed_taxonomy, bad_type
):
    sheet = (
        f"== H-001 ==\nverified: no\n[error]\ntype: {bad_type}\nseverity: major\n{ERROR_TEXT}"
        "section: Diagnosis\nfind: grade 2\nreplace: grade 3 of 3, invented here\n"
    )
    parsed = parse_sheet(sheet)
    result = apply_block(_row("H-001"), histo_draft, parsed.blocks["H-001"], fixed_taxonomy)
    assert result.problems == [
        f"[error] 1 (line 3): type '{bad_type}' is not a taxonomy id "
        "(H1, H2, H3, H4, H5, H6, C1, C2, C3)"
    ]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("null\n", "data/drafts/H-016.json is not a JSON object (it holds null)"),
        ("[]\n", "data/drafts/H-016.json is not a JSON object (it holds an array)"),
        ('"text"\n', "data/drafts/H-016.json is not a JSON object (it holds a string)"),
        (
            "{not json\n",
            "data/drafts/H-016.json does not parse as JSON (Expecting property name enclosed "
            "in double quotes at line 1, column 2)",
        ),
        (
            "﻿{}\n",
            "data/drafts/H-016.json does not parse as JSON (Unexpected UTF-8 BOM (decode using "
            "utf-8-sig) at line 1, column 1)",
        ),
        (
            "[" * 100000 + "]" * 100000,
            "data/drafts/H-016.json does not parse as JSON (nested too deeply)",
        ),
    ],
    ids=["null", "array", "string", "invalid", "bom", "deep"],
)
def test_a_draft_that_is_not_a_report_object_is_reported_as_unparseable(
    tmp_path, fixed_taxonomy, content, expected
):
    """The problem names the real cause (round 2: a count of missing fields was shown, and
    JSON nested too deeply stopped the whole run with a traceback)."""
    folder = tmp_path / "data" / "drafts"
    folder.mkdir(parents=True)
    (folder / "H-016.json").write_text(content, encoding="utf-8")
    run = plan([_row("H-016", clean=True)], "", tmp_path, fixed_taxonomy)
    assert run.results[0].problems == [expected]


def test_plant_check_reports_every_report_when_one_draft_is_nested_too_deeply(tree, capsys):
    (tree / "data" / "drafts" / "C-011.json").write_text("[" * 100000 + "]" * 100000)
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    assert cli.main(["plant", "--check"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "H-001 OK" in lines
    assert "C-011 data/drafts/C-011.json does not parse as JSON (nested too deeply)" in lines


def test_readable_reports_a_section_that_is_not_text_and_goes_on(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    write_report_json(folder / "H-001.json", histo | {"sections": histo["sections"] | {"X": None}})
    write_report_json(folder / "H-002.json", histo | {"id": "H-002"})
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert (
        f"FAIL {folder / 'H-001.json'}: cannot make a readable file (section 'X' is not text)"
        in out
    )
    assert sorted(p.name for p in (folder / "_readable").iterdir()) == ["H-002.md"]


def test_readable_ignores_a_folder_whose_name_ends_in_json(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    (folder / "A-old.json").mkdir()
    write_report_json(folder / "H-001.json", histo)
    assert cli.main(["readable", str(folder)]) == 0
    assert capsys.readouterr().out == f"wrote {(folder / '_readable' / 'H-001.md').as_posix()}\n"


# Tests that pin behaviour the S1 review showed was not pinned (each kills a named mutant)


def test_a_given_quote_is_stored_rather_than_the_replace_text(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        """
        section: Microscopic description
        find: Tumour measures 18 mm.
        replace: Tumour measures 25 mm in this invented case.
        quote: Tumour measures 25 mm in this invented case. Margins are clear.
        """,
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == (
        "Tumour measures 25 mm in this invented case. Margins are clear."
    )


def test_a_given_quote_wins_over_the_synoptic_line_rule(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        "section: Synoptic summary\nfind: size: 18 mm\nreplace: size: 25 mm\nquote: size: 25 mm\n",
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == "size: 25 mm"


def test_synoptic_quote_is_the_whole_line_for_a_later_line_changed_mid_line(
    histo_draft, fixed_taxonomy
):
    body = "verified: no\n" + _error(
        "H4",
        "major",
        "section: Synoptic summary\nfind: nodes (positive\nreplace: nodes (involved\n",
    )
    result = _apply(_row("H-001", planned=["H4"]), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == "Lymph nodes (involved/total): 0/3"


@pytest.mark.parametrize(
    ("replace", "ok"),
    [("The tumour measures 25 mm.", True), ("Tumour is 25 mm.", False)],
    ids=["five words", "four words"],
)
def test_five_word_boundary(histo_draft, fixed_taxonomy, replace, ok):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        f"section: Microscopic description\nfind: Tumour measures 18 mm.\nreplace: {replace}\n",
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    if ok:
        assert result.ok, result.problems
        assert result.report["errors"][0]["quoted_sentence"] == replace
    else:
        assert result.problems == [FIVE_WORD_MESSAGE]


def test_overlapping_occurrences_count_separately(histo_draft, fixed_taxonomy):
    histo_draft["sections"]["Comment"] = "Invented ratio 1/1/1 recorded."
    body = "verified: no\n[fix]\nsection: Comment\nfind: 1/1\nreplace: 2/2\nnote: Invented note.\n"
    result = _apply(_row("H-001", clean=True), histo_draft, body, fixed_taxonomy)
    assert result.problems == [
        "[fix] 1 (line 3): the find text occurs 2 times in 'Comment' (it must occur exactly "
        "once); add surrounding words from the readable draft so that it is unique"
    ]


def test_number_change_quotes_the_first_set_analyte_by_default(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error("C2", "minor", "set: MCHC = 41.0\nset: Hb = 9.0\n")
    result = _apply(_row("C-001", planned=["C2"]), cbc_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["errors"][0]["quoted_sentence"] == "MCHC: 41.0 g/dL (ref 31.5–34.5)"


def test_replace_must_differ_from_find(histo_draft, fixed_taxonomy):
    body = "verified: no\n[fix]\nsection: Specimen\nfind: left side\nreplace: left side\nnote: N.\n"
    result = _apply(_row("H-001", clean=True), histo_draft, body, fixed_taxonomy)
    assert result.problems == ["[fix] 1 (line 3): replace is the same as find"]


def test_fixes_apply_before_errors_whatever_the_sheet_order(histo_draft, fixed_taxonomy):
    body = (
        "verified: no\n"
        + _error(
            "H1",
            "major",
            "section: Gross description\nfind: lesion 19 mm across\n"
            "replace: lesion 25 mm across in this invented case\n",
        )
        + "[fix]\nsection: Gross description\nfind: 18 mm across\nreplace: 19 mm across\n"
        + "note: Invented fix.\n"
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["sections"]["Gross description"] == (
        "Fatty tissue 40 x 30 x 20 mm with a firm lesion 25 mm across in this invented case."
    )


def test_review_file_lists_fixes_and_plant_prints_the_validator_summary(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    cli.main(["plant"])
    out = capsys.readouterr().out
    summary = [line for line in out.splitlines() if line.startswith("validate: ")]
    assert len(summary) == 1
    assert summary[0].startswith("validate: 10 reports | histopathology 7, cbc 3 |")
    assert summary[0].endswith("| OK")
    review = (tree / "data" / "reports" / "_review" / "H-016.md").read_text(encoding="utf-8")
    assert "## Fixes\n\n1. Specimen\n   find: left side\n   replace: left breast\n" in review


def test_plant_rebuilds_a_report_after_the_sheet_changes(tree):
    sheet = tree / SHEET_FILE
    sheet.write_text(GOOD_SHEET, encoding="utf-8")
    cli.main(["plant"])
    sheet.write_text(GOOD_SHEET.replace("25 mm across.", "26 mm across."), encoding="utf-8")
    cli.main(["plant"])
    report = read_report_json(tree / "data" / "reports" / "H-001.json")
    assert report["errors"][0]["quoted_sentence"] == "The tumour measures 26 mm across."


def test_init_writes_one_block_per_spec_row_in_spec_order(tree):
    assert cli.main(["plant", "--init"]) == 0
    text = (tree / SHEET_FILE).read_text(encoding="utf-8")
    blocks = [line[3:-3] for line in text.splitlines() if line.startswith("== ")]
    spec = read_report_json(tree / "data" / "specs" / "dataset.json")
    assert blocks == [row["id"] for row in spec["reports"]]


def test_readable_keeps_section_text_exactly_as_stored(histo):
    histo["sections"]["Comment"] = "  Indented first line.\nLast line ends with spaces.  "
    expected = "## Comment\n  Indented first line.\nLast line ends with spaces.  \n"
    assert expected in readable_markdown(histo)


def test_check_works_with_a_draft_taxonomy(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    path = tree / "data" / "taxonomy.json"
    write_report_json(path, read_report_json(path) | {"status": "draft"})
    assert cli.main(["plant", "--check"]) == 1  # 24 planted reports still have no errors
    out = capsys.readouterr().out
    assert "refused" not in out
    assert "H-001 OK" in out and "H-016 OK" in out


def _complete_sheet(spec_path, h001_entry=None) -> str:
    """Every planted row gets one invented error (H-001 gets h001_entry if given); every clean
    row gets a bare block."""
    blocks = []
    for row in read_report_json(spec_path)["reports"]:
        block = f"== {row['id']} ==\nverified: no\n"
        if row["is_clean_control"]:
            pass
        elif row["id"] == "H-001" and h001_entry:
            block += h001_entry
        elif row["modality"] == "histopathology":
            block += _error(
                "H1",
                "major",
                "section: Microscopic description\nfind: Tumour measures 18 mm.\n"
                "replace: The tumour measures 25 mm across.\n",
            )
        else:
            block += _error(
                "C1",
                "major",
                "section: Interpretation\nfind: Mild anaemia with normal red cell indices.\n"
                "replace: Marked anaemia with normal red cell indices.\n",
            )
        blocks.append(block)
    return "".join(blocks)


def test_plant_exits_zero_when_every_block_is_ok(tree, capsys):
    sheet = _complete_sheet(tree / "data" / "specs" / "dataset.json")
    (tree / SHEET_FILE).write_text(sheet, encoding="utf-8")
    assert cli.main(["plant"]) == 0
    out = capsys.readouterr().out
    assert "NOT UPDATED" not in out
    assert "notices: none" in out


def test_plant_prints_the_notices_after_a_build(tree, capsys):
    h2 = _error(
        "H2",
        "critical",
        "section: Diagnosis\nfind: grade 2\nreplace: grade 3 of 3, invented here\n",
    )
    sheet = _complete_sheet(tree / "data" / "specs" / "dataset.json", h001_entry=h2)
    (tree / SHEET_FILE).write_text(sheet, encoding="utf-8")
    assert cli.main(["plant"]) == 0
    out = capsys.readouterr().out
    assert "notices:\n  H-001: planted types H2 differ from the spec's planned types H1\n" in out


# EVAL-02c-fix, S1 review round 2 (each test failed before its fix)

_FILE_WRITES = {"write_text", "write_bytes", "mkdir", "open", "touch", "unlink", "rename", "rmdir"}


def test_plant_module_writes_only_through_write_outputs():
    """S1: no code path in plant.py may write under data/drafts/. Its only file writes are in
    write_outputs, which writes data/reports/ and data/reports/_review/; the `readable`
    command lives in readable.py."""
    tree = ast.parse(Path(plant.__file__).read_text(encoding="utf-8"))
    writers = set()
    for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                called = node.func
                name = called.attr if isinstance(called, ast.Attribute) else called.id
                if name in _FILE_WRITES | {"write_report_json", "append_jsonl"}:
                    writers.add(func.name)
    assert writers == {"write_outputs"}
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module)])
    }
    assert not imported & {"os", "shutil", "tempfile"}  # no file operations outside the check


@pytest.mark.parametrize(
    ("text", "remove", "expected"),
    [
        ("A one.\n\n\nB two.", "A one.", "B two."),
        ("A one.\n\n\nB two.", "B two.", "A one."),
        ("A.\n\n\nB.\n\n\nC.", "B.", "A.\n\n\nC."),
        ("A.\nB.\n\nC.", "B.", "A.\n\nC."),
    ],
)
def test_whole_line_removal_beside_several_blank_lines(text, remove, expected):
    start = text.index(remove)
    assert remove_span(text, start, start + len(remove)) == expected


def test_omission_of_a_first_paragraph_before_two_blank_lines(histo_draft, fixed_taxonomy):
    histo_draft["sections"]["Comment"] = "First invented paragraph.\n\n\nSecond invented paragraph."
    body = "verified: no\n" + _error(
        "H5",
        "major",
        """
        kind: omission
        remove_from: Comment
        remove: First invented paragraph.
        anchor: Staging edition: AJCC 8th edition
        """,
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert result.ok, result.problems
    assert result.report["sections"]["Comment"] == "Second invented paragraph."


def test_a_utf16_sheet_without_a_bom_is_refused_and_reports_stay_as_they_are(tree, capsys):
    sheet = tree / SHEET_FILE
    text = "== H-016 ==\nverified: yes\nverified_on: 2026-11-12\n"
    sheet.write_text(text, encoding="utf-8")
    cli.main(["plant"])
    report = tree / "data" / "reports" / "H-016.json"
    assert read_report_json(report)["provenance"]["verified"] is True
    before = report.read_bytes()
    sheet.write_bytes(text.encode("utf-16-le"))
    capsys.readouterr()
    assert cli.main(["plant"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL data/specs/planting.md is not UTF-8 text (it contains NUL ")
    assert report.read_bytes() == before


def test_readable_reports_a_file_it_cannot_write(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    write_report_json(folder / "H-001.json", histo)
    (folder / "_readable").write_text("a file where the folder should be", encoding="utf-8")
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAIL {folder / 'H-001.json'}: cannot write ")


def test_readable_reports_json_nested_too_deeply_and_goes_on(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    (folder / "A-deep.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    write_report_json(folder / "H-001.json", histo)
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert (
        f"FAIL {folder / 'A-deep.json'}: cannot make a readable file (JSON nested too deeply)"
        in out
    )
    assert (folder / "_readable" / "H-001.md").is_file()


def test_readable_reports_a_file_it_cannot_read_and_goes_on(tmp_path, histo, capsys, monkeypatch):
    from pathqc_eval import readable as readable_module

    folder = tmp_path / "drafts"
    folder.mkdir()
    write_report_json(folder / "H-001.json", histo)
    write_report_json(folder / "H-002.json", histo | {"id": "H-002"})
    real_read = readable_module.read_report_json

    def read(path):
        if Path(path).name == "H-001.json":
            raise PermissionError(13, "Permission denied", str(path))
        return real_read(path)

    monkeypatch.setattr(readable_module, "read_report_json", read)
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert f"FAIL {folder / 'H-001.json'}: cannot make a readable file (" in out
    assert sorted(p.name for p in (folder / "_readable").iterdir()) == ["H-002.md"]


def test_a_draft_that_cannot_be_read_is_reported_in_plain_words(
    tmp_path, histo_draft, fixed_taxonomy, monkeypatch
):
    folder = tmp_path / "data" / "drafts"
    folder.mkdir(parents=True)
    write_report_json(folder / "H-016.json", histo_draft | {"id": "H-016"})

    def unreadable(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(plant, "read_report_json", unreadable)
    run = plan([_row("H-016", clean=True)], "", tmp_path, fixed_taxonomy)
    assert run.results[0].problems == ["data/drafts/H-016.json cannot be read (Permission denied)"]


# EVAL-02c-fix, S1 review round 3 (each test failed before its fix)

LONE_SURROGATE = "Invented comment \\ud83d with half a character."  # JSON text: a \ud83d escape


def _plan_one(tmp_path, taxonomy, raw: bytes):
    folder = tmp_path / "data" / "drafts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "H-016.json").write_bytes(raw)
    return plan([_row("H-016", clean=True)], "", tmp_path, taxonomy).results[0].problems


def test_a_draft_with_an_integer_too_long_to_read_is_reported_in_plain_words(
    tmp_path, fixed_taxonomy
):
    problems = _plan_one(tmp_path, fixed_taxonomy, b'{"n": ' + b"1" * 5000 + b"}\n")
    assert len(problems) == 1
    assert problems[0].startswith(
        "data/drafts/H-016.json does not parse as JSON (Exceeds the limit (4300 digits)"
    )


def test_a_draft_that_is_not_utf8_is_reported_in_plain_words(tmp_path, fixed_taxonomy):
    problems = _plan_one(tmp_path, fixed_taxonomy, b'{"x": "\x96"}\n')
    assert problems == ["data/drafts/H-016.json is not UTF-8 text (invalid start byte at byte 7)"]


def _with_lone_surrogate(draft: dict) -> bytes:
    """The draft as JSON text whose Comment holds an unpaired surrogate escape."""
    text = json.dumps(draft | {"sections": draft["sections"] | {"Comment": "PLACEHOLDER"}})
    return text.replace("PLACEHOLDER", LONE_SURROGATE).encode("utf-8")


def test_a_draft_with_a_lone_surrogate_is_reported_in_plain_words(
    tmp_path, histo_draft, fixed_taxonomy
):
    raw = _with_lone_surrogate(histo_draft | {"id": "H-016", "is_clean_control": True})
    problems = _plan_one(tmp_path, fixed_taxonomy, raw)
    assert problems == [
        "data/drafts/H-016.json holds text that cannot be written as UTF-8 (surrogates not allowed)"
    ]


def test_plant_never_empties_a_report_whose_draft_holds_a_lone_surrogate(tree, capsys):
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    cli.main(["plant"])
    report = tree / "data" / "reports" / "H-016.json"
    before = report.read_bytes()
    draft_path = tree / "data" / "drafts" / "H-016.json"
    draft_path.write_bytes(_with_lone_surrogate(read_report_json(draft_path)))
    capsys.readouterr()
    assert cli.main(["plant", "--check"]) == 1
    assert "H-016 data/drafts/H-016.json holds text that cannot be written as UTF-8" in (
        capsys.readouterr().out
    )
    assert cli.main(["plant"]) == 1
    out = capsys.readouterr().out
    assert "H-016 NOT UPDATED\n  data/drafts/H-016.json holds text that cannot be written" in out
    assert "H-001 built |" in out and "validate: " in out
    assert report.read_bytes() == before


def test_readable_reports_a_lone_surrogate_and_goes_on(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    (folder / "A-surrogate.json").write_bytes(_with_lone_surrogate(histo))
    write_report_json(folder / "H-002.json", histo | {"id": "H-002"})
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert (
        f"FAIL {folder / 'A-surrogate.json'}: cannot make a readable file (it holds text that "
        "cannot be written as UTF-8 (surrogates not allowed))\n"
    ) in out
    assert sorted(p.name for p in (folder / "_readable").iterdir()) == ["H-002.md"]


def test_readable_goes_on_after_a_file_it_cannot_write(tmp_path, histo, capsys):
    folder = tmp_path / "drafts"
    folder.mkdir()
    write_report_json(folder / "H-001.json", histo)
    write_report_json(folder / "H-002.json", histo | {"id": "H-002"})
    (folder / "_readable" / "H-001.md").mkdir(parents=True)  # a folder where the file goes
    assert cli.main(["readable", str(folder)]) == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAIL {folder / 'H-001.json'}: cannot write ")
    assert (folder / "_readable" / "H-002.md").is_file()


def test_readable_keeps_the_last_sections_trailing_line_breaks(histo):
    histo["sections"]["Synoptic summary"] += "\n\n"
    assert readable_markdown(histo).endswith("Staging edition: AJCC 8th edition\n\n\n")


def test_draft_problems_never_write_under_data_drafts(tree, capsys):
    (tree / "data" / "drafts" / "H-016.json").write_text("{not json", encoding="utf-8")
    (tree / "data" / "drafts" / "C-011.json").write_text("[" * 100000 + "]" * 100000)
    (tree / SHEET_FILE).write_text(GOOD_SHEET, encoding="utf-8")
    drafts = _snapshot(tree / "data" / "drafts")
    assert cli.main(["plant", "--check"]) == 1
    assert cli.main(["plant"]) == 1
    assert _snapshot(tree / "data" / "drafts") == drafts


# EVAL-09 H9 (owner decision, 2026-11-11): a report file that cannot be written is listed as
# NOT WRITTEN in plain words, and plant carries on with the others.


def test_a_report_file_that_cannot_be_written_is_listed_and_the_others_are_written(tree, capsys):
    import os
    import stat

    sheet = _complete_sheet(tree / "data" / "specs" / "dataset.json")
    (tree / SHEET_FILE).write_text(sheet, encoding="utf-8")
    assert cli.main(["plant"]) == 0
    capsys.readouterr()
    reports = tree / "data" / "reports"
    locked = reports / "H-001.json"
    before = locked.read_bytes()
    other = reports / "H-002.json"
    other.unlink()  # so that its writing again is visible
    os.chmod(locked, stat.S_IREAD)
    try:
        assert cli.main(["plant"]) == 1
    finally:
        os.chmod(locked, stat.S_IREAD | stat.S_IWRITE)
    out = capsys.readouterr().out
    assert "Traceback" not in out
    assert (
        "H-001 NOT WRITTEN: data/reports/H-001.json cannot be written (Permission denied); "
        "the other reports are written. Make the file writable and run plant again."
    ) in out
    assert "H-002 built | 1 planted error(s)" in out
    assert other.is_file()
    assert locked.read_bytes() == before


# EVAL-10 K (owner decision, 2026-11-11): an [error] may name up to three other places, each a
# group: also_section with also_quote (unchanged) or with also_find and also_replace (changed
# too), or, for CBC, also_analyte alone. Lines: 1 block, 2 verified, 3 [error], 4-7 the
# required keys, 8 onwards the body.

SIZE_ERROR = "section: Synoptic summary\nfind: size: 18 mm\nreplace: size: 25 mm\n"
GROSS_LINE = "Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm across."
DIAG_LINE = "Invasive tumour of no special type, grade 2, 25 mm."


def _places(result) -> list[tuple[str, str]]:
    assert result.ok, result.problems
    return [
        (p["section"], p["quoted_sentence"]) for p in result.report["errors"][0]["other_places"]
    ]


def test_an_unchanged_and_a_changed_other_place_are_read_in_order(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        SIZE_ERROR
        + f"also_section: Gross description\nalso_quote: {GROSS_LINE}\n"
        + "also_section: Diagnosis\nalso_find: grade 2, 18 mm.\nalso_replace: grade 2, 25 mm.\n",
    )
    before = copy.deepcopy(histo_draft)
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert _places(result) == [("Gross description", GROSS_LINE), ("Diagnosis", DIAG_LINE)]
    assert result.report["sections"]["Diagnosis"] == DIAG_LINE
    assert result.report["sections"]["Gross description"] == GROSS_LINE  # unchanged
    assert result.report["errors"][0]["quoted_sentence"] == "Tumour size: 25 mm"
    assert histo_draft == before  # the draft itself is never changed


def test_the_changed_places_quote_is_the_whole_line_with_the_replacement(
    histo_draft, fixed_taxonomy
):
    body = "verified: no\n" + _error(
        "H3",
        "critical",
        "section: Diagnosis\nfind: grade 2, 18 mm.\nreplace: grade 2, 18 mm, pT3.\n"
        "quote: Invasive tumour of no special type, grade 2, 18 mm, pT3.\n"
        "also_section: Synoptic summary\nalso_find: pT: pT1c\nalso_replace: pT: pT3\n",
    )
    result = _apply(_row("H-001", planned=["H3"]), histo_draft, body, fixed_taxonomy)
    assert _places(result) == [("Synoptic summary", "pT: pT3")]


def test_a_cbc_other_place_is_an_analytes_rendered_line(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error("C2", "minor", "set: MCHC = 41.0\nalso_analyte: Hb\n")
    result = _apply(_row("C-001", planned=["C2"]), cbc_draft, body, fixed_taxonomy)
    hb_line = result.report["sections"]["Values"].split("\n")[0]
    assert hb_line.startswith("Hb")
    assert _places(result) == [("Values", hb_line)]


def test_three_other_places_are_allowed(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H1",
        "major",
        SIZE_ERROR
        + f"also_section: Gross description\nalso_quote: {GROSS_LINE}\n"
        + "also_section: Microscopic description\nalso_quote: Tumour measures 18 mm.\n"
        + "also_section: Diagnosis\nalso_quote: grade 2, 18 mm.\n",
    )
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert [s for s, _ in _places(result)] == [
        "Gross description",
        "Microscopic description",
        "Diagnosis",
    ]


def test_an_omission_may_name_an_other_place_in_any_section(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "H5",
        "minor",
        "kind: omission\nremove_from: Synoptic summary\nremove: Perineural invasion: Absent\n"
        "anchor: Lymphovascular invasion: Absent\n"
        "also_section: Microscopic description\nalso_quote: Margins are clear.\n",
    )
    result = _apply(_row("H-001", planned=["H5"]), histo_draft, body, fixed_taxonomy)
    assert _places(result) == [("Microscopic description", "Margins are clear.")]


def test_an_error_without_other_places_is_built_as_before(histo_draft, fixed_taxonomy):
    body = "verified: no\n" + _error("H1", "major", SIZE_ERROR)
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.ok and "other_places" not in result.report["errors"][0]


P = "[error] 1 (line 3): other place"


@pytest.mark.parametrize(
    ("extra", "problem"),
    [
        (
            "also_quote: Margins are clear.\n",
            "line 11: also_quote in [error] 1 (line 3) comes before any also_section line; an "
            "other place starts with also_section (or, for CBC, also_analyte)",
        ),
        (
            "also_section: Gross description\n",
            f"{P} 1 (line 11) needs also_quote, or also_find with also_replace, after also_section",
        ),
        (
            "also_section: Diagnosis\nalso_find: grade 2\n",
            f"{P} 1 (line 11) needs also_quote, or also_find with also_replace, after also_section",
        ),
        (
            "also_section: Diagnosis\nalso_quote: grade 2\nalso_find: grade 2\n"
            "also_replace: grade 3\n",
            f"{P} 1 (line 11) gives also_quote and also_find; give one of them (also_quote, or "
            "also_find with also_replace)",
        ),
        (
            "also_section: Diagnosis\nalso_quote: grade 2\nalso_quote: 18 mm\n",
            "line 13: 'also_quote' is given twice in other place 1 of [error] 1 (line 3)",
        ),
        ("also_analyte: Hb\n", f"{P} 1 (line 11): also_analyte applies only to CBC reports"),
        (
            "also_section: Comment section\nalso_quote: Invented comment.\n",
            f"{P} 1 (line 11): also_section 'Comment section' is not a section of this report "
            "(sections: Clinical details, Specimen, Gross description, Microscopic "
            "description, Immunohistochemistry, Diagnosis, Synoptic summary, Comment)",
        ),
        (
            "also_section: Synoptic summary\nalso_quote: Tumour size: 25 mm\n",
            f"{P} 1 (line 11) repeats the error's main place (the same section and sentence)",
        ),
        (
            "also_section: Gross description\nalso_quote: no such words\n",
            f"{P} 1 (line 11): the also_quote text occurs 0 times in 'Gross description' of the "
            "built report (it must occur exactly once); copy it exactly from the readable draft",
        ),
        (
            "also_section: Microscopic description\nalso_quote: umour\n",
            f"{P} 1 (line 11): the also_quote text occurs 2 times in 'Microscopic description' "
            "of the built report (it must occur exactly once); add surrounding words from the "
            "readable draft so that it is unique",
        ),
        (
            "also_section: Diagnosis\nalso_find: no such words\nalso_replace: other words\n",
            f"{P} 1 (line 11): the also_find text occurs 0 times in 'Diagnosis' (it must occur "
            "exactly once); copy it exactly from the readable draft",
        ),
        (
            "also_section: Microscopic description\nalso_find: umour\nalso_replace: esion\n",
            f"{P} 1 (line 11): the also_find text occurs 2 times in 'Microscopic description' "
            "(it must occur exactly once); add surrounding words from the readable draft so "
            "that it is unique",
        ),
    ],
)
def test_other_place_problems_are_said_in_plain_words(histo_draft, fixed_taxonomy, extra, problem):
    """The main change takes lines 8 to 10, so the group starts at line 11."""
    body = "verified: no\n" + _error("H1", "major", SIZE_ERROR + extra)
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert not result.ok
    assert result.problems == [problem]


def test_a_fourth_other_place_is_refused(histo_draft, fixed_taxonomy):
    groups = "".join(
        f"also_section: Gross description\nalso_quote: {words}\n"
        for words in ("Fatty tissue", "40 x 30", "firm lesion", "18 mm across")
    )
    body = "verified: no\n" + _error("H1", "major", SIZE_ERROR + groups)
    result = _apply(_row("H-001"), histo_draft, body, fixed_taxonomy)
    assert result.problems == [f"{P} 4 (line 17): an error names at most three other places"]


def test_an_unknown_analyte_and_an_analyte_with_other_keys_are_refused(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "C2",
        "minor",
        "set: MCHC = 41.0\nalso_analyte: Haemoglobin\nalso_analyte: Hb\nalso_quote: Hb\n",
    )
    result = _apply(_row("C-001", planned=["C2"]), cbc_draft, body, fixed_taxonomy)
    assert result.problems[0].startswith(
        f"{P} 1 (line 9): also_analyte 'Haemoglobin' is not an analyte; use the names in "
        "cbc_values ("
    )
    assert result.problems[1:] == [
        f"{P} 2 (line 10): also_analyte stands alone; also_quote does not belong with it"
    ]


def test_an_also_find_in_values_is_refused(cbc_draft, fixed_taxonomy):
    body = "verified: no\n" + _error(
        "C2", "minor", "set: MCHC = 41.0\nalso_section: Values\nalso_find: Hb\nalso_replace: Hgb\n"
    )
    result = _apply(_row("C-001", planned=["C2"]), cbc_draft, body, fixed_taxonomy)
    assert result.problems == [
        f"{P} 1 (line 9): the Values text is generated from cbc_values and cannot be edited; "
        "change a number with set lines in an [error] entry"
    ]


def test_other_places_build_deterministically_and_leave_the_drafts_alone(tree, capsys):
    sheet = GOOD_SHEET.replace(
        "replace: The tumour measures 25 mm across.\n",
        "replace: The tumour measures 25 mm across.\n"
        "also_section: Gross description\nalso_quote: firm lesion 18 mm across\n"
        "also_section: Diagnosis\nalso_find: grade 2, 18 mm.\nalso_replace: grade 2, 25 mm.\n",
    )
    assert sheet != GOOD_SHEET
    (tree / SHEET_FILE).write_text(sheet, encoding="utf-8")
    drafts = _snapshot(tree / "data" / "drafts")
    cli.main(["plant"])
    first = _snapshot(tree / "data" / "reports")
    cli.main(["plant"])
    assert _snapshot(tree / "data" / "reports") == first
    assert _snapshot(tree / "data" / "drafts") == drafts
    report = read_report_json(tree / "data" / "reports" / "H-001.json")
    assert report["errors"][0]["other_places"] == [
        {"section": "Gross description", "quoted_sentence": "firm lesion 18 mm across"},
        {"section": "Diagnosis", "quoted_sentence": DIAG_LINE},
    ]
    review = (tree / "data" / "reports" / "_review" / "H-001.md").read_text(encoding="utf-8")
    assert (
        "   other place 1: Gross description | firm lesion 18 mm across\n"
        f"   other place 2: Diagnosis | {DIAG_LINE}\n"
    ) in review


# EVAL-11 N (owner decision, 2026-11-12): the template header that `plant --init` writes lists
# the other-place lines of decision 56.


def test_the_template_header_lists_the_other_place_lines():
    header = plant.TEMPLATE_HEADER
    for key in ("also_section", "also_quote", "also_find", "also_replace", "also_analyte"):
        assert f"{key}" in header, key
    lines = [line for line in header.splitlines() if "also_" in line]
    assert all(line.startswith("#") for line in lines)  # comments only: the sheet stays empty
    assert "up to three" in header


def test_the_template_with_other_place_lines_still_checks_as_the_empty_template(tree, capsys):
    assert cli.main(["plant", "--init"]) == 0
    capsys.readouterr()
    assert cli.main(["plant", "--check"]) == 1
    out = capsys.readouterr().out
    assert not any(line.startswith("sheet ") for line in out.splitlines())
    assert "unknown key" not in out


# EVAL-14 AA (owner decision, 2026-11-12): the header's first line follows decision 64.

NEW_FIRST_LINE = (
    "# Planting sheet (decision 37, amended by decision 64). The owner chooses every planted "
    "error; candidate errors may be drafted by an AI assistant; the owner selects, reads and "
    "verifies them."
)


def test_the_template_header_first_line_follows_decision_64(tree, capsys):
    assert plant.TEMPLATE_HEADER.split("\n")[0] == NEW_FIRST_LINE
    assert cli.main(["plant", "--init"]) == 0
    assert (tree / SHEET_FILE).read_text(encoding="utf-8").split("\n")[0] == NEW_FIRST_LINE
    assert "Written by the owner only" not in plant.TEMPLATE_HEADER
