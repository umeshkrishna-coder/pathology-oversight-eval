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
