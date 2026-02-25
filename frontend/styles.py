"""frontend/styles.py — Clean professional light theme for STAC Manager."""

import streamlit as st


def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Hide Streamlit's auto-injected anchor link icon on headings */
h1 a, h2 a, h3 a { display: none !important; }

/* ── App background ─────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #f5f7fa !important;
}
[data-testid="stHeader"] {
    background: rgba(255,255,255,0.95) !important;
    border-bottom: 1px solid #e2e8f0 !important;
    backdrop-filter: blur(8px);
}

/* ── Tabs ────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #ffffff !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #64748b !important;
    padding: 0.45rem 1.2rem !important;
    border: none !important;
    transition: all 0.2s ease !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
    color: #2563eb !important;
    background: #eff6ff !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    color: #ffffff !important;
    box-shadow: 0 2px 10px rgba(37,99,235,0.3) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* ── Step headers ────────────────────────────────────────────────────── */
.step-header {
    font-size: 0.97rem;
    font-weight: 700;
    margin: 1.6rem 0 0.75rem;
    padding: 0.55rem 1rem;
    background: #eff6ff;
    border-left: 3px solid #2563eb;
    border-radius: 0 8px 8px 0;
    color: #1e40af;
}
.section-title {
    font-size: 0.97rem;
    font-weight: 700;
    margin: 1.4rem 0 0.75rem;
    padding: 0.55rem 1rem;
    background: #f0fdf4;
    border-left: 3px solid #16a34a;
    border-radius: 0 8px 8px 0;
    color: #15803d;
}

/* ── Cards / Expanders ───────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    margin-bottom: 0.55rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stExpander"]:hover {
    border-color: #93c5fd !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.1) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #1e293b !important;
    padding: 0.7rem 1rem !important;
}

/* ── Forms ───────────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.4rem 0.8rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: #f8fafc !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #1e293b !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
    background: #ffffff !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
button[kind="primary"] {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.35) !important;
    transition: opacity 0.2s, transform 0.1s !important;
}
button[kind="primary"]:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important;
}
button[kind="secondary"] {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #374151 !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}
button[kind="secondary"]:hover {
    border-color: #2563eb !important;
    color: #2563eb !important;
    background: #eff6ff !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 0.6rem 0.9rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"] { color: #2563eb !important; font-weight: 700 !important; }

/* ── JSON viewer ─────────────────────────────────────────────────────── */
[data-testid="stJson"] {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    max-height: 420px !important;
    overflow: auto !important;
}

/* ── Dividers ────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #e2e8f0 !important;
    margin: 1.4rem 0 !important;
}

/* ── File uploader ───────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #93c5fd !important;
    border-radius: 12px !important;
    background: #eff6ff !important;
    padding: 0.8rem !important;
    transition: border-color 0.2s, background 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: #2563eb !important;
    background: #dbeafe !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>
""", unsafe_allow_html=True)
