from __future__ import annotations

import json
import os
import sys
import html
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import streamlit as st

from chatbot_core.admin_settings import (
    default_settings,
    load_settings,
    reset_settings,
    save_settings,
)
from chatbot_core.chat_logger import (
    get_all_logs,
    get_answered_count,
    get_correction_counts,
    get_disliked_interactions,
    get_feedback_counts,
    get_messages_per_day,
    get_messages_today,
    get_recent_interactions,
    get_success_rate,
    get_total_messages,
    get_unanswered_count,
    get_unanswered_questions,
    mark_correction_applied,
    update_correction,
)
from chatbot_core.dashboard_styles import DASHBOARD_CSS
from chatbot_core.ingest_database import DATA_PATH, clear_and_reingest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

st.set_page_config(page_title="M1 Assistant Admin", page_icon=":material/analytics:", layout="wide")
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


ADMIN_ICONS = {
    "shield": '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 20 6.5v5.8c0 5-3.2 8.2-8 9.7-4.8-1.5-8-4.7-8-9.7V6.5L12 3Z"/><path d="M9 8.5h6M8.5 11.5h7M9 14.5h6"/></svg>',
    "messages": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6.5h14a2.5 2.5 0 0 1 2.5 2.5v5.5A2.5 2.5 0 0 1 19 17H11l-5 4v-4H5A2.5 2.5 0 0 1 2.5 14.5V9A2.5 2.5 0 0 1 5 6.5Z"/><path d="M7 10h10M7 13h6"/></svg>',
    "check": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.2 2.2 4.8-5.4"/></svg>',
    "help": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.2A2.8 2.8 0 0 1 12.1 7c1.7 0 3 1 3 2.6 0 2.4-3.1 2.2-3.1 4.4"/><path d="M12 17.5h.01"/></svg>',
    "calendar": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M8 3v4M16 3v4M4 10h16"/></svg>',
    "thumb": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 21H4.8A1.8 1.8 0 0 1 3 19.2v-7.4A1.8 1.8 0 0 1 4.8 10H7v11Z"/><path d="M7 10l4.5-7c1.2.2 2 1 2 2.3V9h4.3a2.2 2.2 0 0 1 2.1 2.7l-1.5 6.8A3 3 0 0 1 15.5 21H7"/></svg>',
    "wrench": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 7.5a6 6 0 0 1-7.4 7.4L7.1 21.4a2.2 2.2 0 0 1-3.1-3.1l6.5-6.5A6 6 0 0 1 17.9 4.4L14.5 7.8l1.7 1.7L19.6 6c.5.4 1 .9 1.4 1.5Z"/></svg>',
    "arrow_up": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>',
    "arrow_down": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7 17 17M17 9v8H9"/></svg>',
    "ok": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 12 3 3 7-7"/></svg>',
    "info": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 17v-6M12 7h.01"/></svg>',
}


@st.cache_data(ttl=30)
def load_evaluation_reports():
    reports = []
    directory = PROJECT_ROOT / "evaluation_chatbot"
    if not directory.exists():
        return reports
    for file_path in directory.glob("*.json"):
        try:
            content = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(content, list):
            content = {"results": content, "total_questions": len(content)}
        if isinstance(content, dict):
            reports.append({"name": file_path.name, "mtime": file_path.stat().st_mtime, "data": content})
    return sorted(reports, key=lambda item: item["mtime"], reverse=True)


def metric_card(
    label: str,
    value: str,
    accent: str = "#2563eb",
    icon: str = "messages",
    trend: str = "Live data",
    direction: str = "up",
    comparison_label: str = "vs previous period",
) -> None:
    icon_html = ADMIN_ICONS.get(icon, ADMIN_ICONS["messages"])
    arrow_html = ADMIN_ICONS["arrow_down"] if direction == "down" else ADMIN_ICONS["arrow_up"]
    trend_class = "trend-down" if direction == "down" else "trend-up"
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-head">
                <div class="stat-icon" style="background:{accent}18;color:{accent};">{icon_html}</div>
                <div>
                    <div class="stat-label">{html.escape(label)}</div>
                    <div class="stat-value" style="color:{accent};">{html.escape(value)}</div>
                </div>
            </div>
            <div class="stat-trend {trend_class}">
                {arrow_html}
                <strong>{html.escape(trend)}</strong>
                <span>{html.escape(comparison_label)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _trim(text: str, limit: int = 130) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _source_label(row) -> str:
    tools = clean_cell(row_value(row, "tools_used"))
    if "rag" in tools.lower():
        return "RAG"
    if "image" in tools.lower() or "vision" in tools.lower():
        return "Vision"
    if "grade" in tools.lower():
        return "Calculator"
    if "memory" in tools.lower():
        return "Memory"
    if "file" in tools.lower() or "upload" in tools.lower():
        return "Files"
    return "Chat"


def _question_tags(question: str) -> list[str]:
    lowered = (question or "").lower()
    rules = [
        ("Scolarité", ("scolarité", "certificat", "inscription", "démarche", "demarche")),
        ("Bourses", ("bourse", "crous")),
        ("Logement", ("logement", "résidence", "residence")),
        ("Calendrier", ("jury", "date", "calendrier", "semestre")),
        ("Notes", ("moyenne", "note", "compensation", "bcc", "ue")),
        ("International", ("international", "étranger", "etranger")),
        ("Services", ("carte", "bibliothèque", "bibliotheque", "restaurant")),
    ]
    tags = [label for label, needles in rules if any(item in lowered for item in needles)]
    return tags[:3] or ["Question", "À traiter"]


def render_section_title(title: str, count: int | str) -> None:
    st.markdown(
        f"""
        <div class="section-title-row">
          <h2 class="section-title">{html.escape(title)}</h2>
          <span class="count-pill">{html.escape(str(count))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rows_to_df(rows) -> pd.DataFrame:
    return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


def clean_cell(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value)


def row_value(row, key: str, default: str = ""):
    try:
        return row[key]
    except Exception:
        if hasattr(row, "get"):
            return row.get(key, default)
        return default


def _prepare_logs_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    prepared = df.copy()
    timestamp_col = prepared["timestamp"] if "timestamp" in prepared else pd.Series(pd.NaT, index=prepared.index)
    prepared["_timestamp_dt"] = pd.to_datetime(timestamp_col, errors="coerce")
    return prepared


def _normalize_period(value) -> tuple[datetime.date, datetime.date]:
    today = datetime.now().date()
    default_start = today - timedelta(days=43)
    if isinstance(value, (tuple, list)):
        selected = [item for item in value if item is not None]
        if len(selected) >= 2:
            start, end = selected[0], selected[1]
        elif len(selected) == 1:
            start = end = selected[0]
        else:
            start, end = default_start, today
    else:
        start = end = value or today
    if start > end:
        start, end = end, start
    return start, end


def _filter_logs_by_period(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    prepared = _prepare_logs_df(df) if "_timestamp_dt" not in df.columns else df.copy()
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return prepared[prepared["_timestamp_dt"].between(start_ts, end_ts, inclusive="both")].copy()


def _snapshot(df: pd.DataFrame) -> dict[str, float | int]:
    if df.empty:
        return {
            "total": 0,
            "answered": 0,
            "unanswered": 0,
            "success_rate": 0.0,
            "liked": 0,
            "disliked": 0,
            "satisfaction_rate": 0.0,
            "pending": 0,
        }
    answered_col = (
        pd.to_numeric(df["answered"], errors="coerce")
        if "answered" in df
        else pd.Series(0, index=df.index, dtype=float)
    )
    feedback_col = df["feedback"].fillna("") if "feedback" in df else pd.Series("", index=df.index)
    status_col = (
        df["correction_status"].fillna("pending")
        if "correction_status" in df
        else pd.Series("pending", index=df.index)
    )
    total = int(len(df))
    answered = int((answered_col == 1).sum())
    unanswered = int((answered_col == 0).sum())
    liked = int((feedback_col == "liked").sum())
    disliked = int((feedback_col == "disliked").sum())
    feedback_total = liked + disliked
    return {
        "total": total,
        "answered": answered,
        "unanswered": unanswered,
        "success_rate": round((answered / total) * 100, 1) if total else 0.0,
        "liked": liked,
        "disliked": disliked,
        "satisfaction_rate": round((liked / feedback_total) * 100, 1) if feedback_total else 0.0,
        "pending": int(((feedback_col == "disliked") & (status_col == "pending")).sum()),
    }


def _count_for_day(df: pd.DataFrame, day) -> int:
    if df.empty or "_timestamp_dt" not in df.columns:
        return 0
    return int((df["_timestamp_dt"].dt.date == day).sum())


def _trend(current: float, previous: float, *, percent_points: bool = False) -> tuple[str, str]:
    delta = current - previous
    if percent_points:
        if abs(delta) < 0.05:
            return "0 pts", "up"
        return f"{delta:+.1f} pts", "down" if delta < 0 else "up"
    if abs(delta) < 0.5:
        return "0", "up"
    return f"{delta:+,.0f}", "down" if delta < 0 else "up"


def _messages_per_day(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    if df.empty or "_timestamp_dt" not in df.columns:
        return pd.DataFrame()
    valid = df.dropna(subset=["_timestamp_dt"]).copy()
    if valid.empty:
        return pd.DataFrame()
    counts = valid.groupby(valid["_timestamp_dt"].dt.date).size()
    days = pd.date_range(start=start_date, end=end_date, freq="D")
    return pd.DataFrame(
        {
            "Day": days,
            "Messages": [int(counts.get(day.date(), 0)) for day in days],
        }
    )


def _public_logs_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=["_timestamp_dt"], errors="ignore")


def append_correction_to_knowledge_base(row, corrected_response: str, correction_note: str) -> Path:
    data_path = Path(DATA_PATH)
    data_path.mkdir(exist_ok=True)
    corrections_path = data_path / "admin_corrections.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""

## Correction admin #{int(row["id"])} - {timestamp}

### Question etudiante
{clean_cell(row["question"])}

### Reponse corrigee
{corrected_response.strip()}

### Note admin
{correction_note.strip() or "Aucune note."}

### Reponse originale
{clean_cell(row["response"])}

### Sources originales
{clean_cell(row.get("sources")) or "Aucune source enregistree."}
""".rstrip()
    with corrections_path.open("a", encoding="utf-8") as handle:
        handle.write(entry + "\n")
    return corrections_path


top_left, top_right = st.columns([1.7, 1])
with top_left:
    st.markdown(
        f"""
        <div class="admin-topbar">
            <div class="admin-logo">{ADMIN_ICONS["shield"]}</div>
            <div class="admin-wordmark">UVSQ</div>
        </div>
        <div class="dashboard-header">University Chatbot Dashboard</div>
        <div class="dashboard-subtitle">
            Usage, satisfaction, unanswered questions, files, and evaluation reports.
        </div>
        """,
        unsafe_allow_html=True,
    )
with top_right:
    right_a, right_b = st.columns([1.35, 0.65])
    with right_a:
        period_value = st.date_input(
            "Période",
            value=(datetime.now().date() - timedelta(days=43), datetime.now().date()),
            label_visibility="collapsed",
            key="admin_period",
        )
    with right_b:
        if st.button("Refresh", icon=":material/refresh:", width="stretch"):
            st.cache_data.clear()
            st.rerun()

start_date, end_date = _normalize_period(period_value)
period_days = (end_date - start_date).days + 1
previous_end = start_date - timedelta(days=1)
previous_start = previous_end - timedelta(days=period_days - 1)

all_logs_df = _prepare_logs_df(rows_to_df(get_all_logs()))
filtered_logs_df = _filter_logs_by_period(all_logs_df, start_date, end_date)
previous_logs_df = _filter_logs_by_period(all_logs_df, previous_start, previous_end)

current_stats = _snapshot(filtered_logs_df)
previous_stats = _snapshot(previous_logs_df)
total = int(current_stats["total"])
answered = int(current_stats["answered"])
unanswered = int(current_stats["unanswered"])
success_rate = float(current_stats["success_rate"])
today = _count_for_day(filtered_logs_df, datetime.now().date())
yesterday = _count_for_day(all_logs_df, datetime.now().date() - timedelta(days=1))
satisfaction_rate = float(current_stats["satisfaction_rate"])
pending_fixes = int(current_stats["pending"])

total_trend, total_dir = _trend(total, float(previous_stats["total"]))
success_trend, success_dir = _trend(success_rate, float(previous_stats["success_rate"]), percent_points=True)
unanswered_trend, unanswered_dir = _trend(unanswered, float(previous_stats["unanswered"]))
today_trend, today_dir = _trend(today, yesterday)
satisfaction_trend, satisfaction_dir = _trend(
    satisfaction_rate,
    float(previous_stats["satisfaction_rate"]),
    percent_points=True,
)
pending_trend, pending_dir = _trend(pending_fixes, float(previous_stats["pending"]))

st.markdown('<div class="metric-row-spacer"></div>', unsafe_allow_html=True)
cols = st.columns(6)
with cols[0]:
    metric_card("Total messages", f"{total:,}", "#2563eb", "messages", total_trend, total_dir)
with cols[1]:
    metric_card("Success rate", f"{success_rate}%", "#16a34a", "check", success_trend, success_dir)
with cols[2]:
    metric_card("Unanswered", f"{unanswered}", "#f97316", "help", unanswered_trend, unanswered_dir)
with cols[3]:
    metric_card("Today", f"{today}", "#2563eb", "calendar", today_trend, today_dir, "vs yesterday")
with cols[4]:
    metric_card("Satisfaction", f"{satisfaction_rate}%", "#7c3aed", "thumb", satisfaction_trend, satisfaction_dir)
with cols[5]:
    metric_card("Pending fixes", f"{pending_fixes}", "#dc2626", "wrench", pending_trend, pending_dir)

if not filtered_logs_df.empty:
    csv = _public_logs_df(filtered_logs_df).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export filtered logs CSV",
        data=csv,
        file_name=f"chat_logs_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
        mime="text/csv",
    )

tabs = st.tabs(
    ["Review", "Feedback", "Trends", "Knowledge Base", "Settings", "Evaluations", "All Logs"]
)

with tabs[0]:
    col_unanswered, col_recent = st.columns([1, 1])
    with col_unanswered:
        period_rows = filtered_logs_df.sort_values("_timestamp_dt", ascending=False) if not filtered_logs_df.empty else filtered_logs_df
        if not period_rows.empty and "answered" in period_rows.columns:
            unanswered_rows = period_rows[pd.to_numeric(period_rows["answered"], errors="coerce") == 0].head(15).to_dict("records")
        else:
            unanswered_rows = []
        render_section_title("Questions without answer", unanswered)
        if unanswered_rows:
            for row in unanswered_rows:
                question = clean_cell(row_value(row, "question"))
                tags = "".join(f'<span class="chip">{html.escape(tag)}</span>' for tag in _question_tags(question))
                st.markdown(
                    f"""
                    <div class="unanswered-card">
                      <div class="unanswered-top">
                        <span>{html.escape(clean_cell(row_value(row, 'timestamp')))}</span>
                        <span>Source: {html.escape(_source_label(row))}</span>
                      </div>
                      <div class="unanswered-question">{html.escape(_trim(question, 190))}</div>
                      <div>{tags}</div>
                      <div class="card-menu">⋮</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("No unanswered questions yet.")
    with col_recent:
        recent_rows = period_rows.head(15).to_dict("records") if not period_rows.empty else []
        render_section_title("Recent interactions", f"{total:,}")
        if recent_rows:
            cards: list[str] = ['<div class="interaction-list">']
            for row in recent_rows:
                is_answered = bool(int(row_value(row, "answered", 0) or 0))
                status = "Answered" if is_answered else "Unanswered"
                status_class = "ok" if is_answered else "warn"
                status_icon = ADMIN_ICONS["ok"] if is_answered else ADMIN_ICONS["info"]
                response = _trim(clean_cell(row_value(row, "response")), 92)
                timestamp = clean_cell(row_value(row, "timestamp"))
                cards.append(
                    f'<div class="interaction-card">'
                    f'<div class="interaction-status {status_class}">{status_icon}</div>'
                    f'<div>'
                    f'<div class="interaction-meta"><strong>{html.escape(status)}</strong> · {html.escape(timestamp)}</div>'
                    f'<div class="interaction-question">{html.escape(_trim(clean_cell(row_value(row, "question")), 110))}</div>'
                    f'<div class="interaction-snippet">{html.escape(response or "No response stored yet.")}</div>'
                    f'</div>'
                    f'<div class="interaction-source">{html.escape(_source_label(row))}<br>{html.escape(timestamp[-5:])}</div>'
                    f'</div>'
                )
            cards.append('<div class="interaction-link">Full filtered history is available in All Logs.</div></div>')
            st.markdown("\n".join(cards), unsafe_allow_html=True)
        else:
            st.info("No interactions yet.")

with tabs[1]:
    st.subheader("Correction workflow")
    disliked_df = _prepare_logs_df(rows_to_df(get_disliked_interactions(limit=500)))
    disliked_df = _filter_logs_by_period(disliked_df, start_date, end_date)
    if disliked_df.empty:
        st.success("No disliked answers yet.")
    else:
        disliked_df["correction_status"] = disliked_df["correction_status"].fillna("pending")
        status_filter = st.radio(
            "Queue",
            ["Pending", "In review", "Resolved", "All"],
            horizontal=True,
        )
        filtered_df = disliked_df.copy()
        if status_filter != "All":
            status_value = status_filter.lower().replace(" ", "_")
            filtered_df = filtered_df[filtered_df["correction_status"] == status_value]

        if filtered_df.empty:
            st.info("No items in this queue.")
        else:
            options = filtered_df["id"].tolist()
            selected_id = st.selectbox(
                "Select a disliked answer",
                options=options,
                format_func=lambda row_id: (
                    f"#{row_id} · "
                    f"{filtered_df.loc[filtered_df['id'] == row_id, 'correction_status'].iloc[0]} · "
                    f"{filtered_df.loc[filtered_df['id'] == row_id, 'question'].iloc[0][:90]}"
                ),
            )
            selected = filtered_df[filtered_df["id"] == selected_id].iloc[0]
            col_question, col_answer = st.columns([1, 1])
            with col_question:
                st.markdown("**Student question**")
                st.write(clean_cell(selected["question"]))
                st.markdown("**Sources / tools**")
                st.caption(clean_cell(selected.get("tools_used")) or "No tools recorded")
                if clean_cell(selected.get("sources")):
                    with st.expander("Sources used", expanded=False):
                        st.write(clean_cell(selected["sources"]))
                if clean_cell(selected.get("feedback_comment")):
                    st.markdown("**Feedback comment**")
                    st.info(clean_cell(selected["feedback_comment"]))
            with col_answer:
                st.markdown("**Original answer**")
                st.write(clean_cell(selected["response"]))

            with st.form(f"correction_form_{selected_id}"):
                corrected_response = st.text_area(
                    "Corrected answer",
                    value=clean_cell(selected.get("corrected_response")) or clean_cell(selected["response"]),
                    height=220,
                )
                correction_note = st.text_area(
                    "Admin note",
                    value=clean_cell(selected.get("correction_note")),
                    placeholder="What was wrong, what should be improved in the knowledge base, or what source should be added?",
                    height=90,
                )
                col_status, col_admin = st.columns([1, 1])
                with col_status:
                    current_status = clean_cell(selected.get("correction_status")) or "pending"
                    status = st.selectbox(
                        "Status",
                        ["pending", "in_review", "resolved"],
                        index=["pending", "in_review", "resolved"].index(current_status),
                    )
                with col_admin:
                    corrected_by = st.text_input("Corrected by", value=clean_cell(selected.get("corrected_by")) or "admin")
                apply_to_kb = st.checkbox(
                    "Apply this correction to the knowledge base",
                    value=False,
                    help="Appends the corrected answer to data/admin_corrections.md so it can be retrieved by the chatbot.",
                )
                rebuild_after_apply = st.checkbox(
                    "Rebuild vector database after applying",
                    value=False,
                    disabled=not apply_to_kb,
                )
                submitted = st.form_submit_button("Save correction", type="primary")
                if submitted:
                    if apply_to_kb and not corrected_response.strip():
                        st.error("Write a corrected answer before applying it to the knowledge base.")
                        st.stop()
                    rebuild_failed = False
                    update_correction(
                        int(selected_id),
                        corrected_response=corrected_response,
                        correction_note=correction_note,
                        status=status,
                        corrected_by=corrected_by,
                    )
                    if apply_to_kb:
                        corrections_path = append_correction_to_knowledge_base(
                            selected,
                            corrected_response=corrected_response,
                            correction_note=correction_note,
                        )
                        mark_correction_applied(int(selected_id), str(corrections_path.relative_to(PROJECT_ROOT)))
                        if rebuild_after_apply:
                            with st.spinner("Rebuilding ChromaDB with the correction..."):
                                try:
                                    clear_and_reingest(reset_vector_store=False)
                                except Exception as exc:
                                    rebuild_failed = True
                                    st.warning(f"Correction was saved, but ChromaDB rebuild failed: {exc}")
                    st.success("Correction saved.")
                    st.cache_data.clear()
                    if not rebuild_failed:
                        st.rerun()

        export_columns = [
            col
            for col in [
                "id",
                "timestamp",
                "question",
                "response",
                "corrected_response",
                "correction_status",
                "correction_note",
                "corrected_by",
                "corrected_at",
                "kb_applied_at",
                "kb_source",
                "feedback_comment",
                "tools_used",
                "sources",
            ]
            if col in disliked_df.columns
        ]
        st.divider()
        st.dataframe(_public_logs_df(disliked_df)[export_columns], width="stretch", height=260)
        st.download_button(
            "Export correction queue CSV",
            data=_public_logs_df(disliked_df)[export_columns].to_csv(index=False).encode("utf-8"),
            file_name=f"correction_queue_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
            mime="text/csv",
        )

with tabs[2]:
    st.subheader("Message trend")
    st.caption(f"Période affichée : {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}")
    trend = _messages_per_day(filtered_logs_df, start_date, end_date)
    if trend.empty:
        st.info("No trend data yet.")
    else:
        st.bar_chart(trend.set_index("Day"))

    st.subheader("Answered vs unanswered")
    st.bar_chart(pd.DataFrame({"Count": [answered, unanswered]}, index=["Answered", "Unanswered"]))

with tabs[3]:
    st.subheader("Knowledge Base documents")
    col_upload, col_files = st.columns([1, 1])
    with col_upload:
        uploaded_files = st.file_uploader(
            "Add admin documents to the shared RAG base",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
        )
        if uploaded_files:
            Path(DATA_PATH).mkdir(exist_ok=True)
            for uploaded_file in uploaded_files:
                file_path = Path(DATA_PATH) / uploaded_file.name
                file_path.write_bytes(uploaded_file.getbuffer())
                st.success(f"Saved {uploaded_file.name}")

        st.caption("Rebuild Chroma after adding or deleting documents.")
        if st.button("Rebuild vector database", type="primary"):
            with st.spinner("Rebuilding ChromaDB..."):
                try:
                    chunks = clear_and_reingest(reset_vector_store=False)
                    st.success(f"Database updated: {chunks} chunks created.")
                except Exception as exc:
                    st.error(f"Update failed: {exc}")
        if st.button("Clear vector database"):
            with st.spinner("Clearing ChromaDB..."):
                try:
                    clear_and_reingest(reset_vector_store=True)
                    st.success("Vector database cleared.")
                except Exception as exc:
                    st.error(f"Clear failed: {exc}")

    with col_files:
        data_path = Path(DATA_PATH)
        if not data_path.exists():
            st.error("data/ does not exist.")
        else:
            files = [path for path in data_path.iterdir() if path.is_file() and not path.name.startswith(".")]
            if not files:
                st.info("No files in data/.")
            for path in sorted(files, key=lambda p: p.name.lower()):
                if path.suffix.lower() in {".yaml", ".json"}:
                    continue
                col_name, col_size, col_delete = st.columns([4, 1, 1])
                with col_name:
                    st.write(path.name)
                with col_size:
                    st.caption(f"{path.stat().st_size / 1024:.1f} KB")
                with col_delete:
                    if st.button("Delete", key=f"delete_{path.name}"):
                        path.unlink(missing_ok=True)
                        st.rerun()

    st.divider()
    st.subheader("Add a knowledge entry by typing")
    st.caption(
        "Write a new chunk of trusted information. It will be saved as a Markdown file in `data/` "
        "and indexed at the next rebuild."
    )
    with st.form("add_kb_entry"):
        kb_title = st.text_input("Title", placeholder="e.g. Modalités de rattrapage UE Algo")
        kb_tags = st.text_input(
            "Tags (comma separated, optional)",
            placeholder="rattrapage, jury, S1",
        )
        kb_body = st.text_area(
            "Content (Markdown allowed)",
            height=220,
            placeholder="Décris la règle, la procédure ou l'information à ajouter à la base.",
        )
        rebuild_after = st.checkbox("Rebuild vector database after saving", value=True)
        submitted_kb = st.form_submit_button("Save knowledge entry", type="primary")
        if submitted_kb:
            if not kb_title.strip() or not kb_body.strip():
                st.error("Title and content are both required.")
            else:
                Path(DATA_PATH).mkdir(exist_ok=True)
                kb_dir = Path(DATA_PATH) / "admin_entries"
                kb_dir.mkdir(exist_ok=True)
                slug = (
                    "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in kb_title.strip())
                    .strip("_")[:60]
                    or "entry"
                )
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target = kb_dir / f"{stamp}_{slug}.md"
                meta_line = (
                    f"<!-- tags: {kb_tags.strip()} | author: admin | created: {datetime.now().isoformat(timespec='seconds')} -->"
                    if kb_tags.strip()
                    else f"<!-- author: admin | created: {datetime.now().isoformat(timespec='seconds')} -->"
                )
                content = f"# {kb_title.strip()}\n\n{meta_line}\n\n{kb_body.strip()}\n"
                target.write_text(content, encoding="utf-8")
                st.success(f"Saved {target.relative_to(PROJECT_ROOT)}")
                if rebuild_after:
                    with st.spinner("Rebuilding ChromaDB..."):
                        try:
                            chunks = clear_and_reingest(reset_vector_store=False)
                            st.success(f"Database updated: {chunks} chunks created.")
                        except Exception as exc:
                            st.warning(f"Saved, but rebuild failed: {exc}")

with tabs[4]:
    st.subheader("Runtime settings")
    st.caption(
        "These settings live in `data/admin_settings.json` and are read by the chatbot on every "
        "interaction. No restart required."
    )
    current = load_settings()
    defaults = default_settings()
    with st.form("admin_settings_form"):
        st.markdown("**Feature toggles**")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            file_upload_enabled = st.toggle(
                "File upload (PDF / TXT / MD / DOCX)",
                value=bool(current["file_upload_enabled"]),
            )
            image_upload_enabled = st.toggle(
                "Image upload (vision-to-text)",
                value=bool(current["image_upload_enabled"]),
            )
            suggestions_enabled = st.toggle(
                "Show suggestion buttons",
                value=bool(current["suggestions_enabled"]),
            )
        with col_b:
            voice_input_enabled = st.toggle(
                "Voice input (microphone)",
                value=bool(current["voice_input_enabled"]),
            )
            voice_output_enabled = st.toggle(
                "Voice output (text-to-speech)",
                value=bool(current["voice_output_enabled"]),
            )
            export_enabled = st.toggle(
                "PDF / DOCX export",
                value=bool(current["export_enabled"]),
            )
        with col_c:
            memory_feature_enabled = st.toggle(
                "Student memory feature",
                value=bool(current["memory_feature_enabled"]),
            )
            reranking_enabled = st.toggle(
                "Reranker",
                value=bool(current["reranking_enabled"]),
            )
            query_expansion_enabled = st.toggle(
                "Query expansion / Rerasker",
                value=bool(current["query_expansion_enabled"]),
                help="Generate alternate phrasings before RAG retrieval. This is the safe version of the older rerasker, using the configured LLM chain.",
            )

        st.divider()
        st.markdown("**LLM routing**")
        col_backend, col_temp, col_tokens = st.columns([1, 1, 1])
        backends = ["auto", "gemini", "vllm", "fallback"]
        with col_backend:
            backend_index = backends.index(current["active_backend"]) if current["active_backend"] in backends else 0
            active_backend = st.selectbox(
                "Active backend",
                backends,
                index=backend_index,
                help=(
                    "auto = try Gemini first, then optional OpenAI-compatible providers, "
                    "then the UVSQ/vLLM server as backup. "
                    "Pick a single backend to force it."
                ),
            )
        with col_temp:
            temperature = st.slider(
                "Temperature", 0.0, 1.5, float(current["temperature"]), 0.05
            )
        with col_tokens:
            max_tokens = st.number_input(
                "Max tokens",
                min_value=64,
                max_value=8192,
                step=64,
                value=int(current["max_tokens"]),
            )

        col_vllm, col_fallback, col_gemini = st.columns(3)
        with col_vllm:
            vllm_model = st.text_input(
                "vLLM model",
                value=str(current["vllm_model"]),
                placeholder=defaults["vllm_model"],
            )
        with col_fallback:
            fallback_model = st.text_input(
                "Fallback vLLM model",
                value=str(current["fallback_model"]),
                placeholder="(empty = none)",
            )
        with col_gemini:
            gemini_model = st.text_input(
                "Gemini model",
                value=str(current["gemini_model"]),
                placeholder=defaults["gemini_model"],
            )
        vision_model = st.text_input(
            "Vision model (image-to-text)",
            value=str(current["vision_model"]),
            placeholder=defaults["vision_model"],
            help="Used to convert uploaded images into a textual description before sending to the chat model.",
        )

        st.divider()
        st.markdown("**Retrieval**")
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            retrieval_top_k = st.number_input(
                "Retrieval top K", min_value=1, max_value=50, value=int(current["retrieval_top_k"])
            )
        with col_r2:
            final_context_k = st.number_input(
                "Reranker top K", min_value=1, max_value=20, value=int(current["final_context_k"])
            )
        with col_r3:
            max_upload_chars = st.number_input(
                "Max chars per uploaded file",
                min_value=500,
                max_value=200000,
                step=500,
                value=int(current["max_upload_chars"]),
            )
        with col_r4:
            query_expansion_max_variants = st.number_input(
                "Query variants",
                min_value=1,
                max_value=8,
                value=int(current["query_expansion_max_variants"]),
                help="Maximum alternate queries generated when query expansion is enabled.",
            )

        col_save_settings, col_reset_settings = st.columns([1, 1])
        with col_save_settings:
            saved = st.form_submit_button("Save settings", type="primary")
        with col_reset_settings:
            reset_clicked = st.form_submit_button("Reset to defaults")

        if saved:
            save_settings(
                {
                    "file_upload_enabled": file_upload_enabled,
                    "image_upload_enabled": image_upload_enabled,
                    "voice_input_enabled": voice_input_enabled,
                    "voice_output_enabled": voice_output_enabled,
                    "export_enabled": export_enabled,
                    "memory_feature_enabled": memory_feature_enabled,
                    "suggestions_enabled": suggestions_enabled,
                    "active_backend": active_backend,
                    "vllm_model": vllm_model.strip() or defaults["vllm_model"],
                    "fallback_model": fallback_model.strip(),
                    "gemini_model": gemini_model.strip() or defaults["gemini_model"],
                    "vision_model": vision_model.strip() or defaults["vision_model"],
                    "temperature": float(temperature),
                    "max_tokens": int(max_tokens),
                    "retrieval_top_k": int(retrieval_top_k),
                    "final_context_k": int(final_context_k),
                    "reranking_enabled": reranking_enabled,
                    "query_expansion_enabled": query_expansion_enabled,
                    "query_expansion_max_variants": int(query_expansion_max_variants),
                    "max_upload_chars": int(max_upload_chars),
                }
            )
            st.success("Settings saved. The chatbot picks them up on the next message.")
        elif reset_clicked:
            reset_settings()
            st.success("Settings reset to defaults.")
            st.rerun()

with tabs[5]:
    st.subheader("Evaluation reports")
    reports = load_evaluation_reports()
    if not reports:
        st.info("No evaluation report found. Run `python -m tools.evaluate_chatbot` first.")
    else:
        selected = st.selectbox(
            "Report",
            options=range(len(reports)),
            format_func=lambda idx: f"{reports[idx]['name']} · {datetime.fromtimestamp(reports[idx]['mtime'])}",
        )
        report = reports[selected]["data"]
        results = report.get("results", [])
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Questions", report.get("total_questions", len(results)))
        with col_b:
            if results:
                answer_rate = sum(1 for item in results if item.get("answered")) / len(results) * 100
                st.metric("Answer rate", f"{answer_rate:.1f}%")
        with col_c:
            scores = [item.get("hybrid_score") for item in results if isinstance(item.get("hybrid_score"), (int, float))]
            if scores:
                st.metric("Hybrid score", f"{sum(scores) / len(scores):.1f}")
        if results:
            st.dataframe(pd.DataFrame(results), width="stretch", height=420)

with tabs[6]:
    st.subheader("Complete history")
    if filtered_logs_df.empty:
        st.info("No logs in the selected period.")
    else:
        filter_choice = st.radio("Filter", ["All", "Answered", "Unanswered", "Liked", "Disliked"], horizontal=True)
        df = _public_logs_df(filtered_logs_df).copy()
        if filter_choice == "Answered":
            df = df[df["answered"] == 1]
        elif filter_choice == "Unanswered":
            df = df[df["answered"] == 0]
        elif filter_choice == "Liked":
            df = df[df["feedback"] == "liked"]
        elif filter_choice == "Disliked":
            df = df[df["feedback"] == "disliked"]
        preferred = [
            "timestamp",
            "question",
            "response",
            "answered",
            "feedback",
            "tools_used",
            "num_docs_found",
            "sources",
        ]
        st.dataframe(df[[col for col in preferred if col in df.columns]], width="stretch", height=520)

st.markdown('<div class="admin-footer">All times are in Europe/Paris timezone</div>', unsafe_allow_html=True)
