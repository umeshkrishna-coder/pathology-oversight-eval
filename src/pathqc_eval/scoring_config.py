"""Scorer settings in one place (EVAL-05 6.1).

The owner confirmed these defaults on 2026-11-11 (EVAL-09 G; decision 47, OWNER VERIFIED):
the review bands, false alarms per report as the mean count per valid unit (a clean control
passes a unit with none), severity weights 3, 2, 1, Wilson intervals for per-type recall, and
a bootstrap of 10,000 resamples with seed 20261115. Should OWNER_CONFIRMED ever be set back to
False, `pathqc-eval score --dataset scored` refuses.
"""

OVERLAP_THRESHOLD = 0.6  # decision 8: token containment, the larger of the two directions
BORDERLINE_LOW = 0.4  # type and section right, overlap from here up to the threshold: review
SEVERITY_WEIGHTS = {"critical": 3, "major": 2, "minor": 1}  # for severity-weighted recall
ECE_BINS = 5  # decision 7: equal-width confidence bins on 0 to 1
BOOTSTRAP_RESAMPLES = 10000  # resamples in the paired bootstrap over reports
BOOTSTRAP_SEED = 20261115  # fixed seed for the bootstrap and the adjudication order
CONFIDENCE_LEVEL = 0.95  # Wilson intervals and bootstrap percentile intervals
OWNER_CONFIRMED = True  # confirmed by the owner on 2026-11-11 (EVAL-09 G)
SEVERITIES = ("critical", "major", "minor")  # plain recall by severity (EVAL-09 G), this order


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
