from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from .data_repository import DataRepository, AzureDataError


def _replace_outliers_with_mean(df: pd.DataFrame, threshold: int = 50) -> pd.DataFrame:
    df_cleaned = df.copy()
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        col_mean = df_cleaned[col].mean()
        z_scores = np.abs(stats.zscore(df_cleaned[col]))
        df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)
    return df_cleaned


class FakeNILMAlgorithm:
    def __init__(self) -> None:
        self.components = {
            "Chauffage": {"color": "#FF6B6B", "winter_factor": 2.5, "base_ratio": 0.35},
            "Eclairage": {"color": "#4ECDC4", "base_ratio": 0.15},
            "Equipements": {"color": "#45B7D1", "base_ratio": 0.20},
            "Climatisation": {"color": "#96CEB4", "summer_factor": 2.0, "base_ratio": 0.15},
            "Informatique": {"color": "#FFEAA7", "base_ratio": 0.10},
            "Autres": {"color": "#DDA0DD", "base_ratio": 0.05},
        }

    def decompose_signal(self, df: pd.DataFrame, aggregation: str) -> tuple[Dict[str, np.ndarray], Dict[str, np.ndarray], pd.Series]:
        resample_map = {
            "Heure": "H",
            "Jour": "D",
            "Semaine": "W-MON",
            "Mois": "M",
        }
        freq = resample_map.get(aggregation, "D")
        resampled = df.resample(freq).agg(
            {
                "Energie_periode_kWh": "sum",
                "Puissance_moyenne_kW": "mean",
            }
        )

        total_energy = resampled["Energie_periode_kWh"].fillna(0)
        timestamps = total_energy.index

        decomposed_raw: Dict[str, np.ndarray] = {}
        confidence_intervals: Dict[str, np.ndarray] = {}

        for component, config in self.components.items():
            comp_values, confidence = self._calculate_component(
                total_energy.to_numpy(),
                timestamps,
                component,
                config,
                aggregation,
            )
            decomposed_raw[component] = comp_values
            confidence_intervals[component] = confidence

        sum_components = np.zeros(len(total_energy))
        for values in decomposed_raw.values():
            sum_components += values

        decomposed: Dict[str, np.ndarray] = {}
        total_array = total_energy.to_numpy()
        for component, values in decomposed_raw.items():
            normalized = np.where(sum_components > 0, values * (total_array / sum_components), 0)
            normalized = np.minimum(normalized, total_array)
            decomposed[component] = normalized

        return decomposed, confidence_intervals, total_energy

    def _calculate_component(
        self,
        total_energy: np.ndarray,
        timestamps: pd.DatetimeIndex,
        component_name: str,
        config: Dict[str, float],
        aggregation: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        base_consumption = total_energy * config["base_ratio"]

        if component_name == "Chauffage":
            seasonal_factor = self._heating_pattern(timestamps)
            daily_factor = self._heating_daily_pattern(timestamps, aggregation)
        elif component_name == "Eclairage":
            seasonal_factor = self._lighting_seasonal_pattern(timestamps)
            daily_factor = self._lighting_daily_pattern(timestamps, aggregation)
        elif component_name == "Equipements":
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = self._office_equipment_pattern(timestamps, aggregation)
        elif component_name == "Climatisation":
            seasonal_factor = self._cooling_pattern(timestamps)
            daily_factor = self._cooling_daily_pattern(timestamps, aggregation)
        elif component_name == "Informatique":
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = self._it_equipment_pattern(timestamps, aggregation)
        else:
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = 0.8 + 0.4 * np.random.random(len(timestamps))

        component_values = base_consumption * seasonal_factor * daily_factor
        noise = np.random.normal(0, 0.1, len(component_values))
        component_values = component_values * (1 + noise)
        component_values = np.maximum(component_values, 0)

        uncertainty = 0.3 if component_name in ["Chauffage", "Climatisation"] else 0.2
        confidence = component_values * uncertainty

        return component_values, confidence

    def _heating_pattern(self, timestamps: pd.DatetimeIndex) -> np.ndarray:
        months = np.array([ts.month for ts in timestamps])
        days = np.array([ts.day for ts in timestamps])
        seasonal = 2.0 - 1.5 * np.cos(2 * np.pi * (months - 1) / 12)
        no_heating_mask = (
            (months == 6)
            | (months == 7)
            | (months == 8)
            | ((months == 9) & (days <= 15))
        )
        seasonal[no_heating_mask] = 0.0
        return seasonal

    def _heating_daily_pattern(self, timestamps: pd.DatetimeIndex, aggregation: str) -> np.ndarray:
        if aggregation == "Heure":
            hours = np.array([ts.hour for ts in timestamps])
            daily = 0.7 + 0.3 * (np.sin(2 * np.pi * (hours - 6) / 24) + 0.5)
            daily += 0.2 * np.maximum(0, np.sin(np.pi * (hours - 17) / 10))
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.1, 0.8)
        return daily

    def _lighting_seasonal_pattern(self, timestamps: pd.DatetimeIndex) -> np.ndarray:
        months = np.array([ts.month for ts in timestamps])
        seasonal = 1.3 - 0.6 * np.cos(2 * np.pi * (months - 1) / 12)
        return seasonal

    def _lighting_daily_pattern(self, timestamps: pd.DatetimeIndex, aggregation: str) -> np.ndarray:
        if aggregation == "Heure":
            hours = np.array([ts.hour for ts in timestamps])
            morning_peak = np.maximum(0, np.sin(np.pi * (hours - 5) / 6))
            evening_peak = np.maximum(0, np.sin(np.pi * (hours - 15) / 8))
            daily = 0.3 + 0.4 * (morning_peak + evening_peak)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.2, 0.6)
        return daily

    def _cooling_pattern(self, timestamps: pd.DatetimeIndex) -> np.ndarray:
        months = np.array([ts.month for ts in timestamps])
        days = np.array([ts.day for ts in timestamps])
        seasonal = np.zeros(len(timestamps))
        cooling_mask = (
            (months == 6)
            | (months == 7)
            | (months == 8)
            | ((months == 9) & (days <= 15))
        )
        for i, ts in enumerate(timestamps):
            if cooling_mask[i]:
                if ts.month == 6:
                    seasonal[i] = 1.0 + (ts.day / 30) * 1.0
                elif ts.month in [7, 8]:
                    seasonal[i] = 2.0
                elif ts.month == 9 and ts.day <= 15:
                    seasonal[i] = 2.0 - ((ts.day / 15) * 1.0)
        return seasonal

    def _cooling_daily_pattern(self, timestamps: pd.DatetimeIndex, aggregation: str) -> np.ndarray:
        if aggregation == "Heure":
            hours = np.array([ts.hour for ts in timestamps])
            daily = 0.5 + 0.5 * np.maximum(0, np.sin(np.pi * (hours - 8) / 12))
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.1, 0.7)
        return daily

    def _office_equipment_pattern(self, timestamps: pd.DatetimeIndex, aggregation: str) -> np.ndarray:
        if aggregation == "Heure":
            hours = np.array([ts.hour for ts in timestamps])
            daily = np.where((hours >= 8) & (hours <= 18), 1.2, 0.4)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.0, 0.3)
        return daily

    def _it_equipment_pattern(self, timestamps: pd.DatetimeIndex, aggregation: str) -> np.ndarray:
        if aggregation == "Heure":
            hours = np.array([ts.hour for ts in timestamps])
            daily = np.where((hours >= 7) & (hours <= 19), 1.1, 0.7)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.0, 0.5)
        return daily


def build_nilm(
    repo: DataRepository,
    blob_name: str,
    start_date: str | None,
    end_date: str | None,
    aggregation: str,
) -> Dict[str, object]:
    df = repo.load_excel(blob_name, sheet_name="Donnees_Detaillees")
    if "Date" not in df.columns:
        raise AzureDataError("Missing Date column")

    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    df = _replace_outliers_with_mean(df)

    min_date = df.index.min().date().isoformat()
    max_date = df.index.max().date().isoformat()
    start_date = start_date or min_date
    end_date = end_date or max_date

    filtered_df = df.loc[str(start_date):str(end_date)]
    if filtered_df.empty:
        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "aggregation": aggregation,
            "total_series": [],
            "reconstruction_series": [],
            "components": [],
            "stats": {},
        }

    aggregation = aggregation.capitalize()
    if aggregation not in ["Heure", "Jour", "Semaine", "Mois"]:
        aggregation = "Jour"

    nilm = FakeNILMAlgorithm()
    decomposed, confidence, total_energy = nilm.decompose_signal(filtered_df, aggregation)

    total_series = [
        {"timestamp": idx.isoformat(), "value": float(val)}
        for idx, val in total_energy.items()
    ]

    reconstruction = np.zeros(len(total_energy))
    components_payload = []
    component_totals = {}

    for name, values in decomposed.items():
        reconstruction += values
        series = [
            {"timestamp": total_energy.index[i].isoformat(), "value": float(values[i])}
            for i in range(len(values))
        ]
        conf_series = [
            {"timestamp": total_energy.index[i].isoformat(), "value": float(confidence[name][i])}
            for i in range(len(values))
        ]
        total_val = float(values.sum())
        component_totals[name] = total_val
        components_payload.append(
            {
                "name": name,
                "color": nilm.components[name]["color"],
                "series": series,
                "confidence": conf_series,
                "total_kwh": total_val,
            }
        )

    reconstruction_series = [
        {"timestamp": total_energy.index[i].isoformat(), "value": float(reconstruction[i])}
        for i in range(len(reconstruction))
    ]

    total_real = float(total_energy.sum())
    sum_decomposed = float(sum(component_totals.values()))
    conservation_error_pct = abs(sum_decomposed - total_real) / total_real * 100 if total_real > 0 else 0.0

    primary_component = None
    if component_totals:
        primary_component = max(component_totals, key=component_totals.get)

    stats = {
        "total_energy_kwh": total_real,
        "sum_components_kwh": sum_decomposed,
        "conservation_pct": 100 - conservation_error_pct,
        "primary_component": primary_component,
        "components": [
            {
                "name": name,
                "total_kwh": total_val,
                "percent": (total_val / total_real * 100) if total_real > 0 else 0.0,
            }
            for name, total_val in component_totals.items()
        ],
    }

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "aggregation": aggregation,
        "total_series": total_series,
        "reconstruction_series": reconstruction_series,
        "components": components_payload,
        "stats": stats,
    }
