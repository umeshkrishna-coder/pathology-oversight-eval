"""`pathqc-eval smoke` (EVAL-04b): the live smoke test's command, with the fake client in a
temporary tree. Never reads the repository's data/drafts/ and never builds the real client."""

import copy
import hashlib
import json
import math
from datetime import UTC, datetime

import pytest
from conftest import FIXTURES

from pathqc_eval import cli
from pathqc_eval.cost import cost_usd
from pathqc_eval.harness import EVAL_MAX_TOKENS, EVAL_MODEL, FakeEvalClient, TransportError
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.schema import SmokeConfig

NOW = datetime(2026, 11, 16, 9, 30, 0, tzinfo=UTC)
RUN_ID = "smoke-20261116-093000"
EMPTY = '{"findings": []}'
PURPOSE = "smoke test; not evaluation data"


def _draft(template: dict, report_id: str, split: str) -> dict:
    data = copy.deepcopy(template)
    data["id"] = report_id
    data["split"] = split
    data["errors"] = []
    data["is_clean_control"] = True
    return data


@pytest.fixture
def sleeps(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(cli, "RUN_SLEEP", waits.append)
    return waits


@pytest.fixture
def tree(tmp_path, histo, cbc, real_prompts, monkeypatch, sleeps):
    """Drafts H-021 to H-024 and C-011 (dev) and H-001 (scored), the fixture taxonomy and the
    agent-written prompts with stand-in owner texts. The real client factory fails the test."""
    root = tmp_path
    taxonomy = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    drafts = root / "data" / "drafts"
    drafts.mkdir(parents=True)
    write_report_json(root / "data" / "taxonomy.json", taxonomy)
    for rid, template, split in (("H-021", histo, "dev"), ("H-022", histo, "dev"),
                                 ("H-023", histo, "dev"), ("H-024", histo, "dev"),
                                 ("C-011", cbc, "dev"), ("H-001", histo, "scored")):  # fmt: skip
        write_report_json(drafts / f"{rid}.json", _draft(template, rid, split))

    def refuse():
        raise AssertionError("a client was constructed although the test gave none")

    monkeypatch.setattr(cli, "RUN_ROOT", root)
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW)
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", refuse)
    return root


def _use(monkeypatch, client):
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", lambda: client)
    return client


def _smoke(*args: str) -> int:
    return cli.main(["smoke", *args])


def _data_state(root) -> dict:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "data").rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--ids", "H-001", "--cost-gate", "1.00"],
         "H-001 is a scored report; the smoke test uses dev drafts only"),
        (["--ids", "H-021", "--cost-gate", "1.00", "--condition", "structured"],
         "the smoke test runs the plain condition only"),
        (["--ids", "H-021"], "--cost-gate is required for the smoke test"),
        (["--ids", "H-021", "--cost-gate", "0"], "--cost-gate must be a positive number"),
        (["--ids", "H-021", "--cost-gate", "nan"], "--cost-gate must be a positive number"),
        (["--ids", "H-021,H-021", "--cost-gate", "1.00"], "--ids names a report twice"),
        (["--ids", "X-1", "--cost-gate", "1.00"], "'X-1' is not a report id"),
        (["--ids", ",", "--cost-gate", "1.00"], "--ids names no report"),
        (["--ids", "H-099", "--cost-gate", "1.00"], "data/drafts/H-099.json cannot be read"),
    ],
)  # fmt: skip
def test_refusals_come_before_any_client_or_file(tree, capsys, args, message):
    before = _data_state(tree)
    assert _smoke(*args) == 1
    out = capsys.readouterr().out
    assert out.startswith("smoke refused:") and message in out
    assert not (tree / "runs").exists()
    assert _data_state(tree) == before


def test_a_smoke_run_writes_config_calls_and_results_and_nothing_under_data(
    tree, monkeypatch, capsys
):
    before = _data_state(tree)
    client = _use(monkeypatch, FakeEvalClient([EMPTY, EMPTY]))
    assert _smoke("--ids", "H-021,C-011", "--cost-gate", "1.00") == 0
    folder = tree / "runs" / RUN_ID
    config = SmokeConfig.model_validate(read_report_json(folder / "config.json"))
    assert config.purpose == PURPOSE and config.report_ids == ["H-021", "C-011"]
    assert (config.condition, config.model, config.max_tokens) == ("plain", EVAL_MODEL, 16000)
    assert (config.max_calls, config.transport_retries) == (4, 0)
    assert config.cost_gate_usd == 1.0
    calls = [json.loads(x) for x in (folder / "calls.jsonl").read_text("utf-8").split("\n") if x]
    assert [(c["report_id"], c["repeat"], c["attempt"]) for c in calls] == [
        ("C-011", 1, 1), ("H-021", 1, 1),
    ]  # fmt: skip
    results = read_report_json(folder / "results.json")
    assert [(u["report_id"], u["repeat"], u["status"]) for u in results["units"]] == [
        ("C-011", 1, "valid"), ("H-021", 1, "valid"),
    ]  # fmt: skip
    assert all(max_tokens == EVAL_MAX_TOKENS for _, _, max_tokens in client.calls)
    assert _data_state(tree) == before  # the drafts are read in memory; nothing under data/
    out = capsys.readouterr().out
    requests = [line for line in out.splitlines() if line.startswith("request ")]
    assert [line.split(":")[0] for line in requests] == ["request H-021", "request C-011"]
    for line in requests:  # the request arguments, with the texts replaced by their lengths
        shape = json.loads(line.split(": ", 1)[1])
        assert set(shape) == {"model", "system", "messages", "max_tokens"}
        assert shape["model"] == EVAL_MODEL and shape["max_tokens"] == EVAL_MAX_TOKENS
        assert shape["system"].endswith(" characters>")
        assert shape["messages"][0]["role"] == "user"
        assert shape["messages"][0]["content"].endswith(" characters>")
    system, user, _ = client.calls[0]
    assert system not in out and user not in out


def test_transport_failures_are_not_retried(tree, monkeypatch, capsys, sleeps):
    """Section B caps the calls; a transport retry would be another call."""
    _use(monkeypatch, FakeEvalClient([TransportError("RateLimitError", "rate limited")]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    calls = (tree / "runs" / RUN_ID / "calls.jsonl").read_text("utf-8").split("\n")
    assert len([x for x in calls if x]) == 1 and "RateLimitError" in calls[0]
    assert sleeps == []
    assert "could not be reached (1 tries)" in capsys.readouterr().out


def test_every_call_is_assumed_to_cost_its_ceiling(tree, monkeypatch, capsys):
    """The ceiling (the texts' UTF-8 bytes plus 100 tokens of input, 16,000 output tokens, at
    Sonnet prices) is above $0.10: no gate below it lets a call start."""
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 4))
    assert _smoke("--ids", "H-021", "--cost-gate", "0.10") == 1
    assert client.calls == []
    out = capsys.readouterr().out
    assert "stopped early: cost gate" in out
    config = read_report_json(tree / "runs" / RUN_ID / "config.json")
    ceiling = config["assumed_call_usd"]
    assert ceiling >= cost_usd(EVAL_MODEL, 0, EVAL_MAX_TOKENS) > 0.10


def test_the_gate_admits_a_call_only_while_its_ceiling_fits(tree, monkeypatch, capsys):
    """A call starts only if the spend so far plus the ceiling C fits under the gate. Each
    fake call costs p = 2,500 x $2 + 4,000 x $10 per million = $0.045. With a gate of
    C + p + 0.001: the first call (0 + C) and the second (p + C) start; the third (2p + C)
    does not, so two of the three reports run."""
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 3))
    assert _smoke("--ids", "H-021,H-022,C-011", "--cost-gate", "1.00") == 0  # to read C
    ceiling = read_report_json(tree / "runs" / RUN_ID / "config.json")["assumed_call_usd"]
    per_call = cost_usd(EVAL_MODEL, client.input_tokens, client.output_tokens)
    assert math.isclose(per_call, 0.045) and len(client.calls) == 3
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW.replace(minute=31))
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 3))
    gate = ceiling + per_call + 0.001
    assert _smoke("--ids", "H-021,H-022,C-011", "--cost-gate", f"{gate:.6f}") == 1
    assert len(client.calls) == 2
    assert "stopped early: cost gate" in capsys.readouterr().out


def test_calls_are_capped_at_two_per_report(tree, monkeypatch):
    """Each report gets one call and at most one retry (an unreadable first answer)."""
    client = _use(monkeypatch, FakeEvalClient(["not json"] * 10))
    assert _smoke("--ids", "H-021,C-011", "--cost-gate", "1.00") == 0
    assert len(client.calls) == 4
    results = read_report_json(tree / "runs" / RUN_ID / "results.json")
    assert [u["status"] for u in results["units"]] == ["invalid", "invalid"]


def test_a_smoke_run_folder_that_exists_is_refused(tree, monkeypatch, capsys):
    (tree / "runs" / RUN_ID).mkdir(parents=True)
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert f"runs/{RUN_ID} exists already" in capsys.readouterr().out


def test_smoke_output_is_never_scored(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 0
    monkeypatch.setattr(cli, "SCORE_ROOT", tree)
    capsys.readouterr()
    assert cli.main(["map-list", "--runs", RUN_ID]) == 1
    assert "map-list refused:" in capsys.readouterr().out


# Review round 1 (S8): section B's limits enforced by the code, and the weak tests


def test_a_gate_above_the_hard_stop_is_refused(tree, capsys):
    assert _smoke("--ids", "H-021", "--cost-gate", "1.01") == 1
    assert "above section B's hard stop of $1.00" in capsys.readouterr().out
    assert not (tree / "runs").exists()


def test_the_stage_limits_count_every_earlier_smoke_run(tree, monkeypatch, capsys):
    """Section B: 8 calls and $1.00 for the whole stage, over every invocation (a corrected
    attempt is a new invocation). Each fake call costs $0.045."""
    _use(monkeypatch, FakeEvalClient(["not json"] * 6))
    assert _smoke("--ids", "H-021,H-022,H-023", "--cost-gate", "1.00") == 0  # 6 calls
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW.replace(minute=31))
    client = _use(monkeypatch, FakeEvalClient(["not json"] * 6))
    assert _smoke("--ids", "H-024,C-011", "--cost-gate", "1.00") == 1  # only 2 calls left
    assert len(client.calls) == 2
    config = read_report_json(tree / "runs" / "smoke-20261116-093100" / "config.json")
    assert config["max_calls"] == 2
    assert config["cost_gate_usd"] == pytest.approx(1.00 - 6 * 0.045)
    monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW.replace(minute=32))
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    capsys.readouterr()
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "section B's 8 calls are used up (8 made in earlier smoke runs)" in (
        capsys.readouterr().out
    )
    assert client.calls == []


def test_more_reports_never_make_more_than_eight_calls(tree, monkeypatch):
    client = _use(monkeypatch, FakeEvalClient(["not json"] * 12))
    _smoke("--ids", "H-021,H-022,H-023,H-024,C-011", "--cost-gate", "1.00")
    assert len(client.calls) == 8


def test_a_draft_holding_another_report_is_refused(tree, capsys):
    other = read_report_json(tree / "data" / "drafts" / "H-022.json")
    write_report_json(tree / "data" / "drafts" / "H-021.json", other)
    assert _smoke("--ids", "H-021,H-022", "--cost-gate", "1.00") == 1
    assert "data/drafts/H-021.json holds report H-022" in capsys.readouterr().out


def test_a_draft_with_a_key_given_twice_is_refused(tree, capsys):
    path = tree / "data" / "drafts" / "H-021.json"
    text = path.read_text(encoding="utf-8").replace(
        '"split": "dev"', '"split": "scored", "split": "dev"'
    )
    path.write_text(text, encoding="utf-8")
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "key 'split' is given twice" in capsys.readouterr().out


def test_inference_geo_must_stay_unset(tree, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_INFERENCE_GEO", "secret-region-value")
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    out = capsys.readouterr().out
    assert "ANTHROPIC_INFERENCE_GEO is set; section B requires it unset" in out
    assert "secret-region-value" not in out


def test_the_ceiling_bounds_the_dearest_call(tree, monkeypatch):
    """Input tokens cannot exceed the UTF-8 bytes of the texts (a token covers at least one
    byte), plus 100 tokens for the message wrapping; output cannot exceed max_tokens."""
    client = _use(monkeypatch, FakeEvalClient([EMPTY] * 3))
    assert _smoke("--ids", "H-021,C-011,H-022", "--cost-gate", "1.00") == 0
    longest = max(len(s.encode("utf-8")) + len(u.encode("utf-8")) for s, u, _ in client.calls)
    expected = cost_usd(EVAL_MODEL, longest + 100, EVAL_MAX_TOKENS)
    config = read_report_json(tree / "runs" / RUN_ID / "config.json")
    assert config["assumed_call_usd"] == round(expected, 6)


def test_requests_are_printed_before_the_first_call_with_their_true_lengths(
    tree, monkeypatch, capsys
):
    seen: list[str] = []

    def answer(system: str, user: str) -> str:
        if not seen:
            seen.append(capsys.readouterr().out)  # everything printed before the first call
        return EMPTY

    client = _use(monkeypatch, FakeEvalClient(answer))
    assert _smoke("--ids", "H-021,C-011", "--cost-gate", "1.00") == 0
    printed = {line.split(":")[0]: json.loads(line.split(": ", 1)[1])
               for line in seen[0].splitlines() if line.startswith("request ")}  # fmt: skip
    assert set(printed) == {"request H-021", "request C-011"}
    sent = {u: (s, u) for s, u, _ in client.calls}
    for shape in printed.values():
        lengths = {(len(s), len(u)) for s, u in sent.values()}
        system_len = int(shape["system"].strip("<>").split()[0])
        user_len = int(shape["messages"][0]["content"].strip("<>").split()[0])
        assert (system_len, user_len) in lengths


def test_calls_go_one_at_a_time_without_transport_retries(tree, monkeypatch):
    seen: dict = {}
    real = cli.run_units

    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(cli, "run_units", spy)
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 0
    config = read_report_json(tree / "runs" / RUN_ID / "config.json")
    assert (seen["workers"], seen["transport_retries"], seen["repeats"]) == (1, 0, 1)
    assert seen["min_assumed_usd"] == pytest.approx(config["assumed_call_usd"], abs=1e-6)
    assert seen["max_calls"] == config["max_calls"] == 2


def test_a_cheaper_model_string_is_priced_as_the_model_requested(tree, monkeypatch):
    """The gate must not under-count: a call is priced at the dearer of the model requested
    and the model the API names. (Another model returned also fails the smoke test.)"""
    _use(monkeypatch, FakeEvalClient([EMPTY], model="claude-haiku-5-5"))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    line = json.loads((tree / "runs" / RUN_ID / "calls.jsonl").read_text("utf-8").split("\n")[0])
    assert line["model_returned"] == "claude-haiku-5-5"
    assert line["cost_usd"] == pytest.approx(cost_usd(EVAL_MODEL, 2500, 4000))


def test_results_json_says_it_is_not_evaluation_data(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 0
    results = read_report_json(tree / "runs" / RUN_ID / "results.json")
    assert results["purpose"] == PURPOSE


# Review round 2 (S8)


def test_an_overlapping_smoke_run_is_refused(tree, monkeypatch, capsys):
    """Section B's limits must hold for invocations that overlap, not only for earlier ones."""
    inner: list[int] = []

    def answer(system: str, user: str) -> str:
        if not inner:  # a second invocation starts while the first one's call is in flight
            monkeypatch.setattr(cli, "RUN_CLOCK", lambda: NOW.replace(minute=35))
            inner.append(cli.main(["smoke", "--ids", "H-022", "--cost-gate", "1.00"]))
        return EMPTY

    _use(monkeypatch, FakeEvalClient(answer))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 0
    assert inner == [1]
    assert "another smoke run is going on" in capsys.readouterr().out
    assert not (tree / "runs" / "smoke-20261116-093500").exists()


@pytest.mark.parametrize("bad", ["NaN", "-0.95", '"-Infinity"', "Infinity"])
def test_an_earlier_cost_that_is_not_a_finite_nonnegative_amount_is_refused(
    tree, monkeypatch, capsys, bad
):
    folder = tree / "runs" / "smoke-20261111-000001"
    folder.mkdir(parents=True)
    (folder / "calls.jsonl").write_text(
        '{"cost_usd": 0.95}\n{"cost_usd": ' + bad + "}\n", encoding="utf-8"
    )
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "cannot be read to count earlier calls" in capsys.readouterr().out
    assert client.calls == []


def test_every_line_of_an_earlier_run_counts_as_a_call(tree, monkeypatch):
    """A transport failure or a refused call is a request too."""
    folder = tree / "runs" / "smoke-20261111-000001"
    folder.mkdir(parents=True)
    lines = ['{"error_class": "RateLimitError", "error_message": "x"}'] * 7
    (folder / "calls.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient(["not json"] * 4))
    _smoke("--ids", "H-021", "--cost-gate", "1.00")
    assert len(client.calls) == 1


def test_a_corrupt_earlier_calls_file_is_refused(tree, monkeypatch, capsys):
    folder = tree / "runs" / "smoke-20261111-000001"
    folder.mkdir(parents=True)
    (folder / "calls.jsonl").write_text('{"cost_usd": 0.1\n', encoding="utf-8")
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "cannot be read to count earlier calls" in capsys.readouterr().out


@pytest.mark.parametrize("gate", ["0.0000001", "0.0000004"])
def test_a_gate_too_small_to_record_is_refused(tree, capsys, gate):
    assert _smoke("--ids", "H-021", "--cost-gate", gate) == 1
    assert "is below $0.000001" in capsys.readouterr().out


def test_an_empty_inference_geo_still_counts_as_set(tree, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_INFERENCE_GEO", "")
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "ANTHROPIC_INFERENCE_GEO is set" in capsys.readouterr().out


def test_another_model_returned_fails_the_smoke_test(tree, monkeypatch, capsys):
    _use(monkeypatch, FakeEvalClient([EMPTY], model="claude-other-9"))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "the API returned claude-other-9, not claude-sonnet-5-5" in capsys.readouterr().out


def test_each_request_line_gives_its_own_report_lengths(tree, monkeypatch, capsys):
    client = _use(monkeypatch, FakeEvalClient([EMPTY, EMPTY]))
    assert _smoke("--ids", "H-021,C-011", "--cost-gate", "1.00") == 0
    printed = {}
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("request "):
            shape = json.loads(line.split(": ", 1)[1])
            printed[line.split(":")[0]] = (
                int(shape["system"].strip("<>").split()[0]),
                int(shape["messages"][0]["content"].strip("<>").split()[0]),
            )
    # units run in report-id order: C-011 first, then H-021
    sent = [(len(s), len(u)) for s, u, _ in client.calls]
    assert printed == {"request C-011": sent[0], "request H-021": sent[1]}


# Review round 3 (S8)

HOLD_STAGE_LOCK = """
import sys
from pathlib import Path
from pathqc_eval.harness import run_lock
with run_lock(Path(sys.argv[1])):
    print("locked", flush=True)
    sys.stdin.read()
"""


def test_a_smoke_run_in_another_process_is_refused(tree, monkeypatch, capsys):
    import subprocess
    import sys

    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_STAGE_LOCK, str(tree / "runs" / "_smoke_stage")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    try:
        assert holder.stdout.readline().strip() == "locked"
        assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
    assert client.calls == []
    assert "another smoke run is going on" in capsys.readouterr().out


def test_the_earlier_spend_is_read_while_the_stage_lock_is_held(tree, monkeypatch):
    from pathqc_eval import harness

    held: list[bool] = []
    real = cli._earlier_smoke_spend

    def spy(root):
        held.append(harness.run_is_busy(root / "runs" / "_smoke_stage"))
        return real(root)

    monkeypatch.setattr(cli, "_earlier_smoke_spend", spy)
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 0
    assert held == [True]


def test_an_unusable_stage_lock_is_refused_in_plain_words(tree, monkeypatch, capsys):
    (tree / "runs").mkdir()
    (tree / "runs" / "_smoke_stage").write_text("not a folder", encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "runs/_smoke_stage/.run.lock cannot be used" in capsys.readouterr().out
    assert client.calls == []


def test_a_gate_left_that_rounds_to_nothing_is_refused(tree, monkeypatch, capsys):
    folder = tree / "runs" / "smoke-20261111-000001"
    folder.mkdir(parents=True)
    (folder / "calls.jsonl").write_text('{"cost_usd": 0.9999996}\n', encoding="utf-8")
    client = _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "is used up by earlier smoke runs" in capsys.readouterr().out
    assert client.calls == []


def test_another_model_in_any_attempt_fails_the_smoke_test(tree, monkeypatch, capsys):
    from pathqc_eval.harness import EvalResponse

    other = EvalResponse("not json", "claude-haiku-5-5", 100, 100, "end_turn")
    _use(monkeypatch, FakeEvalClient([other, EMPTY]))  # attempt 2 comes back as Sonnet
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "the API returned claude-haiku-5-5" in capsys.readouterr().out


def test_a_huge_earlier_cost_is_refused_in_plain_words(tree, monkeypatch, capsys):
    folder = tree / "runs" / "smoke-20261111-000001"
    folder.mkdir(parents=True)
    (folder / "calls.jsonl").write_text('{"cost_usd": 1' + "0" * 400 + "}\n", encoding="utf-8")
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    assert "cannot be read to count earlier calls" in capsys.readouterr().out


def test_an_input_that_cannot_be_hashed_is_not_blamed_on_the_lock(tree, monkeypatch, capsys):
    (tree / "data" / "reports" / "x.json").mkdir(parents=True)
    _use(monkeypatch, FakeEvalClient([EMPTY]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 1
    out = capsys.readouterr().out
    assert "cannot be hashed" in out and "_smoke_stage" not in out


def test_results_json_is_marked_even_after_an_interrupt(tree, monkeypatch):
    _use(monkeypatch, FakeEvalClient([KeyboardInterrupt()]))
    assert _smoke("--ids", "H-021", "--cost-gate", "1.00") == 130
    results = read_report_json(tree / "runs" / RUN_ID / "results.json")
    assert results["purpose"] == PURPOSE


# Final audit (S9)


def test_the_help_states_the_call_limit_and_the_condition(capsys):
    with pytest.raises(SystemExit):
        cli.main(["smoke", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "one unit each, at most two calls" in out
    assert "one call each" not in out
