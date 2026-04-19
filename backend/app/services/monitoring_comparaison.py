from __future__ import annotations

from typing import Dict, List, Tuple
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
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


def _load_data(repo: DataRepository, blob_name: str) -> pd.DataFrame:
    df = repo.load_excel(blob_name, sheet_name="Donnees_Detaillees")
    if "Date" not in df.columns:
        raise AzureDataError("Missing Date column")
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return _replace_outliers_with_mean(df)


def detect_time_interval(df: pd.DataFrame) -> Tuple[pd.Timedelta, str]:
    if df.empty or len(df) < 2:
        return pd.Timedelta(minutes=5), "5min (defaut)"

    time_diffs = df.index.to_series().diff().dropna()
    time_diffs = time_diffs[time_diffs <= pd.Timedelta(hours=2)]
    if time_diffs.empty:
        return pd.Timedelta(minutes=5), "5min (defaut)"

    median_interval = time_diffs.median()
    total_seconds = median_interval.total_seconds()
    if total_seconds < 60:
        desc = f"{int(total_seconds)}sec"
    elif total_seconds < 3600:
        desc = f"{int(total_seconds/60)}min"
    else:
        desc = f"{int(total_seconds/3600)}h"
    return median_interval, desc


def fill_missing_data(df: pd.DataFrame, expected_interval: pd.Timedelta) -> pd.DataFrame:
    if df.empty:
        return df
    start_time = df.index.min()
    end_time = df.index.max()
    complete_index = pd.date_range(start=start_time, end=end_time, freq=expected_interval)
    df_complete = df.reindex(complete_index)
    df_complete["is_missing"] = df_complete["Puissance_moyenne_kW"].isna()
    df_complete["Puissance_moyenne_kW"] = df_complete["Puissance_moyenne_kW"].interpolate(method="linear")
    df_complete["Energie_periode_kWh"] = df_complete["Energie_periode_kWh"].interpolate(method="linear")
    return df_complete


def load_daily_data(repo: DataRepository, blob_name: str, selected_date: str) -> pd.DataFrame:
    df = _load_data(repo, blob_name)
    if df.empty:
        return pd.DataFrame()
    start_datetime = pd.to_datetime(selected_date)
    end_datetime = start_datetime + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return df.loc[start_datetime:end_datetime]


def get_date_range(repo: DataRepository, blob_name: str) -> Tuple[str, str]:
    df = _load_data(repo, blob_name)
    if df.empty:
        today = datetime.utcnow().date().isoformat()
        return today, today
    return df.index.min().date().isoformat(), df.index.max().date().isoformat()


def build_comparaison_puissance(
    repo: DataRepository,
    blob_name: str,
    reference_date: str,
    comparison_dates: List[str],
) -> Dict[str, object]:
    all_dates = [reference_date] + [d for d in comparison_dates if d and d != reference_date]

    daily_datasets: Dict[str, pd.DataFrame] = {}
    for date in all_dates:
        df = load_daily_data(repo, blob_name, date)
        if not df.empty:
            daily_datasets[date] = df

    if not daily_datasets:
        return {
            "reference_date": reference_date,
            "comparison_dates": comparison_dates,
            "interval": {"seconds": 300, "label": "5min (defaut)"},
            "series": [],
            "stats": [],
            "summary": {"total_points": 0, "total_interpolated": 0},
        }

    first_df = next(iter(daily_datasets.values()))
    expected_interval, interval_desc = detect_time_interval(first_df)

    processed: Dict[str, pd.DataFrame] = {}
    for date, df in daily_datasets.items():
        processed_df = fill_missing_data(df, expected_interval)
        if not processed_df.empty:
            processed[date] = processed_df

    series = []
    stats_payload = []
    total_points = 0
    total_interpolated = 0

    for date, df in processed.items():
        df_plot = df.copy()
        df_plot["heure_str"] = df_plot.index.strftime("%H:%M")
        df_plot["heure_float"] = df_plot.index.hour + df_plot.index.minute / 60.0

        points = []
        for _, row in df_plot.iterrows():
            points.append(
                {
                    "time": row["heure_str"],
                    "hour_float": float(row["heure_float"]),
                    "power_kw": None if pd.isna(row["Puissance_moyenne_kW"]) else float(row["Puissance_moyenne_kW"]),
                    "is_missing": bool(row["is_missing"]),
                }
            )

        series.append({"date": date, "points": points})

        df_real = df_plot[~df_plot["is_missing"]]
        points_count = int(len(df_real))
        interpolated_count = int(len(df_plot) - len(df_real))
        total_points += int(len(df_plot))
        total_interpolated += interpolated_count

        stats_payload.append(
            {
                "date": date,
                "points": points_count,
                "interpolated_points": interpolated_count,
                "avg_power_kw": float(df_real["Puissance_moyenne_kW"].mean()) if points_count > 0 else 0.0,
                "max_power_kw": float(df_real["Puissance_moyenne_kW"].max()) if points_count > 0 else 0.0,
                "min_power_kw": float(df_real["Puissance_moyenne_kW"].min()) if points_count > 0 else 0.0,
                "missing_pct": float(interpolated_count / len(df_plot) * 100) if len(df_plot) > 0 else 0.0,
            }
        )

    return {
        "reference_date": reference_date,
        "comparison_dates": comparison_dates,
        "interval": {"seconds": int(expected_interval.total_seconds()), "label": interval_desc},
        "series": series,
        "stats": stats_payload,
        "summary": {"total_points": total_points, "total_interpolated": total_interpolated},
    }
