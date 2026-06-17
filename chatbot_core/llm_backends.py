"""Ordre des backends LLM partagé entre chatbot Streamlit et evaluate_chatbot."""

from __future__ import annotations

import os
from typing import Any, List, Optional, Sequence

from langchain_openai import ChatOpenAI

# Chaîne par défaut (IDs type passerelle OpenAI) : rapide → plus fort → raisonnement lent.
# Réordonnez via OPENAI_COMPAT_MODELS dans .env si votre fournisseur expose d’autres noms.
OPENAI_COMPAT_DEFAULT_MODEL_CHAIN: tuple[str, ...] = (
    "deepseek-chat",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "claude-sonnet-4-6",
    "flagship-chat",
    "mistral-medium-latest",
    "deepseek-reasoner",
)


def _truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def resolve_compat_model_names() -> List[str]:
    """
    Ordre des modèles pour une même base URL + clé (secours successifs).
    Priorité : OPENAI_COMPAT_MODELS (CSV) > OPENAI_COMPAT_MODEL > chaîne OPENAI_COMPAT_DEFAULT si MULTI.
    """
    raw = os.getenv("OPENAI_COMPAT_MODELS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    single = os.getenv("OPENAI_COMPAT_MODEL", "").strip()
    if single:
        return [single]
    if _truthy(os.getenv("OPENAI_COMPAT_MULTI", "")):
        return list(OPENAI_COMPAT_DEFAULT_MODEL_CHAIN)
    return []


def _unique_preserve(names: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _clients_for_endpoint(
    base_url: str,
    api_key: str,
    model_names: List[str],
    *,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> List[ChatOpenAI]:
    if not base_url or not api_key or not model_names:
        return []
    base_url = base_url.rstrip("/")
    clients: List[ChatOpenAI] = []
    for model in _unique_preserve(model_names):
        clients.append(
            ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
            )
        )
    return clients


def build_openai_compat_chat_list(
    *,
    temperature: float,
    max_tokens: int,
) -> List[ChatOpenAI]:
    """Un ou plusieurs clients (même passerelle, modèles différents) pour enchaîner les secours."""
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip()
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
    if not base_url or not api_key:
        return []
    timeout = int(os.getenv("OPENAI_COMPAT_TIMEOUT", "90"))
    names = resolve_compat_model_names()
    if not names:
        names = ["deepseek-chat"]
    return _clients_for_endpoint(
        base_url, api_key, names, temperature=temperature, max_tokens=max_tokens, timeout=timeout
    )


def build_openai_compat2_chat_list(
    *,
    temperature: float,
    max_tokens: int,
) -> List[ChatOpenAI]:
    """Deuxième passerelle optionnelle (autre URL / autre clé)."""
    base_url = os.getenv("OPENAI_COMPAT2_BASE_URL", "").strip()
    api_key = os.getenv("OPENAI_COMPAT2_API_KEY", "").strip()
    if not base_url or not api_key:
        return []
    timeout = int(os.getenv("OPENAI_COMPAT2_TIMEOUT", os.getenv("OPENAI_COMPAT_TIMEOUT", "90")))
    raw = os.getenv("OPENAI_COMPAT2_MODELS", "").strip()
    if raw:
        names = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        names = resolve_compat_model_names() or ["deepseek-chat"]
    return _clients_for_endpoint(
        base_url, api_key, names, temperature=temperature, max_tokens=max_tokens, timeout=timeout
    )


def build_all_openai_compat_chat_list(
    *,
    temperature: float,
    max_tokens: int,
) -> List[ChatOpenAI]:
    return [
        *build_openai_compat_chat_list(temperature=temperature, max_tokens=max_tokens),
        *build_openai_compat2_chat_list(temperature=temperature, max_tokens=max_tokens),
    ]


def build_openai_compat_chat(
    *,
    temperature: float,
    max_tokens: int,
) -> Optional[ChatOpenAI]:
    """Rétrocompat : premier client OpenAI-compatible, ou None."""
    lst = build_openai_compat_chat_list(temperature=temperature, max_tokens=max_tokens)
    return lst[0] if lst else None


def generation_llm_order(
    *,
    vllm_reachable: bool,
    vllm_llm: Any,
    openai_compat_llms: Optional[Sequence[Any]],
    tertiary_llm: Any,
) -> List[Any]:
    """
    Priorité release : Gemini / cloud principal (``tertiary_llm``), puis les
    passerelles OpenAI-compatibles, puis le serveur vLLM UVSQ si joignable.
    Le client vLLM reste en dernier recours meme si la sonde etait negative
    afin de permettre un mode force ou un tunnel qui vient de demarrer.
    """
    ordered: List[Any] = []
    if tertiary_llm is not None:
        ordered.append(tertiary_llm)
    if openai_compat_llms:
        for c in openai_compat_llms:
            if c is not None:
                ordered.append(c)
    if vllm_reachable and vllm_llm is not None:
        ordered.append(vllm_llm)
    if vllm_llm is not None and vllm_llm not in ordered:
        ordered.append(vllm_llm)

    seen: set[int] = set()
    out: List[Any] = []
    for m in ordered:
        mid = id(m)
        if mid not in seen:
            seen.add(mid)
            out.append(m)
    return out
