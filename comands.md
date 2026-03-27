# ================================================================
# COMMANDES PRINCIPALES
# ================================================================

# 1. Lancer le chatbot interactif (Streamlit)
python -m streamlit run chatbot.py

# 2. Lancer le dashboard d'administration
python -m streamlit run admin_dashboard.py

# 3. Réingérer les documents dans ChromaDB
python ingest_database.py


# LANCER L'ÉVALUATION COMPLÈTE:
python evaluate_chatbot.py
python evaluate_chatbot.py --max-questions 10












