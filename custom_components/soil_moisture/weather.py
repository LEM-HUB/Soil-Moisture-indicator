"""Weather adjusted drying model for soil moisture forecasts.

The helpers in this module are deliberately free of Home Assistant imports so
the maths can be unit tested without running Home Assistant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
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

# Hourly drivers, used when the forecast has hourly detail.
# Dry air dries the soil faster than humid air (50 % is the reference).
HUMIDITY_REFERENCE = 50.0
HUMIDITY_FACTOR_PER_PERCENT = 0.008
MIN_HUMIDITY_FACTOR = 0.6
MAX_HUMIDITY_FACTOR = 1.4

# Solar irradiance in W/m²; 300 W/m² counts as an average hour.
RADIATION_REFERENCE_W = 300.0
RADIATION_FACTOR_PER_W = 0.0005
MIN_RADIATION_FACTOR = 0.8
MAX_RADIATION_FACTOR = 1.5

# Reported evaporation in mm per hour; 0.05 mm/h counts as an average hour.
EVAPORATION_REFERENCE_MM_H = 0.05
MIN_EVAPORATION_FACTOR = 0.3
MAX_EVAPORATION_FACTOR = 3.0


@dataclass(frozen=True)
class DailyForecast:
    """One day of weather forecast; every field is optional."""

    temperature: float | None = None
    """Daily high in °C."""

    precipitation: float | None = None
    """Rain or snow water equivalent in mm."""

    cloud_coverage: float | None = None
    """Average cloud cover in percent."""


@dataclass(frozen=True)
class HourlyForecast:
    """One hour of weather forecast; every field is optional."""

    start: datetime | None = None
    """Local start of the hour; used to cap the daily rain gain."""

    temperature: float | None = None
    """Temperature in °C."""

    precipitation: float | None = None
    """Rain or snow water equivalent in mm."""

    cloud_coverage: float | None = None
    """Cloud cover in percent."""

    humidity: float | None = None
    """Relative humidity in percent."""

    sun_irradiance: float | None = None
    """Global solar irradiance in W/m²."""

    evaporation: float | None = None
    """Reported evaporation in mm per hour."""


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


def humidity_factor(humidity: float | None) -> float:
    """Factor for the drying speed at ``humidity`` percent relative humidity."""
    if humidity is None or not math.isfinite(humidity):
        return 1.0
    return _clamp(
        1.0 + (HUMIDITY_REFERENCE - humidity) * HUMIDITY_FACTOR_PER_PERCENT,
        MIN_HUMIDITY_FACTOR,
        MAX_HUMIDITY_FACTOR,
    )


def radiation_factor(sun_irradiance: float | None) -> float:
    """Factor for the drying speed at ``sun_irradiance`` W/m²."""
    if sun_irradiance is None or not math.isfinite(sun_irradiance):
        return 1.0
    return _clamp(
        1.0 + (sun_irradiance - RADIATION_REFERENCE_W) * RADIATION_FACTOR_PER_W,
        MIN_RADIATION_FACTOR,
        MAX_RADIATION_FACTOR,
    )


def evaporation_factor(evaporation: float | None) -> float:
    """Scale drying with the evaporation the weather service reports in mm/h."""
    if evaporation is None or not math.isfinite(evaporation) or evaporation < 0:
        return 1.0
    return _clamp(
        evaporation / EVAPORATION_REFERENCE_MM_H,
        MIN_EVAPORATION_FACTOR,
        MAX_EVAPORATION_FACTOR,
    )


def rain_gain(precipitation: float | None) -> float:
    """Moisture gain in percentage points for ``precipitation`` millimetres."""
    if precipitation is None or not math.isfinite(precipitation) or precipitation <= 0:
        return 0.0
    return min(MAX_DAILY_RAIN_PERCENT, precipitation * RAIN_PERCENT_PER_MM)


def hour_factor(hour: HourlyForecast) -> float:
    """Combined weather factor for one hour of drying.

    A reported evaporation already includes temperature, wind and humidity, so
    it is used on its own. Without evaporation the solar irradiance stands in
    for sun and clouds; without both, the cloud cover is used. Humidity is only
    added while evaporation is unknown, to avoid counting it twice.
    """
    factor = temperature_factor(hour.temperature)
    if hour.evaporation is not None:
        return factor * evaporation_factor(hour.evaporation)
    if hour.sun_irradiance is not None:
        factor *= radiation_factor(hour.sun_irradiance)
    else:
        factor *= cloud_factor(hour.cloud_coverage)
    return factor * humidity_factor(hour.humidity)


def daily_change(slope_per_hour: float, day: DailyForecast) -> float:
    """Net moisture change in percentage points for one forecast day."""
    drying = (
        slope_per_hour
        * 24
        * temperature_factor(day.temperature)
        * cloud_factor(day.cloud_coverage)
    )
    return drying + rain_gain(day.precipitation)


def hourly_change(slope_per_hour: float, hour: HourlyForecast) -> float:
    """Net moisture change in percentage points for one forecast hour."""
    return slope_per_hour * hour_factor(hour) + rain_gain(hour.precipitation)


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


def project_with_hourly_forecast(
    current: float,
    slope_per_hour: float,
    hours: Sequence[HourlyForecast],
    days: float,
) -> float:
    """Project moisture hour by hour and fill missing hours with the trend.

    The rain gain is still capped per calendar day, so a heavy hourly forecast
    cannot refill the soil beyond the daily limit.
    """
    total_hours = max(1, int(round(days * 24)))
    value = current
    used = 0
    rain_by_day: dict[date, float] = {}

    for hour in hours:
        if used >= total_hours:
            break
        rain = 0.0
        if (
            hour.precipitation is not None
            and math.isfinite(hour.precipitation)
            and hour.start is not None
        ):
            day = hour.start.date()
            room = MAX_DAILY_RAIN_PERCENT - rain_by_day.get(day, 0.0)
            rain = max(0.0, min(rain_gain(hour.precipitation), room))
            rain_by_day[day] = rain_by_day.get(day, 0.0) + rain
        value = _clamp_moisture(value + slope_per_hour * hour_factor(hour) + rain)
        used += 1

    if used < total_hours:
        value = _clamp_moisture(value + slope_per_hour * (total_hours - used))
    return value


def _crossing_fraction(
    before: float, delta: float, threshold: float
) -> float | None:
    """Return the fraction of one step until the moisture reaches ``threshold``."""
    if delta < 0 and before + delta <= threshold:
        return (before - threshold) / -delta
    return None


def hours_until_min_with_forecast(
    current: float,
    slope_per_hour: float,
    forecast: Sequence[DailyForecast],
    threshold: float,
) -> float | None:
    """Return the hours until the daily forecast dries the soil to ``threshold``.

    ``0.0`` means the threshold is already reached and ``None`` means the trend
    is not drying out. Once the forecast runs out the plain linear trend
    continues, so a date beyond the forecast range is still answered.
    """
    if current <= threshold:
        return 0.0
    if slope_per_hour >= 0:
        return None

    value = current
    elapsed = 0.0
    for day in forecast:
        delta = daily_change(slope_per_hour, day)
        fraction = _crossing_fraction(value, delta, threshold)
        if fraction is not None:
            return elapsed + fraction * 24
        value = _clamp_moisture(value + delta)
        elapsed += 24.0

    return elapsed + (value - threshold) / -slope_per_hour


def hours_until_min_with_hourly_forecast(
    current: float,
    slope_per_hour: float,
    hours: Sequence[HourlyForecast],
    threshold: float,
) -> float | None:
    """Return the hours until the hourly forecast dries the soil to ``threshold``.

    Every forecast entry counts as one hour, matching
    :func:`project_with_hourly_forecast`. The rain gain is capped per calendar
    day there as well. ``0.0`` means the threshold is already reached, ``None``
    means the trend is not drying out; past the forecast the linear trend
    continues.
    """
    if current <= threshold:
        return 0.0
    if slope_per_hour >= 0:
        return None

    value = current
    elapsed = 0.0
    rain_by_day: dict[date, float] = {}

    for hour in hours:
        rain = 0.0
        if (
            hour.precipitation is not None
            and math.isfinite(hour.precipitation)
            and hour.start is not None
        ):
            day = hour.start.date()
            room = MAX_DAILY_RAIN_PERCENT - rain_by_day.get(day, 0.0)
            rain = max(0.0, min(rain_gain(hour.precipitation), room))
            rain_by_day[day] = rain_by_day.get(day, 0.0) + rain
        delta = slope_per_hour * hour_factor(hour) + rain
        fraction = _crossing_fraction(value, delta, threshold)
        if fraction is not None:
            return elapsed + fraction
        value = _clamp_moisture(value + delta)
        elapsed += 1.0

    return elapsed + (value - threshold) / -slope_per_hour
