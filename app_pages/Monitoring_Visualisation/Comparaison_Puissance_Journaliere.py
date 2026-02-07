import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from scipy import stats
from typing import List, Tuple, Dict
from core.config import get_config
from logic.DataLoader import  DataLoader

# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']
# Initialize the loader
azure_loader = DataLoader(CONNECTION_STRING, CONTAINER_NAME)

# Get blob list
blob_list = azure_loader.get_blob_list()

def detect_time_interval(df: pd.DataFrame) -> Tuple[pd.Timedelta, str]:
    """
    Détecte automatiquement l'intervalle de temps entre les mesures
    Retourne l'intervalle et une description
    """
    if df.empty or len(df) < 2:
        return pd.Timedelta(minutes=5), "5min (défaut)"
    
    # Calculer les différences entre horodates consécutives
    time_diffs = df.index.to_series().diff().dropna()
    
    # Enlever les valeurs aberrantes (plus de 2h)
    time_diffs = time_diffs[time_diffs <= pd.Timedelta(hours=2)]
    
    if time_diffs.empty:
        return pd.Timedelta(minutes=5), "5min (défaut)"
    
    # Prendre la médiane pour éviter les valeurs aberrantes
    median_interval = time_diffs.median()
    
    # Convertir en description lisible
    total_seconds = median_interval.total_seconds()
    if total_seconds < 60:
        desc = f"{int(total_seconds)}sec"
    elif total_seconds < 3600:
        desc = f"{int(total_seconds/60)}min"
    else:
        desc = f"{int(total_seconds/3600)}h"
    
    return median_interval, desc

def fill_missing_data(df: pd.DataFrame, expected_interval: pd.Timedelta) -> pd.DataFrame:
    """
    Remplit les données manquantes et marque les trous
    """
    if df.empty:
        return df
    
    # Créer un index complet avec l'intervalle détecté
    start_time = df.index.min()
    end_time = df.index.max()
    complete_index = pd.date_range(start=start_time, end=end_time, freq=expected_interval)
    
    # Réindexer avec l'index complet
    df_complete = df.reindex(complete_index)
    
    # Marquer les valeurs manquantes
    df_complete['is_missing'] = df_complete['Puissance_moyenne_kW'].isna()
    
    # Interpoler les valeurs manquantes
    df_complete['Puissance_moyenne_kW'] = df_complete['Puissance_moyenne_kW'].interpolate(method='linear')
    df_complete['Energie_periode_kWh'] = df_complete['Energie_periode_kWh'].interpolate(method='linear')
    
    return df_complete

@st.cache_data
def load_daily_data(blob_name: str, selected_date) -> pd.DataFrame:
    """
    Charge les données pour un jour spécifique depuis Azure
    """
    # Charger toutes les données du fichier
    df = azure_loader.load_data(blob_name)
    
    if df.empty:
        return pd.DataFrame()
    
    # Convertir la date en datetime pour le filtrage
    if isinstance(selected_date, str):
        start_datetime = pd.to_datetime(selected_date)
    else:
        start_datetime = pd.to_datetime(selected_date)
    end_datetime = start_datetime + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    # Filtrer pour le jour spécifique
    daily_df = df.loc[start_datetime:end_datetime]
    
    return daily_df

@st.cache_data
def get_date_range(blob_name: str) -> Tuple[datetime, datetime]:
    """
    Récupère la plage de dates disponibles dans le fichier Azure
    """
    try:
        df = azure_loader.load_data(blob_name)
        if df.empty:
            return datetime.now().date(), datetime.now().date()
        
        min_date = df.index.min().date()
        max_date = df.index.max().date()
        
        return min_date, max_date
    except:
        return datetime.now().date(), datetime.now().date()

def create_comparison_chart(daily_datasets: Dict[str, pd.DataFrame], interval_desc: str) -> go.Figure:
    """
    Crée le graphique de comparaison avec gestion des données manquantes
    """
    fig = go.Figure()
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, (date, df) in enumerate(daily_datasets.items()):
        if df.empty:
            continue
            
        color = colors[i % len(colors)]
        
        # Créer une colonne heure en format string pour un meilleur affichage
        df_plot = df.copy()
        df_plot['heure_str'] = df_plot.index.strftime('%H:%M')
        df_plot['heure_float'] = df_plot.index.hour + df_plot.index.minute/60.0
        
        # Séparer les données réelles et interpolées
        real_data = df_plot[~df_plot['is_missing']]
        interpolated_data = df_plot[df_plot['is_missing']]
        
        # Tracer les données réelles
        fig.add_trace(go.Scatter(
            x=real_data['heure_float'],
            y=real_data['Puissance_moyenne_kW'],
            mode='lines+markers',
            name=f'{date}',
            line=dict(color=color, width=2),
            marker=dict(size=4),
            customdata=real_data['heure_str'],
            hovertemplate=f'<b>{date}</b><br>Heure: %{{customdata}}<br>Puissance: %{{y:.2f}} kW<extra></extra>'
        ))
        
        # Tracer les données interpolées (pointillés)
        if not interpolated_data.empty:
            fig.add_trace(go.Scatter(
                x=interpolated_data['heure_float'],
                y=interpolated_data['Puissance_moyenne_kW'],
                mode='lines',
                name=f'{date} (interpolé)',
                line=dict(color=color, width=1, dash='dot'),
                opacity=0.6,
                showlegend=False,
                customdata=interpolated_data['heure_str'],
                hovertemplate=f'<b>{date} (interpolé)</b><br>Heure: %{{customdata}}<br>Puissance: %{{y:.2f}} kW<extra></extra>'
            ))
    
    fig.update_layout(
        title=f'📊 Comparaison de Puissance Journalière (Intervalle: {interval_desc})',
        xaxis_title='Heure de la journée',
        yaxis_title='Puissance (kW)',
        height=600,
        template="plotly_white",
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Configurer l'axe X pour afficher les heures de façon lisible
    fig.update_xaxes(
        tickmode='linear',
        tick0=0,
        dtick=2,  # Tick toutes les 2 heures
        tickvals=list(range(0, 25, 2)),  # 0, 2, 4, 6, ..., 24
        ticktext=[f"{h:02d}:00" for h in range(0, 25, 2)],  # 00:00, 02:00, etc.
        range=[-0.5, 24.5],  # Petit padding pour voir les bords
        gridcolor='lightgray',
        gridwidth=1
    )
    
    # Ajouter des lignes verticales pour marquer les heures importantes
    for hour in [6, 12, 18]:  # Matin, midi, soir
        fig.add_vline(
            x=hour, 
            line_dash="dash", 
            line_color="gray", 
            opacity=0.3,
            annotation_text=f"{hour:02d}:00",
            annotation_position="top"
        )
    
    return fig

def run():
    # Header principal
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #2ca02c); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            📈 Comparaison Puissance Journalière
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown("""
        <div style="background: #f0f2f6; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
            <h2 style="color: #1f77b4; margin: 0;">⚙️ Configuration</h2>
        </div>
        """, unsafe_allow_html=True)

        if not blob_list:
            st.error("Impossible de récupérer la liste des fichiers Azure")
            return
        
        # Créer un dictionnaire pour mapper les noms affichés vers les noms réels
        building_display_map = {}
        display_names = []
        
        for blob_name in blob_list:
            # Enlever l'extension .xlsx/.xls du nom affiché
            if blob_name.lower().endswith(('.xlsx', '.xls')):
                display_name = blob_name.rsplit('.', 1)[0]  # Enlève l'extension
            else:
                display_name = blob_name  # Garde le nom original si pas d'extension Excel
            
            building_display_map[display_name] = blob_name
            display_names.append(display_name)
        
        # Utiliser les noms sans extension dans le selectbox
        selected_display_name = st.selectbox('🏗️ Sélection du Bâtiment', display_names)
        
        # Récupérer le nom réel du fichier
        selected_building = building_display_map[selected_display_name]
    
    try:
        # Récupérer la plage de dates disponibles
        min_date, max_date = get_date_range(selected_building)
        
        with st.sidebar:
            st.markdown("📅 **Sélection des jours à comparer**")
            
            # Date de référence (obligatoire)
            reference_date = st.date_input(
                "🎯 Jour de référence",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                help="Ce jour sera affiché en premier dans la légende"
            )
            
            # Section pour les dates de comparaison
            st.markdown("📊 **Jours de comparaison (optionnels)**")
            
            # Créer des colonnes pour organiser les sélecteurs
            col1, col2 = st.columns(2)
            
            with col1:
                comparison_date_1 = st.date_input(
                    "Jour 2",
                    value=None,
                    min_value=min_date,
                    max_value=max_date,
                    key="comp_1"
                )
                
                comparison_date_3 = st.date_input(
                    "Jour 4", 
                    value=None,
                    min_value=min_date,
                    max_value=max_date,
                    key="comp_3"
                )
            
            with col2:
                comparison_date_2 = st.date_input(
                    "Jour 3",
                    value=None,
                    min_value=min_date,
                    max_value=max_date,
                    key="comp_2"
                )
                
                comparison_date_4 = st.date_input(
                    "Jour 5",
                    value=None,
                    min_value=min_date,
                    max_value=max_date,
                    key="comp_4"
                )
            
            # Collecter toutes les dates de comparaison non nulles
            comparison_dates = [
                date for date in [comparison_date_1, comparison_date_2, comparison_date_3, comparison_date_4]
                if date is not None and date != reference_date
            ]
            
            # Afficher le nombre total de jours sélectionnés
            total_days = 1 + len(comparison_dates)
            st.info(f"📈 {total_days} jour(s) sélectionné(s)")
            
            # Afficher les informations du bâtiment
            st.markdown("### 📈 Informations")
            st.info(f"🏢 **Bâtiment:** {selected_display_name}")
            st.info(f"📅 **Période disponible:** {min_date} - {max_date}")
            
            # Afficher les dates sélectionnées
            if comparison_dates:
                with st.expander("🗓️ Dates sélectionnées"):
                    st.write(f"**Référence:** {reference_date}")
                    for i, date in enumerate(comparison_dates, 1):
                        st.write(f"**Comparaison {i}:** {date}")
    
        # Charger les données pour tous les jours sélectionnés
        daily_datasets = {}
        all_dates = [reference_date] + comparison_dates
        
        # Progress bar pour le chargement
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, date in enumerate(all_dates):
            status_text.text(f"Chargement des données pour {date}...")
            progress_bar.progress((i + 1) / len(all_dates))
            
            df = load_daily_data(selected_building, date)
            if not df.empty:
                daily_datasets[str(date)] = df
        
        progress_bar.empty()
        status_text.empty()
        
        if not daily_datasets:
            st.warning("Aucune donnée trouvée pour les dates sélectionnées")
            return
        
        # Détecter l'intervalle de temps sur le premier dataset disponible
        first_df = next(iter(daily_datasets.values()))
        expected_interval, interval_desc = detect_time_interval(first_df)
        
        # Traiter les données manquantes pour tous les datasets
        processed_datasets = {}
        for date, df in daily_datasets.items():
            processed_df = fill_missing_data(df, expected_interval)
            if not processed_df.empty:
                processed_datasets[date] = processed_df
        
        # Créer et afficher le graphique
        if processed_datasets:
            fig = create_comparison_chart(processed_datasets, interval_desc)
            st.plotly_chart(fig, use_container_width=True)
            
            # Statistiques par jour
            st.markdown("### 📊 Statistiques par Jour")
            
            stats_data = []
            for date, df in processed_datasets.items():
                df_real = df[~df['is_missing']]  # Données réelles uniquement
                stats = {
                    'Date': date,
                    'Points de mesure': len(df_real),
                    'Points interpolés': len(df) - len(df_real),
                    'Puissance moyenne (kW)': df_real['Puissance_moyenne_kW'].mean(),
                    'Puissance max (kW)': df_real['Puissance_moyenne_kW'].max(),
                    'Puissance min (kW)': df_real['Puissance_moyenne_kW'].min(),
                    '% données manquantes': (len(df) - len(df_real)) / len(df) * 100 if len(df) > 0 else 0
                }
                stats_data.append(stats)
            
            stats_df = pd.DataFrame(stats_data)
            
            # Formatter les colonnes numériques
            format_dict = {
                'Puissance moyenne (kW)': '{:.2f}',
                'Puissance max (kW)': '{:.2f}', 
                'Puissance min (kW)': '{:.2f}',
                '% données manquantes': '{:.1f}%'
            }
            
            st.dataframe(
                stats_df.style.format(format_dict),
                use_container_width=True
            )
            
            # Informations techniques
            st.markdown("### 🔧 Informations Techniques")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info(f"⏱️ **Intervalle détecté:** {interval_desc}")
            
            with col2:
                total_points = sum(len(df) for df in processed_datasets.values())
                st.info(f"📊 **Total points:** {total_points:,}")
            
            with col3:
                total_interpolated = sum(df['is_missing'].sum() for df in processed_datasets.values())
                st.info(f"🔄 **Points interpolés:** {total_interpolated:,}")
            
            # Légende explicative
            with st.expander("ℹ️ Guide d'interprétation"):
                st.markdown("""
                **Lecture du graphique :**
                - **Lignes pleines** : Données réelles mesurées
                - **Lignes pointillées** : Données interpolées (remplissage des trous)
                - **Survol** : Cliquez sur une courbe pour voir les détails
                
                **Gestion des données manquantes :**
                - Les intervalles de temps sont détectés automatiquement
                - Les trous dans les données sont comblés par interpolation linéaire
                - Le pourcentage de données manquantes est affiché dans les statistiques
                
                **Comparaison :**
                - Jusqu'à 5 jours peuvent être comparés simultanément
                - Chaque jour a une couleur distinctive
                - Les statistiques permettent d'analyser les différences quantitatives
                """)
        else:
            st.error("Impossible de traiter les données chargées")
            
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {str(e)}")
        st.exception(e)  # Pour le debug en développement

if __name__ == "__main__":
    run()