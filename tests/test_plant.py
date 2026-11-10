"""Planting sheet tool (EVAL-02c): parser, apply rules, determinism and commands.

Temporary folders and invented reports and sheets only; never reads data/drafts/,
data/reports/ or data/specs/planting.md.
"""

import copy
import json
from textwrap import dedent

import pytest
from conftest import FIXTURES, fixture_text, rerender

from pathqc_eval import cli
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.plant import (
    SHEET_FILE,
    apply_block,
    parse_sheet,
    plan,
    readable_markdown,
    remove_span,
)
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
        "validation: H-001-E1: section 'Final diagnosis' is not in the report"
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
