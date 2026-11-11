"""Statistics for the scorer (EVAL-05 6.6): Wilson, Brier, ECE, percentile, paired bootstrap."""

import pytest

from pathqc_eval.stats import brier, ece, paired_bootstrap, percentile, wilson


@pytest.mark.parametrize(
    ("k", "n", "low", "high"),
    [
        # Newcombe (1998), Statistics in Medicine 17:857-872, Table I, method 3 (Wilson).
        (81, 263, 0.2553, 0.3662),
        (15, 148, 0.0624, 0.1605),
        (0, 20, 0.0, 0.1611),
        (1, 29, 0.0061, 0.1718),
    ],
)
def test_wilson_matches_published_values(k, n, low, high):
    lo, hi = wilson(k, n)
    assert (round(lo, 4), round(hi, 4)) == (low, high)


def test_wilson_with_no_trials_is_none():
    assert wilson(0, 0) is None


def test_brier():
    """(0.9 - 1)^2 + (0.3 - 0)^2 = 0.01 + 0.09 = 0.10, over 2 findings = 0.05."""
    assert brier([(0.9, 1), (0.3, 0)]) == pytest.approx(0.05)
    assert brier([]) is None


def test_ece_with_five_equal_bins():
    """Bins [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1]. Pairs: 0.1/0 and 0.3/0 in
    bins 1 and 2 (gaps 0.1 and 0.3); 0.65/1 and 0.75/0 in bin 4 (mean confidence 0.7, mean
    outcome 0.5, gap 0.2); 1.0/1 in bin 5 (gap 0). ECE = (0.1 + 0.3 + 2 x 0.2 + 0) / 5 = 0.16."""
    pairs = [(0.1, 0), (0.3, 0), (0.65, 1), (0.75, 0), (1.0, 1)]
    assert ece(pairs) == pytest.approx(0.16)
    assert ece([]) is None


def test_ece_puts_a_confidence_of_one_in_the_last_bin():
    """1.0 with outcome 0 falls in the last bin [0.8, 1]: gap 1 over one pair. With 0.9/1
    beside it: mean confidence 0.95, mean outcome 0.5, gap 0.45."""
    assert ece([(1.0, 0)]) == pytest.approx(1.0)
    assert ece([(1.0, 0), (0.9, 1)]) == pytest.approx(0.45)


def test_percentile_interpolates():
    assert percentile([0.0, 1.0, 2.0, 3.0], 0.5) == 1.5
    assert percentile([5.0], 0.025) == 5.0
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_bootstrap_is_deterministic():
    values = {"R1": 0.0, "R2": 1.0, "R3": 1.0, "R4": 0.0, "R5": 1.0}

    def statistic(ids):
        return sum(values[i] for i in ids) / len(ids)

    first = paired_bootstrap(list(values), statistic, resamples=500)
    second = paired_bootstrap(list(reversed(list(values))), statistic, resamples=500)
    assert first == second
    assert first["difference"] == pytest.approx(0.6)
    low, high = first["interval"]
    assert 0.0 <= low < 0.6 < high <= 1.0


def test_bootstrap_interval_is_the_percentiles_of_the_resampled_values():
    """The mean of [0, 1, 1, 0, 1] over the default 10,000 resamples with seed 20261115: the
    2.5th and 97.5th percentiles of the resampled means are 0.2 and 1.0."""
    values = {"R1": 0.0, "R2": 1.0, "R3": 1.0, "R4": 0.0, "R5": 1.0}
    result = paired_bootstrap(list(values), lambda ids: sum(values[i] for i in ids) / len(ids))
    assert result["interval"] == pytest.approx([0.2, 1.0])


def test_bootstrap_seed_defaults_to_the_configured_seed():
    values = {"R1": 0.0, "R2": 1.0, "R3": 2.0, "R4": 4.0, "R5": 8.0}

    def statistic(ids):
        return sum(values[i] for i in ids) / len(ids)

    default = paired_bootstrap(list(values), statistic, resamples=50)
    assert default == paired_bootstrap(list(values), statistic, resamples=50, seed=20261115)
    assert default["interval"] == pytest.approx([0.845, 5.2])
    assert paired_bootstrap(list(values), statistic, resamples=50, seed=1)["interval"] == (
        pytest.approx([1.2, 5.0])
    )


def test_bootstrap_of_identical_conditions_is_zero():
    def statistic(ids):
        return 0.0 * len(ids)

    result = paired_bootstrap(["R1", "R2", "R3"], statistic)
    assert result["difference"] == 0.0 and result["interval"] == [0.0, 0.0]
    assert result["resamples"] == 10000 and result["undefined"] == 0


def test_bootstrap_counts_undefined_resamples():
    def statistic(ids):
        return None if "R2" not in ids else 1.0

    result = paired_bootstrap(["R1", "R2"], statistic, resamples=200)
    assert 0 < result["undefined"] < 200
    assert result["interval"] == [1.0, 1.0]


def test_bootstrap_with_no_reports():
    assert paired_bootstrap([], lambda ids: 0.0)["interval"] is None
