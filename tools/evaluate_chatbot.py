# ================================================================
# evaluate_chatbot.py - Evaluation avancee du chatbot (pipeline chatbot)
# ================================================================
# Cette version conserve:
# - le meme pipeline de reponse que chatbot.py (retrieval + rerank + Gemini/vLLM fallback)
# - les memes familles de scores qu'avant simplification:
#   rag_score, judge_score, hybrid_score
# ================================================================

import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import requests
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from chatbot_core.unanswered_detection import is_unanswered_response
from chatbot_core.llm_backends import build_all_openai_compat_chat_list, generation_llm_order
from chatbot_core.reranking import rerank_documents

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation_chatbot"

load_dotenv(PROJECT_ROOT / ".env")


# ================================================================
# CONFIGURATION (alignee avec chatbot.py)
# ================================================================
# Les variables .env gardent les memes noms que chatbot.py pour
# garantir le meme comportement entre chat en ligne et evaluation.
CHROMA_PATH = str(PROJECT_ROOT / "chroma_db")
COLLECTION_NAME = "example_collection"

VLLM_API_BASE = os.getenv("VLLM_BASE_URL") or os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("ANSWER_MODEL") or os.getenv("VLLM_MODEL", "Qwen/Qwen3-30B-A3B")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "").strip()
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "unused")

RERANKER_API_BASE = os.getenv("RERANKER_API_BASE", "http://localhost:8001")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B")
RERANKING_ENABLED = os.getenv("RERANKING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
LOCAL_RERANKER_ENABLED = os.getenv("LOCAL_RERANKER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
LOCAL_RERANKER_MODEL = os.getenv("LOCAL_RERANKER_MODEL", "BAAI/bge-reranker-base")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "12"))
FINAL_CONTEXT_K = int(os.getenv("FINAL_CONTEXT_K", os.getenv("RERANKER_TOP_K", "5")))
GENERATION_TEMPERATURE = float(os.getenv("GENERATION_TEMPERATURE", "0.1"))
GENERATION_MAX_TOKENS = int(os.getenv("GENERATION_MAX_TOKENS", "800"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "10"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ================================================================
# OUTILS REUTILISES DU CHATBOT
# ================================================================

def _probe(url: str, timeout: int = 3) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.RequestException:
        return False


def is_vllm_up() -> bool:
    return _probe(f"{VLLM_API_BASE}/models")


def is_reranker_up() -> bool:
    return _probe(f"{RERANKER_API_BASE}/health")


def build_vllm_chat(model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=VLLM_API_BASE,
        api_key=VLLM_API_KEY,
        model=model_name,
        temperature=GENERATION_TEMPERATURE,
        max_tokens=GENERATION_MAX_TOKENS,
        request_timeout=VLLM_TIMEOUT,
    )


def build_gemini_chat() -> Any:
    if os.getenv("GEMINI_API_KEY"):
        return ChatGoogleGenerativeAI(
            temperature=GENERATION_TEMPERATURE,
            model=GEMINI_MODEL,
        )
    return None


def build_server_backup_llms() -> List[Any]:
    backups: List[Any] = [build_vllm_chat(VLLM_MODEL)]
    if FALLBACK_MODEL and FALLBACK_MODEL != VLLM_MODEL:
        backups.append(build_vllm_chat(FALLBACK_MODEL))
    return backups


def extract_source_name(source: str) -> str:
    if not source:
        return "Unknown"
    return Path(source).name


def format_source(doc) -> str:
    source_name = doc.metadata.get("source_name") or extract_source_name(doc.metadata.get("source", "Unknown"))
    page = doc.metadata.get("page")
    section = doc.metadata.get("section")
    parts = [source_name]
    if page not in (None, "", "N/A"):
        parts.append(f"p. {page}")
    if section:
        parts.append(section)
    return ", ".join(parts)


def build_context(docs) -> str:
    knowledge_parts = []
    for index, doc in enumerate(docs, 1):
        knowledge_parts.append(f"[Source {index}: {format_source(doc)}]\n{doc.page_content}")
    return "\n\n---\n\n".join(knowledge_parts)


def build_sources_block(docs) -> str:
    seen = set()
    lines = []
    for doc in docs:
        label = format_source(doc)
        if label not in seen:
            seen.add(label)
            lines.append(f"- {label}")
    return "\n".join(lines)


def rerank(query: str, docs, top_k: int = FINAL_CONTEXT_K):
    return rerank_documents(
        query,
        docs,
        top_k=top_k,
        enabled=RERANKING_ENABLED,
        server_base=RERANKER_API_BASE,
        server_model=RERANKER_MODEL,
        request_timeout=REQUEST_TIMEOUT,
        server_available=is_reranker_up,
        local_enabled=LOCAL_RERANKER_ENABLED,
        local_model=LOCAL_RERANKER_MODEL,
    )


def is_unanswered(response: str) -> bool:
    # On garde la meme detection que la version precedente du script.
    return is_unanswered_response(response, min_word_count=0)


def get_judge_llm(primary_llm: Any, openai_compat_llms: Any, fallback_llm: Any) -> Any:
    order = generation_llm_order(
        vllm_reachable=is_vllm_up(),
        vllm_llm=primary_llm,
        openai_compat_llms=openai_compat_llms,
        tertiary_llm=fallback_llm,
    )
    return order[0] if order else primary_llm


def build_chatbot_prompt(question: str, docs) -> str:
    knowledge = build_context(docs)
    history = "Aucun historique utile."
    return f"""
Tu es un assistant universitaire pour les etudiants du M1 Informatique UVSQ / Universite Paris-Saclay.
Regles :
- Reponds uniquement a partir des extraits fournis.
- Si l'information n'apparait pas dans les extraits, reponds exactement : "Je n'ai pas trouve cette information dans les documents disponibles."
- Si plusieurs extraits se contredisent, signale l'incertitude et cite les sources concernees.
- Reponds en francais, sauf si l'utilisateur ecrit clairement dans une autre langue.
- Reste concis, fiable et utile.
- Cite les sources dans la reponse sous la forme [nom_fichier, p. X] quand elles sont disponibles.

Question :
{question}

Historique utile :
{history}

Extraits :
{knowledge}
    """.strip()


def generate_chatbot_response(
    question: str,
    docs,
    primary_llm: Any,
    openai_compat_llms: Any,
    fallback_llm: Any,
) -> str:
    rag_prompt = build_chatbot_prompt(question, docs)
    default_response = "Je n'ai pas trouve cette information dans les documents disponibles."

    final_response = "Aucun service de génération n'est disponible pour le moment."
    for chat in generation_llm_order(
        vllm_reachable=is_vllm_up(),
        vllm_llm=primary_llm,
        openai_compat_llms=openai_compat_llms,
        tertiary_llm=fallback_llm,
    ):
        try:
            response = chat.invoke(rag_prompt).content
            final_response = response.strip() or default_response
            break
        except Exception:
            continue

    sources_block = build_sources_block(docs)
    if sources_block:
        final_response = f"{final_response}\n\nSources consultees :\n{sources_block}"

    return final_response


# ================================================================
# CHARGEMENT DES MODELES
# ================================================================

def load_models() -> Tuple[Any, Any, Any, Any, HuggingFaceEmbeddings]:
    print("Chargement des modeles (pipeline chatbot)...")

    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    server_backup_llms = build_server_backup_llms()
    openai_compat_llms = build_all_openai_compat_chat_list(
        temperature=GENERATION_TEMPERATURE,
        max_tokens=GENERATION_MAX_TOKENS,
    )
    fallback_llm = build_gemini_chat()

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVAL_TOP_K})

    print("Modeles chatbot charges avec succes")
    return server_backup_llms[0], [*openai_compat_llms, *server_backup_llms[1:]], fallback_llm, retriever, embeddings_model


# ================================================================
# LECTURE DES QUESTIONS
# ================================================================

def load_questions(file_path: str = None) -> List[str]:
    if file_path is None:
        possible_paths = [
            EVALUATION_DIR / "question.md",
            PROJECT_ROOT / "question.md",
            Path(__file__).parent / "question.md",
        ]
        for p in possible_paths:
            if Path(p).exists():
                file_path = p
                break

        if file_path is None:
            print("Fichier question.md non trouve")
            return []

    print(f"Lecture des questions depuis {file_path}...")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"##\s*.*?\n(.*?)(?=##|\Z)"
    markdown_matches = re.findall(pattern, content, re.DOTALL)

    if markdown_matches:
        questions = [q.strip() for q in markdown_matches if q.strip()]
    else:
        questions = [
            line.strip()
            for line in content.strip().split("\n")
            if line.strip() and not line.startswith("#")
        ]

    print(f"{len(questions)} questions chargees")
    return questions


# ================================================================
# SCORING (meme formule que la version precedente)
# ================================================================

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def context_relevance_score(
    question: str,
    retrieved_docs: List,
    embeddings_model: HuggingFaceEmbeddings,
) -> float:
    if not retrieved_docs:
        return 0.0

    try:
        question_embedding = embeddings_model.embed_query(question)
        question_vec = np.array(question_embedding)

        similarities = []
        doc_embeddings = embeddings_model.embed_documents([doc.page_content for doc in retrieved_docs])
        for doc_embedding in doc_embeddings:
            doc_vec = np.array(doc_embedding)
            similarities.append(cosine_similarity(question_vec, doc_vec))

        similarities.sort(reverse=True)
        avg_similarity = np.mean(similarities[:3]) if similarities else 0.0
        return float((avg_similarity + 1) / 2 * 100)

    except Exception as e:
        print(f"Erreur context_relevance_score: {e}")
        return 0.0


def context_keyword_coverage_score(response: str, retrieved_docs: List) -> float:
    if not retrieved_docs or not response:
        return 0.0

    response_words = set(
        word.lower()
        for word in response.split()
        if len(word) > 3 and word.isalpha()
    )

    docs_text = " ".join([doc.page_content for doc in retrieved_docs]).lower()

    if not response_words:
        return 0.0

    found_count = sum(1 for word in response_words if word in docs_text)
    return float((found_count / len(response_words)) * 100)


def citation_presence_score(response: str, retrieved_docs: List) -> float:
    response_lower = response.lower()

    source_indicators = [
        "page",
        "section",
        "chapitre",
        "document",
        "source",
        "selon",
        "d'apres",
        "extrait",
        "sources consultees",
        "p.",
    ]

    has_citation = any(indicator in response_lower for indicator in source_indicators)
    return float(50.0 if has_citation and retrieved_docs else 20.0)


def calculate_rag_score(
    question: str,
    response: str,
    retrieved_docs: List,
    embeddings_model: HuggingFaceEmbeddings,
) -> Dict[str, float]:
    relevance = context_relevance_score(question, retrieved_docs, embeddings_model)
    coverage = context_keyword_coverage_score(response, retrieved_docs)
    citation = citation_presence_score(response, retrieved_docs)

    rag_score = (relevance * 0.45) + (coverage * 0.35) + (citation * 0.20)

    return {
        "rag_score": float(rag_score),
        "context_relevance": float(relevance),
        "keyword_coverage": float(coverage),
        "citation_presence": float(citation),
    }


def safe_json_extract(text: str) -> Dict:
    try:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass

    return {
        "faithfulness": 50,
        "answer_relevance": 50,
        "completeness": 50,
    }


def llm_judge_scores(question: str, response: str, llm_judge: Any) -> Dict[str, float]:
    prompt = f"""Tu es un evaluateur d'IA expert. Evalue cette reponse sur une echelle 0-100.

La reponse est satisfaisante si elle repond clairement a la question,
sans ambiguite majeure ni doute non resolu. Si la question n'est pas
reellement traitee, les scores doivent etre bas.

Question: {question}

Reponse: {response}

Reponds en JSON avec ces 3 criteres:
{{
    "faithfulness": <Score de fidelite - la reponse respecte-t-elle fidelement la question et les faits?>,
    "answer_relevance": <Score de pertinence - la reponse repond-elle vraiment a la question posee?>,
    "completeness": <Score de completude - la reponse est-elle complete, claire, sans doute important, et non inachevee?>
}}

Reponse JSON uniquement:"""

    try:
        result = llm_judge.invoke(prompt)
        scores = safe_json_extract(result.content)

        return {
            "judge_score": float(
                scores.get("faithfulness", 50) * 0.50
                + scores.get("answer_relevance", 50) * 0.30
                + scores.get("completeness", 50) * 0.20
            ),
            "faithfulness": float(scores.get("faithfulness", 50)),
            "answer_relevance": float(scores.get("answer_relevance", 50)),
            "completeness": float(scores.get("completeness", 50)),
        }
    except Exception as e:
        print(f"Erreur LLM Judge: {e}")
        return {
            "judge_score": 0.0,
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "completeness": 0.0,
        }


def calculate_hybrid_score(rag_scores: Dict, judge_scores: Dict, answered: bool) -> float:
    rag_score = rag_scores["rag_score"]
    judge_score = judge_scores["judge_score"]

    hybrid = (rag_score * 0.55) + (judge_score * 0.45)
    if not answered:
        hybrid *= 0.3
    return float(hybrid)


# ================================================================
# EVALUATION COMPLETE
# ================================================================

def evaluate_question(
    question: str,
    primary_llm: Any,
    openai_compat_llms: Any,
    fallback_llm: Any,
    retriever: Any,
    embeddings_model: HuggingFaceEmbeddings,
) -> Dict:
    # 1) Retrieval + rerank du contexte
    raw_docs = retriever.invoke(question)
    retrieved_docs = rerank(question, raw_docs)
    num_docs = len(retrieved_docs)

    # 2) Generation de reponse avec le meme prompt que le chatbot
    response = generate_chatbot_response(
        question, retrieved_docs, primary_llm, openai_compat_llms, fallback_llm
    )

    # 3) Detection repondu / non repondu
    answered = not is_unanswered(response)

    # 4) Scoring detaille puis score hybride final
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
        judge_llm = get_judge_llm(primary_llm, openai_compat_llms, fallback_llm)
        judge_scores = llm_judge_scores(question, response, judge_llm)

    hybrid_score = calculate_hybrid_score(rag_scores, judge_scores, answered)

    return {
        "question": question,
        "response": response,
        "answered": answered,
        "num_docs": num_docs,
        "timestamp": datetime.now().isoformat(),
        "rag_score": rag_scores["rag_score"],
        "context_relevance": rag_scores["context_relevance"],
        "keyword_coverage": rag_scores["keyword_coverage"],
        "citation_presence": rag_scores["citation_presence"],
        "judge_score": judge_scores["judge_score"],
        "faithfulness": judge_scores["faithfulness"],
        "answer_relevance": judge_scores["answer_relevance"],
        "completeness": judge_scores["completeness"],
        "hybrid_score": hybrid_score,
    }


# ================================================================
# I/O + MAIN
# ================================================================

def save_results_json(results: List[Dict], filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Resultats sauvegardes: {filename}")


def save_results_csv(results: List[Dict], filename: str):
    if not results:
        print("Aucun resultat a sauvegarder")
        return

    keys = results[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"CSV genere: {filename}")


def print_results(results: List[Dict]):
    print("\n" + "=" * 80)
    print("RESULTATS DE L'EVALUATION")
    print("=" * 80)

    total = len(results)
    answered = sum(1 for r in results if r["answered"])

    if total > 0:
        avg_hybrid = np.mean([r["hybrid_score"] for r in results])
        avg_rag = np.mean([r["rag_score"] for r in results])
        avg_judge = np.mean([r["judge_score"] for r in results])

        print("\nStatistiques globales:")
        print(f"   Total questions: {total}")
        print(f"   Questions repondues: {answered}/{total} ({100 * answered / total:.1f}%)")
        print(f"   Score hybride moyen: {avg_hybrid:.2f}/100")
        print(f"   Score RAG moyen: {avg_rag:.2f}/100")
        print(f"   Score Judge moyen: {avg_judge:.2f}/100")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Evaluation avancee du chatbot (pipeline identique a chatbot.py)")
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

    print("\n" + "=" * 80)
    print("EVALUATION AVANCEE DU CHATBOT (meme scoring qu'avant)")
    print("=" * 80 + "\n")

    # Chargement runtime (LLM + retriever) puis questions d'evaluation.
    primary_llm, openai_compat_llms, fallback_llm, retriever, embeddings_model = load_models()
    questions = load_questions(args.input_file)

    if not questions:
        print("Aucune question trouvee dans question.md")
        return

    if args.max_questions is not None and args.max_questions > 0:
        questions = questions[: args.max_questions]
        print(f"Mode test: {len(questions)} questions")

    results = []
    print(f"\nEvaluation en cours ({len(questions)} questions)...\n")

    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Evaluation: {question[:60]}...")
        try:
            result = evaluate_question(
                question,
                primary_llm,
                openai_compat_llms,
                fallback_llm,
                retriever,
                embeddings_model,
            )
            results.append(result)
        except Exception as e:
            print(f"   Erreur: {e}")
            continue

    # Le dashboard admin detecte automatiquement les rapports JSON produits ici.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    EVALUATION_DIR.mkdir(exist_ok=True)
    json_file = EVALUATION_DIR / f"evaluation_results_{timestamp}.json"
    csv_file = EVALUATION_DIR / f"evaluation_results_{timestamp}.csv"

    save_results_json(results, json_file)
    save_results_csv(results, csv_file)
    print_results(results)

    print("\nEvaluation terminee")
    print("Fichiers generes:")
    print(f"   - {json_file}")
    print(f"   - {csv_file}\n")


if __name__ == "__main__":
    main()
