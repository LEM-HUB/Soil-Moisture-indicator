"""Data coordinator for the Soil Moisture Indicator integration."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HISTORY_HOURS,
    CONF_PLANT_TYPE,
    CONF_PREDICTION_HORIZON,
    CONF_SOURCE_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_PLANT_TYPE,
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    FORECAST_SENSORS,
    MAX_HISTORY_HOURS,
    MAX_PREDICTION_HORIZON,
    MIN_HISTORY_HOURS,
    MIN_PREDICTION_HORIZON,
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
from .weather import DailyForecast, project_linear, project_with_forecast

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


def _numeric_value(state: State) -> float | None:
    """Return the numeric state value or ``None`` for unusable states."""
    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "", "none", "None"):
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if value == value else None  # reject NaN


def _as_hours(value: object, fallback: float, minimum: float, maximum: float) -> float:
    """Coerce an option to a float inside ``[minimum, maximum]``."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if number != number:  # NaN
        return fallback
    return max(minimum, min(maximum, number))


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
    def prediction_horizon(self) -> float:
        """Hours into the future the prediction sensor looks."""
        return _as_hours(
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
        return _as_hours(
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

        forecast, forecast_error = await self._async_weather_forecast()
        if forecast:
            weather_forecast = round(
                project_with_forecast(
                    current, slope, forecast, WEATHER_FORECAST_DAYS
                ),
                1,
            )
            weather_days = min(len(forecast), int(WEATHER_FORECAST_DAYS))
        else:
            weather_forecast = None
            weather_days = 0

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
    ) -> tuple[list[DailyForecast] | None, str | None]:
        """Return the daily forecast of the weather entity, cached for a while."""
        entity_id = self.weather_entity
        if entity_id is None:
            weather_entities = self.hass.states.async_entity_ids("weather")
            reason = "no_weather_entity" if not weather_entities else "multiple_weather_entities"
            return None, reason

        now = dt_util.utcnow()
        if (
            self._forecast_time is not None
            and now - self._forecast_time
            < timedelta(minutes=WEATHER_FORECAST_CACHE_MINUTES)
        ):
            return self._forecast, self._forecast_error

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily", "entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - the forecast is optional
            _LOGGER.debug(
                "Could not load a weather forecast from %s",
                entity_id,
                exc_info=True,
            )
            self._forecast = None
            self._forecast_time = None
            self._forecast_error = f"service_error: {err}"
            return None, self._forecast_error

        # Entity services return their response keyed by entity id, plain
        # services return it directly; accept both shapes.
        payload = response or {}
        entity_response = payload.get(entity_id) or payload
        entries = entity_response.get("forecast") or []
        forecast = [
            DailyForecast(
                temperature=_optional_float(entry.get("temperature")),
                precipitation=_optional_float(entry.get("precipitation")),
                cloud_coverage=_optional_float(entry.get("cloud_coverage")),
            )
            for entry in entries
        ]
        self._forecast = forecast or None
        self._forecast_time = now
        self._forecast_error = None if forecast else "empty_forecast"
        return self._forecast, self._forecast_error

    def _prune_samples(self, now: float) -> None:
        """Drop samples older than the configured history window."""
        cutoff = now - self.history_hours * 3600
        self._samples = deque(
            (sample for sample in self._samples if sample[0] >= cutoff),
            maxlen=MAX_SAMPLES,
        )
