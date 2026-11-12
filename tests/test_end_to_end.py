r"""End-to-end rehearsal on invented data (EVAL-05b): plant, validate, freeze, run both
conditions with the fake client, map-list, blind adjudication and score, for the scored split
and for the dev split. Everything happens in a temporary root; no API call is made.

Isolation is checked by watching file access (Python audit events) while each test runs:
nothing is written, created, removed or changed outside the temporary root, and the
repository's .env, data/drafts/, data/reports/, data/specs/, data/taxonomy.json (the root
holds a marked copy) and the owner's prompt texts are never opened. The watch records paths
only; it reads no file. Its limits: audit hooks do not see a child process or a C library's
own file access (sqlite); folder listings are not watched, only opens and changes; and paths
are compared as written, so a junction, a symlink, an 8.3 short name or a UNC share naming
the same file is not recognised (the \\?\, \\.\ and \??\ prefixes and stream suffixes are).
The code under test starts no child process here (the scorer's one `git` call is replaced),
uses no such library and spells no path in those ways.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from conftest import STAND_IN_OWNER_TEXT, rerender

from pathqc_eval import cli
from pathqc_eval import scoring_config as cfg
from pathqc_eval.harness import FakeEvalClient
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.spec import DATASET_SHAPE
from pathqc_eval.taxonomy import REPO_ROOT

DATE = "2026-11-14"
SYNOPTIC_LINES = [
    "Tumour size: 18 mm",
    "Histologic grade: 2",
    "Margins: Clear",
    "Lymphovascular invasion: Absent",
    "Perineural invasion: Absent",
    "Lymph nodes (positive/total): 0/3",
    "pT: pT1c",
    "pN: pN0",
    "Staging edition: AJCC 8th edition",
]
MICRO = "Microscopic description"
SYN = "Synoptic summary"
EMPTY = '{"findings": []}'
RATIONALE = "Invented rationale for the rehearsal."
CONDITIONS = ("plain", "structured")


# 1. The tree: a spec of the real shape and 34 invented drafts


def _rows() -> list[dict]:
    rows, counts = [], {"histopathology": 0, "cbc": 0}
    for (modality, split, clean), n in DATASET_SHAPE.items():
        for _ in range(n):
            counts[modality] += 1
            prefix = "H" if modality == "histopathology" else "C"
            rid = f"{prefix}-{counts[modality]:03d}"
            row = {
                "id": rid,
                "modality": modality,
                "split": split,
                "sex": "female",
                "age": 55,
                "is_clean_control": clean,
                "planned_error_types": [] if clean else [PLAN[rid][0]],
                "brief": "Invented brief for the end-to-end rehearsal; it describes no patient.",
                "brief_status": "approved",
            }
            row["specimen_type" if prefix == "H" else "scenario"] = "Invented subject"
            rows.append(row)
    return rows


def _histo_draft(histo: dict, n: int) -> dict:
    draft = copy.deepcopy(histo)
    draft["sections"] = {
        "Clinical details": f"Invented case number {n}. Lump noted on examination.",
        "Specimen": "Wide local excision, left side.",
        "Gross description": "Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm across.",
        MICRO: (
            "Sections show an invasive tumour of no special type. Tumour measures 18 mm. "
            "Margins are clear."
        ),
        "Immunohistochemistry": "ER: positive in tumour cells.\nPR: positive in tumour cells.",
        "Diagnosis": "Invasive tumour of no special type, grade 2, 18 mm.",
        SYN: "\n".join(SYNOPTIC_LINES),
    }
    draft["errors"] = []
    return draft


def _cbc_draft(cbc: dict, n: int) -> dict:
    draft = copy.deepcopy(cbc)
    values = draft["cbc_values"]
    for name, value in (("Hb", 10.0), ("Hct", 33.0), ("RBC", 3.70), ("MCV", 89.2),
                        ("MCH", 27.0), ("MCHC", 30.3)):  # fmt: skip
        values[name]["value"] = value
    draft["sections"]["Interpretation"] = (
        f"Invented case number {n}. Mild anaemia with normal red cell indices. Platelets are "
        "within the reference range."
    )
    draft["errors"] = []
    return rerender(draft)


# 2. The planting sheet: one error per planted report, every type, both kinds


ERROR_TEXT = "description: Invented error for the rehearsal.\nrationale: Invented rationale.\n"
ENTRIES = {
    "H1": ("major", f"section: {MICRO}\nfind: Tumour measures 18 mm.\n"
                    "replace: The tumour measures 25 mm in the sections.\n"),
    "H2": ("critical", "section: Diagnosis\nfind: grade 2\nreplace: grade 3\n"
                       "quote: Invasive tumour of no special type, grade 3, 18 mm.\n"),
    "H3": ("critical", f"section: {SYN}\nfind: pT: pT1c\nreplace: pT: pT3\n"),
    "H4": ("major", f"section: {SYN}\nfind: Lymph nodes (positive/total): 0/3\n"
                    "replace: Lymph nodes (positive/total): 4/3\n"),
    "H5": ("major", f"section: {MICRO}\nfind: Margins are clear.\n"
                    "replace: Margins are involved by tumour at the deep edge.\n"),
    "H6": ("critical", "section: Immunohistochemistry\nfind: ER: positive in tumour cells.\n"
                       "replace: ER: negative in tumour cells.\n"),
    "H5-omission": ("minor", f"kind: omission\nremove_from: {SYN}\n"
                             "remove: Perineural invasion: Absent\n"
                             "anchor: Lymphovascular invasion: Absent\n"),
    "C1": ("major", "section: Interpretation\nfind: Mild anaemia with normal red cell indices.\n"
                    "replace: Haemoglobin is within the reference range here.\n"),
    "C2": ("minor", "set: MCHC = 41.0\n"),
    "C3-omission": ("critical", "kind: omission\nremove_from: Comment/recommendation\n"
                                "remove: No action needed.\nanchor_analyte: Platelets\n"),
}  # fmt: skip
# EVAL-10 (decision 56): an error with an unchanged other place (the gross size, the other
# side of the contradiction) and one with a changed other place (the Diagnosis gains the pT).
GROSS_SIZE = "a firm lesion 18 mm across"
DIAG_PT3 = "Invasive tumour of no special type, grade 2, 18 mm, pT3."
ENTRIES["H1-also-quote"] = (
    "major",
    ENTRIES["H1"][1] + f"also_section: Gross description\nalso_quote: {GROSS_SIZE}\n",
)
ENTRIES["H3-also-change"] = (
    "critical",
    ENTRIES["H3"][1]
    + "also_section: Diagnosis\nalso_find: grade 2, 18 mm.\nalso_replace: grade 2, 18 mm, pT3.\n",
)
# Report id -> (taxonomy type, entry). H-008 carries a severity override with its reason.
PLAN = {
    "H-001": ("H1", "H1"), "H-002": ("H2", "H2"), "H-003": ("H3", "H3"), "H-004": ("H4", "H4"),
    "H-005": ("H5", "H5"), "H-006": ("H6", "H6"), "H-007": ("H5", "H5-omission"),
    "H-008": ("H1", "H1"), "H-009": ("H2", "H2"), "H-010": ("H3", "H3-also-change"),
    "H-011": ("H4", "H4"),
    "H-012": ("H5", "H5"), "H-013": ("H6", "H6"), "H-014": ("H5", "H5-omission"),
    "H-015": ("H1", "H1-also-quote"), "H-021": ("H1", "H1"), "H-022": ("H3", "H3"),
    "C-001": ("C1", "C1"), "C-002": ("C2", "C2"), "C-003": ("C3", "C3-omission"),
    "C-004": ("C1", "C1"), "C-005": ("C2", "C2"), "C-006": ("C3", "C3-omission"),
    "C-007": ("C1", "C1"), "C-011": ("C2", "C2"),
}  # fmt: skip


def _sheet(rows: list[dict]) -> str:
    parts = ["# Invented planting sheet for the end-to-end rehearsal.\n"]
    for row in rows:
        rid = row["id"]
        parts.append(f"== {rid} ==\nverified: yes\nverified_on: {DATE}\n")
        if rid == "H-016":  # a clean control with a correction that plants nothing
            parts.append(
                "[fix]\nsection: Specimen\nfind: left side\nreplace: left breast\n"
                "note: Invented correction.\n"
            )
        if rid in PLAN:
            type_, entry = PLAN[rid]
            severity, body = ENTRIES[entry]
            extra = ""
            if rid == "H-008":
                severity = "minor"
                extra = "severity_reason: Invented override: the size difference is small.\n"
            parts.append(f"[error]\ntype: {type_}\nseverity: {severity}\n{extra}{ERROR_TEXT}{body}")
    return "\n".join(parts)


# 3. The scripted model


def _finding(category: str, section: str, quote: str, confidence: float = 0.8) -> dict:
    return {
        "quoted_sentence": quote,
        "section": section,
        "category": category,
        "severity": "major",
        "confidence": confidence,
        "rationale": RATIONALE,
    }


PLAIN_WORDS = {
    "H1": "size discrepancy", "H2": "grade unsupported", "H3": "stage wrong",
    "H4": "node count wrong", "H5": "missing element", "H6": "ihc conflict",
    "C1": "value interpretation mismatch", "C2": "index inconsistency",
    "C3": "critical value not flagged",
}  # fmt: skip
CATEGORY_MAP = {words: tid for tid, words in PLAIN_WORDS.items()} | {"wording": "other"}


class Model:
    """Knows each report's planted error and answers by a plan per (condition, report): a
    list of outputs in call order (repeat 1, 2, 3, with attempt 2 right after attempt 1)."""

    def __init__(self, reports: dict[str, dict]) -> None:
        self.reports = reports
        self.marker = {}
        for rid, report in reports.items():
            text = (
                report["sections"].get("Clinical details") or report["sections"]["Interpretation"]
            )
            self.marker[text.split(".")[0]] = rid
        self.plans: dict[tuple[str, str], list[str]] = {}
        self.calls: dict[tuple[str, str], int] = defaultdict(int)

    def report_of(self, user: str) -> str:
        return next(rid for marker, rid in self.marker.items() if marker + "." in user)

    def hit(self, rid: str, condition: str, **change) -> dict:
        err = self.reports[rid]["errors"][0]
        category = err["type"] if condition == "structured" else PLAIN_WORDS[err["type"]]
        return _finding(category, err["section"], err["quoted_sentence"]) | change

    def __call__(self, system: str, user: str) -> str:
        condition = "structured" if "## Error taxonomy" in system else "plain"
        rid = self.report_of(user)
        modality = "histopathology" if rid.startswith("H") else "cbc"
        if condition == "structured":  # the temporary root's stand-in, never the owner's text
            assert STAND_IN_OWNER_TEXT[modality] in system
            assert TAXONOMY_TYPE_TEXT[modality] in system  # the root's copy, not the repo's
        else:  # the plain condition gets no owner text at all
            assert not any(text in system for text in STAND_IN_OWNER_TEXT.values())
        key = (condition, rid)
        plan = self.plans.get(key)
        if plan is None:  # the default: every planted error found, nothing else
            errors = self.reports[rid]["errors"]
            plan = [json.dumps({"findings": [self.hit(rid, condition)] if errors else []})] * 3
        n = self.calls[key]
        self.calls[key] += 1
        return plan[n]


def _out(*findings: dict) -> str:
    return json.dumps({"findings": list(findings)})


def _script_scored(model: Model) -> None:
    """The scored-split events, worked out in test_scored_split's docstring."""
    m, R = model, model.reports
    # plain
    # found in repeat 1 only: 1 of 3 is no majority, so a miss
    m.plans["plain", "H-006"] = [_out(m.hit("H-006", "plain")), EMPTY, EMPTY]
    near = m.hit("H-002", "plain", category=PLAIN_WORDS["H1"])  # right sentence, wrong type
    m.plans["plain", "H-002"] = [_out(near)] * 3
    alarm = _finding("wording", "Specimen", "Wide local excision, left side.")
    m.plans["plain", "H-003"] = [_out(m.hit("H-003", "plain"), alarm)] * 3  # FA, planted
    clean_alarm = _out(alarm | {"quoted_sentence": "Wide local excision, left breast."})
    m.plans["plain", "H-016"] = [clean_alarm, clean_alarm, EMPTY]  # FA in 2 of 3: fails
    odd = m.hit("H-004", "plain", category="odd wording")  # unmapped: review
    m.plans["plain", "H-004"] = [_out(odd), _out(odd), _out(m.hit("H-004", "plain"))]
    # repeat 1 adds a false alarm; repeat 3 is invalid, so the mean is over 2 valid units
    c1 = m.hit("C-001", "plain")
    m.plans["plain", "C-001"] = [_out(c1, alarm), _out(c1), "not json", "still not"]
    # structured
    h1 = m.hit("H-001", "structured")
    m.plans["structured", "H-001"] = [_out(h1, h1)] * 3  # a duplicate in every unit
    partial = m.hit("H-005", "structured", quoted_sentence="Deep edge appears unusual here.")
    m.plans["structured", "H-005"] = [
        _out(m.hit("H-005", "structured")),
        _out(partial),
        _out(m.hit("H-005", "structured")),
    ]  # borderline overlap in repeat 2: review
    elsewhere = m.hit("H-007", "structured", section=MICRO,
                      quoted_sentence="Perineural invasion is not reported.")  # fmt: skip
    m.plans["structured", "H-007"] = [_out(elsewhere)] + [_out(m.hit("H-007", "structured"))] * 2
    m.plans["structured", "C-002"] = ["garbage"] + [_out(m.hit("C-002", "structured"))] * 3
    m.plans["structured", "H-013"] = [EMPTY] * 3  # a miss
    # EVAL-10: in each condition one finding quotes each error's other place
    for cond in CONDITIONS:
        gross = m.hit("H-015", cond, section="Gross description", quoted_sentence=GROSS_SIZE)
        m.plans[cond, "H-015"] = [_out(gross)] + [_out(m.hit("H-015", cond))] * 2
        diag = m.hit("H-010", cond, section="Diagnosis", quoted_sentence=DIAG_PT3)
        main = _out(m.hit("H-010", cond))
        m.plans[cond, "H-010"] = [main, _out(diag), main]
    assert R["H-016"]["sections"]["Specimen"] == "Wide local excision, left breast."


# 4. The flow


def _snapshot(folder: Path) -> dict[str, str]:
    """Contents of a folder inside the temporary root (the drafts), by sha256."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
# Audit event -> positions of the paths it reads and of the paths it creates or changes.
_EVENTS: dict[str, tuple[tuple[int, ...], tuple[int, ...]]] = {
    "os.mkdir": ((), (0,)), "os.rmdir": ((), (0,)), "os.remove": ((), (0,)),
    "os.rename": ((), (0, 1)), "os.replace": ((), (0, 1)), "shutil.rmtree": ((), (0,)),
    "os.truncate": ((), (0,)), "os.utime": ((), (0,)), "os.chmod": ((), (0,)),
    "os.chown": ((), (0,)), "os.symlink": ((0,), (1,)), "os.link": ((0,), (1,)),
    "shutil.copyfile": ((0,), (1,)), "shutil.copymode": ((0,), (1,)),
    "shutil.copystat": ((0,), (1,)), "_winapi.CopyFile2": ((0,), (1,)),
}  # fmt: skip
_WATCHES: list[FileWatch] = []


class FileWatch:
    """Paths opened, written, created or removed while active (audit events; paths only)."""

    def __init__(self) -> None:
        self.reads: set[str] = set()
        self.changes: set[str] = set()

    def see(self, event: str, args: tuple) -> None:
        if event == "open":
            path, mode, flags = args
            if isinstance(path, int):
                return
            name = _norm(path)
            writes = any(c in (mode or "") for c in "wax+") or bool((flags or 0) & _WRITE_FLAGS)
            (self.changes if writes else self.reads).add(name)
        elif event == "_winapi.CreateFile":  # name, access, share, disposition, flags
            name, access, _, disposition = args[:4]
            writes = bool(access & 0x40000000) or disposition in (1, 2, 4, 5)  # GENERIC_WRITE
            (self.changes if writes else self.reads).add(_norm(name))
        elif event in _EVENTS:
            for positions, found in zip(_EVENTS[event], (self.reads, self.changes), strict=True):
                for i in positions:
                    if i < len(args) and isinstance(args[i], (str, bytes, os.PathLike)):
                        found.add(_norm(args[i]))


def _norm(path) -> str:
    """A comparable spelling: absolute, case-folded on Windows, without the \\\\?\\ prefix
    or an NTFS stream suffix (".env::$DATA" is .env). Junctions and symlinks are not resolved:
    resolving would open the file."""
    text = os.fsdecode(path)
    if os.name == "nt":
        text = text.replace("/", "\\")
        for prefix, keep in (("\\\\?\\UNC\\", "\\\\"), ("\\\\?\\", ""), ("\\\\.\\", ""),
                             ("\\??\\", "")):  # fmt: skip
            if text[: len(prefix)].upper() == prefix.upper():
                text = keep + text[len(prefix) :]
                break
        last = text.rfind("\\")
        stream = text.find(":", max(last, 2))  # a colon in the last part names a stream
        if stream != -1:
            text = text[:stream]
    return os.path.normcase(os.path.abspath(text))


def _audit(event: str, args: tuple) -> None:
    if _WATCHES and (event in ("open", "_winapi.CreateFile") or event in _EVENTS):
        try:
            _WATCHES[-1].see(event, args)
        except Exception:  # never let the watch break the operation it watches
            _WATCHES[-1].changes.add(f"<unreadable audit event {event}>")


sys.addaudithook(_audit)  # an audit hook cannot be removed; it is idle while no watch runs

PROTECTED = [REPO_ROOT / ".env", REPO_ROOT / "data" / "drafts", REPO_ROOT / "data" / "reports",
             REPO_ROOT / "data" / "specs", REPO_ROOT / "prompts" / "structured_histopathology.md",
             REPO_ROOT / "prompts" / "structured_cbc.md",
             REPO_ROOT / "data" / "taxonomy.json"]  # the root's copy is used instead  # fmt: skip
COPY_MARK = " (rehearsal copy)"  # added to one type's definition in the root's taxonomy copy
TAXONOMY_TYPE_TEXT: dict[str, str] = {}  # modality -> its marked definition (world fixture)


def _mark_copy(taxonomy: dict) -> dict[str, str]:
    """Mark the first type of each modality in the root's copy."""
    marked: dict[str, str] = {}
    for entry in taxonomy["types"]:
        if entry["modality"] not in marked:
            entry["definition"] += COPY_MARK
            marked[entry["modality"]] = entry["definition"]
    return marked


def _under(path: str, folder: Path | str) -> bool:
    base = _norm(folder)
    return path == base or path.startswith(base + os.sep)


@pytest.fixture
def world(tmp_path, histo, cbc, real_prompts, monkeypatch):
    root = tmp_path
    (root / "data" / "specs").mkdir(parents=True)
    (root / "data" / "drafts").mkdir(parents=True)
    taxonomy = read_report_json(REPO_ROOT / "data" / "taxonomy.json")
    assert taxonomy["status"] == "final"
    TAXONOMY_TYPE_TEXT.update(_mark_copy(taxonomy))
    write_report_json(root / "data" / "taxonomy.json", taxonomy)  # a temporary, marked copy
    real_load = cli.load_taxonomy  # `validate` loads data/taxonomy.json of the repository
    monkeypatch.setattr(cli, "load_taxonomy", lambda path=None: real_load(
        path if path is not None else root / "data" / "taxonomy.json"))  # fmt: skip
    rows = _rows()
    write_report_json(root / "data" / "specs" / "dataset.json", {"version": "1.0", "reports": rows})
    for n, row in enumerate(rows, start=1):
        base = _histo_draft(histo, n) if row["modality"] == "histopathology" else _cbc_draft(cbc, n)
        draft = base | {"id": row["id"], "split": row["split"],
                        "is_clean_control": row["is_clean_control"]}  # fmt: skip
        write_report_json(root / "data" / "drafts" / f"{row['id']}.json", draft)
    (root / "data" / "specs" / "planting.md").write_text(_sheet(rows), encoding="utf-8")
    for name in ("PLANT_ROOT", "FREEZE_ROOT", "RUN_ROOT", "SCORE_ROOT"):
        monkeypatch.setattr(cli, name, root)
    monkeypatch.setattr(cli, "SPEC_PATH", root / "data" / "specs" / "dataset.json")
    monkeypatch.setattr(cli, "RUN_SLEEP", lambda s: None)
    monkeypatch.setattr(cli, "SCORER_COMMIT", lambda: "rehearsal")
    watch = FileWatch()
    _WATCHES.append(watch)
    try:
        yield root
    finally:
        _WATCHES.remove(watch)
    outside = sorted(p for p in watch.changes if not _under(p, root) and p != _norm(os.devnull))
    assert outside == []  # nothing written, created or removed outside the temporary root
    opened = sorted(p for p in watch.reads | watch.changes if any(_under(p, f) for f in PROTECTED))
    assert opened == []  # the owner's files and .env are never opened


def _main(*args: str) -> int:
    return cli.main(list(args))


def _build(root: Path, capsys) -> tuple[dict, dict]:
    """plant, validate, and the drafts' state before and after."""
    drafts_before = _snapshot(root / "data" / "drafts")
    assert _main("plant") == 0, capsys.readouterr().out
    reports_dir = root / "data" / "reports"
    assert _main("validate", str(reports_dir), "--expect", "34", "--expect-clean", "9",
                 "--expect-dev", "4") == 0  # fmt: skip
    for wrong in (["--expect", "33"], ["--expect-clean", "8"], ["--expect-dev", "5"]):
        assert _main("validate", str(reports_dir), *wrong) == 1  # each count can fail too
    assert _snapshot(root / "data" / "drafts") == drafts_before
    reports = {p.stem: read_report_json(p) for p in sorted(reports_dir.glob("*.json"))}
    return reports, drafts_before


def _run(model: Model, dataset: str, condition: str, monkeypatch) -> str:
    run_id = f"{dataset}-{condition}"
    client = FakeEvalClient(model)
    monkeypatch.setattr(cli, "EVAL_CLIENT_FACTORY", lambda: client)
    args = ["run", "--dataset", dataset, "--condition", condition, "--cost-gate", "100",
            "--workers", "1", "--run-id", run_id]  # fmt: skip
    assert _main(*args) == 0
    return run_id


def _fill_sheet(root: Path, dataset: str, verdicts: dict[str, tuple[str, str]]) -> None:
    folder = root / "results" / dataset / "adjudication"
    items = read_report_json(folder / "adjudication.json")["items"]
    by_id = {i["item_id"]: verdicts[(i["report_id"], i["review_reason"])] for i in items}
    out, current = [], None
    for line in (folder / "adjudication_sheet.md").read_text(encoding="utf-8").split("\n"):
        if line.startswith("== "):
            current = line.strip("= ").strip()
        if current in by_id and line == "verdict:":
            line = f"verdict: {by_id[current][0]}"
        elif current in by_id and line == "reason:":
            line = f"reason: {by_id[current][1]}"
        out.append(line)
    (folder / "adjudication_sheet.md").write_text("\n".join(out), encoding="utf-8")


def _value(entry: dict) -> float | None:
    return entry["value"] if "value" in entry else entry["mean"]


def test_scored_split(world, capsys, monkeypatch):
    """Scored split: 30 reports (22 planted, one error each; 8 clean), 3 repeats, 2 conditions.

    Planted errors by type: H1 3 (H-001, H-008, H-015), H2 2, H3 2, H4 2, H5 4 (H-005, H-012
    statements; H-007, H-014 omissions), H6 2, C1 3, C2 2, C3 2 (omissions) = 22.
    Severity weights (H-008 is overridden to minor): H1 2+1+2=5, H2 6, H3 6, H4 4, H5 2+1+2+1=6,
    H6 6, C1 6, C2 2, C3 6 = 47. All confidences are 0.8.

    Plain: every error found in every unit, except H-006 (found in repeat 1 only: 1 of 3 is no
    majority, so missed: H6), H-002 (a near-miss in all 3 units: the right sentence, category
    mapped to H1), H-004 (an unmapped category in repeats 1 and 2: one review item,
    adjudicated detected), C-001 (repeat 3 invalid after two unreadable outputs; detected in
    both valid units; one false alarm in repeat 1). H-003 adds one false alarm per unit; the
    clean H-016 has one false alarm in repeats 1 and 2, so it fails by majority.
    Recall: H2 1/2, H6 1/2, every other type all; overall 20/22. Weighted (47 - 3 - 3) = 41/47.
    False alarms per report (mean over valid units): planted (H-003 1 + C-001 1/2)/22 = 3/44,
    clean (H-016 2/3)/8 = 1/12, all (1 + 1/2 + 2/3)/30 = 13/180. Specificity: 7/8 by
    majority; per unit 22/24.
    Calibration: 60 hits + 3 near-misses (outcome 1) and 6 false alarms (outcome 0), all at
    0.8: Brier (63 x 0.04 + 6 x 0.64)/69 = 6.36/69; ECE |0.8 - 63/69| (one bin).
    Consistency: H-006 agrees in 1 of 3 pairs, every other error in all: (21 + 1/3)/22 =
    32/33, share 21/22; clean controls: H-016 agrees in 1 of 3 pairs, the other 7 in all:
    (1/3 + 7)/8 = 11/12, share 7/8.
    Wilson 95% interval for overall recall, z = 1.959964: 20/22 gives 0.7219 to 0.9747,
    21/22 gives 0.7820 to 0.9919. Per type: 1/2 gives 0.0945 to 0.9055, 2/2 0.3424 to 1,
    3/3 0.4385 to 1, 4/4 0.5101 to 1.

    Structured: every error found in every unit, except H-013 (missed: H6). H-001 gives a
    duplicate in every unit; H-005's repeat 2 quotes only part of the sentence (overlap 0.4:
    one review item, adjudicated near_miss), so H-005 is found in 2 of 3; H-007's repeat 1
    names the omission under another section (one review item, adjudicated detected); C-002's
    repeat 1 is valid on its second attempt.
    Recall: H6 1/2, every other type all; overall 21/22. Weighted 44/47. No false alarms:
    0, 0, 0. Specificity 8/8 and 24/24. Calibration: 66 findings, all outcome 1: Brier 0.04,
    ECE 0.2. Consistency: H-005 agrees in 1 of 3 pairs, the rest in all: (21 + 1/3)/22 =
    32/33, share 21/22; clean controls 1.0, 1.0.

    Structured minus plain, over all 30 reports: recall +1/22; false alarms -13/180;
    specificity (by majority) 8/8 - 7/8 = +1/8. Review items: 3 (2 detected, 1 near_miss).

    Recall by severity (EVAL-09 G): critical 8 (H2, H3, H6 and C3, two each), major 9 (H-001,
    H-015, H4 2, H-005, H-012, C1 3), minor 5 (H-008 overridden, H-007, H-014, C2 2). Plain
    misses H-002 (H2) and H-006 (H6), both critical: critical 6/8 (Wilson 0.4093 to 0.9285),
    major 9/9 (0.7009 to 1), minor 5/5 (0.5655 to 1). Structured misses H-013 (H6, critical):
    critical 7/8 (0.5291 to 0.9776), major 9/9, minor 5/5.
    EVAL-09 C (an unmapped finding in a report with an omission error goes to review for it)
    changes none of these numbers: no report with an omission error (H-007, H-014, C-003,
    C-006) gets an unmapped finding here; the one unmapped category is in H-004 (a statement
    error), which was already a review item.
    The bootstrap intervals are not worked by hand; they are pinned as the seeded scorer gives
    them, so that a change to the resampling shows.

    Other places (EVAL-10, decision 56): H-015's H1 error names the unchanged gross size
    ("a firm lesion 18 mm across", Gross description) as its other place, and H-010's H3 error
    changes the Diagnosis too ("Invasive tumour of no special type, grade 2, 18 mm, pT3."). In
    both conditions H-015's repeat 1 and H-010's repeat 2 quote the other place instead of the
    main sentence, with the right category: each is a hit through that place (overlap 1.0).
    So no number above changes: these four findings count exactly as the main sentence would.
    Without decision 56 each would be a false alarm and both errors would be found in 2 of 3
    units: still detected by majority, but plain false alarms per planted report would rise
    from 3/44 to (1 + 1/2 + 1/3 + 1/3)/22 = 13/132, structured from 0 to (2/3)/22 = 1/33,
    calibration would gain four outcomes of 0, and repeat consistency would fall."""
    root = world
    reports, drafts_before = _build(root, capsys)
    assert _main("freeze") == 0 and _main("freeze", "--check") == 0
    model = Model(reports)
    _script_scored(model)
    plain, structured = (_run(model, "scored", c, monkeypatch) for c in CONDITIONS)

    assert _main("map-list", "--runs", plain, structured) == 0
    listed = read_report_json(root / "results" / "scored" / "category_strings.json")
    assert {c["category"]: c["mapped"] for c in listed["categories"]}["odd wording"] is False
    write_report_json(
        root / "data" / "category_map.json",
        {"version": "1.0", "status": "approved", "map": CATEGORY_MAP},
    )
    assert cfg.OWNER_CONFIRMED is True  # the owner's confirmation (EVAL-09 G)
    assert _main("adjudicate", "prepare", "--dataset", "scored", "--runs", plain, structured) == 0
    _assert_blind(root, "scored", [plain, structured])
    _fill_sheet(root, "scored", {
        ("H-004", "unmapped_category"): ("detected", "the node count is the planted error"),
        ("H-005", "borderline_overlap"): ("near_miss", "the deep margin, not the sentence"),
        ("H-007", "omission_other_section"): ("detected", "the missing PNI is the omission"),
    })  # fmt: skip
    assert _main("adjudicate", "apply", "--dataset", "scored") == 0
    assert _main("score", "--dataset", "scored", "--runs", plain, structured) == 0

    out = root / "results" / "scored"
    score = read_report_json(out / "score.json")
    p, s = score["metrics"]["plain"], score["metrics"]["structured"]
    recall = {c: {t: (v["k"], v["n"]) for t, v in m["per_type_recall"].items()}
              for c, m in (("plain", p), ("structured", s))}  # fmt: skip
    full = {"H1": (3, 3), "H2": (2, 2), "H3": (2, 2), "H4": (2, 2), "H5": (4, 4),
            "H6": (2, 2), "C1": (3, 3), "C2": (2, 2), "C3": (2, 2)}  # fmt: skip
    assert recall["plain"] == full | {"H2": (1, 2), "H6": (1, 2)}
    assert recall["structured"] == full | {"H6": (1, 2)}
    assert (p["overall_recall"]["k"], p["overall_recall"]["n"]) == (20, 22)
    assert (s["overall_recall"]["k"], s["overall_recall"]["n"]) == (21, 22)
    weighted = {c: (m["severity_weighted_recall"]["detected_weight"],
                    m["severity_weighted_recall"]["planted_weight"])
                for c, m in (("plain", p), ("structured", s))}  # fmt: skip
    assert weighted == {"plain": (41, 47), "structured": (44, 47)}
    rows = {(f["condition"], f["report_id"], f["repeat"], f["finding_index"]): f
            for f in score["findings"]}  # fmt: skip
    for cond in CONDITIONS:  # EVAL-10: the findings on other places are hits
        for key, section in ((("H-015", 1), "Gross description"), (("H-010", 2), "Diagnosis")):
            row = rows[(cond, *key, 1)]
            assert (row["outcome"], row["error_id"], row["section"], row["overlap"]) == (
                "hit", f"{key[0]}-E1", section, 1.0,
            )  # fmt: skip
    built = {rid: read_report_json(root / "data" / "reports" / f"{rid}.json")["errors"][0]
             for rid in ("H-010", "H-015")}  # fmt: skip
    assert built["H-015"]["other_places"] == [
        {"section": "Gross description", "quoted_sentence": GROSS_SIZE}
    ]
    assert built["H-010"]["other_places"] == [{"section": "Diagnosis", "quoted_sentence": DIAG_PT3}]
    by_severity = {c: {k: (v["k"], v["n"], [round(x, 4) for x in v["interval"]])
                       for k, v in m["recall_by_severity"].items()}
                   for c, m in (("plain", p), ("structured", s))}  # fmt: skip
    major, minor = (9, 9, [0.7009, 1.0]), (5, 5, [0.5655, 1.0])
    assert by_severity == {
        "plain": {"critical": (6, 8, [0.4093, 0.9285]), "major": major, "minor": minor},
        "structured": {"critical": (7, 8, [0.5291, 0.9776]), "major": major, "minor": minor},
    }
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "| Critical | 6/8 = 75.0% (95% CI 40.9%–92.9%) | 7/8 = 87.5% (95% CI 52.9%–97.8%) |" in (
        summary
    )
    wilson = {(1, 2): [0.0945, 0.9055], (2, 2): [0.3424, 1.0], (3, 3): [0.4385, 1.0],
              (4, 4): [0.5101, 1.0]}  # fmt: skip
    for m in (p, s):
        for tid, v in m["per_type_recall"].items():
            assert [round(x, 4) for x in v["interval"]] == wilson[(v["k"], v["n"])], tid
    assert [round(x, 4) for x in p["overall_recall"]["interval"]] == [0.7219, 0.9747]
    assert [round(x, 4) for x in s["overall_recall"]["interval"]] == [0.782, 0.9919]
    fa = {k: _value(v) for k, v in p["false_alarms_per_report"].items()}
    assert fa == pytest.approx({"planted": 3 / 44, "clean": 1 / 12, "all": 13 / 180}, abs=1e-6)
    assert {k: _value(v) for k, v in s["false_alarms_per_report"].items()} == {
        "planted": 0.0, "clean": 0.0, "all": 0.0,
    }  # fmt: skip
    spec = {c: {k: (m["specificity"][k]["k"], m["specificity"][k]["n"]) for k in m["specificity"]}
            for c, m in (("plain", p), ("structured", s))}  # fmt: skip
    assert spec == {"plain": {"by_majority": (7, 8), "per_unit": (22, 24)},
                    "structured": {"by_majority": (8, 8), "per_unit": (24, 24)}}  # fmt: skip
    assert p["calibration"]["brier"] == pytest.approx(6.36 / 69, abs=1e-6)
    assert p["calibration"]["ece"] == pytest.approx(abs(0.8 - 63 / 69), abs=1e-6)
    assert p["calibration"]["findings"] == 69
    assert s["calibration"]["brier"] == pytest.approx(0.04, abs=1e-6)
    assert s["calibration"]["ece"] == pytest.approx(0.2, abs=1e-6)
    assert s["calibration"]["findings"] == 66
    for m in (p, s):  # H-006 (plain) and H-005 (structured) agree in 1 of 3 pairs
        planted = m["repeat_consistency"]["planted_errors"]
        assert planted["mean_pairwise_agreement"] == pytest.approx(32 / 33, abs=1e-6)
        assert planted["share_same_in_every_unit"] == pytest.approx(21 / 22, abs=1e-6)
    clean = p["repeat_consistency"]["clean_controls_any_false_alarm"]
    assert clean["mean_pairwise_agreement"] == pytest.approx(11 / 12, abs=1e-6)
    assert clean["share_same_in_every_unit"] == 0.875
    clean = s["repeat_consistency"]["clean_controls_any_false_alarm"]
    assert (clean["mean_pairwise_agreement"], clean["share_same_in_every_unit"]) == (1.0, 1.0)
    comp = score["comparison"]
    assert comp["reports"] == 30 and comp["left_out"] == []
    assert comp["overall_recall"]["difference"] == pytest.approx(1 / 22, abs=1e-6)
    assert comp["false_alarms_per_report"]["difference"] == pytest.approx(-13 / 180, abs=1e-6)
    assert comp["specificity"]["difference"] == pytest.approx(1 / 8, abs=1e-6)
    for key, pinned in BOOTSTRAP_PINNED.items():
        assert comp[key]["interval"] == pytest.approx(pinned, abs=1e-6), key
    counts = score["counts"]
    assert counts["review_items"]["items"] == 3
    assert counts["review_findings"] == 4  # H-004 r1 and r2 (one item), H-005 r2, H-007 r1
    assert counts["review_items"]["verdicts"]["detected"] == 2
    assert counts["review_items"]["verdicts"]["near_miss"] == 1
    by = counts["by_condition"]
    assert (by["plain"]["invalid_units"], by["structured"]["invalid_units"]) == (1, 0)
    assert (by["plain"]["near_misses"], by["structured"]["near_misses"]) == (3, 1)
    assert (by["plain"]["duplicates"], by["structured"]["duplicates"]) == (0, 3)
    assert (by["plain"]["false_alarms"], by["structured"]["false_alarms"]) == (6, 0)
    calls = {c: read_report_json(root / "runs" / r / "results.json")["totals"]["calls"]
             for c, r in (("plain", plain), ("structured", structured))}  # fmt: skip
    assert calls == {"plain": 91, "structured": 91}

    first = {n: (out / n).read_bytes() for n in ("score.json", "summary.md")}
    assert _main("score", "--dataset", "scored", "--runs", plain, structured) == 0
    assert {n: (out / n).read_bytes() for n in ("score.json", "summary.md")} == first
    assert _main("freeze", "--check") == 0
    report = root / "data" / "reports" / "H-001.json"  # the check must also be able to fail
    original = report.read_bytes()
    report.write_bytes(original + b" ")
    assert _main("freeze", "--check") == 1
    report.write_bytes(original)
    assert _main("freeze", "--check") == 0
    assert _snapshot(root / "data" / "drafts") == drafts_before


# Pinned from the seeded scorer (10,000 resamples, seed 20261115); see the docstring.
BOOTSTRAP_PINNED = {"overall_recall": [-0.1, 0.2], "false_alarms_per_report": [-0.161111, 0.0],
                    "specificity": [0.0, 0.4]}  # fmt: skip


def _assert_blind(root: Path, dataset: str, run_ids: list[str]) -> None:
    """The owner-facing files name no condition, run, repeat or model (decision 9): none of
    those words appears, and each item carries only what the findings gave (every scripted
    rationale is the same invented sentence, so nothing can have been added to it)."""
    folder = root / "results" / dataset / "adjudication"
    items = read_report_json(folder / "adjudication.json")["items"]
    assert {i["rationale"] for i in items} == {RATIONALE}
    sheet = (folder / "adjudication_sheet.md").read_text(encoding="utf-8")
    assert [ln for ln in sheet.split("\n") if ln.startswith("# rationale:")] == [
        f"# rationale: {RATIONALE}"
    ] * len(items)
    for name in ("adjudication_sheet.md", "adjudication.json"):
        text = (folder / name).read_text(encoding="utf-8").lower()
        for word in (*CONDITIONS, *run_ids, "repeat", "claude", "sonnet"):
            assert word.lower() not in text, (name, word)


def test_dev_split(world, capsys, monkeypatch):
    """Dev split, no freeze: H-021 (H1), H-022 (H3), C-011 (C2) planted, H-023 clean. Both
    conditions find every error in every unit and nothing else, except that plain gives H-021
    an unmapped category in repeat 1: one review item, adjudicated detected, so it is a hit.
    Recall 3/3 in each (Wilson 0.4385 to 1), per type H1, H3 and C2 1/1 (0.2065 to 1);
    severity-weighted (H1 major 2 + H3 critical 3 + C2 minor 1) 6/6, and by severity
    (EVAL-09 G) critical, major and minor 1/1 each (0.2065 to 1); no false alarms;
    specificity 1/1 by majority and 3/3 per unit; calibration 9 findings, all outcome 1 at
    0.8: Brier 0.04, ECE 0.2; consistency 1.0 with every unit the same (3 errors; the one
    clean control too); differences 0 with bootstrap intervals [0, 0]; review items 1."""
    root = world
    reports, drafts_before = _build(root, capsys)
    model = Model(reports)
    odd = model.hit("H-021", "plain", category="odd wording")
    model.plans["plain", "H-021"] = [_out(odd)] + [_out(model.hit("H-021", "plain"))] * 2
    plain, structured = (_run(model, "dev", c, monkeypatch) for c in CONDITIONS)
    assert _main("map-list", "--runs", plain, structured) == 0
    write_report_json(
        root / "data" / "category_map.json",
        {"version": "1.0", "status": "approved", "map": CATEGORY_MAP},
    )
    assert _main("adjudicate", "prepare", "--dataset", "dev", "--runs", plain, structured) == 0
    _assert_blind(root, "dev", [plain, structured])
    _fill_sheet(root, "dev", {("H-021", "unmapped_category"): ("detected", "the size")})
    assert _main("adjudicate", "apply", "--dataset", "dev") == 0
    assert _main("score", "--dataset", "dev", "--runs", plain, structured) == 0
    out = root / "results" / "dev"
    first = {n: (out / n).read_bytes() for n in ("score.json", "summary.md")}
    assert _main("score", "--dataset", "dev", "--runs", plain, structured) == 0
    assert {n: (out / n).read_bytes() for n in ("score.json", "summary.md")} == first
    score = read_report_json(out / "score.json")
    assert score["counts"]["review_items"]["verdicts"]["detected"] == 1
    for condition in ("plain", "structured"):
        m = score["metrics"][condition]
        assert (m["overall_recall"]["k"], m["overall_recall"]["n"]) == (3, 3)
        fa = m["false_alarms_per_report"]
        assert [fa[k]["mean"] for k in ("planted", "clean", "all")] == [0.0, 0.0, 0.0]
        assert (m["specificity"]["by_majority"]["k"], m["specificity"]["by_majority"]["n"]) == (
            1, 1,
        )  # fmt: skip
    for key in ("overall_recall", "false_alarms_per_report", "specificity"):
        assert score["comparison"][key]["difference"] == 0.0, key
    assert score["counts"]["review_findings"] == 1
    assert score["counts"]["review_items"]["items"] == 1
    for condition in ("plain", "structured"):
        m = score["metrics"][condition]
        assert {t: (v["k"], v["n"]) for t, v in m["per_type_recall"].items() if v["n"]} == {
            "H1": (1, 1), "H3": (1, 1), "C2": (1, 1),
        }  # fmt: skip
        for v in m["per_type_recall"].values():
            assert v["interval"] is None if not v["n"] else (
                [round(x, 4) for x in v["interval"]] == [0.2065, 1.0]
            )  # fmt: skip
        assert [round(x, 4) for x in m["overall_recall"]["interval"]] == [0.4385, 1.0]
        weighted = m["severity_weighted_recall"]
        assert (weighted["detected_weight"], weighted["planted_weight"]) == (6, 6)
        assert {
            k: (v["k"], v["n"], [round(x, 4) for x in v["interval"]])
            for k, v in m["recall_by_severity"].items()
        } == {k: (1, 1, [0.2065, 1.0]) for k in ("critical", "major", "minor")}
        assert (m["specificity"]["per_unit"]["k"], m["specificity"]["per_unit"]["n"]) == (3, 3)
        cal = m["calibration"]
        assert cal["findings"] == 9
        assert cal["brier"] == pytest.approx(0.04, abs=1e-6)
        assert cal["ece"] == pytest.approx(0.2, abs=1e-6)
        for key, n in (("planted_errors", 3), ("clean_controls_any_false_alarm", 1)):
            c = m["repeat_consistency"][key]
            got = (c["n"], c["mean_pairwise_agreement"], c["share_same_in_every_unit"])
            assert got == (n, 1.0, 1.0), key
    for key in ("overall_recall", "false_alarms_per_report", "specificity"):
        assert score["comparison"][key]["interval"] == [0.0, 0.0], key
    by = score["counts"]["by_condition"]
    for key in ("false_alarms", "near_misses", "duplicates", "invalid_units"):
        assert (by["plain"][key], by["structured"][key]) == (0, 0), key
    assert not (root / "data" / "prompts.lock.json").exists()
    assert _snapshot(root / "data" / "drafts") == drafts_before
