import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from pathlib import Path
from dashboard_styles import DASHBOARD_CSS

from ingest_database import (
    DATA_PATH,
    clear_and_reingest,
)
from chat_logger import (
    get_total_messages,
    get_answered_count,
    get_unanswered_count,
    get_success_rate,
    get_unanswered_questions,
    get_recent_interactions,
    get_messages_per_day,
    get_all_logs,
    get_messages_today,
)


@st.cache_data(ttl=30)
def load_evaluation_reports():
    """Charge les rapports d'evaluation JSON trouves dans le projet."""
    base_dir = Path(__file__).parent
    search_dirs = [base_dir, base_dir / "evaluation_chatbot"]
    reports = []

    def _to_report_payload(content):
        # Supporte 2 formats:
        # 1) dict avec "results"
        # 2) liste directe de resultats
        if isinstance(content, dict):
            results = content.get("results", []) if isinstance(content.get("results", []), list) else []
            payload = dict(content)
            payload["results"] = results
            return payload

        if isinstance(content, list):
            results = content
            total_questions = len(results)
            answered_count = sum(1 for r in results if isinstance(r, dict) and r.get("answered") is True)

            def _avg(field_name):
                vals = [r.get(field_name) for r in results if isinstance(r, dict) and isinstance(r.get(field_name), (int, float))]
                return (sum(vals) / len(vals)) if vals else None

            return {
                "results": results,
                "total_questions": total_questions,
                "answer_rate": (answered_count / total_questions) if total_questions else None,
                "global_score": _avg("hybrid_score"),
                "hybrid_scoring": {"avg_hybrid_score": _avg("hybrid_score")},
            }

        return None

    for directory in search_dirs:
        if not directory.exists():
            continue
        for file_path in directory.glob("*.json"):
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    content = json.load(f)
                payload = _to_report_payload(content)
                if payload is not None and isinstance(payload.get("results", []), list):
                    reports.append(
                        {
                            "name": file_path.name,
                            "mtime": file_path.stat().st_mtime,
                            "data": payload,
                        }
                    )
            except Exception:
                continue

    reports.sort(key=lambda item: item["mtime"], reverse=True)
    return reports


def _to_percent_value(value):
    """Convertit une valeur de score en pourcentage borné [0, 100]."""
    if not isinstance(value, (int, float)):
        return None
    percent = value * 100 if value <= 1 else value
    return max(0.0, min(100.0, float(percent)))


def _to_percent_text(value, decimals=1):
    percent = _to_percent_value(value)
    if percent is None:
        return "N/A"
    return f"{percent:.{decimals}f}%"

st.set_page_config(
    page_title="Saclay AI - Admin Dashboard",
    page_icon="📊",
    layout="wide",
)

st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

col_title, col_actions = st.columns([3, 1])

with col_title:
    st.markdown('<div class="dashboard-header">📊 University Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-subtitle">Métriques en temps réel du Chatbot IA Paris-Saclay</div>', unsafe_allow_html=True)

with col_actions:
    st.write("")

    all_logs = get_all_logs()
    if all_logs:
        df_export = pd.DataFrame([dict(row) for row in all_logs])
        csv = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Exporter le rapport (CSV)",
            data=csv,
            file_name=f"chat_logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

st.markdown("---")

total = get_total_messages()
answered = get_answered_count()
unanswered = get_unanswered_count()
success_rate = get_success_rate()
today = get_messages_today()

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
# SECTION : EVALUATION CHATBOT (SCORE + Q/R)
# =============================================
st.markdown("---")
st.subheader("🧪 Évaluation du chatbot")

evaluation_reports = load_evaluation_reports()

if evaluation_reports:
    options = [
        f"{r['name']} — {datetime.fromtimestamp(r['mtime']).strftime('%Y-%m-%d %H:%M:%S')}"
        for r in evaluation_reports
    ]
    selected_index = st.selectbox(
        "Choisir un rapport d'évaluation",
        options=range(len(options)),
        format_func=lambda idx: options[idx],
    )

    selected_report = evaluation_reports[selected_index]["data"]
    hybrid = selected_report.get("hybrid_scoring", {})

    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    with col_e1:
        st.metric("Questions évaluées", selected_report.get("total_questions", 0))
    with col_e2:
        answer_rate = selected_report.get("answer_rate")
        if not isinstance(answer_rate, (int, float)):
            results_tmp = selected_report.get("results", [])
            if results_tmp:
                answered_tmp = sum(1 for r in results_tmp if isinstance(r, dict) and r.get("answered") is True)
                answer_rate = answered_tmp / len(results_tmp)
        st.metric("Taux de réponse", _to_percent_text(answer_rate, decimals=1))
    with col_e3:
        global_score = selected_report.get("global_score")
        if not isinstance(global_score, (int, float)):
            vals = [
                r.get("hybrid_score")
                for r in selected_report.get("results", [])
                if isinstance(r, dict) and isinstance(r.get("hybrid_score"), (int, float))
            ]
            global_score = (sum(vals) / len(vals)) if vals else None
        st.metric("Score global", _to_percent_text(global_score, decimals=1))
    with col_e4:
        avg_hybrid_score = hybrid.get("avg_hybrid_score")
        if not isinstance(avg_hybrid_score, (int, float)):
            vals = [
                r.get("hybrid_score")
                for r in selected_report.get("results", [])
                if isinstance(r, dict) and isinstance(r.get("hybrid_score"), (int, float))
            ]
            avg_hybrid_score = (sum(vals) / len(vals)) if vals else None
        st.metric("Score hybride", _to_percent_text(avg_hybrid_score, decimals=1))

    results = selected_report.get("results", [])
    if results:
        df_eval = pd.DataFrame(results)

        preferred_columns = [
            "question",
            "response",
            "answered",
            "num_docs",
            "hybrid_score",
            "judge_score",
            "rag_score",
        ]
        display_columns = [c for c in preferred_columns if c in df_eval.columns]
        if not display_columns:
            display_columns = list(df_eval.columns)

        df_display_eval = df_eval[display_columns].copy()
        if "answered" in df_display_eval.columns:
            df_display_eval["answered"] = df_display_eval["answered"].map({True: "✅ Oui", False: "❌ Non"})
        rename_map = {
            "question": "Question",
            "response": "Réponse",
            "answered": "Répondu",
            "num_docs": "Docs trouvés",
            "hybrid_score": "Score hybride",
            "judge_score": "Score judge",
            "rag_score": "Score RAG",
        }
        df_display_eval = df_display_eval.rename(columns=rename_map)

        st.markdown("##### Questions et réponses évaluées")
        st.dataframe(df_display_eval, use_container_width=True, height=420)

        eval_csv = df_display_eval.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Exporter les questions/réponses évaluées (CSV)",
            data=eval_csv,
            file_name=f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Ce rapport ne contient pas de résultats détaillés.")
else:
    st.info(
        "Aucun rapport d'évaluation trouvé. Lancez d'abord le script d'évaluation, "
        "puis rechargez ce dashboard."
    )

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
                nb_chunks = clear_and_reingest(reset_vector_store=False)  # Appel à ingest_database.py
                st.success(f"✅ Base mise à jour ! ({nb_chunks} chunks créés)")
            except Exception as e:
                st.error(f"❌ Erreur : {e}")


    if st.button("⚠️ Vider la base de données (sans avec regeneration )", type="secondary"):
        with st.spinner("Vider la base de données... Veuillez patienter."):
            try:
                clear_and_reingest(reset_vector_store=True)  # Appel à ingest_database.py
                st.success(f"✅ Base vidée ! Tous les documents supprimés de ChromaDB.")
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
                if file_name.endswith(".yaml"):
                    continue  # Ignorer les fichiers de config YAML générés
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
