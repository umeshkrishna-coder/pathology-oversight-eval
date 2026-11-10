"""Message assembly for the evaluated model (EVAL-03 step 2)."""

import pytest
from conftest import STAND_IN_OWNER_TEXT, fixture_text, write_prompts

from pathqc_eval.prompting import (
    build_eval_messages,
    read_prompt,
    render_report_text,
    taxonomy_block,
)
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues, Report

PLAIN = "STAND-IN PLAIN PROMPT."
OUTPUT = "STAND-IN OUTPUT BLOCK."


@pytest.fixture
def stand_in_prompts(tmp_path):
    return write_prompts(tmp_path / "prompts", PLAIN + "\n", OUTPUT + "\n")


def test_render_report_text_golden(histo):
    expected = fixture_text("report_text_histopathology.txt").rstrip("\n")
    assert render_report_text(Report.model_validate(histo)) == expected


def test_render_report_text_cbc(cbc):
    values = render_cbc_values(CBCValues.model_validate(cbc["cbc_values"]))
    assert render_report_text(Report.model_validate(cbc)) == (
        f"## Values\n{values}\n\n"
        "## Interpretation\nAll values within reference ranges.\n\n"
        "## Comment/recommendation\nNo action needed."
    )


def test_render_report_text_follows_stored_order(histo):
    histo["sections"] = dict(reversed(list(histo["sections"].items())))
    text = render_report_text(Report.model_validate(histo))
    assert text.startswith("## Synoptic summary\n")
    assert text.endswith("## Clinical details\nSynthetic test case. Lump noted on examination.")


def test_render_report_text_holds_nothing_but_sections(histo):
    text = render_report_text(Report.model_validate(histo))
    for leaked in ("H-001", "dev", "histopathology", "H1", "is_clean_control", "provenance"):
        assert leaked not in text
    assert histo["errors"][0]["description"] not in text


@pytest.mark.parametrize("modality", ["histopathology", "cbc"])
def test_taxonomy_block_golden(fixed_taxonomy, modality):
    expected = fixture_text(f"taxonomy_block_{modality}.txt").rstrip("\n")
    assert taxonomy_block(fixed_taxonomy, modality) == expected


def test_taxonomy_block_is_deterministic(fixed_taxonomy):
    assert taxonomy_block(fixed_taxonomy, "cbc") == taxonomy_block(fixed_taxonomy, "cbc")


@pytest.mark.parametrize("name", ["histo", "cbc"])
def test_plain_assembly(request, name, fixed_taxonomy, stand_in_prompts):
    report = Report.model_validate(request.getfixturevalue(name))
    system, user = build_eval_messages(report, "plain", fixed_taxonomy, stand_in_prompts)
    assert system == PLAIN
    assert user == render_report_text(report)


@pytest.mark.parametrize("name", ["histo", "cbc"])
def test_structured_assembly(request, name, fixed_taxonomy, stand_in_prompts):
    report = Report.model_validate(request.getfixturevalue(name))
    system, user = build_eval_messages(report, "structured", fixed_taxonomy, stand_in_prompts)
    block = fixture_text(f"taxonomy_block_{report.modality}.txt").rstrip("\n")
    assert system == (
        f"{STAND_IN_OWNER_TEXT[report.modality]}\n\n## Error taxonomy\n{block}\n\n{OUTPUT}"
    )
    assert user == render_report_text(report)


@pytest.mark.parametrize("name", ["histo", "cbc"])
def test_user_message_identical_in_both_conditions(request, name, fixed_taxonomy, real_prompts):
    report = Report.model_validate(request.getfixturevalue(name))
    _, plain_user = build_eval_messages(report, "plain", fixed_taxonomy, real_prompts)
    _, structured_user = build_eval_messages(report, "structured", fixed_taxonomy, real_prompts)
    assert plain_user == structured_user


def test_prompt_crlf_is_normalised(tmp_path, histo, fixed_taxonomy):
    folder = write_prompts(tmp_path / "prompts", "Line one.\r\nLine two.\r\n", OUTPUT)
    system, _ = build_eval_messages(Report.model_validate(histo), "plain", fixed_taxonomy, folder)
    assert system == "Line one.\nLine two."
    assert read_prompt(folder / "plain.md") == "Line one.\nLine two."


def test_unknown_condition_raises(histo, fixed_taxonomy, stand_in_prompts):
    with pytest.raises(ValueError, match="unknown condition"):
        build_eval_messages(Report.model_validate(histo), "other", fixed_taxonomy, stand_in_prompts)
