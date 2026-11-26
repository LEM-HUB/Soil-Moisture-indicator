"""Config flow for the Soil Moisture Indicator integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CONTAINER_VOLUME,
    CONF_HISTORY_HOURS,
    CONF_PLANT_TYPE,
    CONF_PREDICTION_HORIZON,
    CONF_SENSOR_TYPE,
    CONF_SOURCE_ENTITY,
    DEFAULT_CONTAINER_VOLUME,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_PLANT_TYPE,
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_SENSOR_TYPE,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    MAX_CONTAINER_VOLUME,
    MAX_HISTORY_HOURS,
    MAX_PREDICTION_HORIZON,
    MIN_CONTAINER_VOLUME,
    MIN_HISTORY_HOURS,
    MIN_PREDICTION_HORIZON,
    PLANT_TYPES,
    SENSOR_TYPES,
)


def _plant_type_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=PLANT_TYPES,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key=CONF_PLANT_TYPE,
        )
    )


def _sensor_type_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SENSOR_TYPES,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key=CONF_SENSOR_TYPE,
        )
    )


class _OptionalWeatherSelector(selector.EntitySelector):
    """Weather entity selector that treats an empty selection as automatic."""

    def __call__(self, data: Any) -> str | None:
        """Validate the selection, allowing it to be empty."""
        if data is None or data == "":
            return None
        return super().__call__(data)


def _weather_selector() -> _OptionalWeatherSelector:
    return _OptionalWeatherSelector(
        selector.EntitySelectorConfig(domain="weather")
    )


def _volume_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_CONTAINER_VOLUME,
            max=MAX_CONTAINER_VOLUME,
            step=0.5,
            unit_of_measurement="L",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class SoilMoistureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a soil moisture indicator."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SoilMoistureOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the source sensor and the plant type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            source_entity: str = user_input[CONF_SOURCE_ENTITY]
            plant_type: str = user_input[CONF_PLANT_TYPE]
            source_state = self.hass.states.get(source_entity)

            if source_state is None:
                errors[CONF_SOURCE_ENTITY] = "entity_not_found"
            else:
                await self.async_set_unique_id(f"{source_entity}_{plant_type}")
                self._abort_if_unique_id_configured()

                title = (user_input.get(CONF_NAME) or "").strip()
                if not title:
                    title = f"{source_state.name} ({plant_type})"
                return self.async_create_entry(
                    title=title,
                    data={
                        **user_input,
                        CONF_WEATHER_ENTITY: user_input.get(CONF_WEATHER_ENTITY)
                        or None,
                        CONF_CONTAINER_VOLUME: float(
                            user_input.get(CONF_CONTAINER_VOLUME) or 0.0
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PLANT_TYPE, default=DEFAULT_PLANT_TYPE
                ): _plant_type_selector(),
                vol.Required(
                    CONF_SENSOR_TYPE, default=DEFAULT_SENSOR_TYPE
                ): _sensor_type_selector(),
                vol.Optional(CONF_WEATHER_ENTITY): _weather_selector(),
                vol.Optional(
                    CONF_CONTAINER_VOLUME, default=DEFAULT_CONTAINER_VOLUME
                ): _volume_selector(),
                vol.Optional(CONF_NAME, default=""): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class SoilMoistureOptionsFlow(OptionsFlow):
    """Allow changing plant type, prediction horizon and history window."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        entry = self.config_entry
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **user_input,
                    CONF_WEATHER_ENTITY: user_input.get(CONF_WEATHER_ENTITY) or None,
                    CONF_CONTAINER_VOLUME: float(
                        user_input.get(CONF_CONTAINER_VOLUME) or 0.0
                    ),
                },
            )

        plant_type = entry.options.get(
            CONF_PLANT_TYPE, entry.data.get(CONF_PLANT_TYPE, DEFAULT_PLANT_TYPE)
        )
        horizon = entry.options.get(
            CONF_PREDICTION_HORIZON, DEFAULT_PREDICTION_HORIZON
        )
        history_hours = entry.options.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS)
        sensor_type = entry.options.get(
            CONF_SENSOR_TYPE,
            entry.data.get(CONF_SENSOR_TYPE, DEFAULT_SENSOR_TYPE),
        )
        weather_entity = entry.options.get(
            CONF_WEATHER_ENTITY, entry.data.get(CONF_WEATHER_ENTITY)
        )
        container_volume = entry.options.get(
            CONF_CONTAINER_VOLUME,
            entry.data.get(CONF_CONTAINER_VOLUME, DEFAULT_CONTAINER_VOLUME),
        )
        weather_field = (
            vol.Optional(
                CONF_WEATHER_ENTITY, description={"suggested_value": weather_entity}
            )
            if weather_entity
            else vol.Optional(CONF_WEATHER_ENTITY)
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PLANT_TYPE, default=plant_type
                ): _plant_type_selector(),
                vol.Required(
                    CONF_SENSOR_TYPE, default=sensor_type
                ): _sensor_type_selector(),
                vol.Required(
                    CONF_PREDICTION_HORIZON, default=horizon
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_PREDICTION_HORIZON,
                        max=MAX_PREDICTION_HORIZON,
                        step=1,
                        unit_of_measurement="h",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_HISTORY_HOURS, default=history_hours
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_HISTORY_HOURS,
                        max=MAX_HISTORY_HOURS,
                        step=1,
                        unit_of_measurement="h",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                weather_field: _weather_selector(),
                vol.Required(
                    CONF_CONTAINER_VOLUME, default=container_volume
                ): _volume_selector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"source_entity": entry.data[CONF_SOURCE_ENTITY]},
        )
