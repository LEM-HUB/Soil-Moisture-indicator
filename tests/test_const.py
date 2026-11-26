"""Tests for the plant profiles."""

from __future__ import annotations

import importlib.util
import json
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
    assert sorted(const.PLANT_TYPES) == sorted(const.PLANT_PROFILES)
    assert len(set(const.PLANT_TYPES)) == len(const.PLANT_TYPES)
    assert const.DEFAULT_PLANT_TYPE in const.PLANT_PROFILES


def _german_labels() -> dict[str, str]:
    path = MODULE_DIR / "translations" / "de.json"
    return json.loads(path.read_text(encoding="utf-8"))["selector"]["plant_type"][
        "options"
    ]


def _sort_key(label: str) -> str:
    """Fold umlauts so German labels sort the way a reader expects."""
    return (
        label.lower()
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ß", "ss")
    )


def test_plant_types_are_sorted_alphabetically():
    labels = _german_labels()
    assert sorted(labels) == sorted(const.PLANT_TYPES)
    assert const.PLANT_TYPES == sorted(
        const.PLANT_TYPES, key=lambda key: _sort_key(labels[key])
    )


def test_calibrate_profile_capacitive_is_unchanged():
    profile = const.get_plant_profile("houseplant")
    assert const.calibrate_profile(profile, const.SENSOR_TYPE_CAPACITIVE) == profile


def test_calibrate_profile_shifts_resistive_thresholds():
    profile = const.get_plant_profile("tomato")
    calibrated = const.calibrate_profile(profile, const.SENSOR_TYPE_RESISTIVE)
    assert calibrated.key == profile.key
    assert calibrated.icon == profile.icon
    assert calibrated.optimal_min == profile.optimal_min - 8
    assert calibrated.optimal_max == profile.optimal_max - 8
    assert calibrated.optimal_min <= calibrated.optimal_target
    assert calibrated.optimal_target <= calibrated.optimal_max


def test_resistive_shift_keeps_every_window_usable():
    for key in const.PLANT_TYPES:
        profile = const.get_plant_profile(key)
        calibrated = const.calibrate_profile(profile, const.SENSOR_TYPE_RESISTIVE)
        assert 0.0 <= calibrated.optimal_min < calibrated.optimal_max <= 100.0
        assert (
            calibrated.optimal_max - calibrated.optimal_min
            >= const.MIN_OPTIMAL_RANGE_WIDTH - 0.05
        )


def test_unknown_sensor_type_falls_back_to_capacitive():
    profile = const.get_plant_profile("rose")
    assert const.sensor_type_or_default("nonsense") == const.DEFAULT_SENSOR_TYPE
    assert const.calibrate_profile(profile, "nonsense") == profile


def test_get_plant_profile_fallback():
    assert const.get_plant_profile("tomato").key == "tomato"
    assert const.get_plant_profile("does-not-exist").key == const.DEFAULT_PLANT_TYPE
    assert const.get_plant_profile(None).key == const.DEFAULT_PLANT_TYPE
