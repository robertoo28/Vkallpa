import streamlit as st
from azure.storage.blob import BlobServiceClient
import pandas as pd
import io
from core.config import get_config

def run():
    
    # Load config once
    config = get_config()

    # Configuration Azure
    CONNECTION_STRING = config['azure']['connection_string']
    CONTAINER_NAME = config['azure']['container_name']

    # Connexion à Azure Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Définition de la hiérarchie
    parent_mapping = {
        "Compteur électrique chauffage armoire CVC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur électrique ventilation armoire CVC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur électrique ascenseur AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur électrique CVC unité extérieure CTA AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur électrique CVC unité extérieure VDI AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Compteur (fictif) RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Centrale de mesure TD R+1.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Centrale de mesure TD R+2.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "UO Compteur électrique photovoltaïque AGBT RDC.xlsx": "UO Centrale de mesure AGBT.xlsx",
        "Compteur électrique éclairage AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur électrique PC AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur électrique CVC AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur électrique ballon ECS AGBT RDC.xlsx": "UO Compteur (fictif) RDC.xlsx",
        "Compteur électrique ballon ECS TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur électrique éclairage TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur électrique PCFM TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur électrique CVC TD R+1.xlsx": "UO Centrale de mesure TD R+1.xlsx",
        "Compteur électrique ballon ECS TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur électrique éclairage TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur électrique PCFM TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur électrique unité extérieure studio TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur électrique unité intérieure studio TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "UO Compteur électrique CVC TD R+2.xlsx": "UO Centrale de mesure TD R+2.xlsx",
        "Compteur énergie thermique CTA double flux.xlsx": "UO Compteur énergie thermique sous-station.xlsx"
    }

    # Chargement des données
    file_data = {}

    with st.spinner("Chargement des données..."):
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

    # Construction de la hiérarchie
    parents = {}
    for file_name, consumption in file_data.items():
        if file_name in parent_mapping:
            parent_file = parent_mapping[file_name]
            if parent_file not in parents:
                parents[parent_file] = {
                    "consumption": file_data.get(parent_file, 0),
                    "children": []
                }
            parents[parent_file]["children"].append({
                "Bâtiment": file_name.split('.')[0].replace('_', ' ').title(),
                "Consommation Annuelle (kWh)": consumption
            })
        else:
            if file_name not in parents:
                parents[file_name] = {"consumption": consumption, "children": []}

    # Tri des parents par consommation décroissante
    sorted_parents = sorted(parents.items(), key=lambda x: x[1]['consumption'], reverse=True)

    # Calcul du total annuel
    total_annuel = sum(parent_info['consumption'] for _, parent_info in sorted_parents)

    # Préparation des données avec hiérarchie visuelle améliorée
    detailed_data = []
    for parent_file, parent_info in sorted_parents:
        parent_name = parent_file.split('.')[0].replace('_', ' ').title()
        detailed_data.append({
            "Bâtiment": f"🏢 {parent_name}",
            "Consommation Annuelle (kWh)": parent_info["consumption"],
            "level": 0,
            "Type": "Compteur Principal"
        })
        
        sorted_children = sorted(parent_info["children"], key=lambda x: -x["Consommation Annuelle (kWh)"])
        
        # Calcul de la somme des enfants pour validation
        total_children = sum(child["Consommation Annuelle (kWh)"] for child in sorted_children)
        
        for i, child in enumerate(sorted_children):
            is_last = (i == len(sorted_children) - 1)
            prefix = "    └── " if is_last else "    ├── "
            detailed_data.append({
                "Bâtiment": f"{prefix}⚡ {child['Bâtiment']}",
                "Consommation Annuelle (kWh)": child["Consommation Annuelle (kWh)"],
                "level": 1,
                "Type": "Sous-compteur"
            })
        
        # Ligne de séparation visuelle entre les groupes (optionnel)
        if len(sorted_children) > 0:
            detailed_data.append({
                "Bâtiment": "─" * 50,
                "Consommation Annuelle (kWh)": 0,
                "level": 2,
                "Type": "Séparateur"
            })

    df_ranking = pd.DataFrame(detailed_data)
    # Supprimer les lignes séparateurs pour l'affichage final
    df_ranking = df_ranking[df_ranking["Type"] != "Séparateur"]

    # Interface Streamlit avec design moderne
    st.title('📊 Tableau de consommation énergétique')

    # Carte de consommation avec design moderne
    if not df_ranking.empty and total_annuel > 0:
        total_formate = f"{total_annuel:,.0f}".replace(',', ' ')
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #b9ce0e 0%, #000000 100%);
                    border-radius: 20px; 
                    padding: 2rem; 
                    margin: 1rem 0; 
                    text-align: center; 
                    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                    border: 1px solid rgba(255,255,255,0.2);">
            <div style="background: rgba(255,255,255,0.95); 
                        border-radius: 12px; 
                        padding: 1.5rem; 
                        backdrop-filter: blur(10px);">
                <h2 style="color: #b9ce0e; margin-bottom: 0.8rem; font-weight: 400; font-size: 1.5rem;">
                    ⚡ Consommation Annuelle Totale
                </h2>
                <div style="font-size: 3rem; 
                           font-weight: bold; 
                           color: #b9ce0e;
                           text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
                           margin: 0.8rem 0;">
                    {total_formate}
                </div>
                <div style="font-size: 1.2rem; 
                           color: #e18222; 
                           font-weight: 400;">
                    kWh
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Informations supplémentaires avec style moderne
        col1, col2, col3 = st.columns(3)
        
        with col1:
            mensuelle_moy = f"{total_annuel/12:,.0f}".replace(',', ' ')
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0c323c 0%, #ffffff 100%);
                        padding: 1rem;
                        border-radius: 12px;
                        text-align: center;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.1);">
                <h4 style="color: #0c323c; margin: 0; font-size: 0.9rem; font-weight: bold;">📊 Mensuelle Moyenne</h4>
                <p style="color: #0c323c; font-size: 1.2rem; font-weight: bold; margin: 0.3rem 0;">
                    {mensuelle_moy} kWh
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            quotidienne_moy = f"{total_annuel/365:,.0f}".replace(',', ' ')
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #e18222 0%, #ffffff 100%);
                        padding: 1rem;
                        border-radius: 12px;
                        text-align: center;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.1);">
                <h4 style="color: #e18222; margin: 0; font-size: 0.9rem; font-weight: bold;">⚡ Quotidienne Moyenne</h4>
                <p style="color: #e18222; font-size: 1.2rem; font-weight: bold; margin: 0.3rem 0;">
                    {quotidienne_moy} kWh
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Estimation du coût (prix moyen de 0.28€/kWh)
            cout_estime = total_annuel * 0.28
            cout_formate = f"{cout_estime:,.0f}".replace(',', ' ')
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #b9ce0e 0%, #ffffff 100%);
                        padding: 1rem;
                        border-radius: 12px;
                        text-align: center;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.1);">
                <h4 style="color: #b9ce0e; margin: 0; font-size: 0.9rem; font-weight: bold;">💰 Coût Estimé Annuel</h4>
                <p style="color: #b9ce0e; font-size: 1.2rem; font-weight: bold; margin: 0.3rem 0;">
                    {cout_formate} €
                </p>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.error("Aucune donnée disponible")

    # Espacement
    st.markdown("<br>", unsafe_allow_html=True)

    # Classement détaillé avec style amélioré
    st.markdown('## 🏢 Classement détaillé des bâtiments')
    if not df_ranking.empty:
        parent_consumptions = df_ranking[df_ranking["level"] == 0]["Consommation Annuelle (kWh)"]
        
        def color_row(s):
            styles = []
            if s["level"] == 0:
                # Style pour les compteurs principaux
                min_val = parent_consumptions.min() if len(parent_consumptions) > 0 else 0
                max_val = parent_consumptions.max() if len(parent_consumptions) > 0 else 0
                normalized = (s["Consommation Annuelle (kWh)"] - min_val)/(max_val - min_val) if max_val > min_val else 0
                
                intensity = normalized
                bg_color = f'background: linear-gradient(90deg, rgba(185,206,14,{0.2 + intensity*0.4}), rgba(225,130,34,{0.1 + intensity*0.3})); font-weight: bold; border-left: 4px solid #b9ce0e'
                styles = ['', bg_color, '', '']
            elif s["level"] == 1:
                # Style pour les sous-compteurs
                bg_color = 'background: rgba(12,50,60,0.08); font-style: italic; border-left: 2px solid #0c323c'
                styles = ['', bg_color, '', '']
            else:
                styles = ['', '', '', '']
            return styles

        # Style CSS personnalisé pour le tableau hiérarchique
        st.markdown("""
        <style>
        .hierarchical-table {
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
            margin: 1.5rem 0;
            border: 1px solid rgba(185,206,14,0.2);
        }
        .hierarchical-table table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .hierarchical-table th {
            background: linear-gradient(135deg, #b9ce0e, #e18222);
            color: white;
            padding: 1.2rem;
            font-weight: bold;
            text-align: left;
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .hierarchical-table td {
            padding: 1rem;
            border-bottom: 1px solid rgba(0,0,0,0.06);
            vertical-align: middle;
        }
        .hierarchical-table tr:hover {
            background: rgba(185,206,14,0.15) !important;
            transform: scale(1.001);
            transition: all 0.2s ease;
        }
        .main-counter {
            font-weight: bold;
            font-size: 1.05em;
        }
        .sub-counter {
            font-style: italic;
            color: #555;
            padding-left: 1rem;
        }
        </style>
        """, unsafe_allow_html=True)

        # Formatage des nombres avec espaces au lieu de virgules
        def format_consumption(value):
            return f"{value:,.0f}".replace(',', ' ') + " kWh"

        styled_df = df_ranking.style.format({
            "Consommation Annuelle (kWh)": format_consumption
        }).apply(color_row, axis=1).hide(axis='index')

        html = styled_df.to_html(index=False, classes='hierarchical-table')
        
        # Améliorations de l'affichage hiérarchique
        html = html.replace('🏢', '<span style="color: #b9ce0e; font-size: 1.2em;">🏢</span>')
        html = html.replace('⚡', '<span style="color: #e18222; font-size: 1.1em;">⚡</span>')
        html = html.replace('├──', '<span style="color: #0c323c;">├──</span>')
        html = html.replace('└──', '<span style="color: #0c323c;">└──</span>')
        
        st.markdown(f'<div class="hierarchical-table">{html}</div>', unsafe_allow_html=True)
        
        # Légende explicative
        st.markdown("""
        <div style="background: rgba(185,206,14,0.1); 
                    border-radius: 10px; 
                    padding: 1rem; 
                    margin: 1rem 0;
                    border-left: 4px solid #b9ce0e;">
            <h4 style="margin: 0 0 0.5rem 0; color: #b9ce0e;">💡 Légende de l'arborescence :</h4>
            <p style="margin: 0.3rem 0; color: #333;"><strong>🏢 Compteur Principal (Level 0)</strong> : Compteur principal de mesure</p>
            <p style="margin: 0.3rem 0; color: #333;"><strong>⚡ Sous-compteur (Level 1)</strong> : Sous-compteurs dont la somme correspond au compteur principal</p>
            <p style="margin: 0; color: #666; font-size: 0.9em; font-style: italic;">
                La hiérarchie montre la décomposition de chaque compteur principal en ses sous-compteurs associés.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        st.warning('Aucune donnée disponible')

    # Sidebar avec style amélioré
    st.sidebar.markdown("""
    <div style="background: linear-gradient(135deg, #0c323c, #b9ce0e);
                padding: 1rem;
                border-radius: 12px;
                color: white;
                text-align: center;
                margin: 1rem 0;">
        <h4>📄 Données en temps réel</h4>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    run()