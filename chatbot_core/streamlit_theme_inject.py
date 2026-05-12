"""Inject Streamlit chrome styles into the parent page.

Modern Streamlit strips ``<style>`` tags inside ``st.markdown(..., unsafe_allow_html=True)``
and leaves the stylesheet body as plain text on the page. The workaround is to
append a ``<style>`` node to ``window.parent.document.head`` via
``components.html`` (same pattern used for microphone / clipboard helpers).

This module exposes the stylesheet string plus a thin injector so ``app/chatbot.py``
does not carry a mega-string next to unrelated logic.

Also load Google Fonts outside the sanitized markdown path — they work when
attached to ``parent.head``.
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

_FONT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
)

_CHATBOT_CSS = r"""
:root {
    --brand-50:#eef8ff; --brand-100:#d7efff; --brand-500:#00a6c8;
    --brand-600:#0057b8; --brand-700:#00428c; --brand-900:#071a35;
    --accent-cyan:#00a6c8; --accent-gold:#f4b321; --accent-gold-soft:#fff5d8;
    --ink-900:#0b1220; --ink-800:#0f172a; --ink-700:#1e293b;
    --ink-600:#334155; --ink-500:#475569; --ink-400:#64748b; --ink-300:#94a3b8;
    --line:#d9e2ef; --line-soft:#edf3f8; --bg:#f6f8fb; --surface:#ffffff;
    --shadow-sm:0 1px 2px rgba(15,23,42,.04);
    --shadow-md:0 4px 16px -2px rgba(15,23,42,.07), 0 2px 4px -1px rgba(15,23,42,.04);
    --shadow-lg:0 12px 32px -8px rgba(15,23,42,.12), 0 4px 12px -2px rgba(15,23,42,.06);
    --radius-sm:8px; --radius:12px; --radius-lg:16px;
}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: "Inter", -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    background: var(--bg) !important;
}
code, pre, kbd, samp {
    font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace !important;
}

.block-container { padding-top: 1.1rem !important; padding-bottom: 6.5rem !important; max-width: 1060px !important; }

/* ----- Hero header ----- */
.app-hero {
    position: relative;
    background:
        linear-gradient(115deg, rgba(0,87,184,.10) 0%, rgba(0,166,200,.06) 38%, transparent 39%),
        linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 24px 28px 22px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-md);
    overflow: hidden;
    text-align: left;
}
.hero-flex {
    display: flex;
    align-items: flex-start;
    gap: 18px;
    flex-wrap: wrap;
    justify-content: flex-start;
}
.hero-mark {
    width:64px;
    height:64px;
    border-radius:14px;
    background: #ffffff;
    display:flex;
    align-items:center;
    justify-content:center;
    color:var(--brand-700);
    flex-shrink:0;
    align-self:flex-start;
    border: 1px solid rgba(0,87,184,.14);
    box-shadow: 0 8px 20px -10px rgba(7,26,53,.35);
    overflow:hidden;
}
.hero-logo { width: 54px; height: 54px; object-fit: contain; display:block; }
.hero-mark svg { width: 32px; height: 32px; stroke: none; }
.hero-mark svg path { stroke: currentColor !important; }
.hero-mark svg circle { stroke: none; }
.hero-mark svg *[fill]:not([fill="none"]) { fill: currentColor; }
.hero-text {
    flex: 1;
    min-width: 0;
    text-align: left;
}
.hero-version {
    font-size:.7rem;
    color:var(--brand-700);
    letter-spacing:.06em;
    text-transform:uppercase;
    margin-bottom:8px;
    font-weight:700;
    text-align: left;
}
.app-title {
    font-size: 2rem;
    font-weight: 800;
    color: var(--ink-900);
    margin: 0;
    letter-spacing: 0;
    line-height:1.18;
}
.app-subtitle {
    color: var(--ink-500);
    margin-top: 8px;
    font-size: .98rem;
    max-width: 72ch;
    line-height: 1.5;
}

.status-row-wrap { margin-top: 12px; }
.status-row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin: 4px 0 14px; }

/* ----- Status pills ----- */
.status-pill {
    display:inline-flex;
    align-items:center;
    gap:6px;
    background: #ffffff;
    border:1px solid var(--line);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight:600;
    color: var(--ink-600);
    box-shadow: var(--shadow-sm);
}
.status-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; display:inline-block; }
.dot-on  { background:#16a34a; box-shadow:0 0 0 3px rgba(22,163,74,.18); }
.dot-off { background:#cbd5e1; }
.dot-warn{ background:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,.18); }
.status-pill.is-active { background: var(--brand-50); border-color: #9bd8e8; color: var(--brand-700); }

/* ----- Memory chips ----- */
.memory-chips-row { margin-top: 14px; text-align:left; }
.memory-chip {
    display:inline-flex;
    align-items:center;
    gap:6px;
    background: linear-gradient(180deg,#eef8ff,#dff4fb);
    border:1px solid #9bd8e8;
    color: var(--brand-700);
    border-radius: 999px;
    padding: 5px 11px;
    font-size:11.5px;
    font-weight:600;
    margin: 5px 6px 0 0;
    vertical-align: middle;
}
.memory-chip strong {
    color: var(--brand-900);
    margin-right: 3px;
    font-weight:700;
}

/* ----- Sidebar ----- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f7fbff 0%, #eef3f8 100%) !important;
    border-right: 1px solid var(--line) !important;
}
section[data-testid="stSidebar"] .stButton > button {
    border-radius: 10px !important;
    font-weight: 500 !important;
    border-color: var(--line) !important;
    transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    border-color: var(--brand-500) !important;
    background: var(--brand-50) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(180deg, var(--brand-600), var(--brand-900)) !important;
    border: none !important;
    color: #fff !important;
    box-shadow: 0 4px 14px -4px rgba(0,87,184,.42) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    filter: brightness(1.05);
}
section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] [data-baseweb="input"] input,
section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    border-radius: 10px !important;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] div[data-testid="stSidebarNav"] span {
    letter-spacing: 0 !important;
}
.sb-section-label {
    text-transform: uppercase;
    letter-spacing:.08em;
    color: var(--ink-400);
    font-size:11px;
    font-weight: 700;
    margin: 14px 4px 8px;
}
.empty-state-sidebar {
    background: #fff;
    border:1px dashed var(--line);
    border-radius: var(--radius);
    padding: 14px;
    color: var(--ink-500);
    font-size: 13px;
    text-align:center;
}

/* ----- Welcome + suggestions ----- */
.welcome-card {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 14px;
    box-shadow: var(--shadow-sm);
    text-align: left;
}
.welcome-card h3 { margin:0 0 6px; font-size:1.15rem; color:var(--ink-900); font-weight:700; }
.welcome-card p  { margin:0; color: var(--ink-500); font-size:.92rem; line-height:1.5; }

/* Suggestion prompts: ONLY target buttons created with key="suggestion_<n>".
   Avoids clobbering wizard buttons, feedback buttons, etc. */
[class*="st-key-suggestion_"] button {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    box-shadow: var(--shadow-sm);
    transition: border-color .18s ease, background .18s ease, box-shadow .18s ease, transform .18s ease;
    min-height: 48px !important;
    height: auto !important;
    line-height: 1.35 !important;
    font-weight: 600 !important;
    border-radius: var(--radius) !important;
    padding: 12px 16px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    color: var(--ink-900) !important;
    margin-bottom: 0 !important;
}
[class*="st-key-suggestion_"] button:hover {
    border-color: var(--brand-500) !important;
    background: var(--brand-50) !important;
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
[class*="st-key-suggestion_"] button p {
    text-align: left !important;
    margin: 0 !important;
    line-height: 1.35 !important;
    font-size: .96rem !important;
}
/* Caption under the suggestion button */
[class*="st-key-suggestion_"] + div [data-testid="stCaptionContainer"],
[class*="st-key-suggestion_"] ~ div [data-testid="stCaptionContainer"] {
    margin: -2px 4px 12px 4px !important;
    color: var(--ink-500) !important;
}

section[data-testid="stSidebar"] button { box-shadow: none !important; }

/* Sidebar conversation rows: square icon-only buttons for pin / delete */
section[data-testid="stSidebar"] [class*="st-key-conv_pin_"] button,
section[data-testid="stSidebar"] [class*="st-key-conv_del_"] button {
    width: 100% !important;
    min-width: 0 !important;
    padding: 6px 0 !important;
    aspect-ratio: 1 / 1;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: var(--ink-500) !important;
}
section[data-testid="stSidebar"] [class*="st-key-conv_del_"] button:hover {
    border-color: #fca5a5 !important;
    background: #fef2f2 !important;
    color: #b91c1c !important;
}
section[data-testid="stSidebar"] [class*="st-key-conv_open_"] button {
    text-align: left !important;
    justify-content: flex-start !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
section[data-testid="stSidebar"] [class*="st-key-conv_open_"] button p {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    margin: 0 !important;
}

/* Assistant message action toolbar: compact, consistent icon row */
[data-testid="stChatMessage"] [class*="st-key-actions_"] button {
    min-width: 36px !important;
    height: 34px !important;
    padding: 4px 10px !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    color: var(--ink-500) !important;
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stChatMessage"] [class*="st-key-actions_"] button:hover {
    background: var(--line-soft) !important;
    color: var(--ink-800) !important;
    border-color: var(--line-soft) !important;
}
[data-testid="stChatMessage"] [class*="st-key-actions_"] button[kind="primary"] {
    background: var(--brand-50) !important;
    color: var(--brand-700) !important;
    border-color: #bfdbfe !important;
}

/* ----- Chat messages ----- */
[data-testid="stChatMessage"] {
    border-radius: var(--radius) !important;
    border: 1px solid var(--line-soft);
    box-shadow: var(--shadow-sm);
    padding: 14px 16px !important;
    background: var(--surface) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(180deg, #eff8ff, #e8f6fb) !important;
    border-color: #cfe9f3 !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p:last-child { margin-bottom: 0 !important; }

[data-testid="stChatMessage"] table {
    border-collapse: separate;
    border-spacing: 0;
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
    font-size: 13.5px;
    margin: 8px 0;
}
[data-testid="stChatMessage"] thead th {
    background: var(--line-soft);
    color: var(--ink-800);
    font-weight: 700;
    padding: 8px 12px;
    border-bottom: 1px solid var(--line);
}
[data-testid="stChatMessage"] tbody td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--line-soft);
}
[data-testid="stChatMessage"] tbody tr:nth-child(even) td { background: #fafbfd; }

[data-testid="stChatMessage"] pre {
    background: var(--brand-900) !important;
    color:#e2e8f0 !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
    font-size: 13px !important;
}
[data-testid="stChatMessage"] code:not(pre code) {
    background: var(--brand-50);
    color: var(--brand-700);
    padding: 1px 6px;
    border-radius: 5px;
    font-size: 90%;
}

/* ----- Voice & TTS (iframe buttons sit in main doc; parent styles help) ----- */
.voice-btn-container {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-left: 0;
    z-index: 9999;
    flex: 0 0 auto;
}
.voice-btn {
    width: 38px !important;
    height: 38px !important;
    border-radius: 10px !important;
    border: 1px solid var(--line);
    background: var(--brand-50);
    color: var(--brand-700);
    cursor: pointer;
    box-shadow: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}
.voice-btn.recording { border-color: var(--brand-600) !important; background: var(--brand-50) !important; }
.voice-btn:hover { border-color: var(--brand-500); background: #ffffff; }
.voice-btn svg {
    width: 18px;
    height: 18px;
    stroke: currentColor;
}

.tts-wrap button {
    border: 0;
    background: transparent;
    color: var(--ink-500);
    min-width: 32px;
    height: 30px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: background .15s ease, color .15s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.tts-wrap button:hover {
    background: var(--line-soft);
    color: var(--ink-800);
}
.tts-wrap svg {
    width: 17px;
    height: 17px;
    stroke: currentColor;
    vertical-align: middle;
}

/* ----- Chat input ----- */
[data-testid="stChatInput"] {
    background: #ffffff !important;
    border-radius: var(--radius) !important;
    border: 1px solid var(--line) !important;
    box-shadow: var(--shadow-md) !important;
    min-height: 52px !important;
    max-height: 86px !important;
    width: 100% !important;
    max-width: 100% !important;
    display: flex !important;
    flex-direction: row !important;
    gap: 10px !important;
    align-items: center !important;
    padding: 0 12px !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--brand-500) !important;
}
[data-testid="stChatInput"] > div:not(.voice-btn-container),
[data-testid="stChatInput"] > div:not(.voice-btn-container) > div {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    flex: 1 1 auto !important;
}
[data-testid="stChatInput"] div:has(> textarea[data-testid="stChatInputTextArea"]),
[data-testid="stChatInput"] div:has(textarea[data-testid="stChatInputTextArea"]) {
    flex: 1 1 auto !important;
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
}
[data-testid="stChatInput"] textarea[data-testid="stChatInputTextArea"] {
    min-height: 42px !important;
    max-height: 72px !important;
    width: 100% !important;
    max-width: none !important;
    padding-top: 10px !important;
    padding-bottom: 10px !important;
    font-size: 15px !important;
}
[data-testid="stChatInput"] button {
    border-radius: 10px !important;
}

[data-testid="stExpander"] {
    border-radius: var(--radius) !important;
    border-color: var(--line) !important;
}
[data-testid="stExpander"] > details > summary {
    font-weight: 600;
    color: var(--ink-700);
}

h1, h2, h3 {
    letter-spacing: 0;
    color: var(--ink-900);
}

.stToast { border-radius: 10px !important; }

/* Hide Streamlit chrome (menu / footer / dev toolbar) BUT keep the header
   structure so the sidebar collapse / expand chevron stays clickable.
   Hiding the whole header[data-testid="stHeader"] used to also hide the
   floating "open sidebar" control, leaving the user with no way to bring
   the sidebar back once it was closed. */
#MainMenu, footer { visibility: hidden !important; height: 0 !important; min-height: 0 !important; }
header[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
    height: 2.75rem !important;
}
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* Floating button shown by Streamlit when the sidebar is collapsed.
   Force it visible so users can always reopen the sidebar. */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"][aria-label*="sidebar" i],
button[kind="headerNoPadding"][aria-label*="sidebar" i] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 1000 !important;
}
[data-testid="collapsedControl"] {
    position: fixed !important;
    top: 0.65rem !important;
    left: 0.65rem !important;
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    padding: 0.35rem 0.5rem !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="collapsedControl"] svg {
    color: var(--ink-700) !important;
    fill: var(--ink-700) !important;
}

/* Streamlit 1.55 renders the native expand button at 0x0 after the sidebar
   closes. Give it a real hit target so the menu remains clickable. */
body:has([data-testid="stSidebar"][aria-expanded="false"]) button[data-testid="stExpandSidebarButton"] {
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    width: 44px !important;
    height: 38px !important;
    min-width: 44px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 2147483646 !important;
    background: #ffffff !important;
    color: var(--brand-700) !important;
    border: 1px solid var(--line) !important;
    border-radius: 12px !important;
    box-shadow: 0 6px 20px -8px rgba(15,23,42,0.25) !important;
}
#m1-open-sidebar-fab {
    display: none !important;
}
body:has([data-testid="stSidebar"][aria-expanded="false"]) #m1-open-sidebar-fab {
    display: inline-flex !important;
}
main .block-container { padding-top: 1.25rem !important; }
"""


def inject_chatbot_theme() -> None:
    """Must run once per page immediately after ``st.set_page_config``."""
    if hasattr(st, "html"):
        style_html = f"<style>@import url({json.dumps(_FONT_URL)});\n{_CHATBOT_CSS.strip()}</style>"
        st.html(style_html)

    css_js = json.dumps(_CHATBOT_CSS.strip())
    font_js = json.dumps(_FONT_URL)
    components.html(
        f"""
        <script>
        (function() {{
            try {{
                const doc = window.parent.document;
                if (!doc) return;
                const fontHref = {font_js};
                if (!doc.querySelector('link[data-m1-amis-chat-font="1"]')) {{
                    const L = doc.createElement('link');
                    L.rel = 'stylesheet';
                    L.href = fontHref;
                    L.setAttribute('data-m1-amis-chat-font', '1');
                    doc.head.appendChild(L);
                }}
                let sheet = doc.getElementById('m1-amis-chatbot-styles');
                if (!sheet) {{
                    sheet = doc.createElement('style');
                    sheet.id = 'm1-amis-chatbot-styles';
                    sheet.type = 'text/css';
                    doc.head.appendChild(sheet);
                }}
                sheet.textContent = {css_js};
            }} catch (e) {{ }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


_SIDEBAR_REOPEN_JS = r"""
<script>
(function() {
    try {
        const doc = window.parent.document;
        if (!doc || doc.getElementById('m1-open-sidebar-fab')) return;

        // Build the floating "open sidebar" button.
        const btn = doc.createElement('button');
        btn.id = 'm1-open-sidebar-fab';
        btn.type = 'button';
        btn.setAttribute('aria-label', "Ouvrir la barre latérale");
        btn.setAttribute('title', "Ouvrir la barre latérale");
        btn.setAttribute(
            'onclick',
            "const b=document.querySelector('[data-testid=\"stExpandSidebarButton\"]'); if(b){b.click();} this.style.display='none';"
        );
        btn.innerHTML = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" '
          + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
          + '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>'
          + '<line x1="9" y1="3" x2="9" y2="21"></line>'
          + '<polyline points="14 9 17 12 14 15"></polyline>'
          + '</svg>'
          + '<span>Menu</span>'
        );

        // Inline style so we never rely on parent CSS being loaded.
        Object.assign(btn.style, {
            position: 'fixed',
            top: '12px',
            left: '12px',
            zIndex: '2147483647',
            display: 'none',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 12px',
            borderRadius: '12px',
            border: '1px solid rgba(15, 23, 42, 0.10)',
            background: '#ffffff',
            color: '#0f172a',
            font: "600 13px/1 'Inter', system-ui, sans-serif",
            cursor: 'pointer',
            pointerEvents: 'auto',
            userSelect: 'none',
            boxShadow: '0 6px 20px -8px rgba(15,23,42,0.25)',
        });
        btn.addEventListener('mouseenter', () => { btn.style.background = '#f8fafc'; });
        btn.addEventListener('mouseleave', () => { btn.style.background = '#ffffff'; });

        function isVisible(el) {
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const style = window.parent.getComputedStyle(el);
            return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        }

        function clickNativeSidebarToggle() {
            const expand = doc.querySelector('[data-testid="stExpandSidebarButton"]');
            if (expand) {
                window.parent.setTimeout(() => {
                    const MouseEvt = window.parent.MouseEvent;
                    expand.dispatchEvent(new MouseEvt('pointerdown', { bubbles: true, cancelable: true, view: window.parent }));
                    expand.dispatchEvent(new MouseEvt('mousedown', { bubbles: true, cancelable: true, view: window.parent }));
                    expand.dispatchEvent(new MouseEvt('mouseup', { bubbles: true, cancelable: true, view: window.parent }));
                    expand.dispatchEvent(new MouseEvt('click', { bubbles: true, cancelable: true, view: window.parent }));
                    expand.click();
                }, 0);
                return true;
            }
            const candidates = [
                '[data-testid="stExpandSidebarButton"]',
                '[data-testid="stSidebarCollapsedControl"] button',
                '[data-testid="stSidebarCollapseButton"] button',
                '[data-testid="stSidebarCollapseButton"]',
                '[data-testid="collapsedControl"] button',
                '[data-testid="collapsedControl"]',
                '[data-testid="stSidebarCollapsedControl"]',
                'button[title*="sidebar" i]',
                'button[aria-label*="barre latérale" i]',
                'button[aria-label="Open sidebar" i]',
                'button[aria-label*="sidebar" i]',
                '[role="button"][aria-label*="sidebar" i]',
            ];
            for (const sel of candidates) {
                const el = doc.querySelector(sel);
                if (el && el !== btn && (isVisible(el) || sel.includes('stExpandSidebarButton'))) {
                    el.click();
                    return true;
                }
            }
            const allButtons = Array.from(doc.querySelectorAll('button, [role="button"], [data-testid]'));
            const fuzzy = allButtons.find((el) => {
                if (!isVisible(el) || el === btn) return false;
                const haystack = [
                    el.getAttribute('aria-label'),
                    el.getAttribute('title'),
                    el.getAttribute('data-testid'),
                    el.textContent,
                    el.className,
                ].join(' ').toLowerCase();
                return haystack.includes('sidebar')
                    || haystack.includes('barre latérale')
                    || haystack.includes('collapsed')
                    || haystack.includes('collapse');
            });
            if (fuzzy) { fuzzy.click(); return true; }
            return false;
        }

        btn.addEventListener('pointerdown', (e) => {
            e.stopPropagation();
        });
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            clickNativeSidebarToggle();
            btn.style.display = 'none';
            window.parent.setTimeout(sync, 250);
            window.parent.setTimeout(sync, 800);
        });

        doc.body.appendChild(btn);

        // Toggle visibility based on whether the sidebar is collapsed.
        const sync = () => {
            const sb = doc.querySelector('[data-testid="stSidebar"]');
            if (!sb) { btn.style.display = 'inline-flex'; return; }
            const aria = sb.getAttribute('aria-expanded');
            const collapsedAttr = sb.getAttribute('aria-hidden') === 'true' || aria === 'false';
            const collapsedWidth = sb.getBoundingClientRect().width < 80;
            const isCollapsed = collapsedAttr || collapsedWidth;
            btn.style.display = isCollapsed ? 'inline-flex' : 'none';
        };
        sync();
        const obs = new MutationObserver(sync);
        obs.observe(doc.body, { childList: true, subtree: true, attributes: true,
                                attributeFilter: ['aria-expanded', 'aria-hidden', 'class', 'style'] });
        window.addEventListener('resize', sync);
        window.setInterval(sync, 800);
    } catch (e) { /* swallow */ }
})();
</script>
"""


def inject_sidebar_reopen_button() -> None:
    """Render a small floating button that re-opens the sidebar when collapsed.

    Streamlit's native expand chevron lives inside the page header. Some
    custom themes or browser zoom levels make it hard to find, so we render
    our own fixed-position fallback in the top-left corner of the page.
    The button is hidden whenever the sidebar is already expanded.
    """
    components.html(_SIDEBAR_REOPEN_JS, height=0, width=0)


__all__ = [
    "inject_chatbot_theme",
    "inject_sidebar_reopen_button",
    "_FONT_URL",
]
