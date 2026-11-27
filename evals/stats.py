"""Small statistics helpers."""

from collections.abc import Sequence

import numpy as np


def bootstrap_ci(
    values: Sequence[float], resamples: int, seed: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean.

    Resample the results with replacement many times and see how much the mean moves.
    With a fixed seed the interval is identical on every rerun. If every value is the
    same, the interval has zero width; that does NOT mean there is no uncertainty.
    """
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        raise ValueError("Cannot bootstrap an empty list")
    picks = np.random.default_rng(seed).integers(0, data.size, size=(resamples, data.size))
    means = data[picks].mean(axis=1)
    tail = (1 - confidence) / 2
    low, high = np.quantile(means, [tail, 1 - tail])
    return float(low), float(high)


def percentile(values: Sequence[float], q: float) -> float:
    """The q-th percentile (0-100), with linear interpolation."""
    return float(np.percentile(np.asarray(values, dtype=float), q))


def bootstrap_ratio(
    numerators: Sequence[float], denominators: Sequence[float], resamples: int, seed: int
) -> tuple[float, float, float] | None:
    """(value, low, high) for sum(numerators) / sum(denominators), resampling rows.

    Used for rates whose denominator depends on what the system did, such as precision:
    each resample picks tasks again, then recomputes the ratio. Resamples with a zero
    denominator are left out. Returns None if the ratio is undefined.
    """
    top = np.asarray(numerators, dtype=float)
    bottom = np.asarray(denominators, dtype=float)
    if bottom.sum() == 0:
        return None
    picks = np.random.default_rng(seed).integers(0, top.size, size=(resamples, top.size))
    tops, bottoms = top[picks].sum(axis=1), bottom[picks].sum(axis=1)
    ratios = tops[bottoms > 0] / bottoms[bottoms > 0]
    low, high = np.quantile(ratios, [0.025, 0.975])
    return float(top.sum() / bottom.sum()), float(low), float(high)


def bootstrap_percentile(
    values: Sequence[float], q: float, resamples: int, seed: int
) -> tuple[float, float, float]:
    """(value, low, high) for the q-th percentile."""
    data = np.asarray(values, dtype=float)
    picks = np.random.default_rng(seed).integers(0, data.size, size=(resamples, data.size))
    estimates = np.percentile(data[picks], q, axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(np.percentile(data, q)), float(low), float(high)


def cohens_kappa(first: Sequence[bool], second: Sequence[bool]) -> float | None:
    """Agreement between two raters beyond what chance would give.

    1 is perfect, 0 is chance level. Returns None when it is undefined, which happens
    if both raters gave every item the same single verdict.
    """
    if len(first) != len(second) or not first:
        raise ValueError("Need two equally long, non-empty lists")
    total = len(first)
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / total
    yes_first, yes_second = sum(first) / total, sum(second) / total
    by_chance = yes_first * yes_second + (1 - yes_first) * (1 - yes_second)
    if by_chance == 1:
        return None
    return (observed - by_chance) / (1 - by_chance)


def wilson_interval(successes: int, total: int, z: float = 1.959964) -> tuple[float, float]:
    """95% interval for a share. Unlike the bootstrap, it keeps a width at 0 and 1."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Need 0 <= successes <= total, with total above 0")
    share = successes / total
    spread = z**2 / total
    centre = (share + spread / 2) / (1 + spread)
    half = z * ((share * (1 - share) + spread / 4) / total) ** 0.5 / (1 + spread)
    return max(0.0, centre - half), min(1.0, centre + half)
