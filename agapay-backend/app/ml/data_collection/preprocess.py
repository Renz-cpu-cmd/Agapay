"""Causal features and exact observed targets; no interpolation or model fitting."""
from collections.abc import Collection
import numpy as np
import pandas as pd


def checked_times(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["timestamp_utc"] = pd.to_datetime(result.timestamp_utc, utc=True, errors="raise", format="mixed")
    if result.timestamp_utc.isna().any() or result.timestamp_utc.duplicated().any() or not result.timestamp_utc.is_monotonic_increasing:
        raise ValueError("Preparation requires non-missing, unique, chronological timestamps")
    if result.empty or result.station_id.nunique(dropna=False) != 1 or result.station_id.isna().any():
        raise ValueError("Prepare one identified station at a time")
    return result


def prepare_features(water: pd.DataFrame, rainfall: pd.DataFrame, *, pairing_confirmed: bool = False,
                     accepted_quality_flags: Collection[str] = ("valid", "good"),
                     rainfall_available_delay_minutes: int = 0) -> pd.DataFrame:
    """Caller must confirm watershed/grid pairing; rainfall joins only backward.

    The delay models historical product availability for retrospective studies;
    zero means a retrospective analysis, not a claim of online availability.
    Hourly amounts stay at their native resolution and are never repeated/summed
    across high-frequency water observations.
    """
    if not pairing_confirmed:
        raise ValueError("Confirm hydrological station/grid pairing before alignment")
    if rainfall_available_delay_minutes < 0:
        raise ValueError("Availability delay cannot be negative")
    water, rainfall = checked_times(water), checked_times(rainfall)
    for column in ("water_level_unit", "reference_datum", "measurement_kind"):
        if column not in water or water[column].isna().any() or water[column].nunique() != 1:
            raise ValueError(f"Water series needs one explicit {column}")
    water["water_level"] = pd.to_numeric(water.water_level, errors="coerce")
    water.loc[~np.isfinite(water.water_level) | ~water.quality_flag.isin(accepted_quality_flags), "water_level"] = np.nan
    indexed = water.set_index("timestamp_utc")
    minutes = indexed.index.to_series().diff().dt.total_seconds() / 60
    indexed["water_level_rise_per_minute"] = indexed.water_level.diff() / minutes
    indexed["water_level_mean_60m"] = indexed.water_level.rolling("60min", min_periods=1).mean()
    indexed["water_level_missing"] = indexed.water_level.isna().astype(int)
    rainfall["rainfall_mm"] = pd.to_numeric(rainfall.rainfall_mm, errors="coerce")
    rainfall.loc[~np.isfinite(rainfall.rainfall_mm) | rainfall.rainfall_mm.lt(0), "rainfall_mm"] = np.nan
    intervals = pd.to_numeric(rainfall.rainfall_interval_seconds, errors="coerce")
    if intervals.isna().any() or intervals.nunique() != 1 or intervals.iloc[0] <= 0:
        raise ValueError("Explicit constant rainfall accumulation interval required")
    interval = int(intervals.iloc[0])
    if interval != intervals.iloc[0] or 10800 % interval:
        raise ValueError("Rainfall interval must divide the three-hour window exactly")
    rain_indexed = rainfall.set_index("timestamp_utc")
    # Forbid sums that omit an interval: reindex solely to introduce missingness,
    # never fill or fabricate observed rainfall amounts.
    rain_indexed = rain_indexed.reindex(pd.date_range(rain_indexed.index[0], rain_indexed.index[-1], freq=pd.Timedelta(seconds=interval)))
    if not rainfall.timestamp_utc.isin(rain_indexed.index).all():
        raise ValueError("Rainfall observations are off their declared cadence")
    rain_indexed.index.name = "rainfall_observed_at_utc"
    rain_indexed["rainfall_accumulation_3h_mm"] = rain_indexed.rainfall_mm.rolling("3h", min_periods=10800 // interval).sum()
    rain_indexed["rainfall_available_at_utc"] = rain_indexed.index + pd.Timedelta(minutes=rainfall_available_delay_minutes)
    right = rain_indexed.reset_index()[["rainfall_observed_at_utc", "rainfall_available_at_utc", "rainfall_mm", "rainfall_accumulation_3h_mm"]]
    result = pd.merge_asof(indexed.reset_index(), right, left_on="timestamp_utc", right_on="rainfall_available_at_utc",
                           direction="backward", tolerance=pd.Timedelta(seconds=interval))
    result["rainfall_missing"] = result.rainfall_mm.isna().astype(int)
    result["rainfall_age_minutes"] = (result.timestamp_utc - result.rainfall_observed_at_utc).dt.total_seconds() / 60
    result.attrs["rainfall_location_id"] = rainfall.station_id.iloc[0]
    result.attrs["availability_delay_minutes"] = rainfall_available_delay_minutes
    return result


def add_forecast_targets(features: pd.DataFrame, *, measurement_kind: str,
                         horizons: tuple[int, ...] = (30, 60, 90)) -> pd.DataFrame:
    """Exact timestamp matches only; invalid/unaccepted-quality targets stay null."""
    if measurement_kind not in ("gauge_level", "water_surface_elevation", "local_depth"):
        raise ValueError("Explicit observed measurement_kind required")
    result = checked_times(features)
    if "water_level" not in result or "measurement_kind" not in result or not result.measurement_kind.eq(measurement_kind).all():
        raise ValueError("Matched observed water-level records with consistent measurement semantics are required")
    # Direct callers must not turn provider-flagged or unreviewed values into truth.
    if "water_level_missing" not in result:
        raise ValueError("Use prepare_features to apply the explicit quality acceptance policy first")
    observed = pd.Series(result.water_level.where(result.water_level_missing.eq(0)).to_numpy(), index=result.timestamp_utc)
    for horizon in horizons:
        if horizon <= 0:
            raise ValueError("Forecast horizons must be positive")
        at = result.timestamp_utc + pd.Timedelta(minutes=horizon)
        result[f"target_water_level_{horizon}m"] = observed.reindex(pd.DatetimeIndex(at)).to_numpy()
        result[f"target_at_{horizon}m"] = at
    result.attrs["target_kind"] = measurement_kind
    return result


def chronological_split(frame: pd.DataFrame, *, train_fraction: float = 0.7,
                        validation_fraction: float = 0.15, embargo_minutes: int = 90) -> dict[str, pd.DataFrame]:
    """Purge examples whose target horizon crosses a partition boundary."""
    if not (0 < train_fraction < 1 and 0 < validation_fraction < 1 and train_fraction + validation_fraction < 1):
        raise ValueError("Fractions must leave nonempty train, validation and test portions")
    if embargo_minutes < 0:
        raise ValueError("Embargo must be nonnegative")
    frame = checked_times(frame)
    first, second = int(len(frame) * train_fraction), int(len(frame) * (train_fraction + validation_fraction))
    if first == 0 or second <= first or second >= len(frame):
        raise ValueError("Too few observations for three chronological partitions")
    partitions = {"train": frame.iloc[:first].copy(), "validation": frame.iloc[first:second].copy(), "test": frame.iloc[second:].copy()}
    target_columns = [c for c in frame if c.startswith("target_at_")]
    for name, boundary in (("train", frame.timestamp_utc.iloc[first]), ("validation", frame.timestamp_utc.iloc[second])):
        part = partitions[name]
        keep = part.timestamp_utc + pd.Timedelta(minutes=embargo_minutes) < boundary
        for column in target_columns:
            keep &= pd.to_datetime(part[column], utc=True).lt(boundary)
        partitions[name] = part.loc[keep].copy()
    return partitions
