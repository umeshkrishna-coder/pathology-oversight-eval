"""EVAL-09 A (owner decision, 2026-11-11): the files that tie review items to conditions stay
out of git until the reveal; the owner-facing adjudication files do not."""

import shutil
import subprocess

import pytest

from pathqc_eval.taxonomy import REPO_ROOT

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _ignored(path: str) -> bool:
    found = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", path], cwd=REPO_ROOT, check=False
    )
    assert found.returncode in (0, 1), found
    return found.returncode == 0


@pytest.mark.parametrize("dataset", ["dev", "scored"])
@pytest.mark.parametrize(
    "path",
    [
        "results/{d}/adjudication/adjudication_hidden.json",
        "results/{d}/provisional/score.json",
        "results/{d}/provisional/summary.md",
        "results/{d}/provisional/provisional_log.json",
    ],
)
def test_the_blinding_files_are_ignored(dataset, path):
    assert _ignored(path.format(d=dataset))


@pytest.mark.parametrize("dataset", ["dev", "scored"])
@pytest.mark.parametrize(
    "path",
    [
        "results/{d}/adjudication/adjudication.json",
        "results/{d}/adjudication/adjudication_sheet.md",
        "results/{d}/adjudication/adjudication_log.json",
        "results/{d}/score.json",
        "results/{d}/summary.md",
    ],
)
def test_the_owner_facing_and_final_files_are_not_ignored(dataset, path):
    assert not _ignored(path.format(d=dataset))
