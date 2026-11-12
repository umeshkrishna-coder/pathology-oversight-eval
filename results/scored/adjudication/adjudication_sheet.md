# Blind adjudication sheet. Lines starting with # are comments.
# For each item, fill in two lines:
#   verdict: detected | miss | near_miss | false_alarm
#   reason: your reason in a few words (required with a verdict)
# detected: the finding is the candidate planted error; near_miss: right sentence, wrong kind
# of error; false_alarm: the finding is not a real error; miss: set the finding aside (neither
# a detection nor a false alarm). Then run `pathqc-eval adjudicate apply --dataset scored`.

== A001 ==
# report: H-007
# section: Synoptic summary
# quoted sentence: Perineural invasion: Not applicable
# rationale: Perineural invasion is not assessed anywhere in the microscopic description, so 'Not applicable' is inconsistent. Lymphovascular invasion, which was assessed, is missing from the synoptic summary.
# candidate planted error: H-007-E2 (H5, omission) in Synoptic summary
#   its quoted sentence: Perineural invasion: Not applicable
#   its description: The synoptic summary has no line for lymphovascular invasion.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the lymphovascular invasion line is missing from the synoptic summary

== A002 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count of 0.19 exceeds the stated upper limit of 0.10, yet the interpretation does not address it. It is also high relative to a basophil fraction of 1%, so either the reference range or the value looks wrong.
# candidate planted error: C-006-E3 (C2, statement) in Values
#   its quoted sentence: Neutrophils absolute: 6.00 x10^9/L (ref 2.00–7.00)
#   its other place 1: Values: Neutrophils %: 86.0 % (ref 40.0–80.0)
#   its other place 2: Values: WBC: 18.60 x10^9/L (ref 4.00–10.00)
#   its other place 3: Interpretation: Marked neutrophilic leucocytosis with a neutrophil fraction of 86 per cent and relative lymphopenia, a pattern consistent with acute bacterial infection in the context of four days of fever and productive cough.
#   its description: The absolute neutrophil count is given as 6.00; 86 percent of a white cell count of 18.60 is 16.00.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A003 ==
# report: C-005
# section: Interpretation
# quoted sentence: Platelets are mildly reduced at 95 x10^9/L, also most likely treatment-related.
# rationale: A platelet count of 95 x10^9/L is below 100 and is often graded as moderate rather than mild thrombocytopenia. The grading is borderline, and the treatment-related attribution is reasonable.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: miss
reason: a debatable point about the platelet grading, but not the planted error

== A004 ==
# report: C-005
# section: Interpretation
# quoted sentence: Total white cell count is markedly reduced at 0.9 x10^9/L, with neutrophils forming 22% of the differential, giving an absolute neutrophil count of about 0.2 x10^9/L.
# rationale: A WBC of 0.9 x10^9/L with an ANC of 0.2 x10^9/L is a critical value in a patient on chemotherapy. The report has no critical flag, no urgent communication and no recommendation such as neutropenic precautions, fever assessment or oncology contact. It labels the neutropenia as mild instead.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the critical neutrophil count has no critical-value flag or recommendation

== A005 ==
# report: C-005
# section: Interpretation
# quoted sentence: The findings are in keeping with chemotherapy-induced myelosuppression in a patient who is ten days after a cycle of treatment for breast cancer.
# rationale: The report gives no clinical history, diagnosis or treatment timing, so the breast cancer and the 'ten days after a cycle' statement cannot be verified against the data presented.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error

== A006 ==
# report: C-001
# section: Interpretation
# quoted sentence: The history of menorrhagia makes chronic blood loss the most likely cause, and iron studies and a reticulocyte count are recommended to confirm the diagnosis.
# rationale: The report gives no clinical history, so the menorrhagia is not supported by anything shown. The conclusion that blood loss is the most likely cause rests on it.
# candidate planted error: C-001-E2 (C3, omission) in Values
#   its quoted sentence: Hb: 6.2 g/dL (ref 12.0–15.0)
#   its description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error

== A007 ==
# report: C-005
# section: Interpretation
# quoted sentence: Total white cell count is markedly reduced at 0.9 x10^9/L, with neutrophils forming 22% of the differential, giving an absolute neutrophil count of about 0.2 x10^9/L.
# rationale: WBC 0.9 and ANC 0.2 x10^9/L are critical values in a patient on chemotherapy. The report has no critical-value flag, urgent notification or recommendation (e.g. neutropenic precautions, fever assessment, clinician contact), and the 'mild' wording could delay action.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the critical neutrophil count has no critical-value flag or recommendation

== A008 ==
# report: H-007
# section: Synoptic summary
# quoted sentence: Perineural invasion: Not applicable
# rationale: The synoptic has no lymphovascular invasion field, although LVI is reported as not identified in the microscopic description and diagnosis. The synoptic is therefore incomplete.
# candidate planted error: H-007-E2 (H5, omission) in Synoptic summary
#   its quoted sentence: Perineural invasion: Not applicable
#   its description: The synoptic summary has no line for lymphovascular invasion.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the synoptic summary has no lymphovascular invasion line

== A009 ==
# report: C-001
# section: Interpretation
# quoted sentence: The history of menorrhagia makes chronic blood loss the most likely cause, and iron studies and a reticulocyte count are recommended to confirm the diagnosis.
# rationale: The report contains no clinical history or request details that mention menorrhagia, so this statement is not supported by the data shown.
# candidate planted error: C-001-E2 (C3, omission) in Values
#   its quoted sentence: Hb: 6.2 g/dL (ref 12.0–15.0)
#   its description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error

== A010 ==
# report: C-005
# section: Interpretation
# quoted sentence: The findings are in keeping with chemotherapy-induced myelosuppression in a patient who is ten days after a cycle of treatment for breast cancer.
# rationale: The report contains no clinical details about chemotherapy, timing or breast cancer. This history appears to be assumed or fabricated, and the cause is stated more firmly than the data support.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error

== A011 ==
# report: C-001
# section: Interpretation
# quoted sentence: The history of menorrhagia makes chronic blood loss the most likely cause, and iron studies and a reticulocyte count are recommended to confirm the diagnosis.
# rationale: The report gives no clinical history, so the menorrhagia cannot be verified from the data. The conclusion that blood loss is the most likely cause rests on that unverified statement.
# candidate planted error: C-001-E2 (C3, omission) in Values
#   its quoted sentence: Hb: 6.2 g/dL (ref 12.0–15.0)
#   its description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error

== A012 ==
# report: H-007
# section: Synoptic summary
# quoted sentence: Perineural invasion: Not applicable
# rationale: Perineural invasion is not assessed anywhere in the microscopic description. Marking it 'not applicable' rather than 'not identified' or 'not assessed' is inconsistent, though it is not a clear error.
# candidate planted error: H-007-E2 (H5, omission) in Synoptic summary
#   its quoted sentence: Perineural invasion: Not applicable
#   its description: The synoptic summary has no line for lymphovascular invasion.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: near_miss
reason: right place, but it is about the perineural invasion wording, not the missing line

== A013 ==
# report: C-001
# section: Interpretation
# quoted sentence: The history of menorrhagia makes chronic blood loss the most likely cause, and iron studies and a reticulocyte count are recommended to confirm the diagnosis.
# rationale: Hb 6.2 g/dL is below the usual critical threshold of about 7 g/dL. The report has no critical-value flag, no urgent notification to the clinician and no advice about clinical assessment or transfusion. It recommends only routine confirmatory tests.
# candidate planted error: C-001-E2 (C3, omission) in Values
#   its quoted sentence: Hb: 6.2 g/dL (ref 12.0–15.0)
#   its description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the critical haemoglobin has no critical-value flag or urgent recommendation

== A014 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count of 0.19 is above the stated upper limit of 0.10. It is not flagged or commented on, and it is probably an artefact of the 1% differential on a high WBC.
# candidate planted error: C-006-E2 (C1, statement) in Interpretation
#   its quoted sentence: The platelet count is raised, in keeping with a reactive thrombocytosis.
#   its other place 1: Values: Platelets: 245 x10^9/L (ref 150–410)
#   its description: The interpretation says the platelet count is raised; the count is 245, within the reference range.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A015 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count of 0.19 exceeds the stated upper limit of 0.10, yet the interpretation does not address it. It is also high relative to a basophil fraction of 1%, so either the reference range or the value looks wrong.
# candidate planted error: C-006-E2 (C1, statement) in Interpretation
#   its quoted sentence: The platelet count is raised, in keeping with a reactive thrombocytosis.
#   its other place 1: Values: Platelets: 245 x10^9/L (ref 150–410)
#   its description: The interpretation says the platelet count is raised; the count is 245, within the reference range.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A016 ==
# report: C-002
# section: Values
# quoted sentence: Basophils absolute: 0.48 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count is nearly five times the upper reference limit, yet it is not commented on in the interpretation. It is arithmetically consistent with 1% of the WBC, so the issue is a missing comment rather than a wrong value.
# candidate planted error: C-002-E2 (C2, statement) in Values
#   its quoted sentence: Neutrophils %: 22.0 % (ref 40.0–80.0)
#   its other place 1: Values: Neutrophils absolute: 5.76 x10^9/L (ref 2.00–7.00)
#   its description: Neutrophils are given as 22 percent; the differential then adds up to 110 and does not fit the absolute neutrophil count.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A017 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count exceeds the upper reference limit of 0.10. It is arithmetically consistent with 1% of the WBC, but it is not commented on in the interpretation.
# candidate planted error: C-006-E2 (C1, statement) in Interpretation
#   its quoted sentence: The platelet count is raised, in keeping with a reactive thrombocytosis.
#   its other place 1: Values: Platelets: 245 x10^9/L (ref 150–410)
#   its description: The interpretation says the platelet count is raised; the count is 245, within the reference range.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A018 ==
# report: C-007
# section: Values
# quoted sentence: Basophils absolute: 0.12 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count is above the reference range but is not commented on, although basophilia would be relevant in a suspected myeloproliferative neoplasm.
# candidate planted error: C-007-E2 (C1, statement) in Values
#   its quoted sentence: Platelets: 250 x10^9/L (ref 150–410)
#   its other place 1: Interpretation: Mild leucocytosis with neutrophil predominance and thrombocytosis, together with headache, plethoric facies and pruritus after bathing, raise suspicion of a myeloproliferative neoplasm such as polycythaemia vera, although secondary causes of erythrocytosis must be excluded.
#   its description: The Values give a platelet count of 250, within the reference range; the interpretation speaks of thrombocytosis.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A019 ==
# report: C-005
# section: Interpretation
# quoted sentence: Total white cell count is markedly reduced at 0.9 x10^9/L, with neutrophils forming 22% of the differential, giving an absolute neutrophil count of about 0.2 x10^9/L.
# rationale: A WBC of 0.9 and an ANC of 0.2 in a patient ten days after chemotherapy is a critical finding, with a high risk of neutropenic sepsis. The report has no critical-value flag, no urgent communication and no recommendation for clinical action.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the critical neutrophil count has no critical-value flag or recommendation

== A020 ==
# report: C-002
# section: Values
# quoted sentence: Basophils absolute: 0.48 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count is nearly five times the upper reference limit, yet it is not commented on in the interpretation. It is arithmetically consistent with 1% of the WBC, so the issue is a missing comment rather than a wrong value.
# candidate planted error: C-002-E1 (C1, statement) in Interpretation
#   its quoted sentence: Platelet count is markedly reduced.
#   its other place 1: Values: Platelets: 152 x10^9/L (ref 150–410)
#   its description: The interpretation says the platelet count is markedly reduced; the count is 152, within the reference range.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A021 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count of 0.19 is above the stated upper limit of 0.10. It is not flagged or commented on, and it is probably an artefact of the 1% differential on a high WBC.
# candidate planted error: C-006-E3 (C2, statement) in Values
#   its quoted sentence: Neutrophils absolute: 6.00 x10^9/L (ref 2.00–7.00)
#   its other place 1: Values: Neutrophils %: 86.0 % (ref 40.0–80.0)
#   its other place 2: Values: WBC: 18.60 x10^9/L (ref 4.00–10.00)
#   its other place 3: Interpretation: Marked neutrophilic leucocytosis with a neutrophil fraction of 86 per cent and relative lymphopenia, a pattern consistent with acute bacterial infection in the context of four days of fever and productive cough.
#   its description: The absolute neutrophil count is given as 6.00; 86 percent of a white cell count of 18.60 is 16.00.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A022 ==
# report: H-007
# section: Synoptic summary
# quoted sentence: Perineural invasion: Not applicable
# rationale: Perineural invasion is not a standard renal cell carcinoma synoptic element. Listing it as 'Not applicable' is odd. Elsewhere in the report, lymphovascular invasion is the element that is addressed.
# candidate planted error: H-007-E2 (H5, omission) in Synoptic summary
#   its quoted sentence: Perineural invasion: Not applicable
#   its description: The synoptic summary has no line for lymphovascular invasion.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: near_miss
reason: right place, but it is about the perineural invasion line, and it does not say a line is missing

== A023 ==
# report: C-006
# section: Values
# quoted sentence: Basophils absolute: 0.19 x10^9/L (ref 0.02–0.10)
# rationale: The absolute basophil count exceeds the upper reference limit of 0.10. It is arithmetically consistent with 1% of the WBC, but it is not commented on in the interpretation.
# candidate planted error: C-006-E3 (C2, statement) in Values
#   its quoted sentence: Neutrophils absolute: 6.00 x10^9/L (ref 2.00–7.00)
#   its other place 1: Values: Neutrophils %: 86.0 % (ref 40.0–80.0)
#   its other place 2: Values: WBC: 18.60 x10^9/L (ref 4.00–10.00)
#   its other place 3: Interpretation: Marked neutrophilic leucocytosis with a neutrophil fraction of 86 per cent and relative lymphopenia, a pattern consistent with acute bacterial infection in the context of four days of fever and productive cough.
#   its description: The absolute neutrophil count is given as 6.00; 86 percent of a white cell count of 18.60 is 16.00.
# why it needs you: the section is right, but the quoted sentence only partly matches this planted error (overlap of at least 0.4 and below 0.6)
verdict: miss
reason: the basophil count is truly above the printed range and not commented on; not the planted error

== A024 ==
# report: C-001
# section: Interpretation
# quoted sentence: The history of menorrhagia makes chronic blood loss the most likely cause, and iron studies and a reticulocyte count are recommended to confirm the diagnosis.
# rationale: Hb 6.2 g/dL is below the commonly used critical threshold of about 7 g/dL. The report gives no critical-value flag, urgent notification or advice on clinical assessment or transfusion, and only recommends routine confirmatory tests.
# candidate planted error: C-001-E2 (C3, omission) in Values
#   its quoted sentence: Hb: 6.2 g/dL (ref 12.0–15.0)
#   its description: The haemoglobin of 6.2 g/dL is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: detected
reason: says the critical haemoglobin has no critical-value flag or urgent recommendation

== A025 ==
# report: C-005
# section: Interpretation
# quoted sentence: The findings are in keeping with chemotherapy-induced myelosuppression in a patient who is ten days after a cycle of treatment for breast cancer.
# rationale: The report contains no clinical history, diagnosis or treatment timing. The breast cancer, the chemotherapy and the ten-day interval are not supported by the data shown.
# candidate planted error: C-005-E2 (C3, omission) in Values
#   its quoted sentence: Neutrophils absolute: 0.20 x10^9/L (ref 2.00–7.00)
#   its description: The absolute neutrophil count of 0.20 is a critical value, and the report carries no critical-value flag, comment or recommendation.
# why it needs you: this report has an omission error, and the finding is not a detection of another error; it may be reporting what is missing (the finding has one item for each omission error of the report)
verdict: false_alarm
reason: an interpretation that refers to the clinical history is not an error
