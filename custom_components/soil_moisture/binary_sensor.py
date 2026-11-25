"""Binary sensor platform for the Soil Moisture Indicator integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, STALE_AFTER_MINUTES
from .coordinator import SoilMoistureCoordinator, SoilMoistureData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the watering and data quality binary sensors."""
    coordinator: SoilMoistureCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SoilMoistureWateringRequiredSensor(coordinator, entry),
            SoilMoistureDataStaleSensor(coordinator, entry),
        ]
    )


class _SoilMoistureBinaryBase(
    CoordinatorEntity[SoilMoistureCoordinator], BinarySensorEntity
):
    """Common properties of the binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SoilMoistureCoordinator,
        entry: ConfigEntry,
        translation_key: str,
    ) -> None:
        """Set up the parts shared by every binary sensor."""
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


class SoilMoistureWateringRequiredSensor(_SoilMoistureBinaryBase):
    """On when the soil is drier than the optimal range.

    Intentionally without a device class: ``moisture`` describes the soil
    itself and labels ``on`` as wet and ``off`` as dry, which is the opposite of
    what this sensor reports. Its state texts come from the ``state``
    translations instead (yes/no, or Ja/Nein in German).
    """

    _attr_icon = "mdi:watering-can"

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "watering_required")

    @property
    def is_on(self) -> bool | None:
        """Whether the moisture dropped below the optimal range."""
        data = self._data
        return None if data is None else data.watering_required

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the range, the current value and the time left."""
        data = self._data or SoilMoistureData()
        profile = self.coordinator.profile
        attributes: dict[str, Any] = {
            "current_moisture": data.current,
            "optimal_min": profile.optimal_min,
            "optimal_max": profile.optimal_max,
            **_watering_attributes(data),
        }
        if data.hours_until_min is not None:
            attributes["hours_until_optimal_min"] = round(data.hours_until_min, 1)
        return attributes


class SoilMoistureDataStaleSensor(_SoilMoistureBinaryBase):
    """On when the source sensor stopped reporting."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self, coordinator: SoilMoistureCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "data_stale")

    @property
    def _age_minutes(self) -> float | None:
        data = self._data
        if data is None or data.source_last_updated is None:
            return None
        age = (dt_util.utcnow() - data.source_last_updated).total_seconds() / 60
        return round(age, 1)

    @property
    def is_on(self) -> bool:
        """Whether the source data is too old or the update failed."""
        data = self._data
        if data is None or not self.coordinator.last_update_success:
            return True
        if data.data_stale:
            return True
        age = self._age_minutes
        return age is None or age > STALE_AFTER_MINUTES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose how old the last reading is and where it came from."""
        data = self._data or SoilMoistureData()
        attributes: dict[str, Any] = {
            "data_age_minutes": self._age_minutes,
            "stale_after_minutes": STALE_AFTER_MINUTES,
            "source_entity": self.coordinator.source_entity,
            **_watering_attributes(data),
        }
        if data.source_last_updated is not None:
            attributes["source_last_updated"] = data.source_last_updated.isoformat(
                timespec="seconds"
            )
        if data.source_battery is not None:
            attributes["source_battery"] = data.source_battery
        return attributes


def _watering_attributes(data: SoilMoistureData) -> dict[str, Any]:
    """Return the watering details shared by both binary sensors."""
    attributes: dict[str, Any] = {}
    if data.last_watering is not None:
        attributes["last_watering"] = data.last_watering.isoformat(
            timespec="seconds"
        )
        attributes["minutes_since_watering"] = data.minutes_since_watering
    if data.water_needed_ml is not None:
        attributes["water_needed_ml"] = data.water_needed_ml
    return attributes
