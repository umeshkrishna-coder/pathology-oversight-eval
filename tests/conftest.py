"""Shared fixtures: one synthetic histopathology report and one synthetic CBC report.

Content is synthetic test data only; it describes no patient and is not part of the dataset.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues
from pathqc_eval.taxonomy import REPO_ROOT, Taxonomy, load_taxonomy

FIXTURES = Path(__file__).parent / "fixtures"
# Stand-ins for the owner's texts: tests never read prompts/structured_*.md.
STAND_IN_OWNER_TEXT = {
    "histopathology": "STAND-IN OWNER TEXT (histopathology). The owner's PathQC prompt goes here.",
    "cbc": "STAND-IN OWNER TEXT (cbc). The owner's CBC review checklist goes here.",
}


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.fixture(autouse=True)
def _no_model_api(monkeypatch):
    """No test can reach a model API (EVAL-04): the key is blanked and dotenv loading is off,
    so cli.main cannot load the key from .env and every real client refuses to construct."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")


@pytest.fixture
def fixed_taxonomy() -> Taxonomy:
    """Copy of the draft taxonomy v0.1, so goldens do not move when the owner edits it."""
    return load_taxonomy(FIXTURES / "taxonomy.json")


def write_prompts(folder: Path, plain: str, output: str) -> Path:
    """A prompts folder with the given plain and output texts and the stand-in owner texts."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "plain.md").write_text(plain, encoding="utf-8", newline="\n")
    (folder / "structured_output.md").write_text(output, encoding="utf-8", newline="\n")
    for modality, text in STAND_IN_OWNER_TEXT.items():
        (folder / f"structured_{modality}.md").write_text(
            text + "\n", encoding="utf-8", newline="\n"
        )
    return folder


@pytest.fixture
def real_prompts(tmp_path) -> Path:
    """The repo's plain and output prompts (agent-written) with stand-in owner texts."""
    folder = tmp_path / "prompts"
    folder.mkdir()
    for name in ("plain.md", "structured_output.md"):
        shutil.copyfile(REPO_ROOT / "prompts" / name, folder / name)
    write_prompts(
        folder,
        (folder / "plain.md").read_text(encoding="utf-8"),
        (folder / "structured_output.md").read_text(encoding="utf-8"),
    )
    manifest = {
        name: {"file": f"prompts/{name}.md", "status": "approved"}
        for name in ("plain", "structured_output", "structured_histopathology", "structured_cbc")
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder


def _analyte(value: float, unit: str, low: float, high: float) -> dict:
    return {"value": value, "unit": unit, "ref_low": low, "ref_high": high}


def _provenance() -> dict:
    return {
        "drafted_by": "claude-haiku-5-5",
        "drafted_at": "2026-11-04",
        "edited_by": "owner",
        "verified": False,
        "verified_at": None,
    }


@pytest.fixture
def taxonomy() -> Taxonomy:
    return load_taxonomy()


@pytest.fixture
def histo() -> dict:
    """Planted report with one H1 error; optional sections (IHC, Comment) absent."""
    return {
        "id": "H-001",
        "modality": "histopathology",
        "split": "dev",
        "specimen_type": "Test specimen, wide local excision",
        "sections": {
            "Clinical details": "Synthetic test case. Lump noted on examination.",
            "Specimen": "Wide local excision, left side.",
            "Gross description": "Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm across.",
            "Microscopic description": "Sections show an invasive tumour. Tumour measures 25 mm.",
            "Diagnosis": "Invasive tumour, grade 2.",
            "Synoptic summary": "Size 18 mm; grade 2; margins clear; LVI absent; PNI absent; "
            "nodes 0/3; pT1c pN0.\nStaging edition: AJCC 8th edition",
        },
        "is_clean_control": False,
        "errors": [
            {
                "error_id": "H-001-E1",
                "type": "H1",
                "section": "Microscopic description",
                "quoted_sentence": "Tumour measures 25 mm.",
                "severity": "major",
                "description": "Microscopic size contradicts the 18 mm gross size.",
                "rationale": "Gross, microscopy and synoptic must agree on size.",
            }
        ],
        "provenance": _provenance(),
        "schema_version": "1.0",
    }


def rerender(report: dict) -> dict:
    """Set a cbc report dict's Values text to the text rendered from its cbc_values."""
    values = CBCValues.model_validate(report["cbc_values"])
    report["sections"]["Values"] = render_cbc_values(values)
    return report


@pytest.fixture
def cbc() -> dict:
    """Clean control with fixed units, consistent derived indices and rendered Values text."""
    report = {
        "id": "C-001",
        "modality": "cbc",
        "split": "scored",
        "scenario": "Synthetic routine check",
        "sections": {
            "Values": "",
            "Interpretation": "All values within reference ranges.",
            "Comment/recommendation": "No action needed.",
        },
        "cbc_values": {
            "Hb": _analyte(14.0, "g/dL", 13.0, 17.0),
            "RBC": _analyte(4.70, "x10^12/L", 4.5, 5.5),
            "Hct": _analyte(42.0, "%", 40.0, 50.0),
            "MCV": _analyte(89.4, "fL", 83.0, 101.0),
            "MCH": _analyte(29.8, "pg", 27.0, 32.0),
            "MCHC": _analyte(33.3, "g/dL", 31.5, 34.5),
            "RDW": _analyte(13.0, "%", 11.6, 14.0),
            "WBC": _analyte(8.0, "x10^9/L", 4.0, 11.0),
            "Neutrophils_pct": _analyte(60.0, "%", 40.0, 80.0),
            "Neutrophils_abs": _analyte(4.8, "x10^9/L", 2.0, 7.0),
            "Lymphocytes_pct": _analyte(30.0, "%", 20.0, 40.0),
            "Lymphocytes_abs": _analyte(2.4, "x10^9/L", 1.0, 3.0),
            "Monocytes_pct": _analyte(6.0, "%", 2.0, 10.0),
            "Monocytes_abs": _analyte(0.48, "x10^9/L", 0.2, 1.0),
            "Eosinophils_pct": _analyte(3.0, "%", 1.0, 6.0),
            "Eosinophils_abs": _analyte(0.24, "x10^9/L", 0.02, 0.5),
            "Basophils_pct": _analyte(1.0, "%", 0.0, 2.0),
            "Basophils_abs": _analyte(0.08, "x10^9/L", 0.02, 0.1),
            "Platelets": _analyte(250.0, "x10^9/L", 150.0, 410.0),
            "MPV": _analyte(10.0, "fL", 7.5, 11.5),
        },
        "is_clean_control": True,
        "errors": [],
        "provenance": _provenance(),
        "schema_version": "1.0",
    }
    return rerender(report)
