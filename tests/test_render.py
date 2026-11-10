import ast
from pathlib import Path

from conftest import rerender

from pathqc_eval import render as render_module
from pathqc_eval.cli import main
from pathqc_eval.io import read_report_json, write_report_json
from pathqc_eval.render import render_cbc_values
from pathqc_eval.schema import CBCValues

GOLDEN_LINES = [
    "Hb: 14.0 g/dL (ref 13.0–17.0)",
    "RBC: 4.70 x10^12/L (ref 4.50–5.50)",
    "Hct: 42.0 % (ref 40.0–50.0)",
    "MCV: 89.4 fL (ref 83.0–101.0)",
    "MCH: 29.8 pg (ref 27.0–32.0)",
    "MCHC: 33.3 g/dL (ref 31.5–34.5)",
    "RDW: 13.0 % (ref 11.6–14.0)",
    "WBC: 8.00 x10^9/L (ref 4.00–11.00)",
    "Neutrophils %: 60.0 % (ref 40.0–80.0)",
    "Neutrophils absolute: 4.80 x10^9/L (ref 2.00–7.00)",
    "Lymphocytes %: 30.0 % (ref 20.0–40.0)",
    "Lymphocytes absolute: 2.40 x10^9/L (ref 1.00–3.00)",
    "Monocytes %: 6.0 % (ref 2.0–10.0)",
    "Monocytes absolute: 0.48 x10^9/L (ref 0.20–1.00)",
    "Eosinophils %: 3.0 % (ref 1.0–6.0)",
    "Eosinophils absolute: 0.24 x10^9/L (ref 0.02–0.50)",
    "Basophils %: 1.0 % (ref 0.0–2.0)",
    "Basophils absolute: 0.08 x10^9/L (ref 0.02–0.10)",
    "Platelets: 250 x10^9/L (ref 150–410)",
    "MPV: 10.0 fL (ref 7.5–11.5)",
]
GOLDEN = "\n".join(GOLDEN_LINES)


def test_render_golden(cbc):
    assert render_cbc_values(CBCValues.model_validate(cbc["cbc_values"])) == GOLDEN


def test_render_has_no_trailing_newline_and_one_line_per_field(cbc):
    text = render_cbc_values(CBCValues.model_validate(cbc["cbc_values"]))
    assert not text.endswith("\n")
    assert len(text.split("\n")) == len(CBCValues.model_fields)


def _inconsistent_mchc(cbc: dict) -> dict:
    # Hb 10.0 / Hct 33.0 x 100 = 30.3 g/dL, but MCHC is stored as 41.0 (a planted C2).
    cbc["cbc_values"]["Hb"]["value"] = 10.0
    cbc["cbc_values"]["Hct"]["value"] = 33.0
    cbc["cbc_values"]["MCHC"]["value"] = 41.0
    return cbc


def test_render_keeps_stored_inconsistent_mchc(cbc):
    text = render_cbc_values(CBCValues.model_validate(_inconsistent_mchc(cbc)["cbc_values"]))
    assert "MCHC: 41.0 g/dL (ref 31.5–34.5)" in text.split("\n")


def test_render_cli_keeps_stored_inconsistent_mchc(tmp_path, cbc):
    path = tmp_path / "C-001.json"
    write_report_json(path, _inconsistent_mchc(cbc))
    assert main(["render", str(path)]) == 0
    data = read_report_json(path)
    assert data["cbc_values"]["MCHC"]["value"] == 41.0
    assert "MCHC: 41.0 g/dL (ref 31.5–34.5)" in data["sections"]["Values"].split("\n")


def test_render_module_has_no_arithmetic():
    tree = ast.parse(Path(render_module.__file__).read_text(encoding="utf-8"))
    ops = [node for node in ast.walk(tree) if isinstance(node, (ast.BinOp, ast.AugAssign))]
    assert ops == []


def test_render_cli_rewrites_stale_values_and_is_idempotent(tmp_path, cbc, capsys):
    path = tmp_path / "C-001.json"
    cbc["sections"]["Values"] = "stale text"
    write_report_json(path, cbc)

    assert main(["render", str(tmp_path)]) == 0
    assert capsys.readouterr().out == f"rendered {path}\n"
    assert read_report_json(path)["sections"]["Values"] == GOLDEN
    first = path.read_bytes()

    assert main(["render", str(tmp_path)]) == 0
    assert capsys.readouterr().out == f"unchanged {path}\n"
    assert path.read_bytes() == first


def test_render_cli_skips_histopathology_silently(tmp_path, histo, capsys):
    path = tmp_path / "H-001.json"
    write_report_json(path, histo)
    before = path.read_bytes()
    assert main(["render", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    assert path.read_bytes() == before


def test_render_cli_works_on_files_that_do_not_validate(tmp_path, cbc, capsys):
    path = tmp_path / "C-001.json"
    cbc["sections"]["Values"] = "stale text"
    cbc["provenance"] = "missing fields"  # would fail validation; render must not care
    write_report_json(path, cbc)
    assert main(["render", str(path)]) == 0
    assert read_report_json(path)["sections"]["Values"] == GOLDEN


def test_render_cli_bad_json_exits_one(tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert main(["render", str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith(f"FAIL {path}: does not parse as JSON")


def test_render_cli_missing_cbc_values_exits_one(tmp_path, cbc, capsys):
    path = tmp_path / "C-001.json"
    del cbc["cbc_values"]
    write_report_json(path, cbc)
    assert main(["render", str(path)]) == 1
    assert capsys.readouterr().out == f"FAIL {path}: lacks cbc_values\n"


def test_rerender_helper_matches_cli(tmp_path, cbc):
    path = tmp_path / "C-001.json"
    cbc["sections"]["Values"] = ""
    write_report_json(path, cbc)
    main(["render", str(path)])
    assert read_report_json(path)["sections"] == rerender(cbc)["sections"]
