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
uv run pathqc-eval draft [--ids H-001,C-003] [--force] [--cost-gate 0.25] # draft approved rows (EVAL-02b)
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

## Licences

Code: MIT ([LICENSE](LICENSE)). Dataset: CC BY 4.0 ([data/LICENSE-DATASET](data/LICENSE-DATASET)).
