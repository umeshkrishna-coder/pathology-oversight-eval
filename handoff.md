# HANDOFF — pathology-oversight-eval
Last updated: 2026-11-11 by agent (EVAL-N1 S5: EVAL-04)
Labels: OWNER VERIFIED (decided or checked by the owner) · AGENT VERIFIED (agent's checks green, reported) · REPORTED (stated, not checked) · NOT TESTED · PENDING (not yet done)

## Purpose
A small research pilot: how well Claude detects deliberately planted errors in synthetic histopathology reports and CBC interpretations, scored against pathologist-verified ground truth. Output: a one-page write-up for the owner's Anthropic Research Residency application, due 18 November 2026. Separate from every other project; its own folder, repo and Claude Code session.

## Roles
- Owner: dataset, error taxonomy, every planted error, ground truth, adjudication, write-up, release decisions. OWNER VERIFIED
- Orchestrator (Cowork session): plans, writes EVAL-NN prompts, audits every reply. OWNER VERIFIED
- Agent (Claude Code in this folder): harness, runs, scoring, tests, this file. OWNER VERIFIED

## Decisions (OWNER VERIFIED unless marked PENDING; 1–28 on 2026-11-04, 29–46 on 2026-11-10)
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
22. Modality split: 34 reports = 23 histopathology + 11 CBC. Scored 30: 20 histopathology (5 clean) + 10 CBC (3 clean). Dev 4: 2 histopathology planted, 1 CBC planted, 1 histopathology clean.
23. Each planted report carries 1 to 3 planted errors, the owner's choice per report.
24. Report briefs: the agent proposes all 34 in data/specs/dataset.json (brief_status proposed); the owner edits and marks each approved; the draft command refuses unapproved rows. Planned error types in the spec are the owner's plan and are never shown to the drafting model.
25. Drafting: claude-haiku-5-5, one call per report, default temperature, prompts in prompts/drafting/ (outside the freeze); every call logged to data/drafts/_calls.jsonl with usage and cost, no content; cumulative cost gate $0.25 per run.
26. `render` rewrites the Values text from cbc_values exactly as stored and never recomputes derived indices; derivation happens only at draft time, so a planted C2 error survives a re-render.
27. Every histopathology Synoptic summary ends with the fixed line "Staging edition: AJCC 8th edition"; staging errors are judged against the stated edition.
28. The drafting model's isolation (no taxonomy ids or names, no planned error types, no instruction to include errors) is enforced by a test over every spec row.
29. Lint: ruff with the explicit rule set E, F, I, B; code is fixed, the rule list is not widened.
30. The summary's `overrides` counts only non-default severities that carry a severity_reason.
31. Two tracks from EVAL-02 onwards. Owner track: approve the spec, drafts (EVAL-02b), final taxonomy, planting, validation. Agent track: prompts and freeze (EVAL-03), harness (EVAL-04) and scorer with blind adjudication (EVAL-05), built against test fixtures and a fake client. The tracks meet at the dev run. Targets: PathQC prompt text by 12 Nov; dataset final 14 Nov; scored run 15 Nov; adjudication 16 Nov; write-up 16–17 Nov; application due 18 Nov.
32. Sampling (amends decision 3): the current API does not accept a temperature setting for the evaluated model, so runs use the API's default sampling. 3 repeats per report per condition and majority (2 of 3) are unchanged. RunConfig records `sampling: "default"`. The write-up discloses this and reports repeat consistency.
33. IHC spread in the spec is kept as proposed.
34. Omission errors (amends decision 8): a planted error may be `kind: "omission"`. It quotes an anchor sentence that exists in the report: for CBC, the Values line carrying the number concerned; for histopathology, the Synoptic line next to where the missing element belongs (or the Diagnosis line if none). An omission is detected automatically when the mapped type matches and the finding's section equals the anchor's section; sentence overlap is not required. A finding in the same report with the matching type but another section goes to the owner's blind adjudication.
35. Structured condition (amends decision 13): histopathology reports use the owner's PathQC text verbatim, then the histopathology taxonomy, then the output block. CBC reports use a short CBC review checklist written by the owner, then the CBC taxonomy, then the output block. The plain condition uses one prompt for both modalities.
36. Drafting (amends decision 25): reasoning effort high; cumulative cost gate $0.50 per run.
37. Planting is done through data/specs/planting.md, written by the owner. `pathqc-eval plant` applies it deterministically to the drafts and writes data/reports/; drafts are never edited; reports are never edited by hand; no model takes part. The sheet is published with the dataset as the record of what was planted. The tool refuses to build while the taxonomy status is not "final".
38. For this one run [EVAL-N1, the overnight build run] the rule "one task per prompt, no chaining" is set aside. Stages are chained on condition that every stage passes its own gate and gets its own commit and its own record. Advice noted: bundled work hides which change caused a fault, so a stage that fails its gate is set aside and nothing is built on it.
39. The Project Harness Kit is adopted for this pilot at Light size. The Operating Charter, the decision register and the roadmap are kept by the orchestrator outside the repo; handoff.md stays the session's notes; the repo gets a CLAUDE.md. Three typed words, each typed by the owner in a session: `freeze approved`, `scored run approved`, `release approved`. Nothing in this prompt [the EVAL-N1 prompt] is one of those words. For small API tasks, pasting a prompt that states model, estimate and hard stop is the owner's yes. Status labels gain REPORTED and NOT TESTED. A fix to existing behaviour ships with a test that fails on the old code and passes on the new.
40. Drafting instructions corrected after the audit of the first drafts: the brief's pT and pN are used exactly and no stage group or risk class is added that the brief does not give; the CBC drafting message shows the reference ranges. H-009, H-021, C-008 and C-009 were drafted again. Single-sentence corrections elsewhere are the owner's [fix] entries.
41. Taxonomy final as version 1.0. C2 now names MCV with MCH and MCHC.
42. Isolation, split check: only label forms are refused (`split:` followed by dev or scored, or the quoted key "split"), not the bare words. The user message must still equal the report's section text exactly.
43. Omission anchors: the validator requires an omission's anchor to be in Values (CBC) or in Synoptic summary or Diagnosis (histopathology).
44. Evaluated-model settings: claude-sonnet-5-5 at the API's default reasoning effort (no effort setting is sent), default sampling, max_tokens 16,000, identical in both conditions, recorded in every run config.
45. Unreadable outputs: a call whose output cannot be read as findings is repeated once; both attempts are logged. If the second is also unreadable the repeat is marked invalid and counted. Majority is computed over the valid repeats: with 3 valid, 2 of 3; with 2 valid, both; with fewer than 2 valid, the report has no majority result in that condition and is listed separately, never scored silently.
46. Lenient reading of findings: extra keys are ignored and recorded; an unusable severity or confidence becomes null (excluded from calibration, counted); a finding without a usable quoted_sentence, section or category is dropped and counted. The raw output of every call is kept.
47. PENDING — Scorer defaults awaiting the owner's confirmation; scoring of the scored split refuses until they are confirmed: (a) a finding goes to blind adjudication when its category is unmapped, when the overlap is between 0.4 and 0.6 with type and section right, when type and sentence are right but the section differs, or when an omission is reported under another section; (b) false alarms per report are the mean count per valid unit, and a clean control passes when a unit has none; (c) for calibration a hit, a duplicate or a near-miss counts as 1 and a false alarm as 0; (d) severity weights 3, 2, 1; (e) Wilson intervals for per-type recall; (f) bootstrap of 10,000 resamples with seed 20261115.

## Error taxonomy (OWNER VERIFIED, final, version 1.0, 2026-11-10)
Severity: critical = would change patient management; major = would need an amended report; minor = internal inconsistency without clinical consequence.
- H1 Gross–microscopic mismatch: size, number, laterality or site in the gross contradicted in microscopy or synoptic. Major.
- H2 Diagnosis unsupported by morphology: microscopic description does not support the stated diagnosis or grade. Critical.
- H3 Staging inconsistency: pT/pN contradicts reported size, depth of invasion or node findings. Critical.
- H4 Node arithmetic error: positive nodes exceed total, or text and synoptic counts differ. Major.
- H5 Required element missing or contradictory: margins, LVI or PNI absent, or margin status contradicts the description. Major or minor.
- H6 IHC–diagnosis inconsistency: immunoprofile contradicts the diagnosis. Critical.
- C1 Value–interpretation mismatch: interpretation text contradicts the numbers. Major.
- C2 Derived-index inconsistency: MCV, MCH or MCHC inconsistent with Hb, RBC and Hct; differential not summing to 100; absolute counts inconsistent with WBC. Minor or major.
- C3 Missed critical finding: a critical value or finding with no flag, comment or recommendation. Critical.

## Section conventions for synthetic reports (OWNER VERIFIED)
- Histopathology: Clinical details; Specimen; Gross description; Microscopic description; Immunohistochemistry (when used); Diagnosis; Synoptic summary (size, grade, margins, LVI, PNI, nodes, pT/pN, staging edition); Comment.
- CBC: Values table (Hb, RBC, Hct, MCV, MCH, MCHC, RDW, WBC with differential % and absolute counts, platelets, MPV, each with reference range); Interpretation; Comment/recommendation.

## Working rules for the agent
- Read CLAUDE.md first; it holds the rules that bind this session.
- Every reply ends with the report block below. Every claim tagged [RAN] / [READ] / [INFERRED].
- No API call unless the prompt authorises it with a model and a cost estimate. Never print secrets; names only.
- Pre-flight: clean tree, remote = HEAD, HEAD is the pinned commit or later with only EVAL- commits since.
- `uv run pytest` runs as its own step and its exit code is read before any commit. Commit messages start with the task ID.
- Only what the prompt asks; anything else goes under "Questions for the owner". Reverting own uncommitted edits is allowed but listed under Deviations.
- Every command is run so that its exit code is visible and quoted in the report — in bash `cmd; echo "exit=$?"`, in PowerShell `cmd; "exit=$LASTEXITCODE"`. "Exit not captured" never appears in a report; re-run any command whose exit code was lost.
- .venv/ is listed in .gitignore explicitly.
- Owner-editable areas: data/specs/, data/drafts/, data/reports/, prompts/ and data/taxonomy.json. The owner may have uncommitted edits there while tasks run. Pre-flight "clean tree" means `git status --short` shows nothing outside those areas; list whatever it shows inside them and do not open for editing, stage, revert or commit those files, except files the current task itself creates.
- Never `git add -A` or `git add .`; stage by explicit path, and quote `git status --short` and `git diff --cached --stat` before every commit. Files of the owner's that the agent did not create in the task are never opened for editing, staged, reverted or committed.

## Open items
- PENDING — Owner pastes the PathQC text into prompts/structured_histopathology.md and a CBC checklist into prompts/structured_cbc.md, and approves the four manifest entries (target 12 Nov).
- PENDING — Dev run (24 calls) once the four dev reports are in data/reports/ and the owner texts are in place.
- PENDING — Owner confirms or changes the scorer defaults in decision 47; until OWNER_CONFIRMED is True in src/pathqc_eval/scoring_config.py, scoring the scored split refuses.
- PENDING — Owner's questions from the EVAL-N1 run about CLAUDE.md and handoff.md (OVERNIGHT_REPORT.md Part 4).

## Task log
| ID | Date | Title | Status | Label |
|---|---|---|---|---|
| Step 0 | 2026-11-04 | Repo, hygiene files, handoff | DONE | OWNER VERIFIED |
| EVAL-01 | 2026-11-04 | Scaffold, schemas, taxonomy, validator | DONE | AGENT VERIFIED |
| EVAL-01b | 2026-11-10 | Validator rules, CBC renderer, hygiene | DONE | AGENT VERIFIED |
| EVAL-02 | 2026-11-10 | Dataset spec and drafting tool (dry run) | DONE | AGENT VERIFIED |
| EVAL-03 | 2026-11-10 | Prompts, message assembly, freeze | DONE | AGENT VERIFIED |
| EVAL-02a | 2026-11-10 | Owner's spec approval recorded (0 edits) | DONE | OWNER VERIFIED |
| EVAL-02b | 2026-11-10 | 34 drafts (Haiku 5.5, high effort) | DONE ($0.0480 measured) | AGENT VERIFIED |
| EVAL-02c | 2026-11-10 | Planting sheet tool | DONE | AGENT VERIFIED |
| EVAL-02c-fix | 2026-11-11 | Planting tool audit (EVAL-N1 S1): 20 review findings fixed test-first, readable moved to its own module | DONE | AGENT VERIFIED |
| EVAL-H1 | 2026-11-11 | CLAUDE.md and harness decision (EVAL-N1 S2; decisions 38–39) | DONE | AGENT VERIFIED |
| EVAL-02d | 2026-11-11 | Drafting instructions corrected; H-009, H-021, C-008, C-009 drafted again (EVAL-N1 S3; decision 40) | DONE ($0.0044 measured) | AGENT VERIFIED |
| EVAL-02e | 2026-11-11 | Taxonomy final, version 1.0 (EVAL-N1 S4; decision 41) | DONE | AGENT VERIFIED |
| EVAL-04 | 2026-11-11 | Evaluation harness (fake client), isolation and anchor fixes | DONE | AGENT VERIFIED |

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
