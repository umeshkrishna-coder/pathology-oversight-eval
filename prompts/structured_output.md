Return only a JSON object, with no text before or after it, in this form: {"findings": [ ... ]}
Each finding is an object with exactly these fields:
- "quoted_sentence": the sentence or line from the report that contains the error, copied exactly. If the error is that something is missing, quote the sentence or line that makes the omission evident.
- "section": the name of the section the quoted text is in, exactly as it appears in the report.
- "category": the id of the matching error type from the taxonomy above. If no type fits, use "other".
- "severity": one of "critical", "major", "minor", as defined in the taxonomy above.
- "confidence": a number from 0 to 1, your probability that this is a real error.
- "rationale": one or two sentences explaining the error.
If you find no error, return {"findings": []}.
