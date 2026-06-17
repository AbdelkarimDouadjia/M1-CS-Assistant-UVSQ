from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import base64
from pathlib import Path
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import requests
import streamlit as st
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from chatbot_core.admin_settings import load_settings
from chatbot_core.llm_backends import build_all_openai_compat_chat_list, generation_llm_order
from chatbot_core.chat_logger import (
    clear_global_memory,
    delete_conversation,
    ensure_conversation,
    get_conversation_messages,
    get_global_memory,
    get_recent_interactions,
    list_conversations,
    log_question,
    pin_conversation,
    rename_conversation,
    rename_if_default,
    save_global_memory,
    update_feedback,
)
from chatbot_core.file_tools import (
    IMAGE_FAILURE_PREFIX,
    attachment_display,
    build_inline_prompt,
    export_markdown_to_docx,
    export_markdown_to_pdf,
    extract_uploaded_text,
)
from chatbot_core.grade_calculator import (
    PARCOURS_LIST,
    bo_options,
    build_program,
    calculate_grade_response,
    calculate_report,
    calculate_ue_final,
    format_report,
    infer_parcours,
    is_grade_intent,
    is_grade_query,
)
from chatbot_core.memory_extractor import (
    add_explicit_memory,
    auto_update_memory,
    extract_remember_command,
    warm_memory_from_history,
)
from chatbot_core.query_expander import (
    dedupe_documents,
    expand_query_with_llm,
)
from chatbot_core.reranking import rerank_documents
from chatbot_core.conversation_titler import make_conversation_title
from chatbot_core.grade_simulator import (
    SIMULATOR_TRIGGER,
    close_simulator,
    detect_simulator_intent,
    is_open as simulator_is_open,
    open_simulator,
    render_simulator_panel,
)
from chatbot_core.session_memory import build_session_history
from chatbot_core.streamlit_theme_inject import (
    inject_chatbot_theme,
    inject_sidebar_reopen_button,
)
from chatbot_core.unanswered_detection import is_unanswered_response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

APP_LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "m1-assistant-logo.png"

CHROMA_PATH = str(PROJECT_ROOT / "chroma_db")
VLLM_API_BASE = os.getenv("VLLM_BASE_URL") or os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "unused")
RERANKER_API_BASE = os.getenv("RERANKER_API_BASE", "http://localhost:8001")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B")
LOCAL_RERANKER_ENABLED = os.getenv("LOCAL_RERANKER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
LOCAL_RERANKER_MODEL = os.getenv("LOCAL_RERANKER_MODEL", "BAAI/bge-reranker-base")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "3"))
VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "5"))
VLLM_PROBE_TIMEOUT = int(os.getenv("VLLM_PROBE_TIMEOUT", "1"))


def _asset_data_uri(path: Path) -> str:
    """Return a browser-safe data URI for a small local UI asset."""
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


APP_LOGO_DATA_URI = _asset_data_uri(APP_LOGO_PATH)

SUGGESTIONS = [
    {
        "icon": ":material/event:",
        "title": "Jury du semestre 1",
        "subtitle": "Quand a lieu le jury du premier semestre ?",
        "prompt": "Quand a lieu le jury du premier semestre ?",
    },
    {
        "icon": ":material/calculate:",
        "title": "Calculer ma moyenne",
        "subtitle": "Lance l'assistant guidé pour les notes",
        "prompt": "Calcule ma moyenne S1",
    },
    {
        "icon": ":material/balance:",
        "title": "Compensation entre BCC",
        "subtitle": "Quelles sont les règles de compensation ?",
        "prompt": "Quelles sont les règles de compensation entre BCC ?",
    },
    {
        "icon": ":material/contact_support:",
        "title": "Contacts scolarité",
        "subtitle": "Qui contacter pour les démarches administratives ?",
        "prompt": "Quels contacts dois-je utiliser pour la scolarité ?",
    },
]

EXPORT_INTENT_WORDS = {
    "export",
    "exporte",
    "generate",
    "genere",
    "génère",
    "generer",
    "générer",
    "create",
    "cree",
    "crée",
    "creer",
    "créer",
    "download",
    "telecharger",
    "télécharger",
    "rapport",
    "fichier",
}
PDF_WORDS = {"pdf"}
DOCX_WORDS = {"docx", "word", "doc"}
MIC_ICON = """
<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
  <path d="M12 19v3"></path>
  <path d="M8 22h8"></path>
</svg>
""".strip()
STOP_ICON = """
<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <rect x="7" y="7" width="10" height="10" rx="1.5"></rect>
</svg>
""".strip()
SPEAKER_ICON = """
<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M11 5 6 9H3v6h3l5 4V5Z"></path>
  <path d="M15.5 8.5a5 5 0 0 1 0 7"></path>
  <path d="M18.5 5.5a9 9 0 0 1 0 13"></path>
</svg>
""".strip()

SUGGESTION_ICONS = {
    "calendar": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 10h18"/><circle cx="9" cy="14" r="1" fill="currentColor"/><circle cx="13" cy="14" r="1" fill="currentColor"/><circle cx="17" cy="14" r="1" fill="currentColor"/></svg>',
    "calculator": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="2.5"/><rect x="8" y="6" width="8" height="3" rx="0.6"/><circle cx="9" cy="13" r="0.8" fill="currentColor"/><circle cx="12" cy="13" r="0.8" fill="currentColor"/><circle cx="15" cy="13" r="0.8" fill="currentColor"/><circle cx="9" cy="17" r="0.8" fill="currentColor"/><circle cx="12" cy="17" r="0.8" fill="currentColor"/><circle cx="15" cy="17" r="0.8" fill="currentColor"/></svg>',
    "scale": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18"/><path d="M8 21h8"/><path d="M5 6h14"/><path d="M5 6 2 13a3 3 0 0 0 6 0z"/><path d="M19 6l-3 7a3 3 0 0 0 6 0z"/></svg>',
    "phone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A15 15 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>',
    "sparkle": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.6L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.4L12 3z"/><path d="M19 16l.6 1.4L21 18l-1.4.6L19 20l-.6-1.4L17 18l1.4-.4L19 16z"/></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
    "trash": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M6 6v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6"/><path d="M10 11v6M14 11v6"/></svg>',
    "pin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="m9 3 6 0 1 5 3 3-4 1H9l-4-1 3-3z"/></svg>',
    "plus": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>',
    "graduation": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5a6 6 0 0 0 12 0v-5"/></svg>',
    "shield": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 20 6.5v5.8c0 5-3.2 8.2-8 9.7-4.8-1.5-8-4.7-8-9.7V6.5L12 3Z"/><path d="M9 8.5h6M8.5 11.5h7M9 14.5h6"/></svg>',
    "copy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
    "refresh": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></svg>',
    "memory": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4h6a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z"/><path d="M9 9h6M9 13h4"/></svg>',
    "menu": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>',
    "doc": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>',
    "spark": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3v4M3 5h4M19 13v6M16 16h6M14 4l1.5 4L19 9l-3.5 1L14 14l-1.5-4L9 9l3.5-1z"/></svg>',
}

st.set_page_config(page_title="M1 AMIS Assistant", page_icon=":material/school:", layout="wide", initial_sidebar_state="expanded")
inject_chatbot_theme()
inject_sidebar_reopen_button()

@st.cache_data(ttl=5)
def _cached_settings() -> dict:
    return load_settings()


@st.cache_data(ttl=5)
def _cached_conversations(limit: int = 30) -> list[dict]:
    return [dict(row) for row in list_conversations(limit=limit)]


@st.cache_data(ttl=30)
def _cached_recent_prompts(limit: int = 4) -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in get_recent_interactions(limit=40):
        question = " ".join(str(dict(row).get("question") or "").split())
        if len(question) < 8:
            continue
        lowered = question.lower()
        if lowered.startswith(("calculer ma moyenne", "simulateur de notes")):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        label = question if len(question) <= 86 else question[:83].rstrip() + "…"
        prompts.append({"label": label, "prompt": question})
        if len(prompts) >= limit:
            break
    return prompts


@st.cache_data(ttl=5)
def _cached_memory(_cache_buster: int = 0) -> dict:
    """Return the global student memory shared across all conversations."""
    raw = get_global_memory()
    return {"enabled": bool(raw["enabled"]), "profile": str(raw["profile"] or "")}


ADMIN_SETTINGS = _cached_settings()


def _path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.exists():
            return 0
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
        return total
    except OSError:
        return 0


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


@st.cache_data(ttl=30)
def _storage_snapshot() -> dict[str, int | float]:
    targets = [
        PROJECT_ROOT / "chat_logs.db",
        PROJECT_ROOT / "chroma_db",
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "evaluation_chatbot",
        PROJECT_ROOT / "generated_reports",
    ]
    used = sum(_path_size(path) for path in targets)
    quota_mb = int(os.getenv("M1_ASSISTANT_STORAGE_QUOTA_MB", "3072"))
    quota = max(quota_mb, 1) * 1024 * 1024
    percent = min(100.0, (used / quota) * 100) if quota else 0.0
    return {"used": used, "quota": quota, "percent": percent}


def _memory_chips_html(profile: str, max_chips: int = 10) -> str:
    """Build compact HTML chips from the first lines of the global profile."""
    chips: list[str] = []
    for raw in (profile or "").splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        label, _, rest = line.partition(":")
        label = label.strip()
        rest = rest.strip()
        if not rest:
            continue
        if len(rest) > 72:
            rest = rest[:69] + "…"
        chips.append(
            f'<span class="memory-chip"><strong>{html.escape(label)}</strong>{html.escape(rest)}</span>'
        )
        if len(chips) >= max_chips:
            break
    return "".join(chips)


def _probe(url: str, timeout: float = 1.0) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.RequestException:
        return False


def is_vllm_up() -> bool:
    if "_vllm_up" not in st.session_state or (time.time() - st.session_state.get("_vllm_ts", 0) > 120):
        st.session_state._vllm_up = _probe(f"{VLLM_API_BASE}/models", timeout=VLLM_PROBE_TIMEOUT)
        st.session_state._vllm_ts = time.time()
    return st.session_state._vllm_up


def is_reranker_up() -> bool:
    if "_rr_up" not in st.session_state or (time.time() - st.session_state.get("_rr_ts", 0) > 120):
        st.session_state._rr_up = _probe(f"{RERANKER_API_BASE}/health", timeout=VLLM_PROBE_TIMEOUT)
        st.session_state._rr_ts = time.time()
    return st.session_state._rr_up


def build_vllm_chat(model_name: str, temperature: float, max_tokens: int) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=VLLM_API_BASE,
        api_key=VLLM_API_KEY,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=VLLM_TIMEOUT,
    )


def build_gemini_chat(model_name: str, temperature: float):
    if not os.getenv("GEMINI_API_KEY"):
        return None
    try:
        return ChatGoogleGenerativeAI(temperature=temperature, model=model_name or "gemini-2.5-flash")
    except Exception:
        return None


@st.cache_resource
def load_retriever(top_k: int):
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    return vector_store.as_retriever(search_kwargs={"k": top_k})


def resolve_llm_chain(settings: dict) -> list:
    """Return the release LLM order.

    In ``auto`` mode the app tries Gemini first, then optional
    OpenAI-compatible gateways, then the UVSQ/vLLM server as backup. Manual
    modes still let the admin force a specific backend.
    """
    temperature = float(settings.get("temperature", 0.1))
    max_tokens = int(settings.get("max_tokens", 800))
    backend = settings.get("active_backend", "auto")
    vllm_model = (settings.get("vllm_model") or "").strip()
    fallback_model = (settings.get("fallback_model") or "").strip()
    gemini_model = (settings.get("gemini_model") or "").strip()

    def maybe_vllm(force: bool = False):
        if not vllm_model:
            return None
        if not force and not is_vllm_up():
            return None
        return build_vllm_chat(vllm_model, temperature, max_tokens)

    def maybe_fallback(force: bool = False):
        if not fallback_model:
            return None
        if not force and not is_vllm_up():
            return None
        return build_vllm_chat(fallback_model, temperature, max_tokens)

    def maybe_gemini():
        return build_gemini_chat(gemini_model, temperature)

    def maybe_openai_compat():
        return build_all_openai_compat_chat_list(
            temperature=temperature,
            max_tokens=max_tokens,
        )

    chain: list = []
    if backend == "vllm":
        chain = [maybe_vllm(force=True)]
    elif backend == "fallback":
        chain = [maybe_fallback(force=True)]
    elif backend == "gemini":
        chain = [maybe_gemini()]
    else:
        chain = generation_llm_order(
            vllm_reachable=is_vllm_up(),
            vllm_llm=maybe_vllm(force=True),
            openai_compat_llms=[*maybe_openai_compat(), maybe_fallback()],
            tertiary_llm=maybe_gemini(),
        )
    return [client for client in chain if client is not None]


def extract_source_name(source: str) -> str:
    return Path(source).name if source else "Unknown"


def format_source(doc) -> str:
    source_name = doc.metadata.get("source_name") or extract_source_name(doc.metadata.get("source", "Unknown"))
    page = doc.metadata.get("page")
    section = doc.metadata.get("section")
    parts = [source_name]
    if page not in (None, "", "N/A"):
        parts.append(f"p. {page}")
    elif section:
        parts.append(f"CHUNK: {section}")
    if section and page not in (None, "", "N/A"):
        parts.append(str(section))
    return ", ".join(parts)


def build_context(docs) -> str:
    return "\n\n---\n\n".join(
        f"[Source {index}: {format_source(doc)}]\n{doc.page_content}"
        for index, doc in enumerate(docs, 1)
    )


def build_sources_block(docs) -> str:
    seen = set()
    lines = []
    for doc in docs:
        label = format_source(doc)
        if label not in seen:
            seen.add(label)
            lines.append(label)
    return "\n".join(lines)


def format_sources_for_display(sources_block: str) -> str:
    sources = [line.strip() for line in sources_block.splitlines() if line.strip()]
    if not sources:
        return ""
    return "\n".join(f"- {source}" for source in sources)


def clean_answer_text(text: str) -> str:
    cleaned = re.sub(r"(?is)\n*\s*Sources consult[ée]es?\s*:.*$", "", text).strip()
    cleaned = re.sub(r"\s*\[[^\]]*(?:\.pdf|\.md|\.txt)[^\]]*\]\.?", "", cleaned, flags=re.IGNORECASE)
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"\[[^\]]*(?:\.pdf|\.md|\.txt)[^\]]*\]\.?", stripped, flags=re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def rerank(query: str, docs, top_k: int, enabled: bool):
    return rerank_documents(
        query,
        docs,
        top_k=top_k,
        enabled=enabled,
        server_base=RERANKER_API_BASE,
        server_model=RERANKER_MODEL,
        request_timeout=REQUEST_TIMEOUT,
        server_available=is_reranker_up,
        local_enabled=LOCAL_RERANKER_ENABLED,
        local_model=LOCAL_RERANKER_MODEL,
    )


_TOOLBAR_ICON_CSS = """
<style>
  html, body { margin:0; padding:0; background:transparent; }
  .tts-wrap { display:flex; align-items:center; justify-content:flex-start; height:34px; }
  .tts-wrap button {
    width:34px; height:34px; min-width:34px;
    display:inline-flex; align-items:center; justify-content:center;
    border:1px solid transparent; background:transparent; color:#475569;
    border-radius:8px; cursor:pointer; padding:0;
    transition: background .15s ease, color .15s ease, border-color .15s ease;
  }
  .tts-wrap button:hover { background:#edf3f8; color:#0f172a; border-color:#edf3f8; }
  .tts-wrap button:focus-visible { outline:2px solid #00a6c8; outline-offset:1px; }
  .tts-wrap svg { width:18px; height:18px; stroke:currentColor; fill:none; }
</style>
""".strip()


def speak_button(text: str, key: str) -> None:
    escaped = json.dumps(clean_answer_text(text)[:4000])
    speaker_icon = json.dumps(SPEAKER_ICON)
    stop_icon = json.dumps(STOP_ICON)
    button_id = f"tts_{key}".replace("-", "_")
    st.components.v1.html(
        f"""
        {_TOOLBAR_ICON_CSS}
        <div class="tts-wrap">
          <button id="{button_id}" title="Lire à voix haute" aria-label="Lire la réponse"></button>
        </div>
        <script>
        (function() {{
            const parentWindow = window.parent;
            const btn = document.getElementById("{button_id}");
            const synth = parentWindow.speechSynthesis || window.speechSynthesis;
            const speakerIcon = {speaker_icon};
            const stopIcon = {stop_icon};
            btn.innerHTML = speakerIcon;
            btn.onclick = (event) => {{
                event.preventDefault();
                if (!synth) {{
                    parentWindow.alert("Text to speech is not supported in this browser.");
                    return;
                }}
                const state = parentWindow.__m1AmisTts || {{}};
                if (state.activeId === "{button_id}" && synth.speaking) {{
                    synth.cancel();
                    state.activeId = null;
                    btn.innerHTML = speakerIcon;
                    parentWindow.__m1AmisTts = state;
                    return;
                }}
                synth.cancel();
                const Utterance = parentWindow.SpeechSynthesisUtterance || window.SpeechSynthesisUtterance;
                const utterance = new Utterance({escaped});
                utterance.lang = "fr-FR";
                utterance.rate = 1;
                utterance.onend = () => {{
                    state.activeId = null;
                    state.activeButton = null;
                    btn.innerHTML = speakerIcon;
                    parentWindow.__m1AmisTts = state;
                }};
                utterance.onerror = () => {{
                    state.activeId = null;
                    state.activeButton = null;
                    btn.innerHTML = speakerIcon;
                    parentWindow.__m1AmisTts = state;
                }};
                if (state.activeButton && state.activeButton !== btn) {{
                    state.activeButton.innerHTML = speakerIcon;
                }}
                state.activeId = "{button_id}";
                state.activeButton = btn;
                parentWindow.__m1AmisTts = state;
                btn.innerHTML = stopIcon;
                setTimeout(() => synth.speak(utterance), 60);
            }};
        }})();
        </script>
        """,
        height=38,
    )


def _tool_status_row_html(
    *,
    rag_ok: bool,
    rerank_ok: bool,
    rerank_warn: bool = False,
    memory_on: bool,
    uploads_on: bool,
    llm_ok: bool,
) -> str:
    def pill(label: str, on: bool, warn: bool = False) -> str:
        dot = "dot-warn" if warn else ("dot-on" if on else "dot-off")
        cls = "status-pill" + (" is-active" if on and not warn else "")
        return f'<span class="{cls}"><span class="status-dot {dot}"></span>{html.escape(label)}</span>'

    parts = [
        pill("RAG", rag_ok, warn=not rag_ok),
        pill("Reranker", rerank_ok, warn=rerank_warn),
        pill("Mémoire", memory_on),
        pill("Fichiers", uploads_on),
        pill("LLM", llm_ok, warn=not llm_ok),
    ]
    return '<div class="status-row">' + "".join(parts) + "</div>"


def copy_answer_button(text: str, key: str) -> None:
    """Copy assistant answer to the clipboard (browser)."""
    safe = json.dumps(clean_answer_text(text)[:12000])
    bid = f"cpy_{key}".replace("-", "_")
    icon = json.dumps(SUGGESTION_ICONS["copy"])
    st.components.v1.html(
        f"""
        {_TOOLBAR_ICON_CSS}
        <div class="tts-wrap">
          <button id="{bid}" title="Copier la réponse" aria-label="Copier"></button>
        </div>
        <script>
        (function() {{
            const btn = document.getElementById("{bid}");
            const icon = {icon};
            btn.innerHTML = icon;
            btn.onclick = function(e) {{
                e.preventDefault();
                const t = {safe};
                const parent = window.parent;
                if (parent.navigator.clipboard && parent.navigator.clipboard.writeText) {{
                    parent.navigator.clipboard.writeText(t).then(function() {{
                        btn.style.color = '#16a34a';
                        setTimeout(function() {{ btn.style.color = ''; }}, 900);
                    }}).catch(function() {{ parent.alert('Copie impossible dans ce navigateur.'); }});
                }} else {{
                    parent.alert('Copie impossible : utilisez un navigateur récent (HTTPS).');
                }}
            }};
        }})();
        </script>
        """,
        height=36,
    )


def render_assistant_actions(
    text: str,
    log_id: int | None,
    key_prefix: str,
    voice_output_enabled: bool,
    *,
    message_index: int | None = None,
) -> None:
    if message_index is not None and message_index > 0:
        cols = st.columns([0.5, 0.5, 0.5, 0.5, 0.5, 6])
        with cols[0]:
            copy_answer_button(text, f"{key_prefix}_copy")
        with cols[1]:
            if st.button(
                "",
                icon=":material/refresh:",
                key=f"{key_prefix}_regen",
                help="Regénérer cette réponse (relance la même question)",
                width="stretch",
            ):
                prev = st.session_state.messages[message_index - 1]
                if prev.get("role") == "user":
                    st.session_state.messages = st.session_state.messages[:message_index]
                    user_count = sum(1 for m in st.session_state.messages if m.get("role") == "user")
                    st.session_state.questions = st.session_state.questions[:user_count]
                    st.session_state.responces = st.session_state.responces[:user_count]
                    st.session_state["_pending_input"] = prev.get("content", "")
                    st.rerun()
        voice_col, like_col, dislike_col = cols[2], cols[3], cols[4]
    else:
        cols = st.columns([0.5, 0.5, 0.5, 0.5, 6.5])
        with cols[0]:
            copy_answer_button(text, f"{key_prefix}_copy")
        voice_col, like_col, dislike_col = cols[1], cols[2], cols[3]

    if voice_output_enabled:
        with voice_col:
            speak_button(text, f"{key_prefix}_speak")
    if not log_id:
        return
    selected = st.session_state.feedback_by_log_id.get(str(log_id), "")
    with like_col:
        if st.button(
            "",
            icon=":material/thumb_up:",
            key=f"{key_prefix}_like",
            help="Bonne réponse",
            width="stretch",
            type="primary" if selected == "liked" else "secondary",
        ):
            update_feedback(log_id, "liked")
            st.session_state.feedback_by_log_id[str(log_id)] = "liked"
            st.toast("Merci — retour enregistré.")
    with dislike_col:
        if st.button(
            "",
            icon=":material/thumb_down:",
            key=f"{key_prefix}_dislike",
            help="Mauvaise réponse",
            width="stretch",
            type="primary" if selected == "disliked" else "secondary",
        ):
            update_feedback(log_id, "disliked")
            st.session_state.feedback_by_log_id[str(log_id)] = "disliked"
            st.toast("Merci — retour enregistré.")


def conversation_text() -> str:
    parts = []
    for message in st.session_state.messages:
        role = "Student" if message["role"] == "user" else "Assistant"
        parts.append(f"{role}:\n{message['content']}")
    return "\n\n".join(parts)


def last_assistant_text() -> str:
    for message in reversed(st.session_state.messages):
        if message["role"] == "assistant":
            return clean_answer_text(message["content"])
    return conversation_text()


def _tokens(text: str) -> set[str]:
    return set(re.sub(r"[^\w]+", " ", text.lower()).split())


def requested_export_formats(text: str) -> list[str]:
    tokens = _tokens(text)
    has_intent = bool(tokens & EXPORT_INTENT_WORDS)
    wants_pdf = bool(tokens & PDF_WORDS)
    wants_docx = bool(tokens & DOCX_WORDS)
    if not has_intent:
        return []
    if wants_pdf and wants_docx:
        return ["pdf", "docx"]
    if wants_pdf:
        return ["pdf"]
    if wants_docx:
        return ["docx"]
    if tokens & {"rapport", "fichier", "export"}:
        return ["pdf", "docx"]
    return []


def build_export_body(user_input: str) -> tuple[str, str]:
    tokens = _tokens(user_input)
    wants_full_chat = bool(tokens & {"conversation", "chat", "historique", "tout", "toute", "all"})
    if wants_full_chat:
        return "Conversation M1 AMIS", conversation_text()
    body = last_assistant_text()
    if body:
        return "Réponse M1 AMIS", body
    return "Conversation M1 AMIS", conversation_text()


def create_requested_exports(user_input: str) -> list[dict[str, object]]:
    formats = requested_export_formats(user_input)
    if not formats:
        return []
    title, body = build_export_body(user_input)
    if not body.strip():
        body = "Aucun contenu disponible à exporter pour le moment."
    stamp = time.strftime("%Y%m%d_%H%M%S")
    files = []
    for fmt in formats:
        if fmt == "pdf":
            files.append(
                {
                    "label": "Télécharger le PDF",
                    "id": str(uuid4()),
                    "file_name": f"m1_amis_{stamp}.pdf",
                    "mime": "application/pdf",
                    "bytes": export_markdown_to_pdf(title, body),
                }
            )
        if fmt == "docx":
            files.append(
                {
                    "label": "Télécharger le Word",
                    "id": str(uuid4()),
                    "file_name": f"m1_amis_{stamp}.docx",
                    "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "bytes": export_markdown_to_docx(title, body),
                }
            )
    return files


def render_file_downloads(files: list[dict[str, object]], key_prefix: str, use_container_width: bool = False) -> None:
    for index, file_info in enumerate(files):
        key_id = file_info.get("id") or file_info["file_name"]
        st.download_button(
            str(file_info["label"]),
            data=file_info["bytes"],
            file_name=str(file_info["file_name"]),
            mime=str(file_info["mime"]),
            key=f"{key_prefix}_{index}_{key_id}",
            width="stretch" if use_container_width else "content",
        )


def render_generated_files(key_prefix: str, use_container_width: bool = False) -> None:
    render_file_downloads(st.session_state.generated_files[-4:], key_prefix, use_container_width)


def inject_voice_to_text() -> None:
    st.components.v1.html(
        """
        <script>
        (function() {
            const parentWindow = window.parent;
            const parentDoc = window.parent.document;
            const micIcon = `
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <path d="M12 19v3"></path>
                  <path d="M8 22h8"></path>
                </svg>`;
            const stopIcon = `
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="7" y="7" width="10" height="10" rx="1.5"></rect>
                </svg>`;
            const state = parentWindow.__m1AmisVoiceInput || {
                recognition: null,
                recording: false,
                baseText: '',
                button: null,
                observer: null,
            };
            parentWindow.__m1AmisVoiceInput = state;
            function getInput() {
                return parentDoc.querySelector('textarea[data-testid="stChatInputTextArea"]')
                    || parentDoc.querySelector('[data-testid="stChatInput"] textarea');
            }
            function mount() {
                const input = getInput();
                if (!input) return false;
                const chatInputRoot = input.closest('[data-testid="stChatInput"]') || input.parentElement;
                if (!chatInputRoot) return false;
                const existing = parentDoc.getElementById('voiceBtnContainer');
                if (existing && chatInputRoot.contains(existing)) return true;
                if (existing) existing.remove();
                const container = parentDoc.createElement('div');
                container.className = 'voice-btn-container';
                container.id = 'voiceBtnContainer';
                const btn = parentDoc.createElement('button');
                btn.type = 'button';
                btn.className = 'voice-btn';
                btn.title = 'Voice input';
                btn.setAttribute('aria-label', 'Voice input');
                btn.innerHTML = state.recording ? stopIcon : micIcon;
                if (state.recording) btn.classList.add('recording');
                container.appendChild(btn);
                chatInputRoot.appendChild(container);
                state.button = btn;
                wireButton(btn);
                return true;
            }
            function setButtonRecording(recording) {
                state.recording = recording;
                if (!state.button) return;
                state.button.classList.toggle('recording', recording);
                state.button.innerHTML = recording ? stopIcon : micIcon;
            }
            function setInput(textarea, text) {
                const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(textarea, text);
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                textarea.focus();
            }
            function wireButton(btn) {
                if (btn.dataset.voiceBound) return;
                btn.dataset.voiceBound = 'true';
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    const SpeechAPI = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
                    if (!SpeechAPI) {
                        window.parent.alert('Voice input works best in Chrome or Edge.');
                        return;
                    }
                    if (state.recording && state.recognition) {
                        state.recognition.stop();
                        return;
                    }
                    const input = getInput();
                    state.baseText = input ? input.value.trim() : '';
                    state.recognition = new SpeechAPI();
                    state.recognition.lang = 'fr-FR';
                    state.recognition.interimResults = true;
                    state.recognition.continuous = true;
                    state.recognition.onstart = function() { setButtonRecording(true); };
                    state.recognition.onend = function() { setButtonRecording(false); };
                    state.recognition.onerror = function() { setButtonRecording(false); };
                    state.recognition.onresult = function(event) {
                        let finalText = '';
                        let interimText = '';
                        for (let i = 0; i < event.results.length; i++) {
                            const chunk = event.results[i][0].transcript.trim();
                            if (event.results[i].isFinal) finalText += chunk + ' ';
                            else interimText += chunk + ' ';
                        }
                        const spoken = (finalText + interimText).trim();
                        const textarea = getInput();
                        if (textarea && spoken) {
                            const prefix = state.baseText ? state.baseText + ' ' : '';
                            setInput(textarea, prefix + spoken);
                        }
                    };
                    state.recognition.start();
                });
            }
            mount();
            if (!state.observer) {
                state.observer = new MutationObserver(function() { mount(); });
                state.observer.observe(parentDoc.body, { childList: true, subtree: true });
            }
        })();
        </script>
        """,
        height=0,
    )


for key, value in {
    "messages": [],
    "questions": [],
    "responces": [],
    "feedback_by_log_id": {},
    "generated_files": [],
    "moyenne_wizard": None,
    "_loaded_session": None,
    "_memory_facts_notice": [],
    "_simulator_open": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


def _push_tool_response(
    *,
    user_input: str,
    display_input: str,
    response_text: str,
    tool_name: str,
    auto_title: str | None = None,
    generated_files: list[dict] | None = None,
) -> None:
    """Append a deterministic tool response to the chat and persist it.

    Centralised so every "intent detected → tool answered" path produces
    the same shape of message + DB row + auto-title side-effect.
    Defined near the top of the module so it is in scope for the panel
    render blocks that run before the chat-input intent handlers.
    """
    st.session_state.messages.append({"role": "user", "content": display_input or user_input})
    st.session_state.questions.append(user_input)
    log_id = log_question(
        question=user_input,
        response=response_text,
        answered=True,
        num_docs_found=0,
        session_id=st.session_state.session_id,
        tools_used=tool_name,
        sources="",
    )
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_text,
            "log_id": log_id,
            "details": "",
            "sources": "",
            "images": [],
            "generated_files": generated_files or [],
        }
    )
    st.session_state.responces.append(response_text)
    st.session_state.feedback_by_log_id.setdefault(str(log_id), "")
    if auto_title:
        try:
            sid = st.session_state.session_id
            if not st.session_state.get(f"_titled_{sid}") and rename_if_default(sid, auto_title):
                _cached_conversations.clear()
                st.session_state[f"_titled_{sid}"] = True
        except Exception:
            pass


def _load_conversation(session_id: str) -> None:
    rows = get_conversation_messages(session_id)
    messages: list[dict] = []
    questions: list[str] = []
    responses: list[str] = []
    feedback: dict[str, str] = {}
    for row in rows:
        question = row["question"]
        answer = row["response"] or ""
        messages.append({"role": "user", "content": question})
        messages.append(
            {
                "role": "assistant",
                "content": answer,
                "log_id": row["id"],
                "details": "",
                "sources": row["sources"] or "",
                "images": [],
                "generated_files": [],
            }
        )
        questions.append(question)
        responses.append(answer)
        if row["feedback"] in {"liked", "disliked"}:
            feedback[str(row["id"])] = row["feedback"]
    if bool(ADMIN_SETTINGS.get("memory_feature_enabled", True)):
        current_memory = get_global_memory()
        if not str(current_memory.get("profile") or "").strip():
            warmed = warm_memory_from_history(session_id, [*questions, *responses])
            if warmed:
                _cached_memory.clear()
    st.session_state.messages = messages
    st.session_state.questions = questions
    st.session_state.responces = responses
    st.session_state.feedback_by_log_id = feedback
    st.session_state.moyenne_wizard = None
    st.session_state.generated_files = []
    st.session_state._loaded_session = session_id


def _switch_conversation(session_id: str) -> None:
    st.session_state.session_id = session_id
    _load_conversation(session_id)
    st.rerun()


def _new_conversation() -> None:
    st.session_state.session_id = str(uuid4())
    st.session_state.messages = []
    st.session_state.questions = []
    st.session_state.responces = []
    st.session_state.feedback_by_log_id = {}
    st.session_state.generated_files = []
    st.session_state.moyenne_wizard = None
    st.session_state._loaded_session = st.session_state.session_id
    st.rerun()


if "session_id" not in st.session_state:
    existing = list_conversations(limit=1)
    if existing:
        st.session_state.session_id = existing[0]["session_id"]
        _load_conversation(st.session_state.session_id)
    else:
        st.session_state.session_id = str(uuid4())
        st.session_state._loaded_session = st.session_state.session_id

if st.session_state._loaded_session != st.session_state.session_id:
    _load_conversation(st.session_state.session_id)


def _start_moyenne_wizard(default_parcours: str | None) -> None:
    st.session_state.moyenne_wizard = {
        "step": "parcours",
        "parcours": default_parcours,
        "period": None,
        "selected_bo": [],
        "input_mode": None,
        "current_index": 0,
        "answers": {},
    }


def _close_moyenne_wizard() -> None:
    st.session_state.moyenne_wizard = None


def _wizard_ues(state: dict) -> list:
    return build_program(
        state["parcours"],
        state["period"],
        selected_bo_codes=state["selected_bo"] if state["period"] in {"s2", "year"} else None,
    )


def _grade_input(label: str, key: str, value) -> float | None:
    """Render a number input that accepts blank values and clamps to 0..20."""
    raw = st.text_input(
        label,
        value="" if value is None else str(value),
        key=key,
        placeholder="0–20",
        help="Notes obligatoirement comprises entre 0 et 20.",
    )
    raw = raw.strip().replace(",", ".")
    if raw == "":
        return None
    try:
        parsed = float(raw)
    except ValueError:
        st.warning(f"Valeur ignorée (non numérique) : {raw!r}")
        return None
    if parsed < 0 or parsed > 20:
        st.error(f"La note {parsed:g} est hors de l'intervalle 0–20 et a été ignorée.")
        return None
    return round(parsed, 2)


def render_moyenne_wizard(parcours_hint: str | None) -> str | None:
    """Render the multi-step moyenne calculator.

    Returns the final Markdown report (so the chat can store it as an assistant
    message) once the user clicks "Terminer & envoyer dans le chat", otherwise
    returns ``None``.
    """
    state = st.session_state.moyenne_wizard
    if state is None:
        return None
    with st.container(border=True):
        header_cols = st.columns([5, 1])
        with header_cols[0]:
            st.markdown("### Calculer ma moyenne (M1 Informatique)")
            st.caption(
                "Outil guidé : parcours → période → mode de saisie → notes → rapport. "
                "Le jury et le relevé officiel restent seuls juges."
            )
        with header_cols[1]:
            if st.button("Fermer", key="moyenne_close", width="content"):
                _close_moyenne_wizard()
                return None

        if state["step"] == "parcours":
            st.markdown("**Étape 1 — Votre parcours**")
            default = state["parcours"] or parcours_hint
            options = PARCOURS_LIST
            index = options.index(default) if default in options else 0
            if default and default in options:
                st.success(f"Parcours détecté dans votre profil : **{default}**. Confirmez ou modifiez ci-dessous.")
            parcours = st.radio("Parcours", options=options, index=index, horizontal=True, key="moyenne_parcours")
            if st.button("Suivant →", key="moyenne_parcours_next", type="primary"):
                state["parcours"] = parcours
                state["step"] = "period"
                st.rerun()
            return None

        if state["step"] == "period":
            st.markdown("**Étape 2 — Période et BO**")
            period_label = st.radio(
                "Que voulez-vous calculer ?",
                options=["Semestre 1", "Semestre 2", "Année complète"],
                horizontal=True,
                key="moyenne_period_radio",
            )
            period = {"Semestre 1": "s1", "Semestre 2": "s2", "Année complète": "year"}[period_label]
            selected_bo: list[str] = []
            if period in {"s2", "year"}:
                bo_list = bo_options(state["parcours"])
                st.caption(
                    f"Choisissez exactement 2 UEs Bloc Optionnel (BO) parmi celles disponibles pour {state['parcours']}."
                )
                checked = state["selected_bo"] or []
                cols = st.columns(2)
                for index, ue in enumerate(bo_list):
                    with cols[index % 2]:
                        if st.checkbox(
                            f"{ue.name} ({ue.code})",
                            value=ue.code in checked,
                            key=f"moyenne_bo_{ue.code}",
                        ):
                            selected_bo.append(ue.code)
            col_back, col_next = st.columns([1, 1])
            with col_back:
                if st.button("← Retour", key="moyenne_period_back"):
                    state["step"] = "parcours"
                    st.rerun()
            with col_next:
                if st.button("Suivant →", key="moyenne_period_next", type="primary"):
                    if period in {"s2", "year"} and len(selected_bo) != 2:
                        st.error("Sélectionnez exactement 2 UEs BO avant de continuer.")
                    else:
                        state["period"] = period
                        state["selected_bo"] = selected_bo
                        state["step"] = "mode"
                        st.rerun()
            return None

        if state["step"] == "mode":
            st.markdown("**Étape 3 — Mode de saisie**")
            mode_label = st.radio(
                "Comment saisirez-vous vos notes ?",
                options=[
                    "Note finale / moyenne du module",
                    "CC + Examen (formule (CC + 2 × ET) / 3)",
                ],
                key="moyenne_mode_radio",
            )
            mode = "final" if mode_label.startswith("Note finale") else "cc_et"
            col_back, col_next = st.columns([1, 1])
            with col_back:
                if st.button("← Retour", key="moyenne_mode_back"):
                    state["step"] = "period"
                    st.rerun()
            with col_next:
                if st.button("Suivant →", key="moyenne_mode_next", type="primary"):
                    state["input_mode"] = mode
                    state["current_index"] = 0
                    state["step"] = "notes"
                    st.rerun()
            return None

        if state["step"] == "notes":
            ues = _wizard_ues(state)
            if not ues:
                st.error("Aucune UE à saisir pour cette configuration.")
                if st.button("← Retour", key="moyenne_notes_back"):
                    state["step"] = "period"
                    st.rerun()
                return None
            index = max(0, min(state["current_index"], len(ues) - 1))
            ue = ues[index]
            st.markdown(f"**Étape 4 — UE {index + 1} / {len(ues)} : {ue.name}** ({ue.code})")
            st.caption(
                f"BCC : {ue.bcc} · ECTS : {ue.ects:g} · Règle : {ue.rule}"
            )
            answer = state["answers"].get(ue.code, {})
            if state["input_mode"] == "final":
                final = _grade_input("Note finale (0–20)", f"moyenne_final_{ue.code}", answer.get("final"))
                answer = {"final": final}
            else:
                if ue.rule == "exam_only":
                    st.info("UE évaluée uniquement par un écrit (pas de CC).")
                    exam = _grade_input("Note de l'examen écrit", f"moyenne_exam_{ue.code}", answer.get("exam"))
                    answer = {"exam": exam}
                elif ue.rule == "cc_only_no_s2":
                    st.info("UE évaluée uniquement en CC, pas de session 2.")
                    cc = _grade_input("Note de CC", f"moyenne_cc_{ue.code}", answer.get("cc"))
                    answer = {"cc": cc}
                elif ue.rule == "cc_s1_exam_s2":
                    st.info("Session 1 = CC, session 2 = écrit. Renseignez ce que vous avez.")
                    cc = _grade_input("Note de CC (session 1)", f"moyenne_cc_{ue.code}", answer.get("cc"))
                    exam = _grade_input("Note de l'examen (session 2, optionnel)", f"moyenne_exam_{ue.code}", answer.get("exam"))
                    answer = {"cc": cc, "exam": exam}
                else:
                    cc = _grade_input("Note de CC", f"moyenne_cc_{ue.code}", answer.get("cc"))
                    exam = _grade_input("Note de l'examen écrit (ET)", f"moyenne_exam_{ue.code}", answer.get("exam"))
                    answer = {"cc": cc, "exam": exam}
            state["answers"][ue.code] = answer
            cols = st.columns([1, 1, 1, 1])
            with cols[0]:
                if st.button("← Précédent", key=f"moyenne_prev_{index}", disabled=index == 0):
                    state["current_index"] = max(0, index - 1)
                    st.rerun()
            with cols[1]:
                if st.button("Ignorer", key=f"moyenne_skip_{index}"):
                    state["answers"][ue.code] = {}
                    state["current_index"] = min(len(ues) - 1, index + 1)
                    st.rerun()
            with cols[2]:
                if index < len(ues) - 1:
                    if st.button("Suivant →", key=f"moyenne_next_{index}", type="primary"):
                        state["current_index"] = index + 1
                        st.rerun()
            with cols[3]:
                if index == len(ues) - 1:
                    if st.button("Calculer", key=f"moyenne_compute_{index}", type="primary"):
                        state["step"] = "report"
                        st.rerun()
            return None

        if state["step"] == "report":
            ues = _wizard_ues(state)
            entries = []
            for ue in ues:
                answer = state["answers"].get(ue.code, {})
                entries.append(
                    calculate_ue_final(
                        ue,
                        cc=answer.get("cc"),
                        exam=answer.get("exam"),
                        final=answer.get("final"),
                    )
                )
            semester_for_report = state["period"]
            selected_bo = state["selected_bo"] if state["period"] in {"s2", "year"} else None
            report = calculate_report(
                state["parcours"],
                entries,
                semester=semester_for_report,
                selected_bo_codes=selected_bo,
            )
            body, _details = format_report(report)
            st.markdown(body)
            col_back, col_restart, col_send = st.columns([1, 1, 2])
            with col_back:
                if st.button("← Modifier", key="moyenne_report_back"):
                    state["step"] = "notes"
                    st.rerun()
            with col_restart:
                if st.button("Recommencer", key="moyenne_report_restart"):
                    _start_moyenne_wizard(state["parcours"])
                    st.rerun()
            with col_send:
                if st.button("✓ Envoyer dans le chat", key="moyenne_report_send", type="primary"):
                    _close_moyenne_wizard()
                    return body
            return None
        return None

retrieval_top_k = int(ADMIN_SETTINGS.get("retrieval_top_k", 12))
final_context_k = int(ADMIN_SETTINGS.get("final_context_k", 5))
reranking_enabled = bool(ADMIN_SETTINGS.get("reranking_enabled", True))
query_expansion_enabled = bool(ADMIN_SETTINGS.get("query_expansion_enabled", False))
query_expansion_max_variants = int(ADMIN_SETTINGS.get("query_expansion_max_variants", 3))

# Retriever and LLM chain are intentionally NOT initialised at boot. They are
# expensive (bge-m3 weights ~2GB, vLLM probe, etc.) and are only useful when a
# chat answer is actually about to be produced. Wizard / sidebar / conversation
# switches stay snappy because they skip this entirely.
retriever_error: Exception | None = None


def get_retriever_or_error() -> tuple[object | None, Exception | None]:
    """Lazily build the retriever the first time the chat path needs it."""
    global retriever_error
    if "_retriever" not in st.session_state:
        try:
            st.session_state._retriever = load_retriever(retrieval_top_k)
        except Exception as exc:
            st.session_state._retriever = None
            retriever_error = exc
    return st.session_state.get("_retriever"), retriever_error


def get_llm_chain() -> list:
    """Build the LLM chain only when we actually need to call an LLM."""
    if "_llm_chain_ts" not in st.session_state or (
        time.time() - st.session_state.get("_llm_chain_ts", 0) > 120
    ):
        st.session_state._llm_chain = resolve_llm_chain(ADMIN_SETTINGS)
        st.session_state._llm_chain_ts = time.time()
    return st.session_state._llm_chain


def has_llm_configuration(settings: dict) -> bool:
    """Cheap status check for first paint; real reachability is checked on send."""
    backend = settings.get("active_backend", "auto")
    has_vllm = bool((settings.get("vllm_model") or "").strip())
    has_fallback = bool((settings.get("fallback_model") or "").strip())
    has_gemini = bool((settings.get("gemini_model") or "").strip() and os.getenv("GEMINI_API_KEY", "").strip())
    if backend == "vllm":
        return has_vllm
    if backend == "fallback":
        return has_fallback
    if backend == "gemini":
        return has_gemini
    return has_vllm or has_fallback or has_gemini


file_upload_enabled = bool(ADMIN_SETTINGS.get("file_upload_enabled", True))
image_upload_enabled = bool(ADMIN_SETTINGS.get("image_upload_enabled", True))
voice_input_enabled = bool(ADMIN_SETTINGS.get("voice_input_enabled", True))
voice_output_enabled = bool(ADMIN_SETTINGS.get("voice_output_enabled", True))
export_enabled = bool(ADMIN_SETTINGS.get("export_enabled", True))
memory_feature_enabled = bool(ADMIN_SETTINGS.get("memory_feature_enabled", True))
suggestions_enabled = bool(ADMIN_SETTINGS.get("suggestions_enabled", True))
max_upload_chars = int(ADMIN_SETTINGS.get("max_upload_chars", 12000))
vision_model = ADMIN_SETTINGS.get("vision_model") or "gemini-2.5-flash"
memory = _cached_memory()
memory_enabled = bool(memory["enabled"]) if memory_feature_enabled else False
profile = str(memory["profile"] or "") if (memory_feature_enabled and memory_enabled) else ""

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="sidebar-brand-mark">{SUGGESTION_ICONS["shield"]}</div>
          <div>
            <div class="sidebar-brand-name">UVSQ</div>
            <div class="sidebar-brand-subtitle">Université Paris-Saclay</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Nouvelle conversation",
        icon=":material/add:",
        width="stretch",
        key="sidebar_new_conv",
        type="primary",
    ):
        _new_conversation()

    parcours_hint = (
        infer_parcours(str(memory.get("profile") or ""))
        or infer_parcours(" ".join(st.session_state.questions[-3:]))
    )
    if st.session_state.moyenne_wizard is None:
        if st.button(
            "Calculer ma moyenne",
            icon=":material/calculate:",
            width="stretch",
            key="sidebar_open_moyenne",
        ):
            _start_moyenne_wizard(parcours_hint)
            st.rerun()
    else:
        if st.button(
            "Fermer le calculateur",
            icon=":material/close:",
            width="stretch",
            key="sidebar_close_moyenne",
        ):
            _close_moyenne_wizard()
            st.rerun()

    if st.button(
        "Simulateur Et si…",
        icon=":material/tune:",
        width="stretch",
        key="sidebar_open_simulator",
        help="Ajustez les notes en direct et visualisez la validation.",
    ):
        open_simulator(parcours_hint)
        st.rerun()

    st.divider()
    with st.expander("Mémoire étudiante (partagée entre toutes les conversations)", expanded=False):
        if memory_feature_enabled:
            memory_enabled = st.toggle("Activer", value=bool(memory["enabled"]))
            profile = st.text_area(
                "Profil (édition libre)",
                value=str(memory["profile"]),
                placeholder=(
                    "Ex:\nNom : Abdelkarim\nÂge : 23 ans\nLieu : Paris, France\n"
                    "Statut : étudiant\nParcours : DataScale\nUEs choisies : Ranking, Simulation"
                ),
                height=170,
                disabled=not memory_enabled,
                help=(
                    "Cette mémoire est partagée entre toutes vos conversations (comme ChatGPT). "
                    "Elle se met à jour automatiquement quand vous donnez votre nom, âge, lieu, parcours, etc. "
                    "Vous pouvez aussi écrire dans le chat « souviens-toi que ... » ou « /remember ... »."
                ),
            )
            col_save, col_clear = st.columns(2)
            with col_save:
                if st.button("Enregistrer", width="stretch", key="memory_save"):
                    save_global_memory(memory_enabled, profile)
                    _cached_memory.clear()
                    st.toast("Mémoire enregistrée")
            with col_clear:
                if st.button("Vider", width="stretch", key="memory_clear"):
                    clear_global_memory()
                    _cached_memory.clear()
                    st.toast("Mémoire vidée")
                    st.rerun()
        else:
            memory_enabled = False
            profile = ""
            st.caption("Mémoire désactivée par l'administrateur.")

    st.divider()
    st.markdown('<p class="sb-section-label">Conversations</p>', unsafe_allow_html=True)
    conv_filter = st.text_input(
        "Rechercher",
        value="",
        key="conv_filter",
        placeholder="Filtrer par titre…",
        help="Tapez un mot-clé pour réduire la liste des conversations.",
    )
    needle = (conv_filter or "").strip().lower()
    conversations = _cached_conversations(limit=30)
    if conversations:
        active = st.session_state.session_id
        shown = 0
        for conv in conversations:
            sid = conv["session_id"]
            title = conv["title"] or "Sans titre"
            if needle and needle not in title.lower():
                continue
            shown += 1
            is_active = sid == active
            row = st.columns([0.74, 0.13, 0.13])
            with row[0]:
                if conv["pinned"]:
                    row_icon = ":material/push_pin:"
                elif is_active:
                    row_icon = ":material/forum:"
                else:
                    row_icon = ":material/chat_bubble_outline:"
                if st.button(
                    title,
                    icon=row_icon,
                    key=f"conv_open_{sid}",
                    width="stretch",
                    type="primary" if is_active else "secondary",
                    help=f"Mise à jour: {conv['updated_at']}",
                ):
                    if not is_active:
                        _switch_conversation(sid)
            with row[1]:
                if st.button(
                    "",
                    icon=":material/push_pin:",
                    key=f"conv_pin_{sid}",
                    help="Désépingler" if conv["pinned"] else "Épingler",
                    width="stretch",
                    type="primary" if conv["pinned"] else "secondary",
                ):
                    pin_conversation(sid, not bool(conv["pinned"]))
                    _cached_conversations.clear()
                    st.rerun()
            with row[2]:
                if st.button(
                    "",
                    icon=":material/delete:",
                    key=f"conv_del_{sid}",
                    help="Supprimer la conversation",
                    width="stretch",
                ):
                    delete_conversation(sid)
                    _cached_conversations.clear()
                    if sid == st.session_state.session_id:
                        _new_conversation()
                    st.rerun()
        if shown == 0:
            st.caption("Aucune conversation ne correspond à ce filtre.")
    else:
        st.markdown(
            '<div class="empty-state-sidebar">Aucune conversation enregistrée pour le moment.</div>',
            unsafe_allow_html=True,
        )

    storage = _storage_snapshot()
    storage_used = int(storage["used"])
    storage_quota = int(storage["quota"])
    storage_percent = float(storage["percent"])
    st.markdown(
        f"""
        <div class="storage-meter">
          <div class="storage-top">
            <span>Espace utilisé</span>
            <strong>{storage_percent:.0f}%</strong>
          </div>
          <div class="storage-track"><span style="width:{storage_percent:.1f}%"></span></div>
          <div class="storage-caption">{html.escape(_format_size(storage_used))} / {html.escape(_format_size(storage_quota))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    if export_enabled:
        with st.expander("Fichiers générés", expanded=False):
            if st.session_state.generated_files:
                render_generated_files("sidebar_generated", use_container_width=True)
            else:
                st.caption("Demandez un export PDF ou Word dans la conversation pour récupérer un fichier ici.")

hero_mark_html = (
    f'<img class="hero-logo" src="{APP_LOGO_DATA_URI}" alt="Logo Assistant M1 Informatique">'
    if APP_LOGO_DATA_URI
    else SUGGESTION_ICONS["graduation"]
)

st.markdown(
    f"""
    <div class="app-hero">
      <div class="hero-status-card">
        <span class="hero-status-dot"></span>
        <span class="hero-status-title">En ligne</span>
        <span class="hero-status-model">Modèle: {html.escape(str(ADMIN_SETTINGS.get("gemini_model") or "Gemini 2.5 Flash"))}</span>
      </div>
      <div class="hero-version">Master 1 · Informatique · UVSQ / Université Paris-Saclay</div>
      <div class="hero-flex">
        <div class="hero-mark">{hero_mark_html}</div>
        <div class="hero-text">
          <h1 class="app-title">Assistant M1 Informatique</h1>
          <p class="app-subtitle">
            Réponses fondées sur les documents du programme, calculateur de moyenne,
            analyse de pièces jointes et <strong>mémoire persistante</strong> partagée
            entre toutes vos conversations.
          </p>
        </div>
      </div>
      {('<div class="memory-chips-row">' + _memory_chips_html(profile) + "</div>") if (memory_feature_enabled and memory_enabled and profile.strip()) else ""}
    </div>
    """,
    unsafe_allow_html=True,
)

_rag_ok = retriever_error is None
_rerank_on = bool(reranking_enabled)
_rerank_warn = False
_memory_on = bool(memory_feature_enabled and memory_enabled and profile.strip())
_uploads_on = bool(file_upload_enabled or image_upload_enabled)
_llm_ok = has_llm_configuration(ADMIN_SETTINGS)
st.markdown(
    _tool_status_row_html(
        rag_ok=_rag_ok,
        rerank_ok=_rerank_on,
        rerank_warn=_rerank_warn,
        memory_on=_memory_on,
        uploads_on=_uploads_on,
        llm_ok=_llm_ok,
    ),
    unsafe_allow_html=True,
)
if st.session_state._memory_facts_notice:
    learned_lines = "\n".join(f"- {fact}" for fact in st.session_state._memory_facts_notice)
    with st.expander("Mémoire mise à jour automatiquement", expanded=False):
        st.markdown(learned_lines)
    st.session_state._memory_facts_notice = []
ensure_conversation(st.session_state.session_id)
if retriever_error is not None:
    st.info(
        "Recherche documentaire indisponible (modèle d'embedding non chargé). "
        "Le chatbot peut quand même répondre à partir de la mémoire étudiante, "
        "des pièces jointes et du calculateur de moyenne.",
        icon=":material/info:",
    )

for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        display_content = clean_answer_text(message["content"]) if message["role"] == "assistant" else message["content"]
        st.markdown(display_content)
        if message["role"] == "assistant":
            if message.get("generated_files"):
                render_file_downloads(message["generated_files"], f"files_{idx}_{message.get('log_id', idx)}")
            render_assistant_actions(
                display_content,
                message.get("log_id"),
                f"actions_{idx}_{message.get('log_id', idx)}",
                voice_output_enabled,
                message_index=idx,
            )
            details = message.get("details")
            sources = message.get("sources")
            images = message.get("images", [])
            if details or sources or images:
                with st.expander("Sources consultées", expanded=False):
                    if details:
                        st.markdown(details)
                    if sources:
                        st.markdown(format_sources_for_display(sources))
                    if images:
                        for image_result in images:
                            if image_result.get("thumbnail"):
                                st.image(image_result["thumbnail"], caption=image_result.get("title") or image_result.get("link"))
                            st.markdown(f"[{image_result.get('title')}]({image_result.get('link')})")

if not st.session_state.messages and suggestions_enabled:
    st.markdown(
        """
        <div class="welcome-card">
          <h3>Par où commencer ?</h3>
          <p>Choisissez une suggestion ci-dessous ou posez votre propre question dans le champ en bas de page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for index, item in enumerate(SUGGESTIONS):
        with cols[index % 2]:
            if st.button(
                f"{item['title']}\n{item.get('subtitle', '')}",
                icon=item.get("icon"),
                key=f"suggestion_{index}",
                width="stretch",
                help=item.get("subtitle") or item.get("prompt", ""),
            ):
                st.session_state["_pending_input"] = item["prompt"]
                st.rerun()
    recent_prompts = _cached_recent_prompts()
    if recent_prompts:
        st.markdown(
            """
            <div class="recent-suggestions-card">
              <h3>Suggestions récentes</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        recent_cols = st.columns(len(recent_prompts))
        for index, item in enumerate(recent_prompts):
            with recent_cols[index]:
                if st.button(
                    item["label"],
                    icon=":material/history:",
                    key=f"recent_suggestion_{index}",
                    width="stretch",
                    help=item["prompt"],
                ):
                    st.session_state["_pending_input"] = item["prompt"]
                    st.rerun()

wizard_result = render_moyenne_wizard(parcours_hint)
if wizard_result:
    request_text = f"Calculer ma moyenne ({parcours_hint or 'parcours sélectionné'})."
    st.session_state.messages.append({"role": "user", "content": request_text})
    st.session_state.questions.append(request_text)
    log_id = log_question(
        question=request_text,
        response=wizard_result,
        answered=True,
        num_docs_found=0,
        session_id=st.session_state.session_id,
        tools_used="grade_calculator_wizard",
        sources="",
    )
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": wizard_result,
            "log_id": log_id,
            "details": "",
            "sources": "",
            "images": [],
            "generated_files": [],
        }
    )
    st.session_state.responces.append(wizard_result)
    st.session_state.feedback_by_log_id.setdefault(str(log_id), "")
    st.rerun()

if simulator_is_open():
    sim_result = render_simulator_panel(default_parcours=parcours_hint)
    if sim_result:
        _push_tool_response(
            user_input="Simulateur de notes",
            display_input="Simulateur de notes",
            response_text=sim_result,
            tool_name="grade_simulator_send",
            auto_title="Simulateur de notes",
        )
        st.rerun()

if voice_input_enabled:
    inject_voice_to_text()

allowed_types: list[str] = []
if file_upload_enabled:
    allowed_types += ["pdf", "txt", "md", "docx"]
if image_upload_enabled:
    allowed_types += ["png", "jpg", "jpeg", "webp"]

chat_kwargs: dict = {}
if allowed_types:
    chat_kwargs["accept_file"] = "multiple"
    chat_kwargs["file_type"] = allowed_types
else:
    st.caption("File and image uploads are disabled by the administrator.")

prompt_value = st.chat_input(
    "Posez une question M1, joignez un fichier, ou dites « souviens-toi que ... »",
    **chat_kwargs,
)

prompt_files = []
if prompt_value and not isinstance(prompt_value, str):
    prompt_files = list(getattr(prompt_value, "files", []) or [])
    typed_input = getattr(prompt_value, "text", "") or ""
else:
    typed_input = prompt_value or ""

attachments: list[dict[str, str]] = []
if prompt_files:
    with st.spinner("Lecture des fichiers joints..."):
        for uploaded in prompt_files:
            suffix = Path(uploaded.name).suffix.lower()
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"} and not image_upload_enabled:
                st.warning(f"Image upload is disabled: {uploaded.name} ignored.")
                continue
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"} and not file_upload_enabled:
                st.warning(f"File upload is disabled: {uploaded.name} ignored.")
                continue
            try:
                text, kind = extract_uploaded_text(
                    uploaded,
                    max_chars=max_upload_chars,
                    vision_model=vision_model,
                )
            except RuntimeError as exc:
                st.error(str(exc))
                continue
            if kind == "image" and text.startswith(IMAGE_FAILURE_PREFIX):
                st.warning(text.replace(IMAGE_FAILURE_PREFIX, "").strip())
                # Still attach a short marker so the LLM acknowledges the image was sent.
                text = f"[Image jointe: {uploaded.name}] (lecture automatique indisponible — l'utilisateur peut décrire l'image manuellement.)"
            elif not text and kind == "image":
                st.warning(
                    f"Aucun moteur de vision n'a pu lire {uploaded.name}. Configurez GEMINI_API_KEY ou installez Tesseract."
                )
            attachments.append({"name": uploaded.name, "text": text, "kind": kind})

user_input = build_inline_prompt(typed_input, attachments)
display_input = ""
if attachments:
    summary = attachment_display(attachments)
    display_input = (typed_input.strip() + "\n\n" + summary).strip() if typed_input.strip() else summary
elif typed_input:
    display_input = typed_input

if not user_input and st.session_state.get("_pending_input"):
    user_input = st.session_state.pop("_pending_input")
    display_input = user_input

if user_input and memory_feature_enabled:
    remember_payload = extract_remember_command(typed_input or user_input)
    if remember_payload:
        saved, stored_line = add_explicit_memory(remember_payload)
        if saved:
            _cached_memory.clear()
            memory = _cached_memory()
            confirmation_lines = [
                "C'est noté, je m'en souviendrai pour toutes nos conversations.",
                "",
                "Détails ajoutés à la mémoire :",
            ]
            for line in stored_line.splitlines():
                line = line.strip()
                if line:
                    confirmation_lines.append(f"- {line}")
            confirmation = "\n".join(confirmation_lines)
            st.session_state.messages.append({"role": "user", "content": display_input or user_input})
            st.session_state.questions.append(user_input)
            log_id = log_question(
                question=user_input,
                response=confirmation,
                answered=True,
                num_docs_found=0,
                session_id=st.session_state.session_id,
                tools_used="memory_remember",
                sources="",
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": confirmation,
                    "log_id": log_id,
                    "details": "",
                    "sources": "",
                    "images": [],
                    "generated_files": [],
                }
            )
            st.session_state.responces.append(confirmation)
            st.session_state.feedback_by_log_id.setdefault(str(log_id), "")
            user_input = ""
            display_input = ""
            st.rerun()

    if user_input:
        updated, learned = auto_update_memory(st.session_state.session_id, user_input, "")
        if updated:
            st.session_state._memory_facts_notice = learned
            _cached_memory.clear()
            memory = _cached_memory()
            # Keep profile in sync with freshly learned facts so this turn's
            # grade/RAG logic can use them immediately.
            profile = str(memory.get("profile") or profile)
            memory_enabled = bool(memory.get("enabled") or memory_enabled)

if user_input and detect_simulator_intent(user_input):
    parcours_hint = (
        infer_parcours(user_input)
        or infer_parcours(str(memory.get("profile") or ""))
        or infer_parcours(" ".join(st.session_state.questions[-3:]))
    )
    open_simulator(parcours_hint)
    notice = (
        "J'ai ouvert le **simulateur 'Et si…'** plus haut dans cette page. "
        "Ajustez les sliders pour visualiser la validation, la compensation entre BCC et la moyenne du semestre."
    )
    _push_tool_response(
        user_input=user_input,
        display_input=display_input,
        response_text=notice,
        tool_name="grade_simulator_intent",
        auto_title="Simulateur de notes",
    )
    st.rerun()

if user_input and is_grade_intent(user_input):
    st.session_state.messages.append({"role": "user", "content": display_input or user_input})
    st.session_state.questions.append(user_input)
    parcours_hint = (
        infer_parcours(user_input)
        or infer_parcours(str(memory.get("profile") or ""))
        or infer_parcours(" ".join(st.session_state.questions[-3:]))
    )
    _start_moyenne_wizard(parcours_hint)
    notice = (
        "Bien sûr — je viens d'ouvrir l'assistant guidé **Calculer ma moyenne** "
        "dans cette page. Indiquez votre parcours et vos notes, puis envoyez le "
        "rapport dans le chat pour qu'on en discute."
    )
    log_id = log_question(
        question=user_input,
        response=notice,
        answered=True,
        num_docs_found=0,
        session_id=st.session_state.session_id,
        tools_used="grade_calculator_intent",
        sources="",
    )
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": notice,
            "log_id": log_id,
            "details": "",
            "sources": "",
            "images": [],
            "generated_files": [],
        }
    )
    st.session_state.responces.append(notice)
    st.session_state.feedback_by_log_id.setdefault(str(log_id), "")
    st.rerun()

if user_input:
    st.session_state.messages.append({"role": "user", "content": display_input or user_input})
    with st.chat_message("user"):
        st.markdown(display_input or user_input)

    st.session_state.questions.append(user_input)
    sources_block = ""
    details_parts = []
    tools_used = []
    image_results: list[dict[str, str]] = []
    generated_now: list[dict[str, object]] = []

    with st.chat_message("assistant"):
        placeholder = st.empty()
        final_response = "Je n'ai pas trouvé cette information dans les documents disponibles."
        docs = []

        if export_enabled and requested_export_formats(user_input):
            try:
                generated_now = create_requested_exports(user_input)
                st.session_state.generated_files.extend(generated_now)
                names = ", ".join(str(item["file_name"]) for item in generated_now)
                final_response = f"Voici le fichier demandé: {names}"
                tools_used.append("file_export")
                placeholder.markdown(final_response)
                render_file_downloads(generated_now, f"generated_now_{len(st.session_state.messages)}")
            except RuntimeError as exc:
                final_response = str(exc)
                placeholder.markdown(final_response)
        elif is_grade_query(user_input):
            final_response, grade_details = calculate_grade_response(user_input, memory_profile=profile)
            details_parts.append(grade_details)
            tools_used.append("grade_calculator")
            placeholder.markdown(final_response)
        else:
            retriever, _retriever_load_err = get_retriever_or_error()
            knowledge = ""
            rag_unavailable_notice = ""
            if retriever is None:
                tools_used.append("rag_unavailable")
                rag_unavailable_notice = (
                    "_Recherche documentaire indisponible_ — réponse basée sur la mémoire et les pièces jointes."
                )
                docs = []
            else:
                with st.status("Recherche dans les documents…", expanded=False) as status:
                    retrieval_history = build_session_history(
                        st.session_state.messages,
                        recent_turns=10,
                        max_chars_per_turn=450,
                        max_chars=3500,
                        older_snippets=4,
                        include_current_user_message=False,
                    )
                    queries = [user_input]
                    if query_expansion_enabled:
                        queries = expand_query_with_llm(
                            user_input,
                            history=retrieval_history,
                            llm_chain=get_llm_chain(),
                            max_variants=query_expansion_max_variants,
                        )
                        if len(queries) > 1:
                            tools_used.append("query_expansion")
                            details_parts.append(
                                "La recherche RAG a utilisé des reformulations de la question pour récupérer un contexte plus robuste."
                            )
                            status.update(label=f"Recherche avec {len(queries)} variantes…", state="running")
                    retrieved_docs = []
                    for query in queries:
                        retrieved_docs.extend(retriever.invoke(query))
                    docs = rerank(
                        user_input,
                        dedupe_documents(retrieved_docs),
                        top_k=final_context_k,
                        enabled=reranking_enabled,
                    )
                    status.update(label=f"Contexte prêt ({len(docs)} extraits)", state="complete")
                sources_block = build_sources_block(docs)
                knowledge = build_context(docs)
            if attachments:
                tools_used.append("attachment_inline")
                details_parts.append(
                    "Les pièces jointes ont été converties en texte et intégrées au message de l'utilisateur."
                )

            history = build_session_history(
                st.session_state.messages,
                recent_turns=15,
                max_chars_per_turn=600,
                max_chars=6000,
                older_snippets=8,
                include_current_user_message=False,
            )
            memory_active = bool(memory_feature_enabled and memory_enabled and profile.strip())
            memory_context = profile.strip() if memory_active else "Mémoire désactivée ou vide."

            knowledge_block = knowledge if knowledge else "Aucun extrait disponible (recherche documentaire indisponible ou hors-sujet)."

            rag_prompt = f"""
Tu es un assistant universitaire pour les étudiants du M1 Informatique UVSQ / Université Paris-Saclay.

Règles:
- La « Mémoire étudiant » fournie ci-dessous fait partie intégrante du contexte : utilise-la en priorité pour répondre aux questions personnelles (nom, âge, lieu, statut, parcours, UEs choisies, encadrant TER, notes...).
- L'« Historique utile » récapitule jusqu'à 15 derniers tours de la conversation en cours plus un résumé des sujets antérieurs : tu DOIS t'y référer pour reprendre un fil ouvert plus tôt (questions de suivi, pronoms comme « lui », « cette UE », « ma note précédente », etc.). Considère que l'utilisateur peut faire référence à n'importe quoi dit plus tôt dans cette session.
- Pour les questions universitaires (règlement, jury, contacts, dates...), réponds à partir des extraits RAG et du message de l'étudiant (incluant le contenu des fichiers joints).
- Si la mémoire contient déjà la réponse à une question personnelle, n'invente rien d'autre, ne dis jamais "je n'ai pas l'information" : cite simplement la valeur mémorisée.
- Si les extraits RAG sont absents et que la question dépend des documents officiels, réponds que la recherche documentaire est temporairement indisponible et propose à l'étudiant de reformuler ou d'attendre.
- Réponds en français, sauf si l'utilisateur écrit clairement dans une autre langue.
- N'inclus jamais les sources, citations, noms de fichiers ou la section "Sources consultees" dans la réponse. L'application les affiche séparément.
- Utilise un tableau Markdown quand cela améliore la lisibilité.
- Ne montre pas de raisonnement privé. Donne seulement la réponse finale.

Message de l'étudiant:
{user_input}

Mémoire étudiant:
{memory_context}

Historique utile:
{history}

Extraits RAG:
{knowledge_block}
            """.strip()

            response = ""
            had_context = bool(docs or attachments or memory_active)
            llm_chain = get_llm_chain()
            if not had_context and retriever is None:
                final_response = (
                    "La recherche dans les documents est indisponible et aucune mémoire n'est enregistrée. "
                    "Activez la mémoire dans la barre latérale ou réessayez quand le moteur d'embedding "
                    f"({EMBEDDING_MODEL}) sera disponible."
                )
            elif had_context and not llm_chain:
                final_response = "Aucun modèle LLM n'est disponible. Configurez vLLM ou GEMINI_API_KEY."
            elif had_context:
                last_error: Exception | None = None
                with st.status("Génération de la réponse…", expanded=False) as gen_status:
                    for client in llm_chain:
                        response = ""
                        try:
                            for chunk in client.stream(rag_prompt):
                                response += getattr(chunk, "content", "") or ""
                                placeholder.markdown(response)
                            if response.strip():
                                final_response = response.strip()
                                last_error = None
                                break
                        except Exception as exc:
                            last_error = exc
                            continue
                    gen_status.update(label="Réponse prête", state="complete")
                if last_error is not None and not response.strip():
                    final_response = "Le serveur LLM n'est pas disponible pour le moment."
            final_response = clean_answer_text(final_response)
            if rag_unavailable_notice and final_response and not final_response.startswith(rag_unavailable_notice):
                final_response = f"{rag_unavailable_notice}\n\n{final_response}"
            placeholder.markdown(final_response)

        details = "\n\n".join(part for part in details_parts if part)
        answered = not is_unanswered_response(final_response, min_word_count=0)
        log_id = log_question(
            question=user_input,
            response=final_response,
            answered=answered,
            num_docs_found=len(docs),
            session_id=st.session_state.session_id,
            tools_used=", ".join(tools_used) if tools_used else "rag",
            sources=sources_block,
        )
        try:
            sid = st.session_state.session_id
            if not st.session_state.get(f"_titled_{sid}"):
                generated_title = make_conversation_title(user_input, get_llm_chain())
                if generated_title and rename_if_default(sid, generated_title):
                    _cached_conversations.clear()
                st.session_state[f"_titled_{sid}"] = True
        except Exception:
            pass
        st.session_state.responces.append(final_response)
        assistant_message = {
            "role": "assistant",
            "content": final_response,
            "log_id": log_id,
            "details": details,
            "sources": sources_block,
            "images": image_results,
            "generated_files": generated_now,
        }
        st.session_state.feedback_by_log_id.setdefault(str(log_id), "")
        st.session_state.messages.append(assistant_message)
        render_assistant_actions(final_response, log_id, f"actions_new_{log_id}", voice_output_enabled)
        if details or sources_block or image_results:
            with st.expander("Sources consultées", expanded=False):
                if details:
                    st.markdown(details)
                if sources_block:
                    st.markdown(format_sources_for_display(sources_block))
                for image_result in image_results:
                    if image_result.get("thumbnail"):
                        st.image(image_result["thumbnail"], caption=image_result.get("title") or image_result.get("link"))
                    st.markdown(f"[{image_result.get('title')}]({image_result.get('link')})")
