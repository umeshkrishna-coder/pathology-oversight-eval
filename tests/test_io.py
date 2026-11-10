from pathqc_eval.io import read_report_json, write_report_json


def test_write_report_json_lf_and_one_trailing_newline(tmp_path):
    path = tmp_path / "r.json"
    data = {"a": [1, 2], "text": "line one\nline two – en dash"}
    write_report_json(path, data)
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert "–".encode() in raw  # ensure_ascii=False keeps UTF-8 characters
    assert read_report_json(path) == data
