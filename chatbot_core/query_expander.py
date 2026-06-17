"""Optional query expansion for RAG retrieval.

The older project had a "rerasker" idea that generated alternate phrasings
before retrieval. This module keeps that useful behavior, but routes it through
the already configured LLM chain and never stores provider keys in code.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def parse_query_variants(raw_text: str, *, max_variants: int = 5) -> list[str]:
    """Parse an LLM response into clean query variants."""
    variants: list[str] = []
    seen: set[str] = set()
    for raw_line in (raw_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]|\d+[.)]|\[\d+\])\s*", "", line).strip()
        line = line.strip("\"'` ")
        if not line or not any(ch.isalpha() for ch in line):
            continue
        key = re.sub(r"\s+", " ", line).casefold()
        if key in seen:
            continue
        seen.add(key)
        variants.append(line)
        if len(variants) >= max_variants:
            break
    return variants


def expand_query_with_llm(
    user_question: str,
    *,
    history: str = "",
    llm_chain: Sequence[object] | None = None,
    max_variants: int = 5,
) -> list[str]:
    """Return the original question plus LLM-generated retrieval variants.

    If no LLM is available or generation fails, the function returns only the
    original question so the normal RAG path remains unchanged.
    """
    question = (user_question or "").strip()
    if not question:
        return []
    if not llm_chain:
        return [question]

    prompt = f"""
Tu reformules une question pour ameliorer une recherche RAG dans des documents universitaires.

Question actuelle:
{question}

Historique utile:
{history or "Aucun historique utile."}

Genere exactement {max_variants} variantes courtes qui gardent la meme intention.
Si la question fait reference a une reponse precedente, rends la variante autonome avec le contexte utile.
Ecris uniquement une variante par ligne, sans explication.
    """.strip()

    for client in llm_chain:
        try:
            response = client.invoke(prompt)
            variants = parse_query_variants(_response_text(response), max_variants=max_variants)
            break
        except Exception:
            variants = []
            continue
    else:
        variants = []

    ordered = [question, *variants]
    seen: set[str] = set()
    deduped: list[str] = []
    for item in ordered:
        key = re.sub(r"\s+", " ", item.strip()).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item.strip())
    return deduped


def dedupe_documents(docs: Iterable[object]) -> list[object]:
    """Deduplicate LangChain documents while preserving first-seen order."""
    seen: set[tuple[object, object, object, int]] = set()
    unique: list[object] = []
    for doc in docs:
        metadata = getattr(doc, "metadata", {}) or {}
        content = getattr(doc, "page_content", "") or ""
        key = (
            metadata.get("source") or metadata.get("source_name"),
            metadata.get("page"),
            metadata.get("section"),
            hash(content),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique
