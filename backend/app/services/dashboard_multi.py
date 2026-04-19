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


def _load_monthly_consumption(repo: DataRepository) -> Dict[str, float]:
    file_data: Dict[str, float] = {}
    blobs = repo.list_blobs()
    for blob in blobs:
        if not blob.lower().endswith(".xlsx"):
            continue
        try:
            df_monthly = repo.load_excel(blob, sheet_name="Consommation_Mensuelle")
        except AzureDataError:
            continue
        if "Energie_periode_kWh" not in df_monthly.columns:
            continue
        annual = float(pd.to_numeric(df_monthly["Energie_periode_kWh"], errors="coerce").sum())
        file_data[blob] = annual
    return file_data


def _classify_equipment(name: str) -> tuple[str, str, str]:
    nom_lower = _normalize(name)

    if "mirail" in nom_lower:
        batiment = "Mirail"
    elif "agbt" in nom_lower:
        batiment = "AGBT (Bât. Principal)"
    elif "td r+1" in nom_lower:
        batiment = "Tour Direction R+1"
    elif "td r+2" in nom_lower:
        batiment = "Tour Direction R+2"
    elif "sous-station" in nom_lower or "thermique" in nom_lower:
        batiment = "Sous-station thermique"
    elif "centrale de mesure" in nom_lower:
        if "agbt" in nom_lower:
            batiment = "AGBT (Bât. Principal)"
        elif "td r+1" in nom_lower:
            batiment = "Tour Direction R+1"
        elif "td r+2" in nom_lower:
            batiment = "Tour Direction R+2"
        else:
            batiment = "Centrale de mesure"
    else:
        if "rdc" in nom_lower or "fictif" in nom_lower:
            batiment = "AGBT (Bât. Principal)"
        else:
            batiment = "Autres"

    if "energie thermique" in nom_lower or "thermique" in nom_lower:
        fluide = "Energie thermique"
    elif any(x in nom_lower for x in ["eau", "ecs", "sanitaire"]):
        fluide = "Eau"
    elif "gaz" in nom_lower:
        fluide = "Gaz"
    elif "electrique" in nom_lower or "compteur" in nom_lower:
        fluide = "Electricite"
    else:
        fluide = "Electricite"

    if any(x in nom_lower for x in ["cvc", "chauffage", "ventilation", "climatisation"]):
        usage = "CVC"
    elif "eclairage" in nom_lower:
        usage = "Eclairage"
    elif any(x in nom_lower for x in ["pc", "pcfm"]):
        usage = "Prises de courant"
    elif "ecs" in nom_lower or "ballon" in nom_lower:
        usage = "ECS"
    elif "ascenseur" in nom_lower:
        usage = "Transport vertical"
    elif "photovoltaique" in nom_lower or "pv" in nom_lower:
        usage = "Production PV"
    else:
        usage = "Autres"

    return batiment, fluide, usage


def _get_main_counters_only(file_data: Dict[str, float], parent_mapping: Dict[str, str]) -> Dict[str, float]:
    parent_mapping_norm = {_normalize(k): _normalize(v) for k, v in parent_mapping.items()}
    all_parents_norm = set(parent_mapping_norm.values())

    main_counters: Dict[str, float] = {}
    for filename, consumption in file_data.items():
        filename_norm = _normalize(filename)
        if filename_norm in all_parents_norm:
            main_counters[filename] = consumption
        elif filename_norm not in parent_mapping_norm and filename_norm not in all_parents_norm:
            main_counters[filename] = consumption

    return main_counters


def _simulate_university_usage_distribution(total_consumption: float) -> Dict[str, float]:
    usage_distribution = {
        "Chauffage": 0.35,
        "Eclairage": 0.20,
        "Equipements de recherche": 0.15,
        "Climatisation": 0.12,
        "Informatique/Serveurs": 0.10,
        "Autres": 0.08,
    }
    return {usage: total_consumption * pct for usage, pct in usage_distribution.items()}


def _order_batiments(batiments: List[str]) -> List[str]:
    ordered = []
    if "Mirail" in batiments:
        ordered.append("Mirail")
    for bat in batiments:
        if bat not in ["Mirail", "Autres"]:
            ordered.append(bat)
    if "Autres" in batiments:
        ordered.append("Autres")
    return ordered


def build_dashboard_multi_summary(repo: DataRepository) -> Dict[str, object]:
    file_data = _load_monthly_consumption(repo)
    if not file_data:
        return {
            "kpis": {},
            "charts": {},
            "table": [],
            "summary": {},
        }

    parent_mapping = _build_parent_mapping()
    main_counters = _get_main_counters_only(file_data, parent_mapping)

    data_analysis: List[Dict[str, object]] = []
    for filename, consumption in main_counters.items():
        compteur = filename.replace(".xlsx", "")
        batiment, fluide, usage = _classify_equipment(compteur)
        data_analysis.append(
            {
                "compteur": compteur,
                "batiment": batiment,
                "fluide": fluide,
                "usage": usage,
                "consommation_kwh": float(consumption),
            }
        )

    df = pd.DataFrame(data_analysis)

    total_kwh = float(df["consommation_kwh"].sum())
    total_electric = float(df[df["fluide"] == "Electricite"]["consommation_kwh"].sum())
    total_thermique = float(df[df["fluide"] == "Energie thermique"]["consommation_kwh"].sum())
    total_eau = float(df[df["fluide"] == "Eau"]["consommation_kwh"].sum())
    total_gaz = float(df[df["fluide"] == "Gaz"]["consommation_kwh"].sum())
    nb_compteurs = int(len(df))

    par_batiment = df.groupby("batiment")["consommation_kwh"].sum()
    batiments_ordre = _order_batiments(list(par_batiment.index))
    par_batiment_ordonne = par_batiment.reindex(batiments_ordre)

    usage_distribution = _simulate_university_usage_distribution(total_kwh)
    hours_distribution = {"Heures ouvrees": total_kwh * 0.65, "Hors heures": total_kwh * 0.35}

    par_fluide = df.groupby("fluide")["consommation_kwh"].sum()
    par_fluide = par_fluide[par_fluide > 0]

    df_display = df.sort_values("consommation_kwh", ascending=False)

    return {
        "kpis": {
            "total_kwh": total_kwh,
            "total_electric_kwh": total_electric,
            "total_thermique_kwh": total_thermique,
            "total_eau_kwh": total_eau,
            "total_gaz_kwh": total_gaz,
            "nb_compteurs": nb_compteurs,
        },
        "charts": {
            "consumption_by_building": [
                {"batiment": idx, "kwh": float(val)}
                for idx, val in par_batiment_ordonne.items()
                if pd.notna(val)
            ],
            "usage_distribution": [
                {"usage": name, "kwh": float(val)} for name, val in usage_distribution.items()
            ],
            "hours_distribution": [
                {"label": name, "kwh": float(val)} for name, val in hours_distribution.items()
            ],
            "fluid_distribution": [
                {"fluide": name, "kwh": float(val)} for name, val in par_fluide.items()
            ],
        },
        "table": df_display.to_dict(orient="records"),
        "summary": {
            "batiments_count": int(len(par_batiment_ordonne.index)),
            "fluides_presents": list(par_fluide.index),
            "compteurs_principaux": nb_compteurs,
        },
    }
