import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from azure.storage.blob import BlobServiceClient
import io
from datetime import date, timedelta
from core.config import get_config


def load_real_data():
    """Charge les donnees reelles depuis Azure Blob Storage"""
    # Configuration Azure
    # Load config once
    config = get_config()
    CONNECTION_STRING = config['azure']['connection_string']
    CONTAINER_NAME = config['azure']['container_name']

    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Hierarchie des compteurs
    parent_mapping = {
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
        "Compteur energie thermique CTA double flux.xlsx": "UO Compteur energie thermique sous-station.xlsx"
    }

    # Chargement des donnees
    file_data = {}
    blobs_list = container_client.list_blobs()
    
    for blob in blobs_list:
        if not blob.name.lower().endswith('.xlsx'):
            continue
        try:
            blob_client = container_client.get_blob_client(blob.name)
            blob_data = blob_client.download_blob().readall()
            df_monthly = pd.read_excel(io.BytesIO(blob_data), sheet_name='Consommation_Mensuelle', engine='openpyxl')
            if 'Energie_periode_kWh' not in df_monthly.columns:
                continue
            annual_consumption = df_monthly['Energie_periode_kWh'].sum()
            file_data[blob.name] = annual_consumption
        except Exception:
            continue

    return file_data, parent_mapping

def classify_equipment(nom_compteur):
    """Classifie un compteur par batiment, fluide et usage"""
    nom_lower = nom_compteur.lower()
    
    # Identification du batiment avec priorite pour Mirail
    if "mirail" in nom_lower:
        batiment = "Mirail"
    elif "agbt" in nom_lower:
        batiment = "AGBT (Bat. Principal)"
    elif "td r+1" in nom_lower:
        batiment = "Tour Direction R+1"
    elif "td r+2" in nom_lower:
        batiment = "Tour Direction R+2"
    elif "sous-station" in nom_lower or "thermique" in nom_lower:
        batiment = "Sous-station thermique"
    elif "centrale de mesure" in nom_lower:
        if "agbt" in nom_lower:
            batiment = "AGBT (Bat. Principal)"
        elif "td r+1" in nom_lower:
            batiment = "Tour Direction R+1"
        elif "td r+2" in nom_lower:
            batiment = "Tour Direction R+2"
        else:
            batiment = "Centrale de mesure"
    else:
        if "rdc" in nom_lower:
            batiment = "AGBT (Bat. Principal)"
        elif "fictif" in nom_lower:
            batiment = "AGBT (Bat. Principal)"
        else:
            batiment = "Autres"
    
    # Identification du fluide
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
    
    # Identification de l'usage
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

def get_main_counters_only(file_data, parent_mapping):
    """Retourne uniquement les compteurs principaux"""
    main_counters = {}
    
    # Identifie tous les parents
    all_parents = set(parent_mapping.values())
    
    # Les compteurs principaux sont ceux qui apparaissent comme parents
    for filename, consumption in file_data.items():
        if filename in all_parents:
            main_counters[filename] = consumption
    
    # Ajoute aussi les compteurs isoles
    for filename, consumption in file_data.items():
        if filename not in parent_mapping and filename not in all_parents:
            main_counters[filename] = consumption
    
    return main_counters

def simulate_university_usage_distribution(total_consumption):
    """Simule une repartition typique des usages pour un campus universitaire"""
    import numpy as np
    
    usage_distribution = {
        "Chauffage": 0.35,
        "Eclairage": 0.20,
        "Equipements de recherche": 0.15,
        "Climatisation": 0.12,
        "Informatique/Serveurs": 0.10,
        "Autres": 0.08
    }
    
    simulated_usage = {}
    for usage, percentage in usage_distribution.items():
        simulated_usage[usage] = total_consumption * percentage
    
    return simulated_usage

def run():
    st.title("Dashboard Energetique Multi-Batiments")
    st.caption("Vue d'ensemble du portefeuille immobilier avec donnees reelles")

    # Chargement des donnees reelles
    with st.spinner("Chargement des donnees..."):
        try:
            file_data, parent_mapping = load_real_data()
        except Exception as e:
            st.error(f"Erreur de chargement : {str(e)}")
            return

    if not file_data:
        st.error("Aucune donnee disponible")
        return

    # Analyse et classification des donnees
    main_counters = get_main_counters_only(file_data, parent_mapping)
    
    data_analysis = []
    for nom_fichier, consommation in main_counters.items():
        nom_compteur = nom_fichier.replace('.xlsx', '')
        batiment, fluide, usage = classify_equipment(nom_compteur)
        
        data_analysis.append({
            'compteur': nom_compteur,
            'batiment': batiment,
            'fluide': fluide,
            'usage': usage,
            'consommation_kwh': consommation,
            'is_parent': True
        })

    df = pd.DataFrame(data_analysis)
    
    # Calculs des KPI
    total_kwh = df['consommation_kwh'].sum()
    total_electrique = df[df['fluide'] == 'Electricite']['consommation_kwh'].sum()
    total_thermique = df[df['fluide'] == 'Energie thermique']['consommation_kwh'].sum()
    total_eau = df[df['fluide'] == 'Eau']['consommation_kwh'].sum()
    total_gaz = df[df['fluide'] == 'Gaz']['consommation_kwh'].sum()
    nb_compteurs = len(df)

    # CSS personnalise pour reduire la taille des KPI
    st.markdown("""
    <style>
    .metric-container [data-testid="metric-container"] {
        font-size: 0.8rem;
    }
    .metric-container [data-testid="metric-container"] > div {
        font-size: 0.8rem;
    }
    .metric-container [data-testid="metric-container"] > div > div {
        font-size: 1.2rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Format compact pour eviter les "..."
    def format_number(value):
        if value >= 1000000:
            return f"{value/1000000:.1f}M"
        elif value >= 1000:
            return f"{value/1000:.0f}k"
        else:
            return f"{value:.0f}"

    # Affichage des KPI
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Total", f"{format_number(total_kwh)} kWh")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Electricite", f"{format_number(total_electrique)} kWh")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        # Affichage dynamique selon les fluides presents
        if total_thermique > 0:
            st.metric("Thermique", f"{format_number(total_thermique)} kWh")
        elif total_gaz > 0:
            st.metric("Gaz", f"{format_number(total_gaz)} kWh")
        elif total_eau > 0:
            st.metric("Eau", f"{format_number(total_eau)} kWh")
        else:
            st.metric("Compteurs", f"{nb_compteurs}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Compteurs", f"{nb_compteurs}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Ligne A : 3 graphiques principaux
    colA1, colA2, colA3 = st.columns([1, 1, 1])

    # Consommation par batiment avec Mirail en premier et Autres en dernier
    par_batiment = df.groupby('batiment')['consommation_kwh'].sum()
    
    # Reorganiser pour mettre Mirail en premier et Autres en dernier
    batiments_ordre = []
    if 'Mirail' in par_batiment.index:
        batiments_ordre.append('Mirail')
    
    # Ajouter les autres batiments (sauf Mirail et Autres)
    for bat in par_batiment.index:
        if bat not in ['Mirail', 'Autres']:
            batiments_ordre.append(bat)
    
    # Ajouter Autres en dernier s'il existe
    if 'Autres' in par_batiment.index:
        batiments_ordre.append('Autres')
    
    # Reorganiser les donnees selon cet ordre
    par_batiment_ordonne = par_batiment.reindex(batiments_ordre)
    
    fig_bat = go.Figure(go.Bar(
        x=par_batiment_ordonne.values, 
        y=par_batiment_ordonne.index, 
        orientation="h",
        marker_color='#b9ce0e'
    ))
    fig_bat.update_layout(
        title="Consommation par batiment (compteurs principaux)",
        height=280, 
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title="kWh", 
        yaxis_title=None
    )
    colA1.plotly_chart(fig_bat, use_container_width=True)

    # Simulation des usages universitaires
    university_usage = simulate_university_usage_distribution(total_kwh)
    usage_values = list(university_usage.values())
    usage_names = list(university_usage.keys())
    
    # Tri par valeur croissante pour l'affichage
    sorted_usage = sorted(zip(usage_names, usage_values), key=lambda x: x[1])
    usage_names_sorted = [x[0] for x in sorted_usage]
    usage_values_sorted = [x[1] for x in sorted_usage]
    
    fig_usage = go.Figure(go.Bar(
        x=usage_values_sorted, 
        y=usage_names_sorted, 
        orientation="h",
        marker_color='#e18222'
    ))
    fig_usage.update_layout(
        title="Consommation par usage (Campus universitaire)",
        height=280, 
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title="kWh", 
        yaxis_title=None
    )
    colA2.plotly_chart(fig_usage, use_container_width=True)

    # Repartition Heures ouvrees vs Hors heures
    kwh_ouvre = total_kwh * 0.65
    kwh_ferme = total_kwh * 0.35
    
    donut_hours = pd.DataFrame({
        "Tranche": ["Heures ouvrees", "Hors heures"], 
        "kWh": [kwh_ouvre, kwh_ferme]
    })
    fig_donut_hours = px.pie(
        donut_hours, 
        names="Tranche", 
        values="kWh", 
        hole=0.55,
        color_discrete_sequence=['#b9ce0e', '#e18222']
    )
    fig_donut_hours.update_layout(
        title="Repartition heures ouvrees vs hors heures",
        height=280, 
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=True
    )
    colA3.plotly_chart(fig_donut_hours, use_container_width=True)

    # Ligne B : 1 graphique seulement
    st.markdown("---")  # Separateur visuel
    
    # Repartition par fluide (Donut) - Centre sur la page
    col_center = st.columns([1, 2, 1])
    
    with col_center[1]:
        par_fluide = df.groupby('fluide')['consommation_kwh'].sum()
        # Filtrer les fluides avec valeur > 0
        par_fluide = par_fluide[par_fluide > 0]
        
        fig_donut = px.pie(
            values=par_fluide.values, 
            names=par_fluide.index, 
            hole=0.55,
            color_discrete_sequence=['#b9ce0e', '#e18222', '#0c323c', '#ffcc00', '#ff6b6b']
        )
        fig_donut.update_layout(
            title="Repartition par type de fluide",
            height=400, 
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=True
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Tableau de synthese
    st.markdown("## Synthese des compteurs principaux")
    
    # Formatage pour affichage
    df_display = df.copy()
    df_display = df_display.sort_values('consommation_kwh', ascending=False)
    df_display['consommation_kwh'] = df_display['consommation_kwh'].apply(
        lambda x: f"{x:,.0f}".replace(',', ' ') + " kWh"
    )
    
    # Style du tableau
    st.markdown("""
    <style>
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    .dataframe th {
        background: linear-gradient(135deg, #b9ce0e, #e18222) !important;
        color: white !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.dataframe(
        df_display[['compteur', 'batiment', 'fluide', 'usage', 'consommation_kwh']].rename(columns={
            'compteur': 'Compteur Principal',
            'batiment': 'Batiment', 
            'fluide': 'Fluide',
            'usage': 'Usage',
            'consommation_kwh': 'Consommation'
        }),
        use_container_width=True,
        height=400
    )

    # Sidebar avec informations
    st.sidebar.markdown("""
    <div style="background: linear-gradient(135deg, #0c323c, #b9ce0e);
                padding: 1rem;
                border-radius: 12px;
                color: white;
                text-align: center;
                margin: 1rem 0;">
        <h4>Donnees en temps reel</h4>
        <p><small>Compteurs principaux uniquement</small></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Comptage dynamique des fluides presents
    fluides_presents = par_fluide.index.tolist()
    
    st.sidebar.info(f"""
    **Resume du portefeuille:**
    - **{len(par_batiment_ordonne)} batiments** analyses
    - **{len(fluides_presents)} fluides energetiques** : {", ".join(fluides_presents)}
    - **{nb_compteurs} compteurs principaux** au total
    
    **Donnees simulees:**
    - Repartition par usage basee sur un campus universitaire type
    - Heures ouvrees : 65% / Hors heures : 35%
    """)

if __name__ == "__main__":
    run()