# Scores: dev split

Runs: plain 20261112-133401-dev-plain, structured 20261112-133439-dev-structured. Lock created: none (dev split). Scorer commit: 0150f1bc2da7a880eb1f67b4f5bed8ef6aa887ab.

## Per-type recall by condition

| | Plain | Structured |
|---|---|---|
| H1 | – (none) | – (none) |
| H2 | 1/1 = 100.0% (95% CI 20.7%–100.0%) | 1/1 = 100.0% (95% CI 20.7%–100.0%) |
| H3 | 1/1 = 100.0% (95% CI 20.7%–100.0%) | 1/1 = 100.0% (95% CI 20.7%–100.0%) |
| H4 | 1/1 = 100.0% (95% CI 20.7%–100.0%) | 1/1 = 100.0% (95% CI 20.7%–100.0%) |
| H5 | – (none) | – (none) |
| H6 | – (none) | – (none) |
| C1 | – (none) | – (none) |
| C2 | 1/1 = 100.0% (95% CI 20.7%–100.0%) | 1/1 = 100.0% (95% CI 20.7%–100.0%) |
| C3 | – (none) | – (none) |

## Overall recall

| | Plain | Structured |
|---|---|---|
| Overall recall | 4/4 = 100.0% (95% CI 51.0%–100.0%) | 4/4 = 100.0% (95% CI 51.0%–100.0%) |

## False alarms per report

| | Plain | Structured |
|---|---|---|
| Planted reports | 1.22 (3 reports) | 0.78 (3 reports) |
| Clean controls | 0.00 (1 reports) | 0.00 (1 reports) |
| All | 0.92 (4 reports) | 0.58 (4 reports) |

## Specificity on clean controls

| | Plain | Structured |
|---|---|---|
| By majority | 1/1 = 100.0% | 1/1 = 100.0% |
| Per unit | 3/3 = 100.0% | 3/3 = 100.0% |

## Calibration

| | Plain | Structured |
|---|---|---|
| Brier score | 0.080 | 0.049 |
| ECE (5 bins) | 0.179 | 0.126 |
| Findings used | 29 | 26 |
| Left out: verdict miss or in review | 0 | 0 |
| Left out: no confidence | 0 | 0 |

## Repeat consistency

| | Plain | Structured |
|---|---|---|
| Planted errors detected: mean pairwise agreement | 100.0% (n=4) | 100.0% (n=4) |
| Planted errors detected: same result in every valid unit | 100.0% | 100.0% |
| Clean controls with any false alarm: mean pairwise agreement | 100.0% (n=1) | 100.0% (n=1) |
| Clean controls with any false alarm: same result in every valid unit | 100.0% | 100.0% |

## Recall by severity

| | Plain | Structured |
|---|---|---|
| Critical | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| Major | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| Minor | – (none) | – (none) |

## Severity-weighted recall

| | Plain | Structured |
|---|---|---|
| Severity-weighted recall | 10/10 = 100.0% | 10/10 = 100.0% |

## Type agreement (structured condition)

Labels decide no detection (decision 61). Over the structured condition's hits and duplicates, the share whose category is the planted error's type id:

| | Structured |
|---|---|
| Overall | 15/19 = 78.9% |
| H1 | – (none) |
| H2 | 3/3 = 100.0% |
| H3 | 6/6 = 100.0% |
| H4 | 3/4 = 75.0% |
| H5 | – (none) |
| H6 | – (none) |
| C1 | – (none) |
| C2 | 3/6 = 50.0% |
| C3 | – (none) |

Plain condition: labels were free text and were not scored (19 distinct labels).

## Structured minus plain

| Metric | Difference | 95% interval (paired bootstrap) |
|---|---|---|
| Overall recall | +0.0 pp | +0.0 pp to +0.0 pp |
| False alarms per report | -0.33 | -1.00 to +0.00 |
| Specificity (by majority) | +0.0 pp | +0.0 pp to +0.0 pp |

Reports in the paired comparison: 4; left out (no majority result in a condition): 0.

## Counts

| | Plain | Structured |
|---|---|---|
| Reports | 4 | 4 |
| Invalid units | 0 | 0 |
| Findings in valid units | 29 | 26 |
| False alarms | 11 | 7 |
| Near-misses | 0 | 0 |
| Duplicates | 6 | 7 |
| Review findings | 0 | 0 |
| Set aside by a verdict of miss | 0 | 0 |
| Still in review | 0 | 0 |
| Findings with a null confidence | 0 | 0 |
| Findings with a null severity | 0 | 0 |
| Dropped findings | 0 | 0 |
| Reports with no majority result | 0 | 0 |

Planted errors by type: H1 0, H2 1, H3 1, H4 1, H5 0, H6 0, C1 0, C2 1, C3 0.
Review items: none prepared (0 review findings).

## Disclosures

The reports are synthetic: drafted by claude-haiku-5-5 and corrected by the owner. Sampling was the API default. One evaluated model was used; the API returned the model string claude-sonnet-5-5. 4 reports were scored (dev split). A detection means the finding quoted the planted sentence or one of its named other places, in the right section, with a token overlap of at least 0.6; an omission is detected only by the owner's verdict. Labels (categories) were not used to decide detections. The adjudication sheet showed no category, condition, repeat, model or run. 0 review item(s) were adjudicated by hand.
