"""Sensor platform for the Soil Moisture Indicator integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SoilMoistureCoordinator, SoilMoistureData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the prediction and optimal moisture sensors."""
    coordinator: SoilMoistureCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SoilMoisturePredictionSensor(coordinator, entry),
            SoilMoistureOptimalSensor(coordinator, entry),
        ]
    )


class _SoilMoistureBase(CoordinatorEntity[SoilMoistureCoordinator], SensorEntity):
    """Common properties of both sensors."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.MOISTURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"
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


class SoilMoisturePredictionSensor(_SoilMoistureBase):
    """Predicted soil moisture at the configured horizon."""

    _attr_translation_key = "prediction"
    _attr_icon = "mdi:chart-timeline-variant"

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
            "trend_per_hour": round(trend.slope, 3) if trend else None,
            "trend_direction": trend.direction if trend else "unknown",
            "confidence": round(trend.r_squared, 2) if trend else None,
            "samples": data.sample_count,
            "moisture_status": data.status,
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

    _attr_translation_key = "optimal"
    _attr_state_class = None

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
