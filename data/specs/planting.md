# Planting sheet (decision 37, amended 2026-11-12). The owner chose every planted error. H-001, H-021, H-022 and C-011: written from the owner's own words. All other planted reports: the owner selected from candidate errors drafted by an AI assistant; he reads and verifies each built report.
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
# Errors: the owner's own, dictated on 2026-11-12.
[error]
type: H3
severity: critical
section: Synoptic summary
find: pT: pT2
replace: pT: pT1c
also_section: Diagnosis
also_quote: pT2 pN1a (AJCC 8th edition).
description: pT1c is given for a tumour of 32 mm; pT1c is for tumours of more than 10 mm and up to 20 mm.
rationale: The pT category must follow the tumour size; a tumour of this size is pT2.

[error]
type: H1
severity: major
section: Synoptic summary
find: Tumour size: 32 mm in greatest dimension
replace: Tumour size: 25 mm in greatest dimension
also_section: Gross description
also_quote: Left mastectomy specimen with a firm, ill-defined, grey-white tumour in the upper outer quadrant measuring 32 mm in greatest dimension.
also_section: Diagnosis
also_quote: 1. Invasive carcinoma of no special type, Nottingham grade 2, 32 mm in greatest dimension, with lymphovascular invasion.
description: The synoptic summary gives the tumour size as 25 mm; the gross description and the diagnosis give 32 mm.
rationale: The tumour size must be the same in every section of the report.

[error]
type: H4
severity: major
section: Synoptic summary
find: Lymph nodes (positive/total): 3/14
replace: Lymph nodes (positive/total): 4/14
also_section: Microscopic description
also_quote: Three of 14 axillary lymph nodes contain metastatic carcinoma.
also_section: Diagnosis
also_quote: 2. Metastatic carcinoma in 3 of 14 axillary lymph nodes, without extranodal extension.
also_section: Synoptic summary
also_quote: pN: pN1a
description: The synoptic summary gives 4 of 14 positive lymph nodes; the microscopy and the diagnosis give 3 of 14.
rationale: The node count must agree across sections; four positive nodes would also not fit pN1a.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[fix]
section: Gross description
find: The tumour extends to the serosal surface, which appears intact, with no adherent tissue.
replace: The serosal surface over the tumour appears intact, with no adherent tissue.
note: The draft's wording could read as serosal involvement, which the microscopy rules out (approved by the owner, 2026-11-12).

[error]
type: H1
severity: major
section: Gross description
find: Eighteen lymph nodes are identified in the mesentery, ranging from 3 mm to 15 mm.
replace: Fifteen lymph nodes are identified in the mesentery, ranging from 3 mm to 15 mm.
also_section: Microscopic description
also_quote: Two of 18 lymph nodes contain metastatic adenocarcinoma.
also_section: Synoptic summary
also_quote: Lymph nodes (positive/total): 2/18
description: The gross description counts fifteen lymph nodes; the microscopy and the synoptic summary count 18.
rationale: The number of lymph nodes found at grossing must agree with the number examined and reported.

[error]
type: H3
severity: critical
section: Synoptic summary
find: pN: pN1b
replace: pN: pN1a
also_section: Diagnosis
also_quote: - Metastatic adenocarcinoma in 2 of 18 regional lymph nodes (pN1b).
also_section: Comment
also_quote: pT3 pN1b corresponds to AJCC 8th edition stage group IIIB for carcinoma of the caecum.
description: pN1a is given although two regional lymph nodes are positive; two or three positive nodes is pN1b.
rationale: The pN category must follow the number of positive lymph nodes.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H5
severity: major
section: Synoptic summary
find: Margins: Circumferential resection margin 4 mm (clear); distal margin 25 mm (clear)
replace: Margins: Circumferential resection margin involved; distal margin 25 mm (clear)
also_section: Microscopic description
also_quote: Tumour lies 4 mm from the circumferential resection margin.
also_section: Diagnosis
also_quote: Circumferential and distal resection margins clear.
also_section: Comment
also_quote: Clear circumferential margin and absence of lymphovascular and perineural invasion are noted for multidisciplinary review.
description: The synoptic summary reports the circumferential resection margin as involved; the microscopy places tumour 4 mm from it and the diagnosis calls it clear.
rationale: Margin status must agree with the description; an involved circumferential margin changes management.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H2
severity: critical
section: Synoptic summary
find: Histologic grade: G2 (moderately differentiated)
replace: Histologic grade: G3 (poorly differentiated)
also_section: Microscopic description
also_quote: Sections show an intestinal-type adenocarcinoma with gland formation and moderate cytological atypia, classified as moderately differentiated.
also_section: Diagnosis
also_quote: - Intestinal-type adenocarcinoma of the antrum, moderately differentiated (G2), 50 mm, invading subserosal connective tissue without penetration of the visceral peritoneum (pT3).
description: The synoptic summary grades the tumour G3, poorly differentiated; the microscopy describes gland formation and a moderately differentiated tumour.
rationale: The stated grade must be supported by the microscopic description.

[error]
type: H3
severity: critical
section: Comment
find: pathological prognostic stage IIIA
replace: pathological prognostic stage IIB
quote: Assuming M0 on clinical assessment, this corresponds to pathological prognostic stage IIB under the AJCC 8th edition staging system for gastric carcinoma.
also_section: Comment
also_quote: The pathological stage is pT3 pN2.
also_section: Synoptic summary
also_quote: pT: pT3
also_section: Synoptic summary
also_quote: pN: pN2
description: The comment gives stage IIB for pT3 pN2; pT3 pN2 M0 is stage IIIA in AJCC 8th edition gastric staging.
rationale: The stage group must follow the pT and pN categories.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H5
severity: major
section: Synoptic summary
find: Perineural invasion: Present
replace: Perineural invasion: Not identified
also_section: Microscopic description
also_quote: Perineural invasion is present.
also_section: Diagnosis
also_quote: Perineural invasion present.
also_section: Comment
also_quote: Single involved ipsilateral node with a deposit of 18 mm and no extranodal extension, together with perineural invasion.
description: The synoptic summary says perineural invasion is not identified; the microscopy, the diagnosis and the comment say it is present.
rationale: Perineural invasion is a required element and its status must agree across the report.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H1
severity: major
section: Gross description
find: is present in the upper pole of the right lobe
replace: is present in the upper pole of the left lobe
quote: A firm, ill-defined, grey-white nodule measuring 2.4 cm in greatest dimension is present in the upper pole of the left lobe, 5 mm from the posterior surface.
also_section: Diagnosis
also_quote: Right thyroid lobe with isthmus, total thyroidectomy and central compartment neck dissection:
also_section: Microscopic description
also_quote: Surgical margins are free of tumour; the closest margin is 5 mm (posterior, right lobe).
also_section: Clinical details
also_quote: Right thyroid nodule with fine-needle aspiration reported as Bethesda category VI (malignant).
description: The gross description places the nodule in the left lobe; the clinical details, the microscopy and the diagnosis place the tumour in the right lobe.
rationale: The side of the tumour must be the same throughout the report.

[error]
type: H2
severity: critical
section: Diagnosis
find: Papillary thyroid carcinoma, classic subtype
replace: Papillary thyroid carcinoma, tall cell subtype
quote: 1. Papillary thyroid carcinoma, tall cell subtype, 24 mm, right lobe, confined to the thyroid without extrathyroidal extension (pT2).
also_section: Microscopic description
also_quote: Sections show a solitary tumour composed of papillae with fibrovascular cores, lined by cells with enlarged, overlapping, clear nuclei, nuclear grooves and intranuclear pseudoinclusions, consistent with classic papillary thyroid carcinoma.
also_section: Comment
also_quote: Classic papillary thyroid carcinoma with a single nodal metastasis in the central compartment.
description: The diagnosis gives the tall cell subtype; the microscopy describes the classic pattern and the comment calls the tumour classic.
rationale: The stated subtype must be supported by the microscopic description.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H1
severity: major
section: Diagnosis
find: Left kidney, radical nephrectomy
replace: Right kidney, radical nephrectomy
quote: Right kidney, radical nephrectomy: clear cell renal cell carcinoma, WHO/ISUP grade 2, 65 mm, confined to the kidney without invasion of renal sinus or perinephric fat (pT1b).
also_section: Specimen
also_quote: Left radical nephrectomy with perinephric fat and intact Gerota fascia.
also_section: Clinical details
also_quote: A 55-year-old man with an incidentally detected left renal mass, referred for radical nephrectomy.
description: The diagnosis names the right kidney; the clinical details and the specimen are a left radical nephrectomy.
rationale: The side of the specimen must be the same throughout the report.

[error]
type: H5
severity: minor
kind: omission
remove_from: Synoptic summary
remove: Lymphovascular invasion: Not identified
anchor: Perineural invasion: Not applicable
description: The synoptic summary has no line for lymphovascular invasion.
rationale: Lymphovascular invasion is a required element of the synoptic summary.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H4
severity: major
section: Microscopic description
find: All 12 pelvic lymph nodes are free of metastatic carcinoma.
replace: All 10 pelvic lymph nodes are free of metastatic carcinoma.
also_section: Gross description
also_quote: Twelve pelvic lymph nodes are identified, each measuring 5 to 15 mm, and are submitted entirely.
also_section: Synoptic summary
also_quote: Lymph nodes (positive/total): 0/12
also_section: Diagnosis
also_quote: - Zero of 12 pelvic lymph nodes involved (pN0).
description: The microscopy counts 10 pelvic lymph nodes; the gross description, the diagnosis and the synoptic summary count 12.
rationale: The node count in the text must agree with the synoptic count.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H5
severity: major
section: Synoptic summary
find: Margins: Clear (vaginal cuff and parametrial margins)
replace: Margins: Parametrial margin involved; vaginal cuff clear
also_section: Microscopic description
also_quote: The vaginal cuff and parametrial margins are free of tumour.
also_section: Diagnosis
also_quote: Margins clear.
description: The synoptic summary reports the parametrial margin as involved; the microscopy and the diagnosis say the margins are free.
rationale: Margin status must agree with the description; an involved parametrial margin changes management.

[error]
type: H3
severity: critical
section: Synoptic summary
find: pN: pN1
replace: pN: pN0
also_section: Diagnosis
also_quote: Metastatic squamous cell carcinoma in 2 of 20 lymph nodes (pN1).
also_section: Synoptic summary
also_quote: Lymph nodes (positive/total): 2/20
also_section: Microscopic description
also_quote: Two of 20 pelvic lymph nodes contain metastatic carcinoma.
description: pN0 is given although two of 20 pelvic lymph nodes contain metastatic carcinoma.
rationale: The pN category must follow the node findings.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[fix]
section: Synoptic summary
find: Margins: Clear; closest margin bronchial, 15 mm
replace: Margins: Clear; closest margin vascular, 12 mm
note: The gross description gives the vascular margin as nearer (12 mm) than the bronchial margin (15 mm) (approved by the owner, 2026-11-12).

[error]
type: H3
severity: critical
section: Diagnosis
find: Pathological stage group IA3 (AJCC 8th edition).
replace: Pathological stage group IB (AJCC 8th edition).
also_section: Diagnosis
also_quote: pT1c pN0 (0/9 lymph nodes), R0 resection.
also_section: Synoptic summary
also_quote: pT: pT1c
also_section: Synoptic summary
also_quote: pN: pN0
description: The diagnosis gives stage group IB for pT1c pN0; pT1c pN0 is stage IA3 in AJCC 8th edition.
rationale: The stage group must follow the pT and pN categories.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[fix]
section: Comment
find: The AJCC 8th edition does not provide a stage for lymphoma, so pT and pN are recorded as not applicable.
replace: Lymphomas are not staged by pT and pN, so these are recorded as not applicable.
note: AJCC 8th edition does cover lymphoma staging; the draft's sentence was inaccurate (approved by the owner, 2026-11-12).

[fix]
section: Comment
find: to determine whether the tumour is double-hit or double-expressor, which may influence management
replace: to exclude a double-hit lymphoma, which may influence management
note: Double-expressor status is shown by immunohistochemistry, not by FISH (approved by the owner, 2026-11-12).

[error]
type: H6
severity: critical
section: Immunohistochemistry
find: CD20: positive. PAX5: positive. CD3: negative.
replace: CD20: negative. PAX5: negative. CD3: positive.
description: The immunohistochemistry gives a T-cell profile (CD20 and PAX5 negative, CD3 positive); the diagnosis is a B-cell lymphoma.
rationale: The immunoprofile must support the diagnosis.

[error]
type: H6
severity: critical
section: Diagnosis
find: germinal centre B-cell-like phenotype (Hans algorithm)
replace: non-germinal centre B-cell-like phenotype (Hans algorithm)
quote: Diffuse large B-cell lymphoma, non-germinal centre B-cell-like phenotype (Hans algorithm).
also_section: Immunohistochemistry
also_quote: CD10: positive. BCL6: positive. MUM1: negative.
description: The diagnosis gives a non-germinal centre phenotype; CD10 is positive, which is germinal centre B-cell-like by the Hans algorithm.
rationale: The cell-of-origin statement must follow the immunoprofile.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H5
severity: major
section: Synoptic summary
find: Margins: Peripheral 4 mm clear; deep 3 mm clear
replace: Margins: Peripheral 4 mm clear; deep margin involved
also_section: Microscopic description
also_quote: The peripheral margin is clear at 4 mm and the deep margin is clear at 3 mm.
also_section: Diagnosis
also_quote: Peripheral and deep margins clear.
description: The synoptic summary reports the deep margin as involved; the microscopy and the diagnosis say it is clear at 3 mm.
rationale: Margin status must agree with the description; an involved deep margin changes management.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H2
severity: critical
section: Microscopic description
find: Focal acinar and papillary architecture is seen.
replace: No gland formation or mucin is seen, and the tumour cells show keratinisation and intercellular bridges.
also_section: Diagnosis
also_quote: Liver, ultrasound-guided core biopsy: metastatic poorly differentiated adenocarcinoma infiltrating liver parenchyma.
description: The microscopy describes squamous features (keratinisation, intercellular bridges, no gland formation); the diagnosis is adenocarcinoma.
rationale: The diagnosis must be supported by the microscopic description.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[fix]
section: Comment
find: is classified as intermediate risk
replace: is classified as low risk
note: Under Miettinen criteria a gastric tumour of 5.1 to 10 cm with 5 or fewer mitoses is low risk (approved by the owner, 2026-11-12).

[error]
type: H1
severity: major
section: Diagnosis
find: Stomach, gastric body, laparoscopic wedge resection:
replace: Stomach, gastric antrum, laparoscopic wedge resection:
also_section: Clinical details
also_quote: 54-year-old woman with a submucosal mass of the gastric body.
description: The diagnosis places the tumour in the gastric antrum; the clinical details place the mass in the gastric body.
rationale: The site of the tumour must be the same throughout the report.

[error]
type: H6
severity: critical
section: Immunohistochemistry
find: Tumour cells show diffuse strong positivity for CD117 and DOG1 and are positive for CD34. Desmin, S100 and smooth muscle actin are negative.
replace: Tumour cells are negative for CD117 and DOG1 and are positive for CD34. Desmin and smooth muscle actin are diffusely positive; S100 is negative.
also_section: Diagnosis
also_quote: Gastrointestinal stromal tumour (GIST), spindle cell type, 55 mm, mitotic count 3 per 5 mm2.
description: The immunohistochemistry gives a smooth muscle profile (CD117 and DOG1 negative, desmin and smooth muscle actin positive); the diagnosis is gastrointestinal stromal tumour.
rationale: The immunoprofile must support the diagnosis.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: H4
severity: major
section: Synoptic summary
find: Lymph nodes (positive/total): 0/2 (sentinel)
replace: Lymph nodes (positive/total): 0/3 (sentinel)
also_section: Gross description
also_quote: B. Two lymph nodes, measuring 9 mm and 7 mm, grey-pink and rubbery.
also_section: Microscopic description
also_quote: B. Both sentinel lymph nodes are free of metastatic carcinoma on haematoxylin and eosin sections.
also_section: Diagnosis
also_quote: B. Sentinel lymph nodes (2): no metastatic carcinoma (0/2).
description: The synoptic summary counts three sentinel lymph nodes; the gross description, the microscopy and the diagnosis count two.
rationale: The node count in the synoptic summary must agree with the text.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
section: Interpretation
find: Severe microcytic hypochromic anaemia is present
replace: Severe normocytic normochromic anaemia is present
quote: Severe normocytic normochromic anaemia is present, with haemoglobin 6.2 g/dL, haematocrit 22.1% and red cell count 3.56 x10^12/L.
also_analyte: MCV
also_analyte: MCH
also_section: Interpretation
also_quote: The low mean cell volume and mean cell haemoglobin, together with the raised red cell distribution width, indicate marked anisocytosis and a pattern consistent with iron deficiency.
description: The interpretation calls the anaemia normocytic and normochromic; MCV is 62.1 fL and MCH is 17.4 pg, both low.
rationale: The interpretation must agree with the red cell indices.

[error]
type: C3
severity: critical
kind: omission
remove_section: Comment/recommendation
anchor_analyte: Hb
description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
rationale: A critical value needs a flag and a recommendation for urgent review.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
section: Interpretation
find: Platelet count is within the reference range.
replace: Platelet count is markedly reduced.
also_analyte: Platelets
description: The interpretation says the platelet count is markedly reduced; the count is 152, within the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C2
severity: minor
set: Neutrophils_pct = 22.0
also_analyte: Neutrophils_abs
description: Neutrophils are given as 22 percent; the differential then adds up to 110 and does not fit the absolute neutrophil count.
rationale: The differential must add up to 100 and each absolute count must follow from the percentage and the white cell count.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
set: Platelets = 120
also_section: Interpretation
also_quote: Platelet count is severely reduced at 12 x10^9/L, with a raised mean platelet volume of 11.8 fL, indicating increased platelet turnover or peripheral destruction rather than a primary marrow failure pattern.
also_section: Comment/recommendation
also_quote: CRITICAL VALUE: Platelet count 12 x10^9/L.
description: The Values give a platelet count of 120; the interpretation and the comment speak of a count of 12.
rationale: The interpretation must agree with the numbers.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[fix]
section: Interpretation
find: Marked normocytic-to-macrocytic anaemia is present
replace: Marked anaemia is present
note: An MCV of 118 fL is macrocytic; the draft's "normocytic-to-macrocytic" could read as a contradiction (approved by the owner, 2026-11-12).

[error]
type: C1
severity: major
section: Interpretation
find: The MCHC is within the normal range, and the RDW is raised, consistent with anisocytosis.
replace: The MCHC is within the normal range, and the RDW is normal, with no anisocytosis.
also_analyte: RDW
description: The interpretation says the RDW is normal; the RDW is 18.5, above the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C1
severity: major
section: Interpretation
find: Mild leukopenia and mild thrombocytopenia accompany the anaemia
replace: A normal white cell count and platelet count accompany the anaemia
quote: A normal white cell count and platelet count accompany the anaemia, a pattern that, together with the strict vegetarian diet, fatigue, paraesthesia and glossitis, is suggestive of vitamin B12 deficiency.
also_analyte: WBC
also_analyte: Platelets
description: The interpretation says the white cell count and platelet count are normal; WBC is 3.20 and platelets are 110, both below the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C2
severity: major
set: MCH = 29.0
also_analyte: Hb
also_analyte: RBC
description: MCH is given as 29.0 pg; Hb 7.8 g/dL and RBC 2.00 give 39.0 pg.
rationale: MCH must follow from Hb and RBC.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
section: Interpretation
find: This is severe neutropenia.
replace: This is mild neutropenia.
quote: This is mild neutropenia.
also_analyte: Neutrophils_abs
description: The interpretation calls the neutropenia mild; the absolute neutrophil count is 0.20, which is severe.
rationale: The interpretation must agree with the numbers.

[error]
type: C3
severity: critical
kind: omission
remove_section: Comment/recommendation
anchor_analyte: Neutrophils_abs
description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
rationale: A critical value needs a flag and a recommendation for urgent review.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
section: Interpretation
find: Haemoglobin, red cell indices and red cell distribution width are within the reference range, indicating no anaemia.
replace: Haemoglobin is reduced with low red cell indices, indicating a microcytic anaemia.
also_analyte: Hb
also_analyte: MCV
description: The interpretation reports a microcytic anaemia; Hb is 14.5 and MCV is 87.8, both within the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C1
severity: major
section: Interpretation
find: The platelet count and mean platelet volume are normal.
replace: The platelet count is raised, in keeping with a reactive thrombocytosis.
also_analyte: Platelets
description: The interpretation says the platelet count is raised; the count is 245, within the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C2
severity: major
set: Neutrophils_abs = 6.00
also_analyte: Neutrophils_pct
also_analyte: WBC
also_section: Interpretation
also_quote: Marked neutrophilic leucocytosis with a neutrophil fraction of 86 per cent and relative lymphopenia, a pattern consistent with acute bacterial infection in the context of four days of fever and productive cough.
description: The absolute neutrophil count is given as 6.00; 86 percent of a white cell count of 18.60 is 16.00.
rationale: Each absolute count must follow from the percentage and the white cell count.

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
# Errors: selected by the owner on 2026-11-12 from candidate errors drafted by an AI assistant.
[error]
type: C1
severity: major
section: Interpretation
find: The red-cell indices are within reference limits, consistent with a normocytic and normochromic red-cell population.
replace: The red-cell indices are reduced, consistent with a microcytic and hypochromic red-cell population.
also_analyte: MCV
also_analyte: MCH
also_analyte: MCHC
description: The interpretation says the red-cell indices are reduced; MCV, MCH and MCHC are all within the reference range.
rationale: The interpretation must agree with the numbers.

[error]
type: C1
severity: major
set: Platelets = 250
also_section: Interpretation
also_quote: Mild leucocytosis with neutrophil predominance and thrombocytosis, together with headache, plethoric facies and pruritus after bathing, raise suspicion of a myeloproliferative neoplasm such as polycythaemia vera, although secondary causes of erythrocytosis must be excluded.
description: The Values give a platelet count of 250, within the reference range; the interpretation speaks of thrombocytosis.
rationale: The interpretation must agree with the numbers.

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
