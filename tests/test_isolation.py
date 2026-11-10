"""Decision 28: the drafting model never sees taxonomy ids or names, planned error types, or any
instruction to include errors. Checked on the exact messages for every spec row.

A brief that trips this test is rewritten; the test is never loosened.
"""

import re

import pytest

from pathqc_eval.draft import build_messages
from pathqc_eval.spec import load_spec
from pathqc_eval.taxonomy import load_taxonomy

SPEC = load_spec()
TAXONOMY = load_taxonomy()
FORBIDDEN_PHRASES = [
    "plant",
    "planted",
    "deliberate",
    "deliberately",
    "introduce an error",
    "include an error",
    "mistake",
    "discrepancy",
]


@pytest.mark.parametrize("row", SPEC.reports, ids=lambda r: r.id)
def test_drafting_messages_are_isolated(row):
    system, user = build_messages(row)
    for label, text in (("system", system), ("user", user)):
        lowered = text.lower()
        for type_id in TAXONOMY.type_ids():
            assert not re.search(rf"\b{re.escape(type_id)}\b", text), f"{label}: id {type_id}"
        for error_type in TAXONOMY.types:
            assert error_type.name.lower() not in lowered, f"{label}: name {error_type.name}"
        for planned in row.planned_error_types:
            assert planned not in text, f"{label}: planned type {planned}"
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in lowered, f"{label}: '{phrase}'"
        assert "error" not in lowered.replace("error-free", ""), f"{label}: 'error'"


@pytest.mark.parametrize("row", SPEC.reports, ids=lambda r: r.id)
def test_user_message_uses_only_allowed_fields(row):
    _, user = build_messages(row)
    assert row.brief in user
    assert row.subject in user
    assert f"{row.sex}, {row.age} years" in user
    assert row.id not in user
    assert row.split not in user.split()
