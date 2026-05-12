# ================================================================
# 🎯 ÉVALUATION DU CHATBOT (SCORING AVANCÉ + HYBRIDE)
# ================================================================

# LANCER L'ÉVALUATION COMPLÈTE:
python -m tools.evaluate_chatbot

# Cela va:
#   1. Lire toutes les questions du fichier question.md
#   2. Les poser au chatbot successivement
#   3. Récupérer les documents de ChromaDB
#   4. Calculer les scores AVANCÉS pour chaque réponse:
#      ├─ RAG metrics (45%): Pertinence contexte, couverture keywords, citations
#      ├─ LLM Judge (45%): Fidélité, pertinence, complétude
#      └─ Score Hybride (55% RAG + 45% Judge)
#   5. Sauvegarder les résultats en JSON et CSV
#   6. Afficher un résumé aux statistiques

# Format des résultats générés:
#   - evaluation_results_YYYYMMDD_HHMMSS.json (données brutes)
#   - evaluation_results_YYYYMMDD_HHMMSS.csv  (pour Excel)


# ================================================================
# 📊 COMPRENDRE LES SCORES
# ================================================================

# MÉTRIQUES RAG (Qualité de la recherche documentaire):
#   • context_relevance (0-100): Similarité question/documents trouvés
#   • keyword_coverage (0-100): % de mots-clés importants trouvés dans les docs
#   • citation_presence (0-100): Est-ce que le chatbot cite ses sources?
#   → Score RAG = 45% relevance + 35% coverage + 20% citation

# ÉVALUATION LLM-as-Judge (Qualité de la réponse):
#   • faithfulness (0-100): La réponse respecte-t-elle la question?
#   • answer_relevance (0-100): Pertinence de la réponse?
#   • completeness (0-100): Complétude et clarté?
#   → Score Judge = 50% faithfulness + 30% relevance + 20% completeness

# SCORE HYBRIDE FINAL:
#   → 55% Score RAG + 45% Score Judge = Score 0-100
#   → Pénalité -70% si question sans réponse


# ================================================================
# 📈 ANALYSER LES RÉSULTATS
# ================================================================

# 1. Voir le résumé affiché dans le terminal (top 3 / bottom 3)
# 2. Ouvrir evaluation_results_*.json pour voir TOUS les détails
# 3. Ouvrir evaluation_results_*.csv dans Excel pour faire des graphiques
# 4. Chercher les questions avec score < 50 pour améliorer le chatbot


# ================================================================
# 🔧 AMÉLIORATIONS POSSIBLES SI SCORES FAIBLES
# ================================================================

# Si RAG scores faibles:
#   → Ajouter plus de documents dans data/
#   → Améliorer la qualité des documents existants
#   → Changer la stratégie de découpe des chunks

# Si Judge scores faibles:
#   → Améliorer les prompts du chatbot
#   → Ajuster les paramètres du modèle (température, top_p)
#   → Vérifier que le contexte est assez pertinent

# Si Score Hybride bas:
#   → Vérifier que ChromaDB est bien rempli
#   → Relancer chatbot_core/ingest_database.py pour mettre à jour les embeddings
#   → Tester avec moins de questions d'abord pour déboguer








