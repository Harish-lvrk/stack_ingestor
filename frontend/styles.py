"""frontend/styles.py — Professional navy theme for STAC Manager."""

import streamlit as st


def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── App background — lighter navy, readable everywhere ──────────────── */
[data-testid="stAppViewContainer"] {
    background: #0f1722 !important;
}
[data-testid="stHeader"] {
    background: rgba(15, 23, 34, 0.97) !important;
    border-bottom: 1px solid #253350 !important;
}

/* ── Sidebar (collapsed by default, just in case) ───────────────────── */
section[data-testid="stSidebar"] {
    background: #162032 !important;
}

/* ── Default text ───────────────────────────────────────────────────── */
p, span, label, div {
    color: #dce6f0;
}

/* ── Tabs ───────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #162032 !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid #253350 !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #7a9cc4 !important;
    padding: 0.45rem 1.2rem !important;
    border: none !important;
    transition: all 0.2s ease !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
    color: #b8d0ed !important;
    background: rgba(77,157,224,0.08) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background: linear-gradient(135deg, #1a3d72, #1e4f94) !important;
    color: #7ec8f7 !important;
    box-shadow: 0 2px 10px rgba(77,157,224,0.25) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* ── Step headers ────────────────────────────────────────────────────── */
.step-header {
    font-size: 0.97rem;
    font-weight: 700;
    margin: 1.6rem 0 0.75rem;
    padding: 0.55rem 1rem;
    background: rgba(77,157,224,0.08);
    border-left: 3px solid #4d9de0;
    border-radius: 0 8px 8px 0;
    color: #cde0f5;
}
.section-title {
    font-size: 0.97rem;
    font-weight: 700;
    margin: 1.4rem 0 0.75rem;
    padding: 0.55rem 1rem;
    background: rgba(65,193,200,0.08);
    border-left: 3px solid #41c1c8;
    border-radius: 0 8px 8px 0;
    color: #8ae4e8;
}

/* ── Cards / Expanders ───────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #162032 !important;
    border: 1px solid #253350 !important;
    border-radius: 10px !important;
    margin-bottom: 0.5rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stExpander"]:hover {
    border-color: #3a6098 !important;
    box-shadow: 0 0 14px rgba(77,157,224,0.1) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #cde0f5 !important;
    padding: 0.7rem 1rem !important;
}

/* ── Forms ───────────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: #162032 !important;
    border: 1px solid #253350 !important;
    border-radius: 10px !important;
    padding: 1.1rem 1.3rem 0.7rem !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: #0f1f35 !important;
    border: 1px solid #2b4165 !important;
    border-radius: 7px !important;
    color: #dce6f0 !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #4d9de0 !important;
    box-shadow: 0 0 0 3px rgba(77,157,224,0.15) !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
button[kind="primary"] {
    background: linear-gradient(135deg, #1a5fa8, #2b83d6) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: #fff !important;
    box-shadow: 0 2px 10px rgba(43,131,214,0.4) !important;
    transition: opacity 0.2s, transform 0.1s !important;
}
button[kind="primary"]:hover {
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
}
button[kind="secondary"] {
    background: #1e2e46 !important;
    border: 1px solid #2b4165 !important;
    border-radius: 8px !important;
    color: #b0c8e8 !important;
}
button[kind="secondary"]:hover {
    background: #253650 !important;
    border-color: #4d9de0 !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #162032 !important;
    border: 1px solid #253350 !important;
    border-radius: 10px !important;
    padding: 0.6rem 0.9rem !important;
}
[data-testid="stMetricLabel"] { color: #7a9cc4 !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"] { color: #7ec8f7 !important; font-weight: 700 !important; }

/* ── JSON viewer ─────────────────────────────────────────────────────── */
[data-testid="stJson"] {
    background: #0a1220 !important;
    border: 1px solid #253350 !important;
    border-radius: 10px !important;
    max-height: 420px !important;
    overflow: auto !important;
}

/* ── Dividers ────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #253350 !important;
    margin: 1.4rem 0 !important;
}

/* ── File uploader ───────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #2b4165 !important;
    border-radius: 12px !important;
    background: #111e30 !important;
    padding: 0.8rem !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #4d9de0 !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0f1722; }
::-webkit-scrollbar-thumb { background: #2b4165; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #3a6098; }
</style>
""", unsafe_allow_html=True)
