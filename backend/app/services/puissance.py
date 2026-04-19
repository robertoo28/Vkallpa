from __future__ import annotations

from typing import Dict, List, Optional
from pathlib import Path
import json

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


def _load_alarm_config() -> Dict[str, List[dict]]:
    path = Path(__file__).resolve().parents[2] / "config" / "alarms.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        # Fallback if file has unexpected content
        return {}
    return data.get("alarms", {})


def _get_threshold_for_building(building: str, type_mesure: str = "Puissance") -> Optional[float]:
    alarms = _load_alarm_config().get(building, [])
    for alarm in alarms:
        if alarm.get("type_mesure") == type_mesure and alarm.get("statut") == "active":
            seuil = float(alarm.get("seuil", 0))
            pourcentage = float(alarm.get("pourcentage", 0))
            return seuil * (pourcentage / 100.0)
    return None


def build_puissance(
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

    df = df.loc[str(start_date):str(end_date)]
    if df.empty:
        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "threshold_kw": None,
            "daily": [],
            "alerts": {"count": 0, "items": [], "rate_pct": 0.0},
            "stats": {},
        }

    # Daily stats: max power and peak time
    def _daily_peak(x: pd.DataFrame) -> pd.Series:
        if x.empty:
            return pd.Series({"Puissance_Max": 0.0, "Heure_Pic": None})
        max_val = x["Puissance_moyenne_kW"].max()
        if max_val <= 0:
            return pd.Series({"Puissance_Max": 0.0, "Heure_Pic": None})
        idx = x["Puissance_moyenne_kW"].idxmax()
        return pd.Series({"Puissance_Max": float(max_val), "Heure_Pic": idx.time()})

    daily_stats = df.groupby(pd.Grouper(freq="D")).apply(_daily_peak).dropna()
    filtered_data = daily_stats[daily_stats["Puissance_Max"] > 0]

    threshold_kw = _get_threshold_for_building(blob_name)
    effective_threshold = float("inf") if threshold_kw is None else float(threshold_kw)

    threshold_exceeded = filtered_data[filtered_data["Puissance_Max"] > effective_threshold]

    daily = []
    for idx, row in filtered_data.iterrows():
        status = "exceeded" if row["Puissance_Max"] > effective_threshold else "normal"
        heure_pic = row["Heure_Pic"].strftime("%H:%M") if pd.notnull(row["Heure_Pic"]) else None
        daily.append(
            {
                "date": idx.date().isoformat(),
                "puissance_max_kw": float(row["Puissance_Max"]),
                "heure_pic": heure_pic,
                "status": status,
            }
        )

    alerts_items = []
    for idx, row in threshold_exceeded.iterrows():
        heure_pic = row["Heure_Pic"].strftime("%H:%M") if pd.notnull(row["Heure_Pic"]) else None
        alerts_items.append(
            {
                "date": idx.date().isoformat(),
                "puissance_max_kw": float(row["Puissance_Max"]),
                "heure_pic": heure_pic,
                "depassement_kw": float(row["Puissance_Max"] - effective_threshold),
            }
        )

    alerts_count = int(len(threshold_exceeded))
    total_days = int(len(filtered_data))
    alerts_rate = float(alerts_count / total_days * 100) if total_days > 0 else 0.0

    avg_exceeded = float(threshold_exceeded["Puissance_Max"].mean()) if alerts_count > 0 else 0.0
    max_exceeded = float(threshold_exceeded["Puissance_Max"].max()) if alerts_count > 0 else 0.0

    avg_power = float(filtered_data["Puissance_Max"].mean()) if total_days > 0 else 0.0
    max_power = float(filtered_data["Puissance_Max"].max()) if total_days > 0 else 0.0
    max_date = None
    if total_days > 0:
        max_idx = filtered_data["Puissance_Max"].idxmax()
        max_date = max_idx.date().isoformat()

    # Most common peak hour
    hours = [
        t.hour for t in filtered_data["Heure_Pic"].dropna().tolist() if hasattr(t, "hour")
    ]
    most_common_hour = None
    if hours:
        most_common_hour = int(pd.Series(hours).mode()[0])

    conformity_rate = float(((total_days - alerts_count) / total_days) * 100) if total_days > 0 else 0.0

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "threshold_kw": threshold_kw,
        "daily": daily,
        "alerts": {
            "count": alerts_count,
            "rate_pct": alerts_rate,
            "items": alerts_items,
            "max_exceeded_kw": max_exceeded,
            "avg_exceeded_kw": avg_exceeded,
        },
        "stats": {
            "avg_power_kw": avg_power,
            "max_power_kw": max_power,
            "max_power_date": max_date,
            "most_common_peak_hour": most_common_hour,
            "conformity_rate_pct": conformity_rate,
        },
    }
