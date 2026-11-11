"""Evaluation harness (EVAL-04). Fake client and temporary trees only: never reads data/reports/,
data/drafts/ or the owner's prompt texts, and never constructs the real client with a key."""

import copy
import json
import math
import time
from datetime import UTC, datetime
from importlib.metadata import version
from types import SimpleNamespace

import pytest
from conftest import FIXTURES

from pathqc_eval import cli, harness
from pathqc_eval.draft import MissingAPIKeyError
from pathqc_eval.freeze import freeze
from pathqc_eval.harness import (
    BACKOFF_SECONDS,
    EVAL_MAX_TOKENS,
    EVAL_MODEL,
    AnthropicEvalClient,
    EvalResponse,
    FakeEvalClient,
    TransportError,
    eval_request_args,
    sha256_text,
)
from pathqc_eval.io import read_report_json, write_report_json

NOW = datetime(2026, 11, 16, 9, 30, 0, tzinfo=UTC)
RUN_ID = "20261116-093000-dev-plain"
EMPTY = '{"findings": []}'
DEV_PLAIN = ["--dataset", "dev", "--condition", "plain", "--workers", "1"]


def _finding(**overrides) -> dict:
    return {
        "quoted_sentence": "Tumour measures 25 mm.",
        "section": "Microscopic description",
        "category": "size mismatch",
        "severity": "major",
        "confidence": 0.8,
        "rationale": "Differs from the gross size.",
    } | overrides


def _report(template: dict, report_id: str, split: str, verified: bool = False) -> dict:
    data = copy.deepcopy(template)
    data["id"] = report_id
    data["split"] = split
    for i, err in enumerate(data["errors"], start=1):
        err["error_id"] = f"{report_id}-E{i}"
    if verified:
        data["provenance"] |= {"verified": True, "verified_at": "2026-11-14"}
    return data


@pytest.fixture
def sleeps(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(cli, "RUN_SLEEP", waits.append)
    return waits


@pytest.fixture
def tree(tmp_path, histo, cbc, real_prompts, monkeypatch, sleeps):
    """Two dev reports (H-001 planted, C-001 clean), one scored report (H-002), the fixture
    taxonomy, and the agent-written prompts with stand-in owner texts. The real client factory
    is replaced by one that fails the test if it is ever called."""
    root = tmp_path
    taxonomy = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    (root / "data").mkdir(parents=True, exist_ok=True)
    write_report_json(root / "data" / "taxonomy.json", taxonomy)
    reports = root / "data" / "reports"
    reports.mkdir(parents=True)
    write_report_json(reports / "H-001.json", _report(histo, "H-001", "dev"))
    write_report_json(reports / "C-001.json", _report(cbc, "C-001", "dev"))
    write_report_json(reports / "H-002.json", _report(histo, "H-002", "scored"))

    def refuse():
        raise AssertionError("a client was constructed although the test gave none")

    monkeypatch.setattr(cli, "RUN_ROOT", root)
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW)
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", refuse)
    return root


def _use(monkeypatch, client):
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", lambda: client)
    return client


def _run(*args: str) -> int:
    return cli.main(["run", *args])


def _calls(root, run_id=RUN_ID) -> list[dict]:
    path = root / "runs" / run_id / "calls.jsonl"
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]  # "\n" only, as written


def _results(root, run_id=RUN_ID) -> dict:
    return read_report_json(root / "runs" / run_id / "results.json")


def _which(user: str) -> str:
    return "C-001" if user.startswith("## Values") else "H-001"


# Units, attempts and the retry rule


def test_three_units_per_report_in_report_then_repeat_order(tree, monkeypatch):
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert [_which(user) for _, user, _ in client.calls] == ["C-001"] * 3 + ["H-001"] * 3
    assert all(max_tokens == EVAL_MAX_TOKENS for _, _, max_tokens in client.calls)
    units = _results(tree)["units"]
    assert [(u["report_id"], u["repeat"]) for u in units] == [
        ("C-001", 1), ("C-001", 2), ("C-001", 3), ("H-001", 1), ("H-001", 2), ("H-001", 3),
    ]  # fmt: skip
    assert {u["status"] for u in units} == {"valid"}


def test_attempt_two_after_an_unreadable_output(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient(["Sorry, here are my thoughts.", EMPTY] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    first = [line for line in _calls(tree) if line["report_id"] == "C-001" and line["repeat"] == 1]
    assert [(a["attempt"], a["parse_status"]) for a in first] == [(1, "invalid"), (2, "valid")]
    unit = _results(tree)["units"][0]
    assert (unit["status"], unit["attempts"]) == ("valid", 2)


def test_attempt_two_after_an_abnormal_stop_reason(tree, monkeypatch):
    truncated = EvalResponse(EMPTY, EVAL_MODEL, 100, 16000, "max_tokens")
    _use(monkeypatch, FakeEvalClient([truncated] + [EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    first = [line for line in _calls(tree) if line["repeat"] == 1 and line["report_id"] == "C-001"]
    assert [(a["attempt"], a["stop_reason"], a["parse_status"]) for a in first] == [
        (1, "max_tokens", "valid"),
        (2, "end_turn", "valid"),
    ]
    assert _results(tree)["units"][0]["status"] == "valid"


def test_invalid_after_two_bad_attempts(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient(["not json", '{"answer": 42}'] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    unit = _results(tree)["units"][0]
    assert (unit["status"], unit["attempts"], unit["findings"]) == ("invalid", 2, [])
    totals = _results(tree)["totals"]
    assert (totals["units"], totals["valid"], totals["invalid"], totals["calls"]) == (6, 5, 1, 7)


def test_transport_retries_are_not_attempts(tree, monkeypatch, sleeps):
    script = [
        TransportError("RateLimitError", "rate limited"),
        TransportError("APIConnectionError", "connection reset"),
        EMPTY,
    ] + [EMPTY] * 5
    _use(monkeypatch, FakeEvalClient(script))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    lines = _calls(tree)
    transport = [line for line in lines if "error_class" in line]
    assert [(t["report_id"], t["repeat"], t["error_class"]) for t in transport] == [
        ("C-001", 1, "RateLimitError"),
        ("C-001", 1, "APIConnectionError"),
    ]
    assert all(set(t) == {"run_id", "report_id", "condition", "repeat", "error_class",
                          "error_message"} for t in transport)  # fmt: skip
    attempts = [line for line in lines if "attempt" in line]
    assert len(attempts) == 6 and attempts[0]["attempt"] == 1
    assert sleeps == list(BACKOFF_SECONDS[:2])


def test_transport_failure_after_every_retry_stops_the_run(tree, monkeypatch, sleeps, capsys):
    _use(monkeypatch, FakeEvalClient([TransportError("InternalServerError", "500")] * 4))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert len(_calls(tree)) == 4 and all("error_class" in line for line in _calls(tree))
    assert sleeps == list(BACKOFF_SECONDS)
    assert _results(tree)["totals"]["pending"] == 6
    out = capsys.readouterr().out
    assert "stopped early: transport failures after every retry" in out


def test_a_refused_request_stops_the_run_and_is_logged(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([ValueError("400 invalid request: messages.0")]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    (line,) = _calls(tree)
    assert line | {"run_id": None} == {
        "run_id": None,
        "report_id": "C-001",
        "condition": "plain",
        "repeat": 1,
        "error_class": "ValueError",
        "error_message": "400 invalid request: messages.0",
        "fatal": True,
    }
    out = capsys.readouterr().out
    assert "FAIL C-001 repeat 1: ValueError: 400 invalid request: messages.0" in out


# Resume, gate and pieces


def test_resume_skips_finished_units(tree, monkeypatch):
    first = _use(monkeypatch, FakeEvalClient([EMPTY] * 2))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r1", "--max-calls", "2") == 0
    assert len(first.calls) == 2
    assert _results(tree, "r1")["totals"]["pending"] == 4
    second = _use(monkeypatch, FakeEvalClient([EMPTY] * 4))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r1") == 0
    assert [_which(user) for _, user, _ in second.calls] == ["C-001", "H-001", "H-001", "H-001"]
    totals = _results(tree, "r1")["totals"]
    assert (totals["valid"], totals["pending"], totals["calls"]) == (6, 0, 6)


def test_resume_continues_a_unit_with_attempt_two(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient(["not json"]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r2", "--max-calls", "1") == 0
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r2") == 0
    first = [a for a in _calls(tree, "r2") if a["report_id"] == "C-001" and a["repeat"] == 1]
    assert [a["attempt"] for a in first] == [1, 2]


def test_resume_refuses_a_changed_config(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r3") == 0
    (tree / "prompts" / "plain.md").write_text("A different plain prompt.\n", encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    capsys.readouterr()
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r3") == 1
    assert client.calls == []
    assert "runs/r3 exists with a different config (prompt_hash)" in capsys.readouterr().out


@pytest.mark.parametrize("workers", ["1", "4"])
def test_the_gate_stops_before_the_crossing_call(tree, monkeypatch, workers, capsys):
    # Each call costs 2,500 x $2 + 4,000 x $10 per million tokens = $0.045.
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "0.10"]
    assert _run(*args, "--workers", workers) == 1
    assert len(client.calls) == 2  # a third would reach $0.135
    totals = _results(tree)["totals"]
    assert totals["cost_usd"] == pytest.approx(0.09) and totals["cost_usd"] <= 0.10
    assert "stopped early: cost gate" in capsys.readouterr().out


def test_the_first_call_is_assumed_to_cost_six_cents(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.05") == 1
    assert client.calls == []
    assert "next call assumed $0.0600" in capsys.readouterr().out


def test_max_calls_stops_cleanly(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "3") == 0
    assert len(client.calls) == 3
    totals = _results(tree)["totals"]
    assert (totals["valid"], totals["pending"]) == (3, 3)
    assert "stopped early: --max-calls 3 reached" in capsys.readouterr().out


def test_a_failure_in_flight_is_not_hidden_by_max_calls(tree, monkeypatch, capsys):
    # Both calls are in flight when --max-calls stops scheduling; one of them is refused.
    _use(monkeypatch, FakeEvalClient([ValueError("400 invalid request"), EMPTY]))
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00"]
    assert _run(*args, "--workers", "4", "--max-calls", "2") == 1
    out = capsys.readouterr().out
    assert "stopped early: the API refused a call (ValueError); --max-calls 2 reached" in out


# What a run writes


def test_results_totals_and_ordering(tree, monkeypatch):
    finding = json.dumps({"findings": [_finding(), _finding(category="")]})
    script = [finding, "bad", "bad", EMPTY, EMPTY, EMPTY, EMPTY]
    _use(monkeypatch, FakeEvalClient(script, input_tokens=1000, output_tokens=2000))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    results = _results(tree)
    assert (results["run_id"], results["dataset"], results["condition"]) == (RUN_ID, "dev", "plain")
    first, second = results["units"][:2]
    assert first["findings"] == [_finding()] and first["dropped_count"] == 1
    assert (second["status"], second["attempts"], second["findings"]) == ("invalid", 2, [])
    per_call = 1000 * 2 / 1e6 + 2000 * 10 / 1e6
    assert results["totals"] == {
        "units": 6,
        "valid": 5,
        "invalid": 1,
        "pending": 0,
        "calls": 7,
        "input_tokens": 7000,
        "output_tokens": 14000,
        "cost_usd": round(7 * per_call, 6),
        "models_returned": [EVAL_MODEL],
    }


def _strings(value):
    """Every string inside a parsed JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_calls_lines_carry_hashes_and_no_request_text(tree, monkeypatch):
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    stored = [text for line in _calls(tree) for text in _strings(line)]
    for system, user, _ in client.calls:
        assert not any(system in text or user in text for text in stored)
        assert not any(text and text in system and len(text) > 40 for text in stored)
        # Review round 3: no line of either message (20 characters or more) is stored either.
        request_lines = [ln for ln in (system + "\n" + user).split("\n") if len(ln) >= 20]
        assert not any(ln in text for ln in request_lines for text in stored)
    line = _calls(tree)[0]
    system, user, _ = client.calls[0]
    assert (line["system_sha256"], line["user_sha256"]) == (sha256_text(system), sha256_text(user))
    assert set(line) == {
        "run_id", "report_id", "condition", "repeat", "attempt", "started_at", "duration_s",
        "model_requested", "model_returned", "system_sha256", "user_sha256", "raw_text",
        "stop_reason", "input_tokens", "output_tokens", "cost_usd", "parse_status", "findings",
        "dropped", "notes",
    }  # fmt: skip
    assert line["started_at"] == "2026-11-16T09:30:00Z"
    assert line["raw_text"] == EMPTY


def test_findings_are_read_leniently_and_the_raw_output_kept(tree, monkeypatch):
    text = (
        "```json\n" + json.dumps([_finding(severity="High", extra=1), {"section": "x"}]) + "\n```"
    )
    _use(monkeypatch, FakeEvalClient([text] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    line = _calls(tree)[0]
    assert line["raw_text"] == text
    assert line["findings"] == [_finding(severity=None)]
    assert line["dropped"] == [{"index": 2, "reason": "no usable quoted_sentence, category"}]
    assert "finding 1: extra keys ignored: extra" in line["notes"]


def test_config_records_the_settings(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.50") == 0
    config = read_report_json(tree / "runs" / RUN_ID / "config.json")
    assert config | {"dataset_hash": None, "prompt_hash": None, "taxonomy_hash": None} == {
        "run_id": RUN_ID,
        "dataset": "dev",
        "condition": "plain",
        "model": "claude-sonnet-5-5",
        "sampling": "default",
        "effort": "default",
        "max_tokens": 16000,
        "repeats": 3,
        "dataset_hash": None,
        "prompt_hash": None,
        "taxonomy_hash": None,
        "created_at": "2026-11-16T09:30:00Z",
        "cost_gate_usd": 1.5,
        "sdk_version": version("anthropic"),
        "lock_created_at": None,
    }
    assert all(len(config[k]) == 64 for k in ("dataset_hash", "prompt_hash", "taxonomy_hash"))


def test_unit_lines_and_totals_are_printed(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([json.dumps([_finding()])] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == (
        "C-001 repeat 1: valid | 1 finding(s) | 2500 in + 4000 out tokens | $0.0450 | "
        "running $0.0450"
    )
    assert out[-1] == (
        "totals: 6 units (6 valid, 0 invalid, 0 pending) | 6 calls | 15000 input + 24000 output "
        "tokens | $0.2700 | models returned: claude-sonnet-5-5"
    )


# Refusals before any call


def test_an_isolation_breach_refuses_before_any_call(tree, monkeypatch, capsys):
    (tree / "prompts" / "plain.md").write_text("Review the report. split: dev\n", encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert not (tree / "runs").exists()
    assert "system message contains the split 'dev'" in capsys.readouterr().out


def test_scored_refuses_without_a_lock(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run("--dataset", "scored", "--condition", "plain", "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert (
        "freeze --check: FAILED: data/prompts.lock.json does not exist" in capsys.readouterr().out
    )


@pytest.fixture
def frozen(tmp_path, histo, cbc, real_prompts, monkeypatch, sleeps):
    """A complete frozen tree: 34 verified reports, final taxonomy, approved prompts, a lock."""
    root = tmp_path
    taxonomy = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    (root / "data").mkdir(parents=True, exist_ok=True)
    write_report_json(root / "data" / "taxonomy.json", taxonomy | {"status": "final"})
    reports = root / "data" / "reports"
    reports.mkdir(parents=True)
    for i in range(1, 26):
        rid = f"H-{i:03d}"
        data = _report(histo, rid, "dev" if i <= 3 else "scored", verified=True)
        write_report_json(reports / f"{rid}.json", data)
    for i in range(1, 10):
        rid = f"C-{i:03d}"
        data = _report(cbc, rid, "dev" if i == 1 else "scored", verified=True)
        write_report_json(reports / f"{rid}.json", data)
    assert freeze(root, now=datetime(2026, 11, 15, 8, 0, tzinfo=UTC)).ok
    monkeypatch.setattr(cli, "RUN_ROOT", root)
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW)
    return root


def test_scored_refuses_with_a_lock_that_fails_the_check(frozen, monkeypatch, capsys):
    path = frozen / "data" / "reports" / "H-010.json"
    path.write_bytes(path.read_bytes() + b" ")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run("--dataset", "scored", "--condition", "plain", "--cost-gate", "9.00") == 1
    assert client.calls == []
    out = capsys.readouterr().out
    assert "freeze --check: FAILED: 1 file(s) differ" in out and "data/reports/H-010.json" in out


def test_scored_run_takes_its_hashes_from_the_lock(frozen, monkeypatch):
    client = _use(monkeypatch, FakeEvalClient(lambda system, user: EMPTY))
    args = ["--dataset", "scored", "--condition", "structured", "--cost-gate", "9.00"]
    assert _run(*args, "--workers", "4", "--run-id", "s1") == 0
    assert len(client.calls) == 30 * 3
    lock = read_report_json(frozen / "data" / "prompts.lock.json")
    config = read_report_json(frozen / "runs" / "s1" / "config.json")
    assert config["dataset_hash"] == lock["dataset"]["hash"]
    assert config["taxonomy_hash"] == lock["files"]["data/taxonomy.json"]
    assert config["lock_created_at"] == "2026-11-15T08:00:00Z"
    results = _results(frozen, "s1")
    assert [u["report_id"] for u in results["units"][:3]] == ["C-002"] * 3
    assert results["totals"]["valid"] == 90


def test_dev_refuses_without_dev_reports(tree, monkeypatch, capsys):
    for name in ("H-001.json", "C-001.json"):
        (tree / "data" / "reports" / name).unlink()
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--dry-run") == 1
    assert client.calls == []
    assert "no dev reports in data/reports/" in capsys.readouterr().out


def test_dev_refuses_a_report_that_fails_validation(tree, monkeypatch, capsys):
    path = tree / "data" / "reports" / "H-001.json"
    data = read_report_json(path)
    data["errors"][0]["quoted_sentence"] = "A sentence that is not in the report."
    write_report_json(path, data)
    assert _run(*DEV_PLAIN, "--dry-run") == 1
    out = capsys.readouterr().out
    assert "H-001.json: H-001-E1: quoted_sentence does not occur verbatim" in out


def test_structured_dev_refuses_a_placeholder(tree, monkeypatch, capsys):
    (tree / "prompts" / "structured_cbc.md").write_text("<<OWNER TEXT REQUIRED>>\n", "utf-8")
    assert _run("--dataset", "dev", "--condition", "structured", "--dry-run") == 1
    assert "prompts/structured_cbc.md still holds <<OWNER TEXT REQUIRED>>" in (
        capsys.readouterr().out
    )


def test_a_real_run_needs_a_cost_gate(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN) == 1
    assert client.calls == []
    assert "--cost-gate is required for a real run" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--cost-gate", "0"], "--cost-gate must be a positive number of US dollars"),
        (["--cost-gate", "-1"], "--cost-gate must be a positive number of US dollars"),
        (["--cost-gate", "nan"], "--cost-gate must be a positive number of US dollars"),
        (["--cost-gate", "inf"], "--cost-gate must be a positive number of US dollars"),
        (["--cost-gate", "1", "--workers", "0"], "--workers must be 1 or more"),
        (["--cost-gate", "1", "--max-calls", "0"], "--max-calls must be 1 or more"),
        (["--cost-gate", "1", "--run-id", "../escape"], "--run-id must be letters, digits"),
    ],
)
def test_bad_options_are_refused_before_any_call(tree, monkeypatch, capsys, extra, message):
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run("--dataset", "dev", "--condition", "plain", *extra) == 1
    assert client.calls == []
    assert message in capsys.readouterr().out
    assert not (tree / "runs").exists()


def test_dry_run_needs_no_cost_gate_and_no_client(tree, capsys):
    assert _run("--dataset", "dev", "--condition", "plain", "--dry-run") == 0
    out = capsys.readouterr().out
    assert out.startswith("DRY RUN: no client is constructed and no API call is made.\n")
    assert (
        "dataset dev | condition plain | 2 reports | 6 units (3 repeats each) | at most 12 "
        "calls (2 attempts per unit)"
    ) in out
    assert "===== H-001 system message (plain) =====" in out
    assert "===== C-001 user message =====\n## Values\n" in out
    # S8 (EVAL-04b): the smoke test's four plain calls averaged 1,167.5 input and 776.25 output
    # tokens; plus 50% and rounded up: 1,752 and 1,165. At $2 and $10 per million tokens:
    # 0.003504 + 0.01165 = $0.015154 a call; 6 calls $0.090924; 12 calls $0.181848.
    assert (
        "Estimate (a projection from the four calls of the S8 smoke test, plain condition: "
        "their average plus 50%): 1,752 input + 1,165 output tokens per call at Sonnet prices = "
        "$0.0152 per call; 6 calls (one per unit) = $0.0909; at most 12 calls = $0.1818"
    ) in out
    assert not (tree / "runs").exists()


# The real client, without a key and without a call


def test_real_request_arguments_hold_exactly_model_system_messages_max_tokens():
    args = eval_request_args(EVAL_MODEL, "SYSTEM", "USER", EVAL_MAX_TOKENS)
    assert args == {
        "model": "claude-sonnet-5-5",
        "max_tokens": 16000,
        "system": "SYSTEM",
        "messages": [{"role": "user", "content": "USER"}],
    }


@pytest.mark.parametrize("key", [None, ""])
def test_missing_key_error_names_the_variable_and_prints_no_value(monkeypatch, key):
    if key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    with pytest.raises(MissingAPIKeyError) as caught:
        AnthropicEvalClient()
    assert str(caught.value) == (
        "ANTHROPIC_API_KEY is not set; the owner adds it to .env before a real run"
    )


def test_cli_reports_a_missing_key_and_writes_nothing(tree, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", AnthropicEvalClient)
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert capsys.readouterr().out == (
        "FAIL ANTHROPIC_API_KEY is not set; the owner adds it to .env before a real run\n"
    )
    assert not (tree / "runs").exists()


def test_cost_is_finite_for_every_logged_call(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert all(math.isfinite(line["cost_usd"]) for line in _calls(tree))


def test_an_unpaired_surrogate_in_an_output_is_logged_not_fatal(tree, monkeypatch):
    item = _finding(quoted_sentence="Tumour \ud800 25 mm.")
    _use(monkeypatch, FakeEvalClient([json.dumps([item])] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    first = _calls(tree)[0]
    assert first["findings"][0]["quoted_sentence"] == "Tumour \ufffd 25 mm."
    assert _results(tree)["totals"]["valid"] == 6


def test_an_unpaired_surrogate_in_the_raw_output_is_replaced_and_noted(tree, monkeypatch):
    # The real API cannot send one, but the writer must never fail on a call's content.
    broken = EvalResponse("not json \ud800", EVAL_MODEL, 100, 100, "end_turn")
    refused = ValueError("400 bad \udfff request")
    _use(monkeypatch, FakeEvalClient([broken, EMPTY] + [EMPTY] * 5 + [refused]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    first = _calls(tree)[0]
    assert first["raw_text"] == "not json \ufffd"
    assert "raw_text held unpaired surrogates; replaced with U+FFFD" in first["notes"]
    _use(monkeypatch, FakeEvalClient([refused]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "r9") == 1
    assert _calls(tree, "r9")[0]["error_message"] == "400 bad \ufffd request"


# Review round 1 (S5): failures found by the reviewers


def test_an_interrupt_logs_every_call_in_flight_and_rebuilds_results(tree, monkeypatch, capsys):
    """Ctrl+C while calls are in flight: no new call starts, every call already made (and
    billed) is logged, results.json is rebuilt, and the exit code is 130."""
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    real = harness.parse_findings
    seen: list[str] = []

    def interrupted_on_the_second(text):
        seen.append(text)
        if len(seen) == 2:
            raise KeyboardInterrupt
        return real(text)

    monkeypatch.setattr(harness, "parse_findings", interrupted_on_the_second)
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00", "--workers", "4"]
    assert _run(*args) == 130
    attempts = [line for line in _calls(tree) if "attempt" in line]
    assert len(attempts) == len(client.calls) >= 2
    assert _results(tree)["totals"]["calls"] == len(client.calls)
    assert "interrupted" in capsys.readouterr().out


def test_a_log_write_failure_stops_the_run_and_still_logs_the_other_calls(
    tree, monkeypatch, capsys
):
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    real = harness.append_jsonl
    writes = [0]

    def flaky(path, record):
        writes[0] += 1
        if writes[0] == 2:
            raise PermissionError("the disk said no")
        real(path, record)

    monkeypatch.setattr(harness, "append_jsonl", flaky)
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00", "--workers", "4"]
    assert _run(*args) == 1
    attempts = [line for line in _calls(tree) if "attempt" in line]
    assert len(attempts) == len(client.calls) >= 2
    assert _results(tree)["totals"]["calls"] == len(client.calls)
    assert "FAIL" in capsys.readouterr().out


def test_two_report_files_with_the_same_id_are_refused(tree, monkeypatch, capsys):
    original = tree / "data" / "reports" / "H-001.json"
    (tree / "data" / "reports" / "H-001 - Copy.json").write_bytes(original.read_bytes())
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--dry-run") == 1
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert "report id H-001 is in both H-001 - Copy.json and H-001.json" in (
        capsys.readouterr().out
    )


def test_a_run_folder_with_calls_but_no_config_is_refused(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 3))
    structured = ["--dataset", "dev", "--condition", "structured", "--workers", "1"]
    assert _run(*structured, "--cost-gate", "1.00", "--run-id", "mix", "--max-calls", "3") == 0
    (tree / "runs" / "mix" / "config.json").unlink()
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "mix") == 1
    assert client.calls == []
    assert "runs/mix holds calls.jsonl but no config.json" in capsys.readouterr().out


def _append_line(root, line: dict, run_id: str = RUN_ID) -> None:
    with (root / "runs" / run_id / "calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")


def test_a_call_line_missing_fields_is_refused_cleanly(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    stub = {"run_id": RUN_ID, "report_id": "C-001", "condition": "plain", "repeat": 2}
    _append_line(tree, stub | {"attempt": 1})
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert "line 2 is not a call line this run can read" in capsys.readouterr().out


def test_a_call_line_of_another_condition_is_refused(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    _append_line(tree, _calls(tree)[0] | {"repeat": 2, "condition": "structured"})
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert f"line 2 is from run '{RUN_ID}', condition 'structured'" in capsys.readouterr().out


class _StubResponse:
    """What the SDK's status errors read from a response (no HTTP library needed)."""

    def __init__(self, status: int, headers: dict | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self.request = None


@pytest.mark.parametrize(
    ("status", "headers", "transport"),
    [
        (408, None, True),
        (429, None, True),
        (500, None, True),
        (529, None, True),
        (429, {"x-should-retry": "false"}, True),
        (503, {"x-should-retry": "false"}, True),
        (409, None, False),
        (400, None, False),
        (404, None, False),
        (400, {"x-should-retry": "true"}, False),
    ],
)
def test_rate_limits_server_errors_and_timeouts_are_transport_failures(status, headers, transport):
    """Stage step 4 (review round 2): a rate limit (429), a server error (5xx) and a timeout
    (408) are transport failures whatever the x-should-retry header says; no other status is.
    No client is constructed: the call goes to a stub."""
    import anthropic

    error = anthropic.APIStatusError(
        f"Error code: {status}", response=_StubResponse(status, headers), body=None
    )

    def create(**kwargs):
        raise error

    if transport:
        with pytest.raises(TransportError) as caught:
            harness.call_messages_api(create, anthropic, EVAL_MODEL, "S", "U", 100)
        assert caught.value.error_class == "APIStatusError"
    else:
        with pytest.raises(anthropic.APIStatusError):
            harness.call_messages_api(create, anthropic, EVAL_MODEL, "S", "U", 100)


def test_connection_errors_and_timeouts_are_transport_failures():
    import anthropic

    for error in (anthropic.APIConnectionError(request=None), anthropic.APITimeoutError(None)):

        def create(error=error, **kwargs):
            raise error

        with pytest.raises(TransportError) as caught:
            harness.call_messages_api(create, anthropic, EVAL_MODEL, "S", "U", 100)
        assert caught.value.error_class == type(error).__name__


def test_the_api_call_sends_exactly_the_built_arguments_and_joins_the_text_blocks():
    import anthropic

    sent: list[dict] = []
    message = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text='{"findings"'),
            SimpleNamespace(type="tool_use", id="x"),
            SimpleNamespace(type="text", text=": []}"),
        ],
        model="claude-sonnet-5-5-20261101",
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        stop_reason="end_turn",
    )

    def create(**kwargs):
        sent.append(kwargs)
        return message

    response = harness.call_messages_api(
        create, anthropic, EVAL_MODEL, "SYSTEM", "USER", EVAL_MAX_TOKENS
    )
    assert sent == [
        {
            "model": "claude-sonnet-5-5",
            "max_tokens": 16000,
            "system": "SYSTEM",
            "messages": [{"role": "user", "content": "USER"}],
        }
    ]
    assert response == EvalResponse(
        '{"findings": []}', "claude-sonnet-5-5-20261101", 11, 7, "end_turn"
    )


@pytest.mark.parametrize("run_id", ["NUL", "con", "Aux.txt", "COM1", "lpt9.json", "r1."])
def test_run_ids_windows_cannot_create_are_refused(tree, monkeypatch, capsys, run_id):
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", run_id) == 1
    assert client.calls == []
    assert "--run-id must be" in capsys.readouterr().out
    assert not (tree / "runs").exists()


@pytest.mark.parametrize(
    ("name", "condition"),
    [
        ("plain.md", "plain"),
        ("structured_output.md", "structured"),
        ("structured_histopathology.md", "structured"),
    ],
)
def test_a_prompt_file_that_is_not_utf8_is_refused_naming_it(tree, capsys, name, condition):
    path = tree / "prompts" / name
    path.write_bytes(path.read_text(encoding="utf-8").encode("utf-16"))
    assert _run("--dataset", "dev", "--condition", condition, "--dry-run") == 1
    out = capsys.readouterr().out
    assert out.startswith("run refused:")
    assert f"prompts/{name} is not UTF-8 text; save it as UTF-8" in out


def test_the_gate_is_shown_as_given(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.185") == 1  # four calls of $0.045 fit
    out = capsys.readouterr().out
    assert "gate $0.185" in out and "the next call could cross $0.185" in out


# Review round 1 (S5): tests that would have passed with the feature broken


def test_the_gate_counts_the_spend_of_earlier_invocations(tree, monkeypatch):
    """4 calls of $0.045 = $0.18 in the first invocation; on resume with the same $0.20 gate
    no call may start: 0.18 + 0.045 > 0.20."""
    _use(monkeypatch, FakeEvalClient([EMPTY] * 4))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.20", "--run-id", "g", "--max-calls", "4") == 0
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 2))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.20", "--run-id", "g") == 1
    assert client.calls == []


def test_the_next_call_is_assumed_to_cost_as_much_as_the_dearest_so_far(tree, monkeypatch):
    """Call 1 costs $0.10, call 2 $0.01. Before call 3 the run assumes $0.10: 0.11 + 0.10 =
    0.21 > 0.20 stops it, where the last call's $0.01 would have let it start."""
    dear = EvalResponse(EMPTY, EVAL_MODEL, 0, 10000, "end_turn")
    cheap = EvalResponse(EMPTY, EVAL_MODEL, 0, 1000, "end_turn")
    client = _use(monkeypatch, FakeEvalClient([dear] + [cheap] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.20") == 1
    assert len(client.calls) == 2


def _attempt_line(report_id: str, repeat: int) -> dict:
    return {
        "run_id": "r", "report_id": report_id, "condition": "plain", "repeat": repeat,
        "attempt": 1, "started_at": "2026-11-16T09:30:00Z", "duration_s": 0.0,
        "model_requested": EVAL_MODEL, "model_returned": EVAL_MODEL, "system_sha256": "s",
        "user_sha256": "u", "raw_text": EMPTY, "stop_reason": "end_turn", "input_tokens": 1,
        "output_tokens": 1, "cost_usd": 0.0, "parse_status": "valid", "findings": [],
        "dropped": [], "notes": [],
    }  # fmt: skip


def test_results_are_in_report_then_repeat_order_whatever_the_completion_order():
    completion = [("H-001", 3), ("C-001", 2), ("H-001", 1), ("C-001", 3), ("H-001", 2)]
    attempts = {key: [_attempt_line(*key)] for key in completion}
    results = harness.build_results("r", "dev", "plain", ["H-001", "C-001"], attempts)
    assert [(u["report_id"], u["repeat"], u["status"]) for u in results["units"]] == [
        ("C-001", 1, "pending"), ("C-001", 2, "valid"), ("C-001", 3, "valid"),
        ("H-001", 1, "valid"), ("H-001", 2, "valid"), ("H-001", 3, "valid"),
    ]  # fmt: skip


@pytest.mark.parametrize(
    "name", ["structured_output.md", "structured_histopathology.md", "structured_cbc.md"]
)
def test_resume_refuses_after_any_structured_prompt_file_changed(tree, monkeypatch, capsys, name):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    args = ["--dataset", "dev", "--condition", "structured", "--workers", "1"]
    args += ["--cost-gate", "1.00", "--run-id", "s"]
    assert _run(*args) == 0
    path = tree / "prompts" / name
    path.write_text(path.read_text(encoding="utf-8") + "One more line.\n", encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    capsys.readouterr()
    assert _run(*args) == 1
    assert client.calls == []
    assert "runs/s exists with a different config (prompt_hash)" in capsys.readouterr().out


@pytest.mark.parametrize("field", ["cost_gate_usd", "taxonomy_hash", "dataset_hash"])
def test_resume_refuses_each_changed_setting(tree, monkeypatch, capsys, field):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "h") == 0
    gate = "1.00"
    if field == "cost_gate_usd":
        gate = "2.00"
    elif field == "taxonomy_hash":
        path = tree / "data" / "taxonomy.json"
        write_report_json(path, read_report_json(path) | {"version": "0.1-changed"})
    else:
        path = tree / "data" / "reports" / "C-001.json"
        path.write_bytes(path.read_bytes() + b" ")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    capsys.readouterr()
    assert _run(*DEV_PLAIN, "--cost-gate", gate, "--run-id", "h") == 1
    assert client.calls == []
    assert f"runs/h exists with a different config ({field})" in capsys.readouterr().out


def test_the_raw_output_is_kept_in_full(tree, monkeypatch):
    long = json.dumps({"findings": [_finding(rationale="x" * 60000)]})
    _use(monkeypatch, FakeEvalClient([long] + [EMPTY] * 5))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert _calls(tree)[0]["raw_text"] == long


def test_an_identical_copy_of_a_call_line_is_read_once_and_a_different_one_refused(tmp_path):
    """An interrupt between writing a line and noting it was written can write it twice."""
    path = tmp_path / "calls.jsonl"
    line = _attempt_line("C-001", 1)
    path.write_text(json.dumps(line) + "\n" + json.dumps(line) + "\n", encoding="utf-8")
    assert harness.read_attempts(path, "r", "plain") == {("C-001", 1): [line]}
    other = line | {"raw_text": "something else"}
    path.write_text(json.dumps(line) + "\n" + json.dumps(other) + "\n", encoding="utf-8")
    with pytest.raises(harness.CallsFileError, match="two different lines for C-001 repeat 1"):
        harness.read_attempts(path, "r", "plain")


# Review round 2 (S5)


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"findings": [_finding(rationale="one line separator")]}),
        "not json   at all",
        "not json \u0085 either",
    ],
)
def test_unicode_line_separators_in_an_output_keep_calls_jsonl_readable(tree, monkeypatch, text):
    """U+2028, U+2029 and U+0085 are written as they are; calls.jsonl is read line by line at
    newlines only, so the run finishes, results.json is written and the run can be resumed."""
    _use(monkeypatch, FakeEvalClient([text] + [EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert _results(tree)["totals"]["valid"] == 6
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert client.calls == []


@pytest.mark.parametrize(
    ("name", "condition"),
    [("structured_histopathology.md", "structured"), ("plain.md", "plain")],
)
def test_a_prompt_file_in_utf16_without_a_byte_order_mark_is_refused(tree, capsys, name, condition):
    """UTF-16 without a BOM decodes as UTF-8 with a NUL after every character."""
    path = tree / "prompts" / name
    path.write_bytes(path.read_text(encoding="utf-8").encode("utf-16-le"))
    assert _run("--dataset", "dev", "--condition", condition, "--dry-run") == 1
    assert f"prompts/{name} is not UTF-8 text; save it as UTF-8" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("field", "value"),
    [("cost_usd", "0.045"), ("attempt", "2"), ("input_tokens", "2500"), ("repeat", "2")],
)
def test_a_call_line_with_a_number_written_as_text_is_refused(
    tree, monkeypatch, capsys, field, value
):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    _append_line(tree, _calls(tree)[0] | {"repeat": 2} | {field: value})
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert "line 2 is not a call line this run can read" in capsys.readouterr().out


def test_a_call_line_of_another_run_id_is_refused(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    _append_line(tree, _calls(tree)[0] | {"repeat": 2, "run_id": "some-other-run"})
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert client.calls == []
    assert "line 2 is from run 'some-other-run', condition 'plain'" in capsys.readouterr().out


def test_a_failure_line_missing_fields_is_refused_before_the_client_is_built(
    tree, monkeypatch, capsys
):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    _append_line(tree, {"report_id": "C-001", "condition": "plain", "repeat": 2,
                        "error_class": "X", "error_message": "y"})  # fmt: skip
    built: list[int] = []
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", lambda: built.append(1) or FakeEvalClient([]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert built == []
    assert "line 2 is not a call line this run can read" in capsys.readouterr().out


def _staggered():
    """A script whose first call returns at once and whose later calls take half a second,
    so that calls are still running when the first one is recorded."""
    order = iter(range(1000))

    def script(system, user):
        time.sleep(0 if next(order) == 0 else 0.5)
        return EMPTY

    return script


def test_an_interrupt_starts_no_new_call_and_logs_the_calls_still_running(tree, monkeypatch):
    client = _use(monkeypatch, FakeEvalClient(_staggered()))
    real = harness.parse_findings
    seen: list[str] = []

    def interrupted_on_the_first(text):
        seen.append(text)
        if len(seen) == 1:
            raise KeyboardInterrupt
        return real(text)

    monkeypatch.setattr(harness, "parse_findings", interrupted_on_the_first)
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00", "--workers", "4"]
    assert _run(*args) == 130
    assert len(client.calls) == 4  # the four started together; none after the interrupt
    assert len([line for line in _calls(tree) if "attempt" in line]) == 4
    assert _results(tree)["totals"]["calls"] == 4


def test_an_interrupt_while_a_call_is_being_started_loses_no_call(tree, monkeypatch):
    """The clock is read before a call is started, so an interrupt there starts no call."""
    client = _use(monkeypatch, FakeEvalClient(_staggered()))
    ticks = [0]

    def clock():
        ticks[0] += 1  # 1: the config's created_at; 2: call 1; 3: call 2
        if ticks[0] == 3:
            raise KeyboardInterrupt
        return NOW

    monkeypatch.setattr(cli, "RUN_CLOCK", clock)
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00", "--workers", "4"]
    assert _run(*args) == 130
    attempts = [line for line in _calls(tree) if "attempt" in line]
    assert len(attempts) == len(client.calls) == 1


def test_a_second_interrupt_abandons_the_calls_in_flight_and_still_rebuilds_results(
    tree, monkeypatch, capsys
):
    _use(monkeypatch, FakeEvalClient(_staggered()))
    real = harness.parse_findings
    seen: list[str] = []

    def interrupted_on_the_first(text):
        seen.append(text)
        if len(seen) == 1:
            raise KeyboardInterrupt
        return real(text)

    def out(text):
        if text.startswith("stopping"):
            raise KeyboardInterrupt  # Ctrl+C pressed again
        print(text)

    monkeypatch.setattr(harness, "parse_findings", interrupted_on_the_first)
    monkeypatch.setitem(harness.run_units.__kwdefaults__, "out", out)
    args = ["--dataset", "dev", "--condition", "plain", "--cost-gate", "1.00", "--workers", "4"]
    assert _run(*args) == 130
    logged = tree / "runs" / RUN_ID / "calls.jsonl"  # absent when nothing could be logged
    calls = [line for line in _calls(tree) if "attempt" in line] if logged.exists() else []
    assert _results(tree)["totals"]["calls"] == len(calls)
    assert "results.json was rebuilt" in capsys.readouterr().out


def test_a_log_write_failure_starts_no_new_call(tree, monkeypatch, capsys):
    """With one worker: call 1 is logged, logging call 2 fails, call 2 is logged on the retry,
    and no third call starts."""
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    real = harness.append_jsonl
    writes = [0]

    def flaky(path, record):
        writes[0] += 1
        if writes[0] == 2:
            raise PermissionError("the disk said no")
        real(path, record)

    monkeypatch.setattr(harness, "append_jsonl", flaky)
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert len(client.calls) == 2
    assert len([line for line in _calls(tree) if "attempt" in line]) == 2


def test_a_write_that_fails_part_way_leaves_no_fragment(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    real = harness.append_jsonl
    writes = [0]

    def half_then_fail(path, record):
        writes[0] += 1
        if writes[0] == 2:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line[: len(line) // 2])
            raise OSError(28, "No space left on device")
        real(path, record)

    monkeypatch.setattr(harness, "append_jsonl", half_then_fail)
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert len(_calls(tree)) == 2  # every line whole: the fragment was cut off
    monkeypatch.setattr(harness, "append_jsonl", real)
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert _results(tree)["totals"]["valid"] == 6


def test_a_second_invocation_on_a_run_that_is_going_is_refused(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    with harness.run_lock(tree / "runs" / "busy"):
        assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "busy") == 1
    assert client.calls == []
    assert "runs/busy is being run by another invocation" in capsys.readouterr().out
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "busy") == 0  # free again


def test_the_real_client_sends_system_and_user_in_their_places():
    """complete() over a stub: the instance is made without __init__, so no key is read and
    no SDK client is built."""
    import anthropic

    sent: list[dict] = []
    message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=EMPTY)],
        model=EVAL_MODEL,
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason="end_turn",
    )

    def create(**kwargs):
        sent.append(kwargs)
        return message

    client = object.__new__(AnthropicEvalClient)
    client.model = EVAL_MODEL
    client._errors = anthropic
    client._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    assert client.complete("SYSTEM", "USER", 123).text == EMPTY
    assert sent == [
        {
            "model": EVAL_MODEL,
            "max_tokens": 123,
            "system": "SYSTEM",
            "messages": [{"role": "user", "content": "USER"}],
        }
    ]


def test_a_report_id_in_two_files_of_different_splits_is_refused(tree, capsys):
    data = read_report_json(tree / "data" / "reports" / "H-001.json") | {"split": "scored"}
    write_report_json(tree / "data" / "reports" / "H-001.json.bak.json", data)
    assert _run(*DEV_PLAIN, "--dry-run") == 1
    assert "report id H-001 is in both H-001.json and H-001.json.bak.json" in (
        capsys.readouterr().out
    )


@pytest.mark.parametrize(
    ("amount", "shown"),
    [(1.0, "$1.00"), (0.185, "$0.185"), (1000.005, "$1000.005"), (12345.678, "$12345.678")],
)
def test_amounts_are_shown_to_the_cent_or_as_given(amount, shown):
    assert harness.usd(amount) == shown


def test_a_prompt_file_in_a_windows_code_page_is_refused(tree, capsys):
    """Invalid UTF-8 without any NUL (Windows-1252 'é' is the byte 0xE9)."""
    (tree / "prompts" / "plain.md").write_bytes("Review the report. Café.\n".encode("cp1252"))
    assert _run("--dataset", "dev", "--condition", "plain", "--dry-run") == 1
    assert "prompts/plain.md is not UTF-8 text; save it as UTF-8" in capsys.readouterr().out


# Review round 3 (S5)


def test_a_run_another_invocation_creates_meanwhile_is_compared_under_the_lock(
    tree, monkeypatch, capsys
):
    """Invocation B finds no config.json; while B builds its client, invocation A creates the
    run with a $0.10 gate. Under the lock B compares the config again and refuses."""
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "0.10", "--run-id", "other", "--max-calls", "1") == 0
    other = read_report_json(tree / "runs" / "other" / "config.json")
    client = FakeEvalClient([EMPTY] * 6)

    def factory():  # A, between B's checks and B's lock
        (tree / "runs" / "race").mkdir(parents=True)
        write_report_json(tree / "runs" / "race" / "config.json", other | {"run_id": "race"})
        return client

    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", factory)
    capsys.readouterr()
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "race") == 1
    assert client.calls == []
    assert "runs/race exists with a different config (cost_gate_usd)" in capsys.readouterr().out


def test_a_held_lock_is_reported_before_the_run_files_are_read(tree, monkeypatch, capsys):
    """While another invocation holds the run and is mid-way through writing a line, a second
    one says the run is busy (not that calls.jsonl is damaged) and builds no client."""
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "1") == 0
    path = tree / "runs" / RUN_ID / "calls.jsonl"
    half = json.dumps(_calls(tree)[0] | {"repeat": 2})
    built: list[int] = []
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", lambda: built.append(1) or FakeEvalClient([]))
    with harness.run_lock(tree / "runs" / RUN_ID):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(half[: len(half) // 2])
        capsys.readouterr()
        assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    assert built == []
    assert f"runs/{RUN_ID} is being run by another invocation" in capsys.readouterr().out


def test_a_calls_file_without_a_final_newline_is_continued_cleanly(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 2))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--max-calls", "2") == 0
    path = tree / "runs" / RUN_ID / "calls.jsonl"
    path.write_bytes(path.read_bytes().rstrip(b"\n"))  # an editor that drops the last newline
    _use(monkeypatch, FakeEvalClient([EMPTY] * 4))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert len(_calls(tree)) == 6
    assert _results(tree)["totals"]["valid"] == 6


def test_an_interrupt_after_results_were_written_says_they_were(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY] * 6))

    def out(text):
        if text.startswith("totals:"):
            raise KeyboardInterrupt
        print(text)

    monkeypatch.setitem(harness.run_units.__kwdefaults__, "out", out)
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 130
    assert _results(tree)["totals"]["valid"] == 6
    assert "results.json was rebuilt" in capsys.readouterr().out


def test_an_interrupt_with_results_json_unwritable_says_it_was_not_rebuilt(
    tree, monkeypatch, capsys
):
    _use(monkeypatch, FakeEvalClient(_staggered()))
    (tree / "runs" / RUN_ID / "results.json").mkdir(parents=True)  # cannot be written
    real = harness.parse_findings
    seen: list[str] = []

    def interrupted_on_the_first(text):
        seen.append(text)
        if len(seen) == 1:
            raise KeyboardInterrupt
        return real(text)

    monkeypatch.setattr(harness, "parse_findings", interrupted_on_the_first)
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 130
    assert "results.json was not rebuilt" in capsys.readouterr().out


HOLD_LOCK = """
import sys
from pathlib import Path
from pathqc_eval.harness import run_lock
with run_lock(Path(sys.argv[1])):
    print("locked", flush=True)
    sys.stdin.read()
"""


def test_a_lock_held_by_another_process_refuses_the_run(tree, monkeypatch, capsys):
    import subprocess
    import sys

    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_LOCK, str(tree / "runs" / "held")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    try:
        assert holder.stdout.readline().strip() == "locked"
        assert _run(*DEV_PLAIN, "--cost-gate", "1.00", "--run-id", "held") == 1
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
    assert client.calls == []
    assert "runs/held is being run by another invocation" in capsys.readouterr().out


def test_the_run_holds_its_lock_while_calls_are_made(tree, monkeypatch):
    held: list[bool] = []

    def script(system, user):
        try:
            with harness.run_lock(tree / "runs" / RUN_ID):
                held.append(False)
        except harness.RunInUse:
            held.append(True)
        return EMPTY

    _use(monkeypatch, FakeEvalClient(script))
    assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 0
    assert held == [True] * 6


@pytest.mark.parametrize(("status", "transport"), [(502, True), (599, True), (600, False)])
def test_server_errors_are_the_5xx_statuses(status, transport):
    assert harness.is_transport_status(status) is transport


@pytest.mark.parametrize("kind", ["folder", "read-only file"])
def test_a_lock_file_that_cannot_be_used_is_refused_in_plain_words(tree, monkeypatch, capsys, kind):
    import os
    import stat

    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 6))
    lock = tree / "runs" / RUN_ID / ".run.lock"
    lock.parent.mkdir(parents=True)
    if kind == "folder":
        lock.mkdir()
    else:
        lock.write_bytes(b"")
        os.chmod(lock, stat.S_IREAD)
    try:
        assert _run(*DEV_PLAIN, "--cost-gate", "1.00") == 1
    finally:
        if kind != "folder":
            os.chmod(lock, stat.S_IREAD | stat.S_IWRITE)
    assert client.calls == []
    assert f"runs/{RUN_ID}/.run.lock cannot be used" in capsys.readouterr().out


def test_a_call_is_priced_at_the_dearer_of_the_model_requested_and_returned():
    """S8 (EVAL-04b) review: the gate must never under-count, for `run` and `smoke` alike."""
    from pathqc_eval.cost import cost_usd

    sonnet = EvalResponse(EMPTY, "claude-sonnet-5-5", 1000, 1000, "end_turn")
    haiku = EvalResponse(EMPTY, "claude-haiku-5-5", 1000, 1000, "end_turn")
    unknown = EvalResponse(EMPTY, "claude-unknown-1", 1000, 1000, "end_turn")
    dear = cost_usd("claude-sonnet-5-5", 1000, 1000)
    assert harness._cost(sonnet, "claude-haiku-5-5") == dear  # returned is dearer
    assert harness._cost(haiku, "claude-sonnet-5-5") == dear  # requested is dearer
    assert harness._cost(unknown, "claude-sonnet-5-5") == dear  # unknown: as requested
