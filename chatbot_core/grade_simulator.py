"""Interactive 'What-if' grade simulator.

Renders an interactive Streamlit panel where the student picks a parcours +
period and adjusts every UE note with a slider. After every interaction we
recompute the per-UE status, the per-BCC averages, the compensation groups
and the final semester / annual average using the existing
``grade_calculator`` infrastructure — so the deterministic rules stay in a
single place.

Triggered from:
* the sidebar button ("Simulateur Et si…")
* the chat command ``/simulateur`` (or any natural-language synonym)

The module is intentionally kept UI-light: it only depends on Streamlit at
import time so that ``chatbot_core`` stays importable from headless tests.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import streamlit as st

from chatbot_core.grade_calculator import (
    COMPENSATION_THRESHOLD,
    MAX_BO_CHOICES,
    PARCOURS_LIST,
    UE_STATUS_ACQUIRED,
    UE_STATUS_BELOW,
    UE_STATUS_COMPENSABLE,
    VALIDATION_THRESHOLD,
    bo_options,
    build_program,
    calculate_report,
    calculate_ue_final,
)

SIMULATOR_TRIGGER = "/simulateur"


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def detect_simulator_intent(text: str) -> bool:
    if not text:
        return False
    lowered = _strip_accents(text.lower())
    if SIMULATOR_TRIGGER in lowered:
        return True
    triggers = (
        "simulateur",
        "simule ma moyenne",
        "simuler ma moyenne",
        "et si j",
        "what if",
        "et si je",
        "scenario notes",
        "scenarios notes",
    )
    return any(trigger in lowered for trigger in triggers)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


_STATE_KEY = "_simulator_state"


def _ensure_state() -> dict[str, Any]:
    state = st.session_state.get(_STATE_KEY)
    if state is None:
        state = {
            "parcours": None,
            "period": "S1",
            "selected_bo": [],
            "notes": {},  # ue_code -> float | None
        }
        st.session_state[_STATE_KEY] = state
    return state


def open_simulator(default_parcours: str | None = None) -> None:
    state = _ensure_state()
    if default_parcours and not state.get("parcours"):
        state["parcours"] = default_parcours
    st.session_state["_simulator_open"] = True


def close_simulator() -> None:
    st.session_state["_simulator_open"] = False


def is_open() -> bool:
    return bool(st.session_state.get("_simulator_open"))


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


_STATUS_PILLS = {
    UE_STATUS_ACQUIRED: ("Acquise", "#dcfce7", "#16a34a"),
    UE_STATUS_COMPENSABLE: ("Compensable", "#fef9c3", "#ca8a04"),
    UE_STATUS_BELOW: ("Sous le seuil", "#fee2e2", "#dc2626"),
}


def _status_badge(status: str) -> str:
    label, bg, color = _STATUS_PILLS.get(status, ("—", "#e5e7eb", "#374151"))
    return (
        f'<span style="background:{bg};color:{color};padding:2px 8px;'
        f'border-radius:999px;font-size:11.5px;font-weight:700;">{label}</span>'
    )


def render_simulator_panel(*, default_parcours: str | None = None) -> str | None:
    """Render the interactive simulator. Returns a Markdown report when the
    user clicks "Envoyer dans le chat", otherwise ``None``."""
    state = _ensure_state()
    if state.get("parcours") is None and default_parcours:
        state["parcours"] = default_parcours

    with st.container(border=True):
        header_cols = st.columns([5, 1])
        with header_cols[0]:
            st.markdown("### Simulateur 'Et si…'")
            st.caption(
                "Ajustez les notes en direct pour visualiser la validation, "
                "la compensation entre BCC et la moyenne du semestre."
            )
        with header_cols[1]:
            if st.button("Fermer", key="simulator_close", width="content"):
                close_simulator()
                return None

        cfg_cols = st.columns([1, 1])
        with cfg_cols[0]:
            current_parcours = state.get("parcours") or PARCOURS_LIST[0]
            parcours_index = PARCOURS_LIST.index(current_parcours) if current_parcours in PARCOURS_LIST else 0
            new_parcours = st.selectbox(
                "Parcours",
                options=PARCOURS_LIST,
                index=parcours_index,
                key="simulator_parcours",
            )
            if new_parcours != state.get("parcours"):
                state["parcours"] = new_parcours
                state["selected_bo"] = []
                state["notes"] = {}
        with cfg_cols[1]:
            period_label = st.radio(
                "Période",
                options=["Semestre 1", "Semestre 2", "Année complète"],
                index={"S1": 0, "S2": 1, "year": 2}.get(state.get("period", "S1"), 0),
                horizontal=True,
                key="simulator_period",
            )
            new_period = {"Semestre 1": "S1", "Semestre 2": "S2", "Année complète": "year"}[period_label]
            if new_period != state.get("period"):
                state["period"] = new_period

        parcours = state["parcours"]
        period = state["period"]

        if period in {"S2", "year"}:
            st.markdown("**UEs Bloc Optionnel**")
            st.caption(f"Choisissez exactement {MAX_BO_CHOICES} UEs BO.")
            bo_list = bo_options(parcours)
            chosen = list(state.get("selected_bo") or [])
            choice_cols = st.columns(2)
            new_chosen: list[str] = []
            for idx, ue in enumerate(bo_list):
                with choice_cols[idx % 2]:
                    if st.checkbox(
                        f"{ue.name} ({ue.code})",
                        value=ue.code in chosen,
                        key=f"sim_bo_{ue.code}",
                    ):
                        new_chosen.append(ue.code)
            state["selected_bo"] = new_chosen
            if len(new_chosen) != MAX_BO_CHOICES:
                st.info(
                    f"Sélectionnez {MAX_BO_CHOICES} UEs BO pour un calcul fidèle ({len(new_chosen)} pour le moment).",
                    icon=":material/info:",
                )

        ues = build_program(parcours, period, selected_bo_codes=state.get("selected_bo") or None)
        if not ues:
            st.warning("Aucune UE pour cette combinaison parcours / période.")
            return None

        st.divider()
        st.markdown("**Notes par UE (0–20)**")
        notes_cols = st.columns(2)
        entries = []
        for idx, ue in enumerate(ues):
            with notes_cols[idx % 2]:
                stored = state["notes"].get(ue.code, 12.0)
                value = st.slider(
                    f"{ue.name} ({ue.code}) · {ue.bcc} · {ue.ects} ECTS",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(stored if stored is not None else 12.0),
                    step=0.25,
                    key=f"sim_slider_{ue.code}",
                    help=f"Règle: {ue.rule}",
                )
                state["notes"][ue.code] = value
                entry = calculate_ue_final(ue, final=value)
                entries.append(entry)
                badge = _status_badge(entry.status)
                st.markdown(badge, unsafe_allow_html=True)

        st.divider()
        if st.button("Réinitialiser les notes", key="sim_reset", width="content"):
            state["notes"] = {}
            st.rerun()

        report = calculate_report(
            parcours,
            entries,
            semester=period,
            selected_bo_codes=state.get("selected_bo") or None,
        )

        st.markdown("#### Résultats en direct")

        if report.semester_average is not None:
            avg = report.semester_average
            color = "#16a34a" if avg >= VALIDATION_THRESHOLD else (
                "#ca8a04" if avg >= COMPENSATION_THRESHOLD else "#dc2626"
            )
            st.markdown(
                f'<div style="font-size:1.2rem;font-weight:700;color:{color};">'
                f"Moyenne {period.upper() if period in ('s1','s2') else period}: "
                f"<span style='font-size:1.6rem;'>{avg:.2f}/20</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        bcc_table = []
        for block in report.bcc_results:
            bcc_table.append(
                {
                    "BCC": block.name,
                    "Moyenne": f"{block.average:.2f}" if block.average is not None else "—",
                    "Acquis ?": "✅" if block.acquired else "❌",
                    "ECTS pesés": int(block.weight),
                }
            )
        if bcc_table:
            st.markdown("**Moyennes par BCC**")
            st.dataframe(bcc_table, hide_index=True, width="stretch")

        if report.group_results:
            grp_rows = []
            for grp in report.group_results:
                grp_rows.append(
                    {
                        "Groupe": grp["label"],
                        "Moyenne": f"{grp['average']:.2f}",
                        "Seuil": f"{grp['threshold']:.0f}",
                        "Compensation OK ?": "✅" if grp["passed"] else "❌",
                    }
                )
            st.markdown("**Compensation entre BCC**")
            st.dataframe(grp_rows, hide_index=True, width="stretch")

        if report.warnings:
            with st.expander(f"Avertissements ({len(report.warnings)})", expanded=False):
                for warn in report.warnings:
                    st.markdown(f"- {warn}")
        else:
            st.success("Aucun avertissement — tout valide pour le moment.", icon=":material/check_circle:")

        st.divider()
        if st.button(
            "Envoyer ce simulateur dans le chat",
            key="sim_send_chat",
            type="primary",
            width="content",
        ):
            from chatbot_core.grade_calculator import format_report

            close_simulator()
            return format_report(report)
    return None


__all__ = [
    "SIMULATOR_TRIGGER",
    "detect_simulator_intent",
    "open_simulator",
    "close_simulator",
    "is_open",
    "render_simulator_panel",
]
