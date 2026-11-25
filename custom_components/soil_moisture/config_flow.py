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
    CONF_HISTORY_HOURS,
    CONF_PLANT_TYPE,
    CONF_PREDICTION_HORIZON,
    CONF_SOURCE_ENTITY,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_PLANT_TYPE,
    DEFAULT_PREDICTION_HORIZON,
    DOMAIN,
    MAX_HISTORY_HOURS,
    MAX_PREDICTION_HORIZON,
    MIN_HISTORY_HOURS,
    MIN_PREDICTION_HORIZON,
    PLANT_TYPES,
)


def _plant_type_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=PLANT_TYPES,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key=CONF_PLANT_TYPE,
        )
    )


class SoilMoistureConfigFlow(ConfigFlow):
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
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PLANT_TYPE, default=DEFAULT_PLANT_TYPE
                ): _plant_type_selector(),
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
            return self.async_create_entry(title="", data=user_input)

        plant_type = entry.options.get(
            CONF_PLANT_TYPE, entry.data.get(CONF_PLANT_TYPE, DEFAULT_PLANT_TYPE)
        )
        horizon = entry.options.get(
            CONF_PREDICTION_HORIZON, DEFAULT_PREDICTION_HORIZON
        )
        history_hours = entry.options.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PLANT_TYPE, default=plant_type
                ): _plant_type_selector(),
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
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"source_entity": entry.data[CONF_SOURCE_ENTITY]},
        )
