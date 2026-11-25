"""Trend and prediction maths for soil moisture readings.

The helpers in this module are deliberately free of Home Assistant imports so
the maths can be unit tested without running Home Assistant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

MIN_MOISTURE = 0.0
MAX_MOISTURE = 100.0

# A trend needs at least this many readings and this much time to be useful.
MIN_SAMPLES = 3
MIN_SPAN_HOURS = 0.5

# Slopes below this (in percentage points per hour) count as "stable".
FLAT_SLOPE = 0.05


@dataclass(frozen=True)
class MoistureTrend:
    """Result of a least-squares fit through moisture samples."""

    slope: float
    """Change in percentage points per hour. Negative = drying out."""

    intercept: float
    """Fitted value at the first sample, in percentage points."""

    r_squared: float
    """Coefficient of determination (0..1); how well the line fits."""

    sample_count: int
    span_hours: float

    @property
    def direction(self) -> str:
        """Return ``falling``, ``stable`` or ``rising``."""
        if self.slope <= -FLAT_SLOPE:
            return "falling"
        if self.slope >= FLAT_SLOPE:
            return "rising"
        return "stable"


def _clean_points(
    points: Iterable[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Drop unusable values, de-duplicate timestamps and sort by time."""
    cleaned: dict[float, float] = {}
    for timestamp, value in points:
        try:
            time_value = float(timestamp)
            moisture = float(value)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(time_value) and math.isfinite(moisture)):
            continue
        cleaned[time_value] = moisture
    return sorted(cleaned.items())


def linear_trend(points: Iterable[tuple[float, float]]) -> MoistureTrend | None:
    """Fit a straight line through ``(epoch seconds, moisture)`` samples.

    Returns ``None`` when there is not enough data for a meaningful fit.
    """
    cleaned = _clean_points(points)
    if len(cleaned) < MIN_SAMPLES:
        return None

    span_hours = (cleaned[-1][0] - cleaned[0][0]) / 3600
    if span_hours < MIN_SPAN_HOURS:
        return None

    # Use hours relative to the first sample for numerical stability.
    origin = cleaned[0][0]
    xs = [(timestamp - origin) / 3600 for timestamp, _ in cleaned]
    ys = [value for _, value in cleaned]

    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    syy = sum((y - mean_y) ** 2 for y in ys)

    slope = sxy / sxx
    r_squared = 0.0
    if syy > 0:
        r_squared = max(0.0, min(1.0, (sxy * sxy) / (sxx * syy)))

    return MoistureTrend(
        slope=slope,
        intercept=mean_y - slope * mean_x,
        r_squared=r_squared,
        sample_count=count,
        span_hours=span_hours,
    )


def predicted_value(
    trend: MoistureTrend,
    current: float,
    hours: float,
    minimum: float = MIN_MOISTURE,
    maximum: float = MAX_MOISTURE,
) -> float:
    """Extrapolate the trend ``hours`` into the future, clamped to sensor range."""
    value = current + trend.slope * hours
    return max(minimum, min(maximum, value))


def hours_until_threshold(
    trend: MoistureTrend,
    current: float,
    threshold: float,
) -> float | None:
    """Return hours until the moisture reaches ``threshold``.

    ``0.0`` means the threshold is already reached, ``None`` means the trend is
    not falling fast enough to ever reach it.
    """
    if current <= threshold:
        return 0.0
    if trend.slope > -FLAT_SLOPE:
        return None
    return (current - threshold) / -trend.slope


def classify(value: float, optimal_min: float, optimal_max: float) -> str:
    """Return ``below_optimal``, ``optimal`` or ``above_optimal``."""
    if value < optimal_min:
        return "below_optimal"
    if value > optimal_max:
        return "above_optimal"
    return "optimal"
