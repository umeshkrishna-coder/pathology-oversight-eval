# Scores: scored split

Runs: plain 20261112-153246-scored-plain, structured 20261112-153532-scored-structured. Lock created: 2026-11-12T15:21:36Z. Scorer commit: f7b31729a34de13f01961f88be87607741bb6455.

## Per-type recall by condition

| | Plain | Structured |
|---|---|---|
| H1 | 5/5 = 100.0% (95% CI 56.6%–100.0%) | 5/5 = 100.0% (95% CI 56.6%–100.0%) |
| H2 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| H3 | 5/5 = 100.0% (95% CI 56.6%–100.0%) | 5/5 = 100.0% (95% CI 56.6%–100.0%) |
| H4 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| H5 | 4/5 = 80.0% (95% CI 37.6%–96.4%) | 4/5 = 80.0% (95% CI 37.6%–96.4%) |
| H6 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| C1 | 10/10 = 100.0% (95% CI 72.2%–100.0%) | 10/10 = 100.0% (95% CI 72.2%–100.0%) |
| C2 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| C3 | 0/2 = 0.0% (95% CI 0.0%–65.8%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |

## Overall recall

| | Plain | Structured |
|---|---|---|
| Overall recall | 36/39 = 92.3% (95% CI 79.7%–97.3%) | 38/39 = 97.4% (95% CI 86.8%–99.5%) |

## False alarms per report

| | Plain | Structured |
|---|---|---|
| Planted reports | 1.48 (22 reports) | 0.55 (22 reports) |
| Clean controls | 1.08 (8 reports) | 0.12 (8 reports) |
| All | 1.38 (30 reports) | 0.43 (30 reports) |

## Specificity on clean controls

| | Plain | Structured |
|---|---|---|
| By majority | 2/8 = 25.0% | 8/8 = 100.0% |
| Per unit | 6/24 = 25.0% | 22/24 = 91.7% |

## Calibration

| | Plain | Structured |
|---|---|---|
| Brier score | 0.103 | 0.067 |
| ECE (5 bins) | 0.159 | 0.071 |
| Findings used | 258 | 167 |
| Left out: verdict miss or in review | 5 | 1 |
| Left out: no confidence | 0 | 0 |

## Repeat consistency

| | Plain | Structured |
|---|---|---|
| Planted errors detected: mean pairwise agreement | 98.3% (n=39) | 96.6% (n=39) |
| Planted errors detected: same result in every valid unit | 97.4% | 94.9% |
| Clean controls with any false alarm: mean pairwise agreement | 83.3% (n=8) | 83.3% (n=8) |
| Clean controls with any false alarm: same result in every valid unit | 75.0% | 75.0% |

## Recall by severity

| | Plain | Structured |
|---|---|---|
| Critical | 11/13 = 84.6% (95% CI 57.8%–95.7%) | 13/13 = 100.0% (95% CI 77.2%–100.0%) |
| Major | 24/24 = 100.0% (95% CI 86.2%–100.0%) | 24/24 = 100.0% (95% CI 86.2%–100.0%) |
| Minor | 1/2 = 50.0% (95% CI 9.5%–90.5%) | 1/2 = 50.0% (95% CI 9.5%–90.5%) |

## Severity-weighted recall

| | Plain | Structured |
|---|---|---|
| Severity-weighted recall | 82/89 = 92.1% | 88/89 = 98.9% |

## Type agreement (structured condition)

Labels decide no detection (decision 61). Over the structured condition's hits and duplicates, the share whose category is the planted error's type id:

| | Structured |
|---|---|
| Overall | 124/128 = 96.9% |
| H1 | 16/18 = 88.9% |
| H2 | 12/12 = 100.0% |
| H3 | 15/15 = 100.0% |
| H4 | 9/9 = 100.0% |
| H5 | 16/16 = 100.0% |
| H6 | 9/10 = 90.0% |
| C1 | 33/34 = 97.1% |
| C2 | 9/9 = 100.0% |
| C3 | 5/5 = 100.0% |

Plain condition: labels were free text and were not scored (146 distinct labels).

## Structured minus plain

| Metric | Difference | 95% interval (paired bootstrap) |
|---|---|---|
| Overall recall | +5.1 pp | +0.0 pp to +12.8 pp |
| False alarms per report | -0.94 | -1.33 to -0.62 |
| Specificity (by majority) | +75.0 pp | +40.0 pp to +100.0 pp |

Reports in the paired comparison: 30; left out (no majority result in a condition): 0.

## Counts

| | Plain | Structured |
|---|---|---|
| Reports | 30 | 30 |
| Invalid units | 0 | 0 |
| Findings in valid units | 263 | 168 |
| False alarms | 124 | 39 |
| Near-misses | 2 | 0 |
| Duplicates | 23 | 14 |
| Review findings | 14 | 7 |
| Set aside by a verdict of miss | 5 | 1 |
| Still in review | 0 | 0 |
| Findings with a null confidence | 0 | 0 |
| Findings with a null severity | 1 | 0 |
| Dropped findings | 0 | 0 |
| Reports with no majority result | 0 | 0 |

Planted errors by type: H1 5, H2 3, H3 5, H4 3, H5 5, H6 3, C1 10, C2 3, C3 2.
Review items: 25 (detected 7, miss 10, near_miss 2, false_alarm 6).

## Disclosures

The reports are synthetic: drafted by claude-haiku-5-5 and corrected by the owner. Sampling was the API default. One evaluated model was used; the API returned the model string claude-sonnet-5-5. 30 reports were scored (scored split). A detection means the finding quoted the planted sentence or one of its named other places, in the right section, with a token overlap of at least 0.6; an omission is detected only by the owner's verdict. Labels (categories) were not used to decide detections. The adjudication sheet showed no category, condition, repeat, model or run. 25 review item(s) were adjudicated by hand by the owner. results/scored/provisional/provisional_log.json records no provisional score made before every review finding had a verdict.
