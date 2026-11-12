# pathology-oversight-eval

## For readers from outside

**The question.** Does a short structured review checklist with an error list help Claude (claude-sonnet-5-5) catch errors planted in pathology reports, compared with a plain "find every error" instruction? 30 synthetic reports (22 with 39 planted errors, 8 clean controls), each read 3 times under each prompt.

| Result (30 scored reports) | Plain prompt | Structured prompt | Structured minus plain (95% interval, paired bootstrap) |
|---|---|---|---|
| Planted errors found (overall recall) | 36/39 = 92.3% | 38/39 = 97.4% | +5.1 pp (+0.0 pp to +12.8 pp) |
| False alarms per report (all 30) | 1.38 | 0.43 | -0.94 (-1.33 to -0.62) |
| Clean controls passed by majority | 2/8 = 25.0% | 8/8 = 100.0% | +75.0 pp (+40.0 pp to +100.0 pp) |

- The write-up, with method and limits: [WRITEUP.md](WRITEUP.md)
- Every scored table: [results/scored/summary.md](results/scored/summary.md)
- What was planted, report by report: [data/specs/planting.md](data/specs/planting.md)
- The prompts the model was given: [prompts/](prompts/)
- Every decision and the task log: [handoff.md](handoff.md)

**Checking the results without an API key.** `uv sync`, then `uv run pytest` (the test suite) and `uv run pathqc-eval freeze --check` (the reports, prompts and taxonomy still match the lock taken before the scored run). Then read results/scored/summary.md against results/scored/score.json, which holds every finding and its outcome. Do not run `score` to check: it would rewrite the committed results with a new scorer commit.

All reports are synthetic: no real patient data is anywhere in this repository. What the pilot cannot claim is set out under "Limits" in [WRITEUP.md](WRITEUP.md).

## About the repository

A small research pilot: how well Claude detects deliberately planted errors in synthetic histopathology reports and CBC interpretations, scored against pathologist-verified ground truth. The output is a one-page write-up for the owner's Anthropic Research Residency application. Every design decision, the error taxonomy and the working rules live in [handoff.md](handoff.md).

## Commands

```bash
uv sync                                    # install the locked environment
uv run pathqc-eval validate [data/reports] # validate every report file in the folder
uv run pathqc-eval validate --expect 34 --expect-clean 9 --expect-dev 4   # also enforce counts
uv run pathqc-eval validate --drafts data/drafts                         # drafts mode: errors may be []
uv run pathqc-eval render <file-or-folder> # rewrite each CBC report's Values text from its cbc_values
uv run pathqc-eval spec-check [data/specs/dataset.json]                  # validate the dataset spec
uv run pathqc-eval draft --dry-run         # print the drafting prompts and a cost estimate; no API call
uv run pathqc-eval draft [--ids H-001,C-003] [--force] [--cost-gate 0.50] # draft approved rows (EVAL-02b)
uv run pathqc-eval readable data/drafts   # write data/drafts/_readable/<id>.md to copy sentences from
uv run pathqc-eval plant --init           # write the empty planting sheet data/specs/planting.md
uv run pathqc-eval plant --check          # apply the sheet in memory and list problems; writes nothing
uv run pathqc-eval plant                  # build data/reports/ from drafts + sheet (taxonomy final)
uv run pathqc-eval freeze [--replace]      # hash taxonomy, prompts and dataset into data/prompts.lock.json
uv run pathqc-eval freeze --check          # exit 0 only if every hash still matches the lock
uv run pathqc-eval run --dataset dev --condition plain --dry-run          # messages and estimate; no API call
uv run pathqc-eval run --dataset dev|scored --condition plain|structured --cost-gate USD [--run-id ID] [--workers 4] [--max-calls N]
uv run pathqc-eval smoke --ids H-021,H-022,H-023,C-011 --cost-gate 1.00 [--condition plain]  # live smoke test (EVAL-04b); not evaluation data
uv run pytest                              # run the tests
uv run ruff check .                        # lint
uv run ruff format --check .               # formatting check
```

render only rewrites the Values text from the stored numbers; it never recalculates derived indices, so a planted C2 error is preserved.

## Owner workflow

1. Edit the briefs in `data/specs/dataset.json` and set each row's `brief_status` to `approved`. Review `data/specs/cbc_reference_ranges.json`.
2. `uv run pathqc-eval spec-check` until it prints OK.
3. Drafting run (EVAL-02b, after the key is in `.env`): `uv run pathqc-eval draft`. It refuses any row that is not approved and writes `data/drafts/<id>.json`.
4. `uv run pathqc-eval readable data/drafts` writes `data/drafts/_readable/<id>.md`, each draft's text by section, to copy sentences from.
5. `uv run pathqc-eval plant --init` writes the planting sheet `data/specs/planting.md`: one block per report, `verified: no`, with the split, clean or planted, and the planned types as a comment.
6. Fill in the sheet (see below) and run `uv run pathqc-eval plant --check` until every report prints OK. It works with a draft taxonomy and writes nothing.
7. Set the taxonomy `status` to `"final"`, then `uv run pathqc-eval plant`. It builds `data/reports/<id>.json` for every block without problems and writes `data/reports/_review/<id>.md` (the final text, then each fix and planted error with its quote) for proofreading. A block with problems leaves its existing report untouched and is listed as NOT UPDATED. A report file that cannot be written (read-only, say) is listed as NOT WRITTEN, in plain words, and `plant` carries on with the others and exits 1.
8. `uv run pathqc-eval validate --expect 34 --expect-clean 9 --expect-dev 4`.

Reports in `data/reports/` are generated: never edit them by hand, and never edit a draft. Every change, planted error or not, goes in the sheet, and `plant` rebuilds the reports from the untouched drafts. The same sheet and drafts always give byte-identical reports, and no model takes part. The sheet is published with the dataset as the record of what was planted.

CBC derivation (MCV, MCH, MCHC and absolute counts) happens only at draft time, from the values the drafting model returns. Nothing recalculates them afterwards: a `set:` line changes one stored number and the Values text is re-rendered, so a planted C2 inconsistency is preserved.

The drafting prompts in `prompts/drafting/` are not part of the EVAL-03 freeze: they only produce drafts, which the owner then edits through the sheet and verifies.

## The planting sheet

`data/specs/planting.md` is plain text. Lines starting with `#` are comments and blank lines are ignored. `== H-001 ==` starts a report's block. Every other line is `key: value`, split at the first colon, so values may contain colons. Unknown keys, missing keys and empty values are reported in plain words.

A block holds report-level lines first (`verified: yes` or `no`, required; `verified_on: YYYY-MM-DD`, required when verified is yes), then any number of `[fix]` and `[error]` entries. Fixes apply first and then errors, each in sheet order; error ids are `<id>-E1`, `-E2`, ... in that order. `find` and `remove` must occur exactly once in the named section as it stands at that point. A report with no block is built unchanged with `verified: no`. A clean control with an `[error]`, or a planted report without one, fails. Planted types that differ from the spec's planned types are listed as a notice only.

The examples below use invented text.

**`[fix]`**: corrects the draft without planting an error. It works on text sections only, never on Values, and is allowed in clean and planted reports.

```text
== H-016 ==
verified: yes
verified_on: 2026-11-13
[fix]
section: Gross description
find: The specimen measure 40 x 30 mm.
replace: The specimen measures 40 x 30 mm.
note: Grammar in the draft.
```

**`[error]`, text change**: `section`, `find`, `replace`, with an optional `quote`. The quoted sentence is `quote` if given. In the Synoptic summary it is otherwise the whole changed line. Elsewhere it is the `replace` text, which then needs at least five words; if it is shorter, add a `quote:` line giving the full sentence as it reads after the change.

```text
== H-003 ==
verified: no
[error]
type: H1
severity: major
section: Microscopic description
find: The tumour measures 22 mm.
replace: The tumour measures 32 mm.
quote: The tumour measures 32 mm.
description: Microscopic size contradicts the 22 mm gross size.
rationale: Gross, microscopic and synoptic sizes must agree.
```

**`[error]`, CBC number change**: one `set: <analyte> = <number>` line per number, with analyte names as in `cbc_values` (`MCHC`, `Neutrophils_pct`, ...). Only the stored number changes; nothing is re-derived and the Values text is re-rendered. The quoted sentence is the rendered Values line of `quote_analyte`, which defaults to the first analyte set. A number change that breaks a derived index fails validation unless the error is a C2.

```text
== C-004 ==
verified: no
[error]
type: C2
severity: minor
set: MCHC = 41.0
description: MCHC does not follow from Hb and Hct.
rationale: MCHC = Hb / Hct x 100 would give about 30 g/dL.
```

**`[error]`, omission** (`kind: omission`): delete text with `remove_from` and `remove`, or delete a whole optional section with `remove_section`. Then give the anchor, either `anchor` text or, for CBC, `anchor_analyte`, in `anchor_section`. The anchor section defaults to Values for CBC and to the Synoptic summary for histopathology. The error's section and quoted sentence are the anchor's. A whole removed line takes its line break with it, no double spaces or empty lines are left, and an optional section left empty is dropped.

```text
== H-007 ==
verified: no
[error]
type: H5
severity: major
kind: omission
remove_from: Synoptic summary
remove: Perineural invasion: Not identified
anchor: Lymphovascular invasion: Absent
description: Perineural invasion is not reported.
rationale: PNI is a required synoptic element.

== C-002 ==
verified: no
[error]
type: C3
severity: critical
kind: omission
remove_from: Comment/recommendation
remove: Platelet count of 18 x10^9/L is a critical value; urgent review advised.
anchor_analyte: Platelets
description: The critical platelet count is not flagged.
rationale: A critical value needs a flag and a recommendation.
```

Decision 34 sets the anchor rules: for CBC, the Values line carrying the number concerned; for histopathology, the Synoptic summary line next to where the missing element belongs, or the Diagnosis line if there is none. The validator checks the anchor like any quoted sentence, requires it to be in Values (CBC) or in the Synoptic summary or Diagnosis (histopathology) (decision 43), and its summary counts omissions (`omissions N`). At scoring an omission is never detected automatically: every finding in the report that is not a hit for another error goes to the owner's blind adjudication as a candidate for it (decision 62, 2026-11-12).

The validator also refuses a report with more than three planted errors (decision 23), and requires the last line of every histopathology Synoptic summary to be `Staging edition: AJCC 8th edition` unless one of the report's planted errors quotes that last line (decision 27). Both rules hold for drafts too (EVAL-09).

**Other places** (decision 56): a contradiction has two sides, and the model may quote either, so an `[error]` may name up to three other places in the report. Each is a group of lines after the entry's other keys, in this order: `also_section: <section name>` followed by exactly one of `also_quote` (text left as it is, which must occur exactly once in that section of the built report) or `also_find` with `also_replace` (a second place changed as part of the same error, applied after the entry's main change; `also_find` must occur exactly once at that point, and the place's quote is the whole line holding the replacement). For CBC a group may instead be the single line `also_analyte: <analyte>`: the other place is that analyte's rendered Values line. An incomplete group, a fourth group, a group that repeats the main place, or a section the report does not have is reported in plain words with the block and entry. The built report lists the places under the error's `other_places`; `data/reports/_review/<id>.md` shows them under the error, and the validator checks that each is quoted verbatim in its section and is not the main place (an omission's other places may be in any section). Invented examples:

```text
== H-004 ==
verified: no
[error]
type: H1
severity: major
section: Microscopic description
find: The tumour measures 22 mm.
replace: The tumour measures 32 mm.
quote: The tumour measures 32 mm.
description: Microscopic size contradicts the 22 mm gross size.
rationale: Gross, microscopic and synoptic sizes must agree.
also_section: Gross description
also_quote: a firm lesion 22 mm across

== H-005 ==
verified: no
[error]
type: H3
severity: critical
section: Synoptic summary
find: pT: pT1c
replace: pT: pT3
description: pT3 does not fit an 18 mm tumour.
rationale: pT follows the size for this site.
also_section: Diagnosis
also_find: grade 2, 18 mm.
also_replace: grade 2, 18 mm, pT3.

== C-005 ==
verified: no
[error]
type: C2
severity: minor
set: MCHC = 41.0
description: MCHC does not follow from Hb and Hct.
rationale: MCHC = Hb / Hct x 100 would give about 30 g/dL.
also_analyte: Hb
```

## Evaluation prompts and the two conditions

The user message is the same in both conditions: the report's sections in stored order, each as `## {section name}` followed by its text, separated by one blank line. Nothing else from the report file is sent (no id, split, modality, errors, provenance or flags).

- **plain:** the system message is `prompts/plain.md`, one prompt for both modalities. It never mentions the taxonomy: the isolation check refuses a type id, a type name, a type definition or a severity definition in it.
- **structured:** the system message is the owner's review instruction for the report's modality (`prompts/structured_histopathology.md` or `prompts/structured_cbc.md`: short instructions the owner wrote for this pilot, decision 57), a blank line, `## Error taxonomy` with the severity definitions and that modality's error types only, a blank line, then `prompts/structured_output.md`.

`prompts/manifest.json` lists the four prompt files with `status` `proposed` or `approved`.

In both messages the isolation check also refuses the report id, the fields `is_clean_control`, `provenance` and `error_id`, a planted error's description, rationale or severity reason, and the split in label form: `split:` or `split =` followed by `dev` or `scored` (any case, with quotes or markdown emphasis around), or the quoted key `"split"`. The bare words pass (decision 42).

## Freeze (owner steps)

1. Write the owner's review instruction for each modality into `prompts/structured_histopathology.md` and `prompts/structured_cbc.md`, replacing the `<<OWNER TEXT REQUIRED>>` line.
2. Set all four entries in `prompts/manifest.json` to `"approved"`.
3. Set `status` in `data/taxonomy.json` to `"final"`.
4. `uv run pathqc-eval freeze`. It refuses, listing every unmet condition, unless: the taxonomy is final; all four manifest entries are approved; no prompt file still holds the placeholder; `validate data/reports --expect 34 --expect-clean 9 --expect-dev 4` passes; every report has `provenance.verified` true with a `verified_at` date; and the isolation check passes for every report in both conditions. It does not overwrite an existing lock unless given `--replace`.
5. `uv run pathqc-eval freeze --check`. Scored runs (EVAL-04) call this and refuse to start unless it passes; dev runs do not.

The lock records `created_at`, the taxonomy version, the sha256 of `data/taxonomy.json`, of the four prompt files and of `prompts/manifest.json`, and the dataset hash (sha256 over the sorted lines `<file name>:<sha256>`, one per `data/reports/*.json`) with each report's hash and the report count. All hashes are taken on the file bytes with CRLF normalised to LF.

## Evaluation runs (EVAL-04)

A run covers one dataset (`dev` or `scored`) in one condition (`plain` or `structured`). Each report is reviewed in 3 repeats; a (report, repeat) pair is a unit. The evaluated model is claude-sonnet-5-5 at the API's default reasoning effort and default sampling, with max_tokens 16,000, the same in both conditions (decision 44). Each call sends the system message, one user message and max_tokens only.

Before any call the run refuses, and says why, if:

- scored: `freeze --check` does not pass (the same check);
- dev: there are no dev reports in `data/reports/`, a dev report fails the validator's per-report rules, or (structured) an owner text for a modality in scope still holds the placeholder;
- two files in `data/reports/` hold the same report id (a copy such as `H-001 - Copy.json`), or a report file cannot be read;
- a prompt file the run uses is missing or is not UTF-8 text;
- the messages of any report fail the isolation check;
- resuming: the config differs (below), `runs/<run_id>/` holds calls.jsonl but no config.json, or a line of calls.jsonl is not a call line of this run;
- another invocation is running on the same run id, or the lock file cannot be used. A run holds a lock on `runs/<run_id>/.run.lock` (gitignored) while it goes on; the operating system releases it when the process ends. The lock is checked before the run's files are read, and the config is compared again once it is held.

`--dry-run` constructs no client and needs no `--cost-gate`. It prints the number of reports, units and maximum calls, the full system and user messages for the first report of each modality, and an estimate at 1,752 input and 1,165 output tokens per call at Sonnet prices: the average of the four plain calls of the live smoke test (EVAL-04b) plus 50%, a projection from four calls.

An output that cannot be read as findings, or a call that does not end its turn normally, gets one more attempt; after two such attempts the unit is `invalid` (decision 45). Transport failures are retried up to 3 times, after 2, 8 and 30 seconds, and logged as transport lines; they are not attempts. They are connection errors and timeouts, a request timeout (HTTP 408), a rate limit (429) and server errors (5xx); the SDK's own retries are off, so that each one is logged. A call still failing after its retries, or a call the API rejects for another reason, stops the run once the calls in flight have finished. Findings are read leniently (decision 46): extra keys are ignored and noted, an unusable severity or confidence becomes null, and a finding without a usable quoted_sentence, section or category is dropped and counted.

Each run folder `runs/<run_id>/` holds:

- `config.json`: the run config (dataset, condition, model, sampling, effort, max_tokens, repeats, the dataset, prompt and taxonomy hashes, created_at, cost_gate_usd, the anthropic SDK version and lock_created_at). A scored run takes its hashes from the lock and records the lock's created_at; a dev run computes them with the freeze's own functions, and lock_created_at is null. prompt_hash combines the hashes of the condition's prompt files (plain: `plain.md`; structured: `structured_output.md` and the two owner texts) the way the dataset hash combines the reports.
- `calls.jsonl`: one line per attempt with the ids, attempt number, start time, duration, the model requested and returned, the sha256 of the system and user messages, the full raw output, stop reason, tokens, cost, parse status, parsed findings, dropped findings and notes. A transport failure gets a line with the unit's ids, the error class and the message only; a failure that stopped the run gets the same line marked `"fatal": true`. No request text is stored; the hashes identify it. The file is gitignored and stays local until release (decision 14).
- `results.json`: rebuilt from calls.jsonl at the end of every invocation. One entry per unit, by report id and then repeat (status `valid`, `invalid` or `pending`, attempts, findings, dropped count, model returned, tokens, cost), then the totals: units, valid, invalid, pending, calls, tokens, cost and the distinct models returned. It is committed with the run.

The run id is `<YYYYMMDD-HHMMSS>-<dataset>-<condition>` (UTC) unless `--run-id` is given.

**Resume.** Run the same command again with the same `--run-id`. Units already valid or invalid in calls.jsonl are skipped, and an unfinished unit continues at its next attempt. The config must be identical apart from created_at, including the cost gate and the SDK version; otherwise the run refuses and names the fields that differ. To change any of them, start a new run id.

**The gate.** `--cost-gate USD` is required for every real run; there is no default. It is a true ceiling (owner decision, 2026-11-11). Spend is cumulative over the run, earlier invocations included, read from calls.jsonl. Before a call starts, its maximum possible cost is reserved: input no larger than the UTF-8 bytes of its system and user texts plus 100 tokens of wrapping, and the whole 16,000 tokens of output, at the dearer of the requested model's price and that of any model the API has returned in the run (about $0.17 for a report of a few thousand bytes). A call is not started if the spend so far, plus the reservations of the calls in flight, plus its own reservation would pass the gate; when no call is in flight the run stops and reports what it has. When a call is logged its reservation is released and its real cost counted instead. So a gate needs headroom of one reservation per worker for every worker to be busy: with `--workers 4` and a $1.00 gate, at most about $0.32 can be spent before the fourth call may start (1.00 - 4 x 0.17). A call abandoned by a second Ctrl+C is billed but never logged, so the next invocation cannot count it (the second-Ctrl+C gap, left as it is). `--max-calls N` stops cleanly after N attempts in this invocation, for running in pieces. `--workers N` (default 4) sets how many calls run at once; one thread writes every file.

A real run needs `ANTHROPIC_API_KEY` in `.env`; without it the run stops with a message naming the variable before any call. It prints one line per finished unit (report, repeat, status, findings, tokens, cost, running total), then the totals, and `stopped early: …` with the reason when the gate, `--max-calls` or a failure stopped it. If the run is interrupted (Ctrl+C) or a line cannot be written, no new call starts, the calls already in flight are waited for and logged (they are billed; Ctrl+C again abandons them), and results.json is rebuilt; resume with the same `--run-id`. The exit code is 0 when every unit is finished or `--max-calls` stopped the run, 130 after Ctrl+C, and 1 otherwise.

### Smoke test (EVAL-04b)

`smoke` is the first live contact with the API, not evaluation data (`--condition` takes only `plain`; `structured` is refused): it reads the named dev drafts from `data/drafts/` in memory (writing nothing under `data/`), sends each once in the plain condition, and writes `runs/smoke-<UTC timestamp>/` (config.json and results.json say "smoke test; not evaluation data"; the scorer refuses the folder). Section B of the EVAL-N1 prompt limits the whole stage to 8 calls and $1.00, so: no transport retry; at most two calls per report; the calls and spend of every earlier smoke run count against those limits; a gate above $1.00 is refused; each call is assumed to cost its ceiling (the texts' UTF-8 bytes plus 100 tokens of input, 16,000 tokens of output) before it starts, one call at a time; `ANTHROPIC_INFERENCE_GEO` must be unset; only one smoke run can go on at a time (a lock on `runs/_smoke_stage/.run.lock`); and a model string other than claude-sonnet-5-5 in a response fails the test. Before the first call it prints each request with the texts replaced by their lengths. One gap remains: a call abandoned by a second Ctrl+C is billed but not logged, so later smoke runs cannot count it.

## Scoring and adjudication (EVAL-05; detection by place since EVAL-12)

```bash
uv run pathqc-eval map-list --runs <run id> [<run id> ...]                  # the distinct labels in the runs, with counts
uv run pathqc-eval adjudicate prepare --dataset dev|scored --runs <plain run id> <structured run id> [--replace]
uv run pathqc-eval adjudicate apply --dataset dev|scored                    # read the filled sheet
uv run pathqc-eval adjudicate status --dataset dev|scored                   # verdicts filled and total
uv run pathqc-eval score --dataset dev|scored --runs <plain run id> <structured run id> [--provisional]
```

The scorer turns one plain and one structured run over the same dataset into the numbers for the write-up. Its settings are in `src/pathqc_eval/scoring_config.py` (decision 47, confirmed by the owner on 2026-11-11; `OWNER_CONFIRMED` is `True`).

**How a finding is judged** (decisions 61 and 62, 2026-11-12). The model's label (its "category") plays no part: the plain condition invents its own labels, and only the structured condition was given the taxonomy. What counts is where the finding points. For each planted error of the finding's report, the scorer looks at each of the error's places, its main sentence and any named other places (decision 56), and asks whether the finding names the same section and how much its quoted sentence overlaps that place's sentence (token containment, the larger of the two directions):

- **Hit**: the right section and an overlap of at least 0.6 at some place. If a finding hits more than one error, the highest overlap wins, then the lowest error id; a finding that is a hit is not reviewed for any other error. A second hit on the same error in a unit is a **duplicate**, neither a hit nor a false alarm.
- **Review** (the owner decides, blind): the right section but an overlap from 0.4 up to 0.6 at the best place (`borderline_overlap`); or an overlap of at least 0.6 but another section (`section_mismatch`). The best place is the one giving the best outcome, then the highest overlap, then the main place.
- **Omissions** are never detected automatically: in a report with an omission error, every finding that is not a hit for another error goes to the owner as a candidate for that omission (`omission_candidate`), one item for each omission error of the report.
- A finding that is not a hit may be a review item for several errors, one item each. Its verdicts combine like this: a hit for every error judged `detected`; otherwise a near-miss if any verdict is `near_miss`, a miss if any is `miss`, and a false alarm only when every verdict is `false_alarm`. There is no automatic near-miss any more.
- Anything else, and every finding in a clean report, is a **false alarm**.

An error is detected in a unit when at least one finding is a hit for it or is judged detected. For calibration, a hit, a duplicate, or a verdict of detected or near_miss counts as right and a false alarm as wrong; a verdict of miss, or an item still open, is left out and counted. No category map is used: `data/category_map.json`, if present, is ignored.

**Type agreement** is reported separately, for the structured condition only: over its hits and duplicates (one per finding and error, verdicts included), the share whose label, normalised, is the error's type id, overall and per type as k/n. For the plain condition the summary says that the labels were free text and were not scored, and gives the number of distinct labels.

Owner steps:

1. The scorer defaults are confirmed (decision 47, 2026-11-11). Should `OWNER_CONFIRMED` ever be set back to `False`, `score --dataset scored` refuses.
2. After the scored runs, `adjudicate prepare --dataset scored --runs <plain run id> <structured run id>` collects every finding that needs a person and writes `results/scored/adjudication/`: `adjudication_sheet.md` to fill in, `adjudication.json` (the items) and `adjudication_hidden.json` (where each item came from; do not open it). Findings identical in report, section, quoted sentence (ignoring case and spacing), rationale and candidate error become one item, from either run. An item shows the finding's report, section, quoted sentence and rationale, the candidate planted error with its other places, and the reason it needs review in plain words; never a category, condition, repeat, model or run (decisions 9 and 63). The category stays in the run results and is joined back after the reveal. `adjudication_hidden.json` and everything under `results/*/provisional/` are gitignored until the reveal; the task that does the final scoring commits them. A second `prepare` refuses; `--replace` starts again only while no verdict or reason has been written, in the sheet or in `adjudication.json`; any other text line in the sheet also blocks it, but comment lines (`#`) do not, so keep notes elsewhere. While the sheet is open, do not run `map-list` on the scored runs: its counts of labels per condition could hint at where a finding came from.
3. For every item fill in `verdict:` (`detected`, `miss`, `near_miss` or `false_alarm`) and `reason:`, then run `adjudicate apply`. Nothing is written while the sheet has a problem; each problem names the item. `adjudicate status` shows how many verdicts are filled.
4. `score --dataset scored --runs <plain run id> <structured run id>` writes `results/scored/score.json` and `results/scored/summary.md` (tables to paste and a disclosures paragraph). It refuses while any item lacks a verdict. Once every verdict is filled it reads `adjudication_hidden.json`, checks that it still matches the runs, and writes `adjudication_log.json` (when the adjudication was prepared, completed and joined, the number of items, and the sha256 of `adjudication.json`). After that the verdicts cannot change. `--provisional` is refused on the scored split (owner decision, 2026-11-11): the scored split is scored only once every verdict is in. On the dev split, `--provisional` scores before the adjudication is complete: every number the open items affect is shown as a range, from all of them counted against the model to all counted for it, in `results/<dataset>/provisional/` with PROVISIONAL in every title. **A provisional score is not blind**: its ranges are by condition, and with few items they can show which condition an item came from. It therefore leaves out the per-error and per-finding tables. Every provisional score made before the last verdict is logged in `results/<dataset>/provisional/provisional_log.json`, and the final summary says how many the log records. Keep that file: the provisional folder's other files may be deleted, but without the log the summary can no longer disclose the provisional scores. Score provisionally only when you need to, ideally not before the sheet is filled in.

`map-list --runs <plain run id> <structured run id>` lists every distinct label in the runs (normalised: lower case, single spaces, no trailing punctuation, closing brackets and quotes included) with its count per condition, and writes `results/<dataset>/category_strings.json`. It maps nothing.

A unit is one report in one repeat of one condition. An error is detected by majority when it is detected in at least two valid units: 2 of 3, or both of 2. A report with fewer than two valid units has no majority result in that condition; it is listed, and left out of the majority figures and of the paired comparison. The metrics are per-type and overall recall (Wilson intervals), false alarms per report, specificity on clean controls (by majority and per unit), Brier score and ECE, repeat consistency, recall by severity (critical, major and minor separately, as k/n with Wilson intervals), severity-weighted recall (weights 3, 2, 1), type agreement (above), and structured minus plain for recall, false alarms and specificity with a paired bootstrap over reports (10,000 resamples, seed 20261115). The summary's disclosures say that a detection means the finding quoted the planted sentence or one of its named other places, that labels were not used to decide detections, and that the adjudication sheet showed no category, condition, repeat, model or run.

Before scoring, the two runs must be one plain and one structured run of the dataset, with equal dataset and taxonomy hashes, no pending unit, and every report of the split in repeats 1 to 3; no report id may be held by two files in `data/reports/`. For the scored split also: `freeze --check` passes, each run's hashes equal the lock's, and `OWNER_CONFIRMED` is `True`. If `data/reports/` or the taxonomy changed after the dev runs, dev scoring goes on with a warning in its output. `score.json` and `summary.md` carry no clock time, so scoring twice on the same inputs gives byte-identical files; `score.json` records the run ids, the scorer's git commit, the lock's created_at and the settings.

## Licences

Code: MIT ([LICENSE](LICENSE)). Dataset: CC BY 4.0 ([data/LICENSE-DATASET](data/LICENSE-DATASET)).
