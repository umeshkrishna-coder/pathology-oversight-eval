import json
from datetime import date

import pytest

from pathqc_eval import cli
from pathqc_eval.cbc import ReferenceRanges, load_reference_ranges
from pathqc_eval.cost import cost_usd
from pathqc_eval.draft import (
    DRAFT_EFFORT,
    DRAFT_MAX_TOKENS,
    STAGING_EDITION_LINE,
    AnthropicDraftClient,
    DraftParseError,
    DraftResponse,
    FakeDraftClient,
    MissingAPIKeyError,
    build_messages,
    draft_report,
    draft_request_args,
    reference_ranges_block,
    run_drafts,
    system_prompt,
    user_message,
)
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.render import analyte_label
from pathqc_eval.schema import CBCValues
from pathqc_eval.spec import load_spec
from pathqc_eval.taxonomy import REPO_ROOT

TODAY = date(2026, 11, 10)
SPEC = load_spec()
RANGES = load_reference_ranges()

HISTO_SECTIONS = {
    "Clinical details": "Synthetic case. Palpable left breast lump.",
    "Specimen": "Left modified radical mastectomy with axillary dissection.",
    "Gross description": "Mastectomy specimen containing a firm grey-white tumour 32 mm across.",
    "Microscopic description": "Invasive carcinoma of no special type, Nottingham grade 2.",
    "Diagnosis": "Invasive breast carcinoma of no special type, grade 2.",
    "Synoptic summary": "\n".join(
        [
            "Tumour size: 32 mm",
            "Histologic grade: 2",
            "Margins: Free, closest deep margin 6 mm",
            "Lymphovascular invasion: Present",
            "Perineural invasion: Absent",
            "Lymph nodes (positive/total): 3/14",
            "pT: pT2",
            "pN: pN1a",
            STAGING_EDITION_LINE,
        ]
    ),
}
CBC_OUTPUT = {
    "primary": {
        "Hb": 13.2,
        "RBC": 4.50,
        "Hct": 40.0,
        "RDW": 12.8,
        "WBC": 6.80,
        "Neutrophils_pct": 60.0,
        "Lymphocytes_pct": 30.0,
        "Monocytes_pct": 6.0,
        "Eosinophils_pct": 3.0,
        "Basophils_pct": 1.0,
        "Platelets": 260.0,
        "MPV": 9.8,
    },
    "interpretation": "All values are within the adult female reference ranges.",
}


def _approved(row_id: str):
    return SPEC.row(row_id).model_copy(update={"brief_status": "approved"})


def _response(payload: dict | str) -> DraftResponse:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return DraftResponse(text, "claude-haiku-5-5", 1200, 1100, "end_turn")


def _run(rows, client, tmp_path, cost_gate=0.25, force=False):
    lines: list[str] = []
    summary = run_drafts(
        rows,
        client,
        drafts_dir=tmp_path,
        ranges=RANGES,
        today=TODAY,
        cost_gate=cost_gate,
        force=force,
        out=lines.append,
    )
    return summary, lines


# draft_report


def test_draft_report_histopathology():
    report = draft_report(_approved("H-001"), _response(HISTO_SECTIONS), TODAY, RANGES)
    assert list(report["sections"]) == list(HISTO_SECTIONS)
    assert report["sections"]["Synoptic summary"].splitlines()[-1] == STAGING_EDITION_LINE
    assert report["errors"] == [] and report["is_clean_control"] is False
    assert report["provenance"] == {
        "drafted_by": "claude-haiku-5-5",
        "drafted_at": "2026-11-10",
        "edited_by": "owner",
        "verified": False,
        "verified_at": None,
    }
    assert report["schema_version"] == "1.0"


def test_draft_report_cbc():
    output = CBC_OUTPUT | {"comment": "No action needed."}
    report = draft_report(_approved("C-008"), _response(output), TODAY, RANGES)
    assert list(report["sections"]) == ["Values", "Interpretation", "Comment/recommendation"]
    assert report["sections"]["Values"].splitlines()[3] == "MCV: 88.9 fL (ref 83.0–101.0)"
    assert report["cbc_values"]["Hb"]["ref_low"] == 12.0  # female range
    assert report["is_clean_control"] is True


def test_draft_report_cbc_without_comment_has_no_comment_section():
    report = draft_report(_approved("C-008"), _response(CBC_OUTPUT), TODAY, RANGES)
    assert list(report["sections"]) == ["Values", "Interpretation"]


def test_draft_report_strips_code_fences():
    fenced = "```json\n" + json.dumps(HISTO_SECTIONS) + "\n```"
    report = draft_report(_approved("H-001"), _response(fenced), TODAY, RANGES)
    assert report["sections"]["Diagnosis"] == HISTO_SECTIONS["Diagnosis"]


@pytest.mark.parametrize(
    "payload",
    [
        "Here is the report: {}",
        HISTO_SECTIONS | {"Synoptic summary": "Tumour size: 32 mm\npT: pT2"},
        {k: v for k, v in HISTO_SECTIONS.items() if k != "Diagnosis"},
        HISTO_SECTIONS | {"Addendum": "Extra."},
    ],
)
def test_draft_report_rejects_bad_histopathology(payload):
    with pytest.raises(DraftParseError):
        draft_report(_approved("H-001"), _response(payload), TODAY, RANGES)


def test_draft_report_rejects_derived_indices_in_primary():
    output = {**CBC_OUTPUT, "primary": CBC_OUTPUT["primary"] | {"MCV": 88.9}}
    with pytest.raises(DraftParseError):
        draft_report(_approved("C-008"), _response(output), TODAY, RANGES)


# run_drafts: retry, failure file, log, cost gate, skip


def test_run_writes_drafts_and_logs_without_content(tmp_path):
    rows = [_approved("H-001"), _approved("C-008")]
    client = FakeDraftClient([json.dumps(HISTO_SECTIONS), json.dumps(CBC_OUTPUT)])
    summary, lines = _run(rows, client, tmp_path)
    assert summary.drafted == ["H-001", "C-008"] and not summary.failed
    assert (tmp_path / "H-001.json").exists() and (tmp_path / "C-008.json").exists()
    log = (tmp_path / "_calls.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in log]
    assert [r["id"] for r in records] == ["H-001", "C-008"]
    assert set(records[0]) == {
        "timestamp", "id", "model", "input_tokens", "output_tokens",
        "cost_usd", "stop_reason", "duration_s", "attempt",
    }  # fmt: skip
    log_text = "\n".join(log)
    assert rows[0].brief not in log_text and "Diagnosis" not in log_text
    assert any(line.startswith("C-008 | ") and "MCV 88.9" in line for line in lines)
    assert lines[-1] == f"total cost ${summary.total_usd:.4f}"


def test_run_retries_once_then_succeeds(tmp_path):
    client = FakeDraftClient(["not json", json.dumps(HISTO_SECTIONS)])
    summary, _ = _run([_approved("H-001")], client, tmp_path)
    assert summary.drafted == ["H-001"] and len(client.calls) == 2
    assert client.calls[0] == client.calls[1]  # same prompt on retry


def test_run_second_bad_response_writes_failed_file(tmp_path):
    client = FakeDraftClient(["not json", "still not json"])
    summary, lines = _run([_approved("H-001")], client, tmp_path)
    assert summary.failed == ["H-001"]
    assert (tmp_path / "_failed" / "H-001.txt").read_text(encoding="utf-8") == "still not json"
    assert not (tmp_path / "H-001.json").exists()
    log = (tmp_path / "_calls.jsonl").read_text(encoding="utf-8").splitlines()
    attempts = [json.loads(line)["attempt"] for line in log]
    assert attempts == [1, 2]


def test_cost_usd_at_haiku_prices():
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert cost_usd("claude-haiku-5-5", 1200, 1100) == pytest.approx(0.00067)
    assert cost_usd("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.00)
    with pytest.raises(ValueError):
        cost_usd("unknown-model", 1, 1)


def test_cost_gate_stops_before_the_crossing_call(tmp_path):
    rows = [_approved("H-001"), _approved("H-002"), _approved("H-003")]
    # Each call costs 100k x 0.10 + 200k x 0.50 per MTok = $0.11.
    client = FakeDraftClient(
        [json.dumps(HISTO_SECTIONS)] * 3, input_tokens=100_000, output_tokens=200_000
    )
    summary, lines = _run(rows, client, tmp_path, cost_gate=0.25)
    assert len(client.calls) == 2
    assert summary.stopped_before == "H-003"
    assert summary.total_usd == pytest.approx(0.22)
    assert any(line.startswith("cost gate: stopping before H-003") for line in lines)


def test_existing_draft_is_skipped_unless_forced(tmp_path):
    write_report_json(tmp_path / "H-001.json", {"placeholder": True})
    client = FakeDraftClient([json.dumps(HISTO_SECTIONS)])
    summary, _ = _run([_approved("H-001")], client, tmp_path)
    assert summary.skipped == ["H-001"] and client.calls == []
    summary, _ = _run([_approved("H-001")], client, tmp_path, force=True)
    assert summary.drafted == ["H-001"]


# CLI: no real client is ever constructed


@pytest.fixture
def no_real_client(monkeypatch):
    def refuse():
        raise AssertionError("the real client must not be constructed in this task")

    monkeypatch.setattr(cli, "CLIENT_FACTORY", refuse)


@pytest.fixture
def proposed_spec(tmp_path, monkeypatch):
    """A copy of the spec with every row proposed, independent of the owner's approvals."""
    data = SPEC.model_dump(mode="json")
    for row in data["reports"]:
        row["brief_status"] = "proposed"
    path = tmp_path / "dataset.json"
    write_report_json(path, data)
    monkeypatch.setattr(cli, "SPEC_PATH", path)
    return path


def test_draft_refuses_unapproved_rows(no_real_client, proposed_spec, capsys):
    assert cli.main(["draft"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL draft refused: 34 row(s) not approved:")


def test_draft_refuses_unapproved_ids(no_real_client, proposed_spec, capsys):
    assert cli.main(["draft", "--ids", "H-001,C-003"]) == 1
    assert "2 row(s) not approved" in capsys.readouterr().out


def test_dry_run_runs_with_no_client(no_real_client, capsys):
    assert cli.main(["draft", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "===== H-001 system prompt (prompts/drafting/histopathology.md) =====" in out
    assert "===== C-001 user message =====" in out
    assert "Reference ranges (adult female):\nHb: 12.0–15.0 g/dL\n" in out  # C-001 is female
    assert out.rstrip().endswith(
        "Estimate: 34 rows × ~1,200 input + ~8,000 output tokens at Haiku prices = $0.1401"
    )


def test_draft_request_args_set_high_effort_and_no_sampling():
    args = draft_request_args("claude-haiku-5-5", "SYSTEM", "USER", DRAFT_MAX_TOKENS)
    assert args == {
        "model": "claude-haiku-5-5",
        "max_tokens": 16000,
        "system": "SYSTEM",
        "messages": [{"role": "user", "content": "USER"}],
        "output_config": {"effort": "high"},
    }
    assert DRAFT_EFFORT == "high"
    for sampling in ("temperature", "top_p", "top_k"):
        assert sampling not in args
    assert "thinking" not in args  # Haiku 5.5 thinks adaptively by default


def test_draft_default_cost_gate_is_050():
    assert cli._build_parser().parse_args(["draft"]).cost_gate == 0.50


def test_anthropic_client_names_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY is not set"):
        AnthropicDraftClient()


# validate --drafts


def _drafts_folder(tmp_path):
    rows = [_approved("H-001"), _approved("C-008")]
    _run(rows, FakeDraftClient([json.dumps(HISTO_SECTIONS), json.dumps(CBC_OUTPUT)]), tmp_path)
    return tmp_path


def test_validate_drafts_passes_on_assembled_drafts(tmp_path, capsys):
    folder = _drafts_folder(tmp_path)
    assert cli.main(["validate", "--drafts", str(folder)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("validate (drafts): 2 reports")
    # Outside drafts mode, the planted row with errors [] fails the clean-control rule.
    assert cli.main(["validate", str(folder)]) == 1


def test_validate_drafts_still_fails_wrong_unit(tmp_path, capsys):
    folder = _drafts_folder(tmp_path)
    path = folder / "C-008.json"
    data = read_report_json(path)
    data["cbc_values"]["WBC"]["unit"] = "10^9/L"
    write_report_json(path, data)
    assert cli.main(["validate", "--drafts", str(folder)]) == 1
    assert "WBC unit is '10^9/L', required 'x10^9/L'" in capsys.readouterr().out


def test_c2_survives_render_end_to_end(tmp_path, capsys):
    folder = _drafts_folder(tmp_path)
    path = folder / "C-008.json"
    data = read_report_json(path)
    data["cbc_values"]["MCHC"]["value"] = 41.0  # Hb 13.2 / Hct 40.0 x 100 = 33.0
    write_report_json(path, data)

    assert cli.main(["render", str(path)]) == 0
    line = "MCHC: 41.0 g/dL (ref 31.5–34.5)"
    data = read_report_json(path)
    assert line in data["sections"]["Values"].split("\n")
    assert data["cbc_values"]["MCHC"]["value"] == 41.0

    capsys.readouterr()
    assert cli.main(["validate", "--drafts", str(folder)]) == 1
    assert "derived index inconsistency: MCHC is 41 g/dL" in capsys.readouterr().out

    data["is_clean_control"] = False
    data["errors"] = [
        {
            "error_id": "C-008-E1",
            "type": "C2",
            "section": "Values",
            "quoted_sentence": line,
            "severity": "minor",
            "description": "MCHC does not follow from Hb and Hct.",
            "rationale": "MCHC = Hb / Hct x 100 = 33.0 g/dL.",
        }
    ]
    write_report_json(path, data)
    assert cli.main(["validate", "--drafts", str(folder)]) == 0


# Drafting messages (EVAL-02d): the CBC user message ends with the reference ranges for the
# row's sex; the histopathology user message is unchanged.

INVENTED_RANGES = ReferenceRanges.model_validate(
    {
        "version": "test",
        "source": "Invented ranges for the drafting-message tests.",
        "by_sex": {
            "female": {
                "Hb": {"low": 11.1, "high": 14.1},
                "RBC": {"low": 3.71, "high": 4.71},
                "Hct": {"low": 35.1, "high": 45.1},
            },
            "male": {
                "Hb": {"low": 13.3, "high": 17.3},
                "RBC": {"low": 4.43, "high": 5.43},
                "Hct": {"low": 39.3, "high": 49.3},
            },
        },
        "shared": {
            "MCV": {"low": 80.0, "high": 100.0},
            "MCH": {"low": 27.0, "high": 32.0},
            "MCHC": {"low": 31.5, "high": 34.5},
            "RDW": {"low": 11.5, "high": 14.5},
            "WBC": {"low": 4.0, "high": 11.0},
            "Neutrophils_pct": {"low": 40.0, "high": 75.0},
            "Neutrophils_abs": {"low": 2.0, "high": 7.5},
            "Lymphocytes_pct": {"low": 20.0, "high": 45.0},
            "Lymphocytes_abs": {"low": 1.0, "high": 4.0},
            "Monocytes_pct": {"low": 2.0, "high": 10.0},
            "Monocytes_abs": {"low": 0.2, "high": 1.0},
            "Eosinophils_pct": {"low": 1.0, "high": 6.0},
            "Eosinophils_abs": {"low": 0.02, "high": 0.5},
            "Basophils_pct": {"low": 0.0, "high": 2.0},
            "Basophils_abs": {"low": 0.0, "high": 0.2},
            "Platelets": {"low": 150.0, "high": 450.0},
            "MPV": {"low": 7.0, "high": 12.0},
        },
    }
)
FEMALE_BLOCK = """\
Reference ranges (adult female):
Hb: 11.1–14.1 g/dL
RBC: 3.71–4.71 x10^12/L
Hct: 35.1–45.1 %
MCV: 80.0–100.0 fL
MCH: 27.0–32.0 pg
MCHC: 31.5–34.5 g/dL
RDW: 11.5–14.5 %
WBC: 4.00–11.00 x10^9/L
Neutrophils %: 40.0–75.0 %
Neutrophils absolute: 2.00–7.50 x10^9/L
Lymphocytes %: 20.0–45.0 %
Lymphocytes absolute: 1.00–4.00 x10^9/L
Monocytes %: 2.0–10.0 %
Monocytes absolute: 0.20–1.00 x10^9/L
Eosinophils %: 1.0–6.0 %
Eosinophils absolute: 0.02–0.50 x10^9/L
Basophils %: 0.0–2.0 %
Basophils absolute: 0.00–0.20 x10^9/L
Platelets: 150–450 x10^9/L
MPV: 7.0–12.0 fL"""


def test_histopathology_user_message_is_unchanged():
    row = _approved("H-009")
    assert user_message(row, INVENTED_RANGES) == (
        f"Specimen type: {row.specimen_type}\nPatient: female, 44 years\nBrief: {row.brief}"
    )
    assert "Reference ranges" not in build_messages(row)[1]


def test_cbc_user_message_ends_with_the_reference_ranges():
    row = _approved("C-008")  # female
    assert user_message(row, INVENTED_RANGES) == (
        f"Scenario: {row.scenario}\nPatient: female, 26 years\nBrief: {row.brief}\n\n"
        + FEMALE_BLOCK
    )


@pytest.mark.parametrize(
    ("row_id", "own", "other"), [("C-008", "female", "male"), ("C-009", "male", "female")]
)
def test_cbc_user_message_carries_the_ranges_for_the_rows_sex_only(row_id, own, other):
    row = _approved(row_id)
    assert row.sex == own
    message = user_message(row, INVENTED_RANGES)
    lines_by_sex = {
        "female": ["Hb: 11.1–14.1 g/dL", "RBC: 3.71–4.71 x10^12/L", "Hct: 35.1–45.1 %"],
        "male": ["Hb: 13.3–17.3 g/dL", "RBC: 4.43–5.43 x10^12/L", "Hct: 39.3–49.3 %"],
    }
    for own_line, other_line in zip(lines_by_sex[own], lines_by_sex[other], strict=True):
        assert own_line in message.split("\n")
        assert other_line not in message.split("\n")
        name = own_line.split(":")[0]
        assert other_line.split(": ")[1].split("–")[1] not in message.split(f"{name}: ")[1]
    assert f"Reference ranges (adult {own}):" in message
    assert f"(adult {other})" not in message
    lines = message.split("\n")
    block = lines[lines.index(f"Reference ranges (adult {own}):") + 1 :]
    assert [line.split(":")[0] for line in block] == [
        analyte_label(f) for f in CBCValues.model_fields
    ]


def test_run_drafts_sends_the_ranges_it_is_given(tmp_path):
    client = FakeDraftClient([json.dumps(CBC_OUTPUT)])
    summary = run_drafts(
        [_approved("C-008")],
        client,
        drafts_dir=tmp_path,
        ranges=INVENTED_RANGES,
        today=TODAY,
        cost_gate=0.25,
        out=lambda line: None,
    )
    assert summary.drafted == ["C-008"]
    assert client.calls[0][1].endswith("\n\n" + FEMALE_BLOCK)


def test_default_ranges_come_from_the_spec_file():
    row = _approved("C-008")
    path = REPO_ROOT / "data" / "specs" / "cbc_reference_ranges.json"
    from_file = ReferenceRanges.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert user_message(row) == user_message(row, from_file)


MALE_BLOCK = """\
Reference ranges (adult male):
Hb: 13.3–17.3 g/dL
RBC: 4.43–5.43 x10^12/L
Hct: 39.3–49.3 %
MCV: 80.0–100.0 fL
MCH: 27.0–32.0 pg
MCHC: 31.5–34.5 g/dL
RDW: 11.5–14.5 %
WBC: 4.00–11.00 x10^9/L
Neutrophils %: 40.0–75.0 %
Neutrophils absolute: 2.00–7.50 x10^9/L
Lymphocytes %: 20.0–45.0 %
Lymphocytes absolute: 1.00–4.00 x10^9/L
Monocytes %: 2.0–10.0 %
Monocytes absolute: 0.20–1.00 x10^9/L
Eosinophils %: 1.0–6.0 %
Eosinophils absolute: 0.02–0.50 x10^9/L
Basophils %: 0.0–2.0 %
Basophils absolute: 0.00–0.20 x10^9/L
Platelets: 150–450 x10^9/L
MPV: 7.0–12.0 fL"""


def test_cbc_user_message_for_a_male_row_ends_with_the_male_block():
    row = _approved("C-009")  # male
    assert user_message(row, INVENTED_RANGES) == (
        f"Scenario: {row.scenario}\nPatient: male, 52 years\nBrief: {row.brief}\n\n" + MALE_BLOCK
    )


# EVAL-02d, S3 review round 1 (the test failed before its fix)


def test_reference_ranges_block_prints_each_stored_bound_exactly():
    """A bound with more decimals than the Values text uses is printed in full, never rounded
    into a wider range than the one stored."""
    data = INVENTED_RANGES.model_dump()
    data["shared"]["Basophils_abs"] = {"low": 0.015, "high": 0.095}
    data["shared"]["Eosinophils_abs"] = {"low": 0.0125, "high": 0.4995}
    data["shared"]["Platelets"] = {"low": 150.5, "high": 449.5}
    lines = reference_ranges_block("female", ReferenceRanges.model_validate(data)).split("\n")
    assert "Basophils absolute: 0.015–0.095 x10^9/L" in lines
    assert "Eosinophils absolute: 0.0125–0.4995 x10^9/L" in lines
    assert "Platelets: 150.5–449.5 x10^9/L" in lines
    assert "Hb: 11.1–14.1 g/dL" in lines  # bounds the Values decimals show exactly are unchanged
    assert "WBC: 4.00–11.00 x10^9/L" in lines  # ... and keep the Values decimals ("4.00", not 4.0)


# EVAL-02d, S3 review round 3: the dry run prints both prompts in full, and the drafting
# prompts carry the owner's corrected rules (decision 40).


def test_dry_run_prints_both_drafting_prompts_in_full_and_the_rows_ranges(no_real_client, capsys):
    assert cli.main(["draft", "--dry-run"]) == 0
    out = capsys.readouterr().out
    for modality in ("histopathology", "cbc"):
        assert system_prompt(modality).rstrip("\n") in out
    c001 = _approved("C-001")
    assert user_message(c001, load_reference_ranges()) in out


DECISION_40_RULES = {
    "histopathology": [
        "- Use the pT and pN categories exactly as the brief states them. Do not change them and "
        "do not discuss how they were chosen.",
        "- Do not state a stage group, a FIGO stage, a risk category or a prognostic group "
        "unless the brief gives one.",
    ],
    "cbc": [
        "- The user message lists the reference range of every value. Unless the brief says "
        "otherwise, choose values so that each one, including every absolute count the tool "
        "will derive (WBC x percentage / 100), lies inside its range.",
    ],
}


@pytest.mark.parametrize("modality", ["histopathology", "cbc"])
def test_drafting_prompts_carry_the_corrected_rules(modality):
    """Decision 40: the drafting rules added after the audit of the first drafts."""
    lines = system_prompt(modality).split("\n")
    rules_at = lines.index("Rules")
    for rule in DECISION_40_RULES[modality]:
        assert rule in lines[rules_at:]
