"""Scorer settings in one place (EVAL-05 6.1).

These are proposed defaults awaiting the owner's confirmation (handoff.md, open items). While
OWNER_CONFIRMED is False, `pathqc-eval score --dataset scored` refuses and lists them; dev
scoring and the tests work.
"""

OVERLAP_THRESHOLD = 0.6  # decision 8: token containment, the larger of the two directions
BORDERLINE_LOW = 0.4  # type and section right, overlap from here up to the threshold: review
SEVERITY_WEIGHTS = {"critical": 3, "major": 2, "minor": 1}  # for severity-weighted recall
ECE_BINS = 5  # decision 7: equal-width confidence bins on 0 to 1
BOOTSTRAP_RESAMPLES = 10000  # resamples in the paired bootstrap over reports
BOOTSTRAP_SEED = 20261115  # fixed seed for the bootstrap and the adjudication order
CONFIDENCE_LEVEL = 0.95  # Wilson intervals and bootstrap percentile intervals
OWNER_CONFIRMED = False  # True only once the owner confirms these defaults (scored scoring)

# The defaults awaiting the owner, as `score --dataset scored` lists them while unconfirmed.
PENDING_DEFAULTS = (
    "a finding goes to blind adjudication when its category is unmapped, when the overlap is "
    "between 0.4 and 0.6 with type and section right, when type and sentence are right but the "
    "section differs, or when an omission is reported under another section",
    "false alarms per report are the mean count per valid unit, and a clean control passes when "
    "a unit has none",
    "for calibration a hit, a duplicate or a near-miss counts as 1 and a false alarm as 0",
    "severity weights 3, 2, 1",
    "Wilson intervals for per-type recall",
    "bootstrap of 10,000 resamples with seed 20261115",
)


def config_values() -> dict:
    """The values in this module, as score.json records them."""
    return {
        "OVERLAP_THRESHOLD": OVERLAP_THRESHOLD,
        "BORDERLINE_LOW": BORDERLINE_LOW,
        "SEVERITY_WEIGHTS": dict(SEVERITY_WEIGHTS),
        "ECE_BINS": ECE_BINS,
        "BOOTSTRAP_RESAMPLES": BOOTSTRAP_RESAMPLES,
        "BOOTSTRAP_SEED": BOOTSTRAP_SEED,
        "CONFIDENCE_LEVEL": CONFIDENCE_LEVEL,
        "OWNER_CONFIRMED": OWNER_CONFIRMED,
    }
