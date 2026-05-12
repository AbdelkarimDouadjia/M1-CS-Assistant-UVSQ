from __future__ import annotations

import json
import os
import sys
from datetime import datetime
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

st.set_page_config(page_title="M1 Assistant Admin", page_icon="📊", layout="wide")
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


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


def metric_card(label: str, value: str, accent: str = "#2563eb") -> None:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value" style="color:{accent};">{value}</div>
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


st.markdown('<div class="dashboard-header">University Chatbot Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dashboard-subtitle">Usage, satisfaction, unanswered questions, files, and evaluation reports.</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

total = get_total_messages()
answered = get_answered_count()
unanswered = get_unanswered_count()
success_rate = get_success_rate()
today = get_messages_today()
feedback_counts = get_feedback_counts()
feedback_total = feedback_counts["liked"] + feedback_counts["disliked"]
satisfaction_rate = round((feedback_counts["liked"] / feedback_total) * 100, 1) if feedback_total else 0.0
correction_counts = get_correction_counts()

cols = st.columns(7)
with cols[0]:
    metric_card("Total messages", f"{total:,}")
with cols[1]:
    metric_card("Success rate", f"{success_rate}%", "#16a34a")
with cols[2]:
    metric_card("Unanswered", f"{unanswered}", "#ca8a04")
with cols[3]:
    metric_card("Today", f"{today}", "#2563eb")
with cols[4]:
    metric_card("Likes", f"{feedback_counts['liked']}", "#15803d")
with cols[5]:
    metric_card("Satisfaction", f"{satisfaction_rate}%", "#7c3aed")
with cols[6]:
    metric_card("Pending fixes", f"{correction_counts['pending']}", "#dc2626")

all_logs_df = rows_to_df(get_all_logs())
if not all_logs_df.empty:
    csv = all_logs_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export all logs CSV",
        data=csv,
        file_name=f"chat_logs_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

tabs = st.tabs(
    ["Review", "Feedback", "Trends", "Knowledge Base", "Settings", "Evaluations", "All Logs"]
)

with tabs[0]:
    col_unanswered, col_recent = st.columns([1, 1])
    with col_unanswered:
        st.subheader("Questions without answer")
        unanswered_rows = get_unanswered_questions(limit=15)
        if unanswered_rows:
            for row in unanswered_rows:
                st.markdown(
                    f"""
                    <div class="unanswered-card">
                      <div class="unanswered-label">{row['timestamp']}</div>
                      <div class="unanswered-question">{row['question']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("No unanswered questions yet.")
    with col_recent:
        st.subheader("Recent interactions")
        recent_rows = get_recent_interactions(limit=15)
        if recent_rows:
            for row in recent_rows:
                status = "Answered" if row["answered"] else "Unanswered"
                feedback = row["feedback"] or "no feedback"
                st.markdown(
                    f"""
                    <div class="interaction-card">
                        <div><strong>{status}</strong> · {feedback} · {row['timestamp']}</div>
                        <div class="interaction-question">{row['question'][:140]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No interactions yet.")

with tabs[1]:
    st.subheader("Correction workflow")
    disliked_df = rows_to_df(get_disliked_interactions(limit=100))
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
        st.dataframe(disliked_df[export_columns], use_container_width=True, height=260)
        st.download_button(
            "Export correction queue CSV",
            data=disliked_df[export_columns].to_csv(index=False).encode("utf-8"),
            file_name=f"correction_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

with tabs[2]:
    st.subheader("Message trend")
    days = st.selectbox("Period", [7, 14, 30], format_func=lambda value: f"Last {value} days")
    trend = rows_to_df(get_messages_per_day(days))
    if trend.empty:
        st.info("No trend data yet.")
    else:
        trend.columns = ["Day", "Messages"]
        trend["Day"] = pd.to_datetime(trend["Day"])
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

        st.divider()
        st.markdown("**LLM routing**")
        col_backend, col_temp, col_tokens = st.columns([1, 1, 1])
        backends = ["auto", "vllm", "fallback", "gemini"]
        with col_backend:
            backend_index = backends.index(current["active_backend"]) if current["active_backend"] in backends else 0
            active_backend = st.selectbox(
                "Active backend",
                backends,
                index=backend_index,
                help=(
                    "auto = try vLLM, then fallback, then Gemini. "
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
        col_r1, col_r2, col_r3 = st.columns(3)
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
            st.dataframe(pd.DataFrame(results), use_container_width=True, height=420)

with tabs[6]:
    st.subheader("Complete history")
    if all_logs_df.empty:
        st.info("No logs yet.")
    else:
        filter_choice = st.radio("Filter", ["All", "Answered", "Unanswered", "Liked", "Disliked"], horizontal=True)
        df = all_logs_df.copy()
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
        st.dataframe(df[[col for col in preferred if col in df.columns]], use_container_width=True, height=520)

st.markdown("---")
st.caption("M1 Informatique Assistant · Admin dashboard")
