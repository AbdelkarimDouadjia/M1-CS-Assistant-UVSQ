"""In-session conversation memory.

The chatbot used to send only the last 3 question/answer pairs to the LLM.
This module produces a much richer rolling history so the assistant can
recall information mentioned 20+ turns ago in the *same* chat session
without blowing up the prompt.

Strategy:
  * Keep the most recent ``recent_turns`` Q/A pairs verbatim (truncated
    per-turn so a giant essay doesn't dominate the budget).
  * For everything older, build a compact deterministic summary line that
    enumerates the topics seen so far, plus a few short question snippets.
  * Enforce a global ``max_chars`` budget so the prompt stays predictable.

The output is a single Markdown-flavored string ready to drop into a
prompt template (we already have a "Historique utile:" section).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

_DEFAULT_RECENT_TURNS = 15
_DEFAULT_MAX_CHARS_PER_TURN = 600
_DEFAULT_MAX_CHARS = 6000
_DEFAULT_OLDER_SNIPPETS = 6

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class ConversationTurn:
    """A user-question / assistant-answer pair extracted from messages."""

    question: str
    answer: str


def _clean(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "")).strip()


def _truncate(text: str, max_chars: int) -> str:
    text = _clean(text)
    if len(text) <= max_chars:
        return text
    head = text[: max(0, max_chars - 1)].rstrip()
    return f"{head}…"


def pair_messages(messages: Sequence[dict]) -> list[ConversationTurn]:
    """Walk a Streamlit-style message list and pair user with assistant.

    The chat log alternates user / assistant entries but the alternation is
    not strictly guaranteed (e.g. multiple assistant tool replies).  We
    treat each user message as the start of a turn and consume assistant
    messages that follow until the next user message.
    """
    turns: list[ConversationTurn] = []
    pending_question: str | None = None
    pending_answer_parts: list[str] = []

    def flush() -> None:
        nonlocal pending_question, pending_answer_parts
        if pending_question is None:
            return
        answer = "\n".join(p for p in pending_answer_parts if p).strip()
        turns.append(
            ConversationTurn(
                question=_clean(pending_question),
                answer=_clean(answer),
            )
        )
        pending_question = None
        pending_answer_parts = []

    for message in messages or []:
        role = (message or {}).get("role")
        content = (message or {}).get("content") or ""
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception:
                content = ""
        if role == "user":
            flush()
            pending_question = content
        elif role == "assistant":
            if pending_question is None:
                # Orphan assistant message — record it as a system note.
                pending_question = ""
            pending_answer_parts.append(content)
    flush()
    return [t for t in turns if t.question or t.answer]


def _summarise_older(turns: Iterable[ConversationTurn], max_snippets: int) -> str:
    snippets: list[str] = []
    for turn in turns:
        q = _truncate(turn.question, 120)
        if not q:
            continue
        snippets.append(f"- {q}")
        if len(snippets) >= max_snippets:
            break
    if not snippets:
        return ""
    return (
        "Avant les échanges récents, l'utilisateur a déjà demandé :\n"
        + "\n".join(snippets)
    )


def build_session_history(
    messages: Sequence[dict],
    *,
    recent_turns: int = _DEFAULT_RECENT_TURNS,
    max_chars_per_turn: int = _DEFAULT_MAX_CHARS_PER_TURN,
    max_chars: int = _DEFAULT_MAX_CHARS,
    older_snippets: int = _DEFAULT_OLDER_SNIPPETS,
    include_current_user_message: bool = False,
) -> str:
    """Return a long-but-bounded history block for prompt injection.

    Args:
        messages: Streamlit-style message list (each dict has ``role`` and
            ``content``). Tool outputs already appear here as assistant
            messages so we don't need to look them up separately.
        recent_turns: Number of most-recent Q/A pairs to keep verbatim.
        max_chars_per_turn: Maximum characters kept per side of a turn.
        max_chars: Hard cap on the total returned string.
        older_snippets: Maximum number of older question snippets to list.
        include_current_user_message: When ``False`` (the default), the
            *last* user message is dropped because the LLM prompt already
            contains it as the current question. Set to ``True`` to keep
            it (useful for debugging and unit tests).
    """
    turns = pair_messages(messages)
    if not turns:
        return "Aucun historique utile."

    if not include_current_user_message and turns and not turns[-1].answer:
        turns = turns[:-1]
    if not turns:
        return "Aucun historique utile."

    recent = turns[-recent_turns:]
    older = turns[:-recent_turns] if len(turns) > recent_turns else []

    parts: list[str] = []
    if older:
        summary = _summarise_older(older, older_snippets)
        if summary:
            parts.append(summary)

    for index, turn in enumerate(recent, start=1):
        q = _truncate(turn.question, max_chars_per_turn)
        a = _truncate(turn.answer, max_chars_per_turn)
        if not q and not a:
            continue
        block = [f"Tour {index} — Question: {q or '(vide)'}"]
        if a:
            block.append(f"Tour {index} — Réponse: {a}")
        parts.append("\n".join(block))

    text = "\n\n".join(parts).strip()
    if not text:
        return "Aucun historique utile."

    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


__all__ = [
    "ConversationTurn",
    "build_session_history",
    "pair_messages",
]
