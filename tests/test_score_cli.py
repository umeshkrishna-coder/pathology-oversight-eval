"""`map-list`, `adjudicate` and `score` through the CLI (EVAL-05 6.3, 6.7, 6.8), in temporary
trees with invented runs."""

import json
import os
import re
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scoring_fixtures import (
    DIAGNOSIS,
    MODEL,
    SYNOPTIC,
    Clock,
    all_units,
    error,
    finding,
    report,
    standard_reports,
    write_map,
    write_run,
    write_tree,
)

from pathqc_eval import cli
from pathqc_eval import scoring_config as cfg
from pathqc_eval.freeze import freeze
from pathqc_eval.io import read_report_json, write_report_json

MICRO = "Microscopic description"
TUMOUR = "Tumour measures 25 mm."
IDS = ("H-001", "H-002", "C-001")
PLAIN, STRUCTURED = "dev-plain-run", "dev-structured-run"


@pytest.fixture
def tree(tmp_path, histo, cbc, monkeypatch):
    root = write_tree(tmp_path, standard_reports(histo, cbc))
    monkeypatch.setattr(cli, "SCORE_ROOT", root)
    monkeypatch.setattr(cli, "SCORE_CLOCK", Clock())
    monkeypatch.setattr(cli, "SCORER_COMMIT", lambda: "0123abc")
    return root


def _main(*args: str) -> int:
    return cli.main(list(args))


def _review_runs(root):
    """Three review findings in two items: an unmapped category on H-001's E1 in plain r1
    and, identical, in structured r2 (one item); a section mismatch in structured r1."""
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("size problem", MICRO, TUMOUR)]
    structured = all_units(IDS)
    structured[("H-001", 1)] = [finding("H1", "Diagnosis", TUMOUR)]
    structured[("H-001", 2)] = [finding("Size problem.", MICRO, TUMOUR)]
    write_run(root, PLAIN, "plain", plain)
    write_run(root, STRUCTURED, "structured", structured)


ADJ = Path("results/dev/adjudication")


def _fill(root, verdicts: dict[str, tuple[str, str]]) -> None:
    path = root / ADJ / "adjudication_sheet.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    out, current = [], None
    for line in lines:
        if line.startswith("== "):
            current = line.strip("= ").strip()
        if current in verdicts and line == "verdict:":
            line = f"verdict: {verdicts[current][0]}"
        elif current in verdicts and line == "reason:":
            line = f"reason: {verdicts[current][1]}"
        out.append(line)
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def _items(root) -> list[dict]:
    return read_report_json(root / ADJ / "adjudication.json")["items"]


def _item_for(root, reason: str) -> str:
    return next(i["item_id"] for i in _items(root) if i["review_reason"] == reason)


# map-list


def test_map_list_counts_categories_per_condition_and_never_writes_the_map(tree, capsys):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("Size mismatch", MICRO, TUMOUR), finding("H1", MICRO, TUMOUR)]
    structured = all_units(IDS)
    structured[("H-001", 1)] = [finding("size  mismatch.", MICRO, TUMOUR)]
    structured[("H-001", 2)] = [finding("Odd wording", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    write_map(tree, {"size mismatch": "H1"})
    before = (tree / "data" / "category_map.json").read_bytes()
    assert _main("map-list", "--runs", PLAIN, STRUCTURED) == 0
    out = read_report_json(tree / "results" / "dev" / "category_strings.json")
    assert out["categories"] == [
        {"category": "h1", "count": {"plain": 1, "structured": 0}, "mapped": True, "maps_to": "H1"},
        {"category": "odd wording", "count": {"plain": 0, "structured": 1}, "mapped": False,
         "maps_to": None},
        {"category": "size mismatch", "count": {"plain": 1, "structured": 1}, "mapped": True,
         "maps_to": "H1"},
    ]  # fmt: skip
    assert (tree / "data" / "category_map.json").read_bytes() == before
    assert "3 distinct categories, 1 unmapped" in capsys.readouterr().out


def test_map_list_without_a_map_lists_every_category_as_unmapped(tree):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("Size mismatch", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", plain)
    assert _main("map-list", "--runs", PLAIN) == 0
    assert not (tree / "data" / "category_map.json").exists()
    (row,) = read_report_json(tree / "results" / "dev" / "category_strings.json")["categories"]
    assert (row["category"], row["mapped"]) == ("size mismatch", False)


# Adjudication


def test_prepare_merges_identical_findings_into_one_item(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    items = _items(tree)
    assert sorted(i["review_reason"] for i in items) == ["section_mismatch", "unmapped_category"]
    assert all(i["item_id"] in ("A001", "A002") and i["verdict"] is None for i in items)
    hidden = read_report_json(tree / ADJ / "adjudication_hidden.json")
    merged = hidden[_item_for(tree, "unmapped_category")]
    assert [(r["run_id"], r["condition"], r["repeat"], r["finding_index"]) for r in merged] == [
        (PLAIN, "plain", 1, 1),
        (STRUCTURED, "structured", 2, 1),
    ]
    assert all(r["model"] == MODEL for refs in hidden.values() for r in refs)


def test_the_owner_facing_files_name_no_condition_run_model_or_repeat(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    for name in ("adjudication.json", "adjudication_sheet.md"):
        text = (tree / ADJ / name).read_text(encoding="utf-8").lower()
        for word in ("plain", "structured", PLAIN, STRUCTURED, MODEL, "repeat", "sonnet"):
            assert word.lower() not in text, (name, word)


def test_the_sheet_shows_each_item_and_its_candidate_error(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    sheet = (tree / ADJ / "adjudication_sheet.md").read_text(encoding="utf-8")
    item = _item_for(tree, "section_mismatch")
    block = sheet.split(f"== {item} ==")[1].split("== A")[0]
    assert "# report: H-001" in block and "# section: Diagnosis" in block
    assert "# quoted sentence: Tumour measures 25 mm." in block
    assert "H-001-E1 (H1, statement) in Microscopic description" in block
    assert "Microscopic size contradicts the 18 mm gross size." in block
    assert "the finding names another section" in block
    assert block.rstrip().endswith("verdict:\nreason:")


def test_prepare_refuses_to_overwrite_and_replace_needs_an_empty_sheet(tree, capsys):
    _review_runs(tree)
    args = ["adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    assert _main(*args) == 1
    assert "already prepared" in capsys.readouterr().out
    assert _main(*args, "--replace") == 0
    _fill(tree, {"A001": ("miss", "")})
    assert _main(*args, "--replace") == 1
    assert "verdicts have been entered" in capsys.readouterr().out


def test_apply_rejects_a_wrong_verdict_in_plain_words_and_writes_nothing(tree, capsys):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("maybe", "unsure"), "A002": ("detected", "")})
    before = (tree / ADJ / "adjudication.json").read_bytes()
    assert _main("adjudicate", "apply", "--dataset", "dev") == 1
    out = capsys.readouterr().out
    assert "A001: verdict 'maybe' is not one of detected, miss, near_miss, false_alarm" in out
    assert "A002: the verdict 'detected' needs a reason" in out
    assert (tree / ADJ / "adjudication.json").read_bytes() == before


def test_apply_and_status(tree, capsys):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("Detected", "same sentence")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("adjudicate", "status", "--dataset", "dev") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["adjudication (dev): 1 of 2 verdicts filled"] * 2
    first = next(i for i in _items(tree) if i["item_id"] == "A001")
    assert (first["verdict"], first["verdict_reason"]) == ("detected", "same sentence")


def test_score_refuses_until_the_adjudication_is_complete(tree, capsys):
    _review_runs(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "3 review finding(s) need the owner's blind adjudication (not prepared)" in (
        capsys.readouterr().out
    )
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("miss", "x")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "(1 of 2 verdicts filled)" in capsys.readouterr().out
    assert not (tree / "results" / "dev" / "score.json").exists()
    assert not (tree / ADJ / "adjudication_log.json").exists()


def _complete(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    unmapped = _item_for(tree, "unmapped_category")
    mismatch = _item_for(tree, "section_mismatch")
    _fill(tree, {unmapped: ("detected", "right sentence"), mismatch: ("false_alarm", "no")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0


def test_score_joins_the_verdicts_and_logs_the_order(tree):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    log = read_report_json(tree / ADJ / "adjudication_log.json")
    assert log["prepared_at"] < log["completed_at"] < log["joined_at"]
    assert log["items"] == 2
    for name in ("score.json", "summary.md"):  # no clock time in the scorer's outputs
        text = (tree / "results" / "dev" / name).read_text(encoding="utf-8")
        assert not any(log[k] in text for k in ("prepared_at", "completed_at", "joined_at"))
    score = read_report_json(tree / "results" / "dev" / "score.json")
    outcomes = {
        (f["condition"], f["repeat"]): (f["outcome"], f["verdict"])
        for f in score["findings"]
        if f["report_id"] == "H-001"
    }
    assert outcomes == {
        ("plain", 1): ("hit", "detected"),
        ("structured", 1): ("false_alarm", "false_alarm"),
        ("structured", 2): ("hit", "detected"),
    }
    assert score["counts"]["review_items"]["verdicts"]["detected"] == 1


def test_verdicts_cannot_change_after_the_reveal(tree, capsys):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    assert _main("adjudicate", "apply", "--dataset", "dev") == 1
    assert "cannot change after the reveal" in capsys.readouterr().out
    path = tree / ADJ / "adjudication.json"
    data = read_report_json(path)
    data["items"][0]["verdict_reason"] = "changed afterwards"
    write_report_json(path, data)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "has changed since the reveal" in capsys.readouterr().out


def test_provisional_scores_give_ranges(tree, capsys):
    _review_runs(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED, "--provisional") == 0
    folder = tree / "results" / "dev" / "provisional"
    score = read_report_json(folder / "score.json")
    assert score["provisional"] is True and score["title"].startswith("PROVISIONAL")
    against = score["metrics"]["counted_against"]["plain"]["overall_recall"]
    for_ = score["metrics"]["counted_for"]["plain"]["overall_recall"]
    assert (against["k"], for_["k"]) == (0, 0)  # one review hit in one unit is no majority
    s_against = score["metrics"]["counted_against"]["structured"]["false_alarms_per_report"]
    s_for = score["metrics"]["counted_for"]["structured"]["false_alarms_per_report"]
    assert s_against["planted"]["mean"] > s_for["planted"]["mean"] == 0.0
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    headings = [line for line in summary.splitlines() if line.startswith("#")]
    assert headings and all("PROVISIONAL" in h for h in headings)
    assert " to " in summary.split("False alarms per report")[1].split("##")[0]
    assert not (tree / "results" / "dev" / "score.json").exists()


def test_scoring_twice_gives_byte_identical_files(tree):
    _complete(tree)
    args = ["score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    first = {n: (tree / "results" / "dev" / n).read_bytes() for n in ("score.json", "summary.md")}
    assert _main(*args) == 0
    second = {n: (tree / "results" / "dev" / n).read_bytes() for n in ("score.json", "summary.md")}
    assert first == second


SUBPROCESS_SCORE = """
import sys
from pathlib import Path
from pathqc_eval import cli
cli.SCORE_ROOT = Path(sys.argv[1])
cli.SCORER_COMMIT = lambda: "0123abc"
sys.exit(cli.main(["score", "--dataset", "dev", "--runs", sys.argv[2], sys.argv[3]]))
"""


def test_byte_identical_across_processes_with_different_hash_seeds(tree):
    """Set and dict order must not depend on Python's per-process string hashing."""
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("H1", MICRO, TUMOUR), finding("Odd", "Diagnosis", DIAGNOSIS)]
    plain[("H-002", 2)] = [finding("H5", "Diagnosis", DIAGNOSIS, confidence=None)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS, [finding("H1", MICRO, TUMOUR)]))
    outputs = []
    for seed in ("1", "2"):
        env = os.environ | {"PYTHONHASHSEED": seed, "ANTHROPIC_API_KEY": ""}
        done = subprocess.run(
            [sys.executable, "-c", SUBPROCESS_SCORE, str(tree), PLAIN, STRUCTURED],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        folder = tree / "results" / "dev"
        outputs.append({n: (folder / n).read_bytes() for n in ("score.json", "summary.md")})
    assert outputs[0] == outputs[1]


def test_summary_has_the_tables_and_the_disclosures(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS, [finding("H1", MICRO, TUMOUR)]))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    for heading in (
        "Per-type recall by condition",
        "Overall recall",
        "False alarms per report",
        "Specificity on clean controls",
        "Calibration",
        "Repeat consistency",
        "Severity-weighted recall",
        "Structured minus plain",
        "Counts",
        "Disclosures",
    ):
        assert f"## {heading}" in summary
    assert "| H1 | 1/1 = 100.0% (95% CI 20.7%–100.0%) | 0/1 = 0.0% (95% CI 0.0%–79.3%) |" in summary
    assert "drafted by claude-haiku-5-5 and corrected by the owner" in summary
    assert "the API returned the model string claude-sonnet-5-5" in summary
    assert "3 reports were scored (dev split)" in summary
    assert "0 review item(s) were adjudicated by hand" in summary
    score = read_report_json(tree / "results" / "dev" / "score.json")
    assert score["inputs"]["scorer_commit"] == "0123abc"
    assert score["inputs"]["scoring_config"]["BOOTSTRAP_SEED"] == 20261115


def test_dev_scoring_accepts_a_proposed_or_missing_map(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    write_map(tree, {"size mismatch": "H1"}, status="proposed")
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0


def _change_run(root, run_id: str, **changes) -> None:
    """Change config.json (and, for the split, results.json too) of a written run."""
    for name in ("config.json", "results.json"):
        path = root / "runs" / run_id / name
        data = read_report_json(path)
        write_report_json(path, data | {k: v for k, v in changes.items() if k in data})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda root: write_run(root, PLAIN, "structured", all_units(IDS)),
         "one plain and one structured run"),
        (lambda root: write_run(root, STRUCTURED, "structured", all_units(IDS[:2])),
         f"run {STRUCTURED} covers other reports than the dev reports"),
        (lambda root: write_map(root, {"Size mismatch": "H1"}),
         "key 'Size mismatch' is not normalised; write it as 'size mismatch'"),
        (lambda root: write_map(root, {"size": "H9"}), "'size' maps to 'H9'"),
        (lambda root: _change_run(root, STRUCTURED, dataset="scored"),
         f"run {STRUCTURED} is for the scored split, not dev"),
        (lambda root: _change_run(root, STRUCTURED, taxonomy_hash="c" * 64),
         "the two runs differ in taxonomy_hash"),
        (lambda root: _change_run(root, STRUCTURED, dataset_hash="c" * 64),
         "the two runs differ in dataset_hash"),
        (lambda root: (root / "data" / "category_map.json").write_text(
            '{"version": "1.0", "status": "proposed", '
            '"map": {"size problem": "H1", "size problem": "H2"}}', encoding="utf-8"),
         "key 'size problem' is given twice"),
    ],
)  # fmt: skip
def test_input_refusals(tree, capsys, change, message):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    change(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    out = capsys.readouterr().out
    assert out.startswith("score refused:") and message in out


def test_dev_scoring_after_a_report_changed_goes_on_with_a_warning(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    path = tree / "data" / "reports" / "C-001.json"
    path.write_bytes(path.read_bytes() + b" ")
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    warning = "data/reports/ has changed since the runs (the dataset hash differs)"
    assert f"warning: {warning}" in capsys.readouterr().out
    score = read_report_json(tree / "results" / "dev" / "score.json")
    assert score["inputs"]["warnings"] == [warning]
    assert f"Warning: {warning}" in (tree / "results" / "dev" / "summary.md").read_text("utf-8")


def test_a_run_with_pending_units_is_refused(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    path = tree / "runs" / PLAIN / "results.json"
    data = read_report_json(path)
    data["units"][0]["status"] = "pending"
    write_report_json(path, data)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert f"runs/{PLAIN} has 1 pending unit(s)" in capsys.readouterr().out


# The scored split: each refusal on its own


@pytest.fixture
def scored(tmp_path, histo, cbc, real_prompts, monkeypatch):
    """A frozen tree (34 verified reports, final taxonomy, approved prompts, a lock), scored
    runs whose hashes come from the lock, an approved map and OWNER_CONFIRMED True (the
    module's own value since EVAL-09 G; set here too so these tests do not depend on it)."""
    root = tmp_path
    reports = []
    for i in range(1, 26):
        reports.append(report(histo, f"H-{i:03d}", "dev" if i <= 3 else "scored"))
    for i in range(1, 10):
        reports.append(report(cbc, f"C-{i:03d}", "dev" if i == 1 else "scored"))
    for data in reports:
        data["provenance"] |= {"verified": True, "verified_at": "2026-11-14"}
    write_tree(root, reports, final=True)
    assert freeze(root, now=datetime(2026, 11, 15, 8, 0, tzinfo=UTC)).ok
    ids = [d["id"] for d in reports if d["split"] == "scored"]
    write_run(root, "sp", "plain", all_units(ids), dataset="scored")
    write_run(root, "ss", "structured", all_units(ids), dataset="scored")
    write_map(root, {"size mismatch": "H1"}, status="approved", version="1.0")
    monkeypatch.setattr(cli, "SCORE_ROOT", root)
    monkeypatch.setattr(cli, "SCORE_CLOCK", Clock())
    monkeypatch.setattr(cli, "SCORER_COMMIT", lambda: "0123abc")
    monkeypatch.setattr(cfg, "OWNER_CONFIRMED", True)
    return root


SCORED = ["score", "--dataset", "scored", "--runs", "sp", "ss"]


def _refusal(capsys) -> list[str]:
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "score refused:"
    return out[1:]


def test_scored_scoring_works_when_every_condition_holds(scored):
    assert _main(*SCORED) == 0
    score = read_report_json(scored / "results" / "scored" / "score.json")
    assert score["inputs"]["lock_created_at"] == "2026-11-15T08:00:00Z"
    assert score["inputs"]["category_map"]["version"] == "1.0"
    assert score["counts"]["reports"] == 30


def test_scored_refuses_without_a_lock(scored, capsys):
    (scored / "data" / "prompts.lock.json").unlink()
    assert _main(*SCORED) == 1
    assert _refusal(capsys) == ["  - freeze --check: FAILED: data/prompts.lock.json does not exist"]


def test_scored_refuses_a_map_that_is_not_approved(scored, capsys):
    write_map(scored, {"size mismatch": "H1"}, status="proposed")
    assert _main(*SCORED) == 1
    assert _refusal(capsys) == [
        "  - data/category_map.json must have status approved to score the scored split "
        "(it is proposed)"
    ]


def test_scored_refuses_if_the_confirmation_is_ever_withdrawn(scored, capsys, monkeypatch):
    """EVAL-09 G: the owner confirmed the defaults (OWNER_CONFIRMED True) and the list of
    pending defaults is gone; the flag set back to False still refuses, in one line."""
    monkeypatch.setattr(cfg, "OWNER_CONFIRMED", False)
    assert _main(*SCORED) == 1
    assert _refusal(capsys) == [
        "  - scoring_config.OWNER_CONFIRMED is False: the scorer defaults are not confirmed "
        "by the owner"
    ]


def test_scored_refuses_runs_whose_hashes_differ_from_the_lock(scored, capsys):
    path = scored / "runs" / "sp" / "config.json"
    write_report_json(path, read_report_json(path) | {"prompt_hash": "c" * 64})
    assert _main(*SCORED) == 1
    assert _refusal(capsys) == ["  - run sp: prompt_hash differs from data/prompts.lock.json"]


def test_map_list_never_changes_an_approved_map(scored):
    before = (scored / "data" / "category_map.json").read_bytes()
    assert _main("map-list", "--runs", "sp", "ss") == 0
    assert (scored / "data" / "category_map.json").read_bytes() == before
    assert (
        json.loads((scored / "results" / "scored" / "category_strings.json").read_text())[
            "categories"
        ]
        == []
    )


def test_score_refuses_an_adjudication_prepared_from_other_findings(tree, capsys):
    _complete(tree)
    write_map(tree, {"size problem": "H1"})  # two review findings become hits
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "was prepared from other review findings than these runs give now" in (
        capsys.readouterr().out
    )
    assert not (tree / ADJ / "adjudication_log.json").exists()


def test_two_report_files_with_the_same_id_are_refused(tree, capsys):
    original = tree / "data" / "reports" / "H-001.json"
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    (tree / "data" / "reports" / "H-001 - Copy.json").write_bytes(original.read_bytes())
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "report id H-001 is in both H-001 - Copy.json and H-001.json" in (
        capsys.readouterr().out
    )


# Review round 1 (S6)


def test_review_findings_in_different_reports_keep_their_own_verdicts(tree):
    """Two review findings at the same run, repeat and finding index, in two reports: each
    takes the verdict of its own item."""
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("size problem", MICRO, TUMOUR)]
    plain[("H-002", 1)] = [finding("staging problem", "Synoptic summary", SYNOPTIC)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    by_report = {i["report_id"]: i["item_id"] for i in _items(tree)}
    _fill(tree, {by_report["H-001"]: ("detected", "the size"),
                 by_report["H-002"]: ("false_alarm", "not the stage")})  # fmt: skip
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    outcomes = {
        f["report_id"]: (f["outcome"], f["verdict"])
        for f in score["findings"]
        if (f["condition"], f["repeat"]) == ("plain", 1)
    }
    assert outcomes == {"H-001": ("hit", "detected"), "H-002": ("false_alarm", "false_alarm")}


PROVISIONAL = ["score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED, "--provisional"]


def test_provisional_output_does_not_show_where_open_review_items_come_from(tree):
    """Decision 9: until every verdict is entered, nothing ties a review item to a condition
    or a repeat. The per-error and per-finding tables are left out of provisional output."""
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    folder = tree / "results" / "dev" / "provisional"
    score = read_report_json(folder / "score.json")
    assert "findings" not in score and "errors" not in score
    assert "review_pending_in_repeats" not in json.dumps(score)

    def keys(value) -> set:
        if isinstance(value, dict):
            return set(value) | {k for v in value.values() for k in keys(v)}
        if isinstance(value, list):
            return {k for v in value for k in keys(v)}
        return set()

    per_item = {"repeat", "finding_index", "run_id", "condition", "error_id", "report_id"}
    assert not keys(score) & per_item
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert "The per-error and per-finding tables are left out" in summary
    assert "the counts and ranges by condition can still show where an item came from" in summary
    assert "no review item can be traced" not in summary


def test_provisional_scores_before_completion_are_logged_and_disclosed(tree):
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("miss", "x")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main(*PROVISIONAL) == 0
    path = tree / "results" / "dev" / "provisional" / "provisional_log.json"
    entries = read_report_json(path)["provisional_scores"]
    assert [(e["review_findings"], e["adjudication"]) for e in entries] == [
        (3, "not prepared"),
        (3, "1 of 2 verdicts filled"),
    ]
    _fill(tree, {"A002": ("false_alarm", "y")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    log = read_report_json(tree / ADJ / "adjudication_log.json")
    assert log["provisional_scores_before_completion"] == entries
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert (
        "provisional_log.json records 2 provisional score(s) made before every review finding "
        "had a verdict"
    ) in summary


def test_a_provisional_score_after_completion_is_not_logged(tree):
    _complete(tree)
    assert _main(*PROVISIONAL) == 0
    assert not (tree / "results" / "dev" / "provisional" / "provisional_log.json").exists()
    log = read_report_json(tree / ADJ / "adjudication_log.json")
    assert log["provisional_scores_before_completion"] == []
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert (
        "provisional_log.json records no provisional score made before every review finding "
        "had a verdict."
    ) in summary


def test_provisional_counts_are_ranges(tree):
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    folder = tree / "results" / "dev" / "provisional"
    by = read_report_json(folder / "score.json")["counts"]["by_condition"]
    assert [
        by[scenario][condition]["false_alarms"]
        for scenario in ("counted_against", "counted_for")
        for condition in ("plain", "structured")
    ] == [1, 2, 0, 0]
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert "| False alarms | 1 to 0 | 2 to 0 |" in summary
    assert "| Review findings | 1 | 2 |" in summary


def test_the_disclosure_states_what_the_sheet_hides_and_claims_no_more(tree):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert (
        "2 review item(s) were adjudicated by hand by the owner, from a sheet that names no "
        "condition, repeat, model or run (decision 9). A finding's "
        "category can still suggest its condition."
    ) in summary
    assert "blind to the condition" not in summary


@pytest.mark.parametrize("content", ["{not json", "[]"])
def test_an_unreadable_adjudication_log_is_reported_in_plain_words(tree, capsys, content):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    (tree / ADJ / "adjudication_log.json").write_text(content, encoding="utf-8")
    for args in (
        ("adjudicate", "apply", "--dataset", "dev"),
        ("adjudicate", "status", "--dataset", "dev"),
        ("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED),
    ):
        capsys.readouterr()
        assert _main(*args) == 1, args
        assert "adjudication_log.json cannot be read" in capsys.readouterr().out, args


def test_replace_is_refused_when_a_verdict_was_typed_in_a_second_block(tree, capsys):
    _review_runs(tree)
    args = ["adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    sheet = tree / ADJ / "adjudication_sheet.md"
    extra = "\n== A001 ==\nverdict: detected\nreason: typed in a second block\n"
    sheet.write_text(sheet.read_text(encoding="utf-8") + extra, encoding="utf-8")
    capsys.readouterr()
    assert _main(*args, "--replace") == 1
    assert "verdicts have been entered" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("adjudication_sheet.md", lambda text: text + "\nnote to self: check A001\n"),
        ("adjudication.json", lambda text: "{not json"),
    ],
)
def test_replace_is_refused_when_anything_else_was_written(tree, capsys, name, change):
    _review_runs(tree)
    args = ["adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    path = tree / ADJ / name
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")
    capsys.readouterr()
    assert _main(*args, "--replace") == 1
    assert "verdicts have been entered" in capsys.readouterr().out


def test_score_refuses_a_hidden_file_that_puts_one_finding_in_two_items(tree, capsys):
    _complete(tree)
    path = tree / ADJ / "adjudication_hidden.json"
    hidden = read_report_json(path)
    first, second = sorted(hidden)
    hidden[second] = hidden[second] + [hidden[first][0]]
    write_report_json(path, hidden)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "was prepared from other review findings" in capsys.readouterr().out
    assert not (tree / ADJ / "adjudication_log.json").exists()


def test_an_unreadable_provisional_log_stops_scoring(tree, capsys):
    _review_runs(tree)
    path = tree / "results" / "dev" / "provisional" / "provisional_log.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    assert _main(*PROVISIONAL) == 1
    assert "provisional_log.json cannot be read" in capsys.readouterr().out
    assert not (path.parent / "score.json").exists()
    _complete(tree)
    capsys.readouterr()
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "provisional_log.json cannot be read" in capsys.readouterr().out
    assert not (tree / ADJ / "adjudication_log.json").exists()


def test_map_list_refuses_a_run_named_twice(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    assert _main("map-list", "--runs", PLAIN, PLAIN) == 1
    assert f"--runs names {PLAIN} twice" in capsys.readouterr().out
    assert not (tree / "results" / "dev" / "category_strings.json").exists()


def test_the_sheet_states_the_borderline_band_from_the_settings(tree, monkeypatch):
    monkeypatch.setattr(cfg, "BORDERLINE_LOW", 0.3)
    monkeypatch.setattr(cfg, "OVERLAP_THRESHOLD", 0.7)
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("H1", MICRO, "Tumour size given as 25 cm")]  # overlap 0.5
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    sheet = (tree / ADJ / "adjudication_sheet.md").read_text(encoding="utf-8")
    assert "overlap of at least 0.3 and below 0.7" in sheet


def test_prepare_merges_findings_that_differ_only_in_case_and_spacing(tree):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("size problem", MICRO, TUMOUR)]
    structured = all_units(IDS)
    structured[("H-001", 2)] = [
        finding("Size  Problem", "microscopic  DESCRIPTION", "tumour measures  25 mm.")
    ]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", structured)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    assert len(_items(tree)) == 1


def test_the_summary_shows_the_comparison_intervals_and_the_sampling_disclosure(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS, [finding("H1", MICRO, TUMOUR)]))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    pp = r"[+-]\d+\.\d pp"
    assert re.search(rf"\| Overall recall \| {pp} \| {pp} to {pp} \|", summary)
    assert "Sampling was the API default." in summary


# Review round 2 (S6)


def test_provisional_intervals_are_bracketed_so_the_two_scenarios_can_be_told_apart(tree):
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    summary = (tree / "results" / "dev" / "provisional" / "summary.md").read_text("utf-8")
    pp = r"[+-]\d+\.\d pp"
    row = rf"\| Overall recall \| {pp} to {pp} \| \[{pp}, {pp}\] to \[{pp}, {pp}\] \|"
    assert re.search(row, summary), summary.split("Structured minus plain")[1][:400]


def test_the_counted_for_scenario_counts_review_findings_as_detections(tree):
    """Structured: H-001-E1 is in review in r1 (section mismatch) and r2 (unmapped). Counted
    against: 0 of 3 errors detected; counted for: both become hits, so E1 is detected by
    majority: 1 of 3."""
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    score = read_report_json(tree / "results" / "dev" / "provisional" / "score.json")
    recall = {s: score["metrics"][s]["structured"]["overall_recall"] for s in SCENARIO_NAMES}
    assert [(recall[s]["k"], recall[s]["n"]) for s in SCENARIO_NAMES] == [(0, 3), (1, 3)]


SCENARIO_NAMES = ("counted_against", "counted_for")


def test_a_miss_verdict_is_left_out_of_calibration(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("miss", "x"), "A002": ("miss", "y")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    cal = score["metrics"]["plain"]["calibration"]
    assert (cal["findings"], cal["left_out_miss_or_in_review"]) == (0, 1)


def test_completed_at_waits_for_the_last_verdict_and_the_reveal_is_stamped_once(tree):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("miss", "x")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert read_report_json(tree / ADJ / "adjudication.json")["completed_at"] is None
    _fill(tree, {"A002": ("miss", "y")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert read_report_json(tree / ADJ / "adjudication.json")["completed_at"] is not None
    args = ["score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    first = read_report_json(tree / ADJ / "adjudication_log.json")
    assert _main(*args) == 0
    assert read_report_json(tree / ADJ / "adjudication_log.json") == first


def test_item_ids_follow_the_seeded_shuffle(tree):
    """6.7: ids in an order shuffled with the fixed seed, not in sorted order."""
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding(f"cat {c}", MICRO, TUMOUR) for c in "abcdef"]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    by_id = [i["category"] for i in sorted(_items(tree), key=lambda i: i["item_id"])]
    assert by_id != sorted(by_id)
    assert by_id == SHUFFLED


# The sorted merge keys shuffled with random.Random(20261115); fixed by the seed.
SHUFFLED = ["cat b", "cat e", "cat f", "cat d", "cat a", "cat c"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("candidate_error_id", "H-002-E1"), ("review_reason", "borderline_overlap")],
)
def test_score_refuses_an_item_whose_candidate_or_reason_no_longer_matches(
    tree, capsys, field, value
):
    _complete(tree)
    path = tree / ADJ / "adjudication.json"
    data = read_report_json(path)
    data["items"][0][field] = value
    write_report_json(path, data)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "was prepared from other review findings" in capsys.readouterr().out


def test_a_prepared_adjudication_is_refused_when_the_runs_no_longer_need_it(tree, capsys):
    _complete(tree)
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "was prepared from other review findings" in capsys.readouterr().out


def test_logged_provisional_scores_are_disclosed_even_with_no_review_findings_left(tree):
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert "0 review item(s) were adjudicated by hand." in summary
    assert "from a sheet" not in summary
    assert "provisional_log.json records 1 provisional score(s)" in summary


def test_an_unreadable_adjudication_json_is_reported_as_unreadable_not_unprepared(tree, capsys):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    (tree / ADJ / "adjudication.json").write_text("{not json", encoding="utf-8")
    for args in (["score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED], PROVISIONAL):
        capsys.readouterr()
        assert _main(*args) == 1
        out = capsys.readouterr().out
        assert "adjudication.json cannot be read" in out and "not prepared" not in out
    assert not (tree / "results" / "dev" / "provisional" / "provisional_log.json").exists()


def test_an_output_that_cannot_be_written_is_reported_in_plain_words(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    (tree / "results" / "dev" / "summary.md").mkdir(parents=True)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "summary.md cannot be written" in capsys.readouterr().out


def test_a_sheet_with_carriage_return_line_ends_is_read_and_protected(tree, capsys):
    _review_runs(tree)
    args = ["adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED]
    assert _main(*args) == 0
    _fill(tree, {"A001": ("miss", "x")})
    sheet = tree / ADJ / "adjudication_sheet.md"
    sheet.write_bytes(sheet.read_bytes().replace(b"\n", b"\r"))
    capsys.readouterr()
    assert _main(*args, "--replace") == 1
    assert "verdicts have been entered" in capsys.readouterr().out
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert "1 of 2 verdicts filled" in capsys.readouterr().out


def test_a_provisional_log_with_a_number_written_as_text_is_refused(tree, capsys):
    _review_runs(tree)
    path = tree / "results" / "dev" / "provisional" / "provisional_log.json"
    path.parent.mkdir(parents=True)
    entry = {"scored_at": "2026-11-16T09:01:00Z", "review_findings": "3", "adjudication": "x"}
    write_report_json(path, {"provisional_scores": [entry]})
    assert _main(*PROVISIONAL) == 1
    assert "provisional_log.json cannot be read" in capsys.readouterr().out


# Review round 3 (S6)


def test_a_refused_write_leaves_both_outputs_as_they_were(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    folder = tree / "results" / "dev"
    folder.mkdir(parents=True)
    (folder / "score.json").write_text("OLD\n", encoding="utf-8")
    summary = folder / "summary.md"
    summary.write_text("OLD summary\n", encoding="utf-8")
    os.chmod(summary, stat.S_IREAD)
    try:
        assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
        assert "results/dev/summary.md cannot be written" in capsys.readouterr().out
        assert (folder / "score.json").read_text(encoding="utf-8") == "OLD\n"
    finally:
        os.chmod(summary, stat.S_IREAD | stat.S_IWRITE)


def _add_key(path: Path, key: str, value: str) -> None:
    """Write the key a second time at the end of a JSON object (the last one would win)."""
    text = path.read_text(encoding="utf-8").rstrip().removesuffix("}").rstrip()
    path.write_text(f'{text},\n  "{key}": {value}\n}}\n', encoding="utf-8")


def test_a_provisional_log_with_a_key_given_twice_is_refused(tree, capsys):
    """A second "provisional_scores": [] would otherwise hide the logged score."""
    _review_runs(tree)
    assert _main(*PROVISIONAL) == 0
    _add_key(tree / "results" / "dev" / "provisional" / "provisional_log.json",
             "provisional_scores", "[]")  # fmt: skip
    capsys.readouterr()
    assert _main(*PROVISIONAL) == 1
    out = capsys.readouterr().out
    assert "provisional_log.json cannot be read" in out
    assert "'provisional_scores' is given twice" in out


def test_an_adjudication_log_with_a_key_given_twice_is_refused(tree, capsys):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _add_key(tree / ADJ / "adjudication_log.json", "items", "2")
    capsys.readouterr()
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    out = capsys.readouterr().out
    assert "adjudication_log.json cannot be read" in out and "'items' is given twice" in out


def test_an_adjudication_log_with_a_number_written_as_text_is_refused(tree, capsys):
    _complete(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    path = tree / ADJ / "adjudication_log.json"
    write_report_json(path, read_report_json(path) | {"items": "2"})
    for args in (
        ("adjudicate", "apply", "--dataset", "dev"),
        ("adjudicate", "status", "--dataset", "dev"),
        ("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED),
    ):
        capsys.readouterr()
        assert _main(*args) == 1, args
        assert "adjudication_log.json cannot be read" in capsys.readouterr().out, args


def test_an_adjudication_json_that_is_a_folder_is_reported_as_unreadable(tree, capsys):
    _review_runs(tree)
    (tree / ADJ / "adjudication.json").mkdir(parents=True)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    out = capsys.readouterr().out
    assert "adjudication.json cannot be read" in out and "does not exist" not in out


def test_no_review_items_and_no_log_add_no_provisional_sentence(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    assert "provisional_log.json" not in summary


def test_an_empty_preparation_is_accepted(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _review_runs(tree)
    capsys.readouterr()
    assert _main(*PROVISIONAL) == 0
    summary = (tree / "results" / "dev" / "provisional" / "summary.md").read_text("utf-8")
    assert "Review items: 0 ()" not in summary and "Review items: 0." in summary


def test_a_sheet_saved_with_a_byte_order_mark_is_read(tree, capsys):
    _review_runs(tree)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    _fill(tree, {"A001": ("miss", "x")})
    sheet = tree / ADJ / "adjudication_sheet.md"
    sheet.write_bytes(b"\xef\xbb\xbf" + sheet.read_bytes())
    capsys.readouterr()
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert "1 of 2 verdicts filled" in capsys.readouterr().out


def test_an_unreadable_provisional_log_stops_a_final_score_without_review_findings(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    path = tree / "results" / "dev" / "provisional" / "provisional_log.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 1
    assert "provisional_log.json cannot be read" in capsys.readouterr().out


def test_map_list_reports_an_output_it_cannot_write_in_plain_words(tree, capsys):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    (tree / "results" / "dev" / "category_strings.json").mkdir(parents=True)
    assert _main("map-list", "--runs", PLAIN) == 1
    assert "results/dev/category_strings.json cannot be written" in capsys.readouterr().out


# EVAL-09 (owner decisions, 2026-11-11)

# B: provisional scoring is refused on the scored split; it stays available on the dev split.


def test_provisional_scoring_of_the_scored_split_is_refused(scored, capsys):
    assert _main(*SCORED, "--provisional") == 1
    assert _refusal(capsys) == [
        "  - --provisional is refused on the scored split (owner decision, 2026-11-11): the "
        "scored split is scored only once every review item has a verdict; provisional scores "
        "stay available on the dev split"
    ]
    assert not (scored / "results" / "scored").exists()


def test_provisional_scoring_of_the_dev_split_still_works(tree):
    _review_runs(tree)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED, "--provisional") == 0
    assert (tree / "results" / "dev" / "provisional" / "score.json").is_file()


# H6: once the scored split is scored, a category map with another sha256 is refused.


def test_scoring_the_scored_split_again_refuses_a_changed_category_map(scored, capsys):
    assert _main(*SCORED) == 0
    first = read_report_json(scored / "results" / "scored" / "score.json")
    recorded = first["inputs"]["category_map"]["sha256"]
    capsys.readouterr()
    write_map(scored, {"size mismatch": "H1", "odd wording": "H2"}, "approved", "1.1")
    assert _main(*SCORED) == 1
    lines = _refusal(capsys)
    assert len(lines) == 1
    assert lines[0].startswith(
        "  - data/category_map.json has changed since the scored split was scored: "
        f"results/scored/score.json records sha256 {recorded}, the map now has "
    )
    assert lines[0].endswith("; nothing is remapped after scoring (decision 10)")
    assert read_report_json(scored / "results" / "scored" / "score.json") == first


def test_scoring_the_scored_split_again_with_the_same_map_works(scored):
    assert _main(*SCORED) == 0
    before = (scored / "results" / "scored" / "score.json").read_bytes()
    assert _main(*SCORED) == 0
    assert (scored / "results" / "scored" / "score.json").read_bytes() == before


def test_an_unreadable_scored_score_json_is_refused_in_plain_words(scored, capsys):
    assert _main(*SCORED) == 0
    (scored / "results" / "scored" / "score.json").write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert _main(*SCORED) == 1
    lines = _refusal(capsys)
    assert len(lines) == 1 and lines[0].startswith(
        "  - results/scored/score.json cannot be read, so the category map recorded at the "
        "first scoring cannot be checked ("
    )


def test_the_dev_split_may_be_scored_again_with_another_map(tree):
    write_run(tree, PLAIN, "plain", all_units(IDS))
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    write_map(tree, {"size mismatch": "H1"})
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0


# G: the defaults are confirmed; recall by severity beside the weighted figure.


def test_the_scorer_defaults_are_confirmed_by_the_owner():
    assert cfg.OWNER_CONFIRMED is True
    assert not hasattr(cfg, "PENDING_DEFAULTS")
    assert cfg.config_values()["OWNER_CONFIRMED"] is True


def test_scored_scoring_needs_no_confirmation_step(scored, monkeypatch):
    monkeypatch.undo()  # the module's own OWNER_CONFIRMED, not the fixture's
    monkeypatch.setattr(cli, "SCORE_ROOT", scored)
    monkeypatch.setattr(cli, "SCORE_CLOCK", Clock())
    monkeypatch.setattr(cli, "SCORER_COMMIT", lambda: "0123abc")
    assert _main(*SCORED) == 0


def test_recall_by_severity_is_given_as_k_of_n_with_wilson_intervals(tree):
    """H-001-E1 (major) found in every unit; H-002-E1 (critical) and H-002-E2 (minor) never."""
    found = all_units(IDS)
    for rep in (1, 2, 3):
        found[("H-001", rep)] = [finding("H1", MICRO, TUMOUR)]
    write_run(tree, PLAIN, "plain", found)
    write_run(tree, STRUCTURED, "structured", found)
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    by_severity = score["metrics"]["plain"]["recall_by_severity"]
    assert list(by_severity) == ["critical", "major", "minor"]
    assert {s: (p["k"], p["n"]) for s, p in by_severity.items()} == {
        "critical": (0, 1),
        "major": (1, 1),
        "minor": (0, 1),
    }
    assert by_severity["major"]["interval"] == [0.206549, 1.0]
    assert by_severity["critical"]["interval"] == [0.0, 0.793451]
    assert score["metrics"]["plain"]["severity_weighted_recall"]["value"] == 0.333333
    summary = (tree / "results" / "dev" / "summary.md").read_text(encoding="utf-8")
    section = summary.split("## Recall by severity")[1].split("\n## ")[0]
    assert "| Critical | 0/1 = 0.0% (95% CI 0.0%–79.3%) |" in section
    assert "| Major | 1/1 = 100.0% (95% CI 20.7%–100.0%) |" in section
    assert "| Minor | 0/1 = 0.0% (95% CI 0.0%–79.3%) |" in section
    assert summary.index("## Recall by severity") < summary.index("## Severity-weighted recall")


# C: an unmapped finding in a report with an omission error becomes a review item for it.

VAGUE = "Sections show an invasive tumour."


def test_an_unmapped_finding_in_a_report_with_an_omission_is_reviewed_for_the_omission(tree):
    plain = all_units(IDS)
    plain[("H-002", 1)] = [finding("something seems missing", MICRO, VAGUE)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    items = _items(tree)
    assert [(i["candidate_error_id"], i["review_reason"]) for i in items] == [
        ("H-002-E2", "unmapped_omission")
    ]
    sheet = (tree / ADJ / "adjudication_sheet.md").read_text(encoding="utf-8")
    assert (
        "# why it needs you: its category is not in the category map, and this report has "
        "an omission error; the finding may be reporting what is missing"
    ) in sheet
    assert "H-002-E2 (H5, omission) in Diagnosis" in sheet


def test_an_unmapped_finding_in_a_report_without_an_omission_stays_a_false_alarm(tree):
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("something seems missing", "Diagnosis", VAGUE)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    assert score["counts"]["review_findings"] == 0
    assert score["counts"]["by_condition"]["plain"]["false_alarms"] == 1


def _two_omissions(root, histo):
    """H-003: two omission errors (E1 in Diagnosis, E2 in Synoptic summary), nothing else;
    plain repeat 1 has one unmapped finding in another section."""
    data = report(
        histo,
        "H-003",
        "dev",
        [
            error("H5", "Diagnosis", DIAGNOSIS, "minor", kind="omission"),
            error("H5", "Synoptic summary", SYNOPTIC, "major", kind="omission"),
        ],
    )
    write_report_json(root / "data" / "reports" / "H-003.json", data)
    ids = (*IDS, "H-003")
    plain = all_units(ids)
    plain[("H-003", 1)] = [finding("something seems missing", MICRO, VAGUE)]
    write_run(root, PLAIN, "plain", plain)
    write_run(root, STRUCTURED, "structured", all_units(ids))


def test_with_two_omissions_one_finding_gives_one_item_per_omission(tree, histo):
    _two_omissions(tree, histo)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    items = sorted((i["candidate_error_id"], i["review_reason"]) for i in _items(tree))
    assert items == [("H-003-E1", "unmapped_omission"), ("H-003-E2", "unmapped_omission")]
    hidden = read_report_json(tree / ADJ / "adjudication_hidden.json")
    refs = [(r["run_id"], r["repeat"], r["finding_index"]) for v in hidden.values() for r in v]
    assert refs == [(PLAIN, 1, 1), (PLAIN, 1, 1)]


@pytest.mark.parametrize(
    ("e1", "e2", "outcome", "error_ids", "false_alarms"),
    [
        ("detected", "false_alarm", "hit", ["H-003-E1"], 0),
        ("false_alarm", "detected", "hit", ["H-003-E2"], 0),
        ("detected", "detected", "hit", ["H-003-E1", "H-003-E2"], 0),
        ("false_alarm", "false_alarm", "false_alarm", [], 1),
        ("near_miss", "false_alarm", "near_miss", ["H-003-E1"], 0),
        ("miss", "false_alarm", "miss", ["H-003-E1"], 0),
        ("miss", "near_miss", "near_miss", ["H-003-E2"], 0),
    ],
)
def test_the_verdicts_on_each_omission_decide_the_finding(
    tree, histo, e1, e2, outcome, error_ids, false_alarms
):
    _two_omissions(tree, histo)
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    items = {i["candidate_error_id"]: i["item_id"] for i in _items(tree)}
    _fill(tree, {items["H-003-E1"]: (e1, "invented"), items["H-003-E2"]: (e2, "invented")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    row = next(f for f in score["findings"] if f["report_id"] == "H-003")
    assert (row["outcome"], row["error_ids"]) == (outcome, error_ids)
    assert row["verdict"] == {"H-003-E1": e1, "H-003-E2": e2}
    assert score["counts"]["by_condition"]["plain"]["false_alarms"] == false_alarms
    errors = {e["error_id"]: e["plain"]["detected_by_repeat"] for e in score["errors"]}
    for eid in ("H-003-E1", "H-003-E2"):
        assert errors[eid][0] is (eid in error_ids and outcome == "hit")


# EVAL-10 K (owner decision, 2026-11-11): a finding on an error's other place

GROSS = "Gross description"
OTHER = "a firm lesion 18 mm across"


def _other_place_tree(root, histo, cbc):
    """H-001-E1 (H1, Microscopic description) names the Gross description's size as its
    other place."""
    reports = standard_reports(histo, cbc)
    reports[0]["errors"][0]["other_places"] = [{"section": GROSS, "quoted_sentence": OTHER}]
    write_tree(root, reports)


def test_a_finding_on_the_other_place_is_a_hit(tree, histo, cbc):
    _other_place_tree(tree, histo, cbc)
    plain = all_units(IDS)
    for rep in (1, 2, 3):
        plain[("H-001", rep)] = [finding("H1", GROSS, OTHER)]
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("score", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    score = read_report_json(tree / "results" / "dev" / "score.json")
    assert score["metrics"]["plain"]["per_type_recall"]["H1"]["k"] == 1
    assert score["counts"]["by_condition"]["plain"]["false_alarms"] == 0
    assert {f["outcome"] for f in score["findings"] if f["condition"] == "plain"} == {"hit"}


def test_the_sheet_shows_the_candidate_errors_other_places_after_its_sentence(tree, histo, cbc):
    _other_place_tree(tree, histo, cbc)
    plain = all_units(IDS)
    plain[("H-001", 1)] = [finding("odd wording", GROSS, OTHER)]  # unmapped: review
    write_run(tree, PLAIN, "plain", plain)
    write_run(tree, STRUCTURED, "structured", all_units(IDS))
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", PLAIN, STRUCTURED) == 0
    sheet = (tree / ADJ / "adjudication_sheet.md").read_text(encoding="utf-8")
    assert (
        "#   its quoted sentence: Tumour measures 25 mm.\n"
        f"#   its other place 1: {GROSS}: {OTHER}\n"
        "#   its description:"
    ) in sheet
