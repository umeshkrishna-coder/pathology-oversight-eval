import json

import pytest
from pydantic import ValidationError

from pathqc_eval.taxonomy import DEFAULT_TAXONOMY_PATH, Taxonomy


def test_taxonomy_loads_with_nine_types(taxonomy):
    assert taxonomy.status == "draft"
    assert taxonomy.version == "0.1"
    assert taxonomy.type_ids() == ["H1", "H2", "H3", "H4", "H5", "H6", "C1", "C2", "C3"]
    assert [lvl.id for lvl in taxonomy.severity_levels] == ["critical", "major", "minor"]


def test_taxonomy_modalities_and_list_severities(taxonomy):
    types = taxonomy.by_id()
    assert {t.modality for t in taxonomy.types if t.id.startswith("H")} == {"histopathology"}
    assert {t.modality for t in taxonomy.types if t.id.startswith("C")} == {"cbc"}
    assert types["H5"].default_severity == ["major", "minor"]
    assert types["C2"].default_severity == ["minor", "major"]


def _raw() -> dict:
    return json.loads(DEFAULT_TAXONOMY_PATH.read_text(encoding="utf-8"))


def test_taxonomy_rejects_duplicate_ids():
    raw = _raw()
    raw["types"].append(dict(raw["types"][0]))
    with pytest.raises(ValidationError, match="duplicate"):
        Taxonomy.model_validate(raw)


def test_taxonomy_rejects_prefix_modality_mismatch():
    raw = _raw()
    raw["types"][0]["modality"] = "cbc"
    with pytest.raises(ValidationError, match="prefix"):
        Taxonomy.model_validate(raw)


def test_taxonomy_rejects_extra_fields():
    raw = _raw()
    raw["types"][0]["extra"] = 1
    with pytest.raises(ValidationError):
        Taxonomy.model_validate(raw)
