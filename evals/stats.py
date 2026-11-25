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
