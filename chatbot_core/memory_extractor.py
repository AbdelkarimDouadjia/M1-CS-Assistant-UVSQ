"""Heuristic memory extractor for the M1 assistant.

The student does not need to maintain the profile field manually anymore: every
turn, this module scans the latest user message for stable facts (name, age,
location, status, parcours, chosen optional UEs, current semester, interests)
and merges any new line into the persisted ``student_memory`` profile.

The user can also save free-form notes the way ChatGPT does, by typing
something like ``souviens-toi que ...``, ``n'oublie pas que ...``,
``remember that ...`` or ``/remember ...``. These are caught by
:func:`extract_remember_command` and saved verbatim under ``Note : ...``.

The extractor is intentionally conservative for unrelated chat, but explicit
profile facts are treated as the latest truth. If the user first says
``my name is Abdelkarim`` and later says ``my new name is Riadh``, the stored
``Nom : ...`` line is replaced instead of duplicated.
"""

from __future__ import annotations

import re
from typing import Iterable

from chatbot_core.chat_logger import GLOBAL_MEMORY_KEY, get_memory, save_memory
from chatbot_core.grade_calculator import infer_parcours

# Heuristic keywords for optional UEs (BO + signature S2 modules)
_BO_HINTS = {
    "Méthodes de Ranking": {"ranking"},
    "Simulation": {"simulation"},
    "Tuning de BD": {"tuning"},
    "Conception de BD": {"conception de bd", "conception bd"},
    "Protocoles IP": {"protocoles ip", "protocole ip"},
    "Réseaux étendus": {"reseaux etendus", "réseaux étendus", "wan"},
    "Application Web et Sécurité": {"application web", "app web", "web et securite", "web et sécurité"},
    "Calcul Sécurisé": {"calcul securise", "calcul sécurisé"},
    "Analyses des données EVRY": {"evry", "analyse des donnees", "analyse des données"},
}

_SEMESTER_HINTS = [
    (re.compile(r"\bs\s*1\b|semestre\s*1|semester\s*1", re.IGNORECASE), "Semestre actuel : S1"),
    (re.compile(r"\bs\s*2\b|semestre\s*2|semester\s*2", re.IGNORECASE), "Semestre actuel : S2"),
]

_PARCOURS_PATTERNS = [
    re.compile(r"je\s+suis\s+(?:en|en\s+m1)\s+([A-Za-zÀ-ÿ]+)", re.IGNORECASE),
    re.compile(r"i\s+am\s+(?:in|doing)\s+([A-Za-zÀ-ÿ]+)", re.IGNORECASE),
    re.compile(r"mon\s+parcours\s+(?:est|c'est)\s+([A-Za-zÀ-ÿ]+)", re.IGNORECASE),
]

# Up to "stop" tokens we use to cut a captured group cleanly (comma, end of
# sentence, conjunctions, "en status ..." trailing phrase, etc.).
_STOP_GROUP = r"(?:[,;.!?]|\bet\b|\band\b|\bou\b|\bor\b|\s+en\s+(?:statut|status)\b|$)"

_NAME_PATTERNS = [
    re.compile(rf"\b(?:mon\s+nouveau\s+nom|mon\s+nouveau\s+prenom|mon\s+nouveau\s+prénom)\s+(?:est|c['’]est)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\b(?:my\s+new\s+name|my\s+new\s+first\s+name)\s+is\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\b(?:change|update|set)\s+my\s+name\s+(?:to|as)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\b(?:appelle[-\s]?moi|appelez[-\s]?moi)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bje\s+m['’]\s*appelle\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bmon\s+(?:nom|prenom|prénom)(?:\s+complet)?\s+(?:est|c['’]est)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    # Lenient catch for the typo "mon est X" (missing "nom").
    re.compile(rf"\bmon\s+est\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bmy\s+name\s+is\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bnow\s+my\s+name\s+is\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bi['’]m\s+called\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s]*?){_STOP_GROUP}", re.IGNORECASE),
]

_AGE_PATTERNS = [
    re.compile(r"\bj['’]?\s*ai\s+(?P<value>\d{1,3})\s*ans?\b", re.IGNORECASE),
    re.compile(r"\bi['’]m\s+(?P<value>\d{1,3})\s+years?\s+old\b", re.IGNORECASE),
    re.compile(r"\bi\s+am\s+(?P<value>\d{1,3})\s+years?\s+old\b", re.IGNORECASE),
    re.compile(r"\bmy\s+age\s+is\s+(?P<value>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bmon\s+age\s+(?:est|c['’]est)\s+(?P<value>\d{1,3})\b", re.IGNORECASE),
]

_LOCATION_PATTERNS = [
    re.compile(rf"\bj['’]?\s*habite\s+(?:à|au|aux|en|dans|chez)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s,'.]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bje\s+vis\s+(?:à|au|aux|en|dans)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s,'.]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bje\s+suis\s+(?:en|à|au|aux|dans)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s,'.]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bi\s+live\s+in\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s,'.]*?){_STOP_GROUP}", re.IGNORECASE),
    re.compile(rf"\bi['’]m\s+(?:in|from)\s+(?P<value>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-\s,'.]*?){_STOP_GROUP}", re.IGNORECASE),
]

# Words we do NOT want to capture as a "location" because they belong to other
# patterns (parcours, status, semester...).
_LOCATION_BLOCKLIST = {
    "m1",
    "m2",
    "l1",
    "l2",
    "l3",
    "s1",
    "s2",
    "etudiant",
    "etudiante",
    "stagiaire",
    "salarie",
    "salariee",
    "alternant",
    "alternante",
    "apprenti",
    "apprentie",
    "doctorant",
    "doctorante",
    "datascale",
    "amis",
    "smart",
    "stl",
    "ml",
    "informatique",
    "master",
}

_TER_ENCADRANT_PATTERN = re.compile(
    r"(?:staff|encadrant|tuteur|supervisor|responsable).{0,48}?\bter\b.{0,24}?(?:is|est|c'est|sont|sera)\s*:?\s*"
    r"(?:m\.|mr\.?|monsieur|madame|mme|ms\.?)\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{1,40})",
    re.IGNORECASE | re.DOTALL,
)
_TER_ENCADRANT_PATTERN_2 = re.compile(
    r"\b(?:ter|TER)\b.{0,30}?(?:is|est|c'est)\s*:?\s*(?:m\.|mr\.?|monsieur|madame|mme)\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{1,40})",
    re.IGNORECASE | re.DOTALL,
)

_STATUS_PATTERNS = [
    re.compile(r"\b(?:en\s+(?:statut|status))\s+(?P<value>[A-Za-zÀ-ÿ\-]+(?:\s+[A-Za-zÀ-ÿ\-]+)?)", re.IGNORECASE),
    re.compile(r"\bmon\s+statut\s+(?:est|c['’]est)\s+(?P<value>[A-Za-zÀ-ÿ\-]+(?:\s+[A-Za-zÀ-ÿ\-]+)?)", re.IGNORECASE),
    re.compile(r"\bje\s+suis\s+(?P<value>étudiant|étudiante|etudiant|etudiante|stagiaire|salarié|salariée|salarie|salariee|alternant|alternante|apprenti|apprentie|doctorant|doctorante|en\s+stage|en\s+alternance)\b", re.IGNORECASE),
    re.compile(r"\bi\s+am\s+a[n]?\s+(?P<value>student|intern|employee|apprentice|phd\s+student)\b", re.IGNORECASE),
]

_REMEMBER_PATTERNS = [
    re.compile(r"^\s*(?:souviens[-\s]?toi|rappelle[-\s]?toi|retiens|n['’]oublie\s+pas|note\s+(?:bien)?|memorise|mémorise)\s+(?:que\s+|de\s+|du\s+|d['’])?(?P<value>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:remember|please\s+remember)(?:\s+that)?\s+(?P<value>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*/remember\s+(?P<value>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*/mem(?:ory)?\s+(?P<value>.+?)\s*$", re.IGNORECASE),
]


def _existing_lines(profile: str) -> list[str]:
    return [line.strip() for line in (profile or "").splitlines() if line.strip()]


def _has_line(profile: str, prefix: str) -> bool:
    return any(line.lower().startswith(prefix.lower()) for line in _existing_lines(profile))


def _existing_value(profile: str, *prefixes: str) -> str:
    for line in _existing_lines(profile):
        lowered = line.lower()
        if any(lowered.startswith(prefix.lower()) for prefix in prefixes):
            return line.split(":", 1)[-1].strip() if ":" in line else ""
    return ""


def _should_store_value(profile: str, value: str, *prefixes: str) -> bool:
    existing = _existing_value(profile, *prefixes)
    return bool(value) and _normalize(existing) != _normalize(value)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _clean_capture(value: str) -> str:
    """Tidy a captured fragment: trim spaces, collapse whitespace, strip ending punctuation."""
    cleaned = re.sub(r"\s+", " ", value or "").strip(" .,;:!?\t\n\r-")
    return cleaned


def _capture_name(text: str) -> str:
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        candidate = _clean_capture(match.group("value"))
        if not candidate or len(candidate) < 2 or len(candidate) > 60:
            continue
        # Reject obvious non-name captures (e.g. "complet", "encore", numbers).
        if any(ch.isdigit() for ch in candidate):
            continue
        return candidate.title()
    return ""


def _capture_age(text: str) -> str:
    for pattern in _AGE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            value = int(match.group("value"))
        except (TypeError, ValueError):
            continue
        if 5 <= value <= 110:
            return f"{value} ans"
    return ""


# Splits a captured location chunk like "france maintenant a paris" into
# ["france", "paris"]. Connector words come from the same family we use to
# strip trailing words below.
_LOCATION_SPLITTER = re.compile(
    r"\s+(?:maintenant|actuellement|now|currently|aujourd['’]hui|près\s+de|pres\s+de)\s+(?:à|a|au|aux|en|dans|chez|in|near)?\s+|"
    r"\s*,\s*|"
    r"\s+(?:à|a|au|aux|en|dans|chez|in|near)\s+",
    re.IGNORECASE,
)


def _capture_locations(text: str) -> list[str]:
    seen: list[str] = []

    def _push(raw: str) -> None:
        words = raw.split()
        while words and words[-1].lower() in {"maintenant", "à", "a", "au", "aux", "en", "dans"}:
            words.pop()
        while words and words[0].lower() in {"maintenant", "à", "a", "au", "aux", "en", "dans"}:
            words.pop(0)
        cleaned = " ".join(words).strip(" .,;:!?")
        if not cleaned or len(cleaned) > 60:
            return
        normalized = _normalize(cleaned)
        if normalized in _LOCATION_BLOCKLIST:
            return
        if any(token in _LOCATION_BLOCKLIST for token in normalized.split()):
            return
        pretty = cleaned.title()
        if pretty not in seen:
            seen.append(pretty)

    for pattern in _LOCATION_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _clean_capture(match.group("value"))
            if not candidate:
                continue
            for piece in _LOCATION_SPLITTER.split(candidate):
                _push(piece or "")
    return seen


def _capture_ter_encadrant(text: str) -> str:
    """Extract TER supervisor name from phrases like « staff for the ter is Mr Lopes »."""
    for pattern in (_TER_ENCADRANT_PATTERN, _TER_ENCADRANT_PATTERN_2):
        match = pattern.search(text)
        if not match:
            continue
        name = _clean_capture(match.group(1))
        if 2 <= len(name) <= 50:
            return name.title()
    return ""


def _capture_status(text: str) -> str:
    for pattern in _STATUS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        candidate = _clean_capture(match.group("value"))
        if not candidate or len(candidate) > 40:
            continue
        return candidate.lower()
    return ""


def extract_remember_command(text: str) -> str:
    """Return the free-form content the user asked the bot to remember.

    Returns an empty string when the message is not an explicit memory command.
    """
    if not text:
        return ""
    stripped = text.strip()
    for pattern in _REMEMBER_PATTERNS:
        match = pattern.match(stripped)
        if match:
            content = _clean_capture(match.group("value"))
            if content:
                return content
    return ""


def extract_facts(text: str, existing_profile: str = "") -> list[str]:
    """Return the list of new bullet lines to append to the profile."""
    if not text:
        return []
    facts: list[str] = []
    normalized = _normalize(text)

    name = _capture_name(text)
    if _should_store_value(existing_profile, name, "Nom :"):
        facts.append(f"Nom : {name}")

    age = _capture_age(text)
    if _should_store_value(existing_profile, age, "Âge :", "Age :"):
        facts.append(f"Âge : {age}")

    locations = _capture_locations(text)
    if locations:
        existing_loc = next(
            (line for line in _existing_lines(existing_profile) if line.lower().startswith("lieu")),
            "",
        )
        already_listed = {item.strip().lower() for item in existing_loc.split(":", 1)[-1].split(",") if item.strip()}
        new_items = [loc for loc in locations if loc.lower() not in already_listed]
        if new_items:
            merged = (
                [item.strip() for item in existing_loc.split(":", 1)[-1].split(",") if item.strip()]
                + new_items
            )
            seen: set[str] = set()
            ordered: list[str] = []
            for item in merged:
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(item)
            facts.append("Lieu : " + ", ".join(ordered))

    status = _capture_status(text)
    if _should_store_value(existing_profile, status, "Statut :"):
        facts.append(f"Statut : {status}")

    parcours = infer_parcours(text)
    if not parcours:
        for pattern in _PARCOURS_PATTERNS:
            match = pattern.search(text)
            if match:
                parcours = infer_parcours(match.group(1))
                if parcours:
                    break
    if _should_store_value(existing_profile, parcours or "", "Parcours :"):
        facts.append(f"Parcours : {parcours}")

    for pattern, line in _SEMESTER_HINTS:
        if pattern.search(text) and _should_store_value(
            existing_profile,
            line.split(":", 1)[-1].strip(),
            "Semestre actuel :",
            "Semestre :",
        ):
            facts.append(line)
            break

    chosen: list[str] = []
    for ue_name, keywords in _BO_HINTS.items():
        if any(keyword in normalized for keyword in keywords):
            chosen.append(ue_name)
    if chosen:
        existing_bo = next(
            (line for line in _existing_lines(existing_profile) if line.lower().startswith("ues choisies")),
            "",
        )
        already_listed = {item.strip() for item in existing_bo.split(":", 1)[-1].split(",") if item.strip()}
        new_items = [ue for ue in chosen if ue not in already_listed]
        if new_items:
            merged = sorted(set(list(already_listed) + new_items))
            line = "UEs choisies : " + ", ".join(merged)
            facts.append(line)

    ter_enc = _capture_ter_encadrant(text)
    if _should_store_value(existing_profile, ter_enc, "Encadrant TER"):
        facts.append(f"Encadrant TER : {ter_enc}")

    return facts


def _apply_facts(profile: str, facts: Iterable[str]) -> str:
    new_profile_lines = _existing_lines(profile)
    for fact in facts:
        lower = fact.lower()
        # Replace single-value facts when the user gives a newer value.
        if lower.startswith("nom"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("nom")
            ]
        elif lower.startswith("âge") or lower.startswith("age"):
            new_profile_lines = [
                line
                for line in new_profile_lines
                if not (line.lower().startswith("âge") or line.lower().startswith("age"))
            ]
        elif lower.startswith("statut"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("statut")
            ]
        elif lower.startswith("parcours"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("parcours")
            ]
        elif lower.startswith("semestre"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("semestre")
            ]
        elif lower.startswith("encadrant ter"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("encadrant ter")
            ]
        # Replace any previous "UEs choisies" or "Lieu" line if a newer one is broader.
        elif lower.startswith("ues choisies"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("ues choisies")
            ]
        elif lower.startswith("lieu"):
            new_profile_lines = [
                line for line in new_profile_lines if not line.lower().startswith("lieu")
            ]
        new_profile_lines.append(fact)
    return "\n".join(new_profile_lines).strip()


def auto_update_memory(
    session_id: str | None,
    user_text: str,
    assistant_text: str = "",
) -> tuple[bool, list[str]]:
    """Persist any new facts found in the message into ``student_memory``.

    ``session_id`` is accepted for backward compatibility, but writes are sent
    to the *global* memory row so every conversation shares the same profile.

    Returns ``(updated, new_lines)`` so the UI can show a toast when something
    is learned.
    """
    if not user_text:
        return False, []
    storage_key = GLOBAL_MEMORY_KEY  # Memory is intentionally global.
    memory = get_memory(storage_key)
    profile = str(memory.get("profile") or "")
    new_facts = extract_facts(user_text, existing_profile=profile)
    if assistant_text:
        new_facts.extend(
            extract_facts(
                assistant_text,
                existing_profile=profile + "\n" + "\n".join(new_facts),
            )
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for fact in new_facts:
        key = fact.strip().lower()
        if key and key not in seen:
            deduped.append(fact.strip())
            seen.add(key)
    if not deduped:
        return False, []
    new_profile = _apply_facts(profile, deduped)
    save_memory(storage_key, True, new_profile)
    return True, deduped


def add_explicit_memory(content: str) -> tuple[bool, str]:
    """Append a free-form note from an explicit "remember that ..." command.

    Returns ``(saved, stored_line)`` so the UI can echo what was persisted.
    """
    content = (content or "").strip().rstrip(".")
    if not content:
        return False, ""
    storage_key = GLOBAL_MEMORY_KEY
    memory = get_memory(storage_key)
    profile = str(memory.get("profile") or "")
    # First, try to interpret the note as a structured fact so we get a clean
    # "Nom : ..." / "Lieu : ..." line instead of a generic "Note : ..." entry.
    structured = extract_facts(content, existing_profile=profile)
    new_lines = structured if structured else [f"Note : {content}"]
    deduped: list[str] = []
    seen: set[str] = set()
    profile_lower = {line.lower() for line in _existing_lines(profile)}
    for fact in new_lines:
        key = fact.strip().lower()
        if key in seen or key in profile_lower:
            continue
        seen.add(key)
        deduped.append(fact.strip())
    if not deduped:
        # Even with no new structured fact, we still want to remember the
        # raw note so the user feels heard.
        deduped = [f"Note : {content}"]
    new_profile = _apply_facts(profile, deduped)
    save_memory(storage_key, True, new_profile)
    return True, "\n".join(deduped)


def warm_memory_from_history(session_id: str, history_messages: Iterable[str]) -> int:
    """Replay history (oldest first) through the extractor on a new session.

    Returns the number of facts learned. Useful when the user clicks an old
    conversation: the profile gets rebuilt from past Q&As so the assistant
    "remembers" them even on a brand-new session.
    """
    if not session_id:
        return 0
    total = 0
    for text in history_messages:
        updated, new_lines = auto_update_memory(session_id, text or "", "")
        if updated:
            total += len(new_lines)
    return total
