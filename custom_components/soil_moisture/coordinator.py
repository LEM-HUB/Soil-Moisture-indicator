"""Data coordinator for the Soil Moisture Indicator integration."""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import Sequence

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTAINER_VOLUME,
    CONF_HISTORY_HOURS,
    CONF_PLANT_TYPE,
    CONF_PREDICTION_HORIZON,
    CONF_SOURCE_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_CONTAINER_VOLUME,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_PLANT_TYPE,
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    FORECAST_SENSORS,
    MAX_CONTAINER_VOLUME,
    MAX_HISTORY_HOURS,
    MAX_PREDICTION_HORIZON,
    MIN_CONTAINER_VOLUME,
    MIN_HISTORY_HOURS,
    MIN_PREDICTION_HORIZON,
    ML_PER_PERCENT_LITRE,
    STALE_AFTER_MINUTES,
    WATERING_JUMP_PERCENT,
    WATERING_MAX_GAP_MINUTES,
    PlantProfile,
    WEATHER_FORECAST_CACHE_MINUTES,
    WEATHER_FORECAST_DAYS,
    get_plant_profile,
)
from .predict import (
    MoistureTrend,
    classify,
    hours_until_threshold,
    linear_trend,
    predicted_value,
)
from .weather import (
    DailyForecast,
    HourlyForecast,
    hours_until_min_with_forecast,
    hours_until_min_with_hourly_forecast,
    project_linear,
    project_with_forecast,
    project_with_hourly_forecast,
)

_LOGGER = logging.getLogger(__name__)

MAX_SAMPLES = 5000


@dataclass
class SoilMoistureData:
    """Calculated state of one soil moisture sensor."""

    current: float | None = None
    predicted: float | None = None
    trend: MoistureTrend | None = None
    hours_until_min: float | None = None
    status: str = "unknown"
    sample_count: int = 0
    last_reading: datetime | None = None
    forecasts: dict[str, float] = field(default_factory=dict)
    """Linear forecasts in percent, keyed by the sensor translation key."""
    weather_forecast: float | None = None
    """Forecast for one week that also uses the weather forecast."""
    weather_entity: str | None = None
    weather_days: int = 0
    """Number of forecast days that were available and used."""
    weather_error: str | None = None
    """Why no weather forecast was used; ``None`` when one was available."""
    weather_kind: str | None = None
    """Whether ``daily`` or aggregated ``hourly`` forecast data was used."""
    days_until_min: float | None = None
    """Days until the linear drying reaches the lower end of the optimum."""
    days_until_min_weather: float | None = None
    """Days until the lower end is reached with the weather forecast applied."""
    water_needed_ml: float | None = None
    """Water in millilitres to reach the middle of the optimal range."""
    container_volume: float = 0.0
    """Substrate volume in litres, taken from the options."""
    watering_required: bool = False
    """Whether the moisture is below the optimal range."""
    last_watering: datetime | None = None
    """Last detected watering (a sudden jump in moisture)."""
    minutes_since_watering: float | None = None
    source_last_updated: datetime | None = None
    """Last time the source sensor changed its state."""
    source_battery: float | None = None
    """Battery level of the source sensor, when it reports one."""
    data_stale: bool = False
    """Whether the source sensor stopped reporting."""


def _numeric_value(state: State) -> float | None:
    """Return the numeric state value or ``None`` for unusable states."""
    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "", "none", "None"):
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if value == value else None  # reject NaN


def _as_number(value: object, fallback: float, minimum: float, maximum: float) -> float:
    """Coerce an option to a float inside ``[minimum, maximum]``."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if number != number:  # NaN
        return fallback
    return max(minimum, min(maximum, number))


def _source_battery(state: State) -> float | None:
    """Return the battery level the source sensor reports, if any."""
    for attribute in ("battery", "battery_level"):
        value = _optional_float(state.attributes.get(attribute))
        if value is not None:
            return value
    return None


def _daily_entries(entries: Sequence[dict]) -> list[DailyForecast]:
    """Convert daily forecast entries into the drying model input."""
    return [
        DailyForecast(
            temperature=_optional_float(entry.get("temperature")),
            precipitation=_optional_float(entry.get("precipitation")),
            cloud_coverage=_optional_float(entry.get("cloud_coverage")),
        )
        for entry in entries
    ]


def _hourly_entries(entries: Sequence[dict]) -> list[HourlyForecast]:
    """Convert hourly forecast entries into the hourly drying model input."""
    hours: list[HourlyForecast] = []
    for entry in entries:
        start = dt_util.parse_datetime(str(entry.get("datetime") or ""))
        if start is None:
            continue
        hours.append(
            HourlyForecast(
                start=dt_util.as_local(start),
                temperature=_optional_float(entry.get("temperature")),
                precipitation=_optional_float(entry.get("precipitation")),
                cloud_coverage=_optional_float(entry.get("cloud_coverage")),
                humidity=_optional_float(entry.get("humidity")),
                sun_irradiance=_optional_float(entry.get("sun_irradiance")),
                evaporation=_optional_float(entry.get("evaporation")),
            )
        )
    return hours


def _optional_float(value: object) -> float | None:
    """Coerce a forecast value to a float, ignoring missing or NaN values."""
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number == number else None


class SoilMoistureCoordinator(DataUpdateCoordinator[SoilMoistureData]):
    """Poll one moisture sensor, keep a short sample history and predict the trend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the coordinator for a config entry."""
        self.entry = entry
        self.source_entity: str = entry.data[CONF_SOURCE_ENTITY]
        self._samples: deque[tuple[float, float]] = deque(maxlen=MAX_SAMPLES)
        self._history_loaded = False
        self._forecast: list[DailyForecast] | None = None
        self._forecast_time: datetime | None = None
        self._forecast_error: str | None = None
        self._forecast_kind: str | None = None
        self._forecast_hours: list[HourlyForecast] | None = None
        self._last_watering: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MINUTES),
        )

    @property
    def plant_type(self) -> str:
        """Configured plant type key."""
        return self.entry.options.get(
            CONF_PLANT_TYPE,
            self.entry.data.get(CONF_PLANT_TYPE, DEFAULT_PLANT_TYPE),
        )

    @property
    def profile(self) -> PlantProfile:
        """Optimal moisture profile for the configured plant type."""
        return get_plant_profile(self.plant_type)

    @property
    def weather_entity(self) -> str | None:
        """Weather entity used for the forecast, if any.

        Falls back to the only weather entity of the instance when none is
        configured explicitly.
        """
        configured = self.entry.options.get(
            CONF_WEATHER_ENTITY, self.entry.data.get(CONF_WEATHER_ENTITY)
        )
        if configured:
            return str(configured)
        weather_entities = self.hass.states.async_entity_ids("weather")
        return weather_entities[0] if len(weather_entities) == 1 else None

    @property
    def container_volume(self) -> float:
        """Substrate volume in litres, used for the watering amount."""
        return _as_number(
            self.entry.options.get(
                CONF_CONTAINER_VOLUME,
                self.entry.data.get(
                    CONF_CONTAINER_VOLUME, DEFAULT_CONTAINER_VOLUME
                ),
            ),
            DEFAULT_CONTAINER_VOLUME,
            MIN_CONTAINER_VOLUME,
            MAX_CONTAINER_VOLUME,
        )

    @property
    def prediction_horizon(self) -> float:
        """Hours into the future the prediction sensor looks."""
        return _as_number(
            self.entry.options.get(
                CONF_PREDICTION_HORIZON, DEFAULT_PREDICTION_HORIZON
            ),
            DEFAULT_PREDICTION_HORIZON,
            MIN_PREDICTION_HORIZON,
            MAX_PREDICTION_HORIZON,
        )

    @property
    def history_hours(self) -> float:
        """How much history is used for the trend fit."""
        return _as_number(
            self.entry.options.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS),
            DEFAULT_HISTORY_HOURS,
            MIN_HISTORY_HOURS,
            MAX_HISTORY_HOURS,
        )

    async def _async_update_data(self) -> SoilMoistureData:
        """Read the source sensor, refresh the samples and calculate the trend."""
        state = self.hass.states.get(self.source_entity)
        if state is None:
            raise UpdateFailed(f"Source sensor {self.source_entity} is missing")

        current = _numeric_value(state)
        if current is None:
            raise UpdateFailed(
                f"Source sensor {self.source_entity} has no numeric value "
                f"(state: {state.state})"
            )

        now = dt_util.utcnow()
        self._detect_watering(current, now)
        self._samples.append((now.timestamp(), current))

        if not self._history_loaded:
            self._samples.extend(await self._async_history_samples())
            self._history_loaded = True

        self._prune_samples(now.timestamp())

        samples = sorted(self._samples)
        profile = self.profile
        trend = linear_trend(samples)

        if trend is not None:
            predicted = predicted_value(trend, current, self.prediction_horizon)
            hours_until_min = hours_until_threshold(
                trend, current, profile.optimal_min
            )
        else:
            predicted = current
            hours_until_min = None

        slope = trend.slope if trend is not None else 0.0
        forecasts = {
            key: round(project_linear(current, slope, days), 1)
            for key, days in FORECAST_SENSORS.items()
        }

        forecast_hours, forecast_days_list, forecast_error = (
            await self._async_weather_forecast()
        )
        if forecast_hours:
            weather_forecast = round(
                project_with_hourly_forecast(
                    current, slope, forecast_hours, WEATHER_FORECAST_DAYS
                ),
                1,
            )
            weather_days = min(
                int(math.ceil(len(forecast_hours) / 24)),
                int(WEATHER_FORECAST_DAYS),
            )
        elif forecast_days_list:
            weather_forecast = round(
                project_with_forecast(
                    current, slope, forecast_days_list, WEATHER_FORECAST_DAYS
                ),
                1,
            )
            weather_days = min(len(forecast_days_list), int(WEATHER_FORECAST_DAYS))
        else:
            weather_forecast = None
            weather_days = 0

        days_until_min = (
            None if hours_until_min is None else round(hours_until_min / 24, 1)
        )
        weather_hours_until_min: float | None = None
        if hours_until_min is not None:
            if forecast_hours:
                weather_hours_until_min = hours_until_min_with_hourly_forecast(
                    current, slope, forecast_hours, profile.optimal_min
                )
            elif forecast_days_list:
                weather_hours_until_min = hours_until_min_with_forecast(
                    current, slope, forecast_days_list, profile.optimal_min
                )
        days_until_min_weather = (
            None
            if weather_hours_until_min is None
            else round(weather_hours_until_min / 24, 1)
        )

        volume = self.container_volume
        water_needed_ml = (
            None
            if volume <= 0
            else round(
                max(0.0, profile.optimal_target - current)
                * volume
                * ML_PER_PERCENT_LITRE,
                0,
            )
        )

        return SoilMoistureData(
            current=round(current, 1),
            predicted=round(predicted, 1),
            trend=trend,
            hours_until_min=hours_until_min,
            status=classify(current, profile.optimal_min, profile.optimal_max),
            sample_count=len(samples),
            last_reading=now,
            forecasts=forecasts,
            weather_forecast=weather_forecast,
            weather_entity=self.weather_entity,
            weather_days=weather_days,
            weather_error=forecast_error,
            weather_kind=self._forecast_kind
            if (forecast_hours or forecast_days_list)
            else None,
            days_until_min=days_until_min,
            days_until_min_weather=days_until_min_weather,
            water_needed_ml=water_needed_ml,
            container_volume=volume,
            watering_required=current < profile.optimal_min,
            last_watering=self._last_watering,
            minutes_since_watering=(
                None
                if self._last_watering is None
                else round((now - self._last_watering).total_seconds() / 60, 0)
            ),
            source_last_updated=state.last_updated,
            source_battery=_source_battery(state),
            data_stale=(now - state.last_updated).total_seconds()
            > STALE_AFTER_MINUTES * 60,
        )

    async def _async_history_samples(self) -> list[tuple[float, float]]:
        """Load recent readings from the recorder so predictions survive restarts."""
        try:
            from homeassistant.components.recorder import (  # noqa: PLC0415
                get_instance,
                history,
                is_recording,
            )
        except ImportError:  # pragma: no cover - recorder always ships with core
            return []

        if not is_recording(self.hass):
            return []

        start = dt_util.utcnow() - timedelta(hours=self.history_hours)
        try:
            states: dict[str, list[State]] = await get_instance(
                self.hass
            ).async_add_executor_job(
                partial(
                    history.get_significant_states,
                    self.hass,
                    start,
                    None,
                    [self.source_entity],
                )
            )
        except Exception:  # noqa: BLE001 - history is best effort
            _LOGGER.debug(
                "Could not load recorder history for %s",
                self.source_entity,
                exc_info=True,
            )
            return []

        samples: list[tuple[float, float]] = []
        for historic_state in states.get(self.source_entity, []):
            value = _numeric_value(historic_state)
            if value is not None:
                samples.append((historic_state.last_updated.timestamp(), value))
        return samples

    async def _async_weather_forecast(
        self,
    ) -> tuple[list[HourlyForecast] | None, list[DailyForecast] | None, str | None]:
        """Return the hourly and daily forecast, cached for a while.

        Hourly data allows the more detailed drying model, so it is preferred;
        daily data is the fallback for integrations that only offer that.
        """
        entity_id = self.weather_entity
        if entity_id is None:
            weather_entities = self.hass.states.async_entity_ids("weather")
            reason = (
                "no_weather_entity"
                if not weather_entities
                else "multiple_weather_entities"
            )
            return None, None, reason

        now = dt_util.utcnow()
        if (
            self._forecast_time is not None
            and now - self._forecast_time
            < timedelta(minutes=WEATHER_FORECAST_CACHE_MINUTES)
        ):
            return self._forecast_hours, self._forecast, self._forecast_error

        hours: list[HourlyForecast] = []
        days: list[DailyForecast] = []
        kind = "hourly"
        error: str | None = None
        try:
            hours = _hourly_entries(
                await self._async_forecast_entries(entity_id, "hourly")
            )
        except Exception as err:  # noqa: BLE001 - the forecast is optional
            _LOGGER.debug(
                "Could not load an hourly weather forecast from %s",
                entity_id,
                exc_info=True,
            )
            error = f"service_error: {err}"

        if not hours:
            # Some weather integrations only provide a daily forecast.
            kind = "daily"
            try:
                days = _daily_entries(
                    await self._async_forecast_entries(entity_id, "daily")
                )
                error = None
            except Exception as err:  # noqa: BLE001 - the forecast is optional
                _LOGGER.debug(
                    "Could not load a daily weather forecast from %s",
                    entity_id,
                    exc_info=True,
                )
                error = f"service_error: {err}"

        available = bool(hours or days)
        self._forecast_hours = hours or None
        self._forecast = days or None
        self._forecast_time = now if available else None
        self._forecast_error = None if available else (error or "empty_forecast")
        self._forecast_kind = kind if available else None
        return self._forecast_hours, self._forecast, self._forecast_error

    async def _async_forecast_entries(
        self, entity_id: str, forecast_type: str
    ) -> list[dict]:
        """Fetch the raw forecast entries of a weather entity."""
        response = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {"type": forecast_type, "entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
        # Entity services return their response keyed by entity id, plain
        # services return it directly; accept both shapes.
        payload = response or {}
        entity_response = payload.get(entity_id) or payload
        return list(entity_response.get("forecast") or [])

    def _detect_watering(self, current: float, now: datetime) -> None:
        """Restart the trend when the moisture jumps up because of watering."""
        if not self._samples:
            return
        previous_time, previous_value = max(self._samples)
        if current - previous_value < WATERING_JUMP_PERCENT:
            return
        if now.timestamp() - previous_time > WATERING_MAX_GAP_MINUTES * 60:
            return
        _LOGGER.debug(
            "Detected watering of %s: %.1f %% -> %.1f %%, restarting the trend",
            self.source_entity,
            previous_value,
            current,
        )
        # The jump is not drying, so the old samples would falsify the trend.
        self._samples.clear()
        self._last_watering = now

    def _prune_samples(self, now: float) -> None:
        """Drop samples older than the configured history window."""
        cutoff = now - self.history_hours * 3600
        self._samples = deque(
            (sample for sample in self._samples if sample[0] >= cutoff),
            maxlen=MAX_SAMPLES,
        )
