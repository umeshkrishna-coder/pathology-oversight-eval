import json
from datetime import date

import pytest

from pathqc_eval import cli
from pathqc_eval.cbc import load_reference_ranges
from pathqc_eval.cost import cost_usd
from pathqc_eval.draft import (
    STAGING_EDITION_LINE,
    AnthropicDraftClient,
    DraftParseError,
    DraftResponse,
    FakeDraftClient,
    MissingAPIKeyError,
    draft_report,
    run_drafts,
)
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.spec import load_spec

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
    assert out.rstrip().endswith(
        "Estimate: 34 rows × ~1,200 input + ~1,100 output tokens at Haiku prices = $0.0228"
    )


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
