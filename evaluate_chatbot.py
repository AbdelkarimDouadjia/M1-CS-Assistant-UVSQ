# ================================================================
# evaluate_chatbot.py - Évaluation AVANCÉE du chatbot avec scoring HYBRIDE
# ================================================================
# Ce script :
# 1. Lit les questions d'un fichier markdown
# 2. Les pose au chatbot
# 3. Calcule des scores AVANCÉS (RAG + LLM-as-Judge)
# 4. Enregistre en JSON et CSV
# 5. Affiche les résultats
# ================================================================

import argparse
import csv
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from unanswered_detection import is_unanswered_response

load_dotenv()

# ================================================================
# CONFIGURATION
# ================================================================
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "example_collection"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")


# ================================================================
# CHARGEMENT DES MODÈLES
# ================================================================

def load_models() -> Tuple[ChatGoogleGenerativeAI, Chroma, HuggingFaceEmbeddings]:
    """
    Charge le modèle Gemini, la base ChromaDB et le même
    modèle d'embeddings Hugging Face que l'ingestion locale.
    
    Returns:
        Tuple[LLM, vector_store, embeddings]
    """
    print("⏳ Chargement des modèles...")
    
    # Modèle LLM pour générer les réponses
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2,  # Bas pour cohérence
        top_p=0.95,
    )
    
    # Important: doit matcher l'embedding utilisé dans ingest_database.py
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
    # Base de données vectorielle
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    
    print("✅ Modèles chargés avec succès")
    return llm, vector_store, embeddings_model


# ================================================================
# LECTURE DES QUESTIONS
# ================================================================

def load_questions(file_path: str = None) -> List[str]:
    """
    Lit les questions d'un fichier markdown.
    Accepte 2 formats:
    1. Simple: une question par ligne
    2. Markdown: ## Question 1
    """
    # Si pas de fichier spécifié, chercher dans les emplacements courants
    if file_path is None:
        possible_paths = [
            "question.md",
            "evaluation_chatbot/question.md",
            Path(__file__).parent / "question.md",
        ]
        for p in possible_paths:
            if Path(p).exists():
                file_path = p
                break
        
        if file_path is None:
            print("❌ Fichier question.md non trouvé")
            return []
    
    print(f"📖 Lecture des questions depuis {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    questions = []
    
    # Essayer le format markdown (## Question)
    pattern = r'##\s*.*?\n(.*?)(?=##|\Z)'
    markdown_matches = re.findall(pattern, content, re.DOTALL)
    
    if markdown_matches:
        questions = [q.strip() for q in markdown_matches if q.strip()]
    else:
        # Sinon utiliser le format simple (une ligne = une question)
        questions = [
            line.strip() 
            for line in content.strip().split('\n') 
            if line.strip() and not line.startswith('#')
        ]
    
    print(f"✅ {len(questions)} questions chargées")
    
    return questions


# ================================================================
# UTILITAIRES POUR LE SCORING
# ================================================================

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calcule la similarité cosinus entre deux vecteurs."""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


def is_unanswered(response: str) -> bool:
    """
    Détecte si le chatbot n'a pas su répondre.
    """
    # En evaluation, on traite aussi les reponses trop courtes comme non-reponses.
    return is_unanswered_response(response, min_word_count=4)


# ================================================================
# MÉTRIQUES RAG (Retrieval-Augmented Generation)
# ================================================================

def context_relevance_score(
    question: str,
    retrieved_docs: List,
    embeddings_model: HuggingFaceEmbeddings
) -> float:
    """
    Score de pertinence du contexte (0-100).
    Compare la similarité entre la question et les documents trouvés.
    """
    if not retrieved_docs:
        return 0.0
    
    try:
        # Vectoriser la question
        question_embedding = embeddings_model.embed_query(question)
        question_vec = np.array(question_embedding)
        
        # Calculer la similarité avec chaque document
        similarities = []
        doc_embeddings = embeddings_model.embed_documents(
            [doc.page_content for doc in retrieved_docs]
        )
        for doc_embedding in doc_embeddings:
            doc_vec = np.array(doc_embedding)
            sim = cosine_similarity(question_vec, doc_vec)
            similarities.append(sim)
        
        # Score = moyenne des top 3 similarités
        similarities.sort(reverse=True)
        avg_similarity = np.mean(similarities[:3]) if similarities else 0.0
        
        # Convertir [-1, 1] en [0, 100]
        score = (avg_similarity + 1) / 2 * 100
        return float(score)
    
    except Exception as e:
        print(f"⚠️ Erreur dans context_relevance_score: {e}")
        return 0.0


def context_keyword_coverage_score(response: str, retrieved_docs: List) -> float:
    """
    Score de couverture des keywords (0-100).
    Compte combien de mots-clés importants de la réponse sont dans les documents.
    """
    if not retrieved_docs or not response:
        return 0.0
    
    # Extraire les mots importants de la réponse (mots > 4 caractères)
    response_words = set(
        word.lower() for word in response.split()
        if len(word) > 4 and word.isalpha()
    )
    
    # Kombiner tous les documents
    docs_text = " ".join([doc.page_content for doc in retrieved_docs]).lower()
    
    # Compter combien de mots-clés sont présents
    if not response_words:
        return 0.0
    
    found_count = sum(1 for word in response_words if word in docs_text)
    coverage = (found_count / len(response_words)) * 100
    
    return float(coverage)


def citation_presence_score(response: str, retrieved_docs: List) -> float:
    """
    Score de présence des citations (0-100).
    Vérifie si le chatbot cite ses sources.
    """
    response_lower = response.lower()
    
    # Chercher des indicateurs de citation
    source_indicators = [
        "page",
        "section",
        "chapitre",
        "document",
        "source",
        "selon",
        "d'après",
        "extrait",
    ]
    
    has_citation = any(indicator in response_lower for indicator in source_indicators)
    
    # Score: 50 si mention de source, 20 sinon
    score = 50.0 if has_citation and retrieved_docs else 20.0
    
    return float(score)


def calculate_rag_score(
    question: str,
    response: str,
    retrieved_docs: List,
    embeddings_model: HuggingFaceEmbeddings
) -> Dict[str, float]:
    """
    Calcule les 3 métriques RAG et leur moyenne.
    Poids: pertinence (45%), couverture (35%), citations (20%)
    """
    relevance = context_relevance_score(question, retrieved_docs, embeddings_model)
    coverage = context_keyword_coverage_score(response, retrieved_docs)
    citation = citation_presence_score(response, retrieved_docs)
    
    # Score pondéré
    rag_score = (relevance * 0.45 + coverage * 0.35 + citation * 0.20)
    
    return {
        "rag_score": float(rag_score),
        "context_relevance": float(relevance),
        "keyword_coverage": float(coverage),
        "citation_presence": float(citation),
    }


# ================================================================
# ÉVALUATION PAR LLM (LLM-as-Judge)
# ================================================================

def safe_json_extract(text: str) -> Dict:
    """
    Extrait un JSON du texte LLM (gère les enveloppes markdown).
    """
    try:
        # Essayer d'extraire le JSON directement
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
    except Exception:
        pass
    
    # Fallback: retourner des valeurs par défaut
    return {
        "faithfulness": 50,
        "answer_relevance": 50,
        "completeness": 50,
    }


def llm_judge_scores(
    question: str,
    response: str,
    llm: ChatGoogleGenerativeAI
) -> Dict[str, float]:
    """
    Utilise l'LLM pour juger automatiquement la qualité de la réponse.
    Évalue: fidélité, pertinence, complétude.
    """
    prompt = f"""Tu es un évaluateur d'IA expert. Évalue cette réponse sur une échelle 0-100.

Question: {question}

Réponse: {response}

Réponds en JSON avec ces 3 critères:
{{
  "faithfulness": <Score de fidélité - la réponse respecte-t-elle la question?>,
  "answer_relevance": <Score de pertinence - la réponse est-elle pertinente?>,
  "completeness": <Score de complétude - la réponse est-elle complète?>
}}

Réponse JSON uniquement:"""
    
    try:
        result = llm.invoke(prompt)
        scores = safe_json_extract(result.content)
        
        return {
            "judge_score": float(
                scores.get("faithfulness", 50) * 0.50 +
                scores.get("answer_relevance", 50) * 0.30 +
                scores.get("completeness", 50) * 0.20
            ),
            "faithfulness": float(scores.get("faithfulness", 50)),
            "answer_relevance": float(scores.get("answer_relevance", 50)),
            "completeness": float(scores.get("completeness", 50)),
        }
    
    except Exception as e:
        print(f"⚠️ Erreur LLM Judge: {e}")
        return {
            "judge_score": 0.0,
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "completeness": 0.0,
        }


# ================================================================
# SCORING HYBRIDE (RAG + LLM)
# ================================================================

def calculate_hybrid_score(rag_scores: Dict, judge_scores: Dict, answered: bool) -> float:
    """
    Combine RAG et LLM avec pondération:
    55% RAG + 45% LLM-as-Judge
    
    Pénalité: -70% si question sans réponse
    """
    rag_score = rag_scores["rag_score"]
    judge_score = judge_scores["judge_score"]
    
    # Score hybride
    hybrid = (rag_score * 0.55) + (judge_score * 0.45)
    
    # Pénalité si pas répondu
    if not answered:
        hybrid *= 0.3  # Multiplié par 0.3 = pénalité -70%
    
    return float(hybrid)


# ================================================================
# ÉVALUATION COMPLÈTE
# ================================================================

def evaluate_question(
    question: str,
    llm: ChatGoogleGenerativeAI,
    vector_store: Chroma,
    embeddings_model: HuggingFaceEmbeddings,
) -> Dict:
    """
    Évalue une question complètement.
    """
    # 1. Récupérer les documents pertinents
    results = vector_store.similarity_search_with_score(question, k=5)
    retrieved_docs = [doc for doc, score in results]
    num_docs = len(retrieved_docs)
    
    # 2. Générer une réponse
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    prompt = f"""Utilise UNIQUEMENT les informations PROVIDED pour répondre.
Si l'info n'est pas dans les documents, dis-le clairement.

Contexte:
{context}

Question: {question}

Réponse:"""
    
    response = llm.invoke(prompt).content
    
    # 3. Déterminer si répondu
    answered = not is_unanswered(response)
    
    # 4-5. Calculer les scores.
    # Si la reponse est une non-reponse, on force tous les scores a 0
    # pour eviter de gonfler artificiellement les metriques.
    if not answered:
        rag_scores = {
            "rag_score": 0.0,
            "context_relevance": 0.0,
            "keyword_coverage": 0.0,
            "citation_presence": 0.0,
        }
        judge_scores = {
            "judge_score": 0.0,
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "completeness": 0.0,
        }
    else:
        rag_scores = calculate_rag_score(question, response, retrieved_docs, embeddings_model)
        judge_scores = llm_judge_scores(question, response, llm)
    
    # 6. Score hybride
    hybrid_score = calculate_hybrid_score(rag_scores, judge_scores, answered)
    
    # 7. Résultat complet
    return {
        "question": question,
        "response": response,
        "answered": answered,
        "num_docs": num_docs,
        "timestamp": datetime.now().isoformat(),
        
        # RAG metrics
        "rag_score": rag_scores["rag_score"],
        "context_relevance": rag_scores["context_relevance"],
        "keyword_coverage": rag_scores["keyword_coverage"],
        "citation_presence": rag_scores["citation_presence"],
        
        # LLM Judge
        "judge_score": judge_scores["judge_score"],
        "faithfulness": judge_scores["faithfulness"],
        "answer_relevance": judge_scores["answer_relevance"],
        "completeness": judge_scores["completeness"],
        
        # Hybrid
        "hybrid_score": hybrid_score,
    }


# ================================================================
# SAUVEGARDE DES RÉSULTATS
# ================================================================

def save_results_json(results: List[Dict], filename: str):
    """Sauvegarde les résultats en JSON."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ Résultats sauvegardés: {filename}")


def save_results_csv(results: List[Dict], filename: str):
    """Sauvegarde les résultats en CSV."""
    if not results:
        print("⚠️ Aucun résultat à sauvegarder")
        return
    
    keys = results[0].keys()
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"✅ CSV généré: {filename}")


# ================================================================
# AFFICHAGE DES RÉSULTATS
# ================================================================

def print_results(results: List[Dict]):
    """Affiche un résumé des résultats."""
    print("\n" + "="*80)
    print("📊 RÉSULTATS DE L'ÉVALUATION")
    print("="*80)
    
    total = len(results)
    answered = sum(1 for r in results if r["answered"])
    
    if total > 0:
        avg_hybrid = np.mean([r["hybrid_score"] for r in results])
        avg_rag = np.mean([r["rag_score"] for r in results])
        avg_judge = np.mean([r["judge_score"] for r in results])
        
        print(f"\n📈 Statistiques globales:")
        print(f"   Total questions: {total}")
        print(f"   Questions répondues: {answered}/{total} ({100*answered/total:.1f}%)")
        print(f"   Score hybride moyen: {avg_hybrid:.2f}/100")
        print(f"   Score RAG moyen: {avg_rag:.2f}/100")
        print(f"   Score Judge moyen: {avg_judge:.2f}/100")
        
        print(f"\n📋 Top 3 meilleures réponses:")
        sorted_results = sorted(results, key=lambda x: x["hybrid_score"], reverse=True)
        for i, result in enumerate(sorted_results[:3], 1):
            print(f"   {i}. {result['question'][:50]}... (Score: {result['hybrid_score']:.2f})")
        
        print(f"\n⚠️ Top 3 pires réponses:")
        for i, result in enumerate(sorted_results[-3:], 1):
            print(f"   {i}. {result['question'][:50]}... (Score: {result['hybrid_score']:.2f})")
    
    print("\n" + "="*80)


# ================================================================
# FONCTION PRINCIPALE
# ================================================================

def main():
    """Fonction principale du script d'évaluation."""
    parser = argparse.ArgumentParser(description="Evaluation avancee du chatbot")
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Fichier des questions (par defaut: recherche automatique).",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Nombre max de questions a evaluer (ex: 10).",
    )
    args = parser.parse_args()

    print("\n" + "="*80)
    print("🤖 ÉVALUATION AVANCÉE DU CHATBOT avec SCORING HYBRIDE")
    print("="*80 + "\n")
    
    # Charger les modèles
    llm, vector_store, embeddings_model = load_models()
    
    # Charger les questions
    questions = load_questions(args.input_file)
    
    if not questions:
        print("❌ Aucune question trouvée dans question.md")
        return

    if args.max_questions is not None and args.max_questions > 0:
        questions = questions[:args.max_questions]
        print(f"🎯 Mode test: {len(questions)} questions")
    
    # Évaluer chaque question
    results = []
    print(f"\n🔍 Évaluation en cours ({len(questions)} questions)...\n")
    
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Évaluation: {question[:60]}...")
        
        try:
            result = evaluate_question(question, llm, vector_store, embeddings_model)
            results.append(result)
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            continue
    
    # Sauvegarder les résultats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = f"evaluation_results_{timestamp}.json"
    csv_file = f"evaluation_results_{timestamp}.csv"
    
    save_results_json(results, json_file)
    save_results_csv(results, csv_file)
    
    # Afficher les résultats
    print_results(results)
    
    print("\n✨ Évaluation terminée!")
    print(f"📁 Fichiers générés:")
    print(f"   - {json_file}")
    print(f"   - {csv_file}\n")


if __name__ == "__main__":
    main()
