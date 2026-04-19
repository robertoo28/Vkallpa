from __future__ import annotations

from typing import List, Dict

import pandas as pd
import numpy as np
from scipy import stats

from .data_repository import DataRepository, AzureDataError


VACANCES = [
    ("20/12/2020", "3/1/2021"), ("21/2/2021", "28/2/2021"), ("5/4/2021", "5/4/2021"),
    ("25/4/2021", "2/5/2021"), ("13/5/2021", "16/5/2021"), ("24/5/2021", "24/5/2021"),
    ("17/7/2021", "22/8/2021"), ("1/11/2021", "1/11/2021"), ("11/11/2021", "11/11/2021"),
    ("18/12/2021", "3/1/2022"), ("26/2/2022", "6/3/2022"), ("18/4/2022", "18/4/2022"),
    ("23/4/2022", "8/5/2022"), ("26/5/2022", "29/5/2022"), ("23/7/2022", "21/8/2022"),
    ("29/10/2022", "6/11/2022"), ("1/11/2022", "1/11/2022"), ("11/11/2022", "11/11/2022"),
    ("17/12/2022", "2/1/2023"), ("25/2/2023", "6/3/2023"), ("10/4/2023", "10/4/2023"),
    ("24/4/2023", "7/5/2023"), ("1/5/2023", "1/5/2023"), ("8/5/2023", "8/5/2023"),
    ("18/5/2023", "18/5/2023"), ("23/7/2023", "19/8/2023"), ("28/10/2023", "5/11/2023"),
    ("1/11/2023", "1/11/2023"), ("23/12/2023", "8/1/2024"), ("17/2/2024", "26/2/2024"),
    ("1/4/2022", "1/4/2022"), ("6/4/2024", "22/4/2024"), ("1/5/2024", "1/5/2024"),
    ("8/5/2024", "13/5/2024"), ("20/7/2024", "18/8/2024"), ("26/10/2024", "3/11/2024"),
    ("1/11/2024", "1/11/2024"), ("11/11/2024", "11/11/2024"), ("21/12/2024", "5/1/2025"),
    ("22/2/2025", "3/3/2025"), ("12/4/2025", "28/4/2025"), ("28/5/2025", "2/6/2025"),
]


def _replace_outliers_with_mean(df: pd.DataFrame, threshold: int = 50) -> pd.DataFrame:
    df_cleaned = df.copy()
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        col_mean = df_cleaned[col].mean()
        z_scores = np.abs(stats.zscore(df_cleaned[col]))
        df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)

    return df_cleaned


def _prepare_vacances_df() -> pd.DataFrame:
    vacances_df = pd.DataFrame(VACANCES, columns=["start", "end"])
    vacances_df["start"] = pd.to_datetime(vacances_df["start"], dayfirst=True)
    vacances_df["end"] = pd.to_datetime(vacances_df["end"], dayfirst=True)
    return vacances_df


def _vacances_in_range(filtered_df: pd.DataFrame, start_date: str, end_date: str) -> List[Dict[str, str]]:
    if filtered_df.empty:
        return []
    vacances_df = _prepare_vacances_df()
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    vacances_filtrees = vacances_df[
        (vacances_df["end"] >= start_dt) & (vacances_df["start"] <= end_dt)
    ]

    intervals: List[Dict[str, str]] = []
    for _, row in vacances_filtrees.iterrows():
        vac_mask = (filtered_df.index >= row["start"]) & (filtered_df.index <= row["end"])
        if filtered_df[vac_mask].shape[0] > 0:
            intervals.append(
                {
                    "start": row["start"].date().isoformat(),
                    "end": row["end"].date().isoformat(),
                }
            )

    return intervals


def build_monitoring_graphs(
    repo: DataRepository,
    blob_name: str,
    start_date: str | None,
    end_date: str | None,
    metric: str,
    aggregation: str,
    show_vacances: bool,
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
            "series": [],
            "metric": metric,
            "aggregation": aggregation,
            "start_date": start_date,
            "end_date": end_date,
            "vacances": [],
        }

    metric = metric.capitalize()
    aggregation = aggregation.capitalize()

    resample_map = {
        "Heure": "H",
        "Jour": "D",
        "Semaine": "W-MON",
        "Mois": "M",
        "Annee": "A",
        "Année": "A",
    }

    if aggregation not in resample_map:
        aggregation = "Jour"

    resampled = filtered_df.resample(resample_map[aggregation]).agg(
        {
            "Energie_periode_kWh": "sum" if metric == "Energie" else "mean",
            "Puissance_moyenne_kW": "mean",
        }
    )

    if metric == "Puissance":
        data_series = resampled["Puissance_moyenne_kW"]
        y_label = "Puissance (kW)"
    else:
        data_series = resampled["Energie_periode_kWh"]
        y_label = "Energie (kWh)"

    series = [
        {"timestamp": idx.isoformat(), "value": float(val)}
        for idx, val in data_series.items()
        if pd.notna(val)
    ]

    vacances = _vacances_in_range(filtered_df, start_date, end_date) if show_vacances else []

    return {
        "series": series,
        "metric": metric,
        "aggregation": aggregation,
        "start_date": start_date,
        "end_date": end_date,
        "y_label": y_label,
        "vacances": vacances,
    }


def build_monitoring_heatmap(
    repo: DataRepository,
    blob_name: str,
    start_date: str | None,
    end_date: str | None,
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
            "days": [],
            "hours": [],
            "values": [],
            "metric": "Puissance_moyenne_kW",
            "start_date": start_date,
            "end_date": end_date,
        }

    heatmap_df = filtered_df.copy()
    heatmap_df["Heure"] = heatmap_df.index.hour
    heatmap_df["Jour"] = heatmap_df.index.day_name()

    english_to_french = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    heatmap_df["Jour"] = heatmap_df["Jour"].map(english_to_french).fillna(heatmap_df["Jour"])

    days_order = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    hours_order = list(range(24))

    pivot_table = (
        pd.pivot_table(
            heatmap_df,
            values="Puissance_moyenne_kW",
            index="Jour",
            columns="Heure",
            aggfunc="mean",
        )
        .reindex(days_order)
        .reindex(columns=hours_order)
    )

    values: List[List[float | None]] = []
    for _, row in pivot_table.iterrows():
        values.append([None if pd.isna(val) else float(val) for val in row.values])

    return {
        "days": days_order,
        "hours": hours_order,
        "values": values,
        "metric": "Puissance_moyenne_kW",
        "start_date": start_date,
        "end_date": end_date,
    }


def build_monitoring_calendar(
    repo: DataRepository,
    blob_name: str,
    start_date: str | None,
    end_date: str | None,
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
            "daily": [],
            "stats": {"days": 0, "mean": 0.0, "max": 0.0, "min": 0.0},
            "start_date": start_date,
            "end_date": end_date,
        }

    daily = filtered_df.resample("D").sum()["Energie_periode_kWh"].reset_index()
    daily.columns = ["date", "value"]
    daily = daily[daily["value"] > 0]

    stats = {
        "days": int(len(daily)),
        "mean": float(daily["value"].mean()) if not daily.empty else 0.0,
        "max": float(daily["value"].max()) if not daily.empty else 0.0,
        "min": float(daily["value"].min()) if not daily.empty else 0.0,
    }

    daily_records = [
        {"date": row["date"].date().isoformat(), "value": float(row["value"])}
        for _, row in daily.iterrows()
    ]

    return {
        "daily": daily_records,
        "stats": stats,
        "start_date": start_date,
        "end_date": end_date,
    }


def build_monitoring_boxplots(
    repo: DataRepository,
    blob_name: str,
    start_date: str | None,
    end_date: str | None,
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
            "days_order": [],
            "series": {},
            "stats": {},
            "start_date": start_date,
            "end_date": end_date,
        }

    days_order = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    daily_consumption_df = filtered_df.resample("D").sum()
    daily_consumption_df = daily_consumption_df[daily_consumption_df["Energie_periode_kWh"] > 0]

    english_to_french = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }

    daily_consumption_df["Jour_Semaine_EN"] = daily_consumption_df.index.day_name()
    daily_consumption_df["JourSemaine"] = daily_consumption_df["Jour_Semaine_EN"].map(english_to_french)
    daily_consumption_df.drop(columns=["Jour_Semaine_EN"], inplace=True)

    cleaned_data = []
    for day in days_order:
        day_data = daily_consumption_df[daily_consumption_df["JourSemaine"] == day]
        median_value = day_data["Energie_periode_kWh"].median()
        if pd.notna(median_value):
            threshold = 5 * median_value
            cleaned_day_data = day_data[day_data["Energie_periode_kWh"] <= threshold]
            cleaned_data.append(cleaned_day_data)

    if cleaned_data:
        daily_consumption_df = pd.concat(cleaned_data)

    series: Dict[str, List[float]] = {}
    for day in days_order:
        values = daily_consumption_df[daily_consumption_df["JourSemaine"] == day][
            "Energie_periode_kWh"
        ].dropna()
        series[day] = [float(val) for val in values.tolist()]

    stats_summary = (
        daily_consumption_df.groupby("JourSemaine")["Energie_periode_kWh"]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .round(2)
    )

    stats = {
        day: {
            "count": int(stats_summary.loc[day, "count"]) if day in stats_summary.index else 0,
            "mean": float(stats_summary.loc[day, "mean"]) if day in stats_summary.index else 0.0,
            "median": float(stats_summary.loc[day, "median"]) if day in stats_summary.index else 0.0,
            "std": float(stats_summary.loc[day, "std"]) if day in stats_summary.index else 0.0,
            "min": float(stats_summary.loc[day, "min"]) if day in stats_summary.index else 0.0,
            "max": float(stats_summary.loc[day, "max"]) if day in stats_summary.index else 0.0,
        }
        for day in days_order
    }

    return {
        "days_order": days_order,
        "series": series,
        "stats": stats,
        "start_date": start_date,
        "end_date": end_date,
    }
