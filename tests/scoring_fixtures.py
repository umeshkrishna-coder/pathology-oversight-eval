"""Invented trees for the scorer tests (EVAL-05): reports, runs and category maps written into
temporary folders. Never reads data/reports/, data/drafts/ or runs/ of the repository."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from conftest import FIXTURES

from pathqc_eval.freeze import compute_lock
from pathqc_eval.harness import run_hashes
from pathqc_eval.io import write_report_json

MODEL = "claude-sonnet-5-5"
SYNOPTIC = "Size 18 mm; grade 2; margins clear; LVI absent; PNI absent; nodes 0/3; pT1c pN0."
DIAGNOSIS = "Invasive tumour, grade 2."
CLOCK_START = datetime(2026, 11, 16, 9, 0, 0, tzinfo=UTC)


def taxonomy_data(final: bool = False) -> dict:
    data = json.loads((FIXTURES / "taxonomy.json").read_text(encoding="utf-8"))
    return data | {"status": "final"} if final else data


def report(template: dict, report_id: str, split: str, errors: list[dict] | None = None) -> dict:
    data = copy.deepcopy(template)
    data["id"] = report_id
    data["split"] = split
    if errors is not None:
        data["errors"] = errors
        data["is_clean_control"] = not errors
    for i, err in enumerate(data["errors"], start=1):
        err["error_id"] = f"{report_id}-E{i}"
    return data


def error(type_: str, section: str, quote: str, severity: str, kind: str = "statement") -> dict:
    return {
        "error_id": "X-000-E1",
        "type": type_,
        "section": section,
        "quoted_sentence": quote,
        "severity": severity,
        "description": f"Invented {type_} error for a test.",
        "rationale": "Test data.",
        "kind": kind,
    }


def standard_reports(histo: dict, cbc: dict, split: str = "dev") -> list[dict]:
    """H-001: one H1 (major). H-002: an H3 statement (critical) and an H5 omission anchored
    on the Diagnosis line (minor). C-001: a clean control."""
    return [
        report(histo, "H-001", split),
        report(
            histo,
            "H-002",
            split,
            [
                error("H3", "Synoptic summary", SYNOPTIC, "critical"),
                error("H5", "Diagnosis", DIAGNOSIS, "minor", kind="omission"),
            ],
        ),
        report(cbc, "C-001", split, []),
    ]


def write_tree(root: Path, reports: list[dict], final: bool = False) -> Path:
    (root / "data" / "reports").mkdir(parents=True, exist_ok=True)
    write_report_json(root / "data" / "taxonomy.json", taxonomy_data(final))
    for data in reports:
        write_report_json(root / "data" / "reports" / f"{data['id']}.json", data)
    return root


def finding(category: str, section: str, quote: str, confidence=0.8, severity="major") -> dict:
    return {
        "quoted_sentence": quote,
        "section": section,
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "rationale": f"Invented rationale ({category}).",
    }


INVALID = "invalid"


def write_run(
    root: Path,
    run_id: str,
    condition: str,
    units: dict[tuple[str, int], list[dict] | str],
    dataset: str = "dev",
    model: str = MODEL,
    dropped: dict[tuple[str, int], int] | None = None,
) -> str:
    """runs/<run_id>/config.json and results.json; a unit is a list of findings or INVALID.
    Hashes are those of the tree as it stands (from the lock for a scored run)."""
    if dataset == "scored":
        hashes = run_hashes(root, "scored", condition)
    else:
        current = compute_lock(root)
        hashes = {
            "dataset_hash": current["dataset"]["hash"],
            "prompt_hash": "b" * 64,
            "taxonomy_hash": current["files"]["data/taxonomy.json"],
            "lock_created_at": None,
        }
    config = {
        "run_id": run_id,
        "dataset": dataset,
        "condition": condition,
        "model": MODEL,
        "sampling": "default",
        "effort": "default",
        "max_tokens": 16000,
        "repeats": 3,
        **hashes,
        "created_at": "2026-11-16T09:30:00Z",
        "cost_gate_usd": 5.0,
        "sdk_version": "2.4.0",
    }
    result_units = []
    for (report_id, repeat), found in sorted(units.items()):
        valid = found != INVALID
        result_units.append(
            {
                "report_id": report_id,
                "repeat": repeat,
                "status": "valid" if valid else "invalid",
                "attempts": 1 if valid else 2,
                "findings": found if valid else [],
                "dropped_count": (dropped or {}).get((report_id, repeat), 0),
                "model_returned": model,
                "input_tokens": 2500,
                "output_tokens": 400,
                "cost_usd": 0.009,
            }
        )
    folder = root / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    write_report_json(folder / "config.json", config)
    write_report_json(
        folder / "results.json",
        {
            "run_id": run_id,
            "dataset": dataset,
            "condition": condition,
            "units": result_units,
            "totals": {},
        },
    )
    return run_id


def all_units(report_ids, findings=None) -> dict:
    """Every (report, repeat) with no findings, or with the given findings."""
    return {(rid, rep): list(findings or []) for rid in report_ids for rep in (1, 2, 3)}


def write_map(root: Path, mapping: dict, status: str = "proposed", version: str = "0.1") -> None:
    write_report_json(
        root / "data" / "category_map.json", {"version": version, "status": status, "map": mapping}
    )


class Clock:
    """A clock that moves one minute on every reading."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return CLOCK_START.replace(minute=self.calls)
