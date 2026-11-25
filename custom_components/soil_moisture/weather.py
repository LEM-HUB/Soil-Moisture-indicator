"""Weather adjusted drying model for soil moisture forecasts.

The helpers in this module are deliberately free of Home Assistant imports so
the maths can be unit tested without running Home Assistant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Sequence

MIN_MOISTURE = 0.0
MAX_MOISTURE = 100.0

# Drying is referenced to a 20 °C day without clouds and scales with both.
TEMP_REFERENCE_C = 20.0
TEMP_FACTOR_PER_C = 0.03
MIN_TEMP_FACTOR = 0.5
MAX_TEMP_FACTOR = 2.0

# Full cloud cover slows drying down to this factor (sunny day = 1.0).
CLOUD_FACTOR_AT_FULL_COVER = 0.7

# Rain refills the soil: percentage points per millimetre, capped per day.
RAIN_PERCENT_PER_MM = 2.0
MAX_DAILY_RAIN_PERCENT = 40.0


@dataclass(frozen=True)
class DailyForecast:
    """One day of weather forecast; every field is optional."""

    temperature: float | None = None
    """Daily high in °C."""

    precipitation: float | None = None
    """Rain or snow water equivalent in mm."""

    cloud_coverage: float | None = None
    """Average cloud cover in percent."""


def aggregate_hourly(
    hours: Sequence[tuple[date, float | None, float | None, float | None]],
) -> list[DailyForecast]:
    """Combine hourly forecast values into one entry per calendar day.

    ``hours`` holds ``(day, temperature, precipitation, cloud_coverage)``
    tuples. The temperature is reduced to the daily maximum, precipitation is
    summed and cloud coverage is averaged, matching what weather integrations
    report for a daily forecast.
    """
    order: list[date] = []
    days: dict[date, tuple[list[float], list[float], list[float]]] = {}
    for day, temperature, precipitation, cloud_coverage in hours:
        if day not in days:
            days[day] = ([], [], [])
            order.append(day)
        temperatures, rains, clouds = days[day]
        if temperature is not None and math.isfinite(temperature):
            temperatures.append(temperature)
        if precipitation is not None and math.isfinite(precipitation):
            rains.append(precipitation)
        if cloud_coverage is not None and math.isfinite(cloud_coverage):
            clouds.append(cloud_coverage)

    return [
        DailyForecast(
            temperature=max(temperatures) if temperatures else None,
            precipitation=sum(rains) if rains else None,
            cloud_coverage=sum(clouds) / len(clouds) if clouds else None,
        )
        for temperatures, rains, clouds in (days[day] for day in order)
    ]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Return ``value`` limited to ``[minimum, maximum]``."""
    return max(minimum, min(maximum, value))


def _clamp_moisture(value: float) -> float:
    """Return ``value`` limited to the sensor range."""
    return _clamp(value, MIN_MOISTURE, MAX_MOISTURE)


def temperature_factor(temperature: float | None) -> float:
    """Factor for the drying speed at a daily high of ``temperature`` °C."""
    if temperature is None or not math.isfinite(temperature):
        return 1.0
    return _clamp(
        1.0 + (temperature - TEMP_REFERENCE_C) * TEMP_FACTOR_PER_C,
        MIN_TEMP_FACTOR,
        MAX_TEMP_FACTOR,
    )


def cloud_factor(cloud_coverage: float | None) -> float:
    """Factor for the drying speed at ``cloud_coverage`` percent cover."""
    if cloud_coverage is None or not math.isfinite(cloud_coverage):
        return 1.0
    coverage = _clamp(cloud_coverage, 0.0, 100.0) / 100
    return 1.0 - (1.0 - CLOUD_FACTOR_AT_FULL_COVER) * coverage


def rain_gain(precipitation: float | None) -> float:
    """Moisture gain in percentage points for ``precipitation`` millimetres."""
    if precipitation is None or not math.isfinite(precipitation) or precipitation <= 0:
        return 0.0
    return min(MAX_DAILY_RAIN_PERCENT, precipitation * RAIN_PERCENT_PER_MM)


def daily_change(slope_per_hour: float, day: DailyForecast) -> float:
    """Net moisture change in percentage points for one forecast day."""
    drying = (
        slope_per_hour
        * 24
        * temperature_factor(day.temperature)
        * cloud_factor(day.cloud_coverage)
    )
    return drying + rain_gain(day.precipitation)


def project_linear(current: float, slope_per_hour: float, days: float) -> float:
    """Extrapolate linear drying ``days`` into the future, clamped to 0–100 %."""
    return _clamp_moisture(current + slope_per_hour * 24 * days)


def project_with_forecast(
    current: float,
    slope_per_hour: float,
    forecast: Sequence[DailyForecast],
    days: float,
) -> float:
    """Project moisture over ``days`` using daily weather and linear drying.

    Every forecast day scales the linear drying with the expected temperature
    and cloud cover and adds the rain of that day. Days without a forecast
    entry fall back to the plain linear trend.
    """
    value = current
    used = 0
    for day in forecast[: int(math.ceil(days))]:
        if used >= days:
            break
        value = _clamp_moisture(value + daily_change(slope_per_hour, day))
        used += 1

    remaining = days - used
    if remaining > 0:
        value = _clamp_moisture(value + slope_per_hour * 24 * remaining)
    return value
