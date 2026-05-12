# COMMANDES A FAIRE (ordre exact)

Ce fichier est le mode d'emploi rapide pour lancer le projet en mode complet
(chatbot local + vLLM sur le serveur).

Remplace TON_USER par ton compte serveur (exemple: abderraouf).

## 1) Local Windows - preparation (une seule fois)

```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
copy .env.example .env
python -m chatbot_core.ingest_database
```

## 2) Serveur - lancer vLLM (mode stable)

Connexion SSH:

```bash
ssh TON_USER@charizard.prism.uvsq.fr
```

Dans le serveur (si venv vllm deja cree):

```bash
source ~/venvs/vllm/bin/activate
pkill -f "vllm serve" || true
pkill -f "python.*vllm" || true
sleep 2
nvidia-smi
```

### Terminal serveur A - modele de reponse (GPU 0, port 8000)

```bash
source ~/venvs/vllm/bin/activate
export CUDA_VISIBLE_DEVICES=0
vllm serve Qwen/Qwen3-30B-A3B \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --generation-config vllm
```

### Terminal serveur B - reranker (GPU 1, port 8001)

```bash
source ~/venvs/vllm/bin/activate
export CUDA_VISIBLE_DEVICES=1
vllm serve Qwen/Qwen3-Reranker-4B \
  --host 0.0.0.0 \
  --port 8001 \
  --tensor-parallel-size 1 \
  --runner pooling \
  --hf_overrides '{"architectures":["Qwen3ForSequenceClassification"],"classifier_from_token":["no","yes"],"is_original_qwen3_reranker":true}' \
  --chat-template examples/pooling/score/template/qwen3_reranker.jinja
```

Verification sur le serveur:

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8001/health
```

## 3) Local Windows - ouvrir le tunnel SSH

Dans un terminal local dedie (laisser ouvert):

```powershell
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 TON_USER@charizard.prism.uvsq.fr
```

Verification locale:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/models
Invoke-WebRequest http://127.0.0.1:8001/health
```

## 4) Local Windows - lancer les apps

Terminal local 1:

```powershell
& ".\.venv\Scripts\Activate.ps1"
python -m streamlit run app/chatbot.py
```

Terminal local 2:

```powershell
& ".\.venv\Scripts\Activate.ps1"
python -m streamlit run app/admin_dashboard.py --server.port 8502
```

## 5) URLs

- Chatbot: http://localhost:8501
- Dashboard admin: http://localhost:8502

## 6) Si erreur CUDA revient

```bash
nvidia-smi
pkill -f "vllm serve" || true
```

Puis relancer Terminal A et Terminal B.




# LANCER L'EVALUATION COMPLETE:
python -m tools.evaluate_chatbot
python -m tools.evaluate_chatbot --max-questions 10
