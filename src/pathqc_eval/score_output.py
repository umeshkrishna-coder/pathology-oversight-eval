"""`score` and `map-list` (EVAL-05 6.3 and 6.8): score.json, summary.md and the category list.

score.json and summary.md carry no clock time, so scoring twice on the same inputs gives
byte-identical files. With --provisional, every number that depends on unadjudicated review
items is a range: all of them counted against the model, then all counted for it. A
provisional score leaves out the per-error table and the outcome of every finding, which
would tie a review item to a condition and a repeat before every verdict is entered
(decision 9), and it is logged so that the final scores can disclose it.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pathqc_eval import adjudication
from pathqc_eval import scoring_config as cfg
from pathqc_eval.matching import VERDICTS, normalise_category
from pathqc_eval.scoring import (
    CONDITIONS,
    RESULTS_DIR,
    SCENARIOS,
    Inputs,
    classify_runs,
    error_table,
    finding_count,
    finding_table,
    load_inputs,
    load_run,
    planted_by_type,
    review_findings,
    score_body,
)

TABLES_LEFT_OUT = (
    "The per-error and per-finding tables are left out of provisional scores, so that no "
    "review item is listed with its condition or repeat; the counts and ranges by condition "
    "can still show where an item came from."
)


# Owner decision (EVAL-09 B): no provisional score of the scored split, so that no range by
# condition is ever shown before every verdict is entered there.
PROVISIONAL_SCORED_REFUSED = (
    "--provisional is refused on the scored split (owner decision, 2026-11-11): the scored "
    "split is scored only once every review item has a verdict; provisional scores stay "
    "available on the dev split"
)


@dataclass
class Outcome:
    lines: list[str]
    ok: bool


def _refused(problems: list[str], what: str = "score") -> Outcome:
    return Outcome([f"{what} refused:"] + [f"  - {p}" for p in problems], False)


def _json_bytes(data: dict) -> bytes:
    """The bytes write_report_json writes (indented UTF-8 JSON, LF, one final newline)."""
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write_outputs(root: Path, files: dict[Path, bytes]) -> str:
    """Write the files together, or none of them: every existing target is first opened for
    writing, so a read-only file or a folder in the way is found before anything changes.
    Returns the problem in plain words, or "" when every file is written."""
    current = None
    try:
        for path in files:
            current = path
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                with path.open("ab"):
                    pass
        for path, content in files.items():
            current = path
            path.write_bytes(content)
    except OSError as exc:
        where = current.relative_to(root).as_posix() if current else "the output"
        return f"{where} cannot be written ({exc.strerror or exc})"
    return ""


# score


def run_score(
    root: Path,
    dataset: str,
    run_ids: list[str],
    provisional: bool,
    clock: Callable[[], datetime],
    commit: str,
) -> Outcome:
    if provisional and dataset == "scored":
        return _refused([PROVISIONAL_SCORED_REFUSED])
    inputs, problems = load_inputs(root, dataset, run_ids)
    if inputs is None:
        return _refused(problems)
    views = classify_runs(inputs)
    found = review_findings(views)
    notes: list[str] = []
    joined: adjudication.Joined | None = None
    mode = "final"
    folder = adjudication.adjudication_dir(root, dataset)
    data, problem = adjudication.load_items(folder)
    if data is None and (folder / adjudication.ITEMS_FILE).exists():
        return _refused([problem])
    state = (
        "not prepared" if data is None else f"{data.filled()} of {len(data.items)} verdicts filled"
    )
    if found:
        complete = data is not None and data.items and data.filled() == len(data.items)
        if not complete:
            if not provisional:
                return _refused(
                    [
                        f"{finding_count(found)} review finding(s) need the owner's blind "
                        "adjudication "
                        f"({state}); finish it, or score with --provisional"
                    ]
                )
            mode = "provisional"
        else:
            joined, problems = adjudication.join(root, dataset, found, clock)
            if joined is None:
                return _refused(problems)
            if provisional:
                notes.append("every verdict is filled, so --provisional is not needed")
    elif data is not None and data.items:
        return _refused([adjudication.stale_message(folder)])
    elif provisional:
        notes.append("there are no review findings, so --provisional is not needed")
    verdicts = joined.verdicts if joined is not None else {}
    before: int | None = None  # provisional scores logged before every verdict was entered
    if joined is not None:
        before = joined.provisional_scores
    elif mode == "final":
        logged, problem = adjudication.read_provisional_log(root, dataset)
        if logged is None:
            return _refused([problem])
        before = len(logged)

    def verdict_of(unit, index, error_id):
        return verdicts.get((unit.run_id, unit.report_id, unit.repeat, index, error_id))

    tables: dict = {}
    if mode == "final":
        body = score_body(inputs, views, lambda unit, i, o: verdict_of(unit, i, o.error_id))
        metrics, comparison, by_condition = body["conditions"], body["comparison"], body["counts"]
        tables = {
            "errors": error_table(inputs, views, body["resolved"], body["facts"]),
            "findings": finding_table(views, body["resolved"], verdict_of),
        }
    else:
        bodies = {
            "counted_against": score_body(inputs, views, lambda unit, i, o: "false_alarm"),
            "counted_for": score_body(inputs, views, lambda unit, i, o: "detected"),
        }
        metrics = {s: bodies[s]["conditions"] for s in SCENARIOS}
        comparison = {s: bodies[s]["comparison"] for s in SCENARIOS}
        by_condition = {s: bodies[s]["counts"] for s in SCENARIOS}
        tables = {"tables_left_out": TABLES_LEFT_OUT}
    review_items = None
    if data is not None and found:
        verdict_counts = Counter(item.verdict or "not filled" for item in data.items)
        review_items = {
            "items": len(data.items),
            "verdicts": {v: verdict_counts[v] for v in (*VERDICTS, "not filled")},
        }
    if mode == "provisional":
        entry = adjudication.ProvisionalScore(
            scored_at=adjudication.stamp(clock()),
            review_findings=finding_count(found),
            adjudication=state,
        )
        problem = adjudication.record_provisional(root, dataset, entry)
        if problem:
            return _refused([problem])
    score = {
        "title": f"{'PROVISIONAL scores' if mode == 'provisional' else 'Scores'}: {dataset} split",
        "provisional": mode == "provisional",
        "dataset": dataset,
        "inputs": {
            "runs": inputs.run_ids(),
            "scorer_commit": commit,
            "lock_created_at": inputs.lock_created_at,
            "dataset_hash": inputs.runs["plain"].config.dataset_hash,
            "taxonomy_hash": inputs.runs["plain"].config.taxonomy_hash,
            "scoring_config": cfg.config_values(),
            "models_returned": inputs.models_returned(),
            "drafted_by": sorted({r.provenance.drafted_by for r in inputs.reports.values()}),
            "warnings": inputs.warnings,
        },
        "counts": {
            "reports": len(inputs.reports),
            "planted_errors_by_type": planted_by_type(inputs),
            "review_findings": finding_count(found),
            "review_items": review_items,
            **({} if before is None else {"provisional_scores_before_completion": before}),
            "by_condition": by_condition,
        },
        "metrics": metrics,
        "comparison": comparison,
        **tables,
    }
    out_dir = root / RESULTS_DIR / dataset
    if mode == "provisional":
        out_dir = out_dir / "provisional"
    problem = _write_outputs(
        root,
        {
            out_dir / "score.json": _json_bytes(score),
            out_dir / "summary.md": summary_markdown(score, inputs).encode("utf-8"),
        },
    )
    if problem:
        return _refused([problem])
    lines = (
        [f"warning: {w}" for w in inputs.warnings]
        + notes
        + [
            f"{score['title']}: wrote {(out_dir / 'score.json').as_posix()} and "
            f"{(out_dir / 'summary.md').as_posix()}"
        ]
    )
    return Outcome(lines, True)


# summary.md


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def _num(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"{x:.{digits}f}"


def _level() -> str:
    return f"{100 * cfg.CONFIDENCE_LEVEL:g}%"


def _prop(p: dict, interval: bool = False) -> str:
    if not p["n"]:
        return "– (none)"
    text = f"{p['k']}/{p['n']} = {_pct(p['value'])}"
    if interval and p.get("interval"):
        text += f" ({_level()} CI {_pct(p['interval'][0])}–{_pct(p['interval'][1])})"
    return text


def _between(a: str, b: str) -> str:
    return a if a == b else f"{a} to {b}"


def summary_markdown(score: dict, inputs: Inputs) -> str:
    provisional = score["provisional"]
    prefix = "PROVISIONAL: " if provisional else ""
    if provisional:
        pair = {c: (score["metrics"]["counted_against"][c], score["metrics"]["counted_for"][c])
                for c in CONDITIONS}  # fmt: skip
        comp = (score["comparison"]["counted_against"], score["comparison"]["counted_for"])
    else:
        pair = {c: (score["metrics"][c], score["metrics"][c]) for c in CONDITIONS}
        comp = (score["comparison"], score["comparison"])

    def row(label: str, render: Callable[[dict], str]) -> str:
        cells = [_between(render(pair[c][0]), render(pair[c][1])) for c in CONDITIONS]
        return f"| {label} | {cells[0]} | {cells[1]} |"

    head = "| | Plain | Structured |\n|---|---|---|"
    inp = score["inputs"]
    out = [f"# {score['title']}", ""]
    out.append(
        f"Runs: plain {inp['runs']['plain']}, structured {inp['runs']['structured']}. "
        f"Lock created: {inp['lock_created_at'] or 'none (dev split)'}. "
        f"Scorer commit: {inp['scorer_commit']}."
    )
    for warning in inp["warnings"]:
        out += ["", f"Warning: {warning}; these scores use the current dev reports."]
    if provisional:
        out += [
            "",
            "PROVISIONAL: review items are not all adjudicated. Each range reads: all review "
            f"items counted against the model, to all counted for it. {TABLES_LEFT_OUT} This "
            f"provisional score is logged in results/{score['dataset']}/provisional/"
            f"{adjudication.PROVISIONAL_LOG_FILE}, and the final scores disclose how many "
            "were made.",
        ]
    out += ["", f"## {prefix}Per-type recall by condition", "", head]
    for tid in inputs.taxonomy.type_ids():
        out.append(row(tid, lambda m, t=tid: _prop(m["per_type_recall"][t], True)))
    out += ["", f"## {prefix}Overall recall", "", head]
    out.append(row("Overall recall", lambda m: _prop(m["overall_recall"], True)))
    out += ["", f"## {prefix}False alarms per report", "", head]
    for key, label in (("planted", "Planted reports"), ("clean", "Clean controls"), ("all", "All")):
        out.append(
            row(
                label,
                lambda m, k=key: (
                    f"{_num(m['false_alarms_per_report'][k]['mean'])} "
                    f"({m['false_alarms_per_report'][k]['reports']} reports)"
                ),
            )
        )
    out += ["", f"## {prefix}Specificity on clean controls", "", head]
    out.append(row("By majority", lambda m: _prop(m["specificity"]["by_majority"])))
    out.append(row("Per unit", lambda m: _prop(m["specificity"]["per_unit"])))
    out += ["", f"## {prefix}Calibration", "", head]
    out.append(row("Brier score", lambda m: _num(m["calibration"]["brier"], 3)))
    out.append(row(f"ECE ({cfg.ECE_BINS} bins)", lambda m: _num(m["calibration"]["ece"], 3)))
    out.append(row("Findings used", lambda m: str(m["calibration"]["findings"])))
    out.append(
        row(
            "Left out: verdict miss or in review",
            lambda m: str(m["calibration"]["left_out_miss_or_in_review"]),
        )
    )
    out.append(
        row("Left out: no confidence", lambda m: str(m["calibration"]["left_out_no_confidence"]))
    )
    out += ["", f"## {prefix}Repeat consistency", "", head]
    for key, label in (
        ("planted_errors", "Planted errors detected"),
        ("clean_controls_any_false_alarm", "Clean controls with any false alarm"),
    ):
        out.append(
            row(
                f"{label}: mean pairwise agreement",
                lambda m, k=key: (
                    f"{_pct(m['repeat_consistency'][k]['mean_pairwise_agreement'])} "
                    f"(n={m['repeat_consistency'][k]['n']})"
                ),
            )
        )
        out.append(
            row(
                f"{label}: same result in every valid unit",
                lambda m, k=key: _pct(m["repeat_consistency"][k]["share_same_in_every_unit"]),
            )
        )
    out += ["", f"## {prefix}Recall by severity", "", head]
    for severity in cfg.SEVERITIES:
        out.append(
            row(
                severity.capitalize(),
                lambda m, s=severity: _prop(m["recall_by_severity"][s], True),
            )
        )
    out += ["", f"## {prefix}Severity-weighted recall", "", head]
    out.append(
        row(
            "Severity-weighted recall",
            lambda m: (
                f"{m['severity_weighted_recall']['detected_weight']}/"
                f"{m['severity_weighted_recall']['planted_weight']} = "
                f"{_pct(m['severity_weighted_recall']['value'])}"
            ),
        )
    )
    out += ["", f"## {prefix}Type agreement (structured condition)", ""]
    out += [
        "Labels decide no detection (decision 61). Over the structured condition's hits and "
        "duplicates, the share whose category is the planted error's type id:",
        "",
        "| | Structured |",
        "|---|---|",
    ]
    s_pair = pair["structured"]

    def agreement(label: str, pick: Callable[[dict], dict]) -> str:
        cells = [_prop(pick(m["type_agreement"])) for m in s_pair]
        return f"| {label} | {_between(cells[0], cells[1])} |"

    out.append(agreement("Overall", lambda a: a["overall"]))
    for tid in inputs.taxonomy.type_ids():
        out.append(agreement(tid, lambda a, t=tid: a["per_type"][t]))
    labels = pair["plain"][0]["type_agreement"]["distinct_labels"]
    out += [
        "",
        "Plain condition: labels were free text and were not scored "
        f"({labels} distinct label{'' if labels == 1 else 's'}).",
    ]
    out += [
        "",
        f"## {prefix}Structured minus plain",
        "",
        f"| Metric | Difference | {_level()} interval (paired bootstrap) |",
        "|---|---|---|",
    ]
    for key, label, pp in (
        ("overall_recall", "Overall recall", True),
        ("false_alarms_per_report", "False alarms per report", False),
        ("specificity", "Specificity (by majority)", True),
    ):

        def fmt(x: float | None, pp: bool = pp) -> str:
            if x is None:
                return "–"
            return f"{100 * x:+.1f} pp" if pp else f"{x:+.2f}"

        def interval(c: dict, key: str = key, fmt=fmt) -> str:
            bounds = c[key]["interval"]
            if bounds is None:
                return "–"
            if provisional:  # bracketed, so that "a to b" joins the two scenarios only
                return f"[{fmt(bounds[0])}, {fmt(bounds[1])}]"
            return f"{fmt(bounds[0])} to {fmt(bounds[1])}"

        difference = _between(fmt(comp[0][key]["difference"]), fmt(comp[1][key]["difference"]))
        bounds = _between(interval(comp[0]), interval(comp[1]))
        out.append(f"| {label} | {difference} | {bounds} |")
    left_out = comp[0]["left_out"]
    out += [
        "",
        f"Reports in the paired comparison: {comp[0]['reports']}; left out (no majority result "
        f"in a condition): {len(left_out)}"
        + (f" ({', '.join(left_out)})" if left_out else "")
        + ".",
    ]
    counts = score["counts"]
    by = counts["by_condition"]
    if provisional:
        by_pair = {c: (by["counted_against"][c], by["counted_for"][c]) for c in CONDITIONS}
    else:
        by_pair = {c: (by[c], by[c]) for c in CONDITIONS}
    out += ["", f"## {prefix}Counts", "", head]
    for key, label in (
        ("reports", "Reports"),
        ("invalid_units", "Invalid units"),
        ("findings", "Findings in valid units"),
        ("false_alarms", "False alarms"),
        ("near_misses", "Near-misses"),
        ("duplicates", "Duplicates"),
        ("review_findings", "Review findings"),
        ("verdict_miss", "Set aside by a verdict of miss"),
        ("still_in_review", "Still in review"),
        ("null_confidence", "Findings with a null confidence"),
        ("null_severity", "Findings with a null severity"),
        ("dropped_findings", "Dropped findings"),
    ):
        cells = [_between(str(by_pair[c][0][key]), str(by_pair[c][1][key])) for c in CONDITIONS]
        out.append(f"| {label} | {cells[0]} | {cells[1]} |")
    no_majority = {c: by_pair[c][0]["reports_with_no_majority_result"] for c in CONDITIONS}
    out.append(
        "| Reports with no majority result | "
        + " | ".join(
            f"{len(no_majority[c])}" + (f" ({', '.join(no_majority[c])})" if no_majority[c] else "")
            for c in CONDITIONS
        )
        + " |"
    )
    planted = ", ".join(f"{t} {n}" for t, n in counts["planted_errors_by_type"].items())
    out += ["", f"Planted errors by type: {planted}."]
    items = counts["review_items"]
    if items:
        verdicts = ", ".join(f"{v} {n}" for v, n in items["verdicts"].items() if n)
        out.append(f"Review items: {items['items']}" + (f" ({verdicts})." if verdicts else "."))
    else:
        out.append(f"Review items: none prepared ({counts['review_findings']} review findings).")
    adjudicated = items["items"] - items["verdicts"]["not filled"] if items else 0
    if provisional:
        by_hand = (
            f"{adjudicated} review item(s) have a verdict so far; this provisional score is "
            "logged and will be disclosed with the final scores."
        )
    elif items:
        by_hand = f"{adjudicated} review item(s) were adjudicated by hand by the owner."
    else:
        by_hand = f"{adjudicated} review item(s) were adjudicated by hand."
    before = counts.get("provisional_scores_before_completion")
    log = f"results/{score['dataset']}/provisional/{adjudication.PROVISIONAL_LOG_FILE}"
    if before:
        by_hand += (
            f" {log} records {before} provisional score(s) made before every review finding "
            "had a verdict; each showed ranges by condition, from which the condition of an "
            "item can sometimes be inferred."
        )
    elif before == 0 and items:
        by_hand += (
            f" {log} records no provisional score made before every review finding had a verdict."
        )
    models = ", ".join(inp["models_returned"]) or "none"
    drafted = ", ".join(inp["drafted_by"]) or "unknown"
    out += [
        "",
        f"## {prefix}Disclosures",
        "",
        f"The reports are synthetic: drafted by {drafted} and corrected by the owner. Sampling "
        f"was the API default. One evaluated model was used; the API returned the model string "
        f"{models}. {counts['reports']} reports were scored ({score['dataset']} split). "
        "A detection means the finding quoted the planted sentence or one of its named other "
        f"places, in the right section, with a token overlap of at least "
        f"{cfg.OVERLAP_THRESHOLD:g}; an omission is detected only by the owner's verdict. "
        "Labels (categories) were not used to decide detections. The adjudication sheet showed "
        f"no category, condition, repeat, model or run. {by_hand}",
    ]
    return "\n".join(out) + "\n"


# map-list


def map_list(root: Path, run_ids: list[str]) -> Outcome:
    twice = sorted({run_id for run_id in run_ids if run_ids.count(run_id) > 1})
    if twice:
        return _refused([f"--runs names {run_id} twice" for run_id in twice], "map-list")
    problems: list[str] = []
    runs = []
    for run_id in run_ids:
        run, found = load_run(root, run_id)
        problems += found
        if run is not None:
            runs.append(run)
    if problems:
        return _refused(problems, "map-list")
    datasets = sorted({run.config.dataset for run in runs})
    if len(datasets) != 1:
        return _refused([f"the runs are for different splits ({', '.join(datasets)})"], "map-list")
    counts: dict[str, Counter] = {}
    for run in runs:
        for unit in run.results.units:
            if unit.status == "valid":
                for f in unit.findings:
                    counts.setdefault(normalise_category(f.category), Counter())[run.condition] += 1
    rows = [
        {"category": category, "count": {cond: counts[category][cond] for cond in CONDITIONS}}
        for category in sorted(counts)
    ]
    dataset = datasets[0]
    out = {"dataset": dataset, "runs": sorted(run.run_id for run in runs), "categories": rows}
    path = root / RESULTS_DIR / dataset / "category_strings.json"
    problem = _write_outputs(root, {path: _json_bytes(out)})
    if problem:
        return _refused([problem], "map-list")
    lines = [f"{'plain':>5} {'struct':>6}  category"]
    lines += [
        f"{r['count']['plain']:>5} {r['count']['structured']:>6}  {r['category']}" for r in rows
    ]
    lines.append(f"{len(rows)} distinct categories; wrote {path.as_posix()}")
    return Outcome(lines, True)
