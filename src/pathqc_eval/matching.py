"""Text handling, category mapping and the classification of findings (EVAL-05 6.2 to 6.4).

Decisions 8 and 34: a statement error is detected when the mapped type, the section and the
quoted sentence (token containment, the larger of the two directions) all match; an omission
when the type and the anchor's section match. Ambiguous cases go to the owner's blind
adjudication (decision 9).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from pathqc_eval import scoring_config as cfg

OTHER = "other"
UNMAPPED = "unmapped"
VERDICTS = ("detected", "miss", "near_miss", "false_alarm")
REVIEW_REASONS = (
    "unmapped_category",
    "borderline_overlap",
    "section_mismatch",
    "omission_other_section",
)
# A token is a maximal run of letters and digits; a decimal point between digits stays inside.
_TOKEN = re.compile(r"[^\W_]+(?:(?<=\d)\.(?=\d)[^\W_]+)*")
_TRAILING_STOP = re.compile(r"[\s:.]+$")


# 6.2 Text handling


def _collapse(text: str) -> str:
    return " ".join(text.casefold().split())


def normalise_section(text: str) -> str:
    """Casefold, strip, collapse inner whitespace, drop a trailing colon or full stop."""
    return _TRAILING_STOP.sub("", _collapse(text))


def normalise_category(text: str) -> str:
    """Casefold, strip, collapse whitespace, drop trailing punctuation: every Unicode
    punctuation character at the end (category P: stops, commas, dashes, brackets, quotes),
    so "C2 (indices)." becomes "c2 (indices". Symbols such as + are not punctuation."""
    collapsed = _collapse(text)
    while collapsed and unicodedata.category(collapsed[-1]).startswith("P"):
        collapsed = collapsed[:-1].rstrip()
    return collapsed


def normalise_quote(text: str) -> str:
    """For merging identical review findings: casefold, strip, collapse whitespace."""
    return _collapse(text)


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def overlap(a: str, b: str) -> float:
    """The larger of |A∩B|/|A| and |A∩B|/|B| over token sets; 0 if either set is empty."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    shared = len(ta & tb)
    return max(shared / len(ta), shared / len(tb))


# 6.3 Category mapping


def map_category(category: str, type_ids: Iterable[str], category_map: Mapping[str, str]) -> str:
    """A taxonomy id, "other" or "unmapped". A category equal to a taxonomy id maps to it in
    both conditions; otherwise the map decides. The same string always maps the same way."""
    key = normalise_category(category)
    by_key = {tid.casefold(): tid for tid in type_ids}
    if key in by_key:
        return by_key[key]
    if key == OTHER:
        return OTHER
    return category_map.get(key, UNMAPPED)


# 6.4 Classifying one finding against the planted errors of its report


@dataclass(frozen=True)
class Outcome:
    """One finding's outcome. Before adjudication: hit, review, near_miss or false_alarm;
    after resolution also duplicate and miss."""

    outcome: str
    error_id: str | None = None
    reason: str | None = None  # the review reason
    overlap: float | None = None


_LEVEL = {"hit": 0, "review": 1, "near_miss": 2}


def _error_number(error_id: str) -> int:
    return int(error_id.rsplit("-E", 1)[1])


def candidates(section: str, quote: str, mapped: str, errors: Sequence) -> list[Outcome]:
    """Every outcome the finding qualifies for, one per error at most (6.4)."""
    found: list[Outcome] = []
    f_section = normalise_section(section)
    for err in errors:
        type_ok = mapped == err.type
        section_ok = f_section == normalise_section(err.section)
        ov = overlap(quote, err.quoted_sentence)
        close = ov >= cfg.OVERLAP_THRESHOLD
        outcome: str | None = None
        reason: str | None = None
        if err.kind == "omission":
            if type_ok and section_ok:
                outcome = "hit"
            elif type_ok:
                outcome, reason = "review", "omission_other_section"
            elif mapped == UNMAPPED and section_ok and close:
                outcome, reason = "review", "unmapped_category"
        elif type_ok and section_ok and close:
            outcome = "hit"
        elif section_ok and close and mapped == UNMAPPED:
            outcome, reason = "review", "unmapped_category"
        elif section_ok and close:
            outcome = "near_miss"  # mapped to another taxonomy id or to other
        elif type_ok and section_ok and ov >= cfg.BORDERLINE_LOW:
            outcome, reason = "review", "borderline_overlap"
        elif type_ok and not section_ok and close:
            outcome, reason = "review", "section_mismatch"
        if outcome is not None:
            found.append(Outcome(outcome, err.error_id, reason, ov))
    return found


def classify(section: str, quote: str, mapped: str, errors: Sequence) -> Outcome:
    """hit before review before near_miss; within a level the error with the highest overlap,
    then the lowest error id. A finding related to no error (every finding in a clean report)
    is a false_alarm."""
    found = candidates(section, quote, mapped, errors)
    if not found:
        return Outcome("false_alarm")
    return min(found, key=lambda c: (_LEVEL[c.outcome], -c.overlap, _error_number(c.error_id)))


# Resolution: verdicts or a provisional scenario, then duplicates


def resolve(base: Sequence[Outcome], decide: Callable[[int, Outcome], str | None]) -> list[Outcome]:
    """Final outcomes of one unit's findings, in finding order.

    `decide(index, outcome)` gives the verdict for a review finding (detected, miss, near_miss,
    false_alarm) or None to leave it in review. A detected verdict is a hit for the candidate
    error. Then, per error, the first hit in finding order stays a hit and later hits are
    duplicates (neither hits nor false alarms)."""
    resolved: list[Outcome] = []
    for index, item in enumerate(base, start=1):
        if item.outcome == "review":
            verdict = decide(index, item)
            if verdict == "detected":
                item = replace(item, outcome="hit")
            elif verdict in ("miss", "near_miss", "false_alarm"):
                error_id = None if verdict == "false_alarm" else item.error_id
                item = replace(item, outcome=verdict, error_id=error_id)
        resolved.append(item)
    seen: set[str] = set()
    for i, item in enumerate(resolved):
        if item.outcome == "hit":
            if item.error_id in seen:
                resolved[i] = replace(item, outcome="duplicate")
            else:
                seen.add(item.error_id)
    return resolved
