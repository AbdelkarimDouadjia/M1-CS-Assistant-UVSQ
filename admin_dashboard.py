# ================================================================
# admin_dashboard.py - Interface d'administration du chatbot
# ================================================================
# Ce fichier crée le dashboard admin avec Streamlit.
# Il affiche les statistiques, permet de gérer les fichiers
# de la base de connaissances, et de mettre à jour ChromaDB.
#
# Sections du dashboard :
#   1. 📊 Cartes de statistiques (total, taux succès, sans réponse, aujourd'hui)
#   2. 📚 Knowledge Base (upload, liste, suppression, mise à jour)
#   3. 📈 Graphique tendance des messages
#   4. ⚠️ Questions sans réponse à examiner
#   5. 💬 Interactions récentes
#   6. 📊 Statistiques détaillées (graphique répondu/non répondu)
#   7. 📋 Historique complet avec filtres et export CSV
#
# Lancement : streamlit run admin_dashboard.py
# ================================================================

# --- Imports ---
import streamlit as st        # Framework pour créer l'interface web
import pandas as pd           # Manipulation de données (tableaux, export CSV)
import os                     # Gestion des fichiers (lister, supprimer, taille)
from datetime import datetime, timedelta  # Gestion des dates et heures

# Imports depuis nos propres modules
from ingest_database import (
    DATA_PATH,                # Chemin du dossier data/ ("data")
    clear_and_reingest,       # Fonction : vider ChromaDB + réingérer tous les documents
)
from chat_logger import (
    get_total_messages,       # → Nombre total de questions posées
    get_answered_count,       # → Nombre de questions avec réponse
    get_unanswered_count,     # → Nombre de questions sans réponse
    get_success_rate,         # → Taux de succès en %
    get_unanswered_questions, # → Liste des questions sans réponse
    get_recent_interactions,  # → Dernières interactions
    get_messages_per_day,     # → Messages par jour (pour le graphique)
    get_all_logs,             # → Toutes les interactions (pour l'export)
    get_messages_today,       # → Messages envoyés aujourd'hui
)

# --- Configuration de la page Streamlit ---
st.set_page_config(
    page_title="Saclay AI - Admin Dashboard",  # Titre de l'onglet navigateur
    page_icon="📊",                            # Icône de l'onglet
    layout="wide",                             # Utiliser toute la largeur de l'écran
)

# ================================================================
# STYLE CSS PERSONNALISÉ
# ================================================================
# Ce CSS est injecté dans la page pour personnaliser l'apparence
# des cartes de stats, des badges, des cartes de questions, etc.
# Inspiré de la maquette HTML fournie.
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700;800&display=swap');

    /* Global */
    .block-container { padding-top: 3rem; }
    
    /* Stat cards */
    .stat-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-label {
        color: #64748b;
        font-size: 14px;
        font-weight: 500;
    }
    .stat-value {
        color: #0f172a;
        font-size: 28px;
        font-weight: 700;
        margin-top: 4px;
    }
    .stat-badge-green {
        display: inline-block;
        background: #f0fdf4;
        color: #16a34a;
        font-size: 12px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
    }
    .stat-badge-red {
        display: inline-block;
        background: #fef2f2;
        color: #dc2626;
        font-size: 12px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
    }

    /* Unanswered card */
    .unanswered-card {
        background: #fefce8;
        border-left: 4px solid #facc15;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .unanswered-label {
        color: #854d0e;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .unanswered-question {
        color: #334155;
        font-size: 14px;
        font-style: italic;
    }

    /* Recent interaction */
    .interaction-card {
        padding: 12px 16px;
        border-bottom: 1px solid #f1f5f9;
    }
    .interaction-card:hover {
        background: #f8fafc;
    }
    .interaction-user {
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
    }
    .interaction-time {
        font-size: 11px;
        color: #94a3b8;
    }
    .interaction-question {
        font-size: 13px;
        color: #64748b;
        margin-top: 2px;
    }
    .dot-green {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #22c55e;
        border-radius: 50%;
        margin-right: 6px;
    }
    .dot-yellow {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #eab308;
        border-radius: 50%;
        margin-right: 6px;
    }
    
    /* Header */
    .dashboard-header {
        font-size: 32px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .dashboard-subtitle {
        color: #64748b;
        font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================
# HEADER
# =============================================
# --- En-tête : Titre à gauche, bouton export à droite ---
col_title, col_actions = st.columns([3, 1])  # 3/4 pour le titre, 1/4 pour les actions

with col_title:
    st.markdown('<div class="dashboard-header">📊 University Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Métriques en temps réel du Chatbot IA Paris-Saclay</div>', unsafe_allow_html=True)

with col_actions:
    st.write("")  # Espacement vertical

    # Bouton d'export CSV : télécharge toutes les interactions en fichier CSV
    all_logs = get_all_logs()
    if all_logs:
        # Convertir les résultats SQLite en DataFrame pandas
        df_export = pd.DataFrame([dict(row) for row in all_logs])
        # Convertir le DataFrame en CSV encodé en UTF-8
        csv = df_export.to_csv(index=False).encode("utf-8")
        # Bouton de téléchargement Streamlit
        st.download_button(
            label="📥 Exporter le rapport (CSV)",
            data=csv,
            file_name=f"chat_logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

st.markdown("---")  # Ligne de séparation horizontale

# =============================================
# STATS CARDS
# =============================================
# --- Récupérer toutes les statistiques depuis SQLite ---
total = get_total_messages()       # Nombre total de questions posées
answered = get_answered_count()    # Nombre de questions avec réponse
unanswered = get_unanswered_count()  # Nombre de questions sans réponse
success_rate = get_success_rate()  # Pourcentage de réussite
today = get_messages_today()       # Nombre de messages aujourd'hui

# Créer 4 colonnes égales pour les cartes de statistiques
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
            <div style="padding: 8px; background: rgba(19,91,236,0.1); border-radius: 8px; color: #135bec; font-size: 24px;">💬</div>
        </div>
        <div class="stat-label">Total Messages</div>
        <div class="stat-value">{total:,}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
            <div style="padding: 8px; background: rgba(91,45,106,0.1); border-radius: 8px; color: #5b2d6a; font-size: 24px;">✅</div>
            <span class="stat-badge-green">{success_rate}%</span>
        </div>
        <div class="stat-label">Taux de succès</div>
        <div class="stat-value">{success_rate}%</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
            <div style="padding: 8px; background: rgba(234,179,8,0.1); border-radius: 8px; color: #eab308; font-size: 24px;">⚠️</div>
            <span class="stat-badge-red">{unanswered}</span>
        </div>
        <div class="stat-label">Questions sans réponse</div>
        <div class="stat-value">{unanswered}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-card">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
            <div style="padding: 8px; background: rgba(59,130,246,0.1); border-radius: 8px; color: #3b82f6; font-size: 24px;">📈</div>
        </div>
        <div class="stat-label">Messages aujourd'hui</div>
        <div class="stat-value">{today}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# =============================================
# SECTION 2 : KNOWLEDGE BASE - Gestion des fichiers PDF/TXT
# =============================================
# Cette section permet à l'admin de :
#   - Uploader de nouveaux fichiers PDF/TXT dans le dossier data/
#   - Voir la liste des fichiers existants avec leur taille
#   - Supprimer des fichiers
#   - Relancer la vectorisation (vider ChromaDB + réingérer)
st.markdown("---")
st.subheader("📚 Knowledge Base — Gestion des documents")

# Deux colonnes : upload à gauche, liste des fichiers à droite
col_upload, col_files = st.columns([1, 1])

with col_upload:
    # --- Upload de fichiers ---
    # st.file_uploader crée un bouton drag-and-drop pour uploader des fichiers
    # type=["pdf", "txt"] : accepte uniquement les PDF et TXT
    # accept_multiple_files=True : permet d'uploader plusieurs fichiers en même temps
    st.markdown("##### 📤 Ajouter des fichiers")
    uploaded_files = st.file_uploader(
        "Glissez-déposez vos fichiers ici",
        type=["pdf", "txt"],
        accept_multiple_files=True,
    )

    # Si l'utilisateur a uploadé des fichiers, les sauvegarder dans data/
    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Construire le chemin complet : data/nom_du_fichier.pdf
            file_path = os.path.join(DATA_PATH, uploaded_file.name)

            # Avertir si le fichier existe déjà (il sera écrasé)
            if os.path.exists(file_path):
                st.warning(f"⚠️ **{uploaded_file.name}** existe déjà, il sera remplacé.")

            # Écrire le contenu du fichier uploadé sur le disque
            # "wb" = write binary (les PDF sont des fichiers binaires)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ **{uploaded_file.name}** sauvegardé !")

    st.write("")

    # --- Bouton de mise à jour de ChromaDB ---
    # Quand l'admin clique, on appelle clear_and_reingest() de ingest_database.py
    # qui : 1) vide ChromaDB  2) relit tous les fichiers de data/  3) les vectorise
    st.markdown("##### 🔄 Mettre à jour la base de données")
    st.caption(
        "Cette action vide la base ChromaDB et réingère "
        "tous les fichiers du dossier data/."
    )
    if st.button("🚀 Mettre à jour la base de données", type="primary"):
        with st.spinner("Mise à jour en cours... Veuillez patienter."):
            try:
                nb_chunks = clear_and_reingest()  # Appel à ingest_database.py
                st.success(f"✅ Base mise à jour ! ({nb_chunks} chunks créés)")
            except Exception as e:
                st.error(f"❌ Erreur : {e}")

with col_files:
    # --- Liste des fichiers existants dans data/ ---
    st.markdown("##### 📁 Fichiers dans la base de connaissances")
    if os.path.exists(DATA_PATH):
        # Lister les fichiers, ignorer les fichiers cachés (commençant par .)
        files = [f for f in os.listdir(DATA_PATH) if not f.startswith(".")]
        if files:
            for file_name in files:
                # 3 colonnes : nom du fichier | taille | bouton supprimer
                col_name, col_size, col_del = st.columns([3, 1, 1])
                file_size = os.path.getsize(os.path.join(DATA_PATH, file_name))
                size_kb = file_size / 1024  # Convertir octets → kilooctets
                with col_name:
                    # Icône différente selon le type de fichier
                    icon = "📕" if file_name.endswith(".pdf") else "📄"
                    st.write(f"{icon} **{file_name}")
                with col_size:
                    st.caption(f"{size_kb:.1f} KB")
                with col_del:
                    # Bouton supprimer avec clé unique (key) pour chaque fichier
                    # help= affiche un tooltip au survol
                    if st.button("🗑️", key=f"del_{file_name}", help=f"Supprimer {file_name}"):
                        os.remove(os.path.join(DATA_PATH, file_name))
                        st.success(f"**{file_name}** supprimé !")
                        st.rerun()  # Recharger la page pour mettre à jour la liste
        else:
            st.info("Aucun fichier dans le dossier data/.")
    else:
        st.error("Le dossier data/ n'existe pas.")

st.write("")

# =============================================
# SECTION 3 : GRAPHIQUE + QUESTIONS SANS RÉPONSE
# =============================================
# Layout 2/3 pour le graphique, 1/3 pour les questions à examiner
col_chart, col_review = st.columns([2, 1])

with col_chart:
    st.subheader("📈 Tendance des messages")

    # Menu déroulant pour choisir la période du graphique
    # format_func transforme 7 → "Derniers 7 jours"
    days = st.selectbox("Période", [7, 14, 30], format_func=lambda x: f"Derniers {x} jours")

    # Récupérer les données depuis SQLite (groupées par jour)
    messages_data = get_messages_per_day(days)

    if messages_data:
        # Convertir en DataFrame pandas pour l'affichage
        df_chart = pd.DataFrame([dict(row) for row in messages_data])
        df_chart.columns = ["Jour", "Messages"]
        df_chart["Jour"] = pd.to_datetime(df_chart["Jour"])  # Convertir en datetime
        # Afficher un graphique en barres
        st.bar_chart(df_chart.set_index("Jour"))
    else:
        st.info("Pas encore de données. Les statistiques apparaîtront quand des utilisateurs poseront des questions.")

with col_review:
    # --- Questions sans réponse que l'admin devrait examiner ---
    st.subheader("⚠️ À examiner")

    # Récupérer les 10 dernières questions sans réponse
    unanswered_list = get_unanswered_questions(limit=10)
    
    if unanswered_list:
        cards_html = ""
        for q in unanswered_list:
            question_text = str(q['question']).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            timestamp_text = str(q['timestamp'])
            cards_html += (
                '<div class="unanswered-card">'
                '<div class="unanswered-label">Question sans réponse</div>'
                '<div class="unanswered-question">"' + question_text + '"</div>'
                '<div style="font-size: 11px; color: #94a3b8; margin-top: 6px;">' + timestamp_text + '</div>'
                '</div>'
            )
        st.markdown(
            '<div style="max-height: 340px; overflow-y: auto; padding-right: 8px;">'
            + cards_html
            + '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.success("🎉 Aucune question sans réponse !")

st.markdown("---")

# =============================================
# SECTION 5 : INTERACTIONS RÉCENTES + STATISTIQUES DÉTAILLÉES
# =============================================
col_recent, col_stats = st.columns([2, 1])

with col_recent:
    st.subheader("💬 Interactions récentes")

    # Récupérer les 15 dernières interactions
    recent = get_recent_interactions(limit=15)

    if recent:
        for interaction in recent:
            # Choisir la couleur du point : vert = répondu, jaune = sans réponse
            dot_class = "dot-green" if interaction["answered"] else "dot-yellow"
            status_text = "Répondu" if interaction["answered"] else "Sans réponse"

            # Calculer le temps relatif ("il y a 5 min", "il y a 2 jours")
            ts = datetime.strptime(interaction["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - ts
            if diff.seconds < 60:
                time_ago = "À l'instant"
            elif diff.seconds < 3600:
                time_ago = f"Il y a {diff.seconds // 60} min"
            elif diff.days == 0:
                time_ago = f"Il y a {diff.seconds // 3600}h"
            else:
                time_ago = f"Il y a {diff.days} jour(s)"
            
            # Tronquer la question si trop longue
            question_short = interaction["question"][:80] + "..." if len(interaction["question"]) > 80 else interaction["question"]
            
            st.markdown(f"""
            <div class="interaction-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="{dot_class}"></span>
                        <span class="interaction-user">{status_text}</span>
                    </div>
                    <span class="interaction-time">{time_ago}</span>
                </div>
                <div class="interaction-question">Q: {question_short}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucune interaction pour le moment.")

with col_stats:
    st.subheader("📊 Statistiques détaillées")
    
    if total > 0:
        # Pie chart répondu vs non répondu
        df_pie = pd.DataFrame({
            "Statut": ["Répondu", "Sans réponse"],
            "Nombre": [answered, unanswered]
        })
        st.bar_chart(df_pie.set_index("Statut"))
        
        st.metric("Total questions", total)
        st.metric("Répondues", answered)
        st.metric("Sans réponse", unanswered)
        st.metric("Taux de succès", f"{success_rate}%")
    else:
        st.info("Pas encore de données.")

st.markdown("---")

# =============================================
# SECTION 7 : TABLEAU COMPLET DES LOGS
# =============================================
# Affiche TOUTES les interactions dans un tableau interactif
# avec filtres et possibilité de trier par colonne
st.subheader("📋 Historique complet")

# Récupérer toutes les interactions depuis SQLite
all_logs = get_all_logs()

if all_logs:
    # Convertir les résultats SQLite en DataFrame pandas
    df = pd.DataFrame([dict(row) for row in all_logs])

    # Boutons radio pour filtrer : Tous / Répondues / Sans réponse
    filtre = st.radio("Filtrer par", ["Tous", "Répondues", "Sans réponse"], horizontal=True)

    # Appliquer le filtre sélectionné
    if filtre == "Répondues":
        df = df[df["answered"] == 1]     # Garder seulement answered = 1
    elif filtre == "Sans réponse":
        df = df[df["answered"] == 0]     # Garder seulement answered = 0

    # Sélectionner et renommer les colonnes pour un affichage plus lisible
    df_display = df[["timestamp", "question", "response", "answered", "num_docs_found"]].copy()
    df_display.columns = ["Date", "Question", "Réponse", "Répondu", "Docs trouvés"]

    # Remplacer 1/0 par des emojis pour plus de clarté
    df_display["Répondu"] = df_display["Répondu"].map({1: "✅ Oui", 0: "❌ Non"})

    # Afficher le tableau interactif (triable, scrollable)
    st.dataframe(df_display, use_container_width=True, height=400)
else:
    st.info("Aucune interaction enregistrée pour le moment. Les données apparaîtront quand des utilisateurs utiliseront le chatbot.")

# =============================================
# FOOTER
# =============================================
st.markdown("---")
st.markdown(
    """<div style="text-align: center; color: #94a3b8; font-size: 13px; padding: 12px 0;">
        🎓 © 2025 Université Paris-Saclay — AI Assistant Team
    </div>""",
    unsafe_allow_html=True,
)
