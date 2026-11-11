"""Scorer (EVAL-05): two runs over the same dataset, one plain and one structured, into the
numbers for the write-up, with the owner's blind adjudication in between.

Decisions 4, 7, 8, 9, 10, 34 and 45. Scoring twice on the same inputs gives byte-identical
score.json and summary.md: no clock time, sorted orders and a fixed bootstrap seed.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import Literal

from pydantic import Field

from pathqc_eval import scoring_config as cfg
from pathqc_eval.findings import ParsedFinding
from pathqc_eval.freeze import LOCK_FILE, TAXONOMY_FILE, check_lock, compute_lock, normalized_sha256
from pathqc_eval.harness import REPEATS, RUNS_DIR, run_hashes, valid_run_id
from pathqc_eval.io import read_report_json, unique_keys
from pathqc_eval.matching import OTHER, Outcome, classify, map_category, normalise_category
from pathqc_eval.matching import resolve as resolve_unit
from pathqc_eval.schema import Report, RunConfig, StrictModel
from pathqc_eval.stats import brier, ece, paired_bootstrap, wilson
from pathqc_eval.taxonomy import Taxonomy, load_taxonomy

CATEGORY_MAP_FILE = "data/category_map.json"
REPORTS_DIR = "data/reports"
RESULTS_DIR = "results"
CONDITIONS = ("plain", "structured")
SCENARIOS = ("counted_against", "counted_for")  # provisional: review items against / for


def _short(value: object, limit: int = 200) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _r(value: float | None) -> float | None:
    """Rounded for output (6 decimals, no negative zero)."""
    return None if value is None else round(value, 6) + 0.0


# Inputs: runs, reports, taxonomy, category map


class ResultUnit(StrictModel):
    report_id: str
    repeat: int = Field(ge=1, le=REPEATS)
    status: Literal["valid", "invalid", "pending"]
    attempts: int = Field(ge=0)
    findings: list[ParsedFinding]
    dropped_count: int = Field(ge=0)
    model_returned: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ResultsFile(StrictModel):
    run_id: str
    dataset: Literal["dev", "scored"]
    condition: Literal["plain", "structured"]
    units: list[ResultUnit]
    totals: dict


@dataclass
class Run:
    run_id: str
    config: RunConfig
    results: ResultsFile

    @property
    def condition(self) -> str:
        return self.config.condition

    def models_returned(self) -> list[str]:
        return sorted({u.model_returned for u in self.results.units if u.model_returned})


def load_run(root: Path, run_id: str) -> tuple[Run | None, list[str]]:
    """runs/<run_id>/config.json and results.json, checked against each other."""
    if not valid_run_id(run_id):
        return None, [f"'{_short(run_id, 60)}' is not a run id"]
    loaded: dict = {}
    problems: list[str] = []
    for name, model in (("config.json", RunConfig), ("results.json", ResultsFile)):
        path = root / RUNS_DIR / run_id / name
        if not path.is_file():
            problems.append(f"runs/{run_id}/{name} does not exist")
            continue
        try:
            loaded[name] = model.model_validate(read_report_json(path))
        except (OSError, ValueError, RecursionError) as exc:  # ValidationError is a ValueError
            reason = "nested too deeply" if isinstance(exc, RecursionError) else _short(exc)
            problems.append(f"runs/{run_id}/{name} cannot be read ({reason})")
    if problems:
        return None, problems
    config, results = loaded["config.json"], loaded["results.json"]
    if config.run_id != run_id:
        problems.append(f"runs/{run_id}/config.json names run '{_short(config.run_id, 60)}'")
    for name in ("run_id", "dataset", "condition"):
        if getattr(results, name) != getattr(config, name):
            problems.append(f"runs/{run_id}: results.json and config.json differ in {name}")
    seen: set[tuple[str, int]] = set()
    for unit in results.units:
        key = (unit.report_id, unit.repeat)
        if key in seen:
            problems.append(f"runs/{run_id}/results.json lists {key[0]} repeat {key[1]} twice")
        seen.add(key)
    pending = sum(unit.status == "pending" for unit in results.units)
    if pending:
        problems.append(
            f"runs/{run_id} has {pending} pending unit(s); finish it first with "
            f"`pathqc-eval run --dataset {config.dataset} --condition {config.condition} "
            f"--cost-gate <USD> --run-id {run_id}`"
        )
    return Run(run_id, config, results), problems


@dataclass(frozen=True)
class CategoryMap:
    entries: dict[str, str]
    status: str  # proposed, approved, or missing (no file)
    version: str | None
    sha256: str | None

    def describe(self) -> dict:
        return {"status": self.status, "version": self.version, "sha256": self.sha256}


def load_category_map(root: Path, taxonomy: Taxonomy) -> tuple[CategoryMap | None, list[str]]:
    """data/category_map.json: version, status (proposed | approved) and map from a normalised
    category to a taxonomy id or "other". A missing file is an empty map with status missing."""
    path = root / CATEGORY_MAP_FILE
    if not path.is_file():
        return CategoryMap({}, "missing", None, None), []
    try:
        # A key given twice is refused: one string maps one way (decision 10).
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (OSError, ValueError, RecursionError) as exc:
        reason = "nested too deeply" if isinstance(exc, RecursionError) else _short(exc)
        return None, [f"{CATEGORY_MAP_FILE} cannot be read ({reason})"]
    if not isinstance(data, dict):
        return None, [f"{CATEGORY_MAP_FILE} must be a JSON object with version, status and map"]
    problems: list[str] = []
    extra = sorted(str(key) for key in data if key not in ("version", "status", "map"))
    if extra:
        problems.append(f"{CATEGORY_MAP_FILE}: unknown keys: {', '.join(extra)}")
    version, status, mapping = data.get("version"), data.get("status"), data.get("map")
    if not isinstance(version, str) or not version.strip():
        problems.append(f"{CATEGORY_MAP_FILE}: version must be a non-empty string")
    if status not in ("proposed", "approved"):
        problems.append(f"{CATEGORY_MAP_FILE}: status must be proposed or approved")
    if not isinstance(mapping, dict):
        problems.append(f"{CATEGORY_MAP_FILE}: map must be an object")
        mapping = {}
    ids = taxonomy.type_ids()
    own = {tid.casefold() for tid in ids} | {OTHER}
    for key, value in mapping.items():
        if not isinstance(value, str) or (value not in ids and value != OTHER):
            problems.append(
                f"{CATEGORY_MAP_FILE}: '{_short(key, 60)}' maps to {_short(repr(value), 60)}, "
                f"not to a taxonomy id ({', '.join(ids)}) or 'other'"
            )
        normal = normalise_category(key)
        if normal != key:
            problems.append(
                f"{CATEGORY_MAP_FILE}: key '{_short(key, 60)}' is not normalised; "
                f"write it as '{_short(normal, 60)}'"
            )
        elif key in own:
            problems.append(
                f"{CATEGORY_MAP_FILE}: key '{key}' is a taxonomy id or 'other', which map to "
                "themselves; remove it"
            )
    if problems:
        return None, problems
    return CategoryMap(dict(mapping), status, version, normalized_sha256(path)), []


@dataclass
class Inputs:
    dataset: str
    runs: dict[str, Run]  # by condition
    reports: dict[str, Report]  # the split's reports, by id
    taxonomy: Taxonomy
    category_map: CategoryMap
    lock_created_at: str | None
    warnings: list[str]  # dev only: the tree has changed since the runs

    def run_ids(self) -> dict[str, str]:
        return {cond: self.runs[cond].run_id for cond in CONDITIONS}

    def models_returned(self) -> list[str]:
        return sorted({m for run in self.runs.values() for m in run.models_returned()})


def _load_reports(root: Path, dataset: str) -> tuple[dict[str, Report], list[str]]:
    reports: dict[str, Report] = {}
    problems: list[str] = []
    seen: dict[str, str] = {}  # report id -> the file it was first read from
    for path in sorted((root / REPORTS_DIR).glob("*.json")):
        try:
            report = Report.model_validate(read_report_json(path))
        except (OSError, ValueError, RecursionError) as exc:
            reason = "nested too deeply" if isinstance(exc, RecursionError) else _short(exc)
            problems.append(f"{REPORTS_DIR}/{path.name} cannot be read as a report ({reason})")
            continue
        if report.id in seen:  # e.g. "H-001 - Copy.json": one of the two would be dropped
            problems.append(f"report id {report.id} is in both {seen[report.id]} and {path.name}")
            continue
        seen[report.id] = path.name
        if report.split == dataset:
            reports[report.id] = report
    return reports, problems


def _remap_problems(root: Path, category_map: CategoryMap) -> list[str]:
    """Owner decision (EVAL-09 H6; decision 10, nothing is remapped after scoring): once the
    scored split has been scored, the category map must keep the sha256 that
    results/scored/score.json records."""
    where = f"{RESULTS_DIR}/scored/score.json"
    path = root / RESULTS_DIR / "scored" / "score.json"
    if not path.exists():
        return []
    try:
        recorded = read_report_json(path)["inputs"]["category_map"]["sha256"]
        if not isinstance(recorded, str):
            raise TypeError(f"the recorded sha256 is {type(recorded).__name__}, not text")
    except (OSError, ValueError, RecursionError, KeyError, TypeError) as exc:
        return [
            f"{where} cannot be read, so the category map recorded at the first scoring "
            f"cannot be checked ({_short(exc)})"
        ]
    if recorded == category_map.sha256:
        return []
    return [
        f"{CATEGORY_MAP_FILE} has changed since the scored split was scored: {where} records "
        f"sha256 {recorded}, the map now has {category_map.sha256}; nothing is remapped after "
        "scoring (decision 10)"
    ]


def load_inputs(root: Path, dataset: str, run_ids: Sequence[str]) -> tuple[Inputs | None, list]:
    """Everything adjudication and scoring read, or every reason to refuse (6.8 checks)."""
    problems: list[str] = []
    runs: list[Run] = []
    for run_id in run_ids:
        run, found = load_run(root, run_id)
        problems += found
        if run is not None:
            runs.append(run)
    if problems:
        return None, problems
    for run in runs:
        if run.config.dataset != dataset:
            problems.append(
                f"run {run.run_id} is for the {run.config.dataset} split, not {dataset}"
            )
    conditions = sorted(run.condition for run in runs)
    if conditions != list(CONDITIONS):
        problems.append(
            f"the runs must be one plain and one structured run (got {', '.join(conditions)})"
        )
        return None, problems
    by_condition = {run.condition: run for run in runs}
    plain, structured = by_condition["plain"], by_condition["structured"]
    for name in ("dataset_hash", "taxonomy_hash"):
        if getattr(plain.config, name) != getattr(structured.config, name):
            problems.append(f"the two runs differ in {name}")
    try:
        taxonomy = load_taxonomy(root / TAXONOMY_FILE)
    except (OSError, ValueError) as exc:
        return None, problems + [f"{TAXONOMY_FILE} cannot be loaded ({_short(exc)})"]
    reports, found = _load_reports(root, dataset)
    problems += found
    # The scored split is held to the lock below. A dev run's dataset hash covers every file in
    # data/reports/, so editing any report after a dev run changes it: dev scoring goes on with
    # the current dev reports and records a warning.
    current = compute_lock(root)
    changed = []
    if current["dataset"]["hash"] != plain.config.dataset_hash:
        changed.append(f"{REPORTS_DIR}/ has changed since the runs (the dataset hash differs)")
    if current["files"][TAXONOMY_FILE] != plain.config.taxonomy_hash:
        changed.append(f"{TAXONOMY_FILE} has changed since the runs (its hash differs)")
    warnings = changed if dataset == "dev" else []
    problems += [] if dataset == "dev" else changed
    for run in runs:
        units: dict[str, list[int]] = {}
        for unit in run.results.units:
            units.setdefault(unit.report_id, []).append(unit.repeat)
        if sorted(units) != sorted(reports):
            problems.append(
                f"run {run.run_id} covers other reports than the {dataset} reports in "
                f"{REPORTS_DIR}/"
            )
        for report_id, repeats in sorted(units.items()):
            if sorted(repeats) != list(range(1, REPEATS + 1)):
                problems.append(f"run {run.run_id}: {report_id} does not have repeats 1 to 3")
    category_map, found = load_category_map(root, taxonomy)
    problems += found
    lock_created_at = None
    if dataset == "scored":
        outcome = check_lock(root)
        if not outcome.ok:
            problems += outcome.lines
        else:
            lock_created_at = read_report_json(root / LOCK_FILE)["created_at"]
            for run in runs:
                expected = run_hashes(root, "scored", run.condition)
                differ = [k for k, v in expected.items() if getattr(run.config, k) != v]
                if differ:
                    verb = "differs" if len(differ) == 1 else "differ"
                    problems.append(
                        f"run {run.run_id}: {', '.join(differ)} {verb} from {LOCK_FILE}"
                    )
        if category_map is not None and category_map.status != "approved":
            problems.append(
                f"{CATEGORY_MAP_FILE} must have status approved to score the scored split "
                f"(it is {category_map.status})"
            )
        if category_map is not None:
            problems += _remap_problems(root, category_map)
        if not cfg.OWNER_CONFIRMED:
            problems.append(
                "scoring_config.OWNER_CONFIRMED is False: the scorer defaults are not confirmed "
                "by the owner"
            )
    if problems or category_map is None:
        return None, problems
    inputs = Inputs(
        dataset, by_condition, reports, taxonomy, category_map, lock_created_at, warnings
    )
    return inputs, []


# Classification of every finding in both runs


@dataclass
class UnitView:
    condition: str
    run_id: str
    report_id: str
    repeat: int
    valid: bool
    findings: list[ParsedFinding]
    mapped: list[str]
    base: list[Outcome]  # one per finding: hit, review, near_miss or false_alarm
    dropped: int
    model: str | None


Views = dict[str, dict[tuple[str, int], UnitView]]  # condition -> (report id, repeat) -> unit


def classify_runs(inputs: Inputs) -> Views:
    type_ids = inputs.taxonomy.type_ids()
    views: Views = {}
    for cond in CONDITIONS:
        run = inputs.runs[cond]
        units: dict[tuple[str, int], UnitView] = {}
        for unit in sorted(run.results.units, key=lambda u: (u.report_id, u.repeat)):
            errors = inputs.reports[unit.report_id].errors
            valid = unit.status == "valid"
            findings = list(unit.findings) if valid else []
            mapped = [
                map_category(f.category, type_ids, inputs.category_map.entries) for f in findings
            ]
            base = [
                classify(f.section, f.quoted_sentence, m, errors)
                for f, m in zip(findings, mapped, strict=True)
            ]
            units[(unit.report_id, unit.repeat)] = UnitView(
                cond, run.run_id, unit.report_id, unit.repeat, valid, findings, mapped, base,
                unit.dropped_count, unit.model_returned,
            )  # fmt: skip
        views[cond] = units
    return views


@dataclass(frozen=True)
class ReviewFinding:
    """One review finding and one candidate error: a finding in review for several omission
    errors (EVAL-09 C) gives one ReviewFinding, and so one review item, per omission."""

    unit: UnitView
    index: int  # 1-based position of the finding in its unit
    finding: ParsedFinding
    outcome: Outcome  # the review outcome for this one candidate error


def review_findings(views: Views) -> list[ReviewFinding]:
    found = []
    for cond in CONDITIONS:
        for key in sorted(views[cond]):
            unit = views[cond][key]
            for index, (finding, outcome) in enumerate(
                zip(unit.findings, unit.base, strict=True), start=1
            ):
                if outcome.outcome == "review":
                    for eid in outcome.ids:
                        one = replace(outcome, error_id=eid, error_ids=())
                        found.append(ReviewFinding(unit, index, finding, one))
    return found


def finding_count(found: Sequence[ReviewFinding]) -> int:
    """How many findings are in review (a finding with several candidate errors counts once)."""
    return len({(r.unit.run_id, r.unit.report_id, r.unit.repeat, r.index) for r in found})


Decide = Callable[[UnitView, int, Outcome], str | None]
Resolved = dict[str, dict[tuple[str, int], list[Outcome]]]


def resolve_views(views: Views, decide: Decide) -> Resolved:
    return {
        cond: {
            key: resolve_unit(unit.base, lambda i, o, unit=unit: decide(unit, i, o))
            for key, unit in units.items()
        }
        for cond, units in views.items()
    }


# Metrics (6.5 and 6.6)


def _proportion(k: int, n: int, interval: bool = False) -> dict:
    out: dict = {"k": k, "n": n, "value": _r(k / n) if n else None}
    if interval:
        bounds = wilson(k, n)
        out["interval"] = [_r(bounds[0]), _r(bounds[1])] if bounds else None
    return out


def _consistency(flag_lists: list[list[bool]]) -> dict:
    """Mean pairwise agreement between valid units, and the share with one result in all."""
    if not flag_lists:
        return {"n": 0, "mean_pairwise_agreement": None, "share_same_in_every_unit": None}
    agreements = [
        sum(a == b for a, b in combinations(flags, 2)) / math.comb(len(flags), 2)
        for flags in flag_lists
    ]
    same = sum(len(set(flags)) == 1 for flags in flag_lists)
    return {
        "n": len(flag_lists),
        "mean_pairwise_agreement": _r(sum(agreements) / len(agreements)),
        "share_same_in_every_unit": _r(same / len(flag_lists)),
    }


def _hits(outcomes: Sequence[Outcome]) -> set[str]:
    return {eid for o in outcomes if o.outcome == "hit" for eid in o.ids}


def _false_alarms(outcomes: Sequence[Outcome]) -> int:
    return sum(o.outcome == "false_alarm" for o in outcomes)


@dataclass
class ConditionFacts:
    """Per-report facts of one condition that the metrics and the comparison share."""

    valid: dict[str, list[tuple[int, list[Outcome]]]]  # report id -> (repeat, outcomes)
    majority_ids: list[str]  # reports with at least two valid units
    detected: dict[str, bool]  # error id -> detected by majority (majority reports only)
    fa_mean: dict[str, float]  # report id -> mean false alarms per valid unit (>= 1 valid)
    passes: dict[str, bool]  # clean control id -> passes by majority (majority reports only)


def condition_facts(inputs: Inputs, views: dict, resolved: dict) -> ConditionFacts:
    valid: dict[str, list[tuple[int, list[Outcome]]]] = {}
    for rid in sorted(inputs.reports):
        valid[rid] = [
            (rep, resolved[(rid, rep)]) for rep in range(1, REPEATS + 1) if views[(rid, rep)].valid
        ]
    majority_ids = [rid for rid, units in valid.items() if len(units) >= 2]
    detected = {
        err.error_id: sum(err.error_id in _hits(o) for _, o in valid[rid]) >= 2
        for rid in majority_ids
        for err in inputs.reports[rid].errors
    }
    fa_mean = {
        rid: sum(_false_alarms(o) for _, o in units) / len(units)
        for rid, units in valid.items()
        if units
    }
    passes = {
        rid: sum(_false_alarms(o) == 0 for _, o in valid[rid]) >= 2
        for rid in majority_ids
        if not inputs.reports[rid].errors
    }
    return ConditionFacts(valid, majority_ids, detected, fa_mean, passes)


def condition_metrics(inputs: Inputs, views: dict, facts: ConditionFacts) -> dict:
    reports = inputs.reports
    errors = [(rid, e) for rid in facts.majority_ids for e in reports[rid].errors]
    per_type = {}
    for tid in inputs.taxonomy.type_ids():
        of_type = [e for _, e in errors if e.type == tid]
        per_type[tid] = _proportion(
            sum(facts.detected[e.error_id] for e in of_type), len(of_type), True
        )
    overall = _proportion(sum(facts.detected[e.error_id] for _, e in errors), len(errors), True)
    by_severity = {
        severity: _proportion(
            sum(facts.detected[e.error_id] for _, e in errors if e.severity == severity),
            sum(e.severity == severity for _, e in errors),
            True,
        )
        for severity in cfg.SEVERITIES
    }  # EVAL-09 G: plain recall for each severity, beside the weighted figure
    weights = cfg.SEVERITY_WEIGHTS
    planted_weight = sum(weights[e.severity] for _, e in errors)
    detected_weight = sum(weights[e.severity] for _, e in errors if facts.detected[e.error_id])

    def mean_of(ids: list[str]) -> dict:
        values = [facts.fa_mean[rid] for rid in ids if rid in facts.fa_mean]
        return {"reports": len(values), "mean": _r(sum(values) / len(values)) if values else None}

    planted_ids = [rid for rid in sorted(reports) if reports[rid].errors]
    clean_ids = [rid for rid in sorted(reports) if not reports[rid].errors]
    clean_units = [o for rid in clean_ids for _, o in facts.valid[rid]]

    pairs: list[tuple[float, int]] = []
    left_out_review = left_out_no_confidence = 0
    for rid in sorted(reports):
        for rep, outcomes in facts.valid[rid]:
            for finding, outcome in zip(views[(rid, rep)].findings, outcomes, strict=True):
                if outcome.outcome in ("miss", "review"):
                    left_out_review += 1
                elif finding.confidence is None:
                    left_out_no_confidence += 1
                else:
                    pairs.append((finding.confidence, int(outcome.outcome != "false_alarm")))

    error_flags = [
        [e.error_id in _hits(o) for _, o in facts.valid[rid]]
        for rid in facts.majority_ids
        for e in reports[rid].errors
    ]
    clean_flags = [[_false_alarms(o) > 0 for _, o in facts.valid[rid]] for rid in facts.passes]
    return {
        "per_type_recall": per_type,
        "overall_recall": overall,
        "false_alarms_per_report": {
            "planted": mean_of(planted_ids),
            "clean": mean_of(clean_ids),
            "all": mean_of(sorted(reports)),
        },
        "specificity": {
            "by_majority": _proportion(sum(facts.passes.values()), len(facts.passes)),
            "per_unit": _proportion(
                sum(_false_alarms(o) == 0 for o in clean_units), len(clean_units)
            ),
        },
        "calibration": {
            "brier": _r(brier(pairs)),
            "ece": _r(ece(pairs)),
            "findings": len(pairs),
            "left_out_miss_or_in_review": left_out_review,
            "left_out_no_confidence": left_out_no_confidence,
        },
        "repeat_consistency": {
            "planted_errors": _consistency(error_flags),
            "clean_controls_any_false_alarm": _consistency(clean_flags),
        },
        "recall_by_severity": by_severity,
        "severity_weighted_recall": {
            "detected_weight": detected_weight,
            "planted_weight": planted_weight,
            "value": _r(detected_weight / planted_weight) if planted_weight else None,
        },
    }


def comparison(inputs: Inputs, facts: Mapping[str, ConditionFacts]) -> dict:
    """Structured minus plain over the reports with a majority result in both conditions,
    each with a paired bootstrap over reports (the same resample for both conditions)."""
    reports = inputs.reports
    both = sorted(set(facts["plain"].majority_ids) & set(facts["structured"].majority_ids))
    tallies = {
        cond: {
            rid: (sum(facts[cond].detected[e.error_id] for e in reports[rid].errors),
                  len(reports[rid].errors))
            for rid in both
        }
        for cond in CONDITIONS
    }  # fmt: skip

    def recall(cond: str, ids: list[str]) -> float | None:
        planted = sum(tallies[cond][rid][1] for rid in ids)
        return sum(tallies[cond][rid][0] for rid in ids) / planted if planted else None

    def false_alarms(cond: str, ids: list[str]) -> float | None:
        return sum(facts[cond].fa_mean[rid] for rid in ids) / len(ids) if ids else None

    def specificity(cond: str, ids: list[str]) -> float | None:
        clean = [facts[cond].passes[rid] for rid in ids if rid in facts[cond].passes]
        return sum(clean) / len(clean) if clean else None

    out: dict = {"reports": len(both), "left_out": sorted(set(reports) - set(both))}
    for name, fn in (
        ("overall_recall", recall),
        ("false_alarms_per_report", false_alarms),
        ("specificity", specificity),
    ):

        def statistic(ids: list[str], fn=fn) -> float | None:
            s, p = fn("structured", ids), fn("plain", ids)
            return None if s is None or p is None else s - p

        result = paired_bootstrap(both, statistic)
        out[name] = {
            "difference": _r(result["difference"]),
            "interval": [_r(x) for x in result["interval"]] if result["interval"] else None,
            "resamples": result["resamples"],
            "undefined_resamples": result["undefined"],
        }
    return out


def condition_counts(inputs: Inputs, views: dict, resolved: dict, facts: ConditionFacts) -> dict:
    valid_units = [key for key, unit in sorted(views.items()) if unit.valid]
    outcomes = [o for key in valid_units for o in resolved[key]]
    findings = [f for key in valid_units for f in views[key].findings]
    return {
        "reports": len(inputs.reports),
        "reports_with_no_majority_result": sorted(set(inputs.reports) - set(facts.majority_ids)),
        "invalid_units": sum(not unit.valid for unit in views.values()),
        "findings": len(findings),
        "false_alarms": sum(o.outcome == "false_alarm" for o in outcomes),
        "near_misses": sum(o.outcome == "near_miss" for o in outcomes),
        "duplicates": sum(o.outcome == "duplicate" for o in outcomes),
        "review_findings": sum(
            o.outcome == "review" for key in valid_units for o in views[key].base
        ),
        "verdict_miss": sum(o.outcome == "miss" for o in outcomes),
        "still_in_review": sum(o.outcome == "review" for o in outcomes),
        "null_confidence": sum(f.confidence is None for f in findings),
        "null_severity": sum(f.severity is None for f in findings),
        "dropped_findings": sum(views[key].dropped for key in valid_units),
    }


def error_table(inputs: Inputs, views: Views, resolved: Resolved, facts: Mapping) -> list[dict]:
    rows = []
    for rid in sorted(inputs.reports):
        for err in inputs.reports[rid].errors:
            row = {
                "report_id": rid,
                "error_id": err.error_id,
                "type": err.type,
                "severity": err.severity,
                "kind": err.kind,
            }
            for cond in CONDITIONS:
                units = []
                for rep in range(1, REPEATS + 1):
                    unit = views[cond][(rid, rep)]
                    units.append(
                        err.error_id in _hits(resolved[cond][(rid, rep)]) if unit.valid else None
                    )
                row[cond] = {
                    "detected_by_repeat": units,
                    "detected_by_majority": facts[cond].detected.get(err.error_id),
                    "review_pending_in_repeats": sorted(
                        rep
                        for rep in range(1, REPEATS + 1)
                        for o in resolved[cond][(rid, rep)]
                        if o.outcome == "review" and err.error_id in o.ids
                    ),
                }
            rows.append(row)
    return rows


def finding_table(views: Views, resolved: Resolved, verdict_of: Callable) -> list[dict]:
    rows = []
    for cond in CONDITIONS:
        for key in sorted(views[cond]):
            unit = views[cond][key]
            for index, (finding, mapped, base, final) in enumerate(
                zip(unit.findings, unit.mapped, unit.base, resolved[cond][key], strict=True),
                start=1,
            ):
                rows.append(
                    {
                        "condition": cond,
                        "run_id": unit.run_id,
                        "report_id": unit.report_id,
                        "repeat": unit.repeat,
                        "finding_index": index,
                        "section": finding.section,
                        "category": finding.category,
                        "mapped": mapped,
                        "outcome": final.outcome,
                        "error_id": final.error_id,
                        "error_ids": list(final.ids),
                        "review_reason": base.reason,
                        "verdict": _verdicts(verdict_of, unit, index, base),
                        "overlap": _r(base.overlap),
                    }
                )
    return rows


def _verdicts(verdict_of: Callable, unit: UnitView, index: int, base: Outcome):
    """A review finding's verdict; for one in review for several omission errors (EVAL-09 C),
    the verdict on each, by error id."""
    if base.outcome != "review":
        return None
    if len(base.ids) > 1:
        return {eid: verdict_of(unit, index, eid) for eid in base.ids}
    return verdict_of(unit, index, base.error_id)


def planted_by_type(inputs: Inputs) -> dict[str, int]:
    counts = Counter(e.type for r in inputs.reports.values() for e in r.errors)
    return {tid: counts[tid] for tid in inputs.taxonomy.type_ids()}


def score_body(inputs: Inputs, views: Views, decide: Decide) -> dict:
    """conditions, comparison and counts for one way of resolving the review findings."""
    resolved = resolve_views(views, decide)
    facts = {cond: condition_facts(inputs, views[cond], resolved[cond]) for cond in CONDITIONS}
    return {
        "resolved": resolved,
        "facts": facts,
        "conditions": {
            cond: condition_metrics(inputs, views[cond], facts[cond]) for cond in CONDITIONS
        },
        "comparison": comparison(inputs, facts),
        "counts": {
            cond: condition_counts(inputs, views[cond], resolved[cond], facts[cond])
            for cond in CONDITIONS
        },
    }
