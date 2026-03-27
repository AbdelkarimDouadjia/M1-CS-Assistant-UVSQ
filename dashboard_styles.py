"""Styles partages pour le dashboard Streamlit."""

DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700;800&display=swap');

    .block-container { padding-top: 3rem; }

    .stat-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-label {
        color: #64748b;
        font-size: 14px;
        font-weight: 500;
    }
    .stat-value {
        color: #0f172a;
        font-size: 28px;
        font-weight: 700;
        margin-top: 4px;
    }
    .stat-badge-green {
        display: inline-block;
        background: #f0fdf4;
        color: #16a34a;
        font-size: 12px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
    }
    .stat-badge-red {
        display: inline-block;
        background: #fef2f2;
        color: #dc2626;
        font-size: 12px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
    }

    .unanswered-card {
        background: #fefce8;
        border-left: 4px solid #facc15;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .unanswered-label {
        color: #854d0e;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .unanswered-question {
        color: #334155;
        font-size: 14px;
        font-style: italic;
    }

    .interaction-card {
        padding: 12px 16px;
        border-bottom: 1px solid #f1f5f9;
    }
    .interaction-card:hover {
        background: #f8fafc;
    }
    .interaction-user {
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
    }
    .interaction-time {
        font-size: 11px;
        color: #94a3b8;
    }
    .interaction-question {
        font-size: 13px;
        color: #64748b;
        margin-top: 2px;
    }
    .dot-green {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #22c55e;
        border-radius: 50%;
        margin-right: 6px;
    }
    .dot-yellow {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #eab308;
        border-radius: 50%;
        margin-right: 6px;
    }

    .dashboard-header {
        font-size: 32px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .dashboard-subtitle {
        color: #64748b;
        font-size: 15px;
    }
</style>
"""
