# pathology-oversight-eval

A small research pilot: how well Claude detects deliberately planted errors in synthetic histopathology reports and CBC interpretations, scored against pathologist-verified ground truth. The output is a one-page write-up for the owner's Anthropic Research Residency application. Every design decision, the error taxonomy and the working rules live in [handoff.md](handoff.md).

## Commands

```bash
uv sync                                    # install the locked environment
uv run pathqc-eval validate [data/reports] # validate every report file in the folder
uv run pathqc-eval validate --expect 34 --expect-clean 9 --expect-dev 4   # also enforce counts
uv run pytest                              # run the tests
uv run ruff check .                        # lint
uv run ruff format --check .               # formatting check
```

## Licences

Code: MIT ([LICENSE](LICENSE)). Dataset: CC BY 4.0 ([data/LICENSE-DATASET](data/LICENSE-DATASET)).
