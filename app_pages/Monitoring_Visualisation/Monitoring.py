import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import matplotlib.dates as mdates
from azure.storage.blob import BlobServiceClient
from scipy import stats
from core.config import get_config

# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']

# Configuration des vacances
VACANCES = [
    ('20/12/2020', '3/1/2021'), ('21/2/2021', '28/2/2021'), ('5/4/2021', '5/4/2021'),
    ('25/4/2021', '2/5/2021'), ('13/5/2021', '16/5/2021'), ('24/5/2021', '24/5/2021'),
    ('17/7/2021', '22/8/2021'), ('1/11/2021', '1/11/2021'), ('11/11/2021', '11/11/2021'),
    ('18/12/2021', '3/1/2022'), ('26/2/2022', '6/3/2022'), ('18/4/2022', '18/4/2022'),
    ('23/4/2022', '8/5/2022'), ('26/5/2022', '29/5/2022'), ('23/7/2022', '21/8/2022'),
    ('29/10/2022', '6/11/2022'), ('1/11/2022', '1/11/2022'), ('11/11/2022', '11/11/2022'),
    ('17/12/2022', '2/1/2023'), ('25/2/2023', '6/3/2023'), ('10/4/2023', '10/4/2023'),
    ('24/4/2023', '7/5/2023'), ('1/5/2023', '1/5/2023'), ('8/5/2023', '8/5/2023'),
    ('18/5/2023', '18/5/2023'), ('23/7/2023', '19/8/2023'), ('28/10/2023', '5/11/2023'),
    ('1/11/2023', '1/11/2023'), ('23/12/2023', '8/1/2024'), ('17/2/2024', '26/2/2024'),
    ('1/4/2022', '1/4/2022'), ('6/4/2024', '22/4/2024'), ('1/5/2024', '1/5/2024'),
    ('8/5/2024', '13/5/2024'), ('20/7/2024', '18/8/2024'), ('26/10/2024', '3/11/2024'),
    ('1/11/2024', '1/11/2024'), ('11/11/2024', '11/11/2024'), ('21/12/2024', '5/1/2025'),
    ('22/2/2025', '3/3/2025'), ('12/4/2025', '28/4/2025'), ('28/5/2025', '2/6/2025')
]

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

def prepare_vacances_df():
    """Prépare le DataFrame des vacances"""
    vacances_df = pd.DataFrame(VACANCES, columns=['Début', 'Fin'])
    vacances_df['Début'] = pd.to_datetime(vacances_df['Début'], dayfirst=True)
    vacances_df['Fin'] = pd.to_datetime(vacances_df['Fin'], dayfirst=True)
    return vacances_df

@st.cache_data
def load_azure_data(blob_name):
    """Charge les données depuis Azure Blob Storage"""
    blob_service_client = init_azure_client()
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_name)
    
    data = blob_client.download_blob().readall()
    df = pd.read_excel(data, sheet_name='Donnees_Detaillees', engine='openpyxl')
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    return replace_outliers_with_mean(df)

def get_azure_blob_list():
    """Récupère la liste des blobs Azure"""
    try:
        blob_service_client = init_azure_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        return [blob.name for blob in container_client.list_blobs()]
    except:
        return []

def add_vacation_periods(fig, filtered_df, start_date, end_date, vacances_df):
    """Ajoute les périodes de vacances au graphique"""
    vacances_filtrees = vacances_df[
        (vacances_df['Fin'] >= pd.to_datetime(start_date)) & 
        (vacances_df['Début'] <= pd.to_datetime(end_date))
    ]
    
    has_data_in_vacances = False
    for _, row in vacances_filtrees.iterrows():
        vacance_mask = (filtered_df.index >= row['Début']) & (filtered_df.index <= row['Fin'])
        if filtered_df[vacance_mask].shape[0] > 0:
            has_data_in_vacances = True
            fig.add_vrect(
                x0=row['Début'],
                x1=row['Fin'],
                fillcolor="rgba(255, 0, 0, 0.1)",
                line_width=0,
                name="Vacances",
                legendgroup="vacances",
                showlegend=False
            )
    
    if has_data_in_vacances:
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='lines',
            line=dict(color='rgba(255, 0, 0, 0.1)', width=10),
            showlegend=True,
            name="Périodes de vacances",
            legendgroup="vacances"
        ))
    
    return fig

def run():
    # Header principal avec style
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #ff7f0e); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            Monitoring Énergétique Unifié
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar avec meilleur design
    with st.sidebar:
        st.markdown("""
        <div style="background: #f0f2f6; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
            <h2 style="color: #1f77b4; margin: 0;">Configuration</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Sélection du bâtiment avec extension masquée
        blob_list = get_azure_blob_list()
        
        if not blob_list:
            st.error("Impossible de récupérer la liste des fichiers")
            return
        
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
        
        # Utiliser les noms sans extension dans le selectbox
        selected_display_name = st.selectbox('Sélection du Bâtiment', display_names)
        
        # Récupérer le nom réel du fichier
        selected_building = building_display_map[selected_display_name]
        
        try:
            df = load_azure_data(selected_building)
            
            min_date = df.index.min().date()
            max_date = df.index.max().date()
            
            st.markdown("**Période d'analyse**")
            start_date = st.date_input('Date de début', min_date, min_value=min_date, max_value=max_date)
            end_date = st.date_input('Date de fin', max_date, min_value=min_date, max_value=max_date)
            
            filtered_df = df.loc[str(start_date):str(end_date)]
            
            if filtered_df.empty:
                st.error("Aucune donnée trouvée pour la période sélectionnée")
                return
                
        except Exception as e:
            st.error(f"Erreur de chargement: {str(e)}")
            return
        
        # Navigation avec style amélioré
        st.markdown("""
        <div style="background: #e8f4fd; padding: 1rem; border-radius: 10px; margin: 1rem 0;">
            <h3 style="color: #1f77b4; margin: 0;">Navigation</h3>
        </div>
        """, unsafe_allow_html=True)

    # Préparer les données de vacances
    vacances_df = prepare_vacances_df()

    # Pages de navigation avec cards visuelles
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Graphiques\nPrincipaux", use_container_width=True):
            st.session_state.page = "graphs"
    
    with col2:
        if st.button("Heatmap\nTemporelle", use_container_width=True):
            st.session_state.page = "heatmap"
    
    with col3:
        if st.button("Calendar\nHeatmap", use_container_width=True):
            st.session_state.page = "calendar"
    
    with col4:
        if st.button("Distribution\nBoxplots", use_container_width=True):
            st.session_state.page = "boxplots"

    # Inicializar página por defecto
    if 'page' not in st.session_state:
        st.session_state.page = "graphs"

    # Contenido de las páginas avec separadores visuales
    st.markdown("---")

    if st.session_state.page == "graphs":
        st.markdown("""
        <div style="background: linear-gradient(90deg, #ff7f0e, #2ca02c); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
            <h2 style="color: white; margin: 0;">Analyse Temporelle</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Controles en columnas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metric = st.selectbox('Mesure à afficher', ['Energie', 'Puissance'])
        
        with col2:
            chart_type = st.selectbox('Type de visualisation', ['Ligne', 'Barres'])
        
        with col3:
            time_frame = st.select_slider('Agrégation temporelle', 
                                         options=['Heure', 'Jour', 'Semaine', 'Mois', 'Année'],
                                         value='Jour')
        
        with col4:
            show_vacances = st.checkbox("Afficher vacances", value=True)
        
        resample_map = {
            'Heure': 'H',
            'Jour': 'D',
            'Semaine': 'W-MON',
            'Mois': 'M',
            'Année': 'A'
        }
        
        try:
            resampled = filtered_df.resample(resample_map[time_frame]).agg({
                'Energie_periode_kWh': 'sum' if metric == 'Energie' else 'mean',
                'Puissance_moyenne_kW': 'mean'
            })
            
            if metric == 'Energie':
                data = resampled['Energie_periode_kWh']
                ylabel = 'Énergie (kWh)'
            else:
                data = resampled['Puissance_moyenne_kW']
                ylabel = 'Puissance (kW)'
            
            if chart_type == 'Ligne':
                fig = px.line(data, title=f"{metric} - Agrégation {time_frame}")
                fig.update_traces(line=dict(width=3))
            else:
                fig = px.bar(data, title=f"{metric} - Agrégation {time_frame}")
                fig.update_traces(marker_color='#1f77b4')

            # Ajouter les périodes de vacances si demandé
            if show_vacances:
                fig = add_vacation_periods(fig, filtered_df, start_date, end_date, vacances_df)

            fig.update_layout(
                yaxis_title=ylabel, 
                xaxis_title='Date',
                height=500,
                template="plotly_white"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Données avec style
            st.markdown("### Données Détaillées")
            st.dataframe(resampled, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erreur lors du resampling: {str(e)}")

    elif st.session_state.page == "heatmap":
        st.markdown("""
        <div style="background: linear-gradient(90deg, #d62728, #ff7f0e); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
            <h2 style="color: white; margin: 0;">Analyse de Densité Temporelle</h2>
        </div>
        """, unsafe_allow_html=True)
        
        heatmap_df = filtered_df.copy()
        heatmap_df['Heure'] = heatmap_df.index.hour
        heatmap_df['Jour'] = heatmap_df.index.day_name()
        
        english_to_french = {
            "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
            "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi",
            "Sunday": "Dimanche"
        }
        
        heatmap_df['Jour'] = heatmap_df['Jour'].map(english_to_french)
        days_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        pivot_table = pd.pivot_table(heatmap_df,
                                     values='Puissance_moyenne_kW',
                                     index='Jour',
                                     columns='Heure',
                                     aggfunc='mean').reindex(days_order)
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_table.values,
            x=pivot_table.columns,
            y=pivot_table.index,
            colorscale='Viridis',
            hovertemplate='Heure: %{x}<br>Jour: %{y}<br>Puissance: %{z:.2f} kW<extra></extra>'))
        
        fig.update_layout(
            title='Puissance Moyenne par Heure et Jour',
            xaxis_title='Heure de la Journée',
            yaxis_title='Jour de la Semaine',
            height=500,
            template="plotly_white")
        
        st.plotly_chart(fig, use_container_width=True)

    elif st.session_state.page == "calendar":
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2ca02c, #17becf); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
            <h2 style="color: white; margin: 0;">Distribution Journalière par Année</h2>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            # Utiliser plotly-calplot (recommandé et compatible pandas 2.0+)
            try:
                from plotly_calplot import calplot
                
                # Préparer les données pour plotly-calplot
                daily_data = filtered_df.resample('D').sum()['Energie_periode_kWh'].reset_index()
                daily_data.columns = ['date', 'value']
                
                # Filtrer les valeurs nulles ou négatives
                daily_data = daily_data[daily_data['value'] > 0]
                
                # Créer le calendar heatmap interactif
                fig = calplot(
                    daily_data, 
                    x="date", 
                    y="value",
                    colorscale="viridis",
                    gap=1,
                    years_title=True,
                    month_lines_width=2
                )
                
                fig.update_layout(
                    title="Calendar Heatmap - Consommation Énergétique Journalière",
                    height=600
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Afficher quelques statistiques
                st.markdown("### Statistiques du Calendar Heatmap")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Jours analysés", len(daily_data))
                
                with col2:
                    st.metric("Moyenne (kWh/jour)", f"{daily_data['value'].mean():.1f}")
                
                with col3:
                    st.metric("Maximum (kWh/jour)", f"{daily_data['value'].max():.1f}")
                
                with col4:
                    st.metric("Minimum (kWh/jour)", f"{daily_data['value'].min():.1f}")
                
            except ImportError:
                st.warning("Pour utiliser le calendar heatmap interactif, installez plotly-calplot: `pip install plotly-calplot`")
                
                # Fallback avec Plotly natif
                daily_data = filtered_df.resample('D').sum()['Energie_periode_kWh'].reset_index()
                daily_data = daily_data[daily_data['Energie_periode_kWh'] > 0]
                
                # Utiliser la première colonne comme date
                date_col = daily_data.columns[0]
                
                fig = px.scatter(
                    daily_data, 
                    x=date_col, 
                    y='Energie_periode_kWh',
                    color='Energie_periode_kWh',
                    title="Consommation Journalière (Vue Temporelle)",
                    color_continuous_scale='viridis',
                    size='Energie_periode_kWh',
                    hover_data={date_col: '|%B %d, %Y'}
                )
                
                fig.update_layout(height=500, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                
                # Statistiques
                st.markdown("### Statistiques")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Jours analysés", len(daily_data))
                
                with col2:
                    st.metric("Moyenne (kWh/jour)", f"{daily_data['Energie_periode_kWh'].mean():.1f}")
                
                with col3:
                    st.metric("Maximum (kWh/jour)", f"{daily_data['Energie_periode_kWh'].max():.1f}")
                
                with col4:
                    st.metric("Minimum (kWh/jour)", f"{daily_data['Energie_periode_kWh'].min():.1f}")
                
        except Exception as e:
            st.error(f"Erreur lors de la création du calendar heatmap: {str(e)}")

    elif st.session_state.page == "boxplots":
        st.markdown("""
        <div style="background: linear-gradient(90deg, #9467bd, #8c564b); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
            <h2 style="color: white; margin: 0;">Distribution par Jour de la Semaine</h2>
        </div>
        """, unsafe_allow_html=True)
        
        days_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        daily_consumption_df = filtered_df.resample('D').sum()
        
        english_to_french = {
            "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
            "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi",
            "Sunday": "Dimanche"
        }
        
        daily_consumption_df['Jour_Semaine_EN'] = daily_consumption_df.index.day_name()
        daily_consumption_df['JourSemaine'] = daily_consumption_df['Jour_Semaine_EN'].map(english_to_french)
        daily_consumption_df.drop(columns=['Jour_Semaine_EN'], inplace=True)
        
        # Filtrer données avec énergie > 0
        daily_consumption_df = daily_consumption_df[daily_consumption_df['Energie_periode_kWh'] > 0]
        
        # Nettoyage des outliers
        cleaned_data = []
        for day in days_order:
            day_data = daily_consumption_df[daily_consumption_df['JourSemaine'] == day]
            median_value = day_data['Energie_periode_kWh'].median()
            if pd.notna(median_value):
                threshold = 5 * median_value
                cleaned_day_data = day_data[day_data['Energie_periode_kWh'] <= threshold]
                cleaned_data.append(cleaned_day_data)
        
        if cleaned_data:
            daily_consumption_df = pd.concat(cleaned_data)
        
        fig = px.box(daily_consumption_df,
                     x='JourSemaine',
                     y='Energie_periode_kWh',
                     color='JourSemaine',
                     category_orders={"JourSemaine": days_order},
                     title="Distribution de la Consommation d'Énergie par Jour de la Semaine (sans outliers)")
        
        fig.update_layout(
            xaxis_title='Jour de la Semaine',
            yaxis_title='Énergie (kWh)',
            showlegend=False,
            height=500,
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistiques résumées
        st.markdown("### Statistiques par Jour")
        stats_summary = daily_consumption_df.groupby('JourSemaine')['Energie_periode_kWh'].agg([
            'count', 'mean', 'median', 'std', 'min', 'max'
        ]).round(2)
        
        # Reordenar según el orden de los días
        try:
            stats_summary = stats_summary.reindex(days_order)
        except:
            pass
            
        st.dataframe(stats_summary, use_container_width=True)

    # Footer avec informations
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"**Bâtiment:** {selected_display_name}")
    
    with col2:
        st.info(f"**Période:** {start_date} - {end_date}")
    
    with col3:
        st.info(f"**Points de données:** {len(filtered_df):,}")

if __name__ == "__main__":
    run()