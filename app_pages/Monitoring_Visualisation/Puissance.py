import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from azure.storage.blob import BlobServiceClient
from datetime import datetime
from scipy import stats
import plotly.graph_objects as go
from typing import Optional
from core.config import get_config

# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']

@st.cache_resource
def init_azure_client():
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)

def get_threshold_by_alarme_name(batiment: str, type_mesure: str = "Puissance") -> Optional[float]:
    """
    Obtiene el threshold de la primera alarma activa de un tipo específico.
    
    Args:
        batiment: Nombre del edificio
        type_mesure: Tipo de medida ("Puissance" o "Énergie")
    
    Returns:
        float: Threshold efectivo o None si no existe
    """
    if batiment not in st.session_state.get('alarmes_config', {}):
        return None
    
    alarmes = st.session_state.alarmes_config[batiment]
    
    # Filtrar alarmas activas del tipo especificado
    alarme = next(
        (a for a in alarmes 
         if a['type_mesure'] == type_mesure and a['statut'] == 'active'), 
        None
    )
    
    if alarme:
        return alarme['seuil'] * (alarme['pourcentage'] / 100)

def replace_outliers_with_mean(df, threshold=50):
    """Remplace les outliers par la moyenne"""
    df_cleaned = df.copy()
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        col_mean = df_cleaned[col].mean()
        z_scores = np.abs(stats.zscore(df_cleaned[col]))
        df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)
    
    return df_cleaned

@st.cache_data
def load_azure_data(blob_name, start_date=None, end_date=None):
    """Charge les données depuis Azure Blob Storage"""
    blob_service_client = init_azure_client()
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_name)
    
    data = blob_client.download_blob().readall()
    df = pd.read_excel(data, sheet_name='Donnees_Detaillees')
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    # Filtrer par dates si spécifié
    if start_date and end_date:
        start_datetime = pd.to_datetime(start_date)
        end_datetime = pd.to_datetime(end_date)
        df = df.loc[start_datetime:end_datetime]
    
    return replace_outliers_with_mean(df)

def get_azure_blob_list():
    """Récupère la liste des blobs Azure"""
    try:
        blob_service_client = init_azure_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        return [blob.name for blob in container_client.list_blobs()]
    except:
        return []

def run():
    # Interface utilisateur
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #ff7f0e); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            📈 Analyse de Puissance Énergétique
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.header('⚙️ Configuration')

    # Sélection du bâtiment avec extension masquée
    blob_list = get_azure_blob_list()
    
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
    selected_display_name = st.sidebar.selectbox('🏗️ Sélection du Bâtiment', display_names)
    
    # Récupérer le nom réel du fichier
    selected_building = building_display_map[selected_display_name]

    # Configuration du seuil de consommation
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚠️ Seuil d'alerte")
    power_threshold = get_threshold_by_alarme_name(selected_building)
    if power_threshold is None:
        power_threshold = np.inf

    try:
        # Charger un échantillon pour déterminer les dates disponibles
        sample_df = load_azure_data(selected_building)
        if sample_df.empty:
            st.error("Aucune donnée trouvée dans ce fichier")
            return
        
        min_date = sample_df.index.min().date()
        max_date = sample_df.index.max().date()
        
        # Sélection de la période
        st.sidebar.markdown("---")
        st.sidebar.markdown("📅 **Période d'analyse**")
        date_range = st.sidebar.date_input(
            "Sélectionnez la période", 
            [min_date, max_date], 
            min_value=min_date, 
            max_value=max_date
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            st.warning("Veuillez sélectionner une période complète")
            return
        
        # Chargement et traitement des données
        df = load_azure_data(selected_building, start_date=start_date, end_date=end_date)
        
        if df.empty:
            st.error("Aucune donnée trouvée pour la période sélectionnée")
            return
            
    except Exception as e:
        st.error(f"Erreur de connexion à Azure: {str(e)}")
        return

    # Affichage des informations sur les données
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📈 Informations sur les données")
    st.sidebar.info(f"🏢 **Bâtiment:** {selected_display_name}")
    st.sidebar.info(f"📅 **Période:** {start_date} - {end_date}")
    st.sidebar.info(f"📊 **Points de données:** {len(df):,}")
    if not df.empty:
        st.sidebar.info(f"⚡ **Puissance max:** {df['Puissance_moyenne_kW'].max():.2f} kW")

    # Calcul précis de l'heure de pic par jour
    try:
        # Grouper par jour et calculer le maximum et l'heure du pic
        daily_stats = df.groupby(pd.Grouper(freq='D')).apply(
            lambda x: pd.Series({
                'Puissance_Max': x['Puissance_moyenne_kW'].max(),
                'Heure_Pic': x.loc[x['Puissance_moyenne_kW'].idxmax()].name.time() if not x.empty and x['Puissance_moyenne_kW'].max() > 0 else None
            })
        ).dropna()
        
    except Exception as e:
        st.error(f"Erreur d'analyse : {str(e)}")
        return

    # Filtrage des données (au cas où il y aurait des jours sans données)
    filtered_data = daily_stats[daily_stats['Puissance_Max'] > 0]
    
    # Identifier les dépassements de seuil
    threshold_exceeded = filtered_data[filtered_data['Puissance_Max'] > power_threshold]
    
    # Afficher la notification d'alerte en haut de la page
    if not threshold_exceeded.empty:
        st.markdown("""
        <div style="background-color: #ff4444; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; border-left: 5px solid #cc0000;">
            <h3 style="color: white; margin: 0;">⚠️ ALERTE - Dépassements de Seuil Détectés</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Afficher le nombre de dépassements
        col_alert1, col_alert2, col_alert3 = st.columns(3)
        
        with col_alert1:
            st.metric(
                "🚨 Nombre de dépassements",
                f"{len(threshold_exceeded)}",
                delta=f"{(len(threshold_exceeded)/len(filtered_data)*100):.1f}% des jours",
                delta_color="inverse"
            )
        
        with col_alert2:
            max_exceeded = threshold_exceeded['Puissance_Max'].max()
            st.metric(
                "⚡ Pic maximal enregistré",
                f"{max_exceeded:.2f} kW",
                delta=f"+{(max_exceeded - power_threshold):.2f} kW au-dessus du seuil",
                delta_color="inverse"
            )
        
        with col_alert3:
            avg_exceeded = threshold_exceeded['Puissance_Max'].mean()
            st.metric(
                "📊 Moyenne des dépassements",
                f"{avg_exceeded:.2f} kW",
                delta=f"+{(avg_exceeded - power_threshold):.2f} kW au-dessus du seuil",
                delta_color="inverse"
            )
        
        # Tableau des dépassements
        st.markdown("""
        <div style="background: linear-gradient(90deg, #ff4444, #cc0000); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
            <h3 style="color: white; margin: 0;">🚨 Détails des Dépassements de Seuil</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Formatter le tableau des dépassements
        exceeded_display = threshold_exceeded.copy()
        exceeded_display.index = pd.to_datetime(exceeded_display.index).date
        exceeded_display['Heure_Pic'] = exceeded_display['Heure_Pic'].apply(
            lambda x: x.strftime("%H:%M") if pd.notnull(x) else "N/A"
        )
        exceeded_display['Puissance_Max'] = exceeded_display['Puissance_Max'].round(2)
        exceeded_display['Dépassement'] = (exceeded_display['Puissance_Max'] - power_threshold).round(2)
        
        # Renommer les colonnes
        exceeded_display.columns = ['Puissance Max (kW)', 'Heure du Pic', 'Dépassement (kW)']
        
        # Trier par dépassement décroissant
        exceeded_display = exceeded_display.sort_values('Dépassement (kW)', ascending=False)
        
        st.dataframe(
            exceeded_display.style.background_gradient(
                subset=['Dépassement (kW)'],
                cmap='Reds'
            ),
            use_container_width=True
        )
        
        st.markdown("---")

    # Visualisation interactive
    st.markdown("""
    <div style="background: linear-gradient(90deg, #ff7f0e, #2ca02c); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📊 Analyse des Pics de Puissance</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Créer le graphique en barres avec distinction de couleurs
    fig = go.Figure()
    
    # Barres normales (sous le seuil)
    normal_data = filtered_data[filtered_data['Puissance_Max'] <= power_threshold]
    fig.add_trace(go.Bar(
        x=normal_data.index,
        y=normal_data['Puissance_Max'],
        name='Normal',
        marker_color='#1f77b4',
        hovertemplate=(
            "<b>%{x|%d %B %Y}</b><br>"
            "<b>Pic de puissance</b>: %{y:.2f} kW<br>"
            "<extra></extra>"
        )
    ))
    
    # Barres au-dessus du seuil (en rouge)
    if not threshold_exceeded.empty:
        fig.add_trace(go.Bar(
            x=threshold_exceeded.index,
            y=threshold_exceeded['Puissance_Max'],
            name='Dépassement',
            marker_color='#ff4444',
            hovertemplate=(
                "<b>%{x|%d %B %Y}</b><br>"
                "<b>Pic de puissance</b>: %{y:.2f} kW<br>"
                "<b>⚠️ DÉPASSEMENT</b><br>"
                "<extra></extra>"
            )
        ))
        
        # Ajouter des points rouges pour marquer les dépassements
        fig.add_trace(go.Scatter(
            x=threshold_exceeded.index,
            y=threshold_exceeded['Puissance_Max'],
            mode='markers',
            name='Points d\'alerte',
            marker=dict(
                color='darkred',
                size=12,
                symbol='circle',
                line=dict(color='white', width=2)
            ),
            hovertemplate=(
                "<b>%{x|%d %B %Y}</b><br>"
                "<b>⚠️ ALERTE</b>: %{y:.2f} kW<br>"
                "<extra></extra>"
            )
        ))
    
    # Ajouter la ligne de seuil
    fig.add_hline(
        y=power_threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Seuil: {power_threshold} kW",
        annotation_position="right",
        annotation=dict(font_size=12, font_color="red")
    )
    
    fig.update_layout(
        title='📈 Puissance maximale journalière avec seuil d\'alerte',
        xaxis_title='Date',
        yaxis_title='Puissance Maximale (kW)',
        plot_bgcolor='white',
        hovermode='x unified',
        template="plotly_white",
        height=600,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistiques en metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_power = filtered_data['Puissance_Max'].mean()
        st.metric("⚡ Puissance Moyenne", f"{avg_power:.2f} kW")
    
    with col2:
        max_power = filtered_data['Puissance_Max'].max()
        max_date = filtered_data['Puissance_Max'].idxmax()
        st.metric("🔍 Puissance Maximale", f"{max_power:.2f} kW", 
                 delta=f"Le {max_date.strftime('%d/%m/%Y')}")
    
    with col3:
        # Calculer l'heure de pic la plus fréquente
        hours = pd.to_datetime(filtered_data['Heure_Pic'].dropna(), format='%H:%M:%S').dt.hour
        if not hours.empty:
            most_common_hour = hours.mode()[0]
            st.metric("🕐 Heure de pic fréquente", f"{most_common_hour}:00")
        else:
            st.metric("🕐 Heure de pic fréquente", "N/A")
    
    with col4:
        # Pourcentage de conformité au seuil
        conformity_rate = ((len(filtered_data) - len(threshold_exceeded)) / len(filtered_data) * 100)
        st.metric("✅ Taux de conformité", f"{conformity_rate:.1f}%")
    
    # Affichage du tableau de données complet
    st.markdown("""
    <div style="background: linear-gradient(90deg, #2ca02c, #17becf); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📋 Détails Complets des Pics de Puissance</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Formatter le tableau pour afficher correctement les heures
    display_df = filtered_data.copy()
    display_df.index = pd.to_datetime(display_df.index).date
    display_df['Heure_Pic'] = display_df['Heure_Pic'].apply(
        lambda x: x.strftime("%H:%M") if pd.notnull(x) else "N/A"
    )
    display_df['Puissance_Max'] = display_df['Puissance_Max'].round(2)
    display_df['Statut'] = display_df['Puissance_Max'].apply(
        lambda x: '🚨 DÉPASSEMENT' if x > power_threshold else '✅ Normal'
    )
    
    # Renommer les colonnes pour l'affichage
    display_df.columns = ['Puissance Max (kW)', 'Heure du Pic', 'Statut']
    
    # Appliquer un style conditionnel
    def highlight_exceeded(row):
        if '🚨' in row['Statut']:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        display_df.style.apply(highlight_exceeded, axis=1),
        use_container_width=True
    )

if __name__ == "__main__":
    run()