"""Text handling and the classification of findings (EVAL-05 6.2 and 6.4).

Detection by place (decision 61, EVAL-12; amends decisions 8, 47(a) and 56): a finding detects
a statement error when its section matches and its quoted sentence overlaps one of the error's
places (its main sentence or a named other place) at or above the threshold, whatever its
category. No category is used. An omission is never detected automatically: in a report with an
omission error, every finding that is not a hit for another error goes to the owner's blind
adjudication as a candidate for that omission (decision 62).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from pathqc_eval import scoring_config as cfg

VERDICTS = ("detected", "miss", "near_miss", "false_alarm")
REVIEW_REASONS = ("borderline_overlap", "section_mismatch", "omission_candidate")
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


# 6.4 Classifying one finding against the planted errors of its report


@dataclass(frozen=True)
class Outcome:
    """One finding's outcome. Before adjudication: hit, review or false_alarm; after
    resolution also duplicate, and near_miss or miss by a verdict (there is no automatic
    near-miss).

    A review may concern several errors, one review item each (decision 61): `error_ids` and
    `reasons` list them in error order, and `error_id` and `reason` are the first. After
    resolution a hit on several errors lists them in `error_ids`. Otherwise the error is
    `error_id` alone."""

    outcome: str
    error_id: str | None = None
    reason: str | None = None  # the review reason
    overlap: float | None = None
    error_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def ids(self) -> tuple[str, ...]:
        """Every error this outcome concerns."""
        if self.error_ids:
            return self.error_ids
        return () if self.error_id is None else (self.error_id,)


def _error_number(error_id: str) -> int:
    return int(error_id.rsplit("-E", 1)[1])


def _places(err) -> list[tuple[str, str]]:
    """The error's main place, then its other places (decision 56, EVAL-10)."""
    others = getattr(err, "other_places", None) or []
    return [(err.section, err.quoted_sentence)] + [(p.section, p.quoted_sentence) for p in others]


def _statement(section: str, quote: str, err) -> tuple[str, str | None, float] | None:
    """The best place of one statement error for a finding: (hit or review, reason, overlap),
    or None. Best place: the best outcome, then the highest overlap, then the main place."""
    best: tuple | None = None
    f_section = normalise_section(section)
    for n, (place_section, place_quote) in enumerate(_places(err)):
        section_ok = f_section == normalise_section(place_section)
        ov = overlap(quote, place_quote)
        if section_ok and ov >= cfg.OVERLAP_THRESHOLD:
            found = ("hit", None)
        elif section_ok and ov >= cfg.BORDERLINE_LOW:
            found = ("review", "borderline_overlap")
        elif not section_ok and ov >= cfg.OVERLAP_THRESHOLD:
            found = ("review", "section_mismatch")
        else:
            continue
        key = (0 if found[0] == "hit" else 1, -ov, n)
        if best is None or key < best[0]:
            best = (key, (found[0], found[1], ov))
    return None if best is None else best[1]


def classify(section: str, quote: str, errors: Sequence) -> Outcome:
    """A finding's outcome against the planted errors of its report (decisions 61 and 62).

    hit: section_ok and overlap at or above the threshold at some place of a statement error;
    with several, the highest overlap, then the lowest error id (one hit per finding). A hit
    is no review item for any other error. Otherwise review, one item for each statement error
    with a borderline overlap in the right section or the sentence in another section at its
    best place, and for each omission error of the report (omission_candidate). Otherwise a
    false alarm; in a clean report every finding is a false alarm."""
    hits: list[tuple[float, int, str]] = []
    reviews: list[tuple[int, str, str, float | None]] = []
    for err in errors:
        number = _error_number(err.error_id)
        if err.kind == "omission":
            best = max((overlap(quote, q) for _, q in _places(err)), default=0.0)
            reviews.append((number, err.error_id, "omission_candidate", best))
            continue
        found = _statement(section, quote, err)
        if found is None:
            continue
        outcome, reason, ov = found
        if outcome == "hit":
            hits.append((-ov, number, err.error_id))
        else:
            reviews.append((number, err.error_id, reason, ov))
    if hits:
        neg_ov, _, error_id = min(hits)
        return Outcome("hit", error_id, None, -neg_ov)
    if reviews:
        reviews.sort()
        overlaps = [r[3] for r in reviews if r[3] is not None]
        return Outcome(
            "review",
            reviews[0][1],
            reviews[0][2],
            max(overlaps) if overlaps else None,
            tuple(r[1] for r in reviews),
            tuple(r[2] for r in reviews),
        )
    return Outcome("false_alarm")


# Resolution: verdicts or a provisional scenario, then duplicates


def resolve(base: Sequence[Outcome], decide: Callable[[int, Outcome], str | None]) -> list[Outcome]:
    """Final outcomes of one unit's findings, in finding order.

    `decide(index, outcome)` gives the verdict for a review finding (detected, miss, near_miss,
    false_alarm) or None to leave it in review. A detected verdict is a hit for the candidate
    error. Then, per error, the first hit in finding order stays a hit and later hits are
    duplicates (neither hits nor false alarms).

    A finding in review for several errors gets one verdict per error (decisions 50 and 62),
    each asked with that error and its reason as the outcome's error_id and reason: it is a
    hit for every error judged detected; otherwise a near-miss if any verdict is near_miss, a
    miss if any is miss, and a false alarm only when every verdict is false_alarm. A hit on
    several errors is a duplicate only where every one of them was hit earlier."""
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
    reasons = item.reasons or (item.reason,) * len(item.ids)
    verdicts = [
        (eid, decide(index, replace(item, error_id=eid, reason=r, error_ids=(), reasons=())))
        for eid, r in zip(item.ids, reasons, strict=True)
    ]
    hits = tuple(eid for eid, verdict in verdicts if verdict == "detected")
    if hits:
        several = hits if len(hits) > 1 else ()
        return replace(item, outcome="hit", error_id=hits[0], error_ids=several, reasons=())
    if any(verdict is None for _, verdict in verdicts):
        return item
    for kind in ("near_miss", "miss"):
        eid = next((e for e, verdict in verdicts if verdict == kind), None)
        if eid is not None:
            return replace(item, outcome=kind, error_id=eid, error_ids=(), reasons=())
    if all(verdict == "false_alarm" for _, verdict in verdicts):
        return replace(item, outcome="false_alarm", error_id=None, error_ids=(), reasons=())
    return item  # a verdict outside the four: left in review
