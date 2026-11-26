"""Tests for the weather adjusted drying model."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "soil_moisture"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"soil_moisture_{name}", MODULE_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


weather = _load("weather")


def test_temperature_factor():
    assert weather.temperature_factor(None) == 1.0
    assert weather.temperature_factor(weather.TEMP_REFERENCE_C) == pytest.approx(1.0)
    assert weather.temperature_factor(30) == pytest.approx(1.3)
    assert weather.temperature_factor(80) == weather.MAX_TEMP_FACTOR
    assert weather.temperature_factor(-80) == weather.MIN_TEMP_FACTOR


def test_cloud_factor():
    assert weather.cloud_factor(None) == 1.0
    assert weather.cloud_factor(0) == pytest.approx(1.0)
    assert weather.cloud_factor(100) == pytest.approx(
        weather.CLOUD_FACTOR_AT_FULL_COVER
    )


def test_rain_gain():
    assert weather.rain_gain(None) == 0.0
    assert weather.rain_gain(-1) == 0.0
    assert weather.rain_gain(2) == pytest.approx(4.0)
    assert weather.rain_gain(1000) == weather.MAX_DAILY_RAIN_PERCENT


def test_daily_change_scales_with_weather():
    mild_day = weather.DailyForecast(
        temperature=20, precipitation=0, cloud_coverage=0
    )
    assert weather.daily_change(-0.5, mild_day) == pytest.approx(-12.0)

    rainy_cloudy_day = weather.DailyForecast(
        temperature=20, precipitation=3, cloud_coverage=100
    )
    # -0.5 * 24 * 1.0 * 0.7 + 3 * 2.0
    assert weather.daily_change(-0.5, rainy_cloudy_day) == pytest.approx(-2.4)


def test_daily_change_uses_defaults_for_missing_weather():
    empty_day = weather.DailyForecast()
    assert weather.daily_change(-0.1, empty_day) == pytest.approx(-2.4)


def test_project_linear_is_clamped():
    assert weather.project_linear(50, -0.5, 1) == pytest.approx(38.0)
    assert weather.project_linear(10, -0.5, 7) == 0.0
    assert weather.project_linear(50, 1.0, 7) == 100.0


def test_project_without_rain_matches_linear():
    forecast = [weather.DailyForecast(temperature=20, cloud_coverage=0)] * 7
    assert weather.project_with_forecast(
        60, -0.1, forecast, 7
    ) == pytest.approx(weather.project_linear(60, -0.1, 7))


def test_project_counts_rain():
    dry = [
        weather.DailyForecast(temperature=25, precipitation=0, cloud_coverage=0)
    ] * 7
    wet = [
        weather.DailyForecast(temperature=25, precipitation=3, cloud_coverage=100)
    ] * 7
    assert weather.project_with_forecast(
        60, -0.2, wet, 7
    ) > weather.project_with_forecast(60, -0.2, dry, 7)


def test_short_forecast_falls_back_to_linear_tail():
    forecast = [weather.DailyForecast(temperature=20, cloud_coverage=0)] * 2
    expected = weather.project_linear(weather.project_linear(60, -0.1, 2), -0.1, 5)
    assert weather.project_with_forecast(
        60, -0.1, forecast, 7
    ) == pytest.approx(expected)


def test_humidity_factor():
    assert weather.humidity_factor(None) == 1.0
    assert weather.humidity_factor(50) == pytest.approx(1.0)
    assert weather.humidity_factor(90) == pytest.approx(0.68)
    assert weather.humidity_factor(100) == weather.MIN_HUMIDITY_FACTOR
    assert weather.humidity_factor(0) == weather.MAX_HUMIDITY_FACTOR


def test_radiation_factor():
    assert weather.radiation_factor(None) == 1.0
    assert weather.radiation_factor(weather.RADIATION_REFERENCE_W) == pytest.approx(1.0)
    assert weather.radiation_factor(0) == pytest.approx(0.85)
    assert weather.radiation_factor(5000) == weather.MAX_RADIATION_FACTOR


def test_evaporation_factor():
    assert weather.evaporation_factor(None) == 1.0
    assert weather.evaporation_factor(-1) == 1.0
    assert weather.evaporation_factor(
        weather.EVAPORATION_REFERENCE_MM_H
    ) == pytest.approx(1.0)
    assert weather.evaporation_factor(0.1) == pytest.approx(2.0)
    assert weather.evaporation_factor(5) == weather.MAX_EVAPORATION_FACTOR


def test_hour_factor_prefers_evaporation():
    hour = weather.HourlyForecast(
        temperature=20, humidity=90, sun_irradiance=0, evaporation=0.1
    )
    # Evaporation replaces radiation and humidity; temperature still applies.
    assert weather.hour_factor(hour) == pytest.approx(2.0)


def test_hour_factor_uses_radiation_and_humidity():
    hour = weather.HourlyForecast(temperature=20, humidity=90, sun_irradiance=800)
    # 1.0 temperature * 1.25 radiation * 0.68 humidity
    assert weather.hour_factor(hour) == pytest.approx(0.85)


def test_hour_factor_falls_back_to_clouds():
    hour = weather.HourlyForecast(temperature=20, cloud_coverage=100)
    assert weather.hour_factor(hour) == pytest.approx(0.7)


def test_project_hourly_uses_every_hour():
    start = datetime(2026, 11, 26, 0, tzinfo=timezone.utc)
    hours = [
        weather.HourlyForecast(start=start, temperature=20, cloud_coverage=0)
        for _ in range(3)
    ]
    # 3 hours at -0.01 %/h, then 165 hours of the plain linear trend
    assert weather.project_with_hourly_forecast(
        60, -0.01, hours, 7
    ) == pytest.approx(58.32)


def test_project_hourly_caps_rain_per_day():
    start = datetime(2026, 11, 26, 0, tzinfo=timezone.utc)
    hours = [
        weather.HourlyForecast(start=start, temperature=20, precipitation=50)
        for _ in range(4)
    ]
    # 4 * 50 mm would be 400 points, capped at the daily maximum of 40
    assert weather.project_with_hourly_forecast(
        10, 0.0, hours, 4 / 24
    ) == pytest.approx(50.0)


def test_empty_forecast_uses_linear_projection():
    assert weather.project_with_forecast(
        60, -0.1, [], 7
    ) == pytest.approx(weather.project_linear(60, -0.1, 7))


def test_hours_until_min_without_weather_matches_linear():
    mild = weather.DailyForecast(temperature=20, precipitation=0, cloud_coverage=0)
    # 0.5 pp/h * 24 h = 12 pp per day, 10 pp to go -> 20 h
    assert weather.hours_until_min_with_forecast(
        50, -0.5, [mild] * 7, 40
    ) == pytest.approx(20.0)


def test_hours_until_min_is_delayed_by_rain():
    mild = weather.DailyForecast(temperature=20, precipitation=0, cloud_coverage=0)
    rainy = weather.DailyForecast(temperature=20, precipitation=5, cloud_coverage=0)
    # Two dry days (50 -> 45.2), one rainy day (+7.6 -> 52.8), then 12.8 pp at
    # 2.4 pp per day -> 3 + 5.333 days
    assert weather.hours_until_min_with_forecast(
        50, -0.1, [mild, mild, rainy] + [mild] * 10, 40
    ) == pytest.approx(200.0, abs=0.05)


def test_hours_until_min_falls_back_to_linear_past_the_forecast():
    mild = weather.DailyForecast(temperature=20, precipitation=0, cloud_coverage=0)
    # one day of -12 pp -> 48 pp, then 8 pp at 0.5 pp/h
    assert weather.hours_until_min_with_forecast(60, -0.5, [mild], 40) == pytest.approx(
        40.0
    )


def test_hours_until_min_edge_cases():
    mild = weather.DailyForecast(temperature=20, cloud_coverage=0)
    assert weather.hours_until_min_with_forecast(40, -0.5, [mild], 40) == 0.0
    assert weather.hours_until_min_with_forecast(35, -0.5, [mild], 40) == 0.0
    assert weather.hours_until_min_with_forecast(50, 0.2, [mild], 40) is None
    assert weather.hours_until_min_with_forecast(50, 0.0, [], 40) is None


def test_hours_until_min_hourly_forecast():
    hour = weather.HourlyForecast()
    # no weather fields -> factor 1.0, so 10 pp at 0.5 pp/h is 20 h
    assert weather.hours_until_min_with_hourly_forecast(
        50, -0.5, [hour] * 30, 40
    ) == pytest.approx(20.0)

    start = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)
    rainy_hour = weather.HourlyForecast(start=start, precipitation=1)
    # the first hour adds 2 pp, so 11.5 pp at 0.5 pp/h remain -> 24 h in total
    assert weather.hours_until_min_with_hourly_forecast(
        50, -0.5, [rainy_hour] + [hour] * 40, 40
    ) == pytest.approx(24.0)


def test_hours_until_min_ignores_forecast_beyond_the_projection():
    mild = weather.DailyForecast(temperature=20, precipitation=0, cloud_coverage=0)
    rainy = weather.DailyForecast(temperature=20, precipitation=5, cloud_coverage=0)
    # 50 -> 33.2 % in seven dry days, then 3.2 pp at 2.4 pp/day. The rain of
    # days 8-10 must not delay the crossing, because the projection stops at
    # seven days as well.
    assert weather.hours_until_min_with_forecast(
        50, -0.1, [mild] * 7 + [rainy] * 3, 30
    ) == pytest.approx(200.0)


def test_hours_until_min_hourly_ignores_hours_beyond_the_projection():
    mild = weather.HourlyForecast(temperature=20, cloud_coverage=0)
    start = datetime(2026, 5, 8, tzinfo=timezone.utc)
    rainy = weather.HourlyForecast(start=start, precipitation=5)
    # 168 dry hours take 50 -> 33.2 %, the rainy hours after them are ignored.
    assert weather.hours_until_min_with_hourly_forecast(
        50, -0.1, [mild] * 168 + [rainy] * 72, 30
    ) == pytest.approx(200.0)


def test_flat_trend_never_reaches_the_threshold():
    mild = weather.DailyForecast(temperature=20, cloud_coverage=0)
    hour = weather.HourlyForecast(temperature=20, cloud_coverage=0)
    # -0.01 %/h counts as stable, exactly like FLAT_SLOPE in predict.py.
    assert weather.hours_until_min_with_forecast(50, -0.01, [mild] * 7, 40) is None
    assert (
        weather.hours_until_min_with_hourly_forecast(50, -0.01, [hour] * 168, 40)
        is None
    )
