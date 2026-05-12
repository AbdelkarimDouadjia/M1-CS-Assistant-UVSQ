"""SQLite persistence for chat logs, feedback, and local student memory."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "chat_logs.db"

# Special session_id used to store the user's profile across every conversation.
# Treating the row keyed by this value as the source of truth makes the memory
# behave like ChatGPT's: facts learned in chat A are available in chat B too.
GLOBAL_MEMORY_KEY = "__global__"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            response TEXT,
            answered INTEGER NOT NULL DEFAULT 1,
            num_docs_found INTEGER DEFAULT 0,
            session_id TEXT,
            feedback TEXT,
            feedback_comment TEXT,
            feedback_timestamp TEXT,
            tools_used TEXT,
            sources TEXT
        )
        """
    )
    for name, column_type in {
        "feedback": "TEXT",
        "feedback_comment": "TEXT",
        "feedback_timestamp": "TEXT",
        "tools_used": "TEXT",
        "sources": "TEXT",
        "correction_status": "TEXT DEFAULT 'pending'",
        "corrected_response": "TEXT",
        "correction_note": "TEXT",
        "corrected_by": "TEXT",
        "corrected_at": "TEXT",
        "kb_applied_at": "TEXT",
        "kb_source": "TEXT",
    }.items():
        _ensure_column(conn, "chat_logs", name, column_type)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Nouvelle conversation',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            pinned INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    for name, column_type in {
        "title": "TEXT NOT NULL DEFAULT 'Nouvelle conversation'",
        "archived": "INTEGER NOT NULL DEFAULT 0",
        "pinned": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        _ensure_column(conn, "conversations", name, column_type)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_memory (
            session_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            profile TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Conversation persistence
# ---------------------------------------------------------------------------


def _summarize_title(text: str, max_length: int = 60) -> str:
    text = (text or "").strip().replace("\n", " ").replace("\r", " ")
    if not text:
        return "Nouvelle conversation"
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def ensure_conversation(session_id: str, first_message: str | None = None) -> None:
    """Create the conversation row if it does not exist yet."""
    if not session_id:
        return
    init_db()
    conn = get_connection()
    existing = conn.execute(
        "SELECT session_id FROM conversations WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    title = _summarize_title(first_message) if first_message else "Nouvelle conversation"
    now = _now()
    if existing is None:
        conn.execute(
            """
            INSERT INTO conversations (session_id, title, created_at, updated_at, archived, pinned)
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            (session_id, title, now, now),
        )
    elif first_message:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE session_id = ? AND (title IS NULL OR title = 'Nouvelle conversation' OR title = '')",
            (title, now, session_id),
        )
    conn.commit()
    conn.close()


def touch_conversation(session_id: str) -> None:
    if not session_id:
        return
    init_db()
    conn = get_connection()
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    conn.commit()
    conn.close()


def rename_conversation(session_id: str, title: str) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE session_id = ?",
        (_summarize_title(title), _now(), session_id),
    )
    conn.commit()
    conn.close()


def get_conversation_title(session_id: str) -> str | None:
    """Return the stored title for ``session_id`` or ``None`` if not found."""
    if not session_id:
        return None
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT title FROM conversations WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row["title"] if row else None


def rename_if_default(session_id: str, title: str) -> bool:
    """Replace the title if it still looks like a default placeholder.

    Returns ``True`` when the row was updated (so callers can refresh their
    cached conversation list). The placeholders we treat as "default" are the
    initial value created by :func:`ensure_conversation` and the trimmed first
    message produced by ``_summarize_title``.
    """
    if not session_id or not title:
        return False
    init_db()
    new_title = _summarize_title(title)
    conn = get_connection()
    row = conn.execute(
        "SELECT title FROM conversations WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    current = (row["title"] or "").strip()
    if current and current not in {"", "Nouvelle conversation"} and not current.endswith("…"):
        conn.close()
        return False
    if current == new_title:
        conn.close()
        return False
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE session_id = ?",
        (new_title, _now(), session_id),
    )
    conn.commit()
    conn.close()
    return True


def delete_conversation(session_id: str) -> None:
    init_db()
    if session_id == GLOBAL_MEMORY_KEY:
        return
    conn = get_connection()
    conn.execute("DELETE FROM chat_logs WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM student_memory WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


def pin_conversation(session_id: str, pinned: bool = True) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        "UPDATE conversations SET pinned = ?, updated_at = ? WHERE session_id = ?",
        (1 if pinned else 0, _now(), session_id),
    )
    conn.commit()
    conn.close()


def list_conversations(limit: int = 50, include_archived: bool = False) -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    if include_archived:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY pinned DESC, updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE archived = 0 ORDER BY pinned DESC, updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return rows


def get_conversation_messages(session_id: str) -> list[sqlite3.Row]:
    """Return the persisted Q&A history for a conversation (oldest first)."""
    if not session_id:
        return []
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chat_logs WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return rows


def log_question(
    question: str,
    response: str,
    answered: bool = True,
    num_docs_found: int = 0,
    session_id: str | None = None,
    tools_used: str | None = None,
    sources: str | None = None,
) -> int:
    init_db()
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO chat_logs (
            timestamp, question, response, answered, num_docs_found,
            session_id, tools_used, sources
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _now(),
            question,
            response,
            1 if answered else 0,
            num_docs_found,
            session_id,
            tools_used,
            sources,
        ),
    )
    log_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    if session_id:
        ensure_conversation(session_id, first_message=question)
        touch_conversation(session_id)
    return log_id


def update_feedback(log_id: int, feedback: str, comment: str = "") -> None:
    init_db()
    if feedback not in {"liked", "disliked"}:
        raise ValueError("feedback must be 'liked' or 'disliked'")
    conn = get_connection()
    conn.execute(
        """
        UPDATE chat_logs
        SET feedback = ?, feedback_comment = ?, feedback_timestamp = ?
        WHERE id = ?
        """,
        (feedback, comment.strip(), _now(), log_id),
    )
    conn.commit()
    conn.close()


def get_total_messages() -> int:
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) AS total FROM chat_logs").fetchone()
    conn.close()
    return int(result["total"])


def get_memory(session_id: str) -> dict[str, str | bool]:
    init_db()
    conn = get_connection()
    result = conn.execute(
        "SELECT * FROM student_memory WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    if result is None:
        return {"enabled": False, "profile": ""}
    return {"enabled": bool(result["enabled"]), "profile": result["profile"] or ""}


def save_memory(session_id: str, enabled: bool, profile: str) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO student_memory (session_id, enabled, profile, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            enabled = excluded.enabled,
            profile = excluded.profile,
            updated_at = excluded.updated_at
        """,
        (session_id, 1 if enabled else 0, profile.strip(), _now()),
    )
    conn.commit()
    conn.close()


def clear_memory(session_id: str) -> None:
    save_memory(session_id, False, "")


def get_global_memory() -> dict[str, str | bool]:
    """Return the student profile shared across every conversation.

    First call performs a one-time migration: if the global row is empty but
    some older per-session memory exists, the most recent non-empty profile is
    copied so users don't lose facts learned before this change.
    """
    memory = get_memory(GLOBAL_MEMORY_KEY)
    if memory.get("profile"):
        return memory
    init_db()
    conn = get_connection()
    try:
        legacy = conn.execute(
            """
            SELECT profile, enabled FROM student_memory
            WHERE session_id != ?
              AND profile IS NOT NULL
              AND TRIM(profile) != ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (GLOBAL_MEMORY_KEY,),
        ).fetchone()
    finally:
        conn.close()
    if legacy and legacy["profile"]:
        save_memory(GLOBAL_MEMORY_KEY, bool(legacy["enabled"]), legacy["profile"])
        return {"enabled": bool(legacy["enabled"]), "profile": legacy["profile"]}
    return memory


def save_global_memory(enabled: bool, profile: str) -> None:
    save_memory(GLOBAL_MEMORY_KEY, enabled, profile)


def clear_global_memory() -> None:
    clear_memory(GLOBAL_MEMORY_KEY)


def get_answered_count() -> int:
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) AS total FROM chat_logs WHERE answered = 1").fetchone()
    conn.close()
    return int(result["total"])


def get_unanswered_count() -> int:
    init_db()
    conn = get_connection()
    result = conn.execute("SELECT COUNT(*) AS total FROM chat_logs WHERE answered = 0").fetchone()
    conn.close()
    return int(result["total"])


def get_success_rate() -> float:
    total = get_total_messages()
    if total == 0:
        return 0.0
    return round((get_answered_count() / total) * 100, 1)


def get_feedback_counts() -> dict[str, int]:
    init_db()
    conn = get_connection()
    result = conn.execute(
        """
        SELECT
            SUM(CASE WHEN feedback = 'liked' THEN 1 ELSE 0 END) AS liked,
            SUM(CASE WHEN feedback = 'disliked' THEN 1 ELSE 0 END) AS disliked
        FROM chat_logs
        """
    ).fetchone()
    conn.close()
    return {"liked": int(result["liked"] or 0), "disliked": int(result["disliked"] or 0)}


def get_unanswered_questions(limit: int = 50) -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    results = conn.execute(
        "SELECT * FROM chat_logs WHERE answered = 0 ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return results


def get_disliked_interactions(limit: int = 50) -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    results = conn.execute(
        """
        SELECT * FROM chat_logs
        WHERE feedback = 'disliked'
        ORDER BY
            CASE COALESCE(correction_status, 'pending')
                WHEN 'pending' THEN 0
                WHEN 'in_review' THEN 1
                WHEN 'resolved' THEN 2
                ELSE 3
            END,
            feedback_timestamp DESC,
            timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return results


def get_correction_counts() -> dict[str, int]:
    init_db()
    conn = get_connection()
    result = conn.execute(
        """
        SELECT
            SUM(CASE WHEN feedback = 'disliked' AND COALESCE(correction_status, 'pending') = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN feedback = 'disliked' AND correction_status = 'in_review' THEN 1 ELSE 0 END) AS in_review,
            SUM(CASE WHEN feedback = 'disliked' AND correction_status = 'resolved' THEN 1 ELSE 0 END) AS resolved
        FROM chat_logs
        """
    ).fetchone()
    conn.close()
    return {
        "pending": int(result["pending"] or 0),
        "in_review": int(result["in_review"] or 0),
        "resolved": int(result["resolved"] or 0),
    }


def update_correction(
    log_id: int,
    corrected_response: str,
    correction_note: str = "",
    status: str = "resolved",
    corrected_by: str = "admin",
) -> None:
    init_db()
    if status not in {"pending", "in_review", "resolved"}:
        raise ValueError("status must be pending, in_review, or resolved")
    conn = get_connection()
    conn.execute(
        """
        UPDATE chat_logs
        SET corrected_response = ?,
            correction_note = ?,
            correction_status = ?,
            corrected_by = ?,
            corrected_at = ?
        WHERE id = ?
        """,
        (
            corrected_response.strip(),
            correction_note.strip(),
            status,
            corrected_by.strip() or "admin",
            _now(),
            log_id,
        ),
    )
    conn.commit()
    conn.close()


def mark_correction_applied(log_id: int, kb_source: str) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        """
        UPDATE chat_logs
        SET kb_applied_at = ?, kb_source = ?
        WHERE id = ?
        """,
        (_now(), kb_source, log_id),
    )
    conn.commit()
    conn.close()


def get_recent_interactions(limit: int = 20) -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    results = conn.execute(
        "SELECT * FROM chat_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return results


def get_messages_per_day(days: int = 7) -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    results = conn.execute(
        """
        SELECT DATE(timestamp) AS jour, COUNT(*) AS total
        FROM chat_logs
        WHERE DATE(timestamp) >= DATE('now', ?)
        GROUP BY DATE(timestamp)
        ORDER BY jour ASC
        """,
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return results


def get_all_logs() -> list[sqlite3.Row]:
    init_db()
    conn = get_connection()
    results = conn.execute("SELECT * FROM chat_logs ORDER BY timestamp DESC").fetchall()
    conn.close()
    return results


def get_messages_today() -> int:
    init_db()
    conn = get_connection()
    result = conn.execute(
        "SELECT COUNT(*) AS total FROM chat_logs WHERE DATE(timestamp) = DATE('now')"
    ).fetchone()
    conn.close()
    return int(result["total"])
