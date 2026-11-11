"""Report JSON reading and writing. write_report_json is the package's only JSON writer;
append_jsonl is its only JSON Lines writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_report_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def unique_keys(pairs: list[tuple[str, Any]]) -> dict:
    """json.loads object_pairs_hook: a key given twice in one object is refused, so that a
    later copy cannot silently replace the first."""
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"key '{key[:60]}' is given twice")
        out[key] = value
    return out


def write_report_json(path: Path | str, data: Any) -> None:
    """Indented UTF-8 JSON with LF line endings and exactly one trailing newline.

    The text is encoded before the file is opened, so a value that cannot be written (an
    unpaired surrogate) raises without emptying an existing file."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    Path(path).write_bytes(text.encode("utf-8"))


def append_jsonl(path: Path | str, record: dict[str, Any]) -> None:
    """Append one compact JSON object as a line (UTF-8, LF)."""
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
