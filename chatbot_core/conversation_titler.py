"""Auto-generate a short, human-friendly title for a conversation.

We try the LLM chain first ("summarize this in 4 words, French, no punctuation").
If no LLM is available or the call raises, we fall back to a deterministic
heuristic that strips French stop-words, keeps capitalised proper nouns,
and trims to a sensible length.

The function is intentionally tolerant: it never raises, never blocks the chat,
and returns a string that is always safe to store in the SQLite ``title``
column.
"""

from __future__ import annotations

import re

_FR_STOPWORDS = {
    "a", "à", "ai", "ans", "au", "aux", "avec", "avoir", "ce", "ces", "c'est", "cest",
    "comme", "comment", "dans", "de", "des", "du", "ée", "elle", "en", "est", "et",
    "être", "etre", "il", "ils", "j'", "j'ai", "je", "la", "le", "les", "leur",
    "leurs", "lui", "ma", "mais", "me", "mes", "mon", "n'", "ne", "nos", "notre",
    "nous", "on", "ou", "où", "par", "pas", "pour", "qu'", "que", "quel", "quels",
    "quelle", "quelles", "qui", "sa", "sans", "se", "ses", "si", "sur", "ta", "te",
    "tes", "ton", "toute", "toutes", "tu", "un", "une", "vos", "votre", "vous",
    "this", "that", "the", "a", "an", "is", "are", "for", "with", "what", "which",
    "how", "why", "when", "where",
}

_TRIVIAL_LEADS = (
    "salut",
    "bonjour",
    "hello",
    "hey",
    "hi",
    "coucou",
    "yo",
    "merci",
    "thanks",
)

_MAX_TITLE_CHARS = 60
_MAX_TITLE_WORDS = 6


def _strip_punct_edges(s: str) -> str:
    return s.strip(" \t\r\n.,;:!?…-«»\"'`()[]{}")


def heuristic_title(text: str, max_words: int = _MAX_TITLE_WORDS) -> str:
    """Deterministic fallback: short title from the most informative tokens."""
    if not text:
        return "Nouvelle conversation"
    one_liner = re.sub(r"\s+", " ", text).strip()
    one_liner = _strip_punct_edges(one_liner)
    if not one_liner:
        return "Nouvelle conversation"

    # If the message is very short, just title-case it as-is.
    words = one_liner.split(" ")
    if len(words) <= max_words and len(one_liner) <= _MAX_TITLE_CHARS:
        return one_liner[:_MAX_TITLE_CHARS]

    # Drop polite leading words like "salut, bonjour".
    while words and words[0].lower().rstrip(",.!?;:") in _TRIVIAL_LEADS:
        words.pop(0)

    keepers: list[str] = []
    seen: set[str] = set()
    for raw in words:
        token = _strip_punct_edges(raw)
        if not token:
            continue
        lowered = token.lower()
        if lowered in _FR_STOPWORDS and len(keepers) > 0:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        keepers.append(token)
        if len(keepers) >= max_words:
            break

    if not keepers:
        return one_liner[:_MAX_TITLE_CHARS]
    candidate = " ".join(keepers)
    if len(candidate) > _MAX_TITLE_CHARS:
        candidate = candidate[: _MAX_TITLE_CHARS - 1].rstrip() + "…"
    return candidate


def llm_title(first_message: str, llm_chain) -> str | None:
    """Try the LLM chain to summarise ``first_message`` in <= 6 French words.

    Returns ``None`` if no LLM is available or every backend fails. The chain
    is the same iterable that ``chatbot.py`` already constructs (each item
    must implement an ``invoke`` returning an object with ``.content``).
    """
    if not first_message or not llm_chain:
        return None
    prompt = (
        "Donne un titre TRÈS court (max 6 mots, en français, sans guillemets, "
        "sans ponctuation finale, sans emoji) qui résume cette question d'un "
        "étudiant. Réponds UNIQUEMENT avec le titre.\n\n"
        f"Question: {first_message.strip()[:500]}\n\nTitre:"
    )
    for client in llm_chain:
        try:
            result = client.invoke(prompt)
            content = getattr(result, "content", None) or str(result)
            content = (content or "").strip()
            if not content:
                continue
            content = content.splitlines()[0].strip()
            content = _strip_punct_edges(content)
            content = re.sub(r"^titre\s*[:\-–]\s*", "", content, flags=re.IGNORECASE)
            content = _strip_punct_edges(content)
            if content:
                if len(content) > _MAX_TITLE_CHARS:
                    content = content[: _MAX_TITLE_CHARS - 1].rstrip() + "…"
                return content
        except Exception:
            continue
    return None


def make_conversation_title(first_message: str, llm_chain=None) -> str:
    """Return the best available title for ``first_message``.

    Uses the LLM if it's reachable, otherwise the heuristic. Always returns a
    non-empty string so callers can persist it directly.
    """
    candidate = llm_title(first_message, llm_chain) if llm_chain else None
    if candidate:
        return candidate
    return heuristic_title(first_message)


__all__ = ["make_conversation_title", "heuristic_title", "llm_title"]
