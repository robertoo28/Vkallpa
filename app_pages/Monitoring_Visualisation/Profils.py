import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import calendar
from scipy import stats
from azure.storage.blob import BlobServiceClient
from datetime import datetime
from core.config import get_config


# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']


@st.cache_resource
def init_azure_client():
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)

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
    # Configuration de la page
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #ff7f0e); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            📊 Analyse des Profils Énergétiques
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # Interface principale
    st.sidebar.header('⚙️ Paramètres Principaux')

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

    try:
        # Charger un échantillon pour déterminer les dates disponibles
        sample_df = load_azure_data(selected_building)
        if sample_df.empty:
            st.error("Aucune donnée trouvée dans ce fichier")
            return
        
        min_date = sample_df.index.min().date()
        max_date = sample_df.index.max().date()
        
        st.sidebar.markdown("📅 **Période d'analyse**")
        start_date = st.sidebar.date_input('Date de début', min_date, min_value=min_date, max_value=max_date)
        end_date = st.sidebar.date_input('Date de fin', max_date, min_value=min_date, max_value=max_date)
        
        # Charger les données filtrées
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
        st.sidebar.info(f"⚡ **Consommation totale:** {df['Energie_periode_kWh'].sum():.1f} kWh")

    # Creating time-based features in English first
    df['Heure'] = df.index.hour
    df['Jour_Semaine_EN'] = df.index.day_name()  # English day names
    df['Mois_EN'] = df.index.month_name()  # English month names
    df['Année'] = df.index.year
    df['Semaine_An'] = df.index.isocalendar().week
    df['Jour_Mois'] = df.index.day

    # Dictionary to map English to French without accents
    english_to_french = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi", "Thursday": "Jeudi", "Friday": "Vendredi",
        "Saturday": "Samedi", "Sunday": "Dimanche",
        "January": "Janvier", "February": "Fevrier", "March": "Mars", "April": "Avril", "May": "Mai", "June": "Juin",
        "July": "Juillet", "August": "Aout", "September": "Septembre", "October": "Octobre", "November": "Novembre",
        "December": "Decembre"
    }

    # Convert English names to French without accents
    df['Jour_Semaine'] = df['Jour_Semaine_EN'].map(english_to_french)
    df['Mois'] = df['Mois_EN'].map(english_to_french)

    # Drop temporary English columns
    df.drop(columns=['Jour_Semaine_EN', 'Mois_EN'], inplace=True)

    # Ordre des catégories
    jours_ordre = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    mois_ordre = ['Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre']
    df['Jour_Semaine'] = pd.Categorical(df['Jour_Semaine'], categories=jours_ordre, ordered=True)
    df['Mois'] = pd.Categorical(df['Mois'], categories=mois_ordre, ordered=True)

    # Fonction de visualisation générique améliorée
    def plot_profile(data, x, y, color, title, xlabel):
        fig = px.line(data, x=x, y=y, color=color, 
                     title=title, 
                     labels={x: xlabel, y: 'Énergie (kWh)', color: ''},
                     markers=True)
        fig.update_layout(
            height=500,
            template="plotly_white",
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=6))
        st.plotly_chart(fig, use_container_width=True)

    # 1. Profil énergétique sur 24 heures
    st.markdown("""
    <div style="background: linear-gradient(90deg, #ff7f0e, #2ca02c); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📈 Profil Énergétique sur 24 Heures</h2>
    </div>
    """, unsafe_allow_html=True)
    
    daily_profile = df.groupby(['Jour_Semaine', 'Heure'])['Energie_periode_kWh'].mean().reset_index()
    plot_profile(daily_profile, 'Heure', 'Energie_periode_kWh', 'Jour_Semaine',
                "📊 Consommation Moyenne par Heure de la Journée",
                "Heure de la Journée")

    # Statistiques du profil journalier
    col1, col2, col3 = st.columns(3)
    with col1:
        heure_max = daily_profile.loc[daily_profile['Energie_periode_kWh'].idxmax(), 'Heure']
        st.metric("🔍 Heure de pic", f"{int(heure_max)}h")
    
    with col2:
        heure_min = daily_profile.loc[daily_profile['Energie_periode_kWh'].idxmin(), 'Heure']
        st.metric("📉 Heure de minimum", f"{int(heure_min)}h")
    
    with col3:
        variation = (daily_profile['Energie_periode_kWh'].max() - daily_profile['Energie_periode_kWh'].min()) / daily_profile['Energie_periode_kWh'].mean() * 100
        st.metric("📊 Variation max-min (%)", f"{variation:.1f}%")

    # 2. Profil hebdomadaire type par mois
    st.markdown("""
    <div style="background: linear-gradient(90deg, #d62728, #ff7f0e); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📅 Profil Hebdomadaire Type par Mois</h2>
    </div>
    """, unsafe_allow_html=True)
    
    weekly_month_profile = df.groupby(['Mois', 'Jour_Semaine'])['Energie_periode_kWh'].mean().reset_index()
    plot_profile(weekly_month_profile, 'Jour_Semaine', 'Energie_periode_kWh', 'Mois',
                "📊 Profil Hebdomadaire Moyen par Mois",
                "Jour de la Semaine")

    # 3. Profil mensuel type par année
    st.markdown("""
    <div style="background: linear-gradient(90deg, #2ca02c, #17becf); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📆 Profil Mensuel Type par Année</h2>
    </div>
    """, unsafe_allow_html=True)
    
    monthly_year_profile = df.groupby(['Année', 'Mois'])['Energie_periode_kWh'].sum().reset_index()
    plot_profile(monthly_year_profile, 'Mois', 'Energie_periode_kWh', 'Année',
                "📊 Consommation Mensuelle par Année",
                "Mois")

    # Statistiques du profil mensuel
    if not monthly_year_profile.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            mois_max = monthly_year_profile.loc[monthly_year_profile['Energie_periode_kWh'].idxmax(), 'Mois']
            st.metric("🔍 Mois de pic", str(mois_max))
        
        with col2:
            mois_min = monthly_year_profile.loc[monthly_year_profile['Energie_periode_kWh'].idxmin(), 'Mois']
            st.metric("📉 Mois minimum", str(mois_min))
        
        with col3:
            var_mensuelle = monthly_year_profile['Energie_periode_kWh'].std() / monthly_year_profile['Energie_periode_kWh'].mean() * 100
            st.metric("📊 Variabilité (%)", f"{var_mensuelle:.1f}%")

    # 4. Profil hebdomadaire type par année
    st.markdown("""
    <div style="background: linear-gradient(90deg, #9467bd, #8c564b); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📊 Profil Hebdomadaire Type par Année</h2>
    </div>
    """, unsafe_allow_html=True)
    
    weekly_year_profile = df.groupby(['Année', 'Semaine_An'])['Energie_periode_kWh'].sum().reset_index()
    plot_profile(weekly_year_profile, 'Semaine_An', 'Energie_periode_kWh', 'Année',
                "📊 Profil Hebdomadaire Moyen par Année",
                "Numéro de Semaine")

    # 5. Résumé des insights
    st.markdown("""
    <div style="background: linear-gradient(90deg, #8c564b, #e377c2); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">💡 Patterns Identifiés</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Calculs d'insights
    total_energy = df['Energie_periode_kWh'].sum()
    peak_hour = df.groupby('Heure')['Energie_periode_kWh'].mean().idxmax()
    peak_day = df.groupby('Jour_Semaine')['Energie_periode_kWh'].sum().idxmax()
    
    # Calcul de la régularité
    daily_std = df.groupby(df.index.date)['Energie_periode_kWh'].sum().std()
    daily_mean = df.groupby(df.index.date)['Energie_periode_kWh'].sum().mean()
    regularity = (1 - daily_std/daily_mean) * 100 if daily_mean > 0 else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔍 Patterns Comportementaux")
        st.write(f"• **Heure de pic quotidien :** {peak_hour}h")
        st.write(f"• **Jour de pic hebdomadaire :** {peak_day}")
        
    with col2:
        st.markdown("#### 📊 Indicateurs de Performance")
        st.write(f"• **Consommation totale période :** {total_energy:.1f} kWh")
        st.write(f"• **Indice de régularité :** {regularity:.1f}%")

if __name__ == "__main__":
    run()