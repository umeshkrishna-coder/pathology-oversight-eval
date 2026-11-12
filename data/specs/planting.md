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
# scored | planted | planned types: H1, H3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-002.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-003 ==
# scored | planted | planned types: H4, H5
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H4
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-003.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-004 ==
# scored | planted | planned types: H2, H3, H4
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H2
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-004.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-005 ==
# scored | planted | planned types: H3, H5
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H3
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-005.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-006 ==
# scored | planted | planned types: H1, H2
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-006.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-007 ==
# scored | planted | planned types: H1, H5
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-007.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-008 ==
# scored | planted | planned types: H2, H4
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H2
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-008.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-009 ==
# scored | planted | planned types: H3, H5
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H3
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-009.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-010 ==
# scored | planted | planned types: H1, H3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-010.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-011 ==
# scored | planted | planned types: H2, H6
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H2
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-011.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-012 ==
# scored | planted | planned types: H1, H5, H6
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-012.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-013 ==
# scored | planted | planned types: H2, H6
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H2
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-013.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-014 ==
# scored | planted | planned types: H1, H5, H6
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-014.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-015 ==
# scored | planted | planned types: H4, H6
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: H4
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/H-015.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== H-016 ==
# scored | clean control | planned types: none
verified: no

== H-017 ==
# scored | clean control | planned types: none
verified: no

== H-018 ==
# scored | clean control | planned types: none
verified: no

== H-019 ==
# scored | clean control | planned types: none
verified: no

== H-020 ==
# scored | clean control | planned types: none
verified: no

== H-021 ==
# dev | planted | planned types: H3, H6
verified: yes
verified_on: 2026-11-11
[error]
type: H3
severity: critical
section: Synoptic summary
find: pT: pT1b
replace: pT: pT2
also_section: Diagnosis
also_find: (pT1b)
also_replace: (pT2)
description: the higher stage has been wrongly given.
rationale: it changes the treatment modality of the patient.

== H-022 ==
# dev | planted | planned types: H4, H5
verified: yes
verified_on: 2026-11-11
[error]
type: H4
severity: major
section: Microscopic description
find: Metastatic carcinoma is identified in 3 of 17 regional lymph nodes.
replace: Metastatic carcinoma is identified in 8 of 17 regional lymph nodes.
also_section: Synoptic summary
also_quote: Lymph nodes (positive/total): 3/17
also_section: Diagnosis
also_quote: - Metastatic carcinoma in 3 of 17 regional lymph nodes (pN1).
description: the number of positive lymph nodes does not match.
rationale: lymph node status is vital in determining the treatment modalities.

[error]
type: H2
severity: critical
section: Synoptic summary
find: Histologic grade: G2, moderately differentiated
replace: Histologic grade: G2, poorly differentiated
also_section: Diagnosis
also_quote: - Moderately differentiated ductal adenocarcinoma of the pancreatic head, 26 mm (pT2).
description: the histologic grade does not match.
rationale: histologic grading is vital in determining the treatment modalities.

== H-023 ==
# dev | clean control | planned types: none
verified: yes
verified_on: 2026-11-11

== C-001 ==
# scored | planted | planned types: C1, C2, C3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-001.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-002 ==
# scored | planted | planned types: C1, C2
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-002.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-003 ==
# scored | planted | planned types: C1, C3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-003.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-004 ==
# scored | planted | planned types: C1, C2
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-004.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-005 ==
# scored | planted | planned types: C2, C3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C2
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-005.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-006 ==
# scored | planted | planned types: C1, C2
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-006.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-007 ==
# scored | planted | planned types: C1, C3
verified: no
# Example (delete the leading '# ' on each line to use it):
# [error]
# type: C1
# severity: <critical, major or minor>
# section: <section name>
# find: <text copied exactly from data/drafts/_readable/C-007.md>
# replace: <the text as it should read with the error>
# description: <what is wrong>
# rationale: <why it is an error>

== C-008 ==
# scored | clean control | planned types: none
verified: no

== C-009 ==
# scored | clean control | planned types: none
verified: no

== C-010 ==
# scored | clean control | planned types: none
verified: no

== C-011 ==
# dev | planted | planned types: C1
verified: yes
verified_on: 2026-11-11
[error]
type: C2
severity: major
set: Hct = 20.0
also_section: Interpretation
also_quote: The haematocrit of 48% sits at the upper end of the adult male reference range, with haemoglobin of 16.0 g/dL, which is consistent with haemoconcentration from plasma leakage rather than true polycythaemia.
description: hct value is wrong as 20.
rationale: it doesn't add up with other parameters.
