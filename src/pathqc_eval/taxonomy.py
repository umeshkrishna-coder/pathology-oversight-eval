"""Load and validate the error taxonomy stored in data/taxonomy.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from pathqc_eval.schema import Modality, Severity, StrictModel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY_PATH = REPO_ROOT / "data" / "taxonomy.json"

_PREFIX_FOR_MODALITY = {"histopathology": "H", "cbc": "C"}


class SeverityLevel(StrictModel):
    id: Severity
    definition: str


class ErrorType(StrictModel):
    id: str = Field(pattern=r"^[HC]\d+$")
    name: str
    definition: str
    modality: Modality
    # One value, or a list where the draft allows either ("major or minor").
    default_severity: Severity | list[Severity]


class Taxonomy(StrictModel):
    version: str
    status: Literal["draft", "final"]
    severity_levels: list[SeverityLevel]
    types: list[ErrorType]

    @model_validator(mode="after")
    def _check_consistency(self) -> Taxonomy:
        levels = [level.id for level in self.severity_levels]
        if sorted(levels) != ["critical", "major", "minor"]:
            raise ValueError(
                f"severity_levels must be critical, major, minor once each; got {levels}"
            )
        ids = [t.id for t in self.types]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate type ids: {duplicates}")
        for t in self.types:
            if not t.id.startswith(_PREFIX_FOR_MODALITY[t.modality]):
                raise ValueError(
                    f"type {t.id} has modality {t.modality}, which does not match its prefix"
                )
        return self

    def by_id(self) -> dict[str, ErrorType]:
        return {t.id: t for t in self.types}

    def type_ids(self) -> list[str]:
        return [t.id for t in self.types]


def load_taxonomy(path: Path | str = DEFAULT_TAXONOMY_PATH) -> Taxonomy:
    """Read and validate a taxonomy file (data/taxonomy.json by default)."""
    text = Path(path).read_text(encoding="utf-8")
    return Taxonomy.model_validate(json.loads(text))
