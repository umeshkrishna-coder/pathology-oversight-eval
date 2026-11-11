# OVERNIGHT_REPORT — EVAL-N1 overnight build run (2026-11-10)

Written stage by stage as the run goes (prompt section E5). Every claim carries [RAN], [READ] or
[INFERRED]; every command carries its exit code. Starting commit: `a699037` (EVAL-02c) [RAN].

Run status: IN PROGRESS — S0 to S7 done.

## Part 1. Stages

| stage | status | commit | tests passing after | review rounds | findings confirmed and fixed |
|---|---|---|---|---|---|
| S0 pre-flight | PASS | none (no commit of its own) | 353 | — | — |
| S1 EVAL-02c audit (EVAL-02c-fix) | PASS | cccad44 | 417 | 3 | 20 confirmed and fixed; 5 rejected with reasons |
| S2 EVAL-H1 CLAUDE.md and harness decision | PASS | e85eeb3 | 417 | 2 | 1 fixed in the stage (decision wording); 6 settled in the record; 1 rejected |
| S3 EVAL-02d drafting fixes and four redrafts | PASS | 2269b0d | 440 | 3 | 15 confirmed and fixed (tests first); 0 rejected |
| S4 EVAL-02e taxonomy final 1.0 | PASS | eafc0f0 | 440 | 1 | 0 defects; 2 recorded (exit codes, plant guard); 2 rejected (out of scope) |
| S5 EVAL-04 evaluation harness (fake client) | PASS | 51f79be | 673 | 3 | 32 confirmed and fixed test-first (11, 13, 8; one the lead's own regression), 2 more before review, 18 weak tests strengthened; 4 rejected with reasons (3 to the owner) |
| S6 EVAL-05 scorer, blind adjudication, metrics | PASS | 61982e3 | 816 | 3 | 27 confirmed and fixed test-first (10, 11, 6), 28 weak tests strengthened; 58 mutants, all killed; 1 reading; 7 items to the owner |
| S7 EVAL-05b end-to-end rehearsal | PASS | d09cc0e | 818 | 3 | 1 breach of A4 by the test's own isolation check, caught in review and replaced; 21 confirmed and fixed; 27 mutants, all killed; no src defect found; 1 deviation (bootstrap intervals pinned) |

## Part 2. For the owner

(Written at S9.)

## Part 3. Defaults taken, for the owner to confirm

1. Dates. The run crossed midnight into 2026-11-11. Decisions keep the label the prompt gives them ("OWNER VERIFIED, 2026-11-10"); task-log rows and "Last updated" carry the actual date of the stage (2026-11-11) [RAN `date`].
2. Review rounds. The prompt allows three review rounds per stage. Findings of the third round were fixed with a test that failed first, the lead's mutation check and a re-run of the reviewer's own reproduction scripts, without a fourth review round (S1) [RAN].
3. S1 word count for the five-word minimum: a word is a whitespace-separated token with at least one letter or digit, which matches the scorer's tokens (S1 review finding) [RAN].
4. S2 decisions 38 and 39 hold the owner's decisions 1 and 2 word for word, with two clarifications by the agent in square brackets: "[EVAL-N1, the overnight build run]" after "this one run" and "[the EVAL-N1 prompt]" after "this prompt", so that a later session does not read "this run" as its own. Removing the bracketed words gives the owner's text exactly (checked by script). The owner may keep or drop them [RAN].
5. S5 prompt_hash. The lock holds no single prompt hash, so a run's prompt_hash combines the sha256 of the condition's prompt files (plain: plain.md; structured: structured_output.md and both owner texts) the way the dataset hash combines the reports [RAN].
6. S5 a dev run's dataset_hash is taken over every file in data/reports/ (both splits), with the freeze's own function, so editing any report after a dev run makes its resume refuse (dataset_hash differs) [RAN].
7. S5 resume identity: every RunConfig field except created_at, so the cost gate and the SDK version too; to change one, start a new run id [RAN].
8. S5 a valid attempt needs the stop reason end_turn and a readable output; attempt 2 follows either failure [RAN].
9. S5 failures: a call still failing after its 3 transport retries, or any other API error (logged with "fatal": true), stops the run once the calls in flight have finished (exit 1). Ctrl+C, or a calls.jsonl line that cannot be written: no new call starts, the calls in flight are logged, results.json is rebuilt (exit 130 or 1); a second Ctrl+C abandons the calls in flight [RAN].
10. S5 results.json lists unfinished units as "pending", with a pending total [RAN].
11. S5 transport failures are exactly the stage's list: connection errors and timeouts, HTTP 408 (read as the stage's "timeout"), 429 and 500–599; the API's x-should-retry header is not consulted [RAN].
12. S5 lenient reading: extra top-level keys are accepted and noted; a list item that is not an object is dropped; every nulled severity or confidence is noted; the rationale is stripped; code fences of backticks or tildes are accepted as CommonMark allows (a longer closing fence, an info string, content on the opening line) [RAN].
13. S5 an escaped unpaired surrogate in an output (\ud800) is replaced with U+FFFD, with a note, so the line can be written as UTF-8; raw_text then differs from the output in that character [RAN].
14. S5 refusals beyond the stage text, all before any call: one report id in two files; an unreadable report of either split; a missing prompt file, or one that is not UTF-8 or holds NUL; calls.jsonl without config.json, or a line that is not strictly a call line of this run; a run id outside letters, digits, '.', '_' and '-', longer than 100, ending in '.', or a Windows device name; --workers or --max-calls below 1; a gate that is not a positive finite number; another invocation on the same run id (a lock on runs/<id>/.run.lock, gitignored), or a lock file that cannot be used [RAN].
15. S5 exit codes: 0 when every unit is finished or --max-calls stopped the run; 130 after Ctrl+C; 1 otherwise [RAN].
16. S5 split labels: quotes, markdown emphasis and a joined prefix around `split:` still count; the key is "split" in double quotes, or 'split' in any quotes before a colon; 'split' in quotes in prose passes (decision 42) [RAN].
17. S5 tests/conftest.py blanks ANTHROPIC_API_KEY and disables dotenv for every test, so no test can load the key [RAN].
18. S5 the README's decision-34 paragraph names the anchor sections (decision 43) [RAN].
19. S6 normalise_category drops every trailing Unicode punctuation character, closing brackets and quotes included ("C2 (indices)." becomes "c2 (indices"); map keys must be written that way, and the map refuses a key that is not [RAN].
20. S6 provisional scores: the per-error and per-finding tables are left out; counts by condition are ranges like the metrics; intervals are bracketed; each provisional score made while a verdict is missing is logged in results/<dataset>/provisional/provisional_log.json, copied into adjudication_log.json at the reveal, and its count disclosed (decision 9) [RAN].
21. S6 the disclosure goes beyond "how many items were adjudicated by hand": it says the sheet names no condition, repeat or model, that a finding's category can still suggest its condition, and what the provisional log records [RAN].
22. S6 refusals beyond the stage text: pending units; runs that do not cover exactly the split's reports in repeats 1 to 3; one report id in two files; config.json and results.json disagreeing; category-map checks (unknown keys, keys not normalised, keys equal to a taxonomy id or "other", a key given twice); map-list with a run named twice or runs of different splits; log files read strictly [RAN].
23. S6 dev scoring goes on with a warning when data/reports/ or the taxonomy changed after the runs; the scored split refuses [RAN].
24. S6 after the reveal, apply and prepare --replace refuse; score refuses an adjudication that no longer matches the runs (other findings, none left, a changed candidate error or review reason) and an adjudication.json changed after the reveal [RAN].
25. S6 `prepare --replace` is blocked by a verdict, a reason or any other text line in the sheet, or an unreadable adjudication.json; comment lines are not protected (README) [RAN].
26. S6 the scorer commit carries "-dirty" when src/ has uncommitted changes and is "unknown" when git fails; `adjudicate apply` and `status` take --dataset; a scored `prepare` needs what a scored `score` needs (lock, approved map, OWNER_CONFIRMED) [RAN].
27. S6 extra output fields (title, provisional, the two hashes, models_returned, drafted_by, warnings, undefined_resamples, more counts, per-finding mapped type, overlap, reason and verdict); BOOTSTRAP_SEED also seeds the item-id shuffle; the handoff Decisions header reads "OWNER VERIFIED unless marked PENDING" [RAN].

## Part 4. Left for the owner

1. Confirm the reading of "one block per spec row in id order" for `plant --init` as the spec's row order (histopathology first), which the committed template follows (Part 5 item 2). Sorting by id would put C-001 to C-011 first; the committed template is not regenerated either way.
2. handoff.md's working rule "No API call unless the prompt authorises it with a model and a cost estimate" is weaker than decision 39 and CLAUDE.md ("a model, an estimate and a hard stop"). They do not contradict (CLAUDE.md is stricter and is read first), but S2 did not authorise editing the rule, so it is left for the owner to align (S2 review) [READ].
3. CLAUDE.md's "Never" list is narrower than section A of the EVAL-N1 prompt. Compared rule by rule (S2 reviews): A1, tests may run the typed-word actions only in temporary folders with the fake client; A2, never "approve" owner content, and the category map and its approval are owner-only; A3, never run `plant` in its building form; A4, never "open" `.env`, and no secret in any file, log, commit or report; A6, never `git clean`, `git reset --hard` or `git stash drop`, and branch main only; A7, never weaken, skip, xfail or delete a test, never widen or narrow the ruff rule list (decision 29 covers only widening), no new dependencies; A8, nothing copied in from outside the repository. Section A binds this run; whether CLAUDE.md should carry these after the run is the owner's call [READ].
4. CLAUDE.md says "Evaluation prompts and the taxonomy are the owner's words". prompts/plain.md and prompts/structured_output.md were written by the agent (EVAL-03) and are still "proposed" in prompts/manifest.json; the run treats them as owner-only content (A2) and never edits them (S2 review) [READ].
5. CLAUDE.md says "Heads, test counts, spend and open items are read from `handoff.md`", but handoff.md has no place for commit heads or test counts (Part 5 item 3). The agent did not change handoff.md's format; they are in this report's Part 1. The owner may want a line or column for them in handoff.md (S2 review) [READ].
6. The plain-condition isolation check (prompting.check_eval_isolation) looks for type ids, type names and severity definitions, but not for the type definitions, so a copied definition in prompts/plain.md would pass the freeze. Decision 4 says the plain condition never sees the taxonomy. Today's plain.md holds none (S4 review R2). Whether to extend the check is the owner's call [READ; RAN by R2].
7. The cost gate is not a hard ceiling. The stage's rule assumes the next call costs as much as the dearest so far ($0.06 before any call), but one call at the 16,000-token limit costs about $0.17, so the total can pass the gate by the difference for each call in flight (R3 measured $0.66 against a $0.25 gate with 4 workers). Accept it, or choose a stricter rule (assume the max_tokens price for every call, or cap --workers). Until then a run under a hard stop uses --workers 1 and a gate about $0.17 below the stop; S8 does (S5 review R3) [RAN].
8. `--max-calls` counts attempts; each attempt can send up to 3 more requests through transport retries. Section B counts calls; S8 states how it counts them (S5 review R3) [RAN].
9. Assignment forms of the split ("split = dev", "'split' = 'dev'") are not refused: decision 42 names `split:` and the quoted key only. Say whether '=' forms should count; no draft or prompt holds 'split' today (S5 review R3) [RAN].
10. The EVAL-01 test tests/test_validate.py::test_cli_empty_reports_folder_exits_zero reads the repository's data/reports/ and expects it to be empty, so it will fail once `plant` builds the reports. Outside S5; listed for the final audit (S5 review R1) [READ].
11. Decision 9 against S6's `--provisional` (6.8): ranges and counts by condition, shown before every verdict is entered, can reveal where an item came from. The scorer leaves out the per-item tables, logs each provisional score and discloses the count, and the README says a provisional score is not blind. Accept, or forbid provisional scoring of the scored split while the sheet is open (S6 reviews) [RAN].
12. Decision 10's "nothing is remapped after scoring" is recorded (the map's version and sha256 in score.json), not enforced: an approved map can be edited and the split scored again without a warning (S6 R2) [RAN].
13. Decision 10's "unmapped strings go to adjudication" and the wording of 47(a) against 6.4: an unmapped finding goes to adjudication only when its section and quoted sentence match a planted error; otherwise it is a false alarm. The code follows 6.4; confirm 47(a) before setting OWNER_CONFIRMED (S6 R3) [READ].
14. Decision 9 says the adjudication file shows report, section, quoted sentence, category and rationale only; 6.7 adds the candidate planted error and the review reason. The stage text was followed (S6 R3) [READ].
15. Decision 8 says right sentence but wrong type is a miss logged as a near-miss; 47(c) counts a near-miss as 1 in calibration. Both are as written; confirm with 47 (S6 R3) [READ].
16. results/ is not gitignored, so adjudication_hidden.json (which item came from which condition) and the provisional outputs could be committed before the reveal. Gitignore them, or keep results/ unstaged during adjudication; decide before the scored adjudication (S6 R3) [RAN].
17. Smaller S6 points: a deleted provisional_log.json cannot be detected (the summary then says it records no provisional score; README asks to keep the file); PENDING_DEFAULTS is the literal text of decision 47, so a changed constant needs both updated; running map-list on the scored runs while the sheet is open is warned against in the README, not prevented; item ids past 999 become "A1000" [RAN; READ].

## Part 5. Contradictions between this prompt and the repository, and how each was read

1. S1 says "no code path in plant.py may write under data/drafts/", while the EVAL-02c specification (which S1 audits) requires `pathqc-eval readable <folder>` to write `<folder>/_readable/<id>.md`, and S1's own stage command is `readable data/drafts`; in a699037 that writer lived in plant.py. Round 1 recorded a reading; the round-2 reviews (R1 and R3) showed the conflict was not forced, so it was resolved instead of read: `readable` moved to its own module, src/pathqc_eval/readable.py, with byte-identical output on the 34 drafts, and a test pins that plant.py's only file writer is write_outputs (data/reports/). Both the S1 text and the specification now hold literally [RAN].
2. EVAL-02c says `plant --init` writes "one block per spec row in id order". Read as the spec's own row order: ids ascending within each modality, histopathology first, which is the order of data/specs/dataset.json, spec-check and `plant --check`. The committed template is in this order and S1 forbids regenerating it; a test now pins that the blocks follow the spec rows [READ; RAN].
3. CLAUDE.md (S2, copied verbatim) says "Heads, test counts, spend and open items are read from `handoff.md`", but handoff.md holds no commit heads and no test counts; they are in this report (Part 1). Following CLAUDE.md's own rule ("report that first and change nothing"), the agent changed neither file's format and listed it for the owner (Part 4 item 5) [READ].
4. CLAUDE.md says "bare `python` is not on PATH". A `python` is on PATH, but it is the Windows Store alias that only prints "Python was not found" (exit 49, S0). There is no working bare interpreter, so the instruction holds in effect; recorded rather than changed, since the text is verbatim [RAN].
5. S9 item 3 asks handoff.md to receive "the decision from the top of this prompt about this run (next free number, OWNER VERIFIED, 2026-11-10)". That is owner decision 1, which S2 recorded as decision 38. Read as already met: S9 will not add a duplicate (S2 review R3 OF-5) [READ].
6. S3 step 8 asks for "every sentence or line containing the word \"stage\" other than the fixed staging-edition line". Excluding that line only makes sense if "staging" counts, so Table B also lists sentences with "staging" (four more rows; a superset of the literal reading). The table is for the owner to check each stage group (S3 review R3 OF-1) [READ; RAN].
7. S5 step 4 says transport lines carry "the error class and message only". A line has to name its unit, so the lines also carry run_id, report_id, condition and repeat, and a failure that stopped the run is the same line marked "fatal": true. Read as: no request or response content on these lines (S5 reviews) [READ].
8. S5 step 7 lists "Last updated" EVAL-04 and the task-log row with the handoff.md edits before the step-8 commit; run rule D9 puts them in the record commit. Read as D9, as S3 and S4 did [READ].
9. S5 step 9 says "In the reply"; under the corrections rule it is the S5 record [READ].
10. S6 6.2 "drop a trailing colon or full stop" is read as the trailing run of colons and full stops, so "Diagnosis.:" still matches "Diagnosis" (S6 R1) [READ].
11. S6 6.8's output list names the per-error table and the outcome of every finding; decision 9 keeps condition and repeat hidden until every verdict is entered. Under the corrections rule the decision wins, so a provisional score leaves those two tables out; the final score has them (S6 reviews) [READ].
12. S7 step 7 asks that every headline number equal a value worked out by hand. The comparison's bootstrap intervals come from 10,000 seeded resamples and cannot be worked by hand; the test pins them at the scorer's values, so a change to the resampling still shows. Every other headline number is worked in the docstrings [RAN].

## Part 6. API spend, per stage, from the logs

| stage | model | calls | USD (from the logs) |
|---|---|---|---|
| S0 | — | 0 | 0 |
| S1 | — | 0 | 0 (no API path in S1; R3 checked each round) |
| S2 | — | 0 | 0 (documents only) |
| S3 | claude-haiku-5-5 | 4 | 0.004447 (data/drafts/_calls.jsonl lines 35–38: 0.001354 + 0.001758 + 0.000576 + 0.000759) |
| S4 | — | 0 | 0 |
| S5 | — | 0 | 0 (fake client only; R3 confirmed each round that no real client was built) |
| S6 | — | 0 | 0 (no API path in the scorer; R3 checked each round) |
| S7 | — | 0 | 0 (fake client only; R3 checked each round) |

## Part 7. Stage records

### S0 — Pre-flight (no commit of its own)

Checklist
1. On `main`; `git ls-remote origin main` equals `git rev-parse HEAD`; HEAD is a699037 or later with only EVAL- commits after it; `git log --oneline -8` quoted; starting commit noted — met [RAN].
2. `git status --short` shows nothing outside the owner-editable areas — met: it shows nothing at all [RAN].
3. `.env` exists, `git check-ignore .env` prints `.env`, the key line is present (count 1, never printed), ANTHROPIC_INFERENCE_GEO not set — met [RAN].
4. `uv run pytest` passes — met: 353 passed [RAN].
5. OVERNIGHT_REPORT.md created at the root with the header and S0 results — met (this file; committed with the first record commit) [RAN].

Commands
- `git branch --show-current` — exit 0 — `main` [RAN]
- `git rev-parse HEAD` — exit 0 — `a699037b73086cdf8d9d65ca57579b75cba5370a` [RAN]
- `git ls-remote origin main` — exit 0 — `a699037b73086cdf8d9d65ca57579b75cba5370a refs/heads/main` (equals HEAD) [RAN]
- `git log --oneline -8` — exit 0 [RAN]:
  ```
  a699037 EVAL-02c: planting sheet tool
  83ae954 EVAL-02b: 34 drafts
  fadb975 EVAL-02a: owner's spec approval
  32ac420 EVAL-03: prompts, message assembly, freeze
  b92159d EVAL-02: dataset spec, drafting tool (dry run)
  0a2ab8a EVAL-01b: validator rules, CBC renderer, hygiene
  c417761 EVAL-01: scaffold, schemas, taxonomy, validator
  5aa222f Step 0: repo, hygiene files, handoff
  ```
  HEAD is a699037 itself, so there are no commits after it to check [RAN].
- `git status --short` — exit 0 — empty output [RAN]
- `test -f .env` — `.env exists`; `git check-ignore .env` — exit 0 — prints `.env`; `git ls-files --error-unmatch .env` — `.env` not tracked [RAN]
- `grep -c "^ANTHROPIC_API_KEY=." .env` — exit 0 — `1` (the line itself was never printed) [RAN]
- ANTHROPIC_INFERENCE_GEO: not set in the environment; `grep -c "^ANTHROPIC_INFERENCE_GEO" .env` — exit 1 — `0` (name only) [RAN]
- `uv run pytest -q` — exit 0 — `353 passed in 13.65s` [RAN]
- Baseline: `uv run ruff check .` — exit 0 — `All checks passed!`; `uv run ruff format --check .` — exit 0 — `39 files already formatted` [RAN]
- Environment: uv 0.13.7, Python 3.12.16, anthropic 2.4.0, pydantic 2.14.2 [RAN]; bare `python` resolves only to the Windows Store stub (`Python was not found`, exit 49) [RAN].

Safety measure used for the whole run [RAN]: review sub-agents run every command with `ANTHROPIC_API_KEY=` set empty in their environment. python-dotenv's `load_dotenv(override=False)` skips a key that is already present in the environment (checked in its source: `if k in os.environ and not self.override: continue`), so no reviewer command can load the key from `.env`. Corrected at S2 (review R3 OF-6): the anthropic SDK client itself does not refuse an empty key (it then looks for ANTHROPIC_AUTH_TOKEN, ANTHROPIC_PROFILE or a profile on disk); what refuses is the project's own wrapper, which checks ANTHROPIC_API_KEY before it constructs the SDK client (AnthropicDraftClient; S5's evaluation client must do the same) [READ]. Checked by name only at S2: `.env` defines one variable, ANTHROPIC_API_KEY; the process environment defines one ANTHROPIC_ variable, ANTHROPIC_BASE_URL, whose host is api.anthropic.com (the default endpoint; only the scheme and host were printed); no Anthropic profile folder exists [RAN].

### S1 — EVAL-02c audit: planting sheet tool — PASS

Stage commit `cccad44` "EVAL-02c-fix: full rule set for built reports, readable in its own module, robustness", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = cccad44f9c337e9388a2bc1f87b6d7893adb0aa7 [RAN]. Three review rounds, each with fresh read-only R1, R2 and R3 sub-agents [RAN].

#### Checklist (45 items, all met)

Evidence is R1's (round 3, line numbers as of that round) unless marked; items 1, 32, 33, 42, 44 and 45 were completed after the last review [RAN].

1. Audit commit a699037 (EVAL-02c) against the EVAL-02c specification with the three reviews; commit any confirmed fix as `EVAL-02c-fix: <what>`; if n... — **met** — audited with three review rounds; 20 confirmed findings fixed, 5 rejected with reasons; fix committed as cccad44 `EVAL-02c-fix: ...` and pushed [RAN/READ by R1 round 3; items 1, 32, 33, 42, 44, 45 completed after review: RAN]
2. A built report must pass the full validator rule set: establish whether `check_report(model, taxonomy, drafts=True)` skips a rule that should apply... — **met** — src/pathqc_eval/plant.py:679-681 now calls check_report(model, taxonomy) with drafts=False. src/pathqc_eval/validate.py:206-209 shows drafts=True skips only check_clean_control, so that was the skipped rule. tests/test_plant.py:576-594 asserts the call is m...
3. `set` must never re-derive anything. — **met** — src/pathqc_eval/plant.py:526-532: each set line changes only cbc[name]['value'], then Values is re-rendered. src/pathqc_eval/render.py:37-47 prints the stored numbers and derives nothing. Tests: tests/test_plant.py:450-466 (MCHC 41.0 with Hb 10.0 and Hct 33...
4. No code path in plant.py may write under data/drafts/. — **met** — I read plant.py in full. Its only file writes are in write_outputs (src/pathqc_eval/plant.py:842-863), to root/data/reports and data/reports/_review. The readable writer moved to src/pathqc_eval/readable.py:46-71; plant.py imports only the constant READABLE...
5. The restriction of omission anchors to named sections (decision 34) is NOT added in this stage (it belongs to S5). — **met** — src/pathqc_eval/plant.py:539 takes anchor_section as given, with the default from plant.py:36 and no allow-list. src/pathqc_eval/validate.py:91-99 only checks that the section exists in the report. validate.py is unchanged (not in git status).
6. Stage commands: `uv run pathqc-eval readable data/drafts`; `uv run pathqc-eval plant --check` (expected: 9 OK and 25 "no planted errors yet"). — **met** — Ran on the repo: `ANTHROPIC_API_KEY= uv run pathqc-eval plant --check` gave exit 1 and the last line 'plant --check: 9 OK, 25 with problems, 0 sheet problem(s); nothing written'. 25 lines end in 'no planted errors yet (...)'; OK for H-016..H-020, H-023, C-0...
7. data/specs/planting.md (the template) exists; it is not regenerated and no entry is added to it. — **met** — data/specs/planting.md is unchanged against a699037 (`git diff --stat a699037 -- data/specs/planting.md` is empty). Its mtime is 2026-11-10 23:39:52, before the a699037 commit at 23:40:37. It holds 34 'verified: no' lines and 25 '# [error]' lines; grep for ...
8. Ground rules: no API calls; no [error]/[fix] entry, description or rationale written into the owner's sheet; tests use temporary folders and invent... — **met** — No model client in plant.py or readable.py (imports at plant.py:10-26, readable.py:10-13). data/drafts/_calls.jsonl is unchanged (git status) and there are no runs/ logs. The sheet is unchanged (item 7). Tests use tmp_path trees and invented fixtures: tests...
9. handoff.md records the owner decision on planting (OWNER VERIFIED, 2026-11-10) with the specified content, under the next free decision number. — **met** — handoff.md:50 holds decision 37 with the specified text verbatim. handoff.md:13 reads 'Decisions (all OWNER VERIFIED; 1–28 on 2026-11-04, 29–37 on 2026-11-10)'. At 83ae954 the last decision was 36 (git show 83ae954:handoff.md, line 49), so 37 is the next fr...
10. Sheet: a line starting with `#` is a comment; blank lines are ignored. — **met** — src/pathqc_eval/plant.py:103-106: lines are stripped; blank lines and '#' lines are skipped. Test: tests/test_plant.py:123-157.
11. `== H-001 ==` starts a report block; inside it report-level lines, then any number of `[fix]` and `[error]` entries. — **met** — src/pathqc_eval/plant.py:63 and 107-128 (block line, then report-level lines, then [fix]/[error] entries). Test: tests/test_plant.py:123-157.
12. Every other line is `key: value`, split at the first colon, value trimmed, values may contain colons; unknown keys, missing required keys and empty... — **met** — src/pathqc_eval/plant.py:129-156: split at the first colon, key and value stripped, plain messages for unknown keys and empty values. plant.py:196-197: missing key. Tests: tests/test_plant.py:123-157 (colon inside a value), 160-198.
13. Report-level keys: `verified: yes|no` (required); `verified_on: YYYY-MM-DD` (required when verified is yes). — **met** — src/pathqc_eval/plant.py:562-582. Tests: tests/test_plant.py:240-259, 562-564.
14. `[fix]`: `section`, `find`, `replace`, `note`; allowed in clean and planted reports; text sections only, never Values. — **met** — src/pathqc_eval/plant.py:40, 209-214, 500-501. Values is refused at plant.py:429-434. Fixes are not restricted to clean or planted reports. Tests: tests/test_plant.py:240-259, 1041-1051.
15. `[error]` common keys: `type` (a taxonomy id), `severity`, `description`, `rationale`; optional `severity_reason`, `kind` (statement default, or om... — **met** — src/pathqc_eval/plant.py:41-42 and 247-258: required keys; type checked as a taxonomy id at 248-251; severity; kind defaults to statement.
16. Statement, text change: `section`, `find`, `replace`; optional `quote`. — **met** — src/pathqc_eval/plant.py:43, 286-288, 506-525.
17. Statement, CBC number change: one or more `set: <analyte> = <number>` lines (analyte names as in cbc_values); optional `quote_analyte` (default the... — **met** — src/pathqc_eval/plant.py:44, 149-151, 217-240, 278-285, 526-532. Line 532 uses quote_analyte or the first set analyte. Tests: tests/test_plant.py:476-485, 1009-1013.
18. Omission: `remove_from` + `remove`, or `remove_section` (an optional section deleted whole); then `anchor_section` (default Values for cbc, Synopti... — **met** — src/pathqc_eval/plant.py:36, 45-52, 261-277, 533-546. Tests: tests/test_plant.py:363-403, 422-447, 487-507.
19. Applied per report in sheet order, fixes first then errors; start from data/drafts/<id>.json; the draft file is never written. — **met** — src/pathqc_eval/plant.py:605-616 keeps entries in sheet order; 649-652 applies fixes, then errors; 658 works on a deep copy. plan only reads drafts (plant.py:735-751, 765-784). Tests: tests/test_plant.py:1022-1039, 724-732.
20. `find` and `remove` must occur exactly once in the named section as it stands at that point; otherwise the block fails, saying how many times it oc... — **met** — src/pathqc_eval/plant.py:437-450: the message gives the count and the readable file path. Sections are updated in place, so each later entry sees the text as it stands at that point. Tests: tests/test_plant.py:325-360, 999-1007.
21. `replace` must differ from `find`. — **met** — src/pathqc_eval/plant.py:457-459. Test: tests/test_plant.py:1016-1020.
22. Removing a whole line removes its line break; no double spaces or empty lines are left behind; an optional section left empty is dropped. — **met** — src/pathqc_eval/plant.py:344-381, the round-3 rewrite: a removed first or last line takes the adjacent run of blank lines with it; a line between two runs takes the run after it. plant.py:475-482: an optional section left empty is dropped; a required sectio...
23. `set` changes the stored number only; nothing is re-derived; the Values text is re-rendered with render_cbc_values. — **met** — src/pathqc_eval/plant.py:526-530; src/pathqc_eval/render.py:37-47.
24. quoted_sentence: text change → `quote` if given, otherwise in Synoptic summary the whole line containing the replacement, otherwise the `replace` t... — **met** — src/pathqc_eval/plant.py:512-525: quote if given; else the whole Synoptic line; else the replace text when it has at least 5 words (word_count, plant.py:388-391); else the plain message. plant.py:532: the rendered Values line. plant.py:539-546: the anchor, ...
25. error_id is `<report id>-E<n>` in sheet order. — **met** — src/pathqc_eval/plant.py:550 and 652 (enumerate over the errors in sheet order). Test: tests/test_plant.py:401.
26. is_clean_control comes from the spec; a clean report with an [error], or a planted report with none, fails. — **met** — src/pathqc_eval/plant.py:634-644, 662. Tests: tests/test_plant.py:528-543.
27. provenance: drafted_by and drafted_at from the draft; edited_by owner; verified and verified_at from the sheet. — **met** — src/pathqc_eval/plant.py:664-670. Tests: tests/test_plant.py:219-234, 240-259.
28. The built report must pass every validator rule; failures are reported under its block. — **met** — src/pathqc_eval/plant.py:671-686: pydantic validation, then every check_report rule; reasons go into the block's problems prefixed 'validation:'. They are printed under the block by plant.py:787-791 and 860-862. Tests: tests/test_plant.py:468-473, 510-525, ...
29. Planted types that differ from the spec's planned_error_types are a notice, not a failure. — **met** — src/pathqc_eval/plant.py:690-697; src/pathqc_eval/cli.py:243-245, 262-264. Tests: tests/test_plant.py:567-573, 1124-1134.
30. `pathqc-eval readable <folder>`: for each report JSON in the folder, write `<folder>/_readable/<id>.md`: the id as a heading, then each section nam... — **met** — src/pathqc_eval/readable.py:19-24, 46-71; src/pathqc_eval/cli.py:84-87, 298-302. On a copy of the 34 drafts, every readable file equals '# id' followed by '## section' and the stored text, exactly (check_readable.py: 34 checked, 0 mismatches).
31. `pathqc-eval plant --init`: writes the template sheet (format comments; one block per spec row in id order (reading recorded in OVERNIGHT_REPORT.md... — **met** — src/pathqc_eval/plant.py:866-919 (TEMPLATE_HEADER, template). src/pathqc_eval/cli.py:209-215 refuses an existing sheet. data/specs/planting.md:1-25 are the format comments; :27-38 is a block with the comment line and a commented-out example. Tests: tests/te...
32. `pathqc-eval plant --check`: parse and apply in memory; one line per report (OK, or each problem in plain words with the block and entry number); w... — **met** — the round-3 regression (a draft whose JSON makes the reader raise a plain ValueError) is fixed: plant.py load_draft `except ValueError`; test test_a_draft_with_an_integer_too_long_to_read_is_reported_in_plain_words failed before; `plant --check` on the repo prints one line per report
33. `pathqc-eval plant`: refuses unless taxonomy status is "final"; builds every block without problems into data/reports/<id>.json (through write_repo... — **met** — same fix as 32; plus a draft holding an unpaired surrogate is now NOT UPDATED instead of emptying the existing report (load_draft check; io.write_report_json encodes before opening); tests failed before
34. `.gitignore` adds `data/drafts/_readable/` and `data/reports/_review/`. — **met** — .gitignore:6-7 lists 'data/drafts/_readable/' and 'data/reports/_review/'. `git status --ignored` shows data/drafts/_readable/ as ignored.
35. Tests, parser: comments, blocks, entries, colon inside values, unknown key, missing key, empty value, duplicate block, block for an id not in the s... — **met** — tests/test_plant.py:123-157 (comments, blocks, entries, colon inside a value), 160-165 (unknown key), 198-202 (missing key), 175-179 (empty value), 189-195 (duplicate block), 212-216 (id not in the spec), 219-234 (missing block: built unchanged, verified no).
36. Tests, apply: text fix; text error with the three quote rules (given, synoptic line, five-word minimum failing with the plain message); find occurr... — **met** — tests/test_plant.py: 240-259 (text fix); 262-298 and 316-322 (the three quote rules); 325-348 (find 0 and 2 times); 363-420 (whole-line removal); 422-436 (optional section); 439-447 (required section); 450-466 (MCHC 41.0 with Hb 10.0 and Hct 33.0); 468-473 ...
37. Tests, determinism: same sheet and drafts give byte-identical reports twice; drafts byte-identical before and after. — **met** — tests/test_plant.py:724-732: two runs give byte-identical reports, and the drafts snapshot is unchanged.
38. Tests, commands: `--init` refuses an existing sheet; `--check` writes nothing; `plant` refuses on a draft taxonomy; a failing block leaves an exist... — **met** — tests/test_plant.py:654-670 (--init refuses), 687-694 (--check writes nothing), 696-706 (draft taxonomy refused), 735-748 (failing block listed NOT UPDATED, files byte-identical), 753-770 (golden readable for histopathology and cbc). The fixtures tests/fixt...
39. README: the hand-editing workflow replaced by the sheet workflow, one worked example of each entry type using invented text; states that reports ar... — **met** — README.md:29-40 gives the sheet workflow; it replaces the step 'Plant errors by editing a draft' from 83ae954's README. README.md:40: 'Reports in data/reports/ are generated: never edit them by hand'. README.md:54-122: one invented example each of [fix], te...
40. handoff.md: the decision; "Last updated" EVAL-02c; task-log row `EVAL-02c | <date> | Planting sheet tool | DONE | AGENT VERIFIED`. — **met** — handoff.md:2 'Last updated: 2026-11-10 by agent (EVAL-02c)'; handoff.md:50 decision 37; handoff.md:94 '| EVAL-02c | 2026-11-10 | Planting sheet tool | DONE | AGENT VERIFIED |'.
41. Run on the repo (EVAL-02c, historical): `readable data/drafts` (drafts exist); `plant --init`; `plant --check` (every planted report "no planted er... — **met** — data/drafts holds 34 drafts. data/drafts/_readable/ holds 34 generated files (ignored), identical to my fresh run. `git show --stat a699037` lists data/specs/planting.md | 386 +, the empty template with 34 blocks and no entries. The current `plant --check` ...
42. Checks and commit: pytest as its own step; ruff check and format; explicit staging; quote `git status --short` and `git diff --cached --stat`; comm... — **met** — pytest 417 passed (exit 0), ruff check and format exit 0; explicit staging; `git status --short` and `git diff --cached --stat` quoted below; commit cccad44 pushed; remote = HEAD
43. EVAL-02c PRE-FLIGHT (historical; stop at the first failure): on `main`; `git status --short` clean outside the owner-editable areas (listing what i... — **met** — The current state is consistent with the pre-flight: branch main; HEAD a699037 equals the local origin/main (git rev-parse origin/main; `## main...origin/main`); `git log fadb975..HEAD` shows 'a699037 EVAL-02c: planting sheet tool' and '83ae954 EVAL-02b: 34...
44. GROUND RULES include handoff.md "Working rules for the agent" (exit codes quoted; [RAN]/[READ]/[INFERRED] tags; pytest as its own step; explicit st... — **met** — exit codes quoted, [RAN]/[READ]/[INFERRED] tags, explicit staging; owner-editable areas untouched (only data/drafts/_readable/, gitignored, written by the stage command); reverted own uncommitted edits listed under Deviations in the report block
45. IN THE REPLY, which under the prompt's corrections rule means the S1 record in OVERNIGHT_REPORT.md: the first 40 lines of the generated template; t... — **met** — the first 40 lines of the template, the --check output, one readable draft in full, `git diff --stat` and the EVAL report block are below

#### Gate commands (final state, after the round-3 fixes) [RAN]

- `uv run pytest -q` — exit 0 — `417 passed` (353 at S0).
- `uv run ruff check .` — exit 0 — `All checks passed!`; `uv run ruff format --check .` — exit 0 — `41 files already formatted`.
- `uv run pathqc-eval readable data/drafts` — exit 0 — 34 files written, byte-identical to what a699037's code wrote (`diff -r`, no difference).
- `uv run pathqc-eval plant --check` — exit 1 (expected) — 9 OK, 25 "no planted errors yet"; output below.
- Mutation check by the lead (scratch copies only): 47 mutants — R2's 20 from round 1, a revert of every S1 fix, and R2's round-3 mutants — run against tests/test_plant.py and tests/test_io.py: 47 killed; the unmutated control passes 113 tests.
- R2's round-3 reproduction scripts re-run against the fixed code: the 5000-digit draft is reported in plain words, the lone-surrogate file gets a FAIL line and the next file is still written, and the existing report beside a lone-surrogate draft stays at 1196 bytes with H-016 listed NOT UPDATED.

#### Review findings, triage and fixes

Every confirmed finding was reproduced by the lead and has a test that failed before its fix; the failing output is kept in the scratchpad (failing_before_fix*.txt).

| round | finding | verdict | test that failed first → fix |
|---|---|---|---|
| 1 | Built report checked with `check_report(..., drafts=True)`, which skips check_clean_control (orchestrator's point; lead, R3) | CONFIRMED | test_built_report_is_checked_with_the_full_rule_set (`[True] == [False]`) → plant.py calls `check_report(model, taxonomy)` |
| 1 | `readable` names its output from the JSON id: `../escaped` wrote outside `_readable/` (R3 overwrote the planting sheet in a temp tree); `sub/dir/deep` crashed (lead, R3) | CONFIRMED | test_readable_refuses_an_id_that_is_not_a_report_id (4 cases) → ids must be `[HC]-[0-9]{3}` |
| 1 | Sheet that is not UTF-8 (cp1252, UTF-16) gives a traceback (R2 A2/A3) | CONFIRMED | test_a_sheet_that_is_not_utf8_is_refused_in_plain_words (4) → plain-words FAIL |
| 1 | Whole-line removal beside a blank line leaves an empty line or a leading/trailing line break (R2 D1–D3) | CONFIRMED | test_whole_line_removal_next_to_a_blank_line_leaves_no_empty_line (3), test_omission_of_a_paragraph_leaves_one_blank_line → remove_span rewritten |
| 1 | Five-word minimum counted lone punctuation as words (R2 B5) | CONFIRMED | test_five_word_minimum_counts_words_not_punctuation → `word_count` (tokens with a letter or digit) |
| 1 | Bad type id (`h1`, `X1`) gave a raw pydantic message (R2 H1) | CONFIRMED | test_a_type_that_is_not_a_taxonomy_id_is_reported_in_plain_words (4) → entry-labelled check against the taxonomy ids |
| 1 | Draft holding `null` reported as "not found" (R2 I1) | CONFIRMED | test_a_draft_that_is_not_a_report_object_is_reported_as_unparseable[null] → see round 2 |
| 1 | `readable` crashed on a section that is not text (R2 K1) | CONFIRMED | test_readable_reports_a_section_that_is_not_text_and_goes_on → FAIL line |
| 1 | `readable` crashed on a folder named `*.json` (R2 K2) | CONFIRMED | test_readable_ignores_a_folder_whose_name_ends_in_json → files only |
| 1 | `render` advice in a validation message points at an unbuilt report for a hand-edited draft (R2 I3) | REJECTED: only reachable by editing a draft by hand, which decision 37 forbids; the spec only asks that failures be reported under the block. Listed in Part 8 | — |
| 1 | Template blocks follow spec row order, not sorted ids (R2 J1; again R2 T1 in round 3) | REJECTED: reading recorded (Part 5 item 2); committed template must not be regenerated; owner to confirm (Part 4) | a pinning test added |
| 1 | 12 weak tests (R2) and checklist omissions (R1, R3) | addressed: 16 pinning tests (all 20 R2 mutants killed); checklist items 43–45 added | — |
| 2 | plant.py still held `readable`'s writer, so "no code path in plant.py may write under data/drafts/" held only under a reading (R1 item 4, R3) | CONFIRMED | test_plant_module_writes_only_through_write_outputs → `readable` moved to readable.py (output byte-identical) |
| 2 | Removal beside two or more blank lines still left an empty line (R2 RS-1/2/3/8) | CONFIRMED | test_whole_line_removal_beside_several_blank_lines (3), test_omission_of_a_first_paragraph_before_two_blank_lines → blank runs taken with the line |
| 2 | UTF-16-LE sheet without BOM decoded as UTF-8 and rebuilt a verified report as unverified (R2 SE-1) | CONFIRMED | test_a_utf16_sheet_without_a_bom_is_refused_and_reports_stay_as_they_are → NUL check |
| 2 | `readable` crashed when its output could not be written (R2 RD-1/RD-2) | CONFIRMED | test_readable_reports_a_file_it_cannot_write → FAIL line |
| 2 | Deeply nested JSON crashed `readable` (R2 RD-3) | CONFIRMED | test_readable_reports_json_nested_too_deeply_and_goes_on → FAIL line |
| 2 | Deeply nested draft aborted `plant --check` and `plant` (R2 DJ-1, CLI-1) | CONFIRMED | test_plant_check_reports_every_report_when_one_draft_is_nested_too_deeply → load_draft |
| 2 | Draft problems shown as a meaningless "(8 problem(s))" (R2 DJ-2/DJ-3) | CONFIRMED | parametrized draft test (6 cases, exact messages) → real causes |
| 2 | Dangling CR after removing a CRLF line (R2 RS-7) | REJECTED: decision 21 and the draft writer make all text LF; R2 marked it theoretical | — |
| 3 | Round-2 load_draft narrowed `except ValueError`: a 5000-digit integer gave a traceback (R1 items 32/33, R2 A1, R3 F1) — a regression made in round 2 | CONFIRMED | test_a_draft_with_an_integer_too_long_to_read_is_reported_in_plain_words → `except ValueError` restored after the specific clauses |
| 3 | Draft with an unpaired surrogate passed `--check`, then `plant` emptied the existing report and crashed (R2 A7) | CONFIRMED | test_a_draft_with_a_lone_surrogate_is_reported_in_plain_words, test_plant_never_empties_a_report_whose_draft_holds_a_lone_surrogate, test_write_report_json_never_empties_a_file_it_cannot_encode → load_draft check; write_report_json encodes before opening |
| 3 | Same surrogate crashed `readable` and left a 0-byte file (R2 B1) | CONFIRMED | test_readable_reports_a_lone_surrogate_and_goes_on → encoded before any file is opened |
| 3 | `readable` dropped the last section's trailing line breaks (R2 B7) | CONFIRMED | test_readable_keeps_the_last_sections_trailing_line_breaks → no rstrip |
| 3 | A read-only existing report stops `plant` with a traceback (R2 P1) | REJECTED: pre-existing; unwritable output files are outside the specification; nothing is damaged (the open fails before any truncation). Listed in Part 8 | — |
| 3 | 4 weak tests (R2) | addressed: non-UTF-8 draft, "goes on" after a write failure, exact recursion message, and a snapshot that draft problems write nothing under data/drafts/ (the AST test also forbids os/shutil imports) | — |
| 3 | readable.py must be staged with the commit (R3 F2) | done (staged by explicit path) | — |

Totals: 20 findings confirmed and fixed, 5 rejected with reasons; R3 found no breach of section A in any round, no path to an API, no weakened test and no contradicted decision [RAN by R3].

#### Files changed (cccad44)

```
 src/pathqc_eval/cli.py      |  17 +-
 src/pathqc_eval/io.py       |   7 +-
 src/pathqc_eval/plant.py    | 137 ++++++----
 src/pathqc_eval/readable.py |  77 ++++++
 tests/test_io.py            |  12 +
 tests/test_plant.py         | 630 +++++++++++++++++++++++++++++++++++++++++++-
 6 files changed, 823 insertions(+), 57 deletions(-)
```
(`git diff --stat a699037 cccad44`, the previous EVAL commit to this one; identical to `git diff --cached --stat` before the commit) [RAN]. `git status --short` before the commit [RAN]:
```
M  src/pathqc_eval/cli.py
M  src/pathqc_eval/io.py
M  src/pathqc_eval/plant.py
A  src/pathqc_eval/readable.py
M  tests/test_io.py
M  tests/test_plant.py
?? OVERNIGHT_REPORT.md
```

#### What was not tested

- A sheet saved by the owner's own editor: encodings were simulated with Python's codecs [INFERRED].
- File-permission failures were simulated (monkeypatched PermissionError, a folder where a file belongs); no real ACLs were changed [RAN].
- `plant` in its building form was never run on the repository (A3); it ran only in temporary trees [RAN].

#### Deviations (handoff working rule: own uncommitted edits reverted)

- Round-1 remove_span logic was replaced in rounds 2 and 3; the round-1 placement of `readable` in plant.py was moved out in round 2; round 2's narrowed `except` in load_draft was widened again in round 3 [RAN].

#### In the reply (EVAL-02c "IN THE REPLY", read as this record under the corrections rule)

First 40 lines of data/specs/planting.md (the committed template, unchanged since a699037) [RAN `head -40`, exit 0]:

```text
# Planting sheet (decision 37). Written by the owner only; no model writes planting content.
# `uv run pathqc-eval plant --check` checks it; `uv run pathqc-eval plant` applies it to the
# drafts in data/drafts/ (never modified) and writes data/reports/ (never edited by hand).
#
# Format
# - Lines starting with '#' are comments; blank lines are ignored.
# - '== H-001 ==' starts a report block: report-level lines, then [fix] and [error] entries.
# - Every other line is 'key: value', split at the first colon (values may contain colons).
# - Report level: verified: yes|no (required); verified_on: YYYY-MM-DD (required when yes).
# - [fix] corrects the draft without planting an error (text sections only, never Values):
#     section, find, replace, note
# - [error] needs type, severity, description, rationale; optional severity_reason and
#   kind (statement, the default, or omission). Then one of:
#     text change:        section, find, replace; optional quote
#     CBC number change:  set: <analyte> = <number> (one line per analyte, names as in
#                         cbc_values, e.g. MCHC, Neutrophils_pct); optional quote_analyte
#     omission:           remove_from + remove, or remove_section (an optional section);
#                         then anchor (text) or, for CBC, anchor_analyte; optional
#                         anchor_section (default Values for CBC, Synoptic summary otherwise)
# - find and remove must occur exactly once in the section; copy them from
#   data/drafts/_readable/<id>.md (made by `uv run pathqc-eval readable data/drafts`).
# - Quoted sentence: quote if given; in Synoptic summary the whole changed line; otherwise
#   the replace text, which then needs at least five words. Number change: the rendered
#   Values line. Omission: the anchor.
# - Entries apply in sheet order, fixes first, then errors (error ids E1, E2, ... in order).

== H-001 ==
# scored | planted | planned types: H3, H4
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H3
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-001.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-002 ==
```

`uv run pathqc-eval plant --check` on the repository (exit 1, expected) [RAN]:

```text
H-001 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-002 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-003 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-004 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-005 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-006 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-007 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-008 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-009 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-010 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-011 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-012 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-013 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-014 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-015 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-016 OK
H-017 OK
H-018 OK
H-019 OK
H-020 OK
H-021 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-022 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
H-023 OK
C-001 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-002 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-003 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-004 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-005 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-006 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-007 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
C-008 OK
C-009 OK
C-010 OK
C-011 no planted errors yet (the spec marks this report as planted; add at least one [error] entry)
notices: none
plant --check: 9 OK, 25 with problems, 0 sheet problem(s); nothing written
```

One readable draft in full, data/drafts/_readable/H-023.md (generated, gitignored) [RAN]:

```text
# H-023

## Clinical details
69-year-old woman with a sigmoid adenocarcinoma diagnosed on colonoscopic biopsy. Laparoscopic sigmoid colectomy performed.

## Specimen
Laparoscopic sigmoid colectomy specimen with attached mesentery and mesenteric lymph nodes. Received fresh, then fixed in 10% neutral buffered formalin.

## Gross description
Segment of sigmoid colon measuring 22 cm in length, with proximal and distal resection margins and attached mesentery. Centrally sited, ulcerated, firm tumour in the bowel wall measuring 25 mm in greatest dimension. The serosal surface is intact and no tumour nodules are seen in the mesentery. Fourteen lymph nodes are identified, the largest measuring 9 mm; none appears grossly suspicious. Proximal, distal and mesenteric margins are inked and sampled. Representative sections taken from the tumour, all three margins and all lymph nodes.

## Microscopic description
Sections show a well to moderately differentiated adenocarcinoma composed of irregular glands with focal solid areas. The tumour invades through the mucosa and submucosa into the muscularis propria but does not penetrate beyond it into the subserosa or through the serosa. No lymphovascular or perineural invasion is identified. The peritumoural lymphoid response is mild. The proximal, distal and mesenteric margins are free of tumour. None of the 14 lymph nodes contains metastatic carcinoma.

## Diagnosis
Sigmoid colon, laparoscopic sigmoid colectomy:
- Adenocarcinoma, well to moderately differentiated, 25 mm, invading the muscularis propria (pT2).
- Lymph nodes: 0 of 14 involved (pN0).
- Proximal, distal and mesenteric margins clear.
- No lymphovascular or perineural invasion.

## Synoptic summary
Tumour size: 25 mm
Histologic grade: Low grade (well to moderately differentiated)
Margins: Proximal, distal and mesenteric margins clear
Lymphovascular invasion: Not identified
Perineural invasion: Not identified
Lymph nodes (positive/total): 0/14
pT: pT2
pN: pN0
Staging edition: AJCC 8th edition

## Comment
Mismatch repair status is recommended on this resection specimen if it has not already been determined on the biopsy. Adjuvant treatment decisions should be made with reference to the full clinical picture.
```

```text
=== EVAL REPORT: EVAL-02c-fix Planting sheet tool audit (EVAL-N1 S1) ===
Status: DONE
What was asked: audit a699037 (EVAL-02c) against its specification with three independent reviews; commit confirmed fixes as EVAL-02c-fix.
What was done: built reports now pass every validator rule [RAN]; readable moved to its own module and confined to _readable/ [RAN]; 18 further defects found by the reviews fixed test-first [RAN]; 5 findings rejected with reasons [READ]; 47 mutants killed [RAN].
Files changed: src/pathqc_eval/{cli,io,plant}.py — fixes; src/pathqc_eval/readable.py — readable command, moved from plant.py; tests/test_plant.py, tests/test_io.py — 46 new tests.
Commands run: uv run pytest — 0 — 18 s — 417 passed; ruff check — 0; ruff format --check — 0; pathqc-eval readable data/drafts — 0 — 34 files, byte-identical; pathqc-eval plant --check — 1 (expected) — 9 OK, 25 no planted errors yet.
Checks: pytest 417 passed, 0 failed | ruff check and format clean
Git: branch main; commit cccad44 "EVAL-02c-fix: full rule set for built reports, readable in its own module, robustness"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: own uncommitted edits replaced between review rounds (listed above); readable.py is a new module the specification does not name (it satisfies S1's "no code path in plant.py may write under data/drafts/").
Claims I could not verify: behaviour with the owner's own editor's encodings (simulated only).
Questions for the owner: confirm that "id order" for the template means the spec's row order (Part 4).
handoff.md updated: yes (record commit)
=== END ===
```

### S2 — EVAL-H1: CLAUDE.md and harness decision — PASS

Stage commit `e85eeb3` "EVAL-H1: CLAUDE.md and harness decision", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = e85eeb36a46f11c829f2d287426b06cb9280ebd4 [RAN]. Two review rounds (R1, R2, R3 each) [RAN]. From this stage on, CLAUDE.md binds the run as well as the prompt.

#### Checklist (9 items, all met)

1. Every line of CLAUDE.md checked against the code; commands a later stage adds listed as "not yet present" and kept in the text — **met**:
   - Title and "what this repo is": repository name and purpose match pyproject.toml and README.md [READ]; branch `main` is the source of truth, and origin/main = HEAD [RAN]; the Operating Charter is kept outside the repository and cannot be checked here [READ]; decisions, open items and the task log are sections of handoff.md [READ].
   - The gate: `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` are configured (pyproject.toml dev group, [tool.pytest.ini_options], [tool.ruff]) and run in every stage [RAN]; `validate`, `spec-check`, `plant --check` and `freeze --check` exist (`pathqc-eval <command> --help`, exit 0 each) [RAN].
   - Typed words: `pathqc-eval freeze` writes the lock and `freeze --replace` replaces it [RAN `freeze --help`]; **`pathqc-eval run --dataset scored …`: not yet present** (`pathqc-eval run --help` exit 2; added in S5) [RAN]; "release preparation" names no command [READ].
   - Never: `.env` is gitignored and untracked [RAN]; data/ and runs/ exist [RAN]; the owner-file list equals handoff.md's owner-editable areas [READ].
   - Environment: Windows [RAN]; `uv run` everywhere [RAN]; bare `python` is only the Store alias (Part 5 item 4) [RAN]; LF line endings (.gitattributes `* text=auto eol=lf`) [RAN].
   - Committing and Reporting: consistent with handoff.md's working rules and report block [READ].
   - Facts that change: handoff.md holds no commit heads or test counts (Part 5 item 3, Part 4 item 5) [READ].
   - Other mismatches found by the check and the reviews: Part 4 items 2–5 and Part 5 items 3–5 [READ].
2. CLAUDE.md in the repository root, exactly the text between the markers — **met**: `cmp` against the prompt's lines exit 0; 59 lines, LF only, no BOM, one final line break; sha256 ad13996e…94cc [RAN].
3. Labels line — **met** (handoff.md line 3: the stage's text without its closing full stop, like the old line) [RAN by R1].
4. Owner decisions 1 and 2 as decisions 38 and 39 (OWNER VERIFIED, 2026-11-10, the next free numbers) — **met**: the owner's words exactly, with the agent's clarifications in square brackets (Part 3 item 4); the header now reads "29–39 on 2026-11-10" [RAN].
5. "Read CLAUDE.md first; it holds the rules that bind this session." added as the first working rule; the other rules kept — **met** [RAN].
6. CLAUDE.md binds the run from this stage on — **met**: its "Before acting" and "Do only what the prompt asks" rules decided how the round-2 findings were settled (reported, not changed) [READ].
7. Commit `EVAL-H1: CLAUDE.md and harness decision` — **met** (e85eeb3) [RAN].
8. Gate: `uv run pytest -q` exit 0, 417 passed; `uv run ruff check .` exit 0; `uv run ruff format --check .` exit 0 (42 files: ruff 0.17.3 counts Markdown files, so CLAUDE.md is the 42nd); explicit staging; status and cached stat quoted below; push; remote = HEAD — **met** [RAN].
9. No API call; nothing outside the stage's scope — **met** (R3, both rounds) [RAN].

#### Review findings, triage and fixes

| round | finding | verdict | action |
|---|---|---|---|
| 1 | CLAUDE.md "Facts that change" points to heads and test counts that handoff.md does not hold (R1, R2 C13a, R3-1) | CONFIRMED (a mismatch in the documents) | CLAUDE.md stays verbatim; Part 5 item 3, Part 4 item 5 |
| 1 | handoff.md's API rule lacks "hard stop" (R1, R2 C13b, R3-3) | CONFIRMED (a mismatch) | not edited (S2 does not authorise it); Part 4 item 2 |
| 1 | `python` is on PATH as the Store alias (R1) | CONFIRMED (a nuance) | Part 5 item 4 |
| 1 | CLAUDE.md's Never list is narrower than section A (R3-2) | CONFIRMED (for the owner) | Part 4 item 3 |
| 1 | "Evaluation prompts … are the owner's words" against agent-written prompts (R3-6) | CONFIRMED (for the owner) | Part 4 item 4 |
| 1 | Decisions 38 and 39 reworded the owner's text (R1, R3-4) | CONFIRMED | the owner's words restored, clarifications in brackets (round-2 diff) |
| 1 | Checklist item 5 said "becomes" where the stage says "add" (R1, R2 C14, R3-5) | CONFIRMED (checklist only; the work was right) | checklist corrected |
| 1 | No test reads CLAUDE.md, and `ruff format --check` does not check its content (R2) | REJECTED as a defect | S2 asks for no test; exactness was checked by `cmp` and by R1 and R2; a test pinning the owner's rules file would block the owner's own edits |
| 1 | `cli.main` loads `.env` for every command, so tests that call it load the key unless it is blanked (R3-7) | pre-existing | carried to S5, where the harness tests add a guard |
| 2 | The record claimed the S1 task-log row "was completed" with commit and test count [RAN], which was false and beyond the stage (R1, R2 C16, R3 OF-1) | CONFIRMED | claim removed; no format change; Part 4 item 5 |
| 2 | The bracketed words were not explained (R1, R3 OF-2) | CONFIRMED | Part 3 item 4 |
| 2 | Part 4 item 3's list of section A gaps was incomplete (R1, R3 OF-3) | CONFIRMED | completed |
| 2 | D9's "open items" were not updated for the new owner questions (R1, R3 OF-4) | CONFIRMED | handoff.md Open items updated in this record commit |
| 2 | S9 would record owner decision 1 again (R3 OF-5) | CONFIRMED | Part 5 item 5 |
| 2 | The S0 record overstated the empty-key safeguard (R3 OF-6) | CONFIRMED | S0 record corrected; variable names checked by name only |

#### Files changed (e85eeb3)

`git status --short` and `git diff --cached --stat` before the commit [RAN]:
```
A  CLAUDE.md
 M OVERNIGHT_REPORT.md
M  handoff.md
 CLAUDE.md  | 59 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 handoff.md |  7 +++++--
 2 files changed, 64 insertions(+), 2 deletions(-)
```
OVERNIGHT_REPORT.md was left unstaged; it goes in the record commit.

#### What was not tested

- Whether a new Claude Code session in this folder loads CLAUDE.md automatically [INFERRED from Claude Code's design; not tested].

#### Deviations

- Own uncommitted edit replaced between rounds: decisions 38 and 39 first reworded the owner's text, then restored it with bracketed clarifications [RAN].

```text
=== EVAL REPORT: EVAL-H1 CLAUDE.md and harness decision (EVAL-N1 S2) ===
Status: DONE
What was asked: create CLAUDE.md verbatim after checking it against the code; record owner decisions 1 and 2, the new labels and the first working rule in handoff.md.
What was done: CLAUDE.md created, byte-identical to the prompt's text [RAN]; every command it names exists except `run`, which S5 adds [RAN]; decisions 38 and 39, Labels and the working rule added [RAN]; four mismatches between the documents recorded for the owner [READ].
Files changed: CLAUDE.md — new, the harness rules for the session; handoff.md — Labels, decisions 38–39, first working rule.
Commands run: uv run pytest — 0 — 20 s — 417 passed; ruff check — 0; ruff format --check — 0; pathqc-eval <command> --help — 0 (run: 2, not yet present).
Checks: pytest 417 passed, 0 failed | ruff check and format clean
Git: branch main; commit e85eeb3 "EVAL-H1: CLAUDE.md and harness decision"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: bracketed clarifications inside the owner's decisions (Part 3 item 4).
Claims I could not verify: the Operating Charter, kept outside the repository.
Questions for the owner: Part 4 items 2–5.
handoff.md updated: yes
=== END ===
```

### S3 — EVAL-02d: drafting instructions corrected; four reports drafted again — PASS

Stage commit `2269b0d` "EVAL-02d: drafting instructions corrected; four reports drafted again", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = 2269b0d808b1dffe60722695ec8d7a1370d41775 [RAN]. Three review rounds (R1, R2, R3 each) [RAN]. API: 4 calls to claude-haiku-5-5, $0.004447 by the call log (section B: at most 8 calls, estimate $0.01, hard stop $0.10) [RAN].

#### Checklist (14 items, all met)

1. prompts/drafting/histopathology.md gains the two Rules lines word for word, at the end of the Rules list — **met** [RAN; checked byte for byte by R1].
2. prompts/drafting/cbc.md gains the Rules line word for word — **met** [RAN; R1].
3. The CBC user message ends, after the brief and a blank line, with `Reference ranges (adult <sex>):` and one `<label>: <low>–<high> <unit>` line per analyte in CBCValues order, read from data/specs/cbc_reference_ranges.json for the row's sex (src/pathqc_eval/draft.py `reference_ranges_block`, `user_message`); labels, decimals and units are those of the Values text, and a bound those decimals would round is printed in full. The 23 histopathology user messages are byte-identical to before; each of the 11 CBC messages is the old message plus the block for its own sex — **met** [RAN; R1, R3].
4. Tests: exact-text tests for a female and a male CBC message, a test that each row carries its own sex's ranges and not the other's, the dry-run test now asserts the ranges block, and tests/test_isolation.py is unchanged and passes for all 34 rows (68 cases) — **met** [RAN].
5. `uv run pathqc-eval draft --dry-run` — exit 0 — both prompts are below [RAN].
6. `uv run pathqc-eval draft --ids H-009,H-021,C-008,C-009 --force --cost-gate 0.10` — exit 0 — the four drafts overwritten; the earlier versions stay in git history (83ae954) [RAN].
7. Checks by script, no draft edited — all pass; `uv run pathqc-eval validate --drafts data/drafts` — exit 0 — 34 reports OK. No redraft was needed [RAN].
8. Report-only tables below (Table B also lists sentences with "staging"; Part 5 item 6) — **met** [RAN].
9. S1 passed, so `uv run pathqc-eval readable data/drafts` was run again — exit 0 — 34 files written [RAN].
10. handoff.md decision 40, the stage's text word for word, under the next free number (header now "29–40 on 2026-11-10") — **met** [RAN; R1].
11. Commit `EVAL-02d: drafting instructions corrected; four reports drafted again` with the code, the tests, the two drafting prompts, the four drafts, data/drafts/_calls.jsonl and handoff.md — **met** (2269b0d) [RAN].
12. Section B: claude-haiku-5-5 only, drafting calls only, exactly H-009, H-021, C-008 and C-009, 4 calls (limit 8), $0.004447 (hard stop $0.10; the prompt's estimate $0.01; the tool's own estimate for the four rows $0.0165), ANTHROPIC_INFERENCE_GEO not set in the environment and not in `.env` (checked by name) — **met** [RAN].
13. Owner-editable areas: only the two drafting prompts, the four named drafts, data/drafts/_calls.jsonl (4 lines appended) and the gitignored data/drafts/_readable/ changed; data/specs/cbc_reference_ranges.json and the other 30 drafts are unchanged — **met** [RAN; R1, R3].
14. Run gate: tests that failed on the old code are kept (below); pytest 440 passed, exit 0; ruff check and format exit 0; explicit staging; status and cached stat quoted; push; remote = HEAD — **met** [RAN].

#### Step 5: `uv run pathqc-eval draft --dry-run` (exit 0) — both drafting prompts [RAN]

```text
DRY RUN: no client is constructed and no API call is made.
===== H-001 system prompt (prompts/drafting/histopathology.md) =====
You write synthetic histopathology reports for an evaluation dataset. Each report is fictional and describes no real patient.

Rules
- Do not include any patient name, date, hospital number, laboratory number or other identifier, and do not name any hospital, laboratory or doctor.
- The report must be complete, internally consistent and error-free. Every figure (tumour size, grade, lymph node counts, margin distances, depth of invasion, pT and pN) must be identical wherever it appears.
- Write in the house style of a tertiary-care cancer centre in India, using British spelling.
- Stage according to the AJCC Cancer Staging Manual, 8th edition, for the site.
- Length: 250 to 450 words in total.
- Use the pT and pN categories exactly as the brief states them. Do not change them and do not discuss how they were chosen.
- Do not state a stage group, a FIGO stage, a risk category or a prognostic group unless the brief gives one.

Sections, in this order and with exactly these names:
1. Clinical details
2. Specimen
3. Gross description
4. Microscopic description
5. Immunohistochemistry (include this section only when the brief calls for immunohistochemistry)
6. Diagnosis
7. Synoptic summary
8. Comment (optional)

The Synoptic summary has one element per line, in this order, each written as "Element: value":
Tumour size: ...
Histologic grade: ...
Margins: ...
Lymphovascular invasion: ...
Perineural invasion: ...
Lymph nodes (positive/total): ...
pT: ...
pN: ...
Staging edition: AJCC 8th edition

The last line of the Synoptic summary is always exactly "Staging edition: AJCC 8th edition", even when pT and pN read "Not applicable". Write "Not applicable" for any element that does not apply to the specimen.

Output: return only a JSON object, with no text before or after it. Its keys are the section names above and its values are the section text as plain text (no Markdown). Use \n for line breaks inside a value.
===== H-001 user message =====
Specimen type: Breast, left modified radical mastectomy with axillary dissection
Patient: female, 52 years
Brief: A 52-year-old woman with a palpable left breast lump underwent modified radical mastectomy with level I-II axillary dissection after a core biopsy showed carcinoma. The report describes invasive breast carcinoma of no special type, Nottingham grade 2, 32 mm in greatest dimension, with metastatic carcinoma in 3 of 14 axillary lymph nodes and no extranodal extension. All margins are free, the closest being the deep margin at 6 mm; lymphovascular invasion is present and perineural invasion absent; pT2 pN1a.
===== C-001 system prompt (prompts/drafting/cbc.md) =====
You write synthetic complete blood count (CBC) reports for an evaluation dataset. Each report is fictional and describes no real patient.

Rules
- Do not include any patient name, date, identifier, hospital, laboratory or doctor.
- The values and the text must be complete, internally consistent and error-free, and must match the brief.
- The patient is an adult. Write in the house style of a tertiary-care hospital laboratory in India, using British spelling.
- The user message lists the reference range of every value. Unless the brief says otherwise, choose values so that each one, including every absolute count the tool will derive (WBC x percentage / 100), lies inside its range.

Output: return only a JSON object, with no text before or after it, with these keys:

"primary": an object with exactly these numeric fields, in these units:
- Hb (g/dL), RBC (x10^12/L), Hct (%), RDW (%), WBC (x10^9/L)
- Neutrophils_pct, Lymphocytes_pct, Monocytes_pct, Eosinophils_pct, Basophils_pct (percent of white cells; the five must sum to 100)
- Platelets (x10^9/L), MPV (fL)

Do not include MCV, MCH, MCHC or absolute counts. The tool computes them from your values:
- MCV (fL) = Hct / RBC x 10
- MCH (pg) = Hb / RBC x 10
- MCHC (g/dL) = Hb / Hct x 100
- absolute count (x10^9/L) = WBC x percentage / 100

Choose Hb, RBC and Hct together so that these formulas give the red-cell indices the brief intends.

"interpretation": 3 to 6 sentences of plain text, consistent with the numbers and the brief.

"comment": optional plain text. It is required when the brief says a critical value is present: it must then name the critical value, flag it as critical and give a recommendation.
===== C-001 user message =====
Scenario: Severe iron deficiency anaemia
Patient: female, 34 years
Brief: A 34-year-old woman with menorrhagia, fatigue and breathlessness on exertion. Severe microcytic hypochromic anaemia with haemoglobin about 6.2 g/dL, MCV in the low 60s fL, a raised RDW and a reactive platelet count near 480 x10^9/L; white cells normal. Haemoglobin is at a critical level, so the comment must flag it and recommend urgent clinical review and iron studies.

Reference ranges (adult female):
Hb: 12.0–15.0 g/dL
RBC: 3.80–4.80 x10^12/L
Hct: 36.0–46.0 %
MCV: 83.0–101.0 fL
MCH: 27.0–32.0 pg
MCHC: 31.5–34.5 g/dL
RDW: 11.6–14.0 %
WBC: 4.00–10.00 x10^9/L
Neutrophils %: 40.0–80.0 %
Neutrophils absolute: 2.00–7.00 x10^9/L
Lymphocytes %: 20.0–40.0 %
Lymphocytes absolute: 1.00–3.00 x10^9/L
Monocytes %: 2.0–10.0 %
Monocytes absolute: 0.20–1.00 x10^9/L
Eosinophils %: 1.0–6.0 %
Eosinophils absolute: 0.02–0.50 x10^9/L
Basophils %: 0.0–2.0 %
Basophils absolute: 0.02–0.10 x10^9/L
Platelets: 150–410 x10^9/L
MPV: 7.5–11.5 fL
Estimate: 34 rows × ~1,200 input + ~8,000 output tokens at Haiku prices = $0.1401
```

#### Step 6: `uv run pathqc-eval draft --ids H-009,H-021,C-008,C-009 --force --cost-gate 0.10` (exit 0) [RAN]

```text
  H-009 attempt 1: $0.0014; running $0.0014
H-009 | Cervix, radical hysterectomy with pelvic lymphadenectomy | 264 words
  H-021 attempt 1: $0.0018; running $0.0031
H-021 | Testis, right radical inguinal orchidectomy | 261 words
  C-008 attempt 1: $0.0006; running $0.0037
C-008 | Normal blood count at a pre-employment check | 193 words | MCV 89 MCH 29.7 MCHC 33.3 | notes: none
  C-009 attempt 1: $0.0008; running $0.0044
C-009 | Near-normal count with mild eosinophilia | 216 words | MCV 88.9 MCH 29.9 MCHC 33.6 | notes: none
total cost $0.0044
```

The four lines appended to data/drafts/_calls.jsonl (the spend source) [RAN]:

```text
{"timestamp":"2026-11-10T21:28:40+00:00","id":"H-009","model":"claude-haiku-5-5","input_tokens":914,"output_tokens":2525,"cost_usd":0.001354,"stop_reason":"end_turn","duration_s":11.26,"attempt":1}
{"timestamp":"2026-11-10T21:28:55+00:00","id":"H-021","model":"claude-haiku-5-5","input_tokens":889,"output_tokens":3339,"cost_usd":0.001758,"stop_reason":"end_turn","duration_s":14.37,"attempt":1}
{"timestamp":"2026-11-10T21:28:59+00:00","id":"C-008","model":"claude-haiku-5-5","input_tokens":1205,"output_tokens":911,"cost_usd":0.000576,"stop_reason":"end_turn","duration_s":4.19,"attempt":1}
{"timestamp":"2026-11-10T21:29:05+00:00","id":"C-009","model":"claude-haiku-5-5","input_tokens":1228,"output_tokens":1272,"cost_usd":0.000759,"stop_reason":"end_turn","duration_s":5.75,"attempt":1}
```

#### Step 7: checks by script, and the validator [RAN]

```text
PASS H-009 Synoptic has the line 'pT: pT1b1'
PASS H-009 'pT1b2' in no section
PASS H-009 'IIIC' in no section
PASS H-009 'FIGO' in no section
PASS H-021 Synoptic has the line 'pT: pT1b'
PASS H-021 no sentence says pT1 is not subdivided
PASS C-008 every analyte inside its range
PASS C-009 inside its range except Eosinophils_pct and Eosinophils_abs -- Eosinophils_pct 9 % (ref 1-6); Eosinophils_abs 0.65 x10^9/L (ref 0.02-0.5)
PASS C-009 Eosinophils_pct and Eosinophils_abs are the analytes outside (brief: eosinophilia) -- Eosinophils_pct 9 % (ref 1-6); Eosinophils_abs 0.65 x10^9/L (ref 0.02-0.5)
```

`uv run pathqc-eval validate --drafts data/drafts` — exit 0:

```text
validate (drafts): 34 reports | histopathology 23, cbc 11 | dev 4, scored 30 | clean 9, planted 25 | errors by type: H1 0, H2 0, H3 0, H4 0, H5 0, H6 0, C1 0, C2 0, C3 0 | overrides 0 | omissions 0 | OK
```

The redrafted H-009 says `pT: pT1b1` and states no stage group; its Comment reads "Correlation with the clinical staging and multidisciplinary review is recommended." The redrafted H-021 says `pT: pT1b` and has no Comment section [READ].

#### Step 8: report-only tables (nothing changed) [RAN]

Table A: the 11 CBC drafts, every analyte outside its reference range (value, unit, range).

| report | analytes outside their range |
|---|---|
| C-001 | Hb 6.2 g/dL (ref 12-15); RBC 3.56 x10^12/L (ref 3.8-4.8); Hct 22.1 % (ref 36-46); MCV 62.1 fL (ref 83-101); MCH 17.4 pg (ref 27-32); MCHC 28.1 g/dL (ref 31.5-34.5); RDW 21.4 % (ref 11.6-14); Platelets 480 x10^9/L (ref 150-410) |
| C-002 | Hb 12.8 g/dL (ref 13-17); Hct 38.4 % (ref 40-50); WBC 48 x10^9/L (ref 4-10); Neutrophils_pct 12 % (ref 40-80); Lymphocytes_pct 82 % (ref 20-40); Lymphocytes_abs 39.36 x10^9/L (ref 1-3); Monocytes_abs 1.92 x10^9/L (ref 0.2-1); Basophils_abs 0.48 x10^9/L (ref 0.02-0.1) |
| C-003 | Platelets 12 x10^9/L (ref 150-410); MPV 11.8 fL (ref 7.5-11.5) |
| C-004 | Hb 7.8 g/dL (ref 13-17); RBC 2 x10^12/L (ref 4.5-5.5); Hct 23.6 % (ref 40-50); MCV 118 fL (ref 83-101); MCH 39 pg (ref 27-32); RDW 18.5 % (ref 11.6-14); WBC 3.2 x10^9/L (ref 4-10); Neutrophils_abs 1.76 x10^9/L (ref 2-7); Monocytes_abs 0.19 x10^9/L (ref 0.2-1); Platelets 110 x10^9/L (ref 150-410) |
| C-005 | Hb 11.4 g/dL (ref 12-15); Hct 34 % (ref 36-46); WBC 0.9 x10^9/L (ref 4-10); Neutrophils_pct 22 % (ref 40-80); Neutrophils_abs 0.2 x10^9/L (ref 2-7); Lymphocytes_pct 64 % (ref 20-40); Lymphocytes_abs 0.58 x10^9/L (ref 1-3); Monocytes_abs 0.09 x10^9/L (ref 0.2-1); Basophils_abs 0.01 x10^9/L (ref 0.02-0.1); Platelets 95 x10^9/L (ref 150-410) |
| C-006 | WBC 18.6 x10^9/L (ref 4-10); Neutrophils_pct 86 % (ref 40-80); Neutrophils_abs 16 x10^9/L (ref 2-7); Lymphocytes_pct 7 % (ref 20-40); Basophils_abs 0.19 x10^9/L (ref 0.02-0.1) |
| C-007 | Hb 20.4 g/dL (ref 13-17); RBC 6.8 x10^12/L (ref 4.5-5.5); Hct 61 % (ref 40-50); WBC 11.8 x10^9/L (ref 4-10); Neutrophils_abs 8.73 x10^9/L (ref 2-7); Lymphocytes_pct 16 % (ref 20-40); Basophils_abs 0.12 x10^9/L (ref 0.02-0.1); Platelets 520 x10^9/L (ref 150-410) |
| C-008 | none |
| C-009 | Eosinophils_pct 9 % (ref 1-6); Eosinophils_abs 0.65 x10^9/L (ref 0.02-0.5) |
| C-010 | Hb 11.2 g/dL (ref 12-15); RBC 5.6 x10^12/L (ref 3.8-4.8); Hct 35.8 % (ref 36-46); MCV 63.9 fL (ref 83-101); MCH 20 pg (ref 27-32); MCHC 31.3 g/dL (ref 31.5-34.5) |
| C-011 | WBC 2.8 x10^9/L (ref 4-10); Neutrophils_abs 1.26 x10^9/L (ref 2-7); Lymphocytes_pct 44 % (ref 20-40); Platelets 38 x10^9/L (ref 150-410) |

Table B: the 23 histopathology drafts, every sentence or line containing "stage" or "staging", except the fixed line "Staging edition: AJCC 8th edition" (case-insensitive). Rows marked with a sentence that has only "staging" are the four added after review (H-001, H-009, H-014 and H-022's second Comment sentence).

| report | section | sentence |
|---|---|---|
| H-001 | Diagnosis | "Pathological prognostic stage cannot be assigned until oestrogen receptor, progesterone receptor and HER2 status are available." |
| H-001 | Comment | "Oestrogen receptor, progesterone receptor and HER2 status should be requested on the invasive component to complete pathological prognostic staging and to guide systemic therapy." |
| H-002 | Comment | "pT3 pN1b corresponds to AJCC 8th edition stage group IIIB for carcinoma of the caecum." |
| H-003 | Comment | "The pathological stage is I (pT2 pN0) according to the AJCC 8th edition." |
| H-004 | Comment | "The pathological stage is pT3 pN2." |
| H-004 | Comment | "Assuming M0 on clinical assessment, this corresponds to pathological prognostic stage IIIA under the AJCC 8th edition staging system for gastric carcinoma." |
| H-005 | Diagnosis | "Pathological stage (AJCC 8th edition): pT2 pN1, stage group III." |
| H-006 | Diagnosis | "Pathological stage (AJCC 8th edition, patient under 55 years): pT2 pN1a, stage I." |
| H-006 | Diagnosis | "The M category is not assessed on this specimen; stage I assumes M0." |
| H-007 | Comment | "Pathological stage group I (pT1b pN0), assuming M0 on clinical assessment." |
| H-008 | Diagnosis | "- Pathological stage IA according to AJCC 8th edition." |
| H-008 | Comment | "Low-grade endometrioid histology with no lymphovascular invasion and negative nodes indicates an early-stage tumour." |
| H-009 | Comment | "Correlation with the clinical staging and multidisciplinary review is recommended." |
| H-010 | Diagnosis | "Pathological stage group IA3 (AJCC 8th edition)." |
| H-011 | Comment | "The AJCC 8th edition does not provide a stage for lymphoma, so pT and pN are recorded as not applicable." |
| H-011 | Comment | "Clinical (Ann Arbor) stage should be assigned by the treating team after imaging and bone marrow assessment, with reference to the Lugano classification." |
| H-012 | Comment | "Regional nodal status was not assessed, so a pathological stage group cannot be assigned." |
| H-013 | Comment | "If a lung primary is confirmed, the multiple hepatic metastases would correspond to M1c and stage IVB under AJCC 8th edition." |
| H-014 | Comment | "In AJCC 8th edition staging of gastric GIST, the T category is assigned by tumour size." |
| H-015 | Diagnosis | "Pathological staging: pT1c pN0(sn), pathological prognostic stage IA." |
| H-016 | (none) | |
| H-017 | (none) | |
| H-018 | Diagnosis | "Pathological stage (AJCC 8th edition): IA (pT1a pN0)." |
| H-018 | Comment | "The tumour is confined to one ovary with an intact capsule, an uninvolved ovarian surface and negative peritoneal washings, which corresponds to stage IA." |
| H-019 | Diagnosis | "AJCC 8th edition stage IIA (pT2a pN0 M not assessed in this specimen)." |
| H-019 | Comment | "Clinical correlation with imaging for metastatic disease is advised, as M stage cannot be assessed from this specimen." |
| H-020 | Comment | "Pathological stage group IIIA (AJCC 8th edition, squamous cell carcinoma, pT3 pN1)." |
| H-021 | (none) | |
| H-022 | Comment | "Pathological stage group IIB (pT2 pN1; M category not assessed in this specimen), AJCC 8th edition." |
| H-022 | Comment | "Clinical correlation is advised for any further staging and for adjuvant treatment planning at the multidisciplinary meeting." |
| H-023 | (none) | |

#### Review findings, triage and fixes

| round | finding | verdict | action |
|---|---|---|---|
| 1 | Range bounds were printed with the Values decimals, so a stored bound such as 0.015 or 150.5 would be rounded into a wider range (R2 M06; latent: all 80 bounds of the current file print exactly) | CONFIRMED | test_reference_ranges_block_prints_each_stored_bound_exactly failed first → `_bound` prints a bound in full when the decimals would round it; the dry-run output stayed byte-identical |
| 1 | The ranges loader accepted NaN, infinities, true/false and text as bounds (R2 M09) | CONFIRMED | test_reference_ranges_refuse_a_bound_that_is_not_a_finite_number and test_reference_ranges_file_with_nan_is_refused failed first → cbc.Range refuses them |
| 1 | Three weak tests (R2): run_drafts tested with the default ranges; the sex test checked only low bounds; the default-path test compared the loader with itself | CONFIRMED | strengthened (invented ranges, a full male block, a direct read of the file); R2's surviving mutants A, B, C and G now killed |
| 1 | Table B left out sentences with "staging" (R3 OF-1) | CONFIRMED | Table B regenerated; Part 5 item 6 |
| 1 | No failing-first output for the drafting-message change (R3 OF-2) | CONFIRMED | kept: on HEAD's code the new tests fail at import (`cannot import name 'reference_ranges_block'`); R3's shim run gave 7 failed |
| 1 | Command lines and exit codes missing from the evidence (R3 OF-3) | CONFIRMED | quoted in this record |
| 1 | The reviewers' PowerShell instruction (`$env:ANTHROPIC_API_KEY=''`) deletes the variable in Windows PowerShell, so `.env` would load (R3 OF-4) | CONFIRMED | reviewer instructions changed: project code only in Git Bash with `ANTHROPIC_API_KEY= PYTHON_DOTENV_DISABLED=1`; checked that no reviewer made a call (data/drafts/_calls.jsonl has exactly 34 + 4 lines) |
| 2 | An integer too large for a float raised OverflowError instead of a validation error (R2 C3; a regression from round 1) | CONFIRMED | the 10**400 cases failed first → the validator converts with float() and refuses on OverflowError |
| 2 | The finite-number test's match also accepted the old ordering error, so 3 cases never exercised the new rule; False untested (R2, R3 F1) | CONFIRMED | match narrowed to the refusal message; every case keeps low <= high; False and an oversized integer added |
| 2 | The exact-bound test covered only low bounds with one extra decimal; the sex test checked only low bounds (R2 M3, M4, M5) | CONFIRMED | high bounds and bounds with several extra decimals added; each sex's exact Hb, RBC and Hct lines pinned; mutants M2–M7 killed |
| 3 | An integer longer than Python will print gave Python's own limit message instead of the refusal (R2 V05) | CONFIRMED | test_reference_ranges_refuse_an_integer_too_long_to_print failed first → the refusal text is built safely |
| 3 | No test pinned that the dry run prints both prompts in full and the row's own block, or that the drafting prompts carry decision 40's rules (R2) | CONFIRMED | two tests added; R2's mutants M30, M31, M32 and M34 now killed |
| 3 | The exact-bound test never checked a bound the Values decimals reformat (R2, M10) | CONFIRMED | `WBC: 4.00–11.00` asserted |
| 3 | A test docstring said every case keeps low <= high, untrue for a 10**400 low (R3 F1) | CONFIRMED | that case now uses -(10**400) |
| 3 | draft.py's module docstring did not mention the ranges block (R3 F2) | CONFIRMED | docstring updated |

Lead's mutation check (scratch copies; tests/test_draft.py and tests/test_cbc.py): 18 mutants (R2's survivors from rounds 1 to 3 and a revert of every fix), all killed; the unmutated control passes 62 tests [RAN].

#### Files changed (2269b0d)

```text
M  data/drafts/C-008.json
M  data/drafts/C-009.json
M  data/drafts/H-009.json
M  data/drafts/H-021.json
M  data/drafts/_calls.jsonl
M  handoff.md
M  prompts/drafting/cbc.md
M  prompts/drafting/histopathology.md
M  src/pathqc_eval/cbc.py
M  src/pathqc_eval/draft.py
M  src/pathqc_eval/render.py
M  tests/test_cbc.py
M  tests/test_draft.py
---
 data/drafts/C-008.json             |  30 ++---
 data/drafts/C-009.json             |  33 +++---
 data/drafts/H-009.json             |  16 +--
 data/drafts/H-021.json             |  17 ++-
 data/drafts/_calls.jsonl           |   4 +
 handoff.md                         |   3 +-
 prompts/drafting/cbc.md            |   1 +
 prompts/drafting/histopathology.md |   2 +
 src/pathqc_eval/cbc.py             |  26 ++++-
 src/pathqc_eval/draft.py           |  60 ++++++++--
 src/pathqc_eval/render.py          |   5 +-
 tests/test_cbc.py                  |  53 ++++++++-
 tests/test_draft.py                | 223 ++++++++++++++++++++++++++++++++++++-
 13 files changed, 406 insertions(+), 67 deletions(-)
```

#### What was not tested

- The Haiku drafting run itself was made once (step 6); the round-1 and round-2 fixes do not change the messages built from the current ranges file (the dry-run output is byte-identical before and after), so no draft was made again [RAN].

```text
=== EVAL REPORT: EVAL-02d Drafting instructions corrected; four reports drafted again (EVAL-N1 S3) ===
Status: DONE
What was asked: add the owner's three drafting rules, show the CBC reference ranges in the drafting message, redraft H-009, H-021, C-008 and C-009 with Haiku, check them by script, and list the out-of-range values and stage sentences for the owner.
What was done: rules and ranges block added [RAN]; four drafts made again in 4 calls, every check passes [RAN]; tables written [RAN]; review findings fixed test-first (exact bounds, a stricter ranges loader, stronger tests) [RAN].
Files changed: src/pathqc_eval/{draft,render,cbc}.py; tests/test_draft.py, tests/test_cbc.py; prompts/drafting/{histopathology,cbc}.md; data/drafts/{H-009,H-021,C-008,C-009}.json; data/drafts/_calls.jsonl; handoff.md.
Commands run: uv run pytest — 0 — 18 s — 440 passed; ruff check — 0; ruff format --check — 0; pathqc-eval draft --dry-run — 0; pathqc-eval draft --ids H-009,H-021,C-008,C-009 --force --cost-gate 0.10 — 0 — 30 s; validate --drafts — 0; readable data/drafts — 0.
Checks: pytest 440 passed, 0 failed | ruff check and format clean
Git: branch main; commit 2269b0d "EVAL-02d: drafting instructions corrected; four reports drafted again"; push ok; remote HEAD matches local HEAD: yes
API spend this task: $0.004447 (4 calls, claude-haiku-5-5, from data/drafts/_calls.jsonl)
Deviations from the prompt: Table B also lists "staging" sentences (Part 5 item 6); the ranges loader now refuses bounds that are not finite numbers (a review finding).
Claims I could not verify: none.
Questions for the owner: the stage groups listed in Table B are for the owner's [fix] entries.
handoff.md updated: yes
=== END ===
```

### S4 — EVAL-02e: taxonomy final, version 1.0 — PASS

Stage commit `eafc0f0` "EVAL-02e: taxonomy final, version 1.0", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = eafc0f0450ae877844addda7704f4b6d96c97fb7 [RAN]. One review round (R1, R2, R3) [RAN].

#### Checklist (7 items, all met)

1. data/taxonomy.json: `version` "1.0", `status` "final", C2's definition exactly "MCV, MCH or MCHC inconsistent with Hb, RBC and Hct; differential not summing to 100; absolute counts inconsistent with WBC."; nothing else changed (R1's byte comparison: the JSON paths changed are /version, /status and /types[7]/definition only; LF, no BOM, same layout); tests/fixtures/taxonomy.json unchanged — **met** [RAN].
2. The updated test is **tests/test_taxonomy.py::test_taxonomy_loads_with_nine_types**: it asserted status "draft" and version "0.1"; it now asserts "final", "1.0" and the exact C2 wording. Run on the unchanged file first, it failed (`AssertionError: assert 'draft' == 'final'`, 1 failed, 4 passed). No other test changed — **met** [RAN].
3. handoff.md: heading "## Error taxonomy (OWNER VERIFIED, final, version 1.0, 2026-11-10)"; the C2 line carries the new wording; the open item "Taxonomy finalised by the owner before any draft is edited" removed; decision 41 "Taxonomy final as version 1.0. C2 now names MCV with MCH and MCHC." (header "29–41 on 2026-11-10") — **met** [RAN; R1].
4. Stage commands — **met** [RAN]:
   - `uv run pathqc-eval plant --check` — exit 1, the expected result while 25 planted reports have no [error] entry — plant --check: 9 OK, 25 with problems, 0 sheet problem(s); nothing written (9 OK, 25 "no planted errors yet"; identical to the output with the draft taxonomy, R1).
   - `uv run pathqc-eval freeze --check` — exit 1 — `freeze --check: FAILED: data/prompts.lock.json does not exist`.
5. Commit `EVAL-02e: taxonomy final, version 1.0` — **met** (eafc0f0) [RAN].
6. Gate: `uv run pytest -q` exit 0, 440 passed; ruff check and format exit 0; explicit staging; push; remote = HEAD — **met** [RAN].
7. No API call (data/drafts/_calls.jsonl unchanged, 38 lines); only the three stage files changed — **met** [RAN; R3].

#### Review findings and triage

| finding | verdict | action |
|---|---|---|
| The plain-condition isolation check looks for type ids, type names and severity definitions, not for type definitions, so a copied definition in the plain prompt would pass the freeze (R2 S5; pre-existing, not caused by S4) | REJECTED for S4: outside the stage (S4 allows no other test or code change) | Part 4 item 6 |
| No test pins that nothing else in data/taxonomy.json changed, and a leftover duplicate "status" key would pass (R2 weak tests) | REJECTED: S4 allows exactly one test change; the one-off diff was verified byte by byte (R1) and the file has no duplicate keys (R2) | — |
| With the taxonomy final, `pathqc-eval plant` in its building form is no longer refused, so section A3 ("nothing is written under data/reports/ tonight") now rests on never running it on the repository (R3 F1) | CONFIRMED (a hazard, not a defect) | Part 8 item 5; every later review keeps the rule "never run plant without --check or --init, nor freeze without --check, on the repository"; the end-to-end test (S7) runs them only in temporary trees |
| The stage-command evidence lacked exit codes (R3 F2) | CONFIRMED | quoted above |

#### Files changed (eafc0f0)

```text
--- git status --short
M  data/taxonomy.json
M  handoff.md
M  tests/test_taxonomy.py
--- git diff --cached --stat
 data/taxonomy.json     | 6 +++---
 handoff.md             | 8 ++++----
 tests/test_taxonomy.py | 9 +++++++--
 3 files changed, 14 insertions(+), 9 deletions(-)
```

```text
=== EVAL REPORT: EVAL-02e Taxonomy final, version 1.0 (EVAL-N1 S4) ===
Status: DONE
What was asked: set the taxonomy to final, version 1.0, with MCV added to C2's wording; update the one test that asserted the draft; record decision 41.
What was done: three values changed in data/taxonomy.json [RAN]; test_taxonomy_loads_with_nine_types updated test-first [RAN]; handoff.md updated [RAN].
Files changed: data/taxonomy.json — final 1.0, C2 wording; tests/test_taxonomy.py — the draft assertions now the final facts; handoff.md — heading, C2 line, open item, decision 41.
Commands run: uv run pytest — 0 — 20 s — 440 passed; ruff check — 0; ruff format --check — 0; pathqc-eval plant --check — 1 (expected) — 9 OK, 25 no planted errors yet; pathqc-eval freeze --check — 1 — no lock exists.
Checks: pytest 440 passed, 0 failed | ruff check and format clean
Git: branch main; commit eafc0f0 "EVAL-02e: taxonomy final, version 1.0"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: none.
Claims I could not verify: none.
Questions for the owner: Part 4 item 6 (plain isolation and type definitions).
handoff.md updated: yes
=== END ===
```

### S5 — EVAL-04: evaluation harness (fake client), isolation and anchor fixes — PASS

Stage commit `51f79be` "EVAL-04: evaluation harness, isolation and anchor fixes", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = 51f79be5fc3d6aa49aee0e1ace34376b1fc96974 [RAN]. Three review rounds (R1, R2, R3); the round-3 findings were fixed test-first without a fourth round (Part 3 item 2), checked with the lead's mutation run and by re-running R2's own reproduction scripts [RAN]. No model API call was made in this stage [RAN; R3 each round].

#### Pre-flight [RAN]

- On `main`; HEAD d14b648 = `git ls-remote origin main`; `git status --short` empty, so nothing inside the owner-editable areas either; HEAD is after 32ac420 and the 11 commits since it all start with EVAL-.
- `git log --oneline -5`: d14b648 EVAL-N1: record S4; eafc0f0 EVAL-02e: taxonomy final, version 1.0; d70747a EVAL-N1: record S3; 2269b0d EVAL-02d: drafting instructions corrected; four reports drafted again; 857ae24 EVAL-N1: record S2.
- `uv run pytest` before the stage: 440 passed, exit 0. The output of the run made when the stage began was not kept; the count is from HEAD d14b648 re-run on a git-archive copy during review round 1, and R1 and R3 each got the same [RAN].

#### Checklist (items 0–22, all met)

0. Pre-flight — **met** (above).
1. `check_eval_isolation`: the whole-word split test is replaced by label forms, in both messages, any case: `split:` followed by dev or scored, with spaces, quotes or markdown emphasis allowed around the colon and a prefix joined to the label still counting (`data_split: dev`); the key `"split"` in double quotes, or 'split' in any quotes before a colon. "HER2 scored 2+", "The dev slide was reviewed." and 'split' in quotes in prose pass; the user message must still equal the report text. Test first: 12 failed on the old code — **met** [RAN].
2. `check_omission_anchor`: an omission's anchor must be in Values (CBC) or in the Synoptic summary or Diagnosis (histopathology); the message names the error id, the section given and the sections allowed; pass and fail tests for both modalities. Test first: 6 failed. On the repository `plant --check` shows no anchor problem — **met** [RAN].
3. RunConfig gains `effort` ("default"), `max_tokens`, `sdk_version`, `lock_created_at`; one dataset and one condition per run; the run id is `<YYYYMMDD-HHMMSS>-<dataset>-<condition>` (UTC) unless given — **met** [RAN].
4. `findings.py`: `parse_findings` → ParseResult(status, findings, dropped, notes); code fences, `{"findings": [...]}` or a bare list; anything else invalid, an empty list valid; ParsedFinding with stripped required strings, severity lower-cased or null, confidence a number in [0, 1] or null, rationale a string or ""; extra keys noted; findings without a usable required string dropped with the reason; `schema.Finding` unchanged — **met** [RAN].
5. Clients: `EvalClient.complete(system, user, max_tokens)` → EvalResponse; `AnthropicEvalClient` sends exactly model, system, one user message and max_tokens (claude-sonnet-5-5; no effort, sampling or tools), refuses a missing key with the drafting client's names-only error, joins the text blocks; `FakeEvalClient` for tests — **met** [RAN].
6. Units (report, repeat 1–3); isolation checked for every report and the run refused before any call; attempt 2 after an unreadable output or a stop reason other than end_turn; then valid or invalid — **met** [RAN].
7. Transport failures — connection errors and timeouts, HTTP 408, 429 and 500–599, whatever the API's x-should-retry header says — retried up to 3 times after 2, 8 and 30 s and logged as transport lines, not attempts — **met** [RAN].
8. `config.json`: the RunConfig; a scored run's hashes from the lock with lock_created_at, a dev run's computed with the freeze's functions, lock_created_at null — **met** [RAN].
9. `calls.jsonl` (gitignored): one line per attempt with the 20 fields; transport lines carry the unit ids, the error class and the message (Part 5 item 7); no request text — **met** [RAN].
10. `results.json`: rebuilt from calls.jsonl at the end of every invocation; units by report id, then repeat; totals with the distinct models returned — **met** [RAN].
11. Resume skips finished units and refuses a changed config — **met** [RAN].
12. Cost gate: `--cost-gate` required; cumulative from calls.jsonl; the next call assumed to cost as much as the dearest so far ($0.06 before any), counting calls in flight — **met** (a soft bound by this rule: Part 4 item 7) [RAN].
13. `--workers N` (default 4), one writer, results ordered by report then repeat, `--max-calls N` stops cleanly — **met** [RAN].
14. `pathqc-eval run`: scored refuses unless `freeze --check` passes (the same check_lock); dev uses the dev reports and refuses none, an invalid one, or (structured) a placeholder — **met** [RAN].
15. `--dry-run`: no client, no gate needed; counts, the full messages of the first report of each modality, and the estimate labelled as an assumption — **met** [RAN].
16. A real run prints a line per finished unit and the totals — **met** [RAN].
17. Tests: every case the stage lists, with the fake client in temporary folders only. R1's and R3's audit hooks over the whole suite found no read of data/reports/, data/drafts/, the owner's texts or `.env`, no socket and no SDK client — **met** [RAN; R1, R3].
18. README: the run command, the run folder, resume, the gate, and calls.jsonl kept local until release — **met** [RAN].
19. handoff.md: decisions 42–46 word for word (R1's byte comparison), the open item on model settings replaced by the dev-run item, in the stage commit; "Last updated" and the task-log row in this record commit, as in S3 and S4 (Part 5 item 8) — **met** [RAN].
20. Checks and commit — **met** (below) [RAN].
21. The record — this section.
22. Run rules: no API call; no change outside the stage; owner files untouched; no new dependency; no test weakened — **met** [RAN; R3 each round].

#### Gate commands (final state, 51f79be) [RAN]

- `uv run pytest` — exit 0 — 673 passed
- `uv run ruff check .` — exit 0 — All checks passed!
- `uv run ruff format --check .` — exit 0 — 46 files already formatted
- `uv run pathqc-eval run --dataset dev --condition plain --dry-run` — exit 1, the step-8 refusal the stage expects:

```text
run refused:
  - no dev reports in data/reports/
```

- `uv run pathqc-eval freeze --check` — exit 1 — `freeze --check: FAILED: data/prompts.lock.json does not exist`

#### In the reply (step 9; invented data, fake client, temporary folder) [RAN]

The fake run's console output (one worker; 2 dev reports, C-001 clean and H-001 planted; repeat 2 of C-001 unreadable twice):

```text
run 20261116-093000-dev-plain: 2 reports x 3 repeats, dev, plain, gate $1.00
C-001 repeat 1: valid | 0 finding(s) | 2400 in + 380 out tokens | $0.0086 | running $0.0086
C-001 repeat 2: invalid | 0 finding(s) | 4800 in + 760 out tokens | $0.0172 | running $0.0258
C-001 repeat 3: valid | 0 finding(s) | 2400 in + 380 out tokens | $0.0086 | running $0.0344
H-001 repeat 1: valid | 1 finding(s) | 2400 in + 380 out tokens | $0.0086 | running $0.0430
H-001 repeat 2: valid | 1 finding(s) | 2400 in + 380 out tokens | $0.0086 | running $0.0516
H-001 repeat 3: valid | 1 finding(s) | 2400 in + 380 out tokens | $0.0086 | running $0.0602
totals: 6 units (5 valid, 1 invalid, 0 pending) | 7 calls | 16800 input + 2660 output tokens | $0.0602 | models returned: claude-sonnet-5-5
[exit code 0]
```

A calls.jsonl line of a valid unit, as stored:

```json
{"run_id":"20261116-093000-dev-plain","report_id":"H-001","condition":"plain","repeat":1,"attempt":1,"started_at":"2026-11-16T09:30:00Z","duration_s":0.0,"model_requested":"claude-sonnet-5-5","model_returned":"claude-sonnet-5-5","system_sha256":"bf0a38617fcd283bd9dff0820a9e089e724b5b9b767e910d1802464568424bef","user_sha256":"5f75aea5e25b067f0edceab1a5061f86c75042646538b80fbb79d8de94fb7c9b","raw_text":"```json\n{\"findings\": [{\"quoted_sentence\": \"Tumour measures 25 mm.\", \"section\": \"Microscopic description\", \"category\": \"size mismatch between gross and microscopy\", \"severity\": \"major\", \"confidence\": 0.85, \"rationale\": \"The gross description gives 18 mm.\", \"note\": \"extra\"}]}\n```","stop_reason":"end_turn","input_tokens":2400,"output_tokens":380,"cost_usd":0.0086,"parse_status":"valid","findings":[{"quoted_sentence":"Tumour measures 25 mm.","section":"Microscopic description","category":"size mismatch between gross and microscopy","severity":"major","confidence":0.85,"rationale":"The gross description gives 18 mm."}],"dropped":[],"notes":["finding 1: extra keys ignored: note"]}
```

A calls.jsonl line of an invalid attempt, as stored:

```json
{"run_id":"20261116-093000-dev-plain","report_id":"C-001","condition":"plain","repeat":2,"attempt":1,"started_at":"2026-11-16T09:30:00Z","duration_s":0.0,"model_requested":"claude-sonnet-5-5","model_returned":"claude-sonnet-5-5","system_sha256":"bf0a38617fcd283bd9dff0820a9e089e724b5b9b767e910d1802464568424bef","user_sha256":"e051b86323241d95c84e2da4d1dc0760d427fe8345718747b02208e5874b6de5","raw_text":"I could not find any errors in this report.","stop_reason":"end_turn","input_tokens":2400,"output_tokens":380,"cost_usd":0.0086,"parse_status":"invalid","findings":[],"dropped":[],"notes":["output is not JSON (JSONDecodeError)"]}
```

The resulting results.json:

```json
{
  "run_id": "20261116-093000-dev-plain",
  "dataset": "dev",
  "condition": "plain",
  "units": [
    {
      "report_id": "C-001",
      "repeat": 1,
      "status": "valid",
      "attempts": 1,
      "findings": [],
      "dropped_count": 0,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 2400,
      "output_tokens": 380,
      "cost_usd": 0.0086
    },
    {
      "report_id": "C-001",
      "repeat": 2,
      "status": "invalid",
      "attempts": 2,
      "findings": [],
      "dropped_count": 0,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 4800,
      "output_tokens": 760,
      "cost_usd": 0.0172
    },
    {
      "report_id": "C-001",
      "repeat": 3,
      "status": "valid",
      "attempts": 1,
      "findings": [],
      "dropped_count": 0,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 2400,
      "output_tokens": 380,
      "cost_usd": 0.0086
    },
    {
      "report_id": "H-001",
      "repeat": 1,
      "status": "valid",
      "attempts": 1,
      "findings": [
        {
          "quoted_sentence": "Tumour measures 25 mm.",
          "section": "Microscopic description",
          "category": "size mismatch between gross and microscopy",
          "severity": "major",
          "confidence": 0.85,
          "rationale": "The gross description gives 18 mm."
        }
      ],
      "dropped_count": 0,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 2400,
      "output_tokens": 380,
      "cost_usd": 0.0086
    },
    {
      "report_id": "H-001",
      "repeat": 2,
      "status": "valid",
      "attempts": 1,
      "findings": [
        {
          "quoted_sentence": "Tumour measures 25 mm.",
          "section": "Microscopic description",
          "category": "size mismatch between gross and microscopy",
          "severity": "major",
          "confidence": 0.85,
          "rationale": "The gross description gives 18 mm."
        }
      ],
      "dropped_count": 0,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 2400,
      "output_tokens": 380,
      "cost_usd": 0.0086
    },
    {
      "report_id": "H-001",
      "repeat": 3,
      "status": "valid",
      "attempts": 1,
      "findings": [
        {
          "quoted_sentence": "Tumour measures 25 mm.",
          "section": "Microscopic description",
          "category": "size mismatch between gross and microscopy",
          "severity": null,
          "confidence": 0.85,
          "rationale": "The gross description gives 18 mm."
        }
      ],
      "dropped_count": 1,
      "model_returned": "claude-sonnet-5-5",
      "input_tokens": 2400,
      "output_tokens": 380,
      "cost_usd": 0.0086
    }
  ],
  "totals": {
    "units": 6,
    "valid": 5,
    "invalid": 1,
    "pending": 0,
    "calls": 7,
    "input_tokens": 16800,
    "output_tokens": 2660,
    "cost_usd": 0.0602,
    "models_returned": [
      "claude-sonnet-5-5"
    ]
  }
}
```

The dry run on a temporary tree with two dev reports (H-001 planted, C-001 clean); invented data:

```text
DRY RUN: no client is constructed and no API call is made.
dataset dev | condition plain | 2 reports | 6 units (3 repeats each) | at most 12 calls (2 attempts per unit)
===== H-001 system message (plain) =====
You are reviewing a laboratory report before it is signed out. The report is given in the user message, section by section.

Read the whole report and identify every error you can find in it. Do not rewrite the report.

Return only a JSON object, with no text before or after it, in this form: {"findings": [ ... ]}
Each finding is an object with exactly these fields:
- "quoted_sentence": the sentence or line from the report that contains the error, copied exactly. If the error is that something is missing, quote the sentence or line that makes the omission evident.
- "section": the name of the section the quoted text is in, exactly as it appears in the report.
- "category": a short label, in your own words, for the kind of error.
- "severity": one of "critical", "major", "minor".
- "confidence": a number from 0 to 1, your probability that this is a real error.
- "rationale": one or two sentences explaining the error.
If you find no error, return {"findings": []}.
===== H-001 user message =====
## Clinical details
Synthetic test case. Lump noted on examination.

## Specimen
Wide local excision, left side.

## Gross description
Fatty tissue 40 x 30 x 20 mm with a firm lesion 18 mm across.

## Microscopic description
Sections show an invasive tumour. Tumour measures 25 mm.

## Diagnosis
Invasive tumour, grade 2.

## Synoptic summary
Size 18 mm; grade 2; margins clear; LVI absent; PNI absent; nodes 0/3; pT1c pN0.
===== C-001 system message (plain) =====
You are reviewing a laboratory report before it is signed out. The report is given in the user message, section by section.

Read the whole report and identify every error you can find in it. Do not rewrite the report.

Return only a JSON object, with no text before or after it, in this form: {"findings": [ ... ]}
Each finding is an object with exactly these fields:
- "quoted_sentence": the sentence or line from the report that contains the error, copied exactly. If the error is that something is missing, quote the sentence or line that makes the omission evident.
- "section": the name of the section the quoted text is in, exactly as it appears in the report.
- "category": a short label, in your own words, for the kind of error.
- "severity": one of "critical", "major", "minor".
- "confidence": a number from 0 to 1, your probability that this is a real error.
- "rationale": one or two sentences explaining the error.
If you find no error, return {"findings": []}.
===== C-001 user message =====
## Values
Hb: 14.0 g/dL (ref 13.0–17.0)
RBC: 4.70 x10^12/L (ref 4.50–5.50)
Hct: 42.0 % (ref 40.0–50.0)
MCV: 89.4 fL (ref 83.0–101.0)
MCH: 29.8 pg (ref 27.0–32.0)
MCHC: 33.3 g/dL (ref 31.5–34.5)
RDW: 13.0 % (ref 11.6–14.0)
WBC: 8.00 x10^9/L (ref 4.00–11.00)
Neutrophils %: 60.0 % (ref 40.0–80.0)
Neutrophils absolute: 4.80 x10^9/L (ref 2.00–7.00)
Lymphocytes %: 30.0 % (ref 20.0–40.0)
Lymphocytes absolute: 2.40 x10^9/L (ref 1.00–3.00)
Monocytes %: 6.0 % (ref 2.0–10.0)
Monocytes absolute: 0.48 x10^9/L (ref 0.20–1.00)
Eosinophils %: 3.0 % (ref 1.0–6.0)
Eosinophils absolute: 0.24 x10^9/L (ref 0.02–0.50)
Basophils %: 1.0 % (ref 0.0–2.0)
Basophils absolute: 0.08 x10^9/L (ref 0.02–0.10)
Platelets: 250 x10^9/L (ref 150–410)
MPV: 10.0 fL (ref 7.5–11.5)

## Interpretation
All values within reference ranges.

## Comment/recommendation
No action needed.
Estimate (an ASSUMPTION until the dev run measures it): 2,500 input + 4,000 output tokens per call at Sonnet prices = $0.0450 per call; 6 calls (one per unit) = $0.2700; at most 12 calls = $0.5400
[exit code 0]
```

The step-8 refusal on the repository is quoted under the gate commands above. `git diff --stat d14b648 51f79be` (from the previous EVAL commit):

```text
 .gitignore                   |    1 +
 README.md                    |   36 +-
 handoff.md                   |    9 +-
 src/pathqc_eval/cli.py       |  225 ++++++-
 src/pathqc_eval/findings.py  |  168 ++++++
 src/pathqc_eval/harness.py   |  871 +++++++++++++++++++++++++++
 src/pathqc_eval/prompting.py |   17 +-
 src/pathqc_eval/schema.py    |    7 +
 src/pathqc_eval/validate.py  |   18 +
 tests/conftest.py            |    8 +
 tests/test_eval_isolation.py |  119 ++++
 tests/test_findings.py       |  248 ++++++++
 tests/test_harness.py        | 1335 ++++++++++++++++++++++++++++++++++++++++++
 tests/test_plant.py          |   28 +-
 tests/test_schema.py         |   28 +
 tests/test_validate.py       |   73 +++
 16 files changed, 3183 insertions(+), 8 deletions(-)
```

#### Review findings, triage and fixes

Before the first review the lead found and fixed two defects test-first: a failure in flight was hidden when --max-calls had stopped scheduling (exit 0), and an escaped unpaired surrogate in an output stopped the run while the call was logged [RAN].

Round 1 (R1 spec audit, R2 adversarial test: 59 cases, 17 failed; R3 safety and scope) [RAN]:

| finding | verdict | fix (test that failed first) |
|---|---|---|
| Ctrl+C, or a calls.jsonl write that fails, lost the lines of every call in flight (billed) and left results.json unbuilt (R2 KB-01/02, R3-2) | CONFIRMED | no new call starts; the calls in flight are waited for and logged; results.json is rebuilt from calls.jsonl; exit 130 after Ctrl+C, 1 after a write failure (test_an_interrupt_logs_every_call_in_flight_and_rebuilds_results; test_a_log_write_failure_stops_the_run_and_still_logs_the_other_calls) |
| Two files with the same report id: one silently dropped, dry-run counts wrong (R2 HR-05) | CONFIRMED | refused, naming both files (test_two_report_files_with_the_same_id_are_refused) |
| config.json deleted, then a resume in another condition adopted the old calls.jsonl lines (R2 HR-08) | CONFIRMED | refused: "holds calls.jsonl but no config.json"; every line must belong to this run and condition (test_a_run_folder_with_calls_but_no_config_is_refused; test_a_call_line_of_another_condition_is_refused) |
| A calls.jsonl line that parses but lacks fields crashed the resume (R2 HR-06) | CONFIRMED | each line validated as an attempt or failure line before the client is built (test_a_call_line_missing_fields_is_refused_cleanly) |
| HTTP 408 (a timeout) was fatal instead of retried (R2 CL-06/08) | CONFIRMED | 408 is a transport failure (round 2 settled the full list) |
| Split labels missed: `{'split': 'scored'}`, `data_split: dev`, `**Split:** scored`, `split: “dev”` (R2 ISO-01..04) | CONFIRMED | label regex allows quotes and markdown around the colon and a joined prefix (test_decorated_split_labels_fail) |
| `--run-id NUL` (a Windows device name) ended in a traceback after the client was built (R2 HR-10) | CONFIRMED | device names and a trailing dot refused (test_run_ids_windows_cannot_create_are_refused) |
| A prompt file saved as UTF-16 ended in a traceback (R2 HR-11/11b) | CONFIRMED | refused: "is not UTF-8 text; save it as UTF-8" (test_a_prompt_file_that_is_not_utf8_is_refused_naming_it) |
| Tilde code fences refused (R2 PF-01) | CONFIRMED | accepted (test_tilde_and_longer_code_fences_are_accepted) |
| Extra keys of a dropped finding not noted (R2 PF-09) | CONFIRMED | noted (test_extra_keys_of_a_dropped_finding_are_noted) |
| Gate shown rounded to the cent ($0.185 as $0.18) (R2) | CONFIRMED | shown as given (test_the_gate_is_shown_as_given) |
| Transport lines carry the unit ids, though the stage says "error class and message only" (R2 HR-18, R1) | REJECTED as a defect: a line has to name its unit; no request or response content is stored | Part 5 |
| `--max-calls` counts attempts, not HTTP requests (R3-3) | REJECTED for S5: the stage text says attempts | Part 4; S8 handles its call cap |
| The gate is a soft bound: one call at the 16,000-token limit costs about $0.17 against the $0.06 first-call assumption (R3-1) | REJECTED as a defect: the stage text prescribes the rule | README says so; Part 4 (owner) |
| Seven tests passed with their feature broken (R2 weak tests, mutants A–H and O) | CONFIRMED | new tests: spend read back on resume; dearest not last call; results order independent of completion; call_messages_api argument shape, text joining and 429; prompt_hash over every structured prompt file; resume refuses each changed setting; raw output kept in full. Each mutant re-run: KILLED (lead_mutants_round1.txt) |
| Pre-flight pytest count missing from the evidence (R1, R3-5) | CONFIRMED | HEAD's suite re-run from a git-archive copy: 440 passed, exit 0 (the start-of-stage output was not kept) |
| fake_run.txt re-serialised the calls lines (R3-5) | CONFIRMED | the record quotes the stored lines |

Round 2 (R2: 41 cases, 24 failed; R1 item 7 partly) [RAN]:

| finding | verdict | fix (test that failed first) |
|---|---|---|
| A model output holding U+2028, U+2029 or U+0085 broke calls.jsonl: read with str.splitlines, the invocation failed after its calls and the run could not be resumed (R2 LS-01..03) | CONFIRMED (serious) | calls.jsonl is split at "\n" only (test_unicode_line_separators_in_an_output_keep_calls_jsonl_readable) |
| The round-1 fence regex was cubic: 16,000 backticks took 64 s on the run's only writer thread (R2 PF-05) | CONFIRMED | linear fence reader (test_a_long_run_of_fence_characters_is_read_quickly) |
| Longer closing fence, a space before the info string, `json5` refused (R2 PF-01..03) | CONFIRMED | accepted (test_more_code_fence_forms_are_accepted) |
| UTF-16 without a byte order mark passed the UTF-8 and placeholder checks; a NUL-interleaved placeholder would reach the model (R2 ENC-01..04) | CONFIRMED | a prompt file holding NUL is refused as not UTF-8 (test_a_prompt_file_in_utf16_without_a_byte_order_mark_is_refused; with a Windows-1252 file for the plain decode path) |
| Numbers written as text passed the lax line validation and crashed the resume (R2 CL-01..04) | CONFIRMED | strict validation (test_a_call_line_with_a_number_written_as_text_is_refused) |
| Ctrl+C between starting a call and noting it in flight lost a billed call (R2 KB-01) | CONFIRMED | the clock is read before the call starts; the call is noted in the same statement (test_an_interrupt_while_a_call_is_being_started_loses_no_call) |
| A write that failed part-way left a fragment, making calls.jsonl unparseable (R2 PW-01) | CONFIRMED | the file is cut back to its size before the write (test_a_write_that_fails_part_way_leaves_no_fragment) |
| Two invocations on one run id repeated calls and corrupted the run (R2 CC-01/02) | CONFIRMED | an exclusive lock on runs/<id>/.run.lock (gitignored) while a run goes on; the operating system releases it at exit (test_a_second_invocation_on_a_run_that_is_going_is_refused) |
| A second Ctrl+C skipped the rebuild while the CLI said results.json was rebuilt (R2 KB-03) | CONFIRMED | the rebuild runs after a second Ctrl+C; the message says whether it happened (test_a_second_interrupt_abandons_the_calls_in_flight_and_still_rebuilds_results) |
| 'split' in single or typographic quotes in prose was refused (R2 ISO-01/02; R3 decision 42) | CONFIRMED | the key is "split" in double quotes, or 'split' in any quotes before a colon; prose passes (test_split_in_quotes_in_prose_passes) |
| The SDK retry rule went beyond the stage list: 429/5xx with x-should-retry false were fatal, 409 and any status with x-should-retry true retried (R1 item 7) | CONFIRMED | exactly the stage list: connection errors and timeouts, 408, 429, 5xx, whatever the header says (test_rate_limits_server_errors_and_timeouts_are_transport_failures) |
| Amounts of 1000 or more shown rounded ($1000.005 as $1000) (R2 USD) | CONFIRMED | shown as given (test_amounts_are_shown_to_the_cent_or_as_given) |
| The user-message variant of '"Split": "dev"' was dropped in round 1 (R3-1) | CONFIRMED | the decorated-label test runs over both messages |
| Weak tests (R2 M1–M7): drain of calls still running, no new call after Ctrl+C or a write failure, run_id compared, failure lines validated, complete() argument order, check before the client, duplicates across splits | CONFIRMED | new tests; every mutant KILLED (lead_mutants_round2.txt: 45 mutants, all killed after one added test) |
| --max-calls and transport retries; the soft gate (R3-2, R3-3, carried) | REJECTED for S5 (stage text) | Part 4; S8 |
| Behaviours beyond the stage text to disclose (R3-4) | CONFIRMED | Part 3 |

Round 3, the last round (R1: all items met or pending the commit; R2: 101 cases, 16 failed from 7 defects; R3: no rule broken) [RAN]. Fixed test-first without a fourth review round (Part 3 item 2); each fix was then checked with the lead's mutation run and by re-running R2's own reproduction scripts on the fixed code (every failing case now passes; one regression the re-run found, LK-06/07, was fixed test-first too):

| finding | verdict | fix (test that failed first) |
|---|---|---|
| The config was compared before the lock was taken, so an invocation that another one overtook could resume under its own settings (R2 LK-03, low-medium) | CONFIRMED | the config and calls.jsonl are checked again once the lock is held (test_a_run_another_invocation_creates_meanwhile_is_compared_under_the_lock) |
| While another invocation held the run and was mid-write, a second one reported calls.jsonl as damaged instead of busy, and built its client first (R2 LK-05, R3-1) | CONFIRMED | the lock is probed before the run's files are read or a client is built (test_a_held_lock_is_reported_before_the_run_files_are_read) |
| A calls.jsonl whose last newline was removed by an outside edit got the next line glued to it (R2 CL-03) | CONFIRMED | a missing final newline is written before the next line (test_a_calls_file_without_a_final_newline_is_continued_cleanly) |
| Ctrl+C during the final printout said results.json was not rebuilt when it was (R2 IN-01) | CONFIRMED | flagged as rebuilt (test_an_interrupt_after_results_were_written_says_they_were) |
| Underscore emphasis after the value hid a label ("Split: _dev_") (R2 IS-05) | CONFIRMED | after the value no letter or digit may follow; "_" may (test_split_labels_with_underscore_emphasis_fail) |
| JSON beginning on the opening fence line was dropped with the info string, a regression from round 2 (R2 FN-01a/b) | CONFIRMED | content starting with { or [ on the opening line is kept (test_json_that_starts_on_the_opening_fence_line_is_read) |
| Status codes 600 and above counted as server errors (R2 TR-12) | CONFIRMED (negligible) | 500 to 599 only (test_server_errors_are_the_5xx_statuses) |
| The lock probe added in this round raised a traceback when .run.lock is a folder or read-only (re-run of R2's LK-06/07) | CONFIRMED (own regression) | refused in plain words (test_a_lock_file_that_cannot_be_used_is_refused_in_plain_words) |
| Weak tests: the lock test held the lock in-process only (R2 MB, MA2); no test of the "was not rebuilt" message (MC); no line of request text checked (MD); 5xx rows 500, 503, 529 only (ME) | CONFIRMED | a second process holds the lock; the run is checked to hold its own lock while calls are made; results.json made unwritable; every request line of 20 characters or more is checked absent from calls.jsonl; 502 and 599 rows |
| The gate is a soft bound; --max-calls counts attempts, not HTTP requests (R3-2, R3-3, carried) | REJECTED for S5 (the stage text) | Part 4; S8 |
| Assignment forms ("split = dev", "'split' = 'dev'") are not refused; round 3 stopped refusing the quoted one (R3-5) | REJECTED as a defect: outside decision 42's forms | Part 4 (owner) |
| Behaviours beyond the stage text, and the lead's own reversals (R3-4) | CONFIRMED | Part 3; Deviations in the EVAL block |

#### Files changed (51f79be)

```text
--- git status --short
M  .gitignore
M  README.md
M  handoff.md
M  src/pathqc_eval/cli.py
A  src/pathqc_eval/findings.py
A  src/pathqc_eval/harness.py
M  src/pathqc_eval/prompting.py
M  src/pathqc_eval/schema.py
M  src/pathqc_eval/validate.py
M  tests/conftest.py
M  tests/test_eval_isolation.py
A  tests/test_findings.py
A  tests/test_harness.py
M  tests/test_plant.py
M  tests/test_schema.py
M  tests/test_validate.py
--- git diff --cached --stat
 .gitignore                   |    1 +
 README.md                    |   36 +-
 handoff.md                   |    9 +-
 src/pathqc_eval/cli.py       |  225 ++++++-
 src/pathqc_eval/findings.py  |  168 ++++++
 src/pathqc_eval/harness.py   |  871 +++++++++++++++++++++++++++
 src/pathqc_eval/prompting.py |   17 +-
 src/pathqc_eval/schema.py    |    7 +
 src/pathqc_eval/validate.py  |   18 +
 tests/conftest.py            |    8 +
 tests/test_eval_isolation.py |  119 ++++
 tests/test_findings.py       |  248 ++++++++
 tests/test_harness.py        | 1335 ++++++++++++++++++++++++++++++++++++++++++
 tests/test_plant.py          |   28 +-
 tests/test_schema.py         |   28 +
 tests/test_validate.py       |   73 +++
 16 files changed, 3183 insertions(+), 8 deletions(-)
```

#### What was not tested

- The real API: no call was made (the stage forbids it). `AnthropicEvalClient.complete` and `call_messages_api` were tested over stubs only; whether the API sends 408 or an x-should-retry header was not seen. S8 is the first contact.
- A console Ctrl+C: interrupts were raised in the main thread by the tests (and with `_thread.interrupt_main` by R2).
- The run lock on Linux or macOS (the fcntl branch); only Windows (msvcrt) ran. Two processes were tested on Windows (the suite and R1/R2).
- A whitespace-only API key (the key check is empty or missing).

```text
=== EVAL REPORT: EVAL-04 Evaluation harness (fake client), isolation and anchor fixes (EVAL-N1 S5) ===
Status: DONE
What was asked: the run harness for the evaluated model, built and tested against a fake client and exercised in dry-run mode only; the label-form split check; the omission-anchor rule; the five owner decisions recorded.
What was done: findings.py and harness.py written and `pathqc-eval run` added [RAN]; RunConfig extended [RAN]; isolation and anchor fixes test-first [RAN]; three review rounds: 32 defects confirmed and fixed, each with a test that failed first, and 18 weak tests strengthened; every mutant of the lead's mutation checks killed [RAN]; README and handoff.md updated [RAN].
Files changed: .gitignore — runs/*/.run.lock; README.md — the run section, refusals, the anchor rule; handoff.md — decisions 42–46, open items; src/pathqc_eval/cli.py — the run command; src/pathqc_eval/findings.py — new, lenient reading; src/pathqc_eval/harness.py — new, the harness; src/pathqc_eval/prompting.py — split label forms; src/pathqc_eval/schema.py — RunConfig fields; src/pathqc_eval/validate.py — check_omission_anchor; tests/conftest.py — the key blanked for every test; tests/test_findings.py and tests/test_harness.py — new; tests/test_eval_isolation.py, test_plant.py, test_schema.py, test_validate.py — the new rules.
Commands run: uv run pytest — 0 — 40 s — 673 passed; uv run ruff check . — 0; uv run ruff format --check . — 0; uv run pathqc-eval run --dataset dev --condition plain --dry-run — 1 (the expected refusal) — no dev reports in data/reports/; uv run pathqc-eval freeze --check — 1 — no lock exists.
Checks: pytest 673 passed, 0 failed | ruff check and format clean
Git: branch main; commit 51f79be "EVAL-04: evaluation harness, isolation and anchor fixes"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: the lead's own choices, changed during review before the commit: the SDK retry rule (409, x-should-retry) dropped for the stage's list; the quoted-'split' key narrowed back to decision 42's forms. "Last updated" and the task-log row go in the record commit (Part 5 item 8).
Claims I could not verify: the real API's behaviour (S8); a console Ctrl+C; the run lock on Linux or macOS.
Questions for the owner: Part 4 items 7–10 (the soft gate; --max-calls and transport retries; '=' forms of the split; an EVAL-01 test that will fail once reports are built).
handoff.md updated: yes
=== END ===
```

### S6 — EVAL-05: scorer, blind adjudication, metrics — PASS

Stage commit `61982e3` "EVAL-05: scorer, blind adjudication, metrics", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = 61982e3f9feb2e61fa1a45cf197d708b70b183c4 [RAN]. Three review rounds; the round-3 findings were fixed test-first without a fourth round (Part 3 item 2), each fix checked with the lead's mutation run. Review round 2 was interrupted when the overnight session ended; on resume R1 and R3 were taken from the run's journal and R2 was run again on the unchanged tree [RAN]. No model API call was made in this stage [RAN; R3 each round: client factories replaced by raising stubs, anthropic not imported].

#### Pre-flight [RAN]

- On `main`; HEAD 3bc68ce (EVAL-N1: record S5) = `git ls-remote origin main`; the working tree held only the stage's files.
- `uv run pytest` at the S5 commit: 673 passed, exit 0 (S5 record).

#### Checklist (items 0–12; the round-3 checklist restates the stage text in full)

0. Decisions 4, 7, 8, 9, 10, 34 and 45 — **met**, with two clauses recorded rather than enforced and sent to the owner: decision 9 against 6.8's `--provisional` (ranges by condition), and decision 10's "nothing is remapped after scoring" (the map's version and sha256 are in score.json) (Part 4) [RAN; R1 round 3].
1. (6.1) scoring_config.py: the eight named constants with one-line comments; OWNER_CONFIRMED False; `score --dataset scored` refuses and lists (a)–(f) — **met** [RAN].
2. (6.2) normalise_section, tokens (a point kept only between digits), overlap (the larger direction) — **met** [RAN].
3. (6.3) category map file and checks; normalise_category drops every trailing Unicode punctuation character (Part 3); map-list writes results/<dataset>/category_strings.json and never the map; no data/category_map.json created — **met** [RAN].
4. (6.4) every rule, precedence hit > review > near_miss, highest overlap then lowest error id, duplicates, verdicts — **met**; boundary tests at ov 0.6 and 0.4 [RAN].
5. (6.5) units, majority over valid units, fewer than two valid listed — **met** [RAN].
6. (6.6) primary and secondary metrics, Wilson intervals, Brier and ECE, consistency, severity-weighted recall, paired bootstrap (10,000 resamples, seed 20261115, percentile interval), counts — **met** [RAN].
7. (6.7) prepare / apply / status; merged items; ids "A" + three digits in a seeded shuffle; owner files name no condition, repeat, model or run (tested); the reveal only in `score`, only when every verdict is filled; adjudication_log.json with prepared_at, completed_at, joined_at, items and sha256 — **met** [RAN].
8. (6.8) checks; refusal until adjudicated, or `--provisional` ranges in results/<dataset>/provisional/ with PROVISIONAL in every title; score.json and summary.md as listed; no clock time; byte-identical reruns, also across processes with different hash seeds — **met**, except that provisional output leaves out the per-error and per-finding tables to protect decision 9 (Part 3, Part 4) [RAN].
9. (6.9) the tests the stage lists, in temporary folders with invented data — **met** [RAN].
10. (6.10) README "Scoring and adjudication (EVAL-05)" with the owner's steps; handoff decision 47 PENDING word for word (R1 string comparison) and the open item — **met** [RAN].
11. Checks and commit — **met** (below) [RAN].
12. Run rules: no API call; owner files untouched; no new dependency; no test weakened (R3 each round); every fix to existing behaviour with a test that failed first — **met** [RAN].

#### Gate commands (final state, 61982e3) [RAN]

- `uv run pytest` — exit 0 — 816 passed
- `uv run ruff check .` — exit 0 — All checks passed!
- `uv run ruff format --check .` — exit 0 — 57 files already formatted
- No stage command runs on the repository's data: there are no reports or runs yet, and map-list, adjudicate and score were exercised only in temporary trees (tests and reviewers' probes).

#### Review findings, triage and fixes

Round 1 (R1 spec audit; R2: 36 cases, 9 failed; R3 safety and scope) [RAN]. Failing output: 12 failed before the fixes; 4 more round-1 tests were shown failing on the round-1 code by R1 and R3 (16 failed) and by the lead's revert mutants.

| finding | verdict | fix (test that failed first) |
|---|---|---|
| Verdicts keyed by run, repeat and finding index: two review findings in different reports took one verdict, or the join refused for good (R2 HIGH) | CONFIRMED | keys carry the report id; a hidden file putting one finding in two items is refused (test_review_findings_in_different_reports_keep_their_own_verdicts) |
| `--provisional` listed condition, run and repeat of every open review finding, breaking decision 9 (R1, R3) | CONFIRMED | provisional output without the per-error and per-finding tables; counts as ranges; each provisional score logged and disclosed at the reveal; README warning (5 tests) |
| The disclosure claimed the adjudication was "blind to the condition, the repeat and the model" (R3) | CONFIRMED | factual wording; "A finding's category can still suggest its condition." |
| `prepare --replace` overwrote a verdict typed in a second block (R2) | CONFIRMED | any non-template line blocks --replace |
| An unreadable adjudication_log.json crashed apply, status and score (R2) | CONFIRMED | plain-words refusals |
| `map-list --runs p1 p1` counted the run twice (R2) | CONFIRMED | refused |
| normalise_category kept closing brackets and quotes (R1, R2) | CONFIRMED | every trailing P character dropped (Part 3) |
| The sheet's borderline band hard-coded (R1) | CONFIRMED | built from the settings |
| Seven tests passed with their feature broken (R2) | CONFIRMED | new tests; 22 mutants, all killed |
| Checklist left out the decisions line and shortened items 4 and 6 (R1, R3) | CONFIRMED | restated in full |
| normalise_section drops a trailing run, not one character (R1) | NOT A DEFECT (reading) | Part 5 |

Round 2 (R2: 49 cases, 14 failed; 15 surviving mutants) [RAN]. Failing output: 13 failed before the fixes.

| finding | verdict | fix (test that failed first) |
|---|---|---|
| Provisional text said no item could be traced while its per-condition counts could (R2, R3) | CONFIRMED (wording) | "...no review item is listed with its condition or repeat; the counts and ranges by condition can still show where an item came from."; decision 9 vs 6.8 to the owner |
| A prepared adjudication was ignored when the runs gave no review findings; logged provisional scores went undisclosed (R2) | CONFIRMED | stale refusal; the log is read without a join |
| Provisional interval cells read "a to b to c to d" (R2, R3) | CONFIRMED | bracketed intervals |
| Deleting the provisional folder made the summary say no provisional score was made (R2, R3) | CONFIRMED | the disclosure states what the log records; README says to keep it |
| Unwritable outputs and an unreadable adjudication.json gave a traceback or "not prepared" (R2) | CONFIRMED | plain-words refusals |
| A CR-only sheet was overwritten by --replace (R2) | CONFIRMED | CRLF, CR and LF accepted |
| The join did not check the review reason; duplicate map keys; lax log types (R2) | CONFIRMED | each fixed |
| 15 surviving mutants (R2) | CONFIRMED | new tests; 26 mutants (with reverts of each fix), all killed |

Round 3, the last (R1: all items met or pending the commit; R2: 28 cases, 3 failed, 6 surviving mutants; R3: no rule broken) [RAN]. Fixed test-first (6 failed first); 10 mutants, all killed:

| finding | verdict | fix |
|---|---|---|
| A refused write could leave a new score.json beside an old summary.md (R2, R3) | CONFIRMED | every target is checked writable before anything is written |
| A key given twice in a log could hide provisional scores (R2) | CONFIRMED | both logs refuse a key given twice |
| adjudication.json as a folder reported as missing (R2); map-list's write unguarded (R1); "Review items: 0 ()." (R2); a garbled README sentence (R1) | CONFIRMED | each fixed |
| Six untested paths (R2 mutants N1–N6) | CONFIRMED | new tests |
| A deleted provisional log; results/ not gitignored; PENDING_DEFAULTS literal text (R3) | OWNER | Part 4 |

#### Files changed (61982e3)

```text
--- git status --short
M  README.md
M  handoff.md
A  src/pathqc_eval/adjudication.py
M  src/pathqc_eval/cli.py
M  src/pathqc_eval/io.py
A  src/pathqc_eval/matching.py
M  src/pathqc_eval/schema.py
A  src/pathqc_eval/score_output.py
A  src/pathqc_eval/scoring.py
A  src/pathqc_eval/scoring_config.py
A  src/pathqc_eval/stats.py
A  tests/scoring_fixtures.py
A  tests/test_matching.py
M  tests/test_schema.py
A  tests/test_score_cli.py
A  tests/test_scoring.py
A  tests/test_stats.py
--- git diff --cached --stat
 README.md                         |   26 +
 handoff.md                        |    4 +-
 src/pathqc_eval/adjudication.py   |  581 +++++++++++++++++++++
 src/pathqc_eval/cli.py            |  101 ++++
 src/pathqc_eval/io.py             |   11 +
 src/pathqc_eval/matching.py       |  178 +++++++
 src/pathqc_eval/schema.py         |   13 +-
 src/pathqc_eval/score_output.py   |  535 +++++++++++++++++++
 src/pathqc_eval/scoring.py        |  691 +++++++++++++++++++++++++
 src/pathqc_eval/scoring_config.py |   42 ++
 src/pathqc_eval/stats.py          |  100 ++++
 tests/scoring_fixtures.py         |  180 +++++++
 tests/test_matching.py            |  257 +++++++++
 tests/test_schema.py              |   22 +-
 tests/test_score_cli.py           | 1031 +++++++++++++++++++++++++++++++++++++
 tests/test_scoring.py             |  286 ++++++++++
 tests/test_stats.py               |  111 ++++
 17 files changed, 4163 insertions(+), 6 deletions(-)
```

#### What was not tested

- Real runs: there are no reports in data/reports/ and no runs yet; the scorer was exercised on invented trees only (tests, reviewers' probes; S7 rehearses the whole flow).
- The scored split with real owner verdicts; the owner's reading of the sheet.
- Linux or macOS file permissions for the write check (Windows only).

```text
=== EVAL REPORT: EVAL-05 Scorer, blind adjudication, metrics (EVAL-N1 S6) ===
Status: DONE
What was asked: the scorer (6.1–6.10): settings, text handling, category mapping, classification, majority, metrics with intervals and a paired bootstrap, blind adjudication with a logged reveal, score and map-list, README and handoff decision 47 PENDING.
What was done: six new modules and the CLI commands [RAN]; three review rounds, every confirmed finding fixed with a test that failed first; 58 mutants across three mutation checks, all killed [RAN]; README and handoff updated [RAN].
Files changed: README.md, handoff.md, src/pathqc_eval/{adjudication,matching,score_output,scoring,scoring_config,stats}.py (new), src/pathqc_eval/{cli,io,schema}.py, tests/{scoring_fixtures,test_matching,test_score_cli,test_scoring,test_stats}.py (new), tests/test_schema.py.
Commands run: uv run pytest — 0 — 58 s — 816 passed; uv run ruff check . — 0; uv run ruff format --check . — 0.
Checks: pytest 816 passed, 0 failed | ruff check and format clean
Git: branch main; commit 61982e3 "EVAL-05: scorer, blind adjudication, metrics"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: provisional output leaves out the per-error and per-finding tables, and adds a provisional log (decision 9); further behaviour beyond the stage text is listed in Part 3.
Claims I could not verify: behaviour on real runs and real owner verdicts; file permissions outside Windows.
Questions for the owner: Part 4 items 11–17.
handoff.md updated: yes
=== END ===
```

### S7 — EVAL-05b: end-to-end rehearsal on invented data — PASS

Stage commit `d09cc0e` "EVAL-05b: end-to-end rehearsal", pushed; `git rev-parse HEAD` = `git ls-remote origin main` = d09cc0ea49c29d250184c02d5dcfb0a3579096f8 [RAN]. One new module, tests/test_end_to_end.py; nothing in src/ changed, because the rehearsal exposed no defect in the S6 code [RAN]. Three review rounds; the round-3 findings were fixed without a fourth round (Part 3 item 2), each checked with the lead's mutation run. No model API call (FakeEvalClient only; R3 each round) [RAN].

#### Checklist (items 1–12, round-3 wording)

1. One new test module; no src change (no defect found) — **met** [RAN].
2. A temporary root with 34 invented drafts (the conftest fixtures the freeze tests use: histo, cbc, real_prompts; plus rerender for the CBC Values text) and a spec of the real shape — **met** [RAN].
3. A planting sheet written by the test: H1–H6 text errors, a C2 number error (`set: MCHC = 41.0`), a C1 text error, a C3 omission with `anchor_analyte: Platelets`, H5 omissions, a [fix] on clean H-016, a severity override with its reason on H-008, nine clean reports, every report verified — **met** [RAN; R1 checked the planted output].
4. Stand-in owner texts, an approved manifest, and a final taxonomy as a temporary copy, marked (" (rehearsal copy)" on one type per modality) so that its use is proven: the fake model checks the mark in every structured prompt, and `validate` is pointed at the copy — **met** [RAN].
5. plant; validate --expect 34 --expect-clean 9 --expect-dev 4 (each count also shown to fail when wrong); freeze; freeze --check — **met** [RAN].
6. Both scored runs with the fake client, every unit's outcome scripted: hits, misses (H-013; H-006 found in 1 of 3), a near-miss, duplicates, false alarms in planted reports (H-003, C-001) and in a clean one (H-016, 2 of 3 repeats), an unmapped category, a borderline overlap (0.4), an omission under another section, an invalid unit after two bad outputs, a unit valid on its second attempt — **met** [RAN].
7. map-list; an approved map; adjudicate prepare (the owner-facing files checked blind); the sheet filled; apply; score with OWNER_CONFIRMED True by monkeypatch only — **met** [RAN].
8. Every headline number equals the docstring's hand-worked value (recall per type and overall with Wilson intervals by formula, weighted recall, false alarms, specificity, Brier, ECE, consistency, differences, counts); freeze --check passes again and is shown to fail on a changed report; a second score is byte-identical; the drafts are byte-identical; nothing outside the temporary root is created, changed or removed, and the repository's .env, drafts, reports, specs, taxonomy and owner texts are never opened (audit-hook watch, paths only) — **met, with one deviation**: the three bootstrap intervals cannot be worked by hand (10,000 seeded resamples), so they are pinned at the scorer's values (Part 5) [RAN].
9. The same flow on the dev split without a freeze, with one adjudicated review item, an approved map, a byte-identical second score and every dev headline number asserted — **met** [RAN].
10. The rehearsal's summary.md in this record, marked as invented data — **met** (below).
11. Checks and commit — **met** [RAN].
12. No API call, no change outside the stage, owner files untouched, no new dependency, no test weakened — **met** [RAN; R3 each round].

#### Gate commands (final state, d09cc0e) [RAN]

- `uv run pytest` — exit 0 — 818 passed
- `uv run ruff check .` — exit 0 — All checks passed!
- `uv run ruff format --check .` — exit 0 — 58 files already formatted
- `uv run pytest tests/test_end_to_end.py -W error` — exit 0 — 2 passed

#### Review findings, triage and fixes

| round | finding | verdict | fix |
|---|---|---|---|
| 1 | The isolation check hashed every repository file, opening .env (a breach of A4 by the test itself; contents hashed only, never printed), the drafts, reports and owner texts (R3, R2) | CONFIRMED | Snapshot removed; an audit-hook watch that records paths only |
| 1 | Writes outside both the root and the repository, and empty folders, went unnoticed; the run could send the repository's owner texts (R2) | CONFIRMED | The watch; the fake model checks the stand-in owner text |
| 1 | Majority boundaries, the valid-unit denominator and intervals untested; blindness, freeze --check and validate checked only when passing; the dev flow shorter (R1, R2) | CONFIRMED | New scripted cases (H-006 1 of 3, H-016 2 of 3, C-001 beside its invalid repeat), intervals, negative checks, the full dev flow |
| 1 | ECE bins untested (all confidences 0.8) | REJECTED for the rehearsal | Covered by tests/test_stats.py (S6) |
| 2 | The watch recorded a link's source, not the link; it missed shutil.copy2 (_winapi.CopyFile2 on this Python), utime, chmod and the \\?\ and ::$DATA aliases (R2, R3) | CONFIRMED | Event table with read and write positions; aliases normalised |
| 2 | The taxonomy copy was never proven used; blindness was a word list; --expect-clean/--expect-dev not shown to bind; dev and per-type numbers not all asserted (R1, R2) | CONFIRMED | Marked copy and protected repository taxonomy; rationale check; negative checks; assertions |
| 3 | \\?\UNC\ became a relative path (a round-2 regression); \??\ not stripped; _winapi.CreateFile unwatched (R2) | CONFIRMED | Fixed; mutants K08–K10 killed by the watch (the files were written and caught) |
| 3 | 8.3 short names, UNC shares, folder listings, child processes, C-library access, junctions (R2, R3) | ACCEPTED as limits | Stated in the module docstring; the code under test uses none |
| 3 | Dev headline numbers not all worked by hand (R1) | CONFIRMED | Worked in the docstring and asserted |

Mutation checks (scratch copies of src/ and tests/): round 1, 12 mutants; round 2, 12 (one survivor, copy2, exposed the CopyFile2 gap; fixed and re-run); round 3, 3; all killed [RAN].

#### The rehearsal's summary.md (INVENTED DATA)

INVENTED DATA from a temporary tree in the test run (the scorer commit shows as "rehearsal"; the lock time is the test's clock). The disclosures paragraph is the scorer's fixed text and is not true here: these reports were not drafted by a model or corrected by the owner, no evaluated model was called (the fake client returned scripted outputs), and the review items were adjudicated by the test, not the owner.

```markdown
# Scores: scored split

Runs: plain scored-plain, structured scored-structured. Category map: approved, version 1.0. Lock created: 2026-11-11T14:39:09Z. Scorer commit: rehearsal.

## Per-type recall by condition

| | Plain | Structured |
|---|---|---|
| H1 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| H2 | 1/2 = 50.0% (95% CI 9.5%–90.5%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| H3 | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| H4 | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| H5 | 4/4 = 100.0% (95% CI 51.0%–100.0%) | 4/4 = 100.0% (95% CI 51.0%–100.0%) |
| H6 | 1/2 = 50.0% (95% CI 9.5%–90.5%) | 1/2 = 50.0% (95% CI 9.5%–90.5%) |
| C1 | 3/3 = 100.0% (95% CI 43.9%–100.0%) | 3/3 = 100.0% (95% CI 43.9%–100.0%) |
| C2 | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |
| C3 | 2/2 = 100.0% (95% CI 34.2%–100.0%) | 2/2 = 100.0% (95% CI 34.2%–100.0%) |

## Overall recall

| | Plain | Structured |
|---|---|---|
| Overall recall | 20/22 = 90.9% (95% CI 72.2%–97.5%) | 21/22 = 95.5% (95% CI 78.2%–99.2%) |

## False alarms per report

| | Plain | Structured |
|---|---|---|
| Planted reports | 0.07 (22 reports) | 0.00 (22 reports) |
| Clean controls | 0.08 (8 reports) | 0.00 (8 reports) |
| All | 0.07 (30 reports) | 0.00 (30 reports) |

## Specificity on clean controls

| | Plain | Structured |
|---|---|---|
| By majority | 7/8 = 87.5% | 8/8 = 100.0% |
| Per unit | 22/24 = 91.7% | 24/24 = 100.0% |

## Calibration

| | Plain | Structured |
|---|---|---|
| Brier score | 0.092 | 0.040 |
| ECE (5 bins) | 0.113 | 0.200 |
| Findings used | 69 | 66 |
| Left out: verdict miss or in review | 0 | 0 |
| Left out: no confidence | 0 | 0 |

## Repeat consistency

| | Plain | Structured |
|---|---|---|
| Planted errors detected: mean pairwise agreement | 97.0% (n=22) | 97.0% (n=22) |
| Planted errors detected: same result in every valid unit | 95.5% | 95.5% |
| Clean controls with any false alarm: mean pairwise agreement | 91.7% (n=8) | 100.0% (n=8) |
| Clean controls with any false alarm: same result in every valid unit | 87.5% | 100.0% |

## Severity-weighted recall

| | Plain | Structured |
|---|---|---|
| Severity-weighted recall | 41/47 = 87.2% | 44/47 = 93.6% |

## Structured minus plain

| Metric | Difference | 95% interval (paired bootstrap) |
|---|---|---|
| Overall recall | +4.5 pp | -10.0 pp to +20.0 pp |
| False alarms per report | -0.07 | -0.16 to +0.00 |
| Specificity (by majority) | +12.5 pp | +0.0 pp to +40.0 pp |

Reports in the paired comparison: 30; left out (no majority result in a condition): 0.

## Counts

| | Plain | Structured |
|---|---|---|
| Reports | 30 | 30 |
| Invalid units | 1 | 0 |
| Findings in valid units | 69 | 66 |
| False alarms | 6 | 0 |
| Near-misses | 3 | 1 |
| Duplicates | 0 | 3 |
| Review findings | 2 | 2 |
| Set aside by a verdict of miss | 0 | 0 |
| Still in review | 0 | 0 |
| Findings with a null confidence | 0 | 0 |
| Findings with a null severity | 0 | 0 |
| Dropped findings | 0 | 0 |
| Reports with no majority result | 0 | 0 |

Planted errors by type: H1 3, H2 2, H3 2, H4 2, H5 4, H6 2, C1 3, C2 2, C3 2.
Review items: 3 (detected 2, near_miss 1).

## Disclosures

The reports are synthetic: drafted by claude-haiku-5-5 and corrected by the owner. Sampling was the API default. One evaluated model was used; the API returned the model string claude-sonnet-5-5. 30 reports were scored (scored split). 3 review item(s) were adjudicated by hand by the owner, from a sheet that names no condition, repeat or model. A finding's category can still suggest its condition. results/scored/provisional/provisional_log.json records no provisional score made before every review finding had a verdict.
```

#### Files changed (d09cc0e)

```text
--- git status --short
A  tests/test_end_to_end.py
--- git diff --cached --stat
 tests/test_end_to_end.py | 702 +++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 702 insertions(+)
```

#### What was not tested

- The real API (S8 is the first contact); the owner's real reports, texts and verdicts.
- The watch's stated limits (child processes, C-library file access, junctions, 8.3 names, UNC shares, folder listings).

```text
=== EVAL REPORT: EVAL-05b End-to-end rehearsal (EVAL-N1 S7) ===
Status: DONE
What was asked: one test module rehearsing plant, validate, freeze, both runs with the fake client, map-list, blind adjudication and score on invented data, every headline number worked by hand, and the same flow on the dev split.
What was done: tests/test_end_to_end.py [RAN]; three review rounds, every confirmed finding fixed; 27 mutants across three checks, all killed [RAN]; no src change (no defect found) [RAN].
Files changed: tests/test_end_to_end.py (new).
Commands run: uv run pytest — 0 — 86 s — 818 passed; uv run ruff check . — 0; uv run ruff format --check . — 0.
Checks: pytest 818 passed, 0 failed | ruff check and format clean
Git: branch main; commit d09cc0e "EVAL-05b: end-to-end rehearsal"; push ok; remote HEAD matches local HEAD: yes
API spend this task: no API calls
Deviations from the prompt: the bootstrap intervals are pinned at the seeded scorer's values, not worked by hand (Part 5 item 12); the round-1 isolation check opened .env to hash it before review caught it (contents never printed; replaced).
Claims I could not verify: the watch's stated limits.
Questions for the owner: none new.
handoff.md updated: yes
=== END ===
```

## Part 8. Known weaknesses, and suggestions that were not acted on

1. S1: `plant` stops with a traceback when an existing report file is read-only (pre-existing; nothing is damaged because the open fails before any truncation). Suggestion: catch OSError per report in write_outputs and list it NOT WRITTEN.
2. S1: when a hand-edited draft's Values text does not match its numbers, the validator's advice names `render` on the unbuilt report path. Only reachable by editing a draft by hand (decision 37 forbids it).
3. S1: the test that plant.py's only writer is write_outputs inspects the source (named write calls, no os/shutil imports); a snapshot test checks behaviour on the draft-error paths.
4. Run procedure (S3 review R3 OF-4): until S3 the reviewers' instructions offered `$env:ANTHROPIC_API_KEY=''` for PowerShell, which in Windows PowerShell deletes the variable, so `cli.main`'s `load_dotenv` would load the key from `.env` into that process. No command the reviewers were allowed to run constructs a client, and data/drafts/_calls.jsonl shows no call other than the lead's (34 lines before S3, 38 after). From S3 on, reviewers run project code only in Git Bash with `ANTHROPIC_API_KEY= PYTHON_DOTENV_DISABLED=1`.
5. Since S4 the taxonomy is final, so `pathqc-eval plant` in its building form is no longer refused. Section A3 (nothing written under data/reports/ tonight) now rests on never running it on the repository: every later stage uses `plant --check` or a temporary tree, and the reviewers' rules forbid bare `plant` and writing `freeze` on the repository (S4 review R3 F1).
6. S5: a Ctrl+C still has two narrow gaps: a few bytecodes between starting a call and noting it as in flight, and a second Ctrl+C, which abandons the calls in flight (billed, not logged; they run again on resume and the gate's spend misses them). The README says so.
7. S5: every run folder keeps an empty, gitignored runs/<id>/.run.lock after the run.
8. S7: `pathqc-eval validate` always loads the repository's data/taxonomy.json (cli.py, load_taxonomy() with no path), even when it validates a folder elsewhere; the rehearsal points it at the temporary copy. Suggestion: take the taxonomy from the validated tree.
9. S7 (process): in review round 1, the rehearsal's own isolation check hashed every file in the repository, which opened .env (contents were only hashed, never printed or stored). R3 caught it; the check was replaced by an audit-hook watch that records paths only, and R3 confirmed with a suite-wide trace that no test opens .env.

## Part 9. EVAL report block

(Written at S9.)
