import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from scipy import stats
from core.config import get_config


def run():

    config = get_config()
    CONNECTION_STRING = config['azure']['connection_string']
    CONTAINER_NAME = config['azure']['container_name']

    def replace_outliers_with_mean(df, threshold=50):
        df_cleaned = df.copy()
        numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            col_mean = df_cleaned[col].mean()
            z_scores = np.abs(stats.zscore(df_cleaned[col]))
            df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)
        
        return df_cleaned

    # Dictionnaire des superficies
    superficie_batiments = {
        'B11_hors salle spectacle': 2500,
        'B11_spectacle': 500,
        'B15_Elec_General': 5000,
        'Centre du Taur': 4850,
        'INSPE Centre des Hautes Pyrénées': 2600,
        'INSPE Saint Agne': 7900,
        'INSPE centre du Gers': 2600,
        'IUT de Blagnac': 8300,
        'IUT de Figeac': 7500,
        'Mirail _ arrivée générale': 130000,
        'Mirail _ bat 32': 1600,
        'PT_05_General': 8000,
        'UO': 3000
    }

    def trouver_superficie(nom_blob):
        for batiment in superficie_batiments:
            if batiment in nom_blob:
                return superficie_batiments[batiment]
        return None

    @st.cache_resource
    def init_azure_client():
        return BlobServiceClient.from_connection_string(CONNECTION_STRING)

    blob_service_client = init_azure_client()
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    @st.cache_data
    def load_data(blob_name):
        blob_client = container_client.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        df = pd.read_excel(data, sheet_name='Donnees_Detaillees', engine='openpyxl')
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df

    # Interface principale avec CSS
    st.title('Comparatif Énergétique des Bâtiments')
    
    # CSS pour améliorer l'apparence
    st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
        text-align: center;
    }
    .insight-box {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Chargement de la liste des bâtiments
    with st.spinner("Connexion en cours..."):
        blob_list = [blob.name for blob in container_client.list_blobs()]
    
    if blob_list:
        st.success(f"✅ {len(blob_list)} bâtiment(s) trouvé(s) dans le conteneur '{CONTAINER_NAME}'")
    else:
        st.error(f"❌ Aucun fichier trouvé dans le conteneur '{CONTAINER_NAME}'")
        st.stop()

    # Sidebar pour les paramètres
    st.sidebar.header('Paramètres Principaux')
    
    # Affichage des superficies disponibles
    with st.sidebar.expander("Superficies Configurées", expanded=False):
        st.markdown("**Bâtiments avec superficie connue:**")
        for batiment, superficie in superficie_batiments.items():
            st.markdown(f"• **{batiment}**: {superficie:,} m²")

    # Créer un dictionnaire pour mapper les noms affichés vers les noms réels
    building_display_map = {}
    display_names = []
    
    for blob_name in blob_list:
        # Enlever l'extension .xlsx/.xls du nom affiché
        if blob_name.lower().endswith(('.xlsx', '.xls')):
            display_name = blob_name.rsplit('.', 1)[0]
        else:
            display_name = blob_name
        
        building_display_map[display_name] = blob_name
        display_names.append(display_name)

    # Utiliser les noms sans extension dans le multiselect
    selected_display_names = st.sidebar.multiselect(
        f'Sélection des Bâtiments ({len(display_names)} disponibles)', 
        display_names,
        help="Sélectionnez au moins 2 bâtiments pour la comparaison"
    )
    
    # Récupérer les noms réels des fichiers
    selected_buildings = [building_display_map[name] for name in selected_display_names]
    
    normalize = st.sidebar.checkbox(
        'Normaliser par superficie (kWh/m²)', 
        help="Divise la consommation par la superficie pour comparer l'intensité énergétique"
    )

    if len(selected_buildings) < 2:
        st.error("⚠️ Veuillez sélectionner au moins deux bâtiments pour afficher les graphiques.")
        st.info("💡 Utilisez le menu latéral pour sélectionner vos bâtiments à comparer.")
        
        # Affichage de la liste des bâtiments disponibles
        st.subheader("Bâtiments Disponibles")
        col1, col2 = st.columns(2)
        
        for i, display_name in enumerate(display_names):
            building = building_display_map[display_name]
            superficie = trouver_superficie(building)
            superficie_text = f"{superficie:,} m²" if superficie else "Superficie inconnue"
            
            with col1 if i % 2 == 0 else col2:
                st.markdown(f"""
                <div class="metric-card">
                    <h5>{display_name}</h5>
                    <p>{superficie_text}</p>
                </div>
                """, unsafe_allow_html=True)
                
    else:
        # Chargement des données
        with st.spinner("Chargement des données..."):
            dfs = {}
            superficie_info = {}
            
            for building in selected_buildings:
                dfs[building] = load_data(building)
                dfs[building] = replace_outliers_with_mean(dfs[building])
                superficie_info[building] = trouver_superficie(building)

        # Vérification des superficies pour la normalisation
        missing_superficies = [b for b in selected_buildings if not superficie_info[b] and normalize]
        if missing_superficies and normalize:
            missing_display_names = [building_display_map[b] if b in building_display_map.values() else b for b in missing_superficies]
            st.markdown(f"""
            <div class="warning-box">
                <h5>⚠️ Attention - Superficies Manquantes</h5>
                <p>Les bâtiments suivants n'ont pas de superficie définie et ne seront pas normalisés :</p>
                <ul>{''.join([f'<li>{b}</li>' for b in missing_display_names])}</ul>
            </div>
            """, unsafe_allow_html=True)

        # Sélection des dates
        min_date = min(df.index.min().date() for df in dfs.values())
        max_date = max(df.index.max().date() for df in dfs.values())
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input('Date début', min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input('Date fin', max_date, min_value=min_date, max_value=max_date)

        # Filtrage des données par dates
        filtered_dfs = {building: df.loc[str(start_date):str(end_date)] for building, df in dfs.items()}

        # Navigation
        page = st.sidebar.radio("Navigation", ["Graphiques Principaux", "Insights & Analyses"])

        if page == "Graphiques Principaux":
            st.header("Analyse Temporelle Comparative")
            
            # Contrôles de l'interface
            col1, col2, col3 = st.columns(3)
            with col1:
                metric = st.selectbox('Mesure à afficher', ['Energie', 'Puissance'])
            with col2:
                chart_type = st.selectbox('Type de visualisation', ['Ligne', 'Barres'])
            with col3:
                time_frame = st.select_slider('Agrégation temporelle', 
                                            options=['Heure', 'Jour', 'Semaine', 'Mois', 'Année'],
                                            value='Jour')
            
            resample_map = {
                'Heure': 'H',
                'Jour': 'D',
                'Semaine': 'W-MON',
                'Mois': 'M',
                'Année': 'A'
            }
            
            # Resampling et normalisation
            resampled_dfs = {}
            for building, df in filtered_dfs.items():
                resampled = df.resample(resample_map[time_frame]).agg({
                    'Energie_periode_kWh': 'sum' if metric == 'Energie' else 'mean',
                    'Puissance_moyenne_kW': 'mean'
                })
                
                # Application de la normalisation
                if normalize and metric == 'Energie' and superficie_info[building]:
                    superficie = superficie_info[building]
                    resampled['Energie_periode_kWh'] = resampled['Energie_periode_kWh'] / superficie
                
                resampled_dfs[building] = resampled

            # Création du graphique
            ylabel = 'kWh/m²' if (normalize and metric == 'Energie') else 'kWh' if metric == 'Energie' else 'kW'
            title = f"Consommation {metric} - {time_frame}"
            if normalize and metric == 'Energie':
                title += " (Normalisée par m²)"
            
            fig = go.Figure()
            
            for i, (building, resampled) in enumerate(resampled_dfs.items()):
                data_col = 'Energie_periode_kWh' if metric == 'Energie' else 'Puissance_moyenne_kW'
                data = resampled[data_col]
                # Utiliser le nom affiché (sans extension) pour la légende
                building_display = next((name for name, blob in building_display_map.items() if blob == building), building)
                
                if chart_type == 'Ligne':
                    fig.add_trace(go.Scatter(
                        x=data.index,
                        y=data,
                        mode='lines+markers',
                        name=building_display,
                        line=dict(width=3)
                    ))
                else:
                    fig.add_trace(go.Bar(
                        x=data.index,
                        y=data,
                        name=building_display,
                        opacity=0.8
                    ))

            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title=ylabel,
                hovermode='x unified',
                height=600,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )

            st.plotly_chart(fig, use_container_width=True)

        elif page == "Insights & Analyses":
            st.header("Insights et Analyses Comparatives")
            
            # Calcul des métriques pour insights
            insights_data = {}
            for building, df in filtered_dfs.items():
                # Utiliser le nom affiché (sans extension)
                building_clean = next((name for name, blob in building_display_map.items() if blob == building), building)
                
                # Données énergie
                total_energie = df['Energie_periode_kWh'].sum()
                mean_energie = df['Energie_periode_kWh'].mean()
                
                # Données puissance
                mean_puissance = df['Puissance_moyenne_kW'].mean()
                max_puissance = df['Puissance_moyenne_kW'].max()
                
                # Normalisation si demandée
                superficie = superficie_info[building]
                if normalize and superficie:
                    total_energie_norm = total_energie / superficie
                    mean_energie_norm = mean_energie / superficie
                else:
                    total_energie_norm = total_energie
                    mean_energie_norm = mean_energie
                
                insights_data[building_clean] = {
                    'total_energie': total_energie_norm,
                    'moyenne_energie': mean_energie_norm,
                    'moyenne_puissance': mean_puissance,
                    'max_puissance': max_puissance,
                    'superficie': superficie or 'Non définie',
                    'building_original': building
                }

            # Affichage du classement
            st.subheader("Classement des Bâtiments - Consommation Énergétique")
            
            # Tri par consommation totale
            sorted_buildings = sorted(insights_data.items(), key=lambda x: x[1]['total_energie'], reverse=True)
            
            cols = st.columns(min(len(sorted_buildings), 4))
            for i, (building, metrics) in enumerate(sorted_buildings):
                col_idx = i % 4
                with cols[col_idx]:
                    rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}️⃣"
                    unit = 'kWh/m²' if normalize else 'kWh'
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>{rank_emoji} {building}</h4>
                        <p><strong>Total:</strong> {metrics['total_energie']:.2f} {unit}</p>
                        <p><strong>Moyenne:</strong> {metrics['moyenne_energie']:.2f} {unit}</p>
                        <p><strong>Puissance moy:</strong> {metrics['moyenne_puissance']:.2f} kW</p>
                        <p><strong>Superficie:</strong> {metrics['superficie']} m²</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Insights automatiques
            st.subheader("Insights Automatiques")
            
            # Analyse comparative
            highest_consumer = max(insights_data.items(), key=lambda x: x[1]['total_energie'])
            lowest_consumer = min(insights_data.items(), key=lambda x: x[1]['total_energie'])
            
            # Calculs des différences
            total_diff = highest_consumer[1]['total_energie'] - lowest_consumer[1]['total_energie']
            percent_diff = ((highest_consumer[1]['total_energie'] - lowest_consumer[1]['total_energie']) / lowest_consumer[1]['total_energie']) * 100
            
            unit = 'kWh/m²' if normalize else 'kWh'
            
            st.markdown(f"""
            <div class="insight-box">
                <h5>💡 Analyse Comparative - Énergie</h5>
                <ul>
                    <li><strong>Plus gros consommateur:</strong> {highest_consumer[0]} ({highest_consumer[1]['total_energie']:.2f} {unit})</li>
                    <li><strong>Plus faible consommateur:</strong> {lowest_consumer[0]} ({lowest_consumer[1]['total_energie']:.2f} {unit})</li>
                    <li><strong>Écart absolu:</strong> {total_diff:.2f} {unit}</li>
                    <li><strong>Écart relatif:</strong> {percent_diff:.1f}% de différence</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            # Analyse de puissance
            highest_power = max(insights_data.items(), key=lambda x: x[1]['moyenne_puissance'])
            lowest_power = min(insights_data.items(), key=lambda x: x[1]['moyenne_puissance'])
            
            st.markdown(f"""
            <div class="insight-box">
                <h5>⚡ Analyse de Puissance</h5>
                <ul>
                    <li><strong>Plus forte puissance moyenne:</strong> {highest_power[0]} ({highest_power[1]['moyenne_puissance']:.2f} kW)</li>
                    <li><strong>Plus faible puissance moyenne:</strong> {lowest_power[0]} ({lowest_power[1]['moyenne_puissance']:.2f} kW)</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            # Graphiques d'analyse
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Distribution des Consommations")
                
                # Graphique en barres des totaux
                buildings_names = list(insights_data.keys())
                total_values = [insights_data[b]['total_energie'] for b in buildings_names]
                
                fig_bar = go.Figure(data=[
                    go.Bar(x=buildings_names, y=total_values, 
                          marker_color='skyblue', opacity=0.8)
                ])
                fig_bar.update_layout(
                    title=f"Consommation Totale ({unit})",
                    xaxis_title="Bâtiments",
                    yaxis_title=f"Consommation ({unit})",
                    height=400
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                st.subheader("Analyse de Puissance")
                
                # Graphique de puissance
                power_values = [insights_data[b]['moyenne_puissance'] for b in buildings_names]
                
                fig_power = go.Figure(data=[
                    go.Bar(x=buildings_names, y=power_values, 
                          marker_color='orange', opacity=0.8)
                ])
                fig_power.update_layout(
                    title="Puissance Moyenne (kW)",
                    xaxis_title="Bâtiments",
                    yaxis_title="Puissance (kW)",
                    height=400
                )
                st.plotly_chart(fig_power, use_container_width=True)

            # Analyse de corrélation si plus de 2 bâtiments
            if len(selected_buildings) > 2:
                st.subheader("Analyse de Corrélation")
                
                # Préparation des données pour corrélation
                correlation_data = pd.DataFrame()
                for building, df in filtered_dfs.items():
                    building_clean = next((name for name, blob in building_display_map.items() if blob == building), building)
                    correlation_data[building_clean] = df['Energie_periode_kWh']
                
                # Calcul et affichage de la matrice de corrélation
                corr_matrix = correlation_data.corr()
                
                fig_corr = px.imshow(
                    corr_matrix,
                    text_auto=True,
                    aspect="auto",
                    title="Matrice de Corrélation - Consommations Énergétiques",
                    color_continuous_scale="RdYlBu"
                )
                st.plotly_chart(fig_corr, use_container_width=True)

    # Informations dans la sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Configuration:**")
    st.sidebar.code(f"Conteneur: {CONTAINER_NAME}")
    
    if normalize:
        st.sidebar.markdown("**Normalisation active**")
        st.sidebar.info("Les valeurs d'énergie sont divisées par la superficie")

if __name__ == "__main__":
    run()