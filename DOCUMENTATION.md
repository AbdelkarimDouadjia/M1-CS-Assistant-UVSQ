# Chatbot M1 AMIS — Documentation Complète

> Assistant RAG (Retrieval-Augmented Generation) pour les étudiants du **M1 Informatique** — UVSQ / Université Paris-Saclay.  
> Le chatbot répond aux questions sur les cours, la notation, la compensation, le planning, les examens, les stages et les règles administratives, **uniquement à partir des documents universitaires indexés**.

---

## Table des Matières

1. [Architecture Générale](#1-architecture-générale)
2. [Stack Technique](#2-stack-technique)
3. [Modules du Projet](#3-modules-du-projet)
4. [Serveur Distant (Charizard)](#4-serveur-distant-charizard)
5. [Variables d'Environnement](#5-variables-denvironnement)
6. [Installation Locale](#6-installation-locale)
7. [Lancer le Projet](#7-lancer-le-projet)
8. [Flux de Données Détaillé](#8-flux-de-données-détaillé)
9. [Structure des Fichiers](#9-structure-des-fichiers)
10. [Plan de Rollback](#10-plan-de-rollback)
11. [FAQ / Troubleshooting](#11-faq--troubleshooting)

---

## 1. Architecture Générale

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MACHINE LOCALE                               │
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────────┐  │
│  │  Documents   │───▶│  Ingestion  │───▶│  ChromaDB (Vector Store) │  │
│  │  (data/)     │    │  Pipeline   │    │  (chroma_db/)            │  │
│  │  PDF + TXT   │    │             │    │                          │  │
│  └─────────────┘    └─────────────┘    └──────────┬───────────────┘  │
│                           │                        │                  │
│                     BAAI/bge-m3                     │                  │
│                     (embeddings)              Retrieval (top 12)      │
│                                                    │                  │
│  ┌─────────────────────────────────────────────────▼───────────────┐  │
│  │                    chatbot.py (Streamlit)                       │  │
│  │                                                                 │  │
│  │  1. Utilisateur pose une question                               │  │
│  │  2. bge-m3 encode la question → recherche dans ChromaDB         │  │
│  │  3. Récupère top 12 chunks                                      │  │
│  │  4. Reranker trie et garde les top 5                            │  │
│  │  5. LLM génère la réponse à partir des chunks                  │  │
│  │  6. Affiche la réponse + sources citées                         │  │
│  └────────────────────┬───────────────────┬───────────────────────┘  │
│                        │                   │                          │
│              SSH Tunnel │ (port 8000)       │ SSH Tunnel (port 8001)  │
└────────────────────────┼───────────────────┼─────────────────────────┘
                         │                   │
┌────────────────────────▼───────────────────▼─────────────────────────┐
│                   SERVEUR DISTANT (Charizard)                        │
│                   2× NVIDIA H100 NVL 96 Go                          │
│                                                                      │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐  │
│  │  vLLM — Port 8000        │  │  vLLM — Port 8001                │  │
│  │  Qwen3-30B-A3B           │  │  Qwen3-Reranker-4B               │  │
│  │  (Answer Model)          │  │  (Reranker)                       │  │
│  │  API OpenAI-compatible   │  │  API /v1/rerank                   │  │
│  └──────────────────────────┘  └──────────────────────────────────┘  │
│                                                                      │
│  Fallback local : Gemini 2.5 Flash (si vLLM inaccessible)           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stack Technique

### Rôle de Chaque Composant

| Composant | Modèle / Outil | Rôle | Où il tourne |
|-----------|----------------|------|---------------|
| **Answer Model** | `Qwen/Qwen3-30B-A3B` | Génère la réponse finale à partir du contexte récupéré | Serveur distant via vLLM |
| **Embeddings** | `BAAI/bge-m3` | Encode les documents et les questions en vecteurs pour la recherche sémantique | Machine locale (CPU) |
| **Reranker** | `Qwen/Qwen3-Reranker-4B` | Réordonne les chunks récupérés par pertinence avant de les envoyer au LLM | Serveur distant via vLLM |
| **Vector Store** | ChromaDB | Stocke les vecteurs d'embeddings et permet la recherche par similarité | Machine locale (disque) |
| **Serving Engine** | vLLM | Sert les modèles LLM sur GPU avec une API OpenAI-compatible | Serveur distant |
| **Frontend** | Streamlit | Interface web de chat | Machine locale |
| **Fallback LLM** | Gemini 2.5 Flash | Répond si vLLM est inaccessible | API Google Cloud |

### Pourquoi Ces Choix ?

- **Qwen3-30B-A3B** : Modèle récent, Apache 2.0, 256K contexte, 100+ langues, ~19 Go — très confortable sur 2× H100
- **BAAI/bge-m3** : Multilingue, supporte dense + sparse + multi-vector, 8192 tokens d'entrée, idéal pour documents FR/EN
- **Qwen3-Reranker-4B** : Reranker dédié de Qwen, améliore la pertinence des chunks récupérés avant génération
- **vLLM** : Serving haute performance avec PagedAttention, batching continu, API OpenAI-compatible
- **ChromaDB** : Simple, local, pas besoin de serveur externe pour le vector store

---

## 3. Modules du Projet

> Le projet est composé de **5 modules principaux** qui fonctionnent ensemble.

### 3.1 `chatbot.py` — Application Principale

**Fichier** : `chatbot.py` (302 lignes)

**Responsabilités** :
- Interface Streamlit (chat)
- Chargement des modèles (embeddings, LLM, fallback)
- Recherche dans ChromaDB (top 12 chunks)
- Reranking via API distante (garde top 5)
- Détection de connectivité (probes vLLM + reranker, cache 60s)
- Génération de réponse avec prompt grounded
- Affichage des sources citées
- Historique de conversation (3 derniers échanges)

**Fonctions clés** :

| Fonction | Description |
|----------|-------------|
| `_probe(url)` | Vérifie si un serveur est joignable (timeout 3s) |
| `is_vllm_up()` | Cache la disponibilité du serveur vLLM pendant 60s |
| `is_reranker_up()` | Cache la disponibilité du reranker pendant 60s |
| `build_vllm_chat()` | Crée un client ChatOpenAI pointant vers vLLM |
| `build_fallback_chat()` | Crée le LLM de fallback (Gemini ou autre modèle vLLM) |
| `load_models()` | Charge embeddings + LLM + vector store (caché par Streamlit) |
| `rerank()` | Appelle le reranker distant, fallback sur tri simple si down |
| `build_context()` | Formate les chunks en contexte numéroté pour le prompt |
| `format_source()` | Extrait nom de fichier, page, section pour citation |

### 3.2 `ingest_database.py` — Pipeline d'Ingestion

**Fichier** : `ingest_database.py` (115 lignes)

**Responsabilités** :
- Charger les documents PDF et TXT depuis `data/`
- Découper en chunks avec des séparateurs académiques
- Enrichir chaque chunk avec des métadonnées
- Reconstruire l'index ChromaDB avec bge-m3

**Pipeline** :
```
data/ (PDF + TXT)
    ↓ PyPDFDirectoryLoader + TextLoader
Pages brutes
    ↓ RecursiveCharacterTextSplitter
Chunks (1200 chars, overlap 150)
    ↓ enrich_chunk() — ajoute source_name, page, section, chunk_id, last_updated
    ↓ BAAI/bge-m3 embeddings
ChromaDB (chroma_db/)
```

**Séparateurs spéciaux** (adaptés aux documents universitaires) :
```
\n# , \n## , \nArticle , \nARTICLE , \nTitre , \nTITRE , \n\n , \n , .  ,
```

**Métadonnées par chunk** :

| Champ | Description |
|-------|-------------|
| `source_name` | Nom du fichier d'origine |
| `title` | Nom du fichier sans extension |
| `page` | Numéro de page (1-indexed) |
| `section` | Premier titre/heading trouvé dans le chunk |
| `chunk_id` | UUID unique |
| `last_updated` | Date de dernière modification du fichier source |

### 3.3 `admin_dashboard.py` — Dashboard Administrateur

**Fichier** : `admin_dashboard.py` (563 lignes)

**Responsabilités** :
- Affichage des métriques en temps réel (total messages, taux de succès, questions sans réponse)
- Gestion de la Knowledge Base (upload/suppression de fichiers PDF/TXT)
- Bouton de mise à jour ChromaDB (réingestion)
- Graphique de tendance des messages par jour
- Liste des questions sans réponse à examiner
- Tableau complet des interactions avec filtres
- Export CSV des logs
- Affichage des rapports d'évaluation du chatbot

**URL** : `http://localhost:8502` (port séparé du chatbot)

**Sections du dashboard** :

| Section | Description |
|---------|-------------|
| **Métriques** | Total messages, taux de succès, questions sans réponse, messages aujourd'hui |
| **Évaluation** | Scores du chatbot (hybride, RAG, judge) si un rapport JSON existe |
| **Knowledge Base** | Upload de fichiers, liste des documents, boutons de réingestion |
| **Tendances** | Graphique en barres du volume de messages sur 7/14/30 jours |
| **À examiner** | Questions auxquelles le chatbot n'a pas pu répondre |
| **Interactions** | Dernières 15 interactions avec statut et temps relatif |
| **Historique** | Tableau complet filtrable de toutes les interactions |

### 3.4 `chat_logger.py` — Enregistrement des Interactions

**Fichier** : `chat_logger.py` (265 lignes)

**Responsabilités** :
- Création et gestion de la base SQLite (`chat_logs.db`)
- Enregistrement de chaque interaction (question, réponse, statut, docs trouvés)
- Fonctions de statistiques pour le dashboard admin

**Fonctions clés** :

| Fonction | Description |
|----------|-------------|
| `log_question()` | Enregistre une interaction dans SQLite |
| `get_total_messages()` | Compte total de messages |
| `get_success_rate()` | Taux de succès en pourcentage |
| `get_unanswered_questions()` | Questions sans réponse récentes |
| `get_messages_per_day()` | Volume par jour (pour le graphique) |
| `get_all_logs()` | Toutes les interactions (pour l'export CSV) |

### 3.5 `dashboard_styles.py` — Styles CSS du Dashboard

**Fichier** : `dashboard_styles.py`

Contient la constante `DASHBOARD_CSS` avec tout le CSS personnalisé pour le dashboard admin (cartes, badges, couleurs, animations).

### 3.6 `evaluate_chatbot.py` — Script d'Évaluation

**Fichier** : `evaluate_chatbot.py`

Script d'évaluation automatique du chatbot. Pose une série de questions prédéfinies et mesure la qualité des réponses (score hybride, score RAG, score judge). Génère un rapport JSON utilisé par le dashboard.

### 3.7 Documents Indexés

**Dossier** : `data/`

| Fichier | Taille | Description |
|---------|--------|-------------|
| `Réunion_de_rentrée_—_M1_AMIS,_DataScale,_IRS_et_SeCReTS.pdf` | 8.8 Mo | Document principal : UE, notation, compensation, planning |
| `RI GS Humanités - Sciences du patrimoine.pdf` | 735 Ko | Règlement intérieur complémentaire |
| `reglement_int.pdf` | 718 Ko | Règlement intérieur supplémentaire |
| `M1_Info_UVSQ_RAG_cleaned.md` | 12.8 Ko | Document Markdown nettoyé pour le RAG |

**Résultat de l'indexation** : ~94 chunks dans ChromaDB avec `BAAI/bge-m3`.

---

## 4. Serveur Distant (Charizard)

### Informations

| Propriété | Valeur |
|-----------|--------|
| **Host** | `charizard.prism.uvsq.fr` |
| **User** | `abdelkarim` |
| **GPU** | 2× NVIDIA H100 NVL, 96 Go VRAM chacun |
| **OS** | Linux |
| **Accès** | SSH (nécessite réseau campus ou VPN UVSQ) |

### Ce qui est installé sur le serveur

| Composant | Chemin / Status |
|-----------|----------------|
| **Ollama** | `~/bin/bin/ollama` (installé manuellement sans sudo) |
| **qwen2.5:72b** | Déjà pullé dans Ollama (ancien modèle, fallback) |
| **vLLM** | À installer/confirmer via pip |

### Commandes pour démarrer vLLM sur le serveur

```bash
# 1. Se connecter au serveur
ssh abdelkarim@charizard.prism.uvsq.fr

# 2. Installer vLLM (si pas encore fait)
pip install vllm

# 3. Lancer le modèle de réponse (port 8000)
vllm serve Qwen/Qwen3-30B-A3B \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 2 \
    --generation-config vllm

# 4. Lancer le reranker (port 8001) — dans un autre terminal
vllm serve Qwen/Qwen3-Reranker-4B \
    --host 0.0.0.0 \
    --port 8001 \
    --runner pooling \
    --hf_overrides '{"architectures":["Qwen3ForSequenceClassification"],"classifier_from_token":["no","yes"],"is_original_qwen3_reranker":true}' \
    --chat-template examples/pooling/score/template/qwen3_reranker.jinja
```

### Vérifier que les services tournent

```bash
# Sur le serveur
curl http://localhost:8000/v1/models    # doit retourner le modèle Qwen3
curl http://localhost:8001/health        # doit retourner "ok"

# Depuis la machine locale (via tunnel SSH)
Invoke-WebRequest http://127.0.0.1:8000/v1/models
Invoke-WebRequest http://127.0.0.1:8001/health
```

---

## 5. Variables d'Environnement

Fichier : `.env` (copier depuis `.env.example`)

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `VLLM_API_BASE` | `http://localhost:8000/v1` | URL de l'API vLLM (via tunnel SSH) |
| `VLLM_MODEL` | `Qwen/Qwen3-30B-A3B` | Modèle de réponse principal |
| `VLLM_API_KEY` | `unused` | Clé API vLLM (pas nécessaire en local) |
| `VLLM_TIMEOUT` | `10` | Timeout en secondes pour les appels vLLM |
| `FALLBACK_MODEL` | _(vide)_ | Modèle vLLM alternatif, sinon utilise Gemini |
| `RERANKER_API_BASE` | `http://localhost:8001` | URL du serveur reranker |
| `RERANKER_MODEL` | `Qwen/Qwen3-Reranker-4B` | Modèle de reranking |
| `RERANKING_ENABLED` | `true` | Activer/désactiver le reranking |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modèle d'embeddings (HuggingFace) |
| `CHUNK_SIZE` | `1200` | Taille des chunks en caractères |
| `CHUNK_OVERLAP` | `150` | Chevauchement entre chunks |
| `RETRIEVAL_TOP_K` | `12` | Nombre de chunks récupérés avant reranking |
| `FINAL_CONTEXT_K` | `5` | Nombre de chunks gardés après reranking |
| `GENERATION_TEMPERATURE` | `0.1` | Température de génération (bas = plus déterministe) |
| `GENERATION_MAX_TOKENS` | `800` | Longueur max de la réponse |
| `REQUEST_TIMEOUT` | `5` | Timeout pour les requêtes reranker |
| `GEMINI_API_KEY` | _(à remplir)_ | Clé API Google pour le fallback Gemini |

---

## 6. Installation Locale

### Prérequis

- Python 3.12+
- Git
- Accès SSH au serveur Charizard (réseau UVSQ ou VPN)

### Étapes

```bash
# 1. Cloner le projet
git clone <repo_url>
cd chatbot_M1_AMIS_2025_2026

# 2. Créer l'environnement virtuel
python -m venv .venv

# 3. Activer l'environnement
# Windows PowerShell :
.\.venv\Scripts\Activate.ps1
# Linux/Mac :
source .venv/bin/activate

# 4. Installer les dépendances
pip install -r requirements.txt

# 5. Copier et configurer .env
copy .env.example .env
# Remplir GEMINI_API_KEY dans .env

# 6. Placer les documents dans data/
# Les PDF et TXT à indexer vont dans le dossier data/

# 7. Indexer les documents
python ingest_database.py
```

---

## 7. Lancer le Projet

### Étape 1 : Indexer les Documents (première fois ou après ajout de fichiers)

```bash
# Activer l'environnement virtuel
# Windows PowerShell :
.\.venv\Scripts\Activate.ps1
# Linux/Mac :
source .venv/bin/activate

# Indexer les documents (reconstruit ChromaDB)
python ingest_database.py
```

### Étape 2 : Mode Complet (avec serveur distant)

```bash
# Terminal 1 — Ouvrir le tunnel SSH vers le serveur GPU
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 abdelkarim@charizard.prism.uvsq.fr

# Terminal 2 — Lancer le chatbot (port 8501)
python -m streamlit run chatbot.py

# Terminal 3 — Lancer le dashboard admin (port 8502)
python -m streamlit run admin_dashboard.py --server.port 8502
```

| Service | URL | Description |
|---------|-----|-------------|
| **Chatbot** | http://localhost:8501 | Interface de chat pour les étudiants |
| **Dashboard Admin** | http://localhost:8502 | Métriques, gestion KB, logs |

### Étape 2 (alt) : Mode Fallback (sans serveur distant)

Si le serveur n'est pas accessible, l'app fonctionne quand même :
- Le LLM utilise **Gemini 2.5 Flash** comme fallback automatique
- Le reranking est **désactivé** automatiquement (utilise l'ordre brut de ChromaDB)
- Les embeddings et la recherche fonctionnent normalement (tout est local)

```bash
# Terminal 1 — Lancer le chatbot
python -m streamlit run chatbot.py

# Terminal 2 — Lancer le dashboard admin
python -m streamlit run admin_dashboard.py --server.port 8502
```

### Réindexer les Documents

Si vous ajoutez ou modifiez des fichiers dans `data/` :

```bash
python ingest_database.py
```

Cela supprime l'ancien index et reconstruit entièrement ChromaDB.

> **Astuce** : Vous pouvez aussi réindexer directement depuis le dashboard admin via le bouton "🚀 Mettre à jour la base de données".

### Commande Rapide (tout-en-un)

```bash
# Depuis le dossier du projet, avec le venv activé :

# 1. Tunnel SSH (si serveur disponible)
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 abdelkarim@charizard.prism.uvsq.fr

# 2. Chatbot
python -m streamlit run chatbot.py

# 3. Dashboard (dans un autre terminal)
python -m streamlit run admin_dashboard.py --server.port 8502
```

---

## 8. Flux de Données Détaillé

### Ingestion (offline, une seule fois)

```
1. load_documents()
   └─ PyPDFDirectoryLoader  → pages PDF
   └─ DirectoryLoader(*.txt) → fichiers texte

2. build_chunks()
   └─ RecursiveCharacterTextSplitter
   └─ Séparateurs : \nArticle, \nTitre, \n##, \n\n, \n, ". ", " "
   └─ chunk_size=1200, chunk_overlap=150

3. enrich_chunk()
   └─ Ajoute : source_name, title, page (1-indexed), section, chunk_id, last_updated

4. BAAI/bge-m3 → embeddings (CPU, normalize=True)

5. ChromaDB.add_documents() → stocké dans chroma_db/
```

### Query (à chaque question utilisateur)

```
1. Utilisateur tape une question
        ↓
2. BAAI/bge-m3 encode la question en vecteur (CPU)
        ↓
3. ChromaDB.similarity_search(query, k=12)
   → Retourne les 12 chunks les plus proches
        ↓
4. is_reranker_up() → probe cache 60s
   ├─ OUI → POST /v1/rerank avec les 12 chunks
   │        → Retourne les top 5 par pertinence
   └─ NON → Garde les 5 premiers par ordre de similarité
        ↓
5. build_context(docs) → Formate les chunks numérotés avec sources
        ↓
6. Construit le prompt RAG :
   - Rôle : assistant universitaire M1 UVSQ
   - Règles : répondre uniquement depuis les extraits
   - Question de l'utilisateur
   - Historique (3 derniers échanges)
   - Extraits numérotés avec sources
        ↓
7. is_vllm_up() → probe cache 60s
   ├─ OUI → ChatOpenAI.stream(prompt) via vLLM (Qwen3-30B)
   └─ NON → Gemini 2.5 Flash en fallback
        ↓
8. Affiche la réponse en streaming + bloc "Sources consultées"
```

---

## 9. Structure des Fichiers

```
chatbot_M1_AMIS_2025_2026/
│
├── chatbot.py              # Application principale (Streamlit + RAG) — port 8501
├── admin_dashboard.py      # Dashboard administrateur (Streamlit) — port 8502
├── chat_logger.py          # Module de logging SQLite des interactions
├── dashboard_styles.py     # Styles CSS pour le dashboard admin
├── ingest_database.py      # Pipeline d'ingestion des documents
├── evaluate_chatbot.py     # Script d'évaluation automatique du chatbot
├── requirements.txt        # Dépendances Python
├── .env                    # Variables d'environnement (non versionné)
├── .env.example            # Template des variables d'environnement
├── .gitignore              # Fichiers ignorés par Git
├── README.md               # Documentation courte
├── DOCUMENTATION.md        # Cette documentation complète
│
├── data/                   # Documents source à indexer
│   ├── Réunion_de_rentrée_—_M1_AMIS,_DataScale,_IRS_et_SeCReTS.pdf
│   ├── RI GS Humanités - Sciences du patrimoine.pdf
│   ├── reglement_int.pdf
│   └── M1_Info_UVSQ_RAG_cleaned.md
│
├── chroma_db/              # Index vectoriel ChromaDB (généré, non versionné)
│
├── 1_historique.md         # Historique du projet
├── 2_glossaire.md          # Glossaire des termes
├── 3_architecture.md       # Notes d'architecture
├── 4_choix_architecture.md # Justification des choix techniques
│
├── chat_logs.db            # Logs des conversations SQLite (non versionné)
├── comands                 # Notes de commandes utiles
├── .venv/                  # Environnement virtuel Python (non versionné)
└── __pycache__/            # Cache Python (non versionné)
```

---

## 10. Plan de Rollback

Si la nouvelle stack ne fonctionne pas, voici comment revenir à l'ancien système :

### Revenir à Qwen 2.5:72b via Ollama

```bash
# 1. Sur le serveur, démarrer Ollama
ssh abdelkarim@charizard.prism.uvsq.fr
nohup ~/bin/bin/ollama serve > ~/ollama.log 2>&1 &

# 2. Vérifier que qwen2.5:72b est disponible
~/bin/bin/ollama list

# 3. Modifier .env localement
VLLM_API_BASE=http://localhost:11434/v1
VLLM_MODEL=qwen2.5:72b
RERANKING_ENABLED=false

# 4. Tunnel SSH sur le port Ollama
ssh -L 11434:localhost:11434 abdelkarim@charizard.prism.uvsq.fr

# 5. Relancer l'app
python -m streamlit run chatbot.py
```

### Fonctionner uniquement avec Gemini (sans serveur)

```bash
# Modifier .env
RERANKING_ENABLED=false
GEMINI_API_KEY=votre_clé_ici

# L'app détectera automatiquement que vLLM est down
# et utilisera Gemini comme fallback
python -m streamlit run chatbot.py
```

---

## 11. FAQ / Troubleshooting

### Le chatbot met trop de temps à répondre

**Cause** : Le serveur vLLM est inaccessible et l'app attend les timeouts.

**Solution** : Les probes de connectivité (`is_vllm_up()`, `is_reranker_up()`) cachent l'état pendant 60 secondes. Si le serveur est down, l'app bascule directement sur Gemini sans attendre. Si c'est toujours lent, vérifier :
- `REQUEST_TIMEOUT` dans `.env` (défaut: `5` secondes)
- `VLLM_TIMEOUT` dans `.env` (défaut: `10` secondes)

### SSH timed out vers Charizard

**Cause** : Vous n'êtes pas sur le réseau UVSQ.

**Solution** : Connectez-vous au VPN UVSQ d'abord, puis retentez le SSH.

### "Je n'ai pas trouvé cette information dans les documents disponibles."

**C'est normal** si la question porte sur un sujet non couvert par les PDFs dans `data/`. Le chatbot est conçu pour ne pas halluciner. Ajoutez les documents pertinents dans `data/` et relancez `python ingest_database.py`.

### Les embeddings sont lents

**Cause** : bge-m3 tourne sur CPU.

**Solution** : C'est normal pour un projet étudiant local. Le premier chargement prend ~30s, ensuite Streamlit le cache. Pour accélérer, vous pouvez changer `model_kwargs={"device": "cuda"}` dans le code si un GPU local est disponible.

### Comment ajouter de nouveaux documents ?

1. Placer les fichiers PDF ou TXT dans `data/`
2. Relancer : `python ingest_database.py`
3. Redémarrer l'app : `python -m streamlit run chatbot.py`

### Comment changer le modèle LLM ?

Modifier `VLLM_MODEL` dans `.env`. Le nouveau modèle doit être servi par vLLM sur le serveur distant.

### Comment désactiver le reranking ?

```env
RERANKING_ENABLED=false
```

L'app gardera les 5 premiers chunks par ordre de similarité cosinus au lieu de les réordonner.

---

*Documentation mise à jour le 30 mars 2026 — Projet TER M1 AMIS, UVSQ / Université Paris-Saclay*
