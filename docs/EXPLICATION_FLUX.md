# Explication complète du flux du projet Chatbot

## Flux complet du projet chatbot — de A à Z

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           PRÉPARATION (une seule fois)                       │
│                                                                              │
│  L'admin dépose des fichiers PDF/TXT dans data/                              │
│        │                                                                     │
│        ▼                                                                     │
│  app/admin_dashboard.py : st.file_uploader()                                     │
│  → uploaded_file.getbuffer() → open("data/fichier.pdf", "wb") → disque       │
│        │                                                                     │
│        ▼                                                                     │
│  L'admin clique "🚀 Mettre à jour la base de données"                       │
│        │                                                                     │
│        ▼                                                                     │
│  chatbot_core/ingest_database.py : clear_and_reingest()                                   │
│    1. Vider ChromaDB (supprimer tous les anciens vecteurs)                   │
│    2. os.listdir("data/") → lister tous les fichiers                         │
│    3. Lire chaque fichier (PDF → extraire texte / TXT → lire brut)          │
│    4. Découper le texte en chunks (petits morceaux)                          │
│    5. Transformer chaque chunk en vecteur (embedding IA)                     │
│    6. Stocker les vecteurs dans ChromaDB (chroma_db/)                        │
│    7. Retourner le nombre de chunks créés                                    │
│        │                                                                     │
│        ▼                                                                     │
│  ChromaDB est prêt (chroma_db/) ✅                                           │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                    UTILISATION (à chaque question)                           │
│                                                                              │
│  L'utilisateur ouvre le chatbot et pose une question                         │
│  "Quels sont les masters disponibles ?"                                      │
│        │                                                                     │
│        ▼                                                                     │
│  app/chatbot.py : Étape 1 - Recherche dans ChromaDB                              │
│    → La question est transformée en vecteur (même modèle d'embedding)        │
│    → ChromaDB compare ce vecteur avec tous les chunks stockés                │
│    → Retourne les N documents les plus proches (les plus pertinents)         │
│        │                                                                     │
│        ▼                                                                     │
│  app/chatbot.py : Étape 2 - Génération de la réponse (LLM / IA)                  │
│    → Envoie au modèle IA : "Voici les documents trouvés + la question"       │
│    → Le modèle génère une réponse en langage naturel                         │
│        │                                                                     │
│        ▼                                                                     │
│  app/chatbot.py : Étape 3 - Détection succès / échec                             │
│    → Parcourt la réponse pour chercher des mots-clés d'échec :               │
│      "je ne sais pas", "aucune information", "désolé", "no information"...   │
│    → any(kw in response.lower() for kw in unanswered_keywords)               │
│    → Si mot-clé trouvé → answered = False (❌ sans réponse)                  │
│    → Si aucun mot-clé   → answered = True  (✅ répondu)                      │
│        │                                                                     │
│        ▼                                                                     │
│  app/chatbot.py : Étape 4 - Enregistrement dans SQLite                           │
│    → Appelle chatbot_core/chat_logger.py : log_question()                                 │
│      INSERT INTO chat_logs VALUES (                                          │
│        timestamp  = "2026-03-10 14:30:00",                                   │
│        question   = "Quels sont les masters ?",                              │
│        response   = "Voici les masters disponibles...",                      │
│        answered   = 1,           (1 = oui, 0 = non)                          │
│        num_docs   = 3,           (3 documents trouvés)                       │
│        session_id = "abc123"                                                 │
│      )                                                                       │
│        │                                                                     │
│        ▼                                                                     │
│  chat_logs.db (fichier SQLite) ← la ligne est sauvegardée                    │
│        │                                                                     │
│        ▼                                                                     │
│  app/chatbot.py : Étape 5 - Affichage                                            │
│    → La réponse est affichée à l'utilisateur dans l'interface Streamlit      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                     DASHBOARD ADMIN (consultation)                           │
│                                                                              │
│  L'admin ouvre app/admin_dashboard.py → Streamlit exécute tout le code           │
│        │                                                                     │
│        ▼                                                                     │
│  Lecture des stats depuis SQLite (chatbot_core/chat_logger.py) :                          │
│                                                                              │
│    get_total_messages()                                                      │
│      → SELECT COUNT(*) FROM chat_logs                        → ex: 150       │
│                                                                              │
│    get_answered_count()                                                      │
│      → SELECT COUNT(*) FROM chat_logs WHERE answered = 1     → ex: 120       │
│                                                                              │
│    get_unanswered_count()                                                    │
│      → SELECT COUNT(*) FROM chat_logs WHERE answered = 0     → ex: 30        │
│                                                                              │
│    get_success_rate()                                                        │
│      → Python : (120 / 150) × 100 = 80.0%                                    │
│                                                                              │
│    get_messages_today()                                                      │
│      → SELECT COUNT(*) WHERE DATE(timestamp) = DATE('now')   → ex: 5         │
│                                                                              │
│    get_messages_per_day(7)                                                   │
│      → SELECT DATE(timestamp), COUNT(*) GROUP BY DATE(timestamp)             │
│      → [("2026-03-04", 12), ("2026-03-05", 8), ...]                          │
│      → Affiché en graphique barres via st.bar_chart()                        │
│                                                                              │
│    get_unanswered_questions(10)                                              │
│      → SELECT * WHERE answered = 0 ORDER BY timestamp DESC LIMIT 10          │
│      → Affiché dans la zone scrollable "⚠️ À examiner"                       │
│                                                                              │
│    get_recent_interactions(15)                                               │
│      → SELECT * ORDER BY timestamp DESC LIMIT 15                             │
│      → Affiché avec points verts/jaunes + temps relatif                      │
│                                                                              │
│    get_all_logs()                                                            │
│      → SELECT * FROM chat_logs ORDER BY timestamp DESC                       │
│      → Affiché dans le tableau "📋 Historique complet"                      │
│      → Converti en CSV via pandas pour le bouton "📥 Exporter"              │
│        │                                                                     │
│        ▼                                                                     │
│  Streamlit affiche tout dans le navigateur (HTML + CSS personnalisé)         │
│  À chaque rechargement → les données sont relues depuis SQLite = temps réel  │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                     BOUCLE D'AMÉLIORATION                                    │
│                                                                              │
│  1. L'admin consulte "⚠️ À examiner" → voit les questions sans réponse      │
│  2. Il identifie les sujets manquants                                        │
│  3. Il prépare des fichiers PDF/TXT couvrant ces sujets                      │
│  4. Il les upload via le dashboard (st.file_uploader)                        │
│  5. Il clique "🚀 Mettre à jour" → clear_and_reingest()                     │
│  6. ChromaDB contient maintenant les nouveaux documents                      │
│  7. Le chatbot peut désormais répondre à ces questions → taux de succès ↑    │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                   ÉVALUATION OFFLINE DU CHATBOT                              │
│                                                                              │
│  L'admin/l'équipe lance le script evaluate_app/chatbot.py                        │
│  (questions depuis evaluation_chatbot/question.md)                           │
│        │                                                                     │
│        ▼                                                                     │
│  evaluate_app/chatbot.py : Pour chaque question                                  │
│    1. Recherche top-k chunks dans ChromaDB                                   │
│    2. Génère une réponse via LLM                                             │
│    3. Détecte si réponse valide ou non (answered True/False)                 │
│    4. Calcule score RAG (pertinence, couverture, citations)                  │
│    5. Calcule score Judge LLM (fidélité, pertinence, complétude)             │
│    6. Combine en score hybride                                               │
│        │                                                                     │
│        ▼                                                                     │
│  Sauvegarde automatique :                                                    │
│    evaluation_results_YYYYMMDD_HHMMSS.json                                   │
│    evaluation_results_YYYYMMDD_HHMMSS.csv                                    │
│        │                                                                     │
│        ▼                                                                     │
│  app/admin_dashboard.py : section "🧪 Évaluation du chatbot"                    │
│    → load_evaluation_reports() lit les fichiers JSON                         │
│    → L'admin choisit un rapport dans une liste                               │
│    → Affiche métriques : nb questions, taux de réponse, score global/hybride │
│    → Affiche tableau Q/R évaluées + export CSV                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Les 5 fichiers et leur rôle

| Fichier | Rôle | Base de données |
|---|---|---|
| **app/chatbot.py** | Interface utilisateur + recherche + réponse IA + écriture logs | Lit ChromaDB / Écrit dans SQLite |
| **chatbot_core/chat_logger.py** | Fonctions SQL (écriture + lecture) | Lit et écrit dans SQLite (`chat_logs.db`) |
| **app/admin_dashboard.py** | Interface admin + stats + gestion fichiers | Lit SQLite / Gère `data/` + ChromaDB |
| **chatbot_core/ingest_database.py** | Vectorisation des documents | Lit `data/` / Écrit dans ChromaDB |
| **evaluate_app/chatbot.py** | Évaluation automatique des réponses (RAG + Judge + hybride) | Lit ChromaDB / Génère `evaluation_results_*.json` et `.csv` |

## Les 2 bases de données

| Base | Format | Contenu | Utilisée par |
|---|---|---|---|
| **chat_logs.db** | SQLite (fichier) | Toutes les questions/réponses | app/chatbot.py (écriture) + app/admin_dashboard.py (lecture) |
| **chroma_db/** | ChromaDB (dossier) | Vecteurs des documents PDF/TXT | chatbot_core/ingest_database.py (écriture) + app/chatbot.py (lecture) |

---

## Détail technique par section du Dashboard

### 1. En-tête (haut de page)
- **Titre** : "📊 University Dashboard" avec le sous-titre "Métriques en temps réel du Chatbot IA Paris-Saclay"
- **Bouton "📥 Exporter le rapport (CSV)"** : télécharge un fichier CSV contenant toutes les interactions (questions, réponses, dates) depuis la base SQLite. Utile pour analyser les données dans Excel.

### 2. Les 4 cartes de statistiques

| Carte | Ce qu'elle affiche |
|---|---|
| 💬 **Total Messages** | Le nombre total de questions posées au chatbot depuis le début |
| ✅ **Taux de succès** | Le pourcentage de questions auxquelles le chatbot a trouvé une réponse |
| ⚠️ **Questions sans réponse** | Le nombre de questions où le chatbot n'a pas pu répondre |
| 📈 **Messages aujourd'hui** | Le nombre de questions posées uniquement aujourd'hui |

### 2 bis. Évaluation du chatbot (section dédiée)
- **Sélecteur de rapport** : la section "🧪 Évaluation du chatbot" scanne les fichiers `.json` d'évaluation et permet d'en choisir un.
- **4 métriques affichées** :
    - Questions évaluées
    - Taux de réponse
    - Score global
    - Score hybride
- **Tableau détaillé** : affiche les Q/R évaluées avec colonnes comme Question, Réponse, Répondu, Docs trouvés, Score hybride, Score judge, Score RAG.
- **Export CSV** : bouton pour exporter le tableau d'évaluation affiché.

### 3. Knowledge Base — Gestion des documents

#### Colonne gauche — Ajouter des fichiers
- **Zone de drag-and-drop** : glissez-déposez (ou cliquez pour parcourir) des fichiers PDF ou TXT. Ces fichiers sont sauvegardés dans le dossier `data/`. C'est la base de connaissances du chatbot — il répond aux questions à partir de ces documents.
- **Bouton "🚀 Mettre à jour la base de données"** : après avoir ajouté ou supprimé des fichiers, cliquez ici. Cela vide ChromaDB (la base vectorielle) puis réingère tous les fichiers de `data/`. Le chatbot utilisera ensuite les nouveaux documents.

#### Colonne droite — Fichiers existants
- Affiche la liste des fichiers présents dans `data/` avec leur taille en KB.
- Chaque fichier a un bouton 🗑️ pour le supprimer. Après suppression, pensez à cliquer "Mettre à jour la base de données" pour que le chatbot ne cherche plus dans ce fichier.

### 4. Tendance des messages (graphique)
- Un graphique en barres montrant le nombre de messages par jour.
- Un menu déroulant permet de choisir la période : 7, 14 ou 30 derniers jours.

### 5. À examiner
- Affiche les 10 dernières questions sans réponse dans une zone scrollable (3 visibles à la fois).
- Chaque carte jaune montre la question posée et la date/heure.
- Cela permet à l'admin d'identifier les sujets manquants et d'ajouter les documents correspondants.

### 6. Interactions récentes
- Liste les 15 dernières interactions avec le chatbot.
- Point vert 🟢 = question répondue, point jaune 🟡 = sans réponse.
- Affiche le temps écoulé ("Il y a 5 min", "Il y a 2 jours") et un aperçu de la question.

### 7. Statistiques détaillées
- Un graphique en barres répondu vs non répondu.
- 4 métriques : total, répondues, sans réponse, taux de succès.

### 8. Historique complet (tableau)
- Un tableau interactif avec toutes les interactions (triable, scrollable).
- Filtres radio : "Tous", "Répondues", "Sans réponse" pour filtrer les lignes.
- Colonnes : Date, Question, Réponse, Répondu (✅/❌), Docs trouvés.

---

## Détail technique : Évaluation du chatbot (evaluate_app/chatbot.py)

### Étape 1 : Lancer l'évaluation
```bash
python -m tools.evaluate_chatbot
```
Options possibles :
- `--input-file` : choisir un autre fichier de questions
- `--max-questions` : limiter le nombre de questions évaluées

### Étape 2 : Calcul des scores
Pour chaque question, le script produit :
- `answered` : réponse valable ou non
- `rag_score` : score RAG (pertinence contexte, couverture, citations)
- `judge_score` : score LLM-as-Judge (fidélité, pertinence, complétude)
- `hybrid_score` : combinaison pondérée RAG + Judge, avec pénalité si non-réponse

### Étape 3 : Fichiers générés
Le script enregistre automatiquement :
- `evaluation_results_YYYYMMDD_HHMMSS.json`
- `evaluation_results_YYYYMMDD_HHMMSS.csv`

---

## Détail technique : Affichage de l'évaluation dans le Dashboard Admin

Dans `app/admin_dashboard.py`, la section "🧪 Évaluation du chatbot" :
1. Appelle `load_evaluation_reports()` qui parcourt les `.json` du projet.
2. Normalise le format (dict avec `results` ou liste directe).
3. Trie les rapports par date de modification (le plus récent en haut).
4. Affiche les métriques globales avec `st.metric`.
5. Affiche le détail dans `st.dataframe`.
6. Propose un export CSV des questions/réponses évaluées.

Cette section permet d'analyser la **qualité des réponses** (évaluation offline) en plus des **statistiques d'usage** (logs SQLite en temps réel).

---

## Détail technique : Upload de fichiers

### Étape 1 : L'utilisateur choisit un fichier
```python
uploaded_files = st.file_uploader(
    "Glissez-déposez vos fichiers ici",
    type=["pdf", "txt"],
    accept_multiple_files=True,
)
```
- `st.file_uploader()` est une fonction Streamlit qui affiche un bouton de téléversement.
- `type=["pdf", "txt"]` → n'accepte que les PDF et TXT.
- `accept_multiple_files=True` → on peut sélectionner plusieurs fichiers d'un coup.
- Streamlit stocke le fichier en mémoire RAM (pas encore sur le disque).

### Étape 2 : Sauvegarder le fichier sur le disque
```python
for uploaded_file in uploaded_files:
    file_path = os.path.join(DATA_PATH, uploaded_file.name)
    # DATA_PATH = "data" (défini dans chatbot_core/ingest_database.py)

    if os.path.exists(file_path):
        st.warning(f"⚠️ {uploaded_file.name} existe déjà, il sera remplacé.")

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"✅ {uploaded_file.name} sauvegardé !")
```
- `os.path.join(DATA_PATH, uploaded_file.name)` → construit le chemin `data/mon_fichier.pdf`
- `os.path.exists(file_path)` → vérifie si le fichier existe déjà
- `open(file_path, "wb")` → ouvre un fichier en écriture binaire (nécessaire pour les PDF)
- `uploaded_file.getbuffer()` → récupère le contenu brut du fichier depuis la RAM
- `f.write(...)` → écrit les octets sur le disque dans `data/`

---

## Détail technique : Mise à jour de ChromaDB

```python
if st.button("🚀 Mettre à jour la base de données", type="primary"):
    with st.spinner("Mise à jour en cours..."):
        nb_chunks = clear_and_reingest()
```
`clear_and_reingest()` (dans chatbot_core/ingest_database.py) fait :
1. Vider ChromaDB → supprime tous les vecteurs existants
2. Lister les fichiers dans `data/` avec `os.listdir(DATA_PATH)`
3. Lire chaque fichier (PDF → extraction texte / TXT → lecture brute)
4. Découper en chunks → le texte est découpé en petits morceaux
5. Vectoriser → chaque chunk est transformé en vecteur numérique (embedding)
6. Stocker dans ChromaDB → les vecteurs sont enregistrés dans `chroma_db/`
7. Retourner `nb_chunks` → le nombre total de morceaux créés

---

## Détail technique : Suppression d'un fichier

```python
if st.button("🗑️", key=f"del_{file_name}"):
    os.remove(os.path.join(DATA_PATH, file_name))
    st.rerun()
```
- `os.remove()` → supprime le fichier du dossier `data/`
- `st.rerun()` → recharge la page Streamlit pour actualiser la liste
- Le fichier est supprimé du disque, mais reste encore dans ChromaDB jusqu'au prochain clic sur "Mettre à jour"

---

## Détail technique : Liste des fichiers existants

```python
files = [f for f in os.listdir(DATA_PATH) if not f.startswith(".")]
file_size = os.path.getsize(os.path.join(DATA_PATH, file_name))
size_kb = file_size / 1024
```
- `os.listdir(DATA_PATH)` → liste tous les fichiers dans `data/`
- `not f.startswith(".")` → ignore les fichiers cachés (ex: `.DS_Store`)
- `os.path.getsize()` → retourne la taille en octets
- `/ 1024` → convertit en kilooctets

---

## Détail technique : Fonctions de statistiques (chatbot_core/chat_logger.py)

| Fonction | Requête SQL | Résultat |
|---|---|---|
| `get_total_messages()` | `SELECT COUNT(*) FROM chat_logs` | Nombre total |
| `get_answered_count()` | `SELECT COUNT(*) FROM chat_logs WHERE answered = 1` | Nb répondues |
| `get_unanswered_count()` | `SELECT COUNT(*) FROM chat_logs WHERE answered = 0` | Nb sans réponse |
| `get_success_rate()` | Calcul Python : `answered / total * 100` | Pourcentage |
| `get_messages_today()` | `WHERE DATE(timestamp) = DATE('now')` | Messages du jour |
| `get_unanswered_questions()` | `WHERE answered = 0 ORDER BY timestamp DESC` | Liste des questions |
| `get_recent_interactions()` | `ORDER BY timestamp DESC LIMIT 15` | 15 dernières |
| `get_messages_per_day(days)` | `GROUP BY DATE(timestamp)` sur N jours | Données du graphique |
| `get_all_logs()` | `SELECT * FROM chat_logs` | Tout (pour Export CSV) |

Chaque fonction :
1. Appelle `init_db()` → vérifie que la table existe
2. Appelle `get_connection()` → ouvre la connexion (avec `row_factory = sqlite3.Row` pour accéder par nom)
3. Exécute une requête SQL → `fetchone()` pour un seul résultat ou `fetchall()` pour plusieurs
4. Ferme la connexion
5. Retourne le résultat

---

**En résumé** : l'upload passe par Streamlit (RAM) → `os` (disque `data/`) → `clear_and_reingest()` (ChromaDB). Les stats passent par `chatbot_core/chat_logger.py` → SQLite → affichage Streamlit.
