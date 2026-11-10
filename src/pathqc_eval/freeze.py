"""Freeze (decision 6): hash the taxonomy, the evaluation prompts and the dataset into
data/prompts.lock.json, and check those hashes before a scored run.

Hashes are sha256 over file bytes with CRLF normalised to LF (decision 21). The dataset hash is
sha256 over the sorted lines `<file name>:<sha256>\\n`, one per data/reports/*.json.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.prompting import (
    OWNER_TEXT_PLACEHOLDER,
    PLAIN_PROMPT,
    STRUCTURED_OUTPUT_PROMPT,
    STRUCTURED_OWNER_PROMPTS,
    build_eval_messages,
    check_eval_isolation,
)
from pathqc_eval.schema import StrictModel
from pathqc_eval.spec import CLEAN_TOTAL, DATASET_SHAPE, TOTAL_REPORTS
from pathqc_eval.taxonomy import REPO_ROOT, load_taxonomy
from pathqc_eval.validate import validate_reports

TAXONOMY_FILE = "data/taxonomy.json"
REPORTS_DIR = "data/reports"
LOCK_FILE = "data/prompts.lock.json"
MANIFEST_FILE = "prompts/manifest.json"
# Manifest entry name -> prompt file, relative to the repo root.
PROMPT_FILES: dict[str, str] = {
    "plain": f"prompts/{PLAIN_PROMPT}",
    "structured_output": f"prompts/{STRUCTURED_OUTPUT_PROMPT}",
    "structured_histopathology": f"prompts/{STRUCTURED_OWNER_PROMPTS['histopathology']}",
    "structured_cbc": f"prompts/{STRUCTURED_OWNER_PROMPTS['cbc']}",
}
FROZEN_FILES = (TAXONOMY_FILE, *PROMPT_FILES.values(), MANIFEST_FILE)
DEV_TOTAL = sum(n for (_, split, _), n in DATASET_SHAPE.items() if split == "dev")  # 4


class ManifestEntry(StrictModel):
    file: str
    status: Literal["proposed", "approved"]


def normalized_sha256(path: Path | str) -> str:
    """sha256 of the file's bytes with CRLF replaced by LF."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def report_hashes(root: Path) -> dict[str, str]:
    return {p.name: normalized_sha256(p) for p in sorted((root / REPORTS_DIR).glob("*.json"))}


def dataset_hash(hashes: dict[str, str]) -> str:
    lines = "".join(f"{name}:{digest}\n" for name, digest in sorted(hashes.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def compute_lock(root: Path) -> dict:
    """Everything the lock records except created_at (missing files hash as null)."""
    files = {
        rel: normalized_sha256(root / rel) if (root / rel).is_file() else None
        for rel in FROZEN_FILES
    }
    reports = report_hashes(root)
    try:
        version = load_taxonomy(root / TAXONOMY_FILE).version
    except (OSError, ValueError):
        version = None
    return {
        "taxonomy_version": version,
        "files": files,
        "dataset": {
            "hash": dataset_hash(reports),
            "report_count": len(reports),
            "reports": reports,
        },
    }


def _manifest_problems(root: Path) -> list[str]:
    path = root / MANIFEST_FILE
    try:
        raw = read_report_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{MANIFEST_FILE} cannot be read ({exc})"]
    if not isinstance(raw, dict):
        return [f"{MANIFEST_FILE} is not a JSON object"]
    problems = []
    for name, expected_file in PROMPT_FILES.items():
        if name not in raw:
            problems.append(f"{MANIFEST_FILE}: entry '{name}' is missing")
            continue
        try:
            entry = ManifestEntry.model_validate(raw[name])
        except ValidationError:
            problems.append(f"{MANIFEST_FILE}: entry '{name}' is malformed")
            continue
        if entry.file != expected_file:
            problems.append(
                f"{MANIFEST_FILE}: entry '{name}' names {entry.file}, expected {expected_file}"
            )
        if entry.status != "approved":
            problems.append(f"{MANIFEST_FILE}: entry '{name}' is {entry.status}, not approved")
    return problems


def freeze_problems(root: Path, replace: bool = False) -> list[str]:
    """Every unmet freeze condition (empty when the freeze may proceed)."""
    problems: list[str] = []
    if (root / LOCK_FILE).exists() and not replace:
        problems.append(f"{LOCK_FILE} already exists; pass --replace to overwrite it")

    taxonomy = None
    try:
        taxonomy = load_taxonomy(root / TAXONOMY_FILE)
    except (OSError, ValueError) as exc:
        problems.append(f"{TAXONOMY_FILE} cannot be loaded ({exc})")
    if taxonomy is not None and taxonomy.status != "final":
        problems.append(f"taxonomy status is '{taxonomy.status}', not 'final'")

    problems += _manifest_problems(root)

    prompts_ok = True
    for rel in PROMPT_FILES.values():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
            prompts_ok = False
        elif OWNER_TEXT_PLACEHOLDER in path.read_text(encoding="utf-8"):
            problems.append(f"{rel} still contains {OWNER_TEXT_PLACEHOLDER}")

    if taxonomy is None:
        return problems
    result = validate_reports(
        root / REPORTS_DIR,
        taxonomy,
        expect=TOTAL_REPORTS,
        expect_clean=CLEAN_TOTAL,
        expect_dev=DEV_TOTAL,
    )
    if not result.ok:
        details = "".join(f"\n      {failure}" for failure in result.failures)
        problems.append(
            f"validate {REPORTS_DIR} --expect {TOTAL_REPORTS} --expect-clean {CLEAN_TOTAL} "
            f"--expect-dev {DEV_TOTAL} fails ({len(result.failures)} failure(s)):{details}"
        )

    for report in result.reports:
        prov = report.provenance
        if not (prov.verified and prov.verified_at is not None):
            problems.append(f"{report.id}: provenance is not verified with a verified_at date")

    if prompts_ok:
        for report in result.reports:
            for condition in ("plain", "structured"):
                system, user = build_eval_messages(report, condition, taxonomy, root / "prompts")
                problems += [
                    f"{report.id} ({condition}): {breach}"
                    for breach in check_eval_isolation(report, condition, system, user, taxonomy)
                ]
    return problems


@dataclass
class FreezeOutcome:
    ok: bool
    lines: list[str] = field(default_factory=list)


def freeze(
    root: Path = REPO_ROOT, replace: bool = False, now: datetime | None = None
) -> FreezeOutcome:
    """Write the lock if every condition holds; otherwise list every unmet condition."""
    problems = freeze_problems(root, replace)
    if problems:
        return FreezeOutcome(
            False,
            [f"freeze refused: {len(problems)} unmet condition(s):"]
            + [f"  - {p}" for p in problems],
        )
    lock_path = root / LOCK_FILE
    replaced = lock_path.exists()
    created = (now or datetime.now(UTC)).isoformat(timespec="seconds").replace("+00:00", "Z")
    lock = {"created_at": created, **compute_lock(root)}
    write_report_json(lock_path, lock)
    lines = []
    if replaced:
        lines.append(f"freeze: replaced the existing {LOCK_FILE}")
    lines.append(
        f"freeze: wrote {LOCK_FILE} | taxonomy {lock['taxonomy_version']} | "
        f"{lock['dataset']['report_count']} reports | dataset {lock['dataset']['hash']}"
    )
    return FreezeOutcome(True, lines)


def check_lock(root: Path = REPO_ROOT) -> FreezeOutcome:
    """Recompute every hash and compare with the lock; name each file that differs."""
    lock_path = root / LOCK_FILE
    if not lock_path.is_file():
        return FreezeOutcome(False, [f"freeze --check: FAILED: {LOCK_FILE} does not exist"])
    try:
        lock = read_report_json(lock_path)
        locked_files = dict(lock["files"])
        locked_reports = dict(lock["dataset"]["reports"])
        locked_hash = lock["dataset"]["hash"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return FreezeOutcome(False, [f"freeze --check: FAILED: {LOCK_FILE} is unreadable ({exc})"])
    current = compute_lock(root)
    differ: list[str] = []
    for rel in sorted(set(locked_files) | set(current["files"])):
        if locked_files.get(rel) != current["files"].get(rel):
            differ.append(rel)
    reports = current["dataset"]["reports"]
    for name in sorted(set(locked_reports) | set(reports)):
        if name not in reports:
            differ.append(f"{REPORTS_DIR}/{name} (removed)")
        elif name not in locked_reports:
            differ.append(f"{REPORTS_DIR}/{name} (added)")
        elif locked_reports[name] != reports[name]:
            differ.append(f"{REPORTS_DIR}/{name}")
    if not differ and locked_hash != current["dataset"]["hash"]:
        differ.append(f"{REPORTS_DIR} (dataset hash)")
    if differ:
        return FreezeOutcome(
            False,
            [f"freeze --check: FAILED: {len(differ)} file(s) differ from {LOCK_FILE}:"]
            + [f"  - {d}" for d in differ],
        )
    return FreezeOutcome(
        True,
        [
            f"freeze --check: OK | {len(locked_files)} files and "
            f"{len(locked_reports)} reports match {LOCK_FILE}"
        ],
    )
