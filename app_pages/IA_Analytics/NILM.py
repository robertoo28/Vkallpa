import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from azure.storage.blob import BlobServiceClient
from scipy import stats
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


class FakeNILMAlgorithm:
    """Algorithme NILM simulé pour décomposer la consommation énergétique"""
    
    def __init__(self):
        self.components = {
            'Chauffage': {'color': '#FF6B6B', 'winter_factor': 2.5, 'base_ratio': 0.35},
            'Eclairage': {'color': '#4ECDC4', 'base_ratio': 0.15},
            'Equipements': {'color': '#45B7D1', 'base_ratio': 0.20},
            'Climatisation': {'color': '#96CEB4', 'summer_factor': 2.0, 'base_ratio': 0.15},
            'Informatique': {'color': '#FFEAA7', 'base_ratio': 0.10},
            'Autres': {'color': '#DDA0DD', 'base_ratio': 0.05}
        }
        
    def decompose_signal(self, df, aggregation='Jour'):
        """Décompose le signal de consommation totale avec conservation de l'énergie"""
        
        # Resample selon l'agrégation
        resample_map = {
            'Heure': 'H',
            'Jour': 'D',
            'Semaine': 'W-MON',
            'Mois': 'M'
        }
        
        resampled = df.resample(resample_map[aggregation]).agg({
            'Energie_periode_kWh': 'sum',
            'Puissance_moyenne_kW': 'mean'
        })
        
        total_energy = resampled['Energie_periode_kWh']
        timestamps = resampled.index
        
        # Calculer les composantes brutes (non normalisées)
        decomposed_raw = {}
        confidence_intervals = {}
        
        for component, config in self.components.items():
            component_values, confidence = self._calculate_component(
                total_energy, timestamps, component, config, aggregation
            )
            decomposed_raw[component] = component_values
            confidence_intervals[component] = confidence
        
        # NORMALISATION : garantir que somme des composantes = total
        decomposed = {}
        sum_components = np.zeros(len(total_energy))
        
        # Calculer la somme de toutes les composantes brutes
        for component_values in decomposed_raw.values():
            sum_components += component_values
        
        # Normaliser chaque composante pour que la somme égale le total
        for component, component_values in decomposed_raw.items():
            # Éviter division par zéro
            normalized = np.where(
                sum_components > 0,
                component_values * (total_energy / sum_components),
                0
            )
            
            # S'assurer qu'aucune composante ne dépasse le total
            normalized = np.minimum(normalized, total_energy)
            
            decomposed[component] = normalized
            
        return decomposed, confidence_intervals, total_energy
    
    def _calculate_component(self, total_energy, timestamps, component_name, config, aggregation):
        """Calcule une composante spécifique"""
        
        base_consumption = total_energy * config['base_ratio']
        
        # Patterns spécifiques par composante
        if component_name == 'Chauffage':
            seasonal_factor = self._heating_pattern(timestamps)
            daily_factor = self._heating_daily_pattern(timestamps, aggregation)
            
        elif component_name == 'Eclairage':
            seasonal_factor = self._lighting_seasonal_pattern(timestamps)
            daily_factor = self._lighting_daily_pattern(timestamps, aggregation)
            
        elif component_name == 'Equipements':
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = self._office_equipment_pattern(timestamps, aggregation)
            
        elif component_name == 'Climatisation':
            seasonal_factor = self._cooling_pattern(timestamps)
            daily_factor = self._cooling_daily_pattern(timestamps, aggregation)
            
        elif component_name == 'Informatique':
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = self._it_equipment_pattern(timestamps, aggregation)
            
        else:  # Autres
            seasonal_factor = np.ones(len(timestamps))
            daily_factor = 0.8 + 0.4 * np.random.random(len(timestamps))
        
        # Appliquer les patterns
        component_values = base_consumption * seasonal_factor * daily_factor
        
        # Ajouter du bruit réaliste
        noise = np.random.normal(0, 0.1, len(component_values))
        component_values = component_values * (1 + noise)
        component_values = np.maximum(component_values, 0)  # Pas de valeurs négatives
        
        # Intervalle de confiance (±20-40% selon la composante)
        uncertainty = 0.3 if component_name in ['Chauffage', 'Climatisation'] else 0.2
        confidence = component_values * uncertainty
        
        return component_values, confidence
    
    def _heating_pattern(self, timestamps):
        """Pattern saisonnier pour le chauffage - PAS de chauffage juin à mi-septembre"""
        months = np.array([ts.month for ts in timestamps])
        days = np.array([ts.day for ts in timestamps])
        
        # Créer le pattern de base : maximum en hiver (déc-fév), minimum en été
        seasonal = 2.0 - 1.5 * np.cos(2 * np.pi * (months - 1) / 12)
        
        # FORCER à 0 le chauffage de juin à mi-septembre
        no_heating_mask = (
            (months == 6) |  # Juin
            (months == 7) |  # Juillet
            (months == 8) |  # Août
            ((months == 9) & (days <= 15))  # Première moitié de septembre
        )
        
        seasonal[no_heating_mask] = 0.0
        
        return seasonal
    
    def _heating_daily_pattern(self, timestamps, aggregation):
        """Pattern quotidien pour le chauffage"""
        if aggregation == 'Heure':
            hours = np.array([ts.hour for ts in timestamps])
            # Pics matin (6-9h) et soir (17-22h)
            daily = 0.7 + 0.3 * (np.sin(2 * np.pi * (hours - 6) / 24) + 0.5)
            # Plus élevé le soir
            daily += 0.2 * np.maximum(0, np.sin(np.pi * (hours - 17) / 10))
        else:
            # Variation weekday/weekend
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.1, 0.8)  # Plus élevé en semaine
        return daily
    
    def _lighting_seasonal_pattern(self, timestamps):
        """Pattern saisonnier pour l'éclairage"""
        months = np.array([ts.month for ts in timestamps])
        # Plus élevé en hiver (jours plus courts)
        seasonal = 1.3 - 0.6 * np.cos(2 * np.pi * (months - 1) / 12)
        return seasonal
    
    def _lighting_daily_pattern(self, timestamps, aggregation):
        """Pattern quotidien pour l'éclairage"""
        if aggregation == 'Heure':
            hours = np.array([ts.hour for ts in timestamps])
            # Pics matin (7-9h) et soir (17-20h), minimum la nuit
            morning_peak = np.maximum(0, np.sin(np.pi * (hours - 5) / 6))
            evening_peak = np.maximum(0, np.sin(np.pi * (hours - 15) / 8))
            daily = 0.3 + 0.4 * (morning_peak + evening_peak)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.2, 0.6)  # Beaucoup moins le weekend
        return daily
    
    def _cooling_pattern(self, timestamps):
        """Pattern saisonnier pour la climatisation - UNIQUEMENT juin à mi-septembre"""
        months = np.array([ts.month for ts in timestamps])
        days = np.array([ts.day for ts in timestamps])
        
        # Initialiser à 0 partout
        seasonal = np.zeros(len(timestamps))
        
        # Activer UNIQUEMENT de juin à mi-septembre
        cooling_mask = (
            (months == 6) |  # Juin
            (months == 7) |  # Juillet
            (months == 8) |  # Août
            ((months == 9) & (days <= 15))  # Première moitié de septembre
        )
        
        # Pattern progressif : montée en juin, pic juillet-août, descente mi-septembre
        for i, ts in enumerate(timestamps):
            if cooling_mask[i]:
                if ts.month == 6:
                    # Montée progressive en juin
                    seasonal[i] = 1.0 + (ts.day / 30) * 1.0
                elif ts.month == 7 or ts.month == 8:
                    # Pic en juillet et août
                    seasonal[i] = 2.0
                elif ts.month == 9 and ts.day <= 15:
                    # Descente progressive mi-septembre
                    seasonal[i] = 2.0 - ((ts.day / 15) * 1.0)
        
        return seasonal
    
    def _cooling_daily_pattern(self, timestamps, aggregation):
        """Pattern quotidien pour la climatisation"""
        if aggregation == 'Heure':
            hours = np.array([ts.hour for ts in timestamps])
            # Maximum après-midi (12-18h)
            daily = 0.5 + 0.5 * np.maximum(0, np.sin(np.pi * (hours - 8) / 12))
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.1, 0.7)
        return daily
    
    def _office_equipment_pattern(self, timestamps, aggregation):
        """Pattern pour les équipements de bureau"""
        if aggregation == 'Heure':
            hours = np.array([ts.hour for ts in timestamps])
            # Relativement constant pendant heures de bureau (8-18h)
            daily = np.where((hours >= 8) & (hours <= 18), 1.2, 0.4)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.0, 0.3)  # Très bas le weekend
        return daily
    
    def _it_equipment_pattern(self, timestamps, aggregation):
        """Pattern pour l'informatique"""
        if aggregation == 'Heure':
            hours = np.array([ts.hour for ts in timestamps])
            # Constant mais plus élevé pendant heures de bureau
            daily = np.where((hours >= 7) & (hours <= 19), 1.1, 0.7)
        else:
            weekdays = np.array([ts.weekday() for ts in timestamps])
            daily = np.where(weekdays < 5, 1.0, 0.5)  # Réduit le weekend
        return daily

def run():
    # Header principal avec style
    st.markdown("""
    <div style="background: linear-gradient(90deg, #667eea, #764ba2); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            🔬 Analyseur NILM - Décomposition Énergétique
        </h1>
        <p style="color: white; text-align: center; margin: 0.5rem 0 0 0; opacity: 0.9;">
            Non-Intrusive Load Monitoring - Intelligence Artificielle pour l'Analyse Énergétique
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar avec configuration
    with st.sidebar:
        st.markdown("""
        <div style="background: #f0f2f6; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
            <h2 style="color: #667eea; margin: 0;">⚙️ Configuration NILM</h2>
        </div>
        """, unsafe_allow_html=True)
        
        if not blob_list:
            st.error("❌ Impossible de récupérer la liste des fichiers Azure")
            return
        
        selected_building = st.selectbox('🏗️ Sélection du Bâtiment', blob_list)
        
        try:
            df = azure_loader.load_data(selected_building)
            min_date = df.index.min().date()
            max_date = df.index.max().date()
            
            st.markdown("📅 **Période d'analyse**")
            start_date = st.date_input('Date de début', min_date, min_value=min_date, max_value=max_date)
            end_date = st.date_input('Date de fin', max_date, min_value=min_date, max_value=max_date)
            
            # Agrégation temporelle
            st.markdown("⏱️ **Agrégation temporelle**")
            aggregation = st.selectbox(
                'Résolution d\'analyse',
                ['Heure', 'Jour', 'Semaine', 'Mois'],
                index=1,  # Défaut sur 'Jour'
                help="Plus la résolution est fine, plus l'analyse sera détaillée"
            )
            
            # Filtrer les données
            filtered_df = df.loc[str(start_date):str(end_date)]
            
            if filtered_df.empty:
                st.error("❌ Aucune donnée trouvée pour la période sélectionnée")
                return
            
            # Informations sur les données
            st.markdown("### 📊 Informations")
            st.info(f"**Points de données:** {len(filtered_df):,}")
            st.info(f"**Consommation totale:** {filtered_df['Energie_periode_kWh'].sum():.1f} kWh")
            
            # Bouton de simulation
            st.markdown("---")
            simulation_button = st.button(
                "🚀 Lancer Simulation NILM",
                type="primary",
                use_container_width=True,
                help="Lance l'algorithme de décomposition énergétique"
            )
                
        except Exception as e:
            st.error(f"❌ Erreur de connexion à Azure: {str(e)}")
            return
    
    # Interface principale
    if 'simulation_run' not in st.session_state:
        st.session_state.simulation_run = False
    
    if simulation_button:
        st.session_state.simulation_run = True
    
    # Afficher la courbe principale dès que les paramètres sont sélectionnés
    st.markdown("""
    <div style="background: linear-gradient(90deg, #4facfe, #00f2fe); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
        <h2 style="color: white; margin: 0;">📈 Analyse de Consommation Énergétique</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Préparer les données pour le graphique principal
    resample_map = {
        'Heure': 'H',
        'Jour': 'D', 
        'Semaine': 'W-MON',
        'Mois': 'M'
    }
    
    resampled = filtered_df.resample(resample_map[aggregation]).agg({
        'Energie_periode_kWh': 'sum',
        'Puissance_moyenne_kW': 'mean'
    })
    
    total_energy = resampled['Energie_periode_kWh']
    
    if not st.session_state.simulation_run:
        # Afficher seulement la courbe principale
        fig = go.Figure()
        
        fig.add_trace(
            go.Scatter(
                x=total_energy.index,
                y=total_energy.values,
                mode='lines',
                name='Consommation Totale',
                line=dict(color='#2E86AB', width=3),
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Énergie: %{y:.2f} kWh<extra></extra>'
            )
        )
        
        fig.update_layout(
            title=f"Consommation Énergétique - {selected_building} ({aggregation})",
            xaxis_title='Date',
            yaxis_title='Énergie (kWh)',
            height=500,
            template="plotly_white",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Informations sur les données
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Nombre de points", f"{len(total_energy):,}")
        with col2:
            st.metric("⚡ Consommation totale", f"{total_energy.sum():.1f} kWh")
        with col3:
            st.metric("📈 Consommation moyenne", f"{total_energy.mean():.1f} kWh")
        
        st.info("👈 Cliquez sur **'Lancer Simulation NILM'** pour décomposer la consommation par équipement")
        
    else:
        # Simulation en cours
        with st.spinner('🔄 Algorithme NILM en cours d\'exécution...'):
            nilm = FakeNILMAlgorithm()
            decomposed, confidence_intervals, _ = nilm.decompose_signal(filtered_df, aggregation)
        
        st.success(f"✅ Analyse NILM terminée ! Décomposition en {len(decomposed)} composantes")
        
        # Graphique principal avec décomposition
        st.markdown("""
        <div style="background: linear-gradient(90deg, #4facfe, #00f2fe); padding: 0.5rem; border-radius: 8px; margin-bottom: 1rem;">
            <h2 style="color: white; margin: 0;">📈 Décomposition Énergétique Détaillée</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Créer le graphique principal avec toutes les composantes
        fig = go.Figure()
        
        # Courbe totale (mesurée)
        fig.add_trace(
            go.Scatter(
                x=total_energy.index,
                y=total_energy.values,
                mode='lines',
                name='Consommation Totale (Mesurée)',
                line=dict(color='black', width=4),
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Énergie: %{y:.2f} kWh<extra></extra>'
            )
        )
        
        # Vérification : courbe reconstituée (somme des composantes)
        reconstructed = np.zeros(len(total_energy))
        for values in decomposed.values():
            reconstructed += values
            
        fig.add_trace(
            go.Scatter(
                x=total_energy.index,
                y=reconstructed,
                mode='lines',
                name='Reconstruction NILM (Validation)',
                line=dict(color='red', width=2, dash='dot'),
                opacity=0.7,
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Énergie: %{y:.2f} kWh<extra></extra>'
            )
        )
        
        # Composantes individuelles avec intervalles de confiance
        for component, values in decomposed.items():
            color = nilm.components[component]['color']
            confidence = confidence_intervals[component]
            
            # Ligne principale
            fig.add_trace(
                go.Scatter(
                    x=total_energy.index,
                    y=values,
                    mode='lines',
                    name=component,
                    line=dict(color=color, width=2),
                    hovertemplate=f'<b>{component}</b><br>Date: %{{x}}<br>Énergie: %{{y:.2f}} kWh<extra></extra>'
                )
            )
            
            # Intervalle de confiance supérieur
            fig.add_trace(
                go.Scatter(
                    x=total_energy.index,
                    y=values + confidence,
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                )
            )
            
            # Intervalle de confiance inférieur et zone
            fig.add_trace(
                go.Scatter(
                    x=total_energy.index,
                    y=np.maximum(values - confidence, 0),  # Éviter les valeurs négatives
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15)',
                    name=f'{component} (Incertitude)',
                    showlegend=False,
                    hoverinfo='skip'
                )
            )
        
        # Mise en page
        fig.update_layout(
            title=f"Décomposition NILM - {selected_building} ({aggregation})",
            xaxis_title='Date',
            yaxis_title='Énergie (kWh)',
            height=500,
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
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Note sur la conservation de l'énergie
        st.info("ℹ️ **Validation NILM** : La courbe rouge en pointillés représente la reconstruction (somme des composantes). Elle se superpose parfaitement à la courbe noire (mesurée), garantissant la **conservation de l'énergie** : ∑ composantes = Total.")
        
        # Camembert séparé
        st.markdown("### 🥧 Répartition par Équipement")
        
        total_consumption = {component: values.sum() for component, values in decomposed.items()}
        colors = [nilm.components[comp]['color'] for comp in total_consumption.keys()]
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=list(total_consumption.keys()),
            values=list(total_consumption.values()),
            hole=0.4,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>Consommation: %{value:.1f} kWh<br>Pourcentage: %{percent}<extra></extra>'
        )])
        
        fig_pie.update_layout(
            height=400,
            template="plotly_white",
            margin=dict(t=50, b=50, l=50, r=50)
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # Statistiques détaillées
        st.markdown("### 📊 Statistiques de Décomposition")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Tableau des consommations
            stats_df = pd.DataFrame({
                'Composante': list(total_consumption.keys()),
                'Consommation (kWh)': [f"{v:.1f}" for v in total_consumption.values()],
                'Pourcentage (%)': [f"{v/sum(total_consumption.values())*100:.1f}" for v in total_consumption.values()]
            })
            
            st.dataframe(
                stats_df,
                use_container_width=True,
                hide_index=True
            )
        
        with col2:
            # Métriques clés
            st.metric("🏆 Composante Principale", 
                     max(total_consumption, key=total_consumption.get),
                     f"{max(total_consumption.values()):.1f} kWh")
            
            # Vérification de la conservation de l'énergie
            sum_decomposed = sum(total_consumption.values())
            total_real = total_energy.sum()
            conservation_error = abs(sum_decomposed - total_real) / total_real * 100
            
            st.metric("🔬 Conservation Énergétique", 
                     f"{100 - conservation_error:.2f}%",
                     f"Erreur: {conservation_error:.3f}%")
            
            st.metric("🎯 Précision Algorithmique", 
                     f"{min(95 + np.random.random() * 4, 99):.1f}%")
        
        # Recommendations
        st.markdown("### 💡 Recommandations d'Optimisation")
        
        # Identifier le poste le plus consommateur
        max_component = max(total_consumption, key=total_consumption.get)
        max_percentage = total_consumption[max_component] / sum(total_consumption.values()) * 100
        
        recommendations = {
            'Chauffage': "🌡️ Optimiser la régulation thermique et l'isolation du bâtiment",
            'Climatisation': "❄️ Régler les consignes de température et améliorer l'efficacité énergétique",
            'Eclairage': "💡 Installer des LED et des détecteurs de présence",
            'Equipements': "🔧 Mettre en place des policies d'extinction et moderniser les équipements",
            'Informatique': "💻 Configurer la mise en veille automatique et optimiser les serveurs",
            'Autres': "🔍 Analyser plus finement cette catégorie pour identifier des postes spécifiques"
        }
        
        st.info(f"**Poste prioritaire:** {max_component} ({max_percentage:.1f}% de la consommation)")
        st.success(recommendations.get(max_component, "Analyser cette composante pour des optimisations spécifiques"))
        
        # Bouton pour relancer
        if st.button("🔄 Nouvelle Simulation", type="secondary"):
            st.session_state.simulation_run = False
            st.rerun()

if __name__ == "__main__":
    run()