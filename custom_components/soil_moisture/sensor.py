"""Sensor platform for the Soil Moisture Indicator integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FORECAST_SENSORS, MANUFACTURER, WEATHER_FORECAST_DAYS
from .coordinator import SoilMoistureCoordinator, SoilMoistureData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the current, forecast, weather and optimal moisture sensors."""
    coordinator: SoilMoistureCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SoilMoistureCurrentSensor(coordinator, entry),
            *(
                SoilMoistureForecastSensor(coordinator, entry, key, days)
                for key, days in FORECAST_SENSORS.items()
            ),
            SoilMoistureWeatherForecastSensor(coordinator, entry),
            SoilMoisturePredictionSensor(coordinator, entry),
            SoilMoistureOptimalSensor(coordinator, entry),
            SoilMoistureWaterNeededSensor(coordinator, entry),
        ]
    )


def _trend_attributes(data: SoilMoistureData) -> dict[str, Any]:
    """Return the trend details shown on every forecast sensor."""
    trend = data.trend
    return {
        "trend_per_hour": round(trend.slope, 3) if trend else None,
        "trend_direction": trend.direction if trend else "unknown",
        "confidence": round(trend.r_squared, 2) if trend else None,
        "samples": data.sample_count,
    }


class _SoilMoistureBase(CoordinatorEntity[SoilMoistureCoordinator], SensorEntity):
    """Common properties of all sensors."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.MOISTURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: SoilMoistureCoordinator,
        entry: ConfigEntry,
        translation_key: str,
    ) -> None:
        """Set up the parts shared by every sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Soil moisture forecast",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _data(self) -> SoilMoistureData | None:
        return self.coordinator.data


class SoilMoistureCurrentSensor(_SoilMoistureBase):
    """Current soil moisture as reported by the source sensor."""

    _attr_icon = "mdi:water-percent"

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "current")

    @property
    def native_value(self) -> float | None:
        """Current moisture reading."""
        return None if self._data is None else self._data.current

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the current status relative to the plant profile."""
        data = self._data or SoilMoistureData()
        profile = self.coordinator.profile
        attributes: dict[str, Any] = {
            "source_entity": self.coordinator.source_entity,
            "plant_type": self.coordinator.plant_type,
            "optimal_min": profile.optimal_min,
            "optimal_max": profile.optimal_max,
            "moisture_status": data.status,
            **_trend_attributes(data),
        }
        if data.last_reading is not None:
            attributes["last_reading"] = data.last_reading.isoformat(
                timespec="seconds"
            )
        if data.last_watering is not None:
            attributes["last_watering"] = data.last_watering.isoformat(
                timespec="seconds"
            )
            attributes["minutes_since_watering"] = data.minutes_since_watering
        if data.source_last_updated is not None:
            attributes["source_last_updated"] = data.source_last_updated.isoformat(
                timespec="seconds"
            )
        if data.source_battery is not None:
            attributes["source_battery"] = data.source_battery
        return attributes


class SoilMoistureForecastSensor(_SoilMoistureBase):
    """Moisture after a fixed number of days of linear drying."""

    _attr_icon = "mdi:chart-timeline-variant"

    def __init__(
        self,
        coordinator: SoilMoistureCoordinator,
        entry: ConfigEntry,
        translation_key: str,
        days: float,
    ) -> None:
        """Set up a forecast sensor for ``days`` days."""
        super().__init__(coordinator, entry, translation_key)
        self._key = translation_key
        self._days = days

    @property
    def native_value(self) -> float | None:
        """Linearly extrapolated moisture after the configured number of days."""
        data = self._data
        return None if data is None else data.forecasts.get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the horizon and the trend behind the linear drying."""
        data = self._data or SoilMoistureData()
        return {
            "days": self._days,
            "hours": round(self._days * 24, 1),
            "basis": "linear_drying",
            "current_moisture": data.current,
            **_trend_attributes(data),
        }


class SoilMoistureWeatherForecastSensor(_SoilMoistureBase):
    """Moisture in one week, scaled with the weather forecast."""

    _attr_icon = "mdi:weather-partly-rainy"

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "weather_forecast")

    @property
    def native_value(self) -> float | None:
        """Moisture after one week of drying plus forecast rain."""
        data = self._data
        return None if data is None else data.weather_forecast

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the weather entity and how the forecast changed the drying."""
        data = self._data or SoilMoistureData()
        return {
            "days": WEATHER_FORECAST_DAYS,
            "basis": "weather_forecast",
            "weather_entity": data.weather_entity,
            "forecast_days_used": data.weather_days,
            "forecast_kind": data.weather_kind,
            "forecast_error": data.weather_error,
            "current_moisture": data.current,
            **_trend_attributes(data),
        }


class SoilMoisturePredictionSensor(_SoilMoistureBase):
    """Predicted soil moisture at the configured horizon."""

    _attr_icon = "mdi:chart-timeline-variant"

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "prediction")

    @property
    def native_value(self) -> float | None:
        """Predicted moisture for the configured horizon."""
        return None if self._data is None else self._data.predicted

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the trend details behind the prediction."""
        data = self._data or SoilMoistureData()
        trend = data.trend
        attributes: dict[str, Any] = {
            "source_entity": self.coordinator.source_entity,
            "current_moisture": data.current,
            "prediction_horizon_hours": self.coordinator.prediction_horizon,
            "history_hours": self.coordinator.history_hours,
            "moisture_status": data.status,
            **_trend_attributes(data),
        }
        if data.hours_until_min is not None:
            attributes["hours_until_optimal_min"] = round(data.hours_until_min, 1)
        if data.last_reading is not None:
            attributes["last_reading"] = data.last_reading.isoformat(
                timespec="seconds"
            )
        return attributes


class SoilMoistureOptimalSensor(_SoilMoistureBase):
    """Target moisture of the configured plant type."""

    _attr_state_class = None

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "optimal")

    @property
    def icon(self) -> str:
        """Use the plant type specific icon."""
        return self.coordinator.profile.icon

    @property
    def native_value(self) -> float:
        """Midpoint of the optimal moisture range."""
        return self.coordinator.profile.optimal_target

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full optimal range and the current status."""
        data = self._data or SoilMoistureData()
        profile = self.coordinator.profile
        return {
            "plant_type": self.coordinator.plant_type,
            "optimal_min": profile.optimal_min,
            "optimal_max": profile.optimal_max,
            "current_moisture": data.current,
            "moisture_status": data.status,
            "source_entity": self.coordinator.source_entity,
        }


class SoilMoistureWaterNeededSensor(_SoilMoistureBase):
    """Water needed to bring the soil back to the optimal moisture."""

    _attr_icon = "mdi:watering-can"
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_state_class = None
    _attr_suggested_display_precision = 0

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "water_needed")

    @property
    def native_value(self) -> float | None:
        """Millilitres needed to reach the middle of the optimal range."""
        data = self._data
        return None if data is None else data.water_needed_ml

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the target, the substrate volume and the amount in litres."""
        data = self._data or SoilMoistureData()
        profile = self.coordinator.profile
        return {
            "container_volume_litres": data.container_volume,
            "target_moisture": profile.optimal_target,
            "current_moisture": data.current,
            "water_needed_litres": (
                None
                if data.water_needed_ml is None
                else round(data.water_needed_ml / 1000, 2)
            ),
        }
