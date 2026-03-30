import os
import time
from pathlib import Path
from uuid import uuid4

import requests
import streamlit as st
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from chat_logger import log_question

load_dotenv()

# --- Configuration de la page Streamlit ---
st.set_page_config(
    page_title="RAG Chatbot",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Style CSS personnalisé ---
st.markdown("""
    <style>
    .main { padding-top: 0; }
    .stChatMessage { background-color: #f0f2f6; border-radius: 10px; padding: 15px; }
    </style>
    """, unsafe_allow_html=True)


# configuration
CHROMA_PATH = r"chroma_db"
VLLM_API_BASE = os.getenv("VLLM_BASE_URL") or os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("ANSWER_MODEL") or os.getenv("VLLM_MODEL", "Qwen/Qwen3-30B-A3B")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "").strip()
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "unused")
RERANKER_API_BASE = os.getenv("RERANKER_API_BASE", "http://localhost:8001")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "12"))
FINAL_CONTEXT_K = int(os.getenv("FINAL_CONTEXT_K", os.getenv("RERANKER_TOP_K", "5")))
GENERATION_TEMPERATURE = float(os.getenv("GENERATION_TEMPERATURE", "0.1"))
GENERATION_MAX_TOKENS = int(os.getenv("GENERATION_MAX_TOKENS", "800"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "10"))
RERANKING_ENABLED = os.getenv("RERANKING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def _probe(url: str, timeout: int = 3) -> bool:
    """Fast check: is a server reachable?"""
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.RequestException:
        return False


def is_vllm_up() -> bool:
    if "_vllm_up" not in st.session_state or (time.time() - st.session_state.get("_vllm_ts", 0) > 60):
        st.session_state._vllm_up = _probe(f"{VLLM_API_BASE}/models")
        st.session_state._vllm_ts = time.time()
    return st.session_state._vllm_up


def is_reranker_up() -> bool:
    if "_rr_up" not in st.session_state or (time.time() - st.session_state.get("_rr_ts", 0) > 60):
        st.session_state._rr_up = _probe(f"{RERANKER_API_BASE}/health")
        st.session_state._rr_ts = time.time()
    return st.session_state._rr_up

# ================================================================
# INITIALISATION DE LA SESSION
# ================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "questions" not in st.session_state:
    st.session_state.questions = []
if "responces" not in st.session_state:
    st.session_state.responces = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())


def build_vllm_chat(model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=VLLM_API_BASE,
        api_key=VLLM_API_KEY,
        model=model_name,
        temperature=GENERATION_TEMPERATURE,
        max_tokens=GENERATION_MAX_TOKENS,
        request_timeout=VLLM_TIMEOUT,
    )


def build_fallback_chat():
    if FALLBACK_MODEL:
        return build_vllm_chat(FALLBACK_MODEL)
    if os.getenv("GEMINI_API_KEY"):
        return ChatGoogleGenerativeAI(
            temperature=GENERATION_TEMPERATURE,
            model="gemini-2.5-flash",
        )
    return None


# ================================================================
# CHARGEMENT DES MODÈLES IA
# ================================================================
@st.cache_resource
def load_models():
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    llm = build_vllm_chat(VLLM_MODEL)
    llm_fallback = build_fallback_chat()
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVAL_TOP_K})
    return llm, llm_fallback, retriever


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
    if not docs:
        return docs
    if not RERANKING_ENABLED or not is_reranker_up():
        return docs[:top_k]
    documents = [doc.page_content for doc in docs]
    endpoints = [
        (
            f"{RERANKER_API_BASE}/v1/rerank",
            {
                "model": RERANKER_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_k, len(documents)),
            },
        ),
        (
            f"{RERANKER_API_BASE}/rerank",
            {
                "model": RERANKER_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_k, len(documents)),
            },
        ),
        (
            f"{RERANKER_API_BASE}/score",
            {
                "model": RERANKER_MODEL,
                "queries": [query] * len(documents),
                "documents": documents,
            },
        ),
    ]
    for endpoint, payload in endpoints:
        try:
            resp = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            body = resp.json()
            if "results" in body:
                ranked_docs = []
                for item in body["results"][:top_k]:
                    ranked_docs.append(docs[item["index"]])
                if ranked_docs:
                    return ranked_docs
            if "data" in body:
                scores = [item.get("score", item.get("relevance_score", 0.0)) for item in body["data"]]
                if len(scores) == len(docs):
                    ranked = sorted(zip(scores, docs), key=lambda pair: pair[0], reverse=True)
                    return [doc for _, doc in ranked[:top_k]]
        except requests.RequestException:
            continue
        except (KeyError, TypeError, ValueError):
            continue
    return docs[:top_k]


llm, llm_fallback, retriever = load_models()

# ================================================================
# INTERFACE UTILISATEUR (UI)
# ================================================================
st.title("💬 RAG Chatbot")
st.markdown("*Ask anything - I'll answer based on the knowledge base*")

# --- Afficher l'historique des messages ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# --- Zone de saisie du chat ---
if user_input := st.chat_input("Type your question here..."):

    # Étape 1 : Ajouter la question de l'utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Étape 2 : Afficher la question dans l'interface
    with st.chat_message("user"):
        st.write(user_input)
    
    st.session_state.questions.append(user_input)
    

    # Retrieve and rerank
    docs = rerank(user_input, retriever.invoke(user_input))
    sources_block = build_sources_block(docs)
    previous_questions = st.session_state.questions[:-1][-3:]
    previous_answers = st.session_state.responces[-3:]
    history_pairs = zip(previous_questions, previous_answers)
    history = "\n\n".join(
        f"Question: {question}\nRéponse: {answer}"
        for question, answer in history_pairs
    ) or "Aucun historique utile."
    knowledge = build_context(docs)

    rag_prompt = f"""
Tu es un assistant universitaire pour les étudiants du M1 Informatique UVSQ / Université Paris-Saclay.
Règles :
- Réponds uniquement à partir des extraits fournis.
- Si l'information n'apparaît pas dans les extraits, réponds exactement : "Je n'ai pas trouvé cette information dans les documents disponibles."
- Si plusieurs extraits se contredisent, signale l'incertitude et cite les sources concernées.
- Réponds en français, sauf si l'utilisateur écrit clairement dans une autre langue.
- Reste concis, fiable et utile.
- Cite les sources dans la réponse sous la forme [nom_fichier, p. X] quand elles sont disponibles.

Question :
{user_input}

Historique utile :
{history}

Extraits :
{knowledge}
    """.strip()
    
    # Display assistant response with streaming
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = ""
        final_response = "Je n'ai pas trouvé cette information dans les documents disponibles."

        if docs:
            active_llm = llm if is_vllm_up() else llm_fallback
            if active_llm is None:
                active_llm = llm  # try anyway
            try:
                for chunk in active_llm.stream(rag_prompt):
                    response += chunk.content
                    placeholder.write(response)
                final_response = response.strip() or final_response
            except Exception:
                if active_llm is llm and llm_fallback is not None:
                    response = ""
                    for chunk in llm_fallback.stream(rag_prompt):
                        response += chunk.content
                        placeholder.write(response)
                    final_response = response.strip() or final_response
                else:
                    final_response = "Le serveur vLLM n'est pas disponible pour le moment."

        if sources_block:
            final_response = f"{final_response}\n\nSources consultees :\n{sources_block}"
        placeholder.write(final_response)
    
    st.session_state.responces.append(final_response)

    # ============================================================
    # DÉTECTION - Le chatbot a-t-il pu répondre ?
    # ============================================================
    unanswered_keywords = [
        # Français
        "je ne sais pas", "je n'ai pas", "pas d'information",
        "ne contient pas", "ne précise pas", "ne précisent pas",
        "ne mentionne pas", "ne mentionnent pas",
        "pas trouvé", "aucune information", "je ne trouve pas",
        "ne contient aucune", "ne contiennent pas",
        "ne permet pas de répondre", "ne fournit pas",
        "ne fournissent pas", "pas mentionné",
        "n'est pas présente dans les documents fournis",
        "Les informations fournies ne précisent pas",
        "n'est pas fournie dans les documents",
        "désolé", "je ne peux pas", "impossible de répondre",
        "pas disponible", "pas dans les informations",
        "hors du contexte", "pas de réponse",
        # Anglais
        "i don't know", "no information", "i cannot", "i can't",
        "not found", "no relevant", "sorry",
        "does not contain", "do not contain",
        "not mentioned", "not available",
        "cannot answer", "unable to answer",
        "does not provide", "not in the provided",
    ]
    answered = not any(kw in final_response.lower() for kw in unanswered_keywords)

    # ============================================================
    # LOGGING - Enregistrer dans SQLite
    # ============================================================
    log_question(
        question=user_input,
        response=final_response,
        answered=answered,
        num_docs_found=len(docs),
        session_id=st.session_state.session_id,
    )

    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": final_response})
