"""Tests for the plant profiles."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "soil_moisture"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"soil_moisture_{name}", MODULE_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")


def test_all_profiles_have_a_sane_range():
    assert const.PLANT_PROFILES
    for key, profile in const.PLANT_PROFILES.items():
        assert profile.key == key
        assert 0.0 <= profile.optimal_min < profile.optimal_max <= 100.0
        assert profile.optimal_min <= profile.optimal_target <= profile.optimal_max
        assert profile.icon.startswith("mdi:")


def test_forecast_sensor_horizons():
    assert const.FORECAST_SENSORS == {
        "moisture_1d": 1.0,
        "moisture_5d": 5.0,
        "moisture_7d": 7.0,
    }
    assert const.WEATHER_FORECAST_DAYS == 7.0


def test_plant_types_match_profiles():
    assert const.PLANT_TYPES == list(const.PLANT_PROFILES)
    assert const.DEFAULT_PLANT_TYPE in const.PLANT_PROFILES


def test_get_plant_profile_fallback():
    assert const.get_plant_profile("tomato").key == "tomato"
    assert const.get_plant_profile("does-not-exist").key == const.DEFAULT_PLANT_TYPE
    assert const.get_plant_profile(None).key == const.DEFAULT_PLANT_TYPE
