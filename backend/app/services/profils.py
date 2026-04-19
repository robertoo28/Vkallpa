from __future__ import annotations

from typing import Dict, List

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


def build_profils(
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
            "profiles": {},
            "stats": {},
        }

    # Time features
    df["Heure"] = df.index.hour
    df["Jour_Semaine_EN"] = df.index.day_name()
    df["Mois_EN"] = df.index.month_name()
    df["Annee"] = df.index.year
    df["Semaine_An"] = df.index.isocalendar().week
    df["Jour_Mois"] = df.index.day

    english_to_french = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi", "Thursday": "Jeudi",
        "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche",
        "January": "Janvier", "February": "Fevrier", "March": "Mars", "April": "Avril",
        "May": "Mai", "June": "Juin", "July": "Juillet", "August": "Aout",
        "September": "Septembre", "October": "Octobre", "November": "Novembre",
        "December": "Decembre",
    }

    df["Jour_Semaine"] = df["Jour_Semaine_EN"].map(english_to_french)
    df["Mois"] = df["Mois_EN"].map(english_to_french)
    df.drop(columns=["Jour_Semaine_EN", "Mois_EN"], inplace=True)

    jours_ordre = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois_ordre = ["Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin", "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]

    # 1. Profil journalier (24h)
    daily_profile = (
        df.groupby(["Jour_Semaine", "Heure"])["Energie_periode_kWh"].mean().reset_index()
    )

    # Stats for daily profile
    if not daily_profile.empty:
        peak_hour = int(daily_profile.loc[daily_profile["Energie_periode_kWh"].idxmax(), "Heure"])
        min_hour = int(daily_profile.loc[daily_profile["Energie_periode_kWh"].idxmin(), "Heure"])
        variation = (
            (daily_profile["Energie_periode_kWh"].max() - daily_profile["Energie_periode_kWh"].min())
            / daily_profile["Energie_periode_kWh"].mean()
            * 100
            if daily_profile["Energie_periode_kWh"].mean() > 0
            else 0.0
        )
    else:
        peak_hour = None
        min_hour = None
        variation = 0.0

    # 2. Profil hebdo par mois
    weekly_month_profile = (
        df.groupby(["Mois", "Jour_Semaine"])["Energie_periode_kWh"].mean().reset_index()
    )

    # 3. Profil mensuel par année
    monthly_year_profile = (
        df.groupby(["Annee", "Mois"])["Energie_periode_kWh"].sum().reset_index()
    )

    # 4. Profil hebdo par année
    weekly_year_profile = (
        df.groupby(["Annee", "Semaine_An"])["Energie_periode_kWh"].sum().reset_index()
    )

    # Insights
    total_energy = float(df["Energie_periode_kWh"].sum())
    peak_hour_global = int(df.groupby("Heure")["Energie_periode_kWh"].mean().idxmax())
    peak_day_global = df.groupby("Jour_Semaine")["Energie_periode_kWh"].sum().idxmax()

    daily_std = df.groupby(df.index.date)["Energie_periode_kWh"].sum().std()
    daily_mean = df.groupby(df.index.date)["Energie_periode_kWh"].sum().mean()
    regularity = (1 - daily_std / daily_mean) * 100 if daily_mean > 0 else 0.0

    profiles = {
        "daily_profile": daily_profile.to_dict(orient="records"),
        "weekly_month_profile": weekly_month_profile.to_dict(orient="records"),
        "monthly_year_profile": monthly_year_profile.to_dict(orient="records"),
        "weekly_year_profile": weekly_year_profile.to_dict(orient="records"),
        "orders": {"jours": jours_ordre, "mois": mois_ordre},
    }

    stats_payload = {
        "daily_profile": {
            "peak_hour": peak_hour,
            "min_hour": min_hour,
            "variation_pct": float(variation),
        },
        "monthly_profile": {},
        "insights": {
            "total_energy_kwh": total_energy,
            "peak_hour": peak_hour_global,
            "peak_day": peak_day_global,
            "regularity_pct": float(regularity),
        },
    }

    if not monthly_year_profile.empty:
        mois_max = monthly_year_profile.loc[monthly_year_profile["Energie_periode_kWh"].idxmax(), "Mois"]
        mois_min = monthly_year_profile.loc[monthly_year_profile["Energie_periode_kWh"].idxmin(), "Mois"]
        var_mensuelle = (
            monthly_year_profile["Energie_periode_kWh"].std()
            / monthly_year_profile["Energie_periode_kWh"].mean()
            * 100
            if monthly_year_profile["Energie_periode_kWh"].mean() > 0
            else 0.0
        )
        stats_payload["monthly_profile"] = {
            "peak_month": str(mois_max),
            "min_month": str(mois_min),
            "variability_pct": float(var_mensuelle),
        }

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "profiles": profiles,
        "stats": stats_payload,
    }
