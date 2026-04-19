from __future__ import annotations

from typing import Dict, List
import unicodedata

import pandas as pd

from .data_repository import DataRepository, AzureDataError


def _normalize(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(normalized.lower().split())


def _build_parent_mapping() -> Dict[str, str]:
    # Accentless mapping (matches Dashboard_Multi), but normalization allows accented names too.
    return {
        "Compteur electrique chauffage armoire CVC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur electrique ventilation armoire CVC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur electrique ascenseur AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur electrique CVC unite exterieure CTA AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur electrique CVC unite exterieure VDI AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Compteur (fictif) RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Centrale de mesure TD R+1.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Centrale de mesure TD R+2.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Compteur electrique photovoltaique AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur electrique eclairage AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur electrique PC AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur electrique CVC AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur electrique ballon ECS AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur electrique ballon ECS TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur electrique eclairage TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur electrique PCFM TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur electrique CVC TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur electrique ballon ECS TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur electrique eclairage TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur electrique PCFM TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur electrique unite exterieure studio TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur electrique unite interieure studio TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "UO Compteur electrique CVC TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur energie thermique CTA double flux.xlsx": "UO Compteur energie thermique sous-station.xlsx",
    }


def _resolve_parent(
    file_name: str,
    parent_mapping: Dict[str, str],
    parent_mapping_norm: Dict[str, str],
    norm_to_actual: Dict[str, str],
) -> str | None:
    if file_name in parent_mapping:
        return parent_mapping[file_name]

    normalized = _normalize(file_name)
    parent_norm = parent_mapping_norm.get(normalized)
    if not parent_norm:
        return None

    return norm_to_actual.get(parent_norm, parent_norm)


def _format_building_name(file_name: str) -> str:
    return file_name.split(".")[0].replace("_", " ").title()


def build_accueil_summary(repo: DataRepository) -> Dict[str, object]:
    try:
        blobs = repo.list_blobs()
    except AzureDataError:
        raise

    file_data: Dict[str, float] = {}
    for blob in blobs:
        if not blob.lower().endswith(".xlsx"):
            continue
        try:
            df_monthly = repo.load_excel(blob, sheet_name="Consommation_Mensuelle")
        except AzureDataError:
            continue

        if "Energie_periode_kWh" not in df_monthly.columns:
            continue

        annual_consumption = float(pd.to_numeric(df_monthly["Energie_periode_kWh"], errors="coerce").sum())
        file_data[blob] = annual_consumption

    if not file_data:
        return {
            "total_annual_kwh": 0.0,
            "monthly_avg_kwh": 0.0,
            "daily_avg_kwh": 0.0,
            "estimated_cost_eur": 0.0,
            "ranking": [],
            "table": [],
        }

    parent_mapping = _build_parent_mapping()
    parent_mapping_norm = {_normalize(k): _normalize(v) for k, v in parent_mapping.items()}
    norm_to_actual = {_normalize(name): name for name in file_data.keys()}

    parents: Dict[str, Dict[str, object]] = {}
    for file_name, consumption in file_data.items():
        parent_file = _resolve_parent(
            file_name,
            parent_mapping,
            parent_mapping_norm,
            norm_to_actual,
        )

        if parent_file:
            if parent_file not in parents:
                parents[parent_file] = {
                    "consumption": float(file_data.get(parent_file, 0.0)),
                    "children": [],
                }
            parents[parent_file]["children"].append(
                {
                    "building": _format_building_name(file_name),
                    "consumption_kwh": float(consumption),
                }
            )
        else:
            if file_name not in parents:
                parents[file_name] = {
                    "consumption": float(consumption),
                    "children": [],
                }

    sorted_parents = sorted(parents.items(), key=lambda x: x[1]["consumption"], reverse=True)
    total_annual = float(sum(parent_info["consumption"] for _, parent_info in sorted_parents))

    ranking: List[Dict[str, object]] = []
    table: List[Dict[str, object]] = []
    for parent_file, parent_info in sorted_parents:
        parent_name = _format_building_name(parent_file)
        children = sorted(
            parent_info["children"],
            key=lambda x: -x["consumption_kwh"],
        )

        ranking.append(
            {
                "parent_file": parent_file,
                "parent_name": parent_name,
                "consumption_kwh": float(parent_info["consumption"]),
                "children": children,
            }
        )

        table.append(
            {
                "building": parent_name,
                "consumption_kwh": float(parent_info["consumption"]),
                "level": 0,
                "type": "parent",
            }
        )
        for child in children:
            table.append(
                {
                    "building": child["building"],
                    "consumption_kwh": float(child["consumption_kwh"]),
                    "level": 1,
                    "type": "child",
                }
            )

    return {
        "total_annual_kwh": total_annual,
        "monthly_avg_kwh": total_annual / 12.0,
        "daily_avg_kwh": total_annual / 365.0,
        "estimated_cost_eur": total_annual * 0.28,
        "ranking": ranking,
        "table": table,
    }
