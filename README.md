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
4. Plant errors by editing a draft: add entries to `errors` and set `is_clean_control` (false for a planted report). For a C2 error, edit the numbers in `cbc_values`, then run `uv run pathqc-eval render <file>` and quote the rendered line.
5. `uv run pathqc-eval validate --drafts data/drafts` until it passes.
6. Move finished files to `data/reports/`.
7. `uv run pathqc-eval validate --expect 34 --expect-clean 9 --expect-dev 4`.

CBC derivation (MCV, MCH, MCHC and absolute counts) happens only at draft time, from the values the drafting model returns. Nothing recalculates them afterwards.

The drafting prompts in `prompts/drafting/` are not part of the EVAL-03 freeze: they only produce drafts, which the owner then edits and verifies.

## Recording an omission error

A planted error has `kind` `"statement"` (the default) or `"omission"`. An omission quotes an *anchor* that occurs word for word in the report:

- CBC: the Values line carrying the number concerned, for example the rendered `Hb: ...` line for an unflagged critical haemoglobin.
- Histopathology: the Synoptic summary line next to where the missing element belongs (the Diagnosis line if there is none).

```json
{"error_id": "H-007-E2", "type": "H5", "kind": "omission", "section": "Synoptic summary",
 "quoted_sentence": "Lymphovascular invasion: Absent", "severity": "major", "severity_reason": null,
 "description": "Perineural invasion is not reported.", "rationale": "PNI is a required synoptic element."}
```

The validator checks the anchor like any quoted sentence, and its summary counts omissions (`omissions N`). At scoring, an omission is detected when the mapped type matches and the finding's section equals the anchor's section; sentence overlap is not required. A finding with the matching type in another section goes to blind adjudication.

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
