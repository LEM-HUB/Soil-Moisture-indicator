"""Constants for the Soil Moisture Indicator integration.

This module intentionally has no Home Assistant imports so it can be imported
by the unit tests without a running Home Assistant instance.
"""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "soil_moisture"
NAME = "Soil Moisture Indicator"
MANUFACTURER = "Soil Moisture Indicator"
VERSION = "1.2.1"

CONF_SOURCE_ENTITY = "source_entity"
CONF_PLANT_TYPE = "plant_type"
CONF_NAME = "name"
CONF_PREDICTION_HORIZON = "prediction_horizon"
CONF_HISTORY_HOURS = "history_hours"
CONF_WEATHER_ENTITY = "weather_entity"

DEFAULT_PLANT_TYPE = "houseplant"
DEFAULT_PREDICTION_HORIZON = 12.0
DEFAULT_HISTORY_HOURS = 24.0
DEFAULT_UPDATE_INTERVAL_MINUTES = 5

MIN_PREDICTION_HORIZON = 1.0
MAX_PREDICTION_HORIZON = 72.0
MIN_HISTORY_HOURS = 2.0
MAX_HISTORY_HOURS = 168.0

MOISTURE_UNIT = "%"

# Fixed forecast sensors, mapping their translation key to the number of days.
FORECAST_SENSORS: dict[str, float] = {
    "moisture_1d": 1.0,
    "moisture_5d": 5.0,
    "moisture_7d": 7.0,
}

# Horizon of the forecast sensor that uses the weather forecast.
WEATHER_FORECAST_DAYS = 7.0

# The weather forecast is cached for this long between coordinator updates.
WEATHER_FORECAST_CACHE_MINUTES = 30


@dataclass(frozen=True)
class PlantProfile:
    """Optimal soil moisture range for one plant type.

    All values are soil moisture percentages as reported by a capacitive or
    resistive soil moisture sensor (0 % = air dry, 100 % = saturated).
    """

    key: str
    optimal_min: float
    optimal_max: float
    icon: str = "mdi:leaf"

    @property
    def optimal_target(self) -> float:
        """Return the middle of the optimal range."""
        return round((self.optimal_min + self.optimal_max) / 2, 1)


PLANT_PROFILES: dict[str, PlantProfile] = {
    "houseplant": PlantProfile("houseplant", 40.0, 60.0, "mdi:potted-plant"),
    "tomato": PlantProfile("tomato", 60.0, 80.0, "mdi:food-apple"),
    "pepper": PlantProfile("pepper", 55.0, 70.0),
    "cucumber": PlantProfile("cucumber", 65.0, 85.0),
    "zucchini": PlantProfile("zucchini", 60.0, 80.0),
    "lettuce": PlantProfile("lettuce", 60.0, 75.0),
    "potato": PlantProfile("potato", 50.0, 70.0),
    "strawberry": PlantProfile("strawberry", 55.0, 75.0),
    "blueberry": PlantProfile("blueberry", 55.0, 75.0),
    "citrus": PlantProfile("citrus", 45.0, 65.0, "mdi:fruit-citrus"),
    "avocado": PlantProfile("avocado", 50.0, 70.0),
    "rose": PlantProfile("rose", 50.0, 70.0, "mdi:flower"),
    "herb": PlantProfile("herb", 45.0, 65.0),
    "fern": PlantProfile("fern", 60.0, 80.0),
    "lawn": PlantProfile("lawn", 40.0, 60.0, "mdi:grass"),
    "hedge": PlantProfile("hedge", 40.0, 65.0, "mdi:tree"),
    "tree": PlantProfile("tree", 40.0, 65.0, "mdi:tree"),
    "bonsai": PlantProfile("bonsai", 50.0, 70.0, "mdi:tree"),
    "orchid": PlantProfile("orchid", 35.0, 55.0, "mdi:flower"),
    "succulent": PlantProfile("succulent", 15.0, 35.0, "mdi:cactus"),
    "aloe_vera": PlantProfile("aloe_vera", 10.0, 30.0, "mdi:leaf"),
    "agave": PlantProfile("agave", 10.0, 30.0, "mdi:cactus"),
    "snake_plant": PlantProfile("snake_plant", 15.0, 30.0, "mdi:leaf"),
    "zz_plant": PlantProfile("zz_plant", 15.0, 35.0, "mdi:leaf"),
    "yucca": PlantProfile("yucca", 20.0, 40.0, "mdi:tree"),
    "pothos": PlantProfile("pothos", 35.0, 55.0, "mdi:leaf"),
    "monstera": PlantProfile("monstera", 40.0, 60.0, "mdi:leaf"),
    "palm": PlantProfile("palm", 50.0, 70.0, "mdi:palm-tree"),
    "bamboo": PlantProfile("bamboo", 55.0, 75.0, "mdi:tree"),
    "peace_lily": PlantProfile("peace_lily", 55.0, 75.0, "mdi:flower"),
    "calathea": PlantProfile("calathea", 60.0, 80.0, "mdi:leaf"),
    "venus_flytrap": PlantProfile("venus_flytrap", 55.0, 80.0, "mdi:flower"),
    "air_plant": PlantProfile("air_plant", 30.0, 50.0, "mdi:flower"),
    "lavender": PlantProfile("lavender", 25.0, 45.0, "mdi:flower"),
    "rosemary": PlantProfile("rosemary", 25.0, 45.0, "mdi:leaf"),
    "chili": PlantProfile("chili", 55.0, 70.0, "mdi:chili-mild"),
}

PLANT_TYPES: list[str] = list(PLANT_PROFILES)


def get_plant_profile(key: str | None) -> PlantProfile:
    """Return the profile for ``key``, falling back to the default plant type."""
    if key and key in PLANT_PROFILES:
        return PLANT_PROFILES[key]
    return PLANT_PROFILES[DEFAULT_PLANT_TYPE]
