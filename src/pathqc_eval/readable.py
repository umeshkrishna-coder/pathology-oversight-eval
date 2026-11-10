"""`pathqc-eval readable <folder>`: a Markdown view of each report JSON in a folder, for the
owner to copy sentences from when filling in the planting sheet (EVAL-02c).

It writes only <folder>/_readable/<id>.md and never writes a report or a draft. It is kept apart
from plant.py, whose only writer is write_outputs (data/reports/).
"""

from __future__ import annotations

import re
from pathlib import Path

from pathqc_eval.io import read_report_json

READABLE_DIR = "_readable"
_REPORT_ID = re.compile(r"[HC]-[0-9]{3}")


def readable_markdown(data: dict) -> str:
    """The id as a heading, then each section name as a heading with its text exactly as
    stored, then one line break."""
    lines = [f"# {data['id']}", ""]
    for name, text in data["sections"].items():
        lines += [f"## {name}", text, ""]
    return "\n".join(lines)


def _readable_content(path: Path) -> tuple[str, bytes]:
    """(id, the readable file's bytes) for the report JSON at path, checked so that the file
    can be made from it; the bytes are encoded before any file is opened."""
    data = read_report_json(path)
    if not (
        isinstance(data, dict)
        and isinstance(data.get("id"), str)
        and isinstance(data.get("sections"), dict)
    ):
        raise ValueError("needs an id and sections")
    # The output file is named from this id: anything but a report id could place it outside
    # <folder>/_readable/.
    if not _REPORT_ID.fullmatch(data["id"]):
        raise ValueError(f"id {data['id']!r} is not a report id such as H-001")
    not_text = [name for name, text in data["sections"].items() if not isinstance(text, str)]
    if not_text:
        raise ValueError(f"section '{not_text[0]}' is not text")
    try:  # a \ud83d-style escape decodes to a lone surrogate, which no file can hold
        content = readable_markdown(data).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"it holds text that cannot be written as UTF-8 ({exc.reason})") from exc
    return data["id"], content


def write_readable(folder: Path) -> tuple[list[str], bool]:
    """Write <folder>/_readable/<id>.md for each report JSON in folder. One line per file; a
    file that cannot be read or written gets a FAIL line and the others still go ahead."""
    lines: list[str] = []
    ok = True
    out = folder / READABLE_DIR
    for path in sorted(p for p in folder.glob("*.json") if p.is_file()):
        try:
            report_id, content = _readable_content(path)
        except (OSError, ValueError, RecursionError) as exc:  # JSONDecodeError is a ValueError
            reason = "JSON nested too deeply" if isinstance(exc, RecursionError) else exc
            lines.append(f"FAIL {path}: cannot make a readable file ({reason})")
            ok = False
            continue
        target = out / f"{report_id}.md"
        try:
            out.mkdir(exist_ok=True)
            target.write_bytes(content)
        except OSError as exc:
            lines.append(f"FAIL {path}: cannot write {target.as_posix()} ({exc})")
            ok = False
            continue
        lines.append(f"wrote {target.as_posix()}")
    if not lines:
        lines.append(f"readable: no report files in {folder.as_posix()}")
    return lines, ok
