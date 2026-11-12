"""Text handling, category mapping and the classification of findings (EVAL-05 6.2 to 6.4).

Decisions 8 and 34: a statement error is detected when the mapped type, the section and the
quoted sentence (token containment, the larger of the two directions) all match; an omission
when the type and the anchor's section match. Ambiguous cases go to the owner's blind
adjudication (decision 9). Owner decision (EVAL-09 C): in a report with an omission error, an
unmapped finding that is not already a hit or a review item for another error becomes a review
item for each omission error of the report.
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
    "unmapped_omission",
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
    after resolution also duplicate and miss.

    `error_ids` is set only where one finding concerns several errors (EVAL-09 C): a review
    for the omission errors of its report (one review item each), and after resolution a hit
    on more than one of them. Otherwise the error is `error_id` alone."""

    outcome: str
    error_id: str | None = None
    reason: str | None = None  # the review reason
    overlap: float | None = None
    error_ids: tuple[str, ...] = ()

    @property
    def ids(self) -> tuple[str, ...]:
        """Every error this outcome concerns."""
        if self.error_ids:
            return self.error_ids
        return () if self.error_id is None else (self.error_id,)


_LEVEL = {"hit": 0, "review": 1, "near_miss": 2}


def _error_number(error_id: str) -> int:
    return int(error_id.rsplit("-E", 1)[1])


def _places(err) -> list[tuple[str, str]]:
    """The error's main place, then its other places (decision 56, EVAL-10)."""
    others = getattr(err, "other_places", None) or []
    return [(err.section, err.quoted_sentence)] + [(p.section, p.quoted_sentence) for p in others]


def _at_place(kind: str, type_ok: bool, mapped: str, section_ok: bool, ov: float):
    """The 6.4 rules for one place of one error: (outcome, review reason) or (None, None)."""
    close = ov >= cfg.OVERLAP_THRESHOLD
    if kind == "omission":
        if type_ok and section_ok:
            return "hit", None
        if type_ok:
            return "review", "omission_other_section"
        if mapped == UNMAPPED and section_ok and close:
            return "review", "unmapped_category"
        return None, None
    if type_ok and section_ok and close:
        return "hit", None
    if section_ok and close and mapped == UNMAPPED:
        return "review", "unmapped_category"
    if section_ok and close:
        return "near_miss", None  # mapped to another taxonomy id or to other
    if type_ok and section_ok and ov >= cfg.BORDERLINE_LOW:
        return "review", "borderline_overlap"
    if type_ok and not section_ok and close:
        return "review", "section_mismatch"
    return None, None


def candidates(section: str, quote: str, mapped: str, errors: Sequence) -> list[Outcome]:
    """Every outcome the finding qualifies for, one per error at most (6.4).

    Decision 56 (EVAL-10): a finding quoting any of an error's places (its main sentence or one
    of its other places) is treated as one quoting the main sentence, using the best-matching
    place: the place giving the best outcome (hit before review before near-miss), then the
    highest overlap, then the main place before the others in order. For an omission, the
    right type in the anchor's section or in the section of any other place is a hit."""
    found: list[Outcome] = []
    f_section = normalise_section(section)
    for err in errors:
        type_ok = mapped == err.type
        best: tuple | None = None
        for n, (place_section, place_quote) in enumerate(_places(err)):
            section_ok = f_section == normalise_section(place_section)
            ov = overlap(quote, place_quote)
            outcome, reason = _at_place(err.kind, type_ok, mapped, section_ok, ov)
            if outcome is None:
                continue
            key = (_LEVEL[outcome], -ov, n)
            if best is None or key < best[0]:
                best = (key, Outcome(outcome, err.error_id, reason, ov))
        if best is not None:
            found.append(best[1])
    return found


def classify(section: str, quote: str, mapped: str, errors: Sequence) -> Outcome:
    """hit before review before near_miss; within a level the error with the highest overlap,
    then the lowest error id. A finding related to no error (every finding in a clean report)
    is a false_alarm."""
    found = candidates(section, quote, mapped, errors)
    if not found:
        omissions = tuple(e.error_id for e in errors if e.kind == "omission")
        if mapped == UNMAPPED and omissions:  # EVAL-09 C: one review item per omission
            return Outcome("review", omissions[0], "unmapped_omission", None, omissions)
        return Outcome("false_alarm")
    return min(found, key=lambda c: (_LEVEL[c.outcome], -c.overlap, _error_number(c.error_id)))


# Resolution: verdicts or a provisional scenario, then duplicates


def resolve(base: Sequence[Outcome], decide: Callable[[int, Outcome], str | None]) -> list[Outcome]:
    """Final outcomes of one unit's findings, in finding order.

    `decide(index, outcome)` gives the verdict for a review finding (detected, miss, near_miss,
    false_alarm) or None to leave it in review. A detected verdict is a hit for the candidate
    error. Then, per error, the first hit in finding order stays a hit and later hits are
    duplicates (neither hits nor false alarms).

    A finding in review for several omission errors (EVAL-09 C) gets one verdict per error,
    each asked with that error as the outcome's error_id: it is a hit for every error judged
    detected; otherwise a near-miss if any verdict is near_miss, a miss if any is miss, and a
    false alarm only when every verdict is false_alarm. A hit on several errors is a duplicate
    only where every one of them was hit earlier."""
    resolved: list[Outcome] = []
    for index, item in enumerate(base, start=1):
        if item.outcome == "review":
            item = _decided(item, index, decide)
        resolved.append(item)
    seen: set[str] = set()
    for i, item in enumerate(resolved):
        if item.outcome == "hit":
            new = tuple(e for e in item.ids if e not in seen)
            if not new:
                resolved[i] = replace(item, outcome="duplicate")
            else:
                seen.update(new)
                if new != item.ids:
                    resolved[i] = replace(
                        item, error_id=new[0], error_ids=new if len(new) > 1 else ()
                    )
    return resolved


def _decided(item: Outcome, index: int, decide: Callable[[int, Outcome], str | None]) -> Outcome:
    """One review finding with its verdicts applied (resolve)."""
    verdicts = [(eid, decide(index, replace(item, error_id=eid, error_ids=()))) for eid in item.ids]
    hits = tuple(eid for eid, verdict in verdicts if verdict == "detected")
    if hits:
        several = hits if len(hits) > 1 else ()
        return replace(item, outcome="hit", error_id=hits[0], error_ids=several)
    if any(verdict is None for _, verdict in verdicts):
        return item
    for kind in ("near_miss", "miss"):
        eid = next((e for e, verdict in verdicts if verdict == kind), None)
        if eid is not None:
            return replace(item, outcome=kind, error_id=eid, error_ids=())
    if all(verdict == "false_alarm" for _, verdict in verdicts):
        return replace(item, outcome="false_alarm", error_id=None, error_ids=())
    return item  # a verdict outside the four: left in review
