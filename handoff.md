# HANDOFF — pathology-oversight-eval
Last updated: 2026-11-10 by agent (EVAL-01b)
Labels: OWNER VERIFIED (decided or checked by the owner) · AGENT VERIFIED (agent's checks green, reported) · PENDING (not yet done or checked)

## Purpose
A small research pilot: how well Claude detects deliberately planted errors in synthetic histopathology reports and CBC interpretations, scored against pathologist-verified ground truth. Output: a one-page write-up for the owner's Anthropic Research Residency application, due 18 November 2026. Separate from every other project; its own folder, repo and Claude Code session.

## Roles
- Owner: dataset, error taxonomy, every planted error, ground truth, adjudication, write-up, release decisions. OWNER VERIFIED
- Orchestrator (Cowork session): plans, writes EVAL-NN prompts, audits every reply. OWNER VERIFIED
- Agent (Claude Code in this folder): harness, runs, scoring, tests, this file. OWNER VERIFIED

## Decisions (all OWNER VERIFIED, 2026-11-04)
1. Evaluated model: claude-sonnet-5-5 only; the `model` field returned by the API is recorded on every call.
2. Drafting model: claude-haiku-5-5, disclosed in the write-up. Planted errors are authored by the owner, never by a model.
3. Temperature 0; 3 repeats per report per condition; per-repeat and majority (≥ 2 of 3) results both kept.
4. Output JSON for both conditions: quoted_sentence, section, category, severity, confidence (0–1), rationale. The plain condition never sees the taxonomy and returns category as free text; categories are mapped to taxonomy types at scoring. The structured condition receives the taxonomy explicitly.
5. Dev split: 4 reports outside the 30 (3 planted + 1 clean control), used only to debug the harness and prompts. Dev runs need no freeze.
6. Freeze: taxonomy and both prompts are hashed into a lock file immediately before the scored run; scored runs refuse to start if any hash differs; nothing is edited afterwards. The taxonomy is finalised before any error is planted.
7. Metrics. Primary: per-type recall, false alarms per report, specificity on clean controls. Secondary: Brier score, ECE (5 bins), repeat consistency, severity-weighted recall. Paired bootstrap CIs over reports for the condition comparison.
8. Matching rule: detected = mapped type matches AND section matches AND quoted sentence overlaps the planted sentence (token containment ≥ 0.6, the larger of the two directions, after case and punctuation normalisation). Right sentence but wrong type = miss, logged as a near-miss. Ambiguous cases adjudicated by the owner with the reason logged.
9. Adjudication is blind: the adjudication file shows report, section, quoted sentence, category and rationale only; condition, repeat and model stay hidden until every verdict is entered; the scorer reveals them afterwards and logs that order.
10. category_map.json: proposed by the agent from the dev run, approved by the owner; the same string always maps the same way; nothing is remapped after scoring; unmapped strings go to adjudication.
11. Clean controls: 8 of 30.
12. CBC format: values table with units and reference ranges, plus interpretation text.
13. Structured condition: the owner's PathQC prompt verbatim (Custom GPT wrapper removed); the owner supplies the text.
14. Repo: pathology-oversight-eval, private until the owner approves release of the whole repo at once; visibility changed only by the owner. Dataset CC BY 4.0, code MIT. runs/*/calls.jsonl gitignored until release, then published.
15. Stack: Python 3.12, uv lockfile, anthropic, pydantic, pytest, JSON/JSONL data.
16. No API key ever enters the repo. The owner alone puts it in `.env`, only when the harness step needs it.
17. CBC Values text is generated deterministically from cbc_values by render_cbc_values; the validator requires the section text to equal the rendered text. A C2 error lives in the numbers; the rendered line is what gets quoted.
18. CBC units are fixed and validated: Hb g/dL; RBC x10^12/L; Hct %; MCV fL; MCH pg; MCHC g/dL; RDW %; WBC and all absolute counts x10^9/L; differential percentages %; Platelets x10^9/L; MPV fL. Anything else fails validation.
19. A planted error's severity must be one of its type's default severities. An override is allowed only with a non-empty severity_reason; severity_reason is null otherwise.
20. Licence holder in LICENSE and data/LICENSE-DATASET: Dr. Umesh Krishna Sureshbabu.
21. Line endings: .gitattributes with `* text=auto eol=lf`; everything is stored and checked out as LF. Freeze hashes (EVAL-03) are computed on LF bytes.

## Error taxonomy (OWNER VERIFIED as draft; to be finalised before any error is planted)
Severity: critical = would change patient management; major = would need an amended report; minor = internal inconsistency without clinical consequence.
- H1 Gross–microscopic mismatch: size, number, laterality or site in the gross contradicted in microscopy or synoptic. Major.
- H2 Diagnosis unsupported by morphology: microscopic description does not support the stated diagnosis or grade. Critical.
- H3 Staging inconsistency: pT/pN contradicts reported size, depth of invasion or node findings. Critical.
- H4 Node arithmetic error: positive nodes exceed total, or text and synoptic counts differ. Major.
- H5 Required element missing or contradictory: margins, LVI or PNI absent, or margin status contradicts the description. Major or minor.
- H6 IHC–diagnosis inconsistency: immunoprofile contradicts the diagnosis. Critical.
- C1 Value–interpretation mismatch: interpretation text contradicts the numbers. Major.
- C2 Derived-index inconsistency: MCH/MCHC inconsistent with Hb, RBC and Hct; differential not summing to 100; absolute counts inconsistent with WBC. Minor or major.
- C3 Missed critical finding: a critical value or finding with no flag, comment or recommendation. Critical.

## Section conventions for synthetic reports (OWNER VERIFIED)
- Histopathology: Clinical details; Specimen; Gross description; Microscopic description; Immunohistochemistry (when used); Diagnosis; Synoptic summary (size, grade, margins, LVI, PNI, nodes, pT/pN); Comment.
- CBC: Values table (Hb, RBC, Hct, MCV, MCH, MCHC, RDW, WBC with differential % and absolute counts, platelets, MPV, each with reference range); Interpretation; Comment/recommendation.

## Working rules for the agent
- Every reply ends with the report block below. Every claim tagged [RAN] / [READ] / [INFERRED].
- No API call unless the prompt authorises it with a model and a cost estimate. Never print secrets; names only.
- Pre-flight: clean tree, remote = HEAD, HEAD is the pinned commit or later with only EVAL- commits since.
- `uv run pytest` runs as its own step and its exit code is read before any commit. Commit messages start with the task ID.
- Only what the prompt asks; anything else goes under "Questions for the owner". Reverting own uncommitted edits is allowed but listed under Deviations.
- Every command is run so that its exit code is visible and quoted in the report — in bash `cmd; echo "exit=$?"`, in PowerShell `cmd; "exit=$LASTEXITCODE"`. "Exit not captured" never appears in a report; re-run any command whose exit code was lost.
- .venv/ is listed in .gitignore explicitly.

## Open items
- PENDING — Taxonomy finalised by the owner before planting (target: before EVAL-02 drafts are edited).
- PENDING — PathQC prompt text supplied by the owner (for EVAL-03).
- PENDING — Key added to `.env` by the owner immediately before EVAL-04.

## Task log
| ID | Date | Title | Status | Label |
|---|---|---|---|---|
| Step 0 | 2026-11-04 | Repo, hygiene files, handoff | DONE | OWNER VERIFIED |
| EVAL-01 | 2026-11-04 | Scaffold, schemas, taxonomy, validator | DONE | AGENT VERIFIED |
| EVAL-01b | 2026-11-10 | Validator rules, CBC renderer, hygiene | DONE | AGENT VERIFIED |

## Report format (every reply ends with this block)
=== EVAL REPORT: EVAL-NN <title> ===
Status: DONE | PARTIAL | BLOCKED
What was asked: <one line>
What was done: <short, factual, each claim tagged [RAN]/[READ]/[INFERRED]>
Files changed: <path — one-line reason> | none
Commands run: <command — exit code — duration — one-line result>
Checks: pytest N passed, N failed | lint/format result
Git: branch <name>; commit <sha> "<message>"; push <ok/failed>; remote HEAD matches local HEAD: yes/no
API spend this task: <USD, or "no API calls">
Deviations from the prompt: <list> | none
Claims I could not verify: <list> | none
Questions for the owner: <list> | none
handoff.md updated: yes/no
=== END ===
