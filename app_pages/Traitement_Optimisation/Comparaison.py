import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from scipy import stats
import warnings
from core.config import get_config
warnings.filterwarnings('ignore')

# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']

# Taux de conversion kWh vers euros
EURO_PER_KWH = 0.17

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

@st.cache_data
def get_date_range(blob_name):
    """Récupère les dates min/max du fichier"""
    try:
        df = load_azure_data(blob_name)
        if df.empty:
            return None, None
        return df.index.min(), df.index.max()
    except:
        return None, None

def calculate_comparison_metrics(period_a, period_b, name_a="Période A", name_b="Période B", metric_column='Energie_periode_kWh'):
    metrics = {}
    
    total_a = period_a[metric_column].sum()
    total_b = period_b[metric_column].sum()
    
    evolution_pct = ((total_b - total_a) / total_a * 100) if total_a > 0 else 0
    
    avg_daily_a = period_a.resample('D').sum()[metric_column].mean()
    avg_daily_b = period_b.resample('D').sum()[metric_column].mean()
    avg_evolution_pct = ((avg_daily_b - avg_daily_a) / avg_daily_a * 100) if avg_daily_a > 0 else 0
    
    max_a = period_a[metric_column].max()
    max_b = period_b[metric_column].max()
    max_evolution_pct = ((max_b - max_a) / max_a * 100) if max_a > 0 else 0
    
    cv_a = (period_a[metric_column].std() / period_a[metric_column].mean() * 100) if period_a[metric_column].mean() > 0 else 0
    cv_b = (period_b[metric_column].std() / period_b[metric_column].mean() * 100) if period_b[metric_column].mean() > 0 else 0
    
    # Calcul de la variation en euros (uniquement pour l'énergie)
    euro_variation = None
    euro_variation_daily = None
    if metric_column == 'Energie_periode_kWh':
        euro_variation = (total_b - total_a) * EURO_PER_KWH
        euro_variation_daily = (avg_daily_b - avg_daily_a) * EURO_PER_KWH
    
    metrics = {
        'names': [name_a, name_b],
        'total_consumption': [total_a, total_b],
        'total_evolution_pct': evolution_pct,
        'avg_daily_consumption': [avg_daily_a, avg_daily_b],
        'avg_daily_evolution_pct': avg_evolution_pct,
        'max_consumption': [max_a, max_b],
        'max_evolution_pct': max_evolution_pct,
        'coefficient_variation': [cv_a, cv_b],
        'nb_days': [len(period_a.resample('D').sum()), len(period_b.resample('D').sum())],
        'euro_variation': euro_variation,
        'euro_variation_daily': euro_variation_daily
    }
    
    return metrics

def run():
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #ff7f0e); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            📊 Comparatif Périodes
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Interface principale
    st.sidebar.header("⚙️ Configuration")
    
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
        # Obtenir les dates min/max
        min_date, max_date = get_date_range(selected_building)
        if min_date is None or max_date is None:
            st.error("Impossible de récupérer la plage de dates")
            return
            
        min_date = min_date.date()
        max_date = max_date.date()
        
        # Affichage des informations dans la sidebar
        st.sidebar.markdown("### 📈 Informations sur les données")
        st.sidebar.info(f"🏢 **Bâtiment:** {selected_display_name}")
        st.sidebar.info(f"📅 **Période disponible:** {min_date} - {max_date}")
        st.sidebar.info(f"📊 **Durée totale:** {(max_date - min_date).days} jours")
        
        # Calcul des dates par défaut sécurisées
        default_end_a = min(min_date + timedelta(days=30), max_date)
        default_start_b = min(min_date + timedelta(days=365), max_date - timedelta(days=1))
        default_end_b = min(default_start_b + timedelta(days=30), max_date)
        
        # Sélection de la métrique à analyser
        metric_option = st.sidebar.selectbox(
            "📊 Métrique à analyser",
            ["Energie_periode_kWh", "Puissance_moyenne_kW"]
        )
        
        metric_label = "Énergie (kWh)" if metric_option == "Energie_periode_kWh" else "Puissance (kW)"
        
        # Comparaison Personnalisée
        st.markdown("""
        <div style="background: linear-gradient(90deg, #ff7f0e, #2ca02c); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
            <h2 style="color: white; margin: 0;">🔄 Comparaison Personnalisée</h2>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔵 Période A")
            start_date_a = st.date_input('Date de début A', min_date, 
                                       min_value=min_date, max_value=max_date, key="start_a")
            end_date_a = st.date_input('Date de fin A', default_end_a, 
                                     min_value=min_date, max_value=max_date, key="end_a")
            name_a = st.text_input("Nom de la période A", "Période A")
        
        with col2:
            st.subheader("🔴 Période B")
            start_date_b = st.date_input('Date de début B', default_start_b, 
                                       min_value=min_date, max_value=max_date, key="start_b")
            end_date_b = st.date_input('Date de fin B', default_end_b, 
                                     min_value=min_date, max_value=max_date, key="end_b")
            name_b = st.text_input("Nom de la période B", "Période B")
        
        # Options d'ajustement
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2ca02c, #17becf); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
            <h3 style="color: white; margin: 0;">⚙️ Options d'Ajustement</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            normalize_days = st.checkbox("Normaliser par nombre de jours", value=True)
        with col2:
            exclude_weekends = st.checkbox("Exclure les weekends", value=False)
        
        if st.button("🚀 Comparer les Périodes", type="primary"):
            with st.spinner("Chargement des données..."):
                period_a = load_azure_data(selected_building, start_date_a, end_date_a)
                period_b = load_azure_data(selected_building, start_date_b, end_date_b)
            
            if period_a.empty or period_b.empty:
                st.error("⏰ Pas de données pour les périodes sélectionnées")
                return
                
            # Exclusion des weekends si demandé
            if exclude_weekends:
                period_a = period_a[period_a.index.dayofweek < 5]
                period_b = period_b[period_b.index.dayofweek < 5]
                name_a += " (jours ouvrés)"
                name_b += " (jours ouvrés)"
            
            # Calcul des métriques
            metrics = calculate_comparison_metrics(
                period_a, period_b, name_a, name_b, metric_option
            )
            
            # Si normalisation demandée, afficher l'info
            if normalize_days and metrics['nb_days'][0] != metrics['nb_days'][1]:
                st.info(f"ℹ️ Normalisation appliquée - Période A: {metrics['nb_days'][0]} jours, Période B: {metrics['nb_days'][1]} jours")
            
            st.success("✅ Comparaison réalisée avec succès!")
            
            # Fonction pour créer des barres colorées
            def create_colored_bar(value, label):
                # Déterminer la couleur (rouge pour augmentation, vert pour diminution)
                color = "red" if value > 0 else "green"
                abs_value = min(abs(value) / 100, 1.0)  # Normalisation
                
                # Créer une barre de progression stylisée
                st.markdown(f"""
                    <div style="margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span><strong>{label}</strong></span>
                            <span>{value:.1f}%</span>
                        </div>
                        <div style="height: 10px; background: #f0f2f6; border-radius: 5px; margin-top: 5px;">
                            <div style="height: 100%; width: {abs_value*100}%; background: {color}; border-radius: 5px;"></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Métriques principales avec barres colorées
            st.markdown("""
            <div style="background: linear-gradient(90deg, #9467bd, #8c564b); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
                <h3 style="color: white; margin: 0;">📊 Évolution des Indicateurs Clés</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Afficher la variation en euros en haut si disponible
            if metrics['euro_variation'] is not None:
                st.markdown("""
                <div style="background: linear-gradient(90deg, #d62728, #e377c2); padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                    <h3 style="color: white; margin: 0; text-align: center;">💰 Impact Financier</h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    variation_color = "🔴" if metrics['euro_variation'] > 0 else "🟢"
                    st.metric(
                        "Variation Totale en Euros",
                        f"{metrics['euro_variation']:.2f} €",
                        delta=f"{abs(metrics['euro_variation']):.2f} € {'en plus' if metrics['euro_variation'] > 0 else 'économisés'}",
                        delta_color="inverse"
                    )
                with col2:
                    st.metric(
                        "Variation Moyenne par Jour",
                        f"{metrics['euro_variation_daily']:.2f} €/jour",
                        delta=f"{abs(metrics['euro_variation_daily']):.2f} €/jour",
                        delta_color="inverse"
                    )
                
                # Projection annuelle
                annual_projection = metrics['euro_variation_daily'] * 365
                type_text = "de surcoût" if annual_projection > 0 else "d'économies"
                pluriel = "s" if annual_projection > 0 else "les"
                st.info(f"📅 **Projection annuelle:** {annual_projection:.2f} € {type_text} potentiel{pluriel}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Évolution Totale",
                    f"{metrics['total_evolution_pct']:.1f}%",
                    delta=f"{metrics['total_consumption'][1] - metrics['total_consumption'][0]:.0f} {metric_label.split('(')[1][:-1]}",
                    delta_color="inverse"
                )
                create_colored_bar(metrics['total_evolution_pct'], "Évolution Totale")
                
            with col2:
                st.metric(
                    "Évolution Moyenne/Jour",
                    f"{metrics['avg_daily_evolution_pct']:.1f}%",
                    delta=f"{metrics['avg_daily_consumption'][1] - metrics['avg_daily_consumption'][0]:.0f} {metric_label.split('(')[1][:-1]}/jour",
                    delta_color="inverse"
                )
                create_colored_bar(metrics['avg_daily_evolution_pct'], "Évolution Moyenne/Jour")
                
            with col3:
                st.metric(
                    "Évolution Pic Max",
                    f"{metrics['max_evolution_pct']:.1f}%",
                    delta=f"{metrics['max_consumption'][1] - metrics['max_consumption'][0]:.0f} {metric_label.split('(')[1][:-1]}",
                    delta_color="inverse"
                )
                create_colored_bar(metrics['max_evolution_pct'], "Évolution Pic Max")
            
            # Tableau détaillé
            st.markdown("""
            <div style="background: linear-gradient(90deg, #17becf, #1f77b4); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
                <h3 style="color: white; margin: 0;">📋 Détail des Métriques</h3>
            </div>
            """, unsafe_allow_html=True)
            
            unit = metric_label.split('(')[1][:-1]
            
            # Créer le tableau avec ou sans ligne euros selon la métrique
            if metrics['euro_variation'] is not None:
                comparison_df = pd.DataFrame({
                    'Métrique': [f'Consommation Totale ({unit})', 
                               'Équivalent en Euros (€)',
                               f'Moyenne Journalière ({unit}/jour)',
                               'Équivalent en Euros/jour (€/jour)',
                               f'Pic Maximum ({unit})', 
                               'Coefficient de Variation (%)', 
                               'Nombre de Jours'],
                    name_a: [f"{metrics['total_consumption'][0]:.0f}",
                            f"{metrics['total_consumption'][0] * EURO_PER_KWH:.2f}",
                            f"{metrics['avg_daily_consumption'][0]:.0f}",
                            f"{metrics['avg_daily_consumption'][0] * EURO_PER_KWH:.2f}",
                            f"{metrics['max_consumption'][0]:.0f}",
                            f"{metrics['coefficient_variation'][0]:.1f}",
                            f"{metrics['nb_days'][0]}"],
                    name_b: [f"{metrics['total_consumption'][1]:.0f}",
                            f"{metrics['total_consumption'][1] * EURO_PER_KWH:.2f}",
                            f"{metrics['avg_daily_consumption'][1]:.0f}",
                            f"{metrics['avg_daily_consumption'][1] * EURO_PER_KWH:.2f}",
                            f"{metrics['max_consumption'][1]:.0f}",
                            f"{metrics['coefficient_variation'][1]:.1f}",
                            f"{metrics['nb_days'][1]}"],
                    'Évolution': [f"{metrics['total_evolution_pct']:.1f}%",
                                f"{metrics['euro_variation']:.2f} €",
                                f"{metrics['avg_daily_evolution_pct']:.1f}%",
                                f"{metrics['euro_variation_daily']:.2f} €/jour",
                                f"{metrics['max_evolution_pct']:.1f}%",
                                f"{metrics['coefficient_variation'][1] - metrics['coefficient_variation'][0]:.1f}pp",
                                f"{metrics['nb_days'][1] - metrics['nb_days'][0]:.0f}"]
                })
            else:
                comparison_df = pd.DataFrame({
                    'Métrique': [f'Consommation Totale ({unit})', 
                               f'Moyenne Journalière ({unit}/jour)',
                               f'Pic Maximum ({unit})', 
                               'Coefficient de Variation (%)', 
                               'Nombre de Jours'],
                    name_a: [f"{metrics['total_consumption'][0]:.0f}",
                            f"{metrics['avg_daily_consumption'][0]:.0f}",
                            f"{metrics['max_consumption'][0]:.0f}",
                            f"{metrics['coefficient_variation'][0]:.1f}",
                            f"{metrics['nb_days'][0]}"],
                    name_b: [f"{metrics['total_consumption'][1]:.0f}",
                            f"{metrics['avg_daily_consumption'][1]:.0f}",
                            f"{metrics['max_consumption'][1]:.0f}",
                            f"{metrics['coefficient_variation'][1]:.1f}",
                            f"{metrics['nb_days'][1]}"],
                    'Évolution (%)': [f"{metrics['total_evolution_pct']:.1f}%",
                                    f"{metrics['avg_daily_evolution_pct']:.1f}%",
                                    f"{metrics['max_evolution_pct']:.1f}%",
                                    f"{metrics['coefficient_variation'][1] - metrics['coefficient_variation'][0]:.1f}pp",
                                    f"{metrics['nb_days'][1] - metrics['nb_days'][0]:.0f}"]
                })
            
            st.dataframe(comparison_df, use_container_width=True)
            
    except Exception as e:
        st.error(f"⏰ Erreur: {str(e)}")
        st.info("Vérifiez votre connexion internet et les paramètres Azure")

if __name__ == "__main__":
    run()