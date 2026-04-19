from __future__ import annotations

from typing import Dict, List, Tuple
import unicodedata

import pandas as pd
import numpy as np
from scipy import stats

from .data_repository import DataRepository, AzureDataError


SUPERFICIES = {
    "B11_hors salle spectacle": 2500,
    "B11_spectacle": 500,
    "B15_Elec_General": 5000,
    "Centre du Taur": 4850,
    "INSPE Centre des Hautes Pyrénées": 2600,
    "INSPE Saint Agne": 7900,
    "INSPE centre du Gers": 2600,
    "IUT de Blagnac": 8300,
    "IUT de Figeac": 7500,
    "Mirail _ arrivée générale": 130000,
    "Mirail _ bat 32": 1600,
    "PT_05_General": 8000,
    "UO": 3000,
}


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.lower()


def _replace_outliers_with_mean(df: pd.DataFrame, threshold: int = 50) -> pd.DataFrame:
    df_cleaned = df.copy()
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        col_mean = df_cleaned[col].mean()
        z_scores = np.abs(stats.zscore(df_cleaned[col]))
        df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)
    return df_cleaned


def _find_superficie(blob_name: str) -> float | None:
    blob_norm = _normalize(blob_name)
    for key, superficie in SUPERFICIES.items():
        if _normalize(key) in blob_norm:
            return float(superficie)
    return None


def _load_data(repo: DataRepository, blob_name: str) -> pd.DataFrame:
    df = repo.load_excel(blob_name, sheet_name="Donnees_Detaillees")
    if "Date" not in df.columns:
        raise AzureDataError("Missing Date column")
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return _replace_outliers_with_mean(df)


def _display_name(blob_name: str) -> str:
    if blob_name.lower().endswith((".xlsx", ".xls")):
        return blob_name.rsplit(".", 1)[0]
    return blob_name


def build_batiments(
    repo: DataRepository,
    buildings: List[str],
    start_date: str | None,
    end_date: str | None,
    metric: str,
    aggregation: str,
    normalize: bool,
) -> Dict[str, object]:
    if not buildings:
        return {
            "series": [],
            "insights": {},
            "missing_superficies": [],
            "period": {"start_date": start_date, "end_date": end_date},
        }

    dfs: Dict[str, pd.DataFrame] = {}
    superficie_info: Dict[str, float | None] = {}

    for building in buildings:
        df = _load_data(repo, building)
        dfs[building] = df
        superficie_info[building] = _find_superficie(building)

    min_date = min(df.index.min().date() for df in dfs.values()).isoformat()
    max_date = max(df.index.max().date() for df in dfs.values()).isoformat()
    start_date = start_date or min_date
    end_date = end_date or max_date

    filtered_dfs = {b: df.loc[str(start_date):str(end_date)] for b, df in dfs.items()}

    resample_map = {
        "Heure": "H",
        "Jour": "D",
        "Semaine": "W-MON",
        "Mois": "M",
        "Annee": "A",
        "Année": "A",
    }
    aggregation = aggregation.capitalize()
    if aggregation not in resample_map:
        aggregation = "Jour"

    metric = metric.capitalize()
    metric_col = "Energie_periode_kWh" if metric == "Energie" else "Puissance_moyenne_kW"
    ylabel = "kWh" if metric == "Energie" else "kW"

    series = []
    for building, df in filtered_dfs.items():
        resampled = df.resample(resample_map[aggregation]).agg(
            {
                "Energie_periode_kWh": "sum" if metric == "Energie" else "mean",
                "Puissance_moyenne_kW": "mean",
            }
        )

        data = resampled[metric_col]
        if normalize and metric == "Energie":
            superficie = superficie_info.get(building)
            if superficie:
                data = data / superficie
                ylabel = "kWh/m2"

        points = [
            {"timestamp": idx.isoformat(), "value": float(val)}
            for idx, val in data.items()
            if pd.notna(val)
        ]
        series.append(
            {
                "building": building,
                "label": _display_name(building),
                "points": points,
            }
        )

    missing_superficies = [
        _display_name(b) for b, s in superficie_info.items() if normalize and not s
    ]

    # Insights
    insights_data = {}
    for building, df in filtered_dfs.items():
        total_energy = float(df["Energie_periode_kWh"].sum())
        mean_energy = float(df["Energie_periode_kWh"].mean())
        mean_power = float(df["Puissance_moyenne_kW"].mean())
        max_power = float(df["Puissance_moyenne_kW"].max())
        superficie = superficie_info.get(building)

        if normalize and superficie:
            total_energy_norm = total_energy / superficie
            mean_energy_norm = mean_energy / superficie
        else:
            total_energy_norm = total_energy
            mean_energy_norm = mean_energy

        insights_data[building] = {
            "label": _display_name(building),
            "total_energy": total_energy_norm,
            "mean_energy": mean_energy_norm,
            "mean_power": mean_power,
            "max_power": max_power,
            "superficie": superficie,
        }

    sorted_buildings = sorted(
        insights_data.items(), key=lambda x: x[1]["total_energy"], reverse=True
    )
    highest = sorted_buildings[0] if sorted_buildings else None
    lowest = sorted_buildings[-1] if sorted_buildings else None

    total_diff = None
    percent_diff = None
    if highest and lowest and lowest[1]["total_energy"] > 0:
        total_diff = highest[1]["total_energy"] - lowest[1]["total_energy"]
        percent_diff = total_diff / lowest[1]["total_energy"] * 100

    # Correlation (energy series only)
    correlation = None
    if len(filtered_dfs) > 2:
        corr_df = pd.DataFrame()
        for building, df in filtered_dfs.items():
            corr_df[_display_name(building)] = df["Energie_periode_kWh"]
        corr_matrix = corr_df.corr()
        correlation = {
            "labels": list(corr_matrix.columns),
            "matrix": corr_matrix.fillna(0).round(4).values.tolist(),
        }

    return {
        "series": series,
        "metric": metric,
        "aggregation": aggregation,
        "ylabel": ylabel,
        "period": {"start_date": start_date, "end_date": end_date},
        "missing_superficies": missing_superficies,
        "insights": {
            "ranked": [
                {
                    "building": key,
                    "label": val["label"],
                    "total_energy": float(val["total_energy"]),
                    "mean_energy": float(val["mean_energy"]),
                    "mean_power": float(val["mean_power"]),
                    "max_power": float(val["max_power"]),
                    "superficie": val["superficie"],
                }
                for key, val in sorted_buildings
            ],
            "highest_consumer": highest[1] if highest else None,
            "lowest_consumer": lowest[1] if lowest else None,
            "total_diff": float(total_diff) if total_diff is not None else None,
            "percent_diff": float(percent_diff) if percent_diff is not None else None,
            "correlation": correlation,
        },
    }
