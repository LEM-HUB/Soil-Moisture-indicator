"""Tests for the soil moisture prediction maths.

The helpers are loaded directly from their file so the tests do not need Home
Assistant (or the package ``__init__`` that imports it) to be installed.
"""

from __future__ import annotations

import importlib.util
import sys
import math

import pytest
from pathlib import Path
from types import ModuleType

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "soil_moisture"
ORIGIN = 1_700_000_000.0


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"soil_moisture_{name}", MODULE_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


predict = _load("predict")


def series(start: float, per_hour: float, count: int = 6, step_hours: float = 1.0):
    return [
        (ORIGIN + i * step_hours * 3600, start + i * step_hours * per_hour)
        for i in range(count)
    ]


def test_falling_trend_slope():
    trend = predict.linear_trend(series(70.0, -2.0))
    assert trend is not None
    assert trend.slope == pytest.approx(-2.0)
    assert trend.direction == "falling"
    assert trend.sample_count == 6
    assert trend.span_hours == pytest.approx(5.0)
    assert trend.r_squared == pytest.approx(1.0)


def test_rising_and_stable_direction():
    assert predict.linear_trend(series(30.0, 1.5)).direction == "rising"
    assert predict.linear_trend(series(50.0, 0.0)).direction == "stable"


def test_prediction_extrapolates_and_clamps():
    trend = predict.linear_trend(series(70.0, -2.0))
    assert predict.predicted_value(trend, 70.0, 6) == pytest.approx(58.0)
    assert predict.predicted_value(trend, 5.0, 12) == 0.0
    rising = predict.linear_trend(series(90.0, 5.0))
    assert predict.predicted_value(rising, 95.0, 10) == 100.0


def test_hours_until_threshold():
    falling = predict.linear_trend(series(70.0, -2.0))
    assert predict.hours_until_threshold(falling, 70.0, 60.0) == pytest.approx(5.0)
    assert predict.hours_until_threshold(falling, 55.0, 60.0) == 0.0

    stable = predict.linear_trend(series(70.0, 0.0))
    assert predict.hours_until_threshold(stable, 70.0, 60.0) is None

    rising = predict.linear_trend(series(40.0, 2.0))
    # Rising moisture never reaches a threshold below the current value.
    assert predict.hours_until_threshold(rising, 70.0, 60.0) is None


def test_not_enough_data():
    assert predict.linear_trend([]) is None
    assert predict.linear_trend(series(50.0, -1.0, count=2)) is None
    # Three samples within 25 minutes are too close together.
    short = [
        (ORIGIN, 50.0),
        (ORIGIN + 600, 49.9),
        (ORIGIN + 1500, 49.8),
    ]
    assert predict.linear_trend(short) is None


def test_unusable_values_are_ignored():
    points = [
        (ORIGIN, 50.0),
        (ORIGIN + 1800, "unavailable"),
        (ORIGIN + 3600, None),
        (ORIGIN + 5400, math.nan),
        (ORIGIN + 7200, 48.0),
        (ORIGIN + 10800, 47.0),
    ]
    trend = predict.linear_trend(points)
    assert trend is not None
    assert trend.sample_count == 3


def test_duplicate_timestamps_are_collapsed():
    points = [(ORIGIN, 50.0), (ORIGIN, 51.0), (ORIGIN + 3600, 49.0), (ORIGIN + 7200, 48.0)]
    trend = predict.linear_trend(points)
    assert trend is not None
    assert trend.sample_count == 3


def test_noisy_series_has_lower_confidence():
    noisy = series(60.0, -1.0, count=24, step_hours=1.0)
    noisy = [(t, v + (3.0 if i % 2 else -3.0)) for i, (t, v) in enumerate(noisy)]
    trend = predict.linear_trend(noisy)
    assert trend is not None
    assert 0.0 <= trend.r_squared < 0.9


def test_classify():
    assert predict.classify(30.0, 40.0, 60.0) == "below_optimal"
    assert predict.classify(50.0, 40.0, 60.0) == "optimal"
    assert predict.classify(75.0, 40.0, 60.0) == "above_optimal"
    assert predict.classify(40.0, 40.0, 60.0) == "optimal"
    assert predict.classify(60.0, 40.0, 60.0) == "optimal"
