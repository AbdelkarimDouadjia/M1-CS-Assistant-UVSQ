# ================================================================
# chat_logger.py - Enregistrement des questions/réponses dans SQLite
# ================================================================
# Ce fichier gère la base de données SQLite qui stocke toutes les
# interactions entre les utilisateurs et le chatbot.
#
# Pourquoi SQLite ?
#   - Intégré à Python (pas besoin d'installer un serveur)
#   - Fichier unique (chat_logs.db) facile à sauvegarder
#   - Rapide pour les requêtes (COUNT, GROUP BY, etc.)
#   - Accès concurrent (chatbot + dashboard en même temps)
#
# Structure de la table chat_logs :
#   | Colonne         | Type    | Description                          |
#   |-----------------|---------|--------------------------------------|
#   | id              | INTEGER | Identifiant auto-incrémenté          |
#   | timestamp       | TEXT    | Date et heure de la question         |
#   | question        | TEXT    | La question posée par l'utilisateur  |
#   | response        | TEXT    | La réponse du chatbot                |
#   | answered        | INTEGER | 1 = répondu, 0 = sans réponse        |
#   | num_docs_found  | INTEGER | Nombre de documents trouvés          |
#   | session_id      | TEXT    | Identifiant unique de la session     |
# ================================================================

import sqlite3           # Module Python intégré pour manipuler des bases SQLite
import os
from datetime import datetime

# --- Chemin vers le fichier de base de données ---
# Le fichier chat_logs.db est créé automatiquement à la racine du projet
DB_PATH = "chat_logs.db"


def get_connection():
    """
    Ouvre une connexion vers la base SQLite.
    
    row_factory = sqlite3.Row permet d'accéder aux colonnes par nom :
        row["question"] au lieu de row[0]
    
    Returns:
        sqlite3.Connection : La connexion à la base.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Crée la table chat_logs si elle n'existe pas encore.
    
    CREATE TABLE IF NOT EXISTS = ne crée la table que si elle n'existe pas déjà.
    Appelée au début de chaque fonction pour être sûr que la table existe.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            response TEXT,
            answered INTEGER NOT NULL DEFAULT 1,
            num_docs_found INTEGER DEFAULT 0,
            session_id TEXT
        )
    """)
    conn.commit()    # Sauvegarder les changements
    conn.close()     # Fermer la connexion


# ================================================================
# FONCTION D'ÉCRITURE - Appelée par chatbot.py
# ================================================================

def log_question(question, response, answered=True, num_docs_found=0, session_id=None):
    """
    Enregistre une interaction (question + réponse) dans la base SQLite.
    
    Appelée automatiquement par chatbot.py après chaque réponse du chatbot.
    
    Args:
        question (str)      : La question posée par l'utilisateur.
        response (str)      : La réponse générée par le chatbot.
        answered (bool)     : True si le chatbot a pu répondre, False sinon.
                              Déterminé par la détection de mots-clés dans chatbot.py.
        num_docs_found (int): Nombre de documents trouvés dans ChromaDB.
        session_id (str)    : Identifiant unique de la session utilisateur.
    """
    init_db()  # S'assurer que la table existe
    conn = get_connection()
    conn.execute(
        """INSERT INTO chat_logs (timestamp, question, response, answered, num_docs_found, session_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Date actuelle formatée
            question,
            response,
            1 if answered else 0,    # Convertir True/False en 1/0 pour SQLite
            num_docs_found,
            session_id,
        ),
    )
    conn.commit()    # Sauvegarder l'insertion
    conn.close()     # Fermer la connexion


# ================================================================
# FONCTIONS DE LECTURE - Appelées par admin_dashboard.py
# ================================================================
# Ces fonctions exécutent des requêtes SQL pour récupérer les statistiques
# affichées dans le dashboard admin.


def get_total_messages():
    """
    Compte le nombre TOTAL de messages dans la base.
    SQL : SELECT COUNT(*) → compte toutes les lignes.
    Affiché dans la carte "Total Messages" du dashboard.
    """
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) as total FROM chat_logs").fetchone()
    conn.close()
    return result["total"]


def get_answered_count():
    """
    Compte les questions auxquelles le chatbot A répondu (answered = 1).
    Affiché dans la carte "Taux de succès" et "Statistiques détaillées".
    """
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) as total FROM chat_logs WHERE answered = 1").fetchone()
    conn.close()
    return result["total"]


def get_unanswered_count():
    """
    Compte les questions auxquelles le chatbot N'A PAS répondu (answered = 0).
    Affiché dans la carte "Questions sans réponse" du dashboard.
    """
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) as total FROM chat_logs WHERE answered = 0").fetchone()
    conn.close()
    return result["total"]


def get_success_rate():
    """
    Calcule le taux de succès en pourcentage.
    Formule : (nombre de réponses / total) × 100
    Exemple : 8 réponses sur 10 questions → 80.0%
    Affiché dans la carte "Taux de succès" du dashboard.
    """
    total = get_total_messages()
    if total == 0:          # Éviter la division par zéro
        return 0.0
    answered = get_answered_count()
    return round((answered / total) * 100, 1)  # Arrondi à 1 décimale


def get_unanswered_questions(limit=50):
    """
    Récupère les questions sans réponse, les plus récentes d'abord.
    Affichées dans la section "⚠️ À examiner" du dashboard.
    
    Args:
        limit (int): Nombre max de résultats (par défaut 50).
    
    Returns:
        list : Liste de lignes SQLite (dictionnaires).
    """
    init_db()
    conn = get_connection()
    results = conn.execute(
        "SELECT * FROM chat_logs WHERE answered = 0 ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return results


def get_recent_interactions(limit=20):
    """
    Récupère les dernières interactions (répondues ou non).
    Affichées dans la section "💬 Interactions récentes" du dashboard.
    
    Args:
        limit (int): Nombre max de résultats (par défaut 20).
    
    Returns:
        list : Liste de lignes SQLite triées par date décroissante.
    """
    init_db()
    conn = get_connection()
    results = conn.execute(
        "SELECT * FROM chat_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return results


def get_messages_per_day(days=7):
    """
    Retourne le nombre de messages par jour sur les N derniers jours.
    Utilisé pour le graphique "📈 Tendance des messages" du dashboard.
    
    SQL : GROUP BY DATE(timestamp) → regroupe les messages par jour.
    
    Args:
        days (int): Nombre de jours à afficher (par défaut 7).
    
    Returns:
        list : Liste de tuples (jour, nombre_de_messages).
    """
    init_db()
    conn = get_connection()
    results = conn.execute(
        """SELECT DATE(timestamp) as jour, COUNT(*) as total
           FROM chat_logs
           WHERE DATE(timestamp) >= DATE('now', ?)
           GROUP BY DATE(timestamp)
           ORDER BY jour ASC""",
        (f"-{days} days",)   # Exemple : "-7 days" = 7 jours en arrière
    ).fetchall()
    conn.close()
    return results


def get_all_logs():
    """
    Récupère TOUTES les interactions de la base.
    Utilisé pour :
      - Le tableau "📋 Historique complet" du dashboard
      - L'export CSV (bouton "Exporter le rapport")
    
    Returns:
        list : Toutes les lignes de la table, triées par date décroissante.
    """
    init_db()
    conn = get_connection()
    results = conn.execute("SELECT * FROM chat_logs ORDER BY timestamp DESC").fetchall()
    conn.close()
    return results


def get_messages_today():
    """
    Compte les messages envoyés AUJOURD'HUI.
    SQL : DATE(timestamp) = DATE('now') → filtre sur la date du jour.
    Affiché dans la carte "Messages aujourd'hui" du dashboard.
    """
    init_db()
    conn = get_connection()
    result = conn.execute(
        "SELECT COUNT(*) as total FROM chat_logs WHERE DATE(timestamp) = DATE('now')"
    ).fetchone()
    conn.close()
    return result["total"]
