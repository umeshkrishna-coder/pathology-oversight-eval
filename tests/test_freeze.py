"""Freeze and freeze --check (EVAL-03 step 4) on complete temporary fixture trees.

Never reads data/reports/, data/drafts/ or the owner's prompt texts.
"""

import copy
import json
from datetime import UTC, datetime

import pytest
from conftest import FIXTURES

from pathqc_eval import cli
from pathqc_eval.freeze import (
    FROZEN_FILES,
    LOCK_FILE,
    check_lock,
    dataset_hash,
    freeze,
    freeze_problems,
    normalized_sha256,
)

NOW = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _report(template: dict, report_id: str, split: str) -> dict:
    data = copy.deepcopy(template)
    data["id"] = report_id
    data["split"] = split
    for i, err in enumerate(data["errors"], start=1):
        err["error_id"] = f"{report_id}-E{i}"
    data["provenance"] |= {"verified": True, "verified_at": "2026-11-14"}
    return data


@pytest.fixture
def tree(tmp_path, histo, cbc, real_prompts):
    """34 verified reports (25 planted, 9 clean, 4 dev), final taxonomy, approved prompts."""
    root = tmp_path
    taxonomy = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    _write_json(root / "data" / "taxonomy.json", taxonomy | {"status": "final"})
    reports = root / "data" / "reports"
    for i in range(1, 26):
        rid = f"H-{i:03d}"
        _write_json(reports / f"{rid}.json", _report(histo, rid, "dev" if i <= 3 else "scored"))
    for i in range(1, 10):
        rid = f"C-{i:03d}"
        _write_json(reports / f"{rid}.json", _report(cbc, rid, "dev" if i == 1 else "scored"))
    assert real_prompts == root / "prompts"
    return root


def _edit_json(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    _write_json(path, data)


def test_complete_tree_freezes(tree):
    assert freeze_problems(tree) == []
    outcome = freeze(tree, now=NOW)
    assert outcome.ok, outcome.lines
    lock = json.loads((tree / LOCK_FILE).read_text(encoding="utf-8"))
    assert lock["created_at"] == "2026-11-14T09:30:00Z"
    assert lock["taxonomy_version"] == "0.1"
    assert sorted(lock["files"]) == sorted(FROZEN_FILES)
    assert all(len(h) == 64 for h in lock["files"].values())
    assert lock["dataset"]["report_count"] == 34
    assert lock["dataset"]["hash"] == dataset_hash(lock["dataset"]["reports"])
    assert outcome.lines == [
        f"freeze: wrote {LOCK_FILE} | taxonomy 0.1 | 34 reports | dataset {lock['dataset']['hash']}"
    ]


def _taxonomy_draft(root):
    _edit_json(root / "data" / "taxonomy.json", lambda d: d.update(status="draft"))


def _manifest_proposed(root):
    _edit_json(root / "prompts" / "manifest.json", lambda d: d["plain"].update(status="proposed"))


def _placeholder(root):
    (root / "prompts" / "structured_cbc.md").write_text("<<OWNER TEXT REQUIRED>>\n", "utf-8")


def _report_missing(root):
    (root / "data" / "reports" / "H-025.json").unlink()


def _unverified(root):
    _edit_json(
        root / "data" / "reports" / "H-010.json",
        lambda d: d["provenance"].update(verified=False, verified_at=None),
    )


def _isolation_breach(root):
    # A planted error's description that appears word for word in the report text.
    _edit_json(
        root / "data" / "reports" / "H-005.json",
        lambda d: d["errors"][0].update(description="Invasive tumour, grade 2."),
    )


def _lock_exists(root):
    assert freeze(root, now=NOW).ok


@pytest.mark.parametrize(
    ("breaker", "expected"),
    [
        (_taxonomy_draft, ["taxonomy status is 'draft', not 'final'"]),
        (_manifest_proposed, ["prompts/manifest.json: entry 'plain' is proposed, not approved"]),
        (_placeholder, ["prompts/structured_cbc.md still contains <<OWNER TEXT REQUIRED>>"]),
        (_unverified, ["H-010: provenance is not verified with a verified_at date"]),
        (
            _isolation_breach,
            [
                "H-005 (plain): user message contains the description of H-005-E1",
                "H-005 (structured): user message contains the description of H-005-E1",
            ],
        ),
        (_lock_exists, [f"{LOCK_FILE} already exists; pass --replace to overwrite it"]),
    ],
)
def test_freeze_refuses_each_unmet_condition(tree, breaker, expected):
    breaker(tree)
    before = (tree / LOCK_FILE).read_bytes() if (tree / LOCK_FILE).exists() else None
    assert freeze_problems(tree) == expected
    outcome = freeze(tree, now=NOW)
    assert not outcome.ok
    assert outcome.lines == [f"freeze refused: {len(expected)} unmet condition(s):"] + [
        f"  - {p}" for p in expected
    ]
    after = (tree / LOCK_FILE).read_bytes() if (tree / LOCK_FILE).exists() else None
    assert after == before


def test_freeze_refuses_when_validation_fails(tree):
    _report_missing(tree)
    problems = freeze_problems(tree)
    assert len(problems) == 1
    assert problems[0].startswith(
        "validate data/reports --expect 34 --expect-clean 9 --expect-dev 4 fails (1 failure(s)):"
    )
    assert "expected 34 reports, found 33" in problems[0]
    assert not (tree / LOCK_FILE).exists() and not freeze(tree).ok


def test_freeze_lists_every_unmet_condition_at_once(tree):
    _taxonomy_draft(tree)
    _placeholder(tree)
    _unverified(tree)
    assert len(freeze_problems(tree)) == 3


def test_replace(tree):
    assert freeze(tree, now=NOW).ok
    assert not freeze(tree).ok
    outcome = freeze(tree, replace=True, now=datetime(2026, 11, 15, tzinfo=UTC))
    assert outcome.ok
    assert outcome.lines[0] == f"freeze: replaced the existing {LOCK_FILE}"
    lock = json.loads((tree / LOCK_FILE).read_text(encoding="utf-8"))
    assert lock["created_at"] == "2026-11-15T00:00:00Z"


def test_check_passes_after_freeze(tree):
    assert freeze(tree, now=NOW).ok
    outcome = check_lock(tree)
    assert outcome.ok
    assert outcome.lines == [f"freeze --check: OK | 6 files and 34 reports match {LOCK_FILE}"]


def test_check_without_lock_fails(tree):
    outcome = check_lock(tree)
    assert not outcome.ok
    assert outcome.lines == [f"freeze --check: FAILED: {LOCK_FILE} does not exist"]


def _append_byte(path):
    path.write_bytes(path.read_bytes() + b" ")


@pytest.mark.parametrize(
    "rel",
    ["prompts/plain.md", "prompts/structured_histopathology.md", "data/taxonomy.json"],
)
def test_check_fails_after_one_byte_change(tree, rel):
    assert freeze(tree, now=NOW).ok
    _append_byte(tree / rel)
    outcome = check_lock(tree)
    assert not outcome.ok
    assert outcome.lines == [
        f"freeze --check: FAILED: 1 file(s) differ from {LOCK_FILE}:",
        f"  - {rel}",
    ]


def test_check_fails_after_one_byte_change_to_a_report(tree):
    assert freeze(tree, now=NOW).ok
    _append_byte(tree / "data" / "reports" / "H-007.json")
    outcome = check_lock(tree)
    assert not outcome.ok
    assert outcome.lines[1:] == ["  - data/reports/H-007.json"]


def test_check_names_added_and_removed_reports(tree):
    assert freeze(tree, now=NOW).ok
    reports = tree / "data" / "reports"
    (reports / "H-025.json").rename(reports / "H-026.json")
    outcome = check_lock(tree)
    assert outcome.lines[1:] == [
        "  - data/reports/H-025.json (removed)",
        "  - data/reports/H-026.json (added)",
    ]


def test_check_ignores_line_ending_changes(tree):
    assert freeze(tree, now=NOW).ok
    path = tree / "prompts" / "plain.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert check_lock(tree).ok


def test_crlf_and_lf_hash_identically(tmp_path):
    lf, crlf = tmp_path / "lf.md", tmp_path / "crlf.md"
    lf.write_bytes(b"line one\nline two\n")
    crlf.write_bytes(b"line one\r\nline two\r\n")
    assert normalized_sha256(lf) == normalized_sha256(crlf)
    other = tmp_path / "other.md"
    other.write_bytes(b"line one\nline two!\n")
    assert normalized_sha256(other) != normalized_sha256(lf)


def test_dataset_hash_is_order_independent():
    assert dataset_hash({"b.json": "2", "a.json": "1"}) == dataset_hash(
        {"a.json": "1", "b.json": "2"}
    )


# CLI


def test_cli_freeze_check_replace(tree, monkeypatch, capsys):
    monkeypatch.setattr(cli, "FREEZE_ROOT", tree)
    assert cli.main(["freeze", "--check"]) == 1
    assert cli.main(["freeze"]) == 0
    assert "freeze: wrote data/prompts.lock.json" in capsys.readouterr().out
    assert cli.main(["freeze", "--check"]) == 0
    assert cli.main(["freeze"]) == 1
    assert "already exists; pass --replace" in capsys.readouterr().out
    assert cli.main(["freeze", "--replace"]) == 0
    assert "freeze: replaced the existing data/prompts.lock.json" in capsys.readouterr().out
    _append_byte(tree / "prompts" / "structured_output.md")
    assert cli.main(["freeze", "--check"]) == 1
    assert "  - prompts/structured_output.md" in capsys.readouterr().out


def test_cli_freeze_refusal_lists_conditions(tree, monkeypatch, capsys):
    monkeypatch.setattr(cli, "FREEZE_ROOT", tree)
    _taxonomy_draft(tree)
    _manifest_proposed(tree)
    assert cli.main(["freeze"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("freeze refused: 2 unmet condition(s):")
    assert not (tree / LOCK_FILE).exists()
