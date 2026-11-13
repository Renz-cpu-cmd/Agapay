import numpy as np
import pandas as pd
import pytest
from app.ml.data_collection.preprocess import prepare_features, add_forecast_targets, chronological_split


def fixtures():
    # Synthetic unit-test fixtures; no claims of sensor observations.
    water = pd.DataFrame({"timestamp_utc": pd.date_range("2020-01-01", periods=20, freq="30min", tz="UTC"),
                          "station_id": "TEST_ONLY", "water_level": np.arange(20, dtype=float), "quality_flag": "good",
                          "water_level_unit": "m", "reference_datum": "fixture zero", "measurement_kind": "gauge_level"})
    rain = pd.DataFrame({"timestamp_utc": pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC"),
                         "station_id": "GRID_TEST_ONLY", "rainfall_mm": np.arange(10, dtype=float), "rainfall_interval_seconds": 3600})
    return water, rain


def test_past_only_features_and_exact_targets():
    water, rain = fixtures()
    result = prepare_features(water, rain, pairing_confirmed=True)
    assert result.rainfall_mm.iloc[1] == 0  # 00:30 cannot see 01:00 rainfall
    assert result.water_level_rise_per_minute.iloc[1] == 1 / 30
    assert result.rainfall_accumulation_3h_mm.iloc[6] == 6
    target = add_forecast_targets(result, measurement_kind="gauge_level")
    assert target.target_water_level_30m.iloc[0] == 1
    assert target.target_water_level_60m.iloc[0] == 2
    assert target.target_water_level_90m.iloc[0] == 3
    assert pd.isna(target.target_water_level_30m.iloc[-1])
    changed = water.copy()
    changed.loc[changed.index >= 10, "water_level"] = 10000
    another = prepare_features(changed, rain, pairing_confirmed=True)
    pd.testing.assert_series_equal(result.water_level_mean_60m.iloc[:10], another.water_level_mean_60m.iloc[:10])


def test_missing_and_rejected_targets_not_interpolated():
    water, rain = fixtures()
    water.loc[1, "quality_flag"] = "suspect"
    water = water.drop(index=2).reset_index(drop=True)
    result = add_forecast_targets(prepare_features(water, rain, pairing_confirmed=True), measurement_kind="gauge_level")
    assert pd.isna(result.target_water_level_30m.iloc[0])
    assert pd.isna(result.target_water_level_60m.iloc[0])
    assert result.water_level_missing.iloc[1] == 1


def test_missing_rain_interval_invalidates_accumulation():
    water, rain = fixtures()
    rain = rain.drop(index=2).reset_index(drop=True)
    result = prepare_features(water, rain, pairing_confirmed=True)
    assert pd.isna(result.rainfall_accumulation_3h_mm.iloc[6])
    assert result.rainfall_missing.iloc[4] == 1


def test_pairing_and_delay():
    water, rain = fixtures()
    with pytest.raises(ValueError, match="pairing"):
        prepare_features(water, rain)
    delayed = prepare_features(water, rain, pairing_confirmed=True, rainfall_available_delay_minutes=60)
    assert pd.isna(delayed.rainfall_mm.iloc[0])
    assert delayed.rainfall_mm.iloc[2] == 0
    with pytest.raises(ValueError):
        add_forecast_targets(delayed, measurement_kind="local_depth")


def test_split_purges_cross_boundary_labels():
    water, rain = fixtures()
    result = add_forecast_targets(prepare_features(water, rain, pairing_confirmed=True), measurement_kind="gauge_level")
    split = chronological_split(result, train_fraction=0.5, validation_fraction=0.3)
    assert split["train"].target_at_90m.max() < split["validation"].timestamp_utc.min()
    assert split["validation"].target_at_90m.max() < split["test"].timestamp_utc.min()
    split = chronological_split(result, train_fraction=0.5, validation_fraction=0.3, embargo_minutes=0)
    assert split["train"].target_at_90m.max() < result.timestamp_utc.iloc[10]


def test_preprocessing_rejects_ambiguous_series():
    water, rain = fixtures()
    with pytest.raises(ValueError): prepare_features(water.iloc[::-1], rain, pairing_confirmed=True)
    water.loc[2, "water_level_unit"] = "cm"
    with pytest.raises(ValueError): prepare_features(water, rain, pairing_confirmed=True)
