import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from azure.storage.blob import BlobServiceClient
import io
from scipy import interpolate
from core.config import get_config

# Configuration Azure
config = get_config()
CONNECTION_STRING = config['azure']['connection_string']
CONTAINER_NAME = config['azure']['container_name']


@st.cache_resource
def init_azure_client():
    """Initialise le client Azure Blob Storage"""
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)

def get_blob_list():
    """Récupère la liste des fichiers dans Azure Blob Storage"""
    try:
        blob_service_client = init_azure_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # Filtrer uniquement les fichiers Excel et CSV
        blob_list = []
        for blob in container_client.list_blobs():
            if blob.name.lower().endswith(('.xlsx', '.xls', '.csv')):
                blob_list.append(blob.name)
        
        return sorted(blob_list)
    except Exception as e:
        st.error(f"Erreur lors de la récupération des fichiers : {str(e)}")
        return []

@st.cache_data
def load_blob_data(blob_name):
    """Charge les données depuis Azure Blob Storage"""
    try:
        blob_service_client = init_azure_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_client = container_client.get_blob_client(blob_name)
        
        blob_data = blob_client.download_blob().readall()
        
        # Charger selon le type de fichier
        if blob_name.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(blob_data))
        else:  # Excel
            df = pd.read_excel(io.BytesIO(blob_data), sheet_name='Donnees_Detaillees')
        
        # Identifier la colonne de date
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'horodate' in col.lower() or 'timestamp' in col.lower() or 'jour' in col.lower()]
        
        if date_columns:
            df['Date'] = pd.to_datetime(df[date_columns[0]])
        elif 'Date' not in df.columns:
            # Si pas de colonne date trouvée, utiliser l'index
            if df.index.name and 'date' in str(df.index.name).lower():
                df['Date'] = pd.to_datetime(df.index)
                df.reset_index(drop=True, inplace=True)
            else:
                st.warning("Aucune colonne de date détectée. Utilisation d'un index temporel générique.")
                df['Date'] = pd.date_range(start='2023-01-01', periods=len(df), freq='5min')
        
        df = df.sort_values('Date')
        return df
    
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier : {str(e)}")
        return None

def detect_gaps(series, threshold=10):
    """
    Détecte les trous de données (séquences de plus de 'threshold' zéros consécutifs)
    Retourne un masque booléen et des statistiques
    """
    # Identifier les zéros
    is_zero = (series == 0) | series.isna()
    
    # Identifier les groupes de zéros consécutifs
    gaps = []
    gap_starts = []
    gap_ends = []
    
    in_gap = False
    gap_start = 0
    gap_length = 0
    
    for i, val in enumerate(is_zero):
        if val:  # C'est un zéro
            if not in_gap:
                in_gap = True
                gap_start = i
                gap_length = 1
            else:
                gap_length += 1
        else:  # Pas un zéro
            if in_gap:
                # Fin d'un trou
                if gap_length > threshold:
                    gaps.append(gap_length)
                    gap_starts.append(gap_start)
                    gap_ends.append(i - 1)
                in_gap = False
                gap_length = 0
    
    # Vérifier si on termine dans un trou
    if in_gap and gap_length > threshold:
        gaps.append(gap_length)
        gap_starts.append(gap_start)
        gap_ends.append(len(series) - 1)
    
    # Créer un masque pour tous les trous significatifs
    gap_mask = np.zeros(len(series), dtype=bool)
    for start, end in zip(gap_starts, gap_ends):
        gap_mask[start:end+1] = True
    
    stats = {
        'n_gaps': len(gaps),
        'total_missing': sum(gaps),
        'pct_missing': (sum(gaps) / len(series)) * 100,
        'gap_lengths': gaps,
        'gap_starts': gap_starts,
        'gap_ends': gap_ends,
        'gap_mask': gap_mask
    }
    
    return stats

def reconstruct_data(series, gap_mask, method='interpolation'):
    """
    Reconstruit les données manquantes
    Methods: 'interpolation', 'forward_fill', 'backward_fill', 'mean'
    """
    series_reconstructed = series.copy()
    
    if method == 'interpolation':
        # Interpolation linéaire pour les trous
        series_reconstructed = series_reconstructed.replace(0, np.nan)
        series_reconstructed = series_reconstructed.interpolate(method='linear', limit_direction='both')
        
    elif method == 'forward_fill':
        series_reconstructed = series_reconstructed.replace(0, np.nan)
        series_reconstructed = series_reconstructed.fillna(method='ffill')
        
    elif method == 'backward_fill':
        series_reconstructed = series_reconstructed.replace(0, np.nan)
        series_reconstructed = series_reconstructed.fillna(method='bfill')
        
    elif method == 'mean':
        # Remplacer par la moyenne des valeurs non-nulles
        mean_val = series[~gap_mask].mean()
        series_reconstructed[gap_mask] = mean_val
    
    # S'assurer que les valeurs reconstruites sont positives
    series_reconstructed = series_reconstructed.clip(lower=0)
    
    return series_reconstructed

def run():
    # Header
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f77b4, #ff7f0e); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; text-align: center; margin: 0;">
            🔧 Détection et Reconstruction de Données Manquantes
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Info box explicative
    st.markdown("""
    <div style="background-color: #e3f2fd; padding: 1rem; border-radius: 8px; border-left: 4px solid #2196F3; margin-bottom: 1rem;">
        <p style="margin: 0; color: #1565C0;">
            <strong>💡 À quoi ça sert ?</strong><br>
            Cet outil détecte automatiquement les <strong>trous dans vos données de consommation</strong> (séquences de zéros ou valeurs manquantes) 
            et les <strong>reconstruit intelligemment</strong> grâce à nos algorithmes. Obtenez une vision complète de votre profil énergétique, 
            même avec des données incomplètes !
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")
    
    # Liste des fichiers disponibles
    blob_list = get_blob_list()
    
    if not blob_list:
        st.error("❌ Impossible de récupérer la liste des fichiers depuis Azure")
        st.info("Vérifiez votre connexion et les paramètres Azure")
        return
    
    # Créer un mapping nom affiché -> nom réel
    display_map = {}
    display_names = []
    
    for blob_name in blob_list:
        # Enlever l'extension pour l'affichage
        display_name = blob_name.rsplit('.', 1)[0] if '.' in blob_name else blob_name
        display_map[display_name] = blob_name
        display_names.append(display_name)
    
    # Sélection du fichier
    selected_display = st.sidebar.selectbox(
        '📁 Sélection du fichier',
        display_names,
        help="Choisissez le fichier de données à analyser"
    )
    
    selected_blob = display_map[selected_display]
    
    # Charger les données
    with st.spinner("Chargement des données..."):
        df = load_blob_data(selected_blob)
    
    if df is None:
        st.error("❌ Impossible de charger les données")
        return
    
    # Afficher les informations sur le fichier
    st.sidebar.markdown("### 📊 Informations")
    st.sidebar.info(f"📄 **Fichier:** {selected_display}")
    st.sidebar.info(f"📅 **Période:** {df['Date'].min().date()} → {df['Date'].max().date()}")
    st.sidebar.info(f"📏 **Nombre de points:** {len(df):,}")
    
    # Identifier les colonnes numériques (consommation)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Filtrer pour ne garder que les colonnes pertinentes
    relevant_cols = [col for col in numeric_cols if any(keyword in col.lower() 
                     for keyword in ['energie', 'kwh', 'puissance', 'kw', 'consommation', 'valeur'])]
    
    if not relevant_cols:
        relevant_cols = numeric_cols[:5]  # Prendre les 5 premières colonnes numériques
    
    # Sélection de la colonne à analyser
    st.markdown("""
    <div style="background: linear-gradient(90deg, #ff7f0e, #2ca02c); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">📊 Configuration de l'Analyse</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_column = st.selectbox(
            '📈 Colonne à analyser',
            relevant_cols,
            help="Sélectionnez la colonne contenant les données de consommation"
        )
    
    with col2:
        gap_threshold = st.slider(
            '🔍 Seuil de détection (zéros consécutifs)',
            min_value=5,
            max_value=50,
            value=10,
            help="Nombre minimum de zéros consécutifs pour considérer qu'il y a un trou"
        )
    
    # Détecter les trous
    series = df[selected_column].copy()
    gap_stats = detect_gaps(series, threshold=gap_threshold)
    
    # Afficher les statistiques de détection
    st.markdown("""
    <div style="background: linear-gradient(90deg, #2ca02c, #17becf); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">🔍 Résultats de la Détection</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Trous détectés", gap_stats['n_gaps'])
    
    with col2:
        st.metric("Points manquants", f"{gap_stats['total_missing']:,}")
    
    with col3:
        st.metric("% de données manquantes", f"{gap_stats['pct_missing']:.2f}%")
    
    if gap_stats['n_gaps'] == 0:
        st.success("✅ Aucun trou significatif détecté dans les données !")
        st.info("Vos données sont complètes et de bonne qualité. Vous pouvez réduire le seuil de détection si vous souhaitez identifier des trous plus petits.")
        
        # Afficher quand même le graphique des données
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=series,
            name="Données complètes",
            mode='lines',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.update_layout(
            title=f"Données de {selected_column}",
            xaxis_title="Date",
            yaxis_title=selected_column,
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        return
    
    # Afficher les détails des trous
    with st.expander(f"📋 Détail des {gap_stats['n_gaps']} trous détectés"):
        gaps_df = pd.DataFrame({
            'N°': range(1, len(gap_stats['gap_lengths']) + 1),
            'Date début': [df['Date'].iloc[start].strftime('%Y-%m-%d %H:%M') for start in gap_stats['gap_starts']],
            'Date fin': [df['Date'].iloc[end].strftime('%Y-%m-%d %H:%M') for end in gap_stats['gap_ends']],
            'Durée (points)': gap_stats['gap_lengths'],
            'Durée (heures)': [length * 5 / 60 for length in gap_stats['gap_lengths']]  # Supposant un pas de 5 min
        })
        st.dataframe(gaps_df, use_container_width=True, hide_index=True)
    
    # Options de reconstruction
    st.markdown("""
    <div style="background: linear-gradient(90deg, #9467bd, #8c564b); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
        <h2 style="color: white; margin: 0;">🔧 Reconstruction des Données</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        reconstruction_method = st.selectbox(
            '🎯 Méthode de reconstruction',
            ['interpolation', 'forward_fill', 'backward_fill', 'mean'],
            format_func=lambda x: {
                'interpolation': '📈 Interpolation linéaire (recommandé)',
                'forward_fill': '⏩ Propagation avant',
                'backward_fill': '⏪ Propagation arrière',
                'mean': '📊 Moyenne des valeurs'
            }[x],
            help="Choisissez la méthode pour reconstruire les données manquantes"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Lancer la Reconstruction", type="primary"):
            st.session_state.reconstruction_done = True
    
    # Afficher les résultats si la reconstruction est lancée
    if st.session_state.get('reconstruction_done', False):
        with st.spinner("Reconstruction en cours..."):
            reconstructed_series = reconstruct_data(series, gap_stats['gap_mask'], method=reconstruction_method)
        
        st.success("✅ Reconstruction terminée avec succès !")
        
        # Graphique comparatif
        st.markdown("""
        <div style="background: linear-gradient(90deg, #17becf, #1f77b4); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
            <h2 style="color: white; margin: 0;">📈 Visualisation Avant / Après</h2>
        </div>
        """, unsafe_allow_html=True)
        
        fig = go.Figure()
        
        # Données originales (sans les trous)
        original_without_gaps = series.copy()
        original_without_gaps[gap_stats['gap_mask']] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=original_without_gaps,
            name="Données originales",
            mode='lines',
            line=dict(color='#1f77b4', width=2),
            legendgroup='original'
        ))
        
        # Zones de trous (en rouge)
        gaps_only = series.copy()
        gaps_only[~gap_stats['gap_mask']] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=gaps_only,
            name="Données manquantes",
            mode='markers',
            marker=dict(color='#d62728', size=4),
            legendgroup='gaps'
        ))
        
        # Données reconstruites (en vert, uniquement dans les trous)
        reconstructed_gaps_only = reconstructed_series.copy()
        reconstructed_gaps_only[~gap_stats['gap_mask']] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=reconstructed_gaps_only,
            name="Données reconstruites",
            mode='lines',
            line=dict(color='#2ca02c', width=2),
            legendgroup='reconstructed'
        ))
        
        fig.update_layout(
            title=f"Reconstruction de {selected_column} - Méthode: {reconstruction_method}",
            xaxis_title="Date",
            yaxis_title=selected_column,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            height=600
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métriques de qualité
        st.markdown("""
        <div style="background: linear-gradient(90deg, #d62728, #e377c2); padding: 0.5rem; border-radius: 8px; margin: 1rem 0;">
            <h3 style="color: white; margin: 0;">📊 Qualité de la Reconstruction</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Statistiques sur les données reconstruites
        reconstructed_mean = reconstructed_series[gap_stats['gap_mask']].mean()
        original_mean = series[~gap_stats['gap_mask']].mean()
        
        with col1:
            st.metric("Valeur moyenne (original)", f"{original_mean:.2f}")
        
        with col2:
            st.metric("Valeur moyenne (reconstruit)", f"{reconstructed_mean:.2f}")
        
        with col3:
            deviation = ((reconstructed_mean - original_mean) / original_mean * 100) if original_mean > 0 else 0
            st.metric("Écart moyen", f"{deviation:.1f}%")
        
        with col4:
            st.metric("Points reconstruits", f"{gap_stats['total_missing']:,}")
        
        # Interprétation
        st.markdown("""
        **💡 Interprétation :**
        
        - **Bleu** : Vos données originales mesurées
        - **Rouge** : Les trous détectés (données manquantes ou nulles)
        - **Vert** : Les valeurs reconstruites par notre algorithme
        
        **Qualité de la reconstruction :**
        """)
        
        if abs(deviation) < 5:
            st.success("✅ Excellente reconstruction ! L'écart avec les données originales est inférieur à 5%.")
        elif abs(deviation) < 15:
            st.info("ℹ️ Bonne reconstruction. L'écart reste acceptable pour une analyse énergétique.")
        else:
            st.warning("⚠️ Reconstruction acceptable mais avec un écart notable. Vérifiez la méthode choisie.")
        
        # Option de téléchargement
        st.markdown("---")
        st.markdown("### 💾 Télécharger les résultats")
        
        # Préparer le DataFrame pour export
        export_df = df[['Date']].copy()
        export_df['Donnees_originales'] = series
        export_df['Donnees_reconstruites'] = reconstructed_series
        export_df['Est_reconstruit'] = gap_stats['gap_mask']
        
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger les données reconstruites (CSV)",
            data=csv,
            file_name=f"reconstruction_{selected_display}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        # Réinitialiser pour nouvelle analyse
        if st.button("🔄 Nouvelle analyse"):
            st.session_state.reconstruction_done = False
            st.rerun()

if __name__ == "__main__":
    run()