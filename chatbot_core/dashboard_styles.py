"""Styles partages pour le dashboard Streamlit."""

DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --admin-brand:#0b57c7;
        --admin-brand-dark:#073f9c;
        --admin-cyan:#08a6bd;
        --admin-ink:#0b1220;
        --admin-muted:#5b667a;
        --admin-line:#dce5f2;
        --admin-line-soft:#edf2f7;
        --admin-bg:#f7faff;
        --admin-surface:#ffffff;
        --admin-shadow:0 10px 34px -22px rgba(15, 23, 42, .38), 0 2px 6px rgba(15, 23, 42, .05);
    }

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif !important;
        background:
            radial-gradient(900px 260px at 12% -12%, rgba(11,87,199,.08), transparent 62%),
            radial-gradient(720px 260px at 92% -8%, rgba(8,166,189,.08), transparent 62%),
            var(--admin-bg) !important;
        color: var(--admin-ink);
    }
    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 2rem !important;
        max-width: 1440px !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
    }
    #MainMenu, footer { visibility: hidden !important; }

    .admin-topbar {
        display:flex;
        align-items:center;
        gap:12px;
        margin: 0 0 12px;
    }
    .admin-logo {
        width:34px;
        height:34px;
        border-radius:10px;
        display:grid;
        place-items:center;
        color:#ffffff;
        background: linear-gradient(180deg, var(--admin-brand), var(--admin-brand-dark));
        box-shadow: 0 10px 22px -14px rgba(11,87,199,.65);
    }
    .admin-logo svg { width:22px; height:22px; stroke: currentColor; }
    .admin-logo svg path { fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
    .admin-wordmark {
        font-size:18px;
        font-weight:800;
        color:var(--admin-brand);
        letter-spacing:.01em;
    }
    .dashboard-header {
        font-size: 30px;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.15;
        color: var(--admin-ink);
        margin: 8px 0 6px;
    }
    .dashboard-subtitle {
        color: var(--admin-muted);
        font-size: 14.5px;
        line-height:1.45;
        margin-bottom: 8px;
    }

    [data-testid="stDateInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div,
    [data-baseweb="select"] {
        border-radius: 10px !important;
    }
    .stButton > button,
    .stDownloadButton > button {
        border-radius: 10px !important;
        border-color: var(--admin-line) !important;
        box-shadow: 0 1px 2px rgba(15,23,42,.04) !important;
        font-weight: 600 !important;
        min-height: 40px !important;
    }
    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(180deg, var(--admin-brand), var(--admin-brand-dark)) !important;
        color:#fff !important;
        border:0 !important;
    }

    .metric-row-spacer { margin-top: 14px; }
    .stat-card {
        min-height: 116px;
        background: rgba(255,255,255,.94);
        border: 1px solid var(--admin-line);
        border-radius: 12px;
        padding: 18px 18px 16px;
        box-shadow: var(--admin-shadow);
        display:flex;
        flex-direction:column;
        justify-content:space-between;
    }
    .stat-head {
        display:flex;
        align-items:center;
        gap:13px;
    }
    .stat-icon {
        width: 42px;
        height: 42px;
        border-radius: 999px;
        display:grid;
        place-items:center;
        flex: 0 0 auto;
    }
    .stat-icon svg {
        width: 23px;
        height: 23px;
        stroke: currentColor;
        fill: none;
        stroke-width: 2.1;
        stroke-linecap: round;
        stroke-linejoin: round;
    }
    .stat-label {
        color: #334155;
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 5px;
    }
    .stat-value {
        font-size: 24px;
        line-height: 1;
        font-weight: 800;
        letter-spacing: 0;
    }
    .stat-trend {
        display:flex;
        align-items:center;
        gap:6px;
        color: #64748b;
        font-size: 12px;
        margin-top: 14px;
        white-space: nowrap;
    }
    .stat-trend strong { font-weight: 700; }
    .trend-up strong { color:#15803d; }
    .trend-down strong { color:#dc2626; }
    .stat-trend svg {
        width: 14px;
        height: 14px;
        stroke: currentColor;
        fill: none;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
        flex: 0 0 auto;
    }
    .stat-trend svg path { fill:none; stroke:currentColor; }

    [data-testid="stTabs"] {
        margin-top: 12px;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 1px solid #d8e1ee;
        gap: 18px;
    }
    [data-testid="stTabs"] [role="tab"] {
        padding: 14px 6px 12px !important;
        font-size: 13px !important;
        color: #1f2937 !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: var(--admin-brand) !important;
        font-weight: 800 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background: var(--admin-brand) !important;
        height: 3px !important;
        border-radius: 999px !important;
    }

    .section-title-row {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin: 18px 0 12px;
    }
    .section-title {
        font-size: 18px;
        font-weight: 800;
        color: var(--admin-ink);
        margin:0;
    }
    .count-pill {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-width: 30px;
        height: 26px;
        padding: 0 10px;
        border-radius: 999px;
        background:#f7f9fc;
        border:1px solid var(--admin-line);
        color:#64748b;
        font-size:12px;
        font-weight:700;
    }

    .unanswered-card {
        position: relative;
        background: linear-gradient(90deg, #fff7d6, #fffdf5 72%);
        border: 1px solid #f5dfa6;
        border-left: 4px solid #f5b400;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
        box-shadow: 0 2px 8px -7px rgba(92, 65, 0, .42);
    }
    .unanswered-top {
        display:flex;
        justify-content:space-between;
        gap:12px;
        color:#64748b;
        font-size:11.5px;
        margin-bottom: 8px;
    }
    .unanswered-question {
        color:#0f172a;
        font-size:13.5px;
        font-weight: 500;
        line-height: 1.4;
        margin-right: 24px;
    }
    .chip {
        display:inline-flex;
        align-items:center;
        height: 21px;
        padding: 0 10px;
        margin: 9px 5px 0 0;
        border: 1px solid #e3d5b8;
        border-radius: 999px;
        background: rgba(255,255,255,.74);
        color:#4b5563;
        font-size: 11px;
        font-weight: 600;
    }
    .card-menu {
        position:absolute;
        right: 14px;
        top: 38px;
        color:#475569;
        font-weight:800;
        letter-spacing:2px;
    }

    .interaction-list {
        background: rgba(255,255,255,.96);
        border: 1px solid var(--admin-line);
        border-radius: 12px;
        box-shadow: var(--admin-shadow);
        overflow:hidden;
    }
    .interaction-card {
        display:grid;
        grid-template-columns: 28px minmax(0, 1fr) 64px;
        gap: 12px;
        align-items:start;
        padding: 14px 14px;
        border-bottom: 1px solid var(--admin-line-soft);
    }
    .interaction-card:last-child { border-bottom: 0; }
    .interaction-card:hover { background:#f8fbff; }
    .interaction-status {
        width:24px;
        height:24px;
        border-radius:50%;
        display:grid;
        place-items:center;
        color:#fff;
        margin-top:2px;
    }
    .interaction-status svg {
        width:15px;
        height:15px;
        stroke:currentColor;
        fill:none;
        stroke-width:2.4;
        stroke-linecap:round;
        stroke-linejoin:round;
    }
    .interaction-status.ok { background:#0f8a43; }
    .interaction-status.warn { background:#3167d5; }
    .interaction-meta {
        color:#64748b;
        font-size:11.5px;
        font-weight:600;
        margin-bottom:5px;
    }
    .interaction-meta strong { color:#0f172a; }
    .interaction-question {
        font-size:13.3px;
        color:#0f172a;
        font-weight: 500;
        line-height: 1.35;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
    }
    .interaction-snippet {
        margin-top: 4px;
        color:#64748b;
        font-size:12px;
        line-height:1.35;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
    }
    .interaction-source {
        color:#475569;
        font-size:12px;
        text-align:right;
        line-height:1.35;
    }
    .interaction-link {
        display:inline-flex;
        margin: 12px 14px 14px;
        color:var(--admin-brand);
        font-weight:700;
        font-size:13px;
        text-decoration:none;
    }

    .admin-footer {
        text-align:center;
        color:#64748b;
        font-size:12px;
        margin: 26px 0 4px;
    }

    @media (max-width: 900px) {
        .dashboard-header { font-size: 25px; }
        .stat-card { min-height: 108px; }
        .interaction-card { grid-template-columns: 28px minmax(0, 1fr); }
        .interaction-source { grid-column: 2; text-align:left; }
    }
</style>
"""
