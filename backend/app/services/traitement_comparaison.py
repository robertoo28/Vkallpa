from __future__ import annotations

from typing import Dict
from datetime import datetime

import pandas as pd
import numpy as np
from scipy import stats

from .data_repository import DataRepository, AzureDataError


EURO_PER_KWH = 0.17


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


def _calculate_metrics(
    period_a: pd.DataFrame,
    period_b: pd.DataFrame,
    name_a: str,
    name_b: str,
    metric_column: str,
) -> Dict[str, object]:
    total_a = float(period_a[metric_column].sum())
    total_b = float(period_b[metric_column].sum())
    evolution_pct = ((total_b - total_a) / total_a * 100) if total_a > 0 else 0.0

    avg_daily_a = float(period_a.resample("D").sum()[metric_column].mean())
    avg_daily_b = float(period_b.resample("D").sum()[metric_column].mean())
    avg_evolution_pct = ((avg_daily_b - avg_daily_a) / avg_daily_a * 100) if avg_daily_a > 0 else 0.0

    max_a = float(period_a[metric_column].max())
    max_b = float(period_b[metric_column].max())
    max_evolution_pct = ((max_b - max_a) / max_a * 100) if max_a > 0 else 0.0

    cv_a = (period_a[metric_column].std() / period_a[metric_column].mean() * 100) if period_a[metric_column].mean() > 0 else 0.0
    cv_b = (period_b[metric_column].std() / period_b[metric_column].mean() * 100) if period_b[metric_column].mean() > 0 else 0.0

    euro_variation = None
    euro_variation_daily = None
    if metric_column == "Energie_periode_kWh":
        euro_variation = (total_b - total_a) * EURO_PER_KWH
        euro_variation_daily = (avg_daily_b - avg_daily_a) * EURO_PER_KWH

    return {
        "names": [name_a, name_b],
        "total_consumption": [total_a, total_b],
        "total_evolution_pct": evolution_pct,
        "avg_daily_consumption": [avg_daily_a, avg_daily_b],
        "avg_daily_evolution_pct": avg_evolution_pct,
        "max_consumption": [max_a, max_b],
        "max_evolution_pct": max_evolution_pct,
        "coefficient_variation": [cv_a, cv_b],
        "nb_days": [int(len(period_a.resample("D").sum())), int(len(period_b.resample("D").sum()))],
        "euro_variation": euro_variation,
        "euro_variation_daily": euro_variation_daily,
    }


def build_comparaison_periode(
    repo: DataRepository,
    blob_name: str,
    start_a: str,
    end_a: str,
    start_b: str,
    end_b: str,
    metric: str,
    normalize_days: bool,
    exclude_weekends: bool,
) -> Dict[str, object]:
    df = _load_data(repo, blob_name)

    period_a = df.loc[str(start_a):str(end_a)]
    period_b = df.loc[str(start_b):str(end_b)]

    if exclude_weekends:
        period_a = period_a[period_a.index.dayofweek < 5]
        period_b = period_b[period_b.index.dayofweek < 5]

    if period_a.empty or period_b.empty:
        return {
            "metric": metric,
            "period_a": {"start": start_a, "end": end_a},
            "period_b": {"start": start_b, "end": end_b},
            "metrics": {},
            "normalize_days": normalize_days,
            "exclude_weekends": exclude_weekends,
        }

    metric_column = "Energie_periode_kWh" if metric == "Energie" else "Puissance_moyenne_kW"
    metrics = _calculate_metrics(period_a, period_b, "Periode A", "Periode B", metric_column)

    return {
        "metric": metric,
        "period_a": {"start": start_a, "end": end_a},
        "period_b": {"start": start_b, "end": end_b},
        "metrics": metrics,
        "normalize_days": normalize_days,
        "exclude_weekends": exclude_weekends,
    }
