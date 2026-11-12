# Pathology Report Oversight Pilot (`pathology-oversight-eval`) — Fact Sheet & Write-Up

**Date:** 12 November 2026  
**Author:** Dr. Umesh Krishna Sureshbabu, MD (Pathology) (`@umeshkrishna-coder`)  
**Repository:** `umeshkrishna-coder/pathology-oversight-eval` (branch `main`; results as of commit `5c0d012`)  
**Purpose:** Verified fact sheet and write-up of the pilot for the Anthropic Research Residency application

## 1. The Question

**Does giving Claude Sonnet 5.5 a short, structured review checklist and an error list (taxonomy) help it catch mistakes planted in pathology reports better than a simple *"find every error"* instruction?**

Before a pathology report is signed out, a pathologist checks that the numbers, descriptions, staging, and final diagnosis all line up. This pilot tests how an AI model performs on that pre-signout check under two different instructions, measuring three practical things:

1. **Errors caught (Recall):** How many of the planted mistakes each prompt finds.
2. **False alarms:** How many extra flags each prompt raises that are not actual planted mistakes.
3. **Clean-report accuracy (Specificity):** How often each prompt leaves a mistake-free report alone without raising false alarms.

## 2. How the Pilot Worked (Method in Five Steps)

* **Synthetic dataset (34 reports, zero real patient data):** `claude-haiku-5-5` (high effort) drafted 34 synthetic pathology reports from clinical briefs proposed by the coding agent and approved by the pathologist—23 surgical histopathology reports (`H-001` to `H-023`) and 11 complete blood count (CBC) reports (`C-001` to `C-011`). The pathologist reviewed and corrected every draft before locking the dataset. Four reports (`H-021` to `H-023`, `C-011`) were used only to test the pipeline in a preliminary dev run. The remaining **30 reports** formed the final scored set: **22 reports with planted errors** (15 histopathology, 7 blood counts) and **8 clean control reports** with no errors at all (5 histopathology, 3 blood counts).
* **Planted errors (39 total across 9 error types):** The 22 error-containing reports held **39 planted mistakes** (1 to 3 per report) spread across 9 clinical categories (`H1`–`H6` for histopathology, `C1`–`C3` for blood counts). By clinical impact, **13 were critical** (would change patient treatment), **24 were major** (would require an amended report), and **2 were minor** (internal mismatch with no clinical harm). Thirty-six were direct contradictions between two parts of a report, while **3 were omissions** where a required synoptic line (`H-007`) or a critical-value warning comment (`C-001`, `C-005`) was removed.
* **Two prompts compared:**
  * **Plain prompt:** Asks the model to read the report and *"identify every error you can find in it"* without rewriting the report, returning a JSON list of findings (quoted sentence, section name, a short free-text label in its own words, severity, a 0–1 confidence score, and a brief reason).
  * **Structured prompt:** Gives the pathologist's own short review checklist for that report type, the error table for that report type with severity definitions (six types, `H1`–`H6`, for histopathology; three types, `C1`–`C3`, for blood counts), and the exact same JSON output format—except the label must be one of that report type's error codes or `"other"`.
* **Model, hash freeze, and test runs:** Only `claude-sonnet-5-5` was tested, using standard API default settings (max output 16,000 tokens) in a single scored run. Before the scored run started, the prompts, error taxonomy, and all 34 reports were locked with cryptographic SHA-256 hashes (`data/prompts.lock.json`, dataset hash `caf11ddc290b592a46de915d73d5ab2673cfbccf58ff576e1806404852431f2a`). Each of the 30 scored reports was read **3 times under each prompt** (**180 API calls in total**). Every call returned valid JSON on the first attempt with zero retries.
* **Scoring and blind manual judging:**
  * **Detections:** For the 36 statement contradictions, a finding counted as a detection if it named the right section and quoted either the planted error sentence or its matching contradiction partner in the report (with at least 60% word overlap). The model's category label was ignored when scoring detections. An error counted as **found** if at least **2 out of 3 repeats** detected it.
  * **Duplicates:** Flagging the same planted error twice in a single reading counted as a duplicate—neither an extra detection nor a false alarm.
  * **Blind judging (25 items):** Because deleted lines leave no text to quote—and some findings had borderline word overlap (40%–60% in the right section, or ≥60% in another section)—**25 findings** (16 omission candidates and 9 borderline items) were judged by hand by the pathologist without knowing which prompt produced them.
  * **False alarms:** Every other finding—including any flag raised on one of the 8 error-free reports—counted as a false alarm. A clean report passed a reading if it had zero false alarms, and passed by majority if at least **2 out of 3 readings** were completely clean.

### Error Categories and Recall by Type

| Code | What the Error Means | Default Severity | Planted | Found (Plain) | Found (Structured) |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **H1** | **Gross–microscopic mismatch:** Size, node count, side (left/right), or site in the gross description conflicts with microscopy or synoptic summary | Major | 5 | 5 / 5 | 5 / 5 |
| **H2** | **Diagnosis unsupported by morphology:** Microscopic description does not match the stated tumor subtype or grade | Critical | 3 | 3 / 3 | 3 / 3 |
| **H3** | **Staging inconsistency:** Pathologic stage (`pT`/`pN` or stage group) conflicts with tumor size, invasion depth, or positive node count | Critical | 5 | 5 / 5 | 5 / 5 |
| **H4** | **Node arithmetic error:** Positive lymph nodes exceed total nodes, or node counts in the text and synoptic summary disagree | Major | 3 | 3 / 3 | 3 / 3 |
| **H5** | **Required element missing or contradictory:** Margin status, lymphovascular invasion (LVI), or perineural invasion (PNI) is missing or contradicts the text | Major / Minor | 5 | 4 / 5 | 4 / 5 |
| **H6** | **IHC–diagnosis inconsistency:** Immunohistochemistry stain results contradict the final diagnosis or cell lineage | Critical | 3 | 3 / 3 | 3 / 3 |
| **C1** | **Value–interpretation mismatch:** Written blood count interpretation contradicts the printed lab numbers | Major | 10 | 10 / 10 | 10 / 10 |
| **C2** | **Derived-index inconsistency:** Red cell indices (MCV, MCH, MCHC) conflict with Hb/RBC/Hct, white cell differential does not add up to 100%, or absolute count conflicts with total WBC | Minor / Major | 3 | 3 / 3 | 3 / 3 |
| **C3** | **Missed critical finding:** A life-threatening lab value has no critical warning flag, comment, or urgent action note | Critical | 2 | 0 / 2 | 2 / 2 |
| **Total** | **All scored planted errors** | **13 Crit / 24 Maj / 2 Min** | **39** | **36 / 39 (92.3%)** | **38 / 39 (97.4%)** |

## 3. Results

**Main takeaway:** The structured prompt cut false alarms to less than a third of the plain prompt's rate and passed every single error-free control report, while recall on planted errors was high under both prompts (92.3% and 97.4%).

### Headline Performance (30 Scored Reports, 180 API Calls)

| Measure | Plain Prompt | Structured Prompt | Difference (95% Confidence Interval) |
| :--- | :---: | :---: | :---: |
| **Planted errors found (of 39)** | 36 / 39 (92.3%) | 38 / 39 (97.4%) | +5.1 points (0.0 to +12.8) |
| **False alarms per report (all 30 reports)** | 1.38 | 0.43 | −0.94 (−1.33 to −0.62) |
| **False alarms per report (22 planted reports)** | 1.48 | 0.55 | — |
| **False alarms per report (8 clean controls)** | 1.08 | 0.12 | — |
| **Clean controls passed by majority (of 8)** | 2 / 8 (25.0%) | 8 / 8 (100.0%) | +75.0 points (+40.0 to +100.0) |
| **Clean-control readings with no finding (of 24)** | 6 / 24 (25.0%) | 22 / 24 (91.7%) | — |
| **Critical errors found (of 13)** | 11 / 13 (84.6%) | 13 / 13 (100.0%) | — |
| **Major errors found (of 24)** | 24 / 24 (100.0%) | 24 / 24 (100.0%) | — |
| **Minor errors found (of 2)** | 1 / 2 (50.0%) | 1 / 2 (50.0%) | — |
| **Severity-weighted recall (weights 3, 2, 1)** | 82 / 89 (92.1%) | 88 / 89 (98.9%) | — |
| **Brier score of stated confidence (lower is better)** | 0.103 | 0.067 | — |
| **Expected calibration error (5 bins)** | 0.159 | 0.071 | — |
| **Repeat consistency on planted errors (pairwise)** | 98.3% | 96.6% | — |
| **Repeat consistency on clean controls (pairwise)** | 83.3% | 83.3% | — |
| **Label matched planted error type** | N/A (146 free-text labels) | 124 / 128 (96.9%; 10 labels) | — |
| **Total findings / False alarms / Duplicates** | 263 / 124 / 23 | 168 / 39 / 14 | — |

### What the Numbers Actually Support

* **False alarms and clean-report performance improved sharply:** Both 95% confidence intervals exclude zero. Across all 30 reports, the structured prompt reduced false alarms from **1.38 to 0.43 per report** (124 total false alarms down to 39). On the 8 error-free control reports, the plain prompt raised at least one false alarm on 7 of the 8 reports and failed 6 of them by majority (passing only 2/8 by majority, or 6/24 individual readings), whereas the structured prompt passed **all 8 clean controls by majority** (22/24 individual readings completely clean).
* **Overall recall did not differ clearly because both prompts hit a ceiling:** Both prompts caught **all 36 direct statement contradictions in every single repeat (3/3)**. Because both prompts maxed out on direct contradictions, the 5.1-point overall recall difference has a confidence interval that starts at zero (`0.0 to +12.8`).
* **The two-error recall gap comes down to missing critical-value warnings (`C3`):** In two blood count reports—`C-001` (hemoglobin `6.2 g/dL`) and `C-005` (neutrophil count `0.20 × 10⁹/L` after chemotherapy)—the critical-value warning comment had been deleted. The plain prompt missed both (0/3 repeats each), while the structured prompt caught both (`2/3` in `C-001` and `3/3` in `C-005`). Both were evaluated by hand during blind judging.
* **One omission was missed by both prompts:** In kidney report `H-007`, the lymphovascular invasion (LVI) line was deleted from the synoptic summary (`H5`, minor). Both prompts caught it in only 1 of 3 repeats, falling short of the 2-of-3 detection rule.
* **Consistent error labeling:** Under the structured prompt, the model's chosen code matched the true planted error category in **124 of 128 detections and duplicates (96.9%)** using only the taxonomy codes and `"other"` (10 labels in all). Under the plain prompt, the model invented **146 different free-text labels**.
* **Preliminary dev run (4 reports, not part of scored set):** Both prompts found 4 of 4 planted errors and passed the clean control (`H-023`), with 0.92 false alarms per report under the plain prompt and 0.58 under the structured prompt (and 15/19 label matches).
* **Low API cost:** Running the 180 scored evaluations cost **$2.04** ($0.99 plain, $1.05 structured; 106,632 input / 77,513 output tokens for plain and 135,582 input / 77,891 output tokens for structured). The entire project—including drafting all 34 reports ($0.05), the 4-call smoke test ($0.04), the dev runs ($0.26), and the scored runs ($2.04)—cost **$2.39** ($2.394846) in API calls.

## 4. Key Facts on How the Pilot Was Built and Run

Every item below records a concrete design choice from the project log (`handoff.md`):

1. **How the planted errors were chosen:** Candidate errors were drafted by an AI assistant; the pathologist selected and verified every one. Specifically, the pathologist chose the errors for `H-001` and the three planted dev reports (`H-021`, `H-022`, `C-011`) in his own words; for the remaining 21 planted reports, the orchestrator drafted four candidate options per report on unranked question cards, and the pathologist chose and verified 1 to 3 errors per report (plus adding two `C2` and two `C3` errors to ensure every error category was tested, and dropping one overlapping WBC error in `C-007`).
2. **Who drafted and fixed the reports:** All 34 reports are completely synthetic, drafted by `claude-haiku-5-5` from clinical briefs that the coding agent proposed and the pathologist approved, and checked by the pathologist. Four reports (`H-009`, `H-021`, `C-008`, `C-009`) were re-drafted on 11 November with tighter instructions, and **eight drafting slips** (`[fix]` entries in `H-002`, `H-010`, `H-011`, `H-014`, `H-019`, `H-020`, `C-004`) were found by the orchestrator, approved for correction by the pathologist and corrected before the freeze.
3. **What counted as a detection:** A finding counted as a detection when it quoted the planted error sentence—or a pre-listed contradiction partner sentence elsewhere in the report—inside the right section (≥60% word overlap). After the dev run showed the plain prompt inventing 19 different free-text labels across just 4 reports, the scoring rule was updated before the freeze so that category labels were never used to decide whether an error was caught.
4. **What counted as a false alarm:** Any finding that was not a detection of a planted error (excluding duplicate detections and items set aside or marked near-misses in blind judging). False alarms were counted automatically by rule and were not reviewed one by one.
5. **How blind judging worked:** The pathologist manually judged **25 findings** (16 omission candidates and 9 borderline-overlap items) without knowing which prompt, run, repeat, or label produced them. An AI assistant that was also blinded to the prompt grouped identical findings onto **12 question cards** (yielding 7 detections [1 plain, 6 structured], 2 near-misses on PNI wording in `H-007` [2 plain], 6 false alarms [6 plain], and 10 set-aside fair remarks [9 plain, 1 structured]). On **four cards**, the assistant asked the pathologist to take a second look because a verdict did not match the finding's wording or conflicted with an earlier ruling on the same type of finding, and the pathologist updated those verdicts himself.
6. **One late typo fix before the freeze:** A typing slip in the blood count review instruction (`"rbs's"` instead of `"RBC's"`) was spotted after the dev run and fixed before the cryptographic freeze locked the files for the scored run.
7. **How the code pipeline was built:** The evaluation harness, validator, and scorer (1,018 passing unit tests) were written with **Claude Code** on the pathologist's PC under his direction, while a **second Claude session** acted as orchestrator—auditing each step against the repository, presenting decision cards, and independently recounting the final numbers from the raw logs.
8. **Single model, default settings:** Only `claude-sonnet-5-5` was evaluated, at default API sampling settings, in a single scored run after the hash freeze.

## 5. Limits (What This Pilot Cannot Claim)

* **Ceiling on recall for direct contradictions:** Most planted errors were clear, head-on contradictions between two sections (such as 32 mm vs. 25 mm tumor size, or left vs. right kidney), and both prompts found all 36 of them every single time (3/3). Because both prompts hit 100% on statement errors, this pilot cannot tell which prompt is better at catching subtle clinical mistakes.
* **The recall difference rests on just two errors:** The gap between 36/39 (92.3%) and 38/39 (97.4%) comes entirely from two errors of the same type (`C3`, missing critical-value comments in blood counts), both scored by hand. Treat this recall edge as a useful hint, not proof.
* **"False alarm" does not always mean the model was wrong:** Because false alarms were counted automatically against the list of planted errors, some findings counted as false alarms were actually reasonable observations about the synthetic drafts. For example, when uncommented high basophil counts came up on the blind judging cards (`C-002`, `C-006`, `C-007`), the pathologist set those 9 items aside as fair clinical remarks rather than false alarms (a tenth set-aside item concerned platelet grading in `C-005`).
* **A dataset formatting quirk hurt the plain prompt:** The synthetic blood count reports did not have a separate "Clinical details" section, even when the written interpretation mentioned clinical context (such as post-chemotherapy status). As a result, the plain prompt flagged *"clinical history not shown"* **17 times** across the blood count runs, while the structured prompt did so only **once**.
* **The two prompts differ in scope as well as structure:** The plain prompt asks the model to find *"every error,"* while the structured prompt gives a focused checklist of the error types for that report type (six for histopathology, three for blood counts). The big drop in false alarms likely comes partly from narrowing what the model is asked to look for, not just from formatting the prompt as a taxonomy.
* **Most false alarms carried low confidence (exploratory count):** Looking at the raw output after the run, **91 of the 124 plain false alarms** (and **35 of the 39 structured false alarms**) had a model-stated confidence below `0.5`, and 95 of the 124 plain false alarms were labeled `"minor"` by the model. Filtering out low-confidence flags would shrink the false-alarm gap in absolute terms (33 plain against 4 structured at confidence 0.5 or above), though this was not a pre-planned test measure.
* **Claude-assisted synthetic data and errors:** Because `claude-haiku-5-5` drafted the reports and a Claude session helped draft candidate errors for the pathologist to pick from, these errors may be unusually easy (or unusually hard) for `claude-sonnet-5-5` to spot compared with real-world human dictation errors.
* **Location-based automated scoring:** For statement errors, the scorer checks whether a finding quotes the right sentence in the right section. If a model quoted a planted sentence for the wrong reason, the automated rule would still count it as a detection.
* **Small, single-pathologist pilot:** The study covers 30 scored reports, 39 planted errors, one model (`claude-sonnet-5-5`), one scored run, and one pathologist who served as both ground-truth author and blind judge.

## 6. Where Every Figure Comes From (Repository Map)

All results are stored in `umeshkrishna-coder/pathology-oversight-eval` (branch `main`, commit `5c0d012`). The orchestrator independently recounted both scored runs with separate verification code, and every headline figure matched `results/scored/summary.md`.

| What to Verify | File Path in Repository |
| :--- | :--- |
| Headline comparison table, per-type recall, confidence intervals, and counts | `results/scored/summary.md` |
| Every individual model finding, outcome classification, and per-repeat error score | `results/scored/score.json` |
| The 25 blind adjudication items, pathologist verdicts, and written reasons | `results/scored/adjudication/adjudication_sheet.md` |
| Prompt origin for each judged item (unsealed only after all verdicts were locked) | `results/scored/adjudication/adjudication_hidden.json` |
| All planted errors, contradiction partner locations, and `[fix]` draft corrections | `data/specs/planting.md` |
| The plain and structured prompt templates and the 9-type error taxonomy | `prompts/`, `data/taxonomy.json` |
| Cryptographic SHA-256 freeze lock across prompts, taxonomy, and all 34 reports | `data/prompts.lock.json` |
| Per-reading results for all 180 scored calls (every finding as parsed, tokens and cost); the raw call logs are kept locally and are not in the repository | `runs/20261112-153246-scored-plain/`, `runs/20261112-153532-scored-structured/` |
| Preliminary 4-report dev run results | `results/dev/summary.md` |
| Chronological register of all 78 project decisions and audit checks | `handoff.md` |

*Note on exploratory counts:* The low-confidence false alarm counts (`91/124` plain and `35/39` structured below `0.5` confidence) and the *"clinical history not shown"* count (`17` plain vs. `1` structured) were tallied directly from `results/scored/score.json` and the raw run logs after scoring; they are labeled exploratory because they are not part of `results/scored/summary.md`.
