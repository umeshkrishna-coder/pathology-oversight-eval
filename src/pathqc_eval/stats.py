"""Small statistics for the scorer (EVAL-05 6.6): the Wilson interval, Brier score, ECE, a
percentile and the paired bootstrap over reports. Standard library only; deterministic."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from statistics import NormalDist

from pathqc_eval import scoring_config as cfg


def z_value(level: float) -> float:
    return NormalDist().inv_cdf(1 - (1 - level) / 2)


def wilson(k: int, n: int, level: float | None = None) -> tuple[float, float] | None:
    """Wilson score interval for k successes in n trials; None when n is 0."""
    if n == 0:
        return None
    z = z_value(cfg.CONFIDENCE_LEVEL if level is None else level)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def brier(pairs: Sequence[tuple[float, int]]) -> float | None:
    """Mean squared difference between confidence and outcome (1 or 0); None without pairs."""
    if not pairs:
        return None
    return sum((c - o) ** 2 for c, o in pairs) / len(pairs)


def ece(pairs: Sequence[tuple[float, int]], bins: int | None = None) -> float | None:
    """Expected calibration error over equal-width bins on 0 to 1; a confidence of exactly 1
    falls in the last bin. None without pairs."""
    if not pairs:
        return None
    bins = cfg.ECE_BINS if bins is None else bins
    total = 0.0
    for b in range(bins):
        members = [(c, o) for c, o in pairs if min(int(c * bins), bins - 1) == b]
        if members:
            mean_c = sum(c for c, _ in members) / len(members)
            mean_o = sum(o for _, o in members) / len(members)
            total += len(members) / len(pairs) * abs(mean_c - mean_o)
    return total


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear interpolation between the closest ranks, q from 0 to 1."""
    if not sorted_values:
        raise ValueError("no values")
    pos = q * (len(sorted_values) - 1)
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def paired_bootstrap(
    ids: Sequence[str],
    statistic: Callable[[list[str]], float | None],
    resamples: int | None = None,
    seed: int | None = None,
    level: float | None = None,
) -> dict:
    """Report ids resampled with replacement; `statistic` gives the structured-minus-plain
    difference over a list of ids (the same resample serves both conditions) or None when it
    is undefined for that resample. Returns the difference over all ids, the percentile
    interval, the number of resamples and how many were undefined."""
    resamples = cfg.BOOTSTRAP_RESAMPLES if resamples is None else resamples
    seed = cfg.BOOTSTRAP_SEED if seed is None else seed
    level = cfg.CONFIDENCE_LEVEL if level is None else level
    ordered = sorted(ids)
    if not ordered:
        return {"difference": None, "interval": None, "resamples": 0, "undefined": 0}
    rng = random.Random(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(resamples):
        value = statistic([ordered[rng.randrange(len(ordered))] for _ in ordered])
        if value is None:
            undefined += 1
        else:
            values.append(value)
    values.sort()
    alpha = 1 - level
    interval = (
        [percentile(values, alpha / 2), percentile(values, 1 - alpha / 2)] if values else None
    )
    return {
        "difference": statistic(ordered),
        "interval": interval,
        "resamples": resamples,
        "undefined": undefined,
    }
