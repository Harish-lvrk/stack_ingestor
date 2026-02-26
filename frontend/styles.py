"""frontend/styles.py — Professional SaaS light theme for STAC Manager."""

import streamlit as st


def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Hide Streamlit's auto-injected anchor link icon on headings */
h1 a, h2 a, h3 a { display: none !important; }

/* ── App background — Clean Slate SaaS Palette ──────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #fdfdfd !important; /* Slightly brighter for map-heavy UI */
}
[data-testid="stHeader"] {
    background: rgba(255, 255, 255, 0.9) !important;
    border-bottom: 1px solid #e2e8f0 !important;
    backdrop-filter: blur(12px);
}

/* ── Tabs ── Pill design with Indigo accents ────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #ffffff !important;
    border-radius: 100px !important;
    padding: 6px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 1.5rem !important;
    width: fit-content !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 100px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #64748b !important; /* Slate-500 */
    padding: 0.5rem 1.4rem !important;
    border: none !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
    color: #4f46e5 !important; /* Indigo-600 */
    background: #f1f5f9 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background: #4f46e5 !important; /* Indigo-600 */
    color: #ffffff !important;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* ── Step headers ────────────────────────────────────────────────────── */
.step-header {
    font-size: 0.95rem;
    font-weight: 700;
    margin: 2rem 0 1rem;
    padding: 0.6rem 1.1rem;
    background: #eef2ff; /* Indigo-50 */
    border-left: 4px solid #4f46e5;
    border-radius: 4px 12px 12px 4px;
    color: #3730a3; /* Indigo-800 */
    letter-spacing: -0.01em;
}
.section-title {
    font-size: 0.95rem;
    font-weight: 700;
    margin: 1.8rem 0 1rem;
    padding: 0.6rem 1.1rem;
    background: #f0fdf4; /* Green-50 */
    border-left: 4px solid #16a34a;
    border-radius: 4px 12px 12px 4px;
    color: #166534; /* Green-800 */
}

/* ── Cards / Expanders — Modern shadows, no heavy borders ─────────────── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #f1f5f9 !important;
    border-radius: 14px !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stExpander"]:hover {
    border-color: #e2e8f0 !important;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08) !important;
    transform: translateY(-1px);
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #0f172a !important; /* Slate-900 */
    padding: 0.85rem 1.2rem !important;
}

/* ── Forms ───────────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid #f1f5f9 !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05) !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: #fcfdfe !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    color: #0f172a !important;
    padding: 0.5rem 0.75rem !important;
    transition: all 0.2s ease;
}

[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: #fcfdfe !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    color: #0f172a !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] div[data-testid="stMarkdownContainer"] p {
    color: #0f172a !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
    border-color: #4f46e5 !important;
    box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1) !important;
    background: #ffffff !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
button[kind="primary"] {
    background: #4f46e5 !important; /* Indigo-600 */
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    color: #ffffff !important;
    box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3) !important;
    transition: all 0.2s ease !important;
}
button[kind="primary"]:hover {
    background: #4338ca !important; /* Indigo-700 */
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(79, 70, 229, 0.4) !important;
}
button[kind="secondary"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    color: #475569 !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
button[kind="secondary"]:hover {
    border-color: #4f46e5 !important;
    color: #4f46e5 !important;
    background: #f5f7ff !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid #f1f5f9 !important;
    border-radius: 14px !important;
    padding: 1rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.8rem !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { color: #4f46e5 !important; font-weight: 800 !important; }

/* ── JSON viewer ─────────────────────────────────────────────────────── */
[data-testid="stJson"] {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* ── File uploader ───────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #c7d2fe !important;
    border-radius: 16px !important;
    background: #f5f7ff !important;
    padding: 1.5rem !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #4f46e5 !important;
    background: #eff1ff !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f8fafc; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* ── Grid & Cards ────────────────────────────────────────────────────── */
.stcard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.25rem;
    margin-top: 1rem;
}

.stcard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem;
    transition: all 0.2s ease;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.stcard:hover {
    border-color: #4f46e5;
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
}

.thumbnail-container {
    width: 100%;
    aspect-ratio: 16/9;
    background: #f1f5f9;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 0.75rem;
    border: 1px solid #e2e8f0;
}

.thumbnail-container img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

/* ── Data Tables ────────────────────────────────────────────────────── */
.stac-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.88rem;
}

.stac-table tr {
    border-bottom: 1px solid #f1f5f9;
}

.stac-table td {
    padding: 0.6rem 0.5rem;
    color: #475569;
}

.stac-table td:first-child {
    font-weight: 600;
    color: #0f172a;
    width: 35%;
}

/* ── Map Wrapper ────────────────────────────────────────────────────── */
.map-container {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    margin-bottom: 1.5rem;
}

/* ── Spacing overrides ────────────────────────────────────────────────── */
.stTabs { margin-top: 1rem; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #0f172a !important; }
</style>
""", unsafe_allow_html=True)
