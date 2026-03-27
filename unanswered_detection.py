import re
import unicodedata


UNANSWERED_KEYWORDS = [
    # Francais
    "je ne sais pas", "je n'ai pas", "pas d'information",
    "ne contient pas", "ne precise pas", "ne precisent pas",
    "ne mentionne pas", "ne mentionnent pas",
    "pas trouve", "aucune information", "je ne trouve pas",
    "ne contient aucune", "ne contiennent pas",
    "ne permet pas de repondre", "ne fournit pas",
    "ne fournissent pas", "pas mentionne",
    "n'est pas presente dans les documents fournis",
    "les informations fournies ne precisent pas",
    "n'est pas fournie dans les documents",
    "desole", "je ne peux pas", "impossible de repondre",
    "pas disponible", "pas dans les informations",
    "hors du contexte", "pas de reponse",
    # Anglais
    "i don't know", "no information", "i cannot", "i can't",
    "not found", "no relevant", "sorry",
    "does not contain", "do not contain",
    "not mentioned", "not available",
    "cannot answer", "unable to answer",
    "does not provide", "not in the provided",
]

UNANSWERED_PATTERNS = [
    r"\bje ne sais pas\b",
    r"\bi don't know\b",
    r"\b(?:aucune|pas de|pas d') information\b",
    r"\bne (?:contient|contiennent|mentionne|mentionnent|precise|precisent|fournit|fournissent) pas\b",
    r"\b(?:n'est|ne sont) pas (?:fourni|fournie|fournies|indique|indiquee|indiquees|mentionne|mentionnee)\b",
    r"\b(?:impossible|unable|cannot|can't) (?:de )?repondre\b",
    r"\bhors du contexte\b",
    r"\bnot available\b",
    r"\bnot in (?:the )?provided\b",
]


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().replace("’", "'").strip()


def is_unanswered_response(response: str, min_word_count: int = 0) -> bool:
    normalized_response = normalize_text(response)

    if not normalized_response:
        return True

    if min_word_count > 0 and len(normalized_response.split()) < min_word_count:
        return True

    if any(keyword in normalized_response for keyword in UNANSWERED_KEYWORDS):
        return True

    return any(re.search(pattern, normalized_response) for pattern in UNANSWERED_PATTERNS)
