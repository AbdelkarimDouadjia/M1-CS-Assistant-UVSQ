# Installation Du Chatbot M1

Ce guide explique comment installer et lancer le projet sur Windows avec PowerShell.

Il est divise en deux parties :

1. Premiere installation apres avoir clone le projet.
2. Relancer le projet plus tard quand tout est deja installe.

## Partie 1 - Premiere Installation Apres Clonage

### 1. Cloner Le Projet

Ouvrir **PowerShell** dans le dossier ou vous voulez mettre le projet.

Exemple :

```powershell
cd "$env:USERPROFILE\Desktop"
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

Remplacer `YOUR_USERNAME` et `YOUR_REPO` par le vrai nom du compte GitHub et du depot.

Si le depot est prive, le compte GitHub utilise doit avoir acces au depot.

### 2. Creer Et Activer L'Environnement Python

Dans **PowerShell, a l'interieur du dossier du projet**, taper :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si `py -3.11` ne marche pas, essayer :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Quand l'environnement est active, PowerShell doit afficher quelque chose comme :

```text
(.venv) PS C:\...\YOUR_REPO>
```

### 3. Creer Le Vrai Fichier `.env`

Le projet lit le fichier `.env`.

Le fichier `.env.example` sert seulement de modele.

Dans **PowerShell, a l'interieur du dossier du projet**, taper :

```powershell
copy .env.example .env
notepad .env
```

Notepad va ouvrir le fichier `.env`. C'est dans ce fichier qu'il faut mettre les cles et les URLs utilisees par le chatbot.

### 4. Configuration Avec Le Serveur vLLM UVSQ

Si vous utilisez le serveur vLLM, mettre ou garder ces valeurs dans `.env` :

```env
VLLM_API_BASE=http://localhost:8000/v1
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=unused
VLLM_MODEL=Qwen/Qwen3-30B-A3B
ANSWER_MODEL=Qwen/Qwen3-30B-A3B

RERANKER_API_BASE=http://localhost:8001
RERANKER_MODEL=Qwen/Qwen3-Reranker-4B
RERANKING_ENABLED=true

GEMINI_API_KEY=
```

Important : `localhost:8000` et `localhost:8001` fonctionnent seulement si le tunnel SSH est ouvert.

### 5. Creer Ou Utiliser Une Cle SSH Pour Le Serveur

La cle SSH ne se met pas dans `.env`.

Elle est stockee sur Windows dans :

```text
C:\Users\YOUR_WINDOWS_USER\.ssh\
```

Pour creer une nouvelle cle, ouvrir **PowerShell** et taper :

```powershell
ssh-keygen -t ed25519 -C "your.email@example.com"
```

Quand PowerShell demande ou enregistrer la cle, appuyer sur **Entree** pour garder le chemin par defaut :

```text
C:\Users\YOUR_WINDOWS_USER\.ssh\id_ed25519
```

Cela cree deux fichiers :

```text
id_ed25519      = cle privee, a garder secrete
id_ed25519.pub  = cle publique, a envoyer a l'admin du serveur
```

Pour afficher la cle publique :

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub
```

Envoyer cette cle publique a l'admin du serveur pour qu'il l'ajoute au compte serveur.

Apres confirmation, tester la connexion :

```powershell
ssh YOUR_SERVER_USER@charizard.prism.uvsq.fr
```

Remplacer `YOUR_SERVER_USER` par l'utilisateur donne par l'admin du serveur.

Si la cle est dans un chemin personnalise, utiliser :

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" YOUR_SERVER_USER@charizard.prism.uvsq.fr
```

### 6. Ouvrir Le Tunnel SSH Pour vLLM

Ouvrir un nouveau terminal **PowerShell**.

Ce terminal sert uniquement au tunnel. Il faut le laisser ouvert.

Taper :

```powershell
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_SERVER_USER@charizard.prism.uvsq.fr
```

Si la cle SSH a un chemin personnalise :

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_SERVER_USER@charizard.prism.uvsq.fr
```

Apres la connexion, ne pas fermer ce terminal.

Ouvrir un autre terminal **PowerShell** et tester :

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/models
Invoke-WebRequest http://127.0.0.1:8001/health
```

Si ces deux commandes echouent, le chatbot peut s'ouvrir, mais la partie vLLM/reranker ne fonctionnera pas.

### 7. Configuration Sans Serveur vLLM

Si vous n'avez pas acces au serveur SSH, utiliser Gemini comme solution de repli.

Ouvrir `.env` :

```powershell
notepad .env
```

Mettre la cle Gemini ici :

```env
GEMINI_API_KEY=PASTE_THE_GEMINI_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash
RERANKING_ENABLED=false
```

La cle Gemini doit rester uniquement dans le fichier `.env` local.

### 8. Construire La Base RAG

Le projet utilise les documents du dossier `data/`, mais la base vectorielle `chroma_db/` doit etre construite localement.

Dans **PowerShell, a l'interieur du dossier du projet**, avec `.venv` active :

```powershell
python -m chatbot_core.ingest_database
```

Cette commande cree ou met a jour `chroma_db/`.

Si cette etape echoue, le chatbot peut s'ouvrir, mais la recherche documentaire ne fonctionnera pas correctement.

### 9. Lancer Le Chatbot

Ouvrir **PowerShell dans le dossier du projet**.

Activer l'environnement :

```powershell
.\.venv\Scripts\Activate.ps1
```

Lancer le chatbot :

```powershell
python -m streamlit run app/chatbot.py
```

Ouvrir ensuite :

```text
http://localhost:8501
```

### 10. Lancer Le Dashboard Admin

Ouvrir un autre **PowerShell dans le dossier du projet**.

Activer l'environnement :

```powershell
.\.venv\Scripts\Activate.ps1
```

Lancer le dashboard :

```powershell
python -m streamlit run app/admin_dashboard.py --server.port 8502
```

Ouvrir ensuite :

```text
http://localhost:8502
```

## Partie 2 - Relancer Le Projet Plus Tard

Utiliser cette partie si le projet est deja clone, les dependances sont deja installees, `.env` existe deja et `chroma_db/` a deja ete cree.

### Cas A - Relancer Avec Le Serveur vLLM

Il faut trois terminaux.

### Terminal 1 : Tunnel SSH

Ouvrir **PowerShell**.

Taper :

```powershell
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_SERVER_USER@charizard.prism.uvsq.fr
```

Laisser ce terminal ouvert.

Test optionnel dans un autre terminal :

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/models
Invoke-WebRequest http://127.0.0.1:8001/health
```

### Terminal 2 : Chatbot

Ouvrir **PowerShell dans le dossier du projet**.

Taper :

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/chatbot.py
```

Ouvrir :

```text
http://localhost:8501
```

### Terminal 3 : Dashboard Admin

Ouvrir **PowerShell dans le dossier du projet**.

Taper :

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/admin_dashboard.py --server.port 8502
```

Ouvrir :

```text
http://localhost:8502
```

### Cas B - Relancer Avec Gemini Seulement

Le tunnel SSH n'est pas necessaire.

Verifier que `.env` contient :

```env
GEMINI_API_KEY=PASTE_THE_GEMINI_KEY_HERE
RERANKING_ENABLED=false
```

Ouvrir **PowerShell dans le dossier du projet** :

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/chatbot.py
```

Ouvrir :

```text
http://localhost:8501
```

## Depannage Rapide

### PowerShell Dit Que Les Scripts Sont Desactives

Ouvrir PowerShell comme utilisateur normal et taper :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Puis reactiver l'environnement :

```powershell
.\.venv\Scripts\Activate.ps1
```

### Erreur `ModuleNotFoundError`

Vous n'etes probablement pas dans l'environnement virtuel.

Dans **PowerShell, a l'interieur du dossier du projet**, taper :

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Le Chatbot Dit Que Le LLM N'est Pas Disponible

Avec vLLM, verifier :

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/models
```

Avec Gemini, verifier que `.env` contient :

```env
GEMINI_API_KEY=PASTE_THE_GEMINI_KEY_HERE
```

### La Recherche Documentaire Ne Marche Pas

Reconstruire la base RAG :

```powershell
python -m chatbot_core.ingest_database
```

### Les Changements De `.env` Ne Sont Pas Pris En Compte

Arreter Streamlit avec `Ctrl + C`, puis relancer :

```powershell
python -m streamlit run app/chatbot.py
```
