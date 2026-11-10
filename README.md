# pathology-oversight-eval

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
7. Set the taxonomy `status` to `"final"`, then `uv run pathqc-eval plant`. It builds `data/reports/<id>.json` for every block without problems and writes `data/reports/_review/<id>.md` (the final text, then each fix and planted error with its quote) for proofreading. A block with problems leaves its existing report untouched and is listed as NOT UPDATED.
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

Decision 34 sets the anchor rules: for CBC, the Values line carrying the number concerned; for histopathology, the Synoptic summary line next to where the missing element belongs, or the Diagnosis line if there is none. The validator checks the anchor like any quoted sentence, and its summary counts omissions (`omissions N`). At scoring, an omission is detected when the mapped type matches and the finding's section equals the anchor's section; sentence overlap is not required. A finding with the matching type in another section goes to blind adjudication.

## Evaluation prompts and the two conditions

The user message is the same in both conditions: the report's sections in stored order, each as `## {section name}` followed by its text, separated by one blank line. Nothing else from the report file is sent (no id, split, modality, errors, provenance or flags).

- **plain:** the system message is `prompts/plain.md`, one prompt for both modalities. It never mentions the taxonomy.
- **structured:** the system message is the owner's text for the report's modality (`prompts/structured_histopathology.md`, the PathQC text, or `prompts/structured_cbc.md`, the CBC checklist), a blank line, `## Error taxonomy` with the severity definitions and that modality's error types only, a blank line, then `prompts/structured_output.md`.

`prompts/manifest.json` lists the four prompt files with `status` `proposed` or `approved`.

## Freeze (owner steps)

1. Paste the PathQC text into `prompts/structured_histopathology.md` and the CBC checklist into `prompts/structured_cbc.md`, replacing the `<<OWNER TEXT REQUIRED>>` line.
2. Set all four entries in `prompts/manifest.json` to `"approved"`.
3. Set `status` in `data/taxonomy.json` to `"final"`.
4. `uv run pathqc-eval freeze`. It refuses, listing every unmet condition, unless: the taxonomy is final; all four manifest entries are approved; no prompt file still holds the placeholder; `validate data/reports --expect 34 --expect-clean 9 --expect-dev 4` passes; every report has `provenance.verified` true with a `verified_at` date; and the isolation check passes for every report in both conditions. It does not overwrite an existing lock unless given `--replace`.
5. `uv run pathqc-eval freeze --check`. Scored runs (EVAL-04) call this and refuse to start unless it passes; dev runs do not.

The lock records `created_at`, the taxonomy version, the sha256 of `data/taxonomy.json`, of the four prompt files and of `prompts/manifest.json`, and the dataset hash (sha256 over the sorted lines `<file name>:<sha256>`, one per `data/reports/*.json`) with each report's hash and the report count. All hashes are taken on the file bytes with CRLF normalised to LF.

## Licences

Code: MIT ([LICENSE](LICENSE)). Dataset: CC BY 4.0 ([data/LICENSE-DATASET](data/LICENSE-DATASET)).
