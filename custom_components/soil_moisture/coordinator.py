"""Data coordinator for the Soil Moisture Indicator integration."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
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
    DEFAULT_HISTORY_HOURS,
    DEFAULT_PLANT_TYPE,
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MAX_HISTORY_HOURS,
    MAX_PREDICTION_HORIZON,
    MIN_HISTORY_HOURS,
    MIN_PREDICTION_HORIZON,
    PlantProfile,
    get_plant_profile,
)
from .predict import (
    MoistureTrend,
    classify,
    hours_until_threshold,
    linear_trend,
    predicted_value,
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


class SoilMoistureCoordinator(DataUpdateCoordinator[SoilMoistureData]):
    """Poll one moisture sensor, keep a short sample history and predict the trend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the coordinator for a config entry."""
        self.entry = entry
        self.source_entity: str = entry.data[CONF_SOURCE_ENTITY]
        self._samples: deque[tuple[float, float]] = deque(maxlen=MAX_SAMPLES)
        self._history_loaded = False
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

        return SoilMoistureData(
            current=round(current, 1),
            predicted=round(predicted, 1),
            trend=trend,
            hours_until_min=hours_until_min,
            status=classify(current, profile.optimal_min, profile.optimal_max),
            sample_count=len(samples),
            last_reading=now,
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

    def _prune_samples(self, now: float) -> None:
        """Drop samples older than the configured history window."""
        cutoff = now - self.history_hours * 3600
        self._samples = deque(
            (sample for sample in self._samples if sample[0] >= cutoff),
            maxlen=MAX_SAMPLES,
        )
