"""frontend/styles.py — Professional SaaS theme with Dark/Light mode support."""

import streamlit as st


def inject_css() -> None:
    """Inject global CSS using custom properties for dark/light mode toggling."""
    # Dark mode state stored in session state
    dark = st.session_state.get("dark_mode", False)

    # Choose colour tokens based on mode
    if dark:
        tokens = """
        --bg-app:        #0f1117;
        --bg-card:       #1a1d27;
        --bg-input:      #1e2130;
        --bg-header:     rgba(15, 17, 23, 0.95);
        --bg-tab-bar:    #1a1d27;
        --bg-tab-active: #4f46e5;
        --bg-step:       #1e1b4b;
        --bg-section:    #052e16;
        --bg-uploader:   #1e2130;
        --bg-json:       #161926;
        --bg-metric:     #1a1d27;
        --bg-form:       #1a1d27;
        --bg-expander:   #1a1d27;
        --bg-scrollbar:  #1a1d27;
        --bg-thumb:      #334155;
        --bg-thumb-h:    #475569;
        --bg-thumbnail:  #1e2130;

        --text-primary:  #f1f5f9;
        --text-muted:    #94a3b8;
        --text-head:     #e2e8f0;

        --border-main:   #2d3148;
        --border-card:   #2d3148;
        --border-input:  #374151;

        --accent:        #6366f1;
        --accent-hover:  #818cf8;
        --shadow-card:   rgba(0,0,0,0.4);
        --shadow-accent: rgba(99, 102, 241, 0.4);
        """
    else:
        tokens = """
        --bg-app:        #fdfdfd;
        --bg-card:       #ffffff;
        --bg-input:      #fcfdfe;
        --bg-header:     rgba(255,255,255,0.9);
        --bg-tab-bar:    #ffffff;
        --bg-tab-active: #4f46e5;
        --bg-step:       #eef2ff;
        --bg-section:    #f0fdf4;
        --bg-uploader:   #f5f7ff;
        --bg-json:       #f8fafc;
        --bg-metric:     #ffffff;
        --bg-form:       #ffffff;
        --bg-expander:   #ffffff;
        --bg-scrollbar:  #f8fafc;
        --bg-thumb:      #cbd5e1;
        --bg-thumb-h:    #94a3b8;
        --bg-thumbnail:  #f1f5f9;

        --text-primary:  #0f172a;
        --text-muted:    #64748b;
        --text-head:     #0f172a;

        --border-main:   #e2e8f0;
        --border-card:   #e2e8f0;
        --border-input:  #e2e8f0;

        --accent:        #4f46e5;
        --accent-hover:  #4338ca;
        --shadow-card:   rgba(0,0,0,0.05);
        --shadow-accent: rgba(79, 70, 229, 0.35);
        """

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
    {tokens}
}}

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}

h1 a, h2 a, h3 a {{ display: none !important; }}

/* ── App background ──────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {{
    background: var(--bg-app) !important;
}}
[data-testid="stHeader"] {{
    background: var(--bg-header) !important;
    border-bottom: 1px solid var(--border-main) !important;
    backdrop-filter: blur(12px);
}}

/* ── Tabs — Pill design ─────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: var(--bg-tab-bar) !important;
    border-radius: 100px !important;
    padding: 6px !important;
    border: 1px solid var(--border-main) !important;
    box-shadow: 0 4px 6px -1px var(--shadow-card) !important;
    margin-bottom: 1.5rem !important;
    width: fit-content !important;
}}
[data-testid="stTabs"] button[data-baseweb="tab"] {{
    background: transparent !important;
    border-radius: 100px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: var(--text-muted) !important;
    padding: 0.5rem 1.4rem !important;
    border: none !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
    color: var(--accent) !important;
    background: var(--bg-step) !important;
}}
[data-testid="stTabs"] button[aria-selected="true"] {{
    background: var(--accent) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 12px var(--shadow-accent) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ display: none !important; }}

/* ── Step & Section headers ─────────────────────────────────────────── */
.step-header {{
    font-size: 0.95rem;
    font-weight: 700;
    margin: 2rem 0 1rem;
    padding: 0.6rem 1.1rem;
    background: var(--bg-step);
    border-left: 4px solid var(--accent);
    border-radius: 4px 12px 12px 4px;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}}
.section-title {{
    font-size: 0.95rem;
    font-weight: 700;
    margin: 1.8rem 0 1rem;
    padding: 0.6rem 1.1rem;
    background: var(--bg-section);
    border-left: 4px solid #16a34a;
    border-radius: 4px 12px 12px 4px;
    color: var(--text-primary);
}}

/* ── Expanders ─────────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: var(--bg-expander) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 14px !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 1px 3px var(--shadow-card) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}}
[data-testid="stExpander"]:hover {{
    border-color: var(--border-main) !important;
    box-shadow: 0 10px 15px -3px var(--shadow-card) !important;
    transform: translateY(-1px);
}}
[data-testid="stExpander"] summary {{
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    padding: 0.85rem 1.2rem !important;
    background: var(--bg-card) !important; /* Explicitly set background */
    border-radius: 14px 14px 0 0 !important;
}}
[data-testid="stExpander"] summary:hover {{
    background: var(--bg-step) !important;
}}

/* ── All text in expanders ──────────────────────────────────────────── */
[data-testid="stExpander"] p,
[data-testid="stExpander"] span,
[data-testid="stExpander"] div,
[data-testid="stExpander"] label {{
    color: var(--text-primary) !important;
}}

/* ── Forms ─────────────────────────────────────────────────────────── */
[data-testid="stForm"] {{
    background: var(--bg-form) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 4px 20px -2px var(--shadow-card) !important;
}}

/* ── Inputs ────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: var(--bg-input) !important;
    border: 1px solid var(--border-input) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 0.5rem 0.75rem !important;
    transition: all 0.2s ease;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    background: var(--bg-input) !important;
    border: 1px solid var(--border-input) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}}
/* Selectbox dropdown items */
[data-baseweb="popover"] [data-baseweb="menu"] {{
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-main) !important;
}}
[data-baseweb="popover"] [data-baseweb="menu"] [role="option"]:hover {{
    background: var(--bg-step) !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] div[data-testid="stMarkdownContainer"] p {{
    color: var(--text-primary) !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15) !important;
    background: var(--bg-card) !important;
}}

/* ── Labels / Markdown text ─────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
label, .stLabel {{
    color: var(--text-primary) !important;
}}

/* ── Streamlit Info/Success/Warning boxes ─────────────────────────── */
[data-testid="stNotification"] {{
    background: var(--bg-input) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-main) !important;
}}
[data-testid="stNotification"] p {{
    color: var(--text-primary) !important;
}}

/* ── Code Blocks / st.code ─────────────────────────────────────────── */
[data-testid="stCodeBlock"], .stCodeBlock, code, pre {{
    background: var(--bg-json) !important;
    border: 1px solid var(--border-main) !important;
    color: var(--text-primary) !important;
}}
div[data-testid="stCodeBlock"] pre {{
    background: var(--bg-json) !important;
}}
div[data-testid="stCodeBlock"] button {{
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
}}

/* ── Buttons ───────────────────────────────────────────────────────── */
button[kind="primary"] {{
    background: var(--accent) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    color: #ffffff !important;
    box-shadow: 0 4px 10px var(--shadow-accent) !important;
    transition: all 0.2s ease !important;
}}
button[kind="primary"]:hover {{
    background: var(--accent-hover) !important;
    transform: translateY(-1px);
}}
button[kind="secondary"] {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 10px !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}}
button[kind="secondary"]:hover {{
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}}

/* ── Metrics ───────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: var(--bg-metric) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 14px !important;
    padding: 1rem !important;
    box-shadow: 0 1px 2px var(--shadow-card) !important;
}}
[data-testid="stMetricLabel"] {{ color: var(--text-muted) !important; font-size: 0.8rem !important; font-weight: 500 !important; }}
[data-testid="stMetricValue"] {{ color: var(--accent) !important; font-weight: 800 !important; }}

/* ── JSON viewer ───────────────────────────────────────────────────── */
[data-testid="stJson"] {{
    background: var(--bg-json) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}}

/* ── File uploader ─────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    border: 2px dashed var(--accent) !important;
    border-radius: 16px !important;
    background: var(--bg-uploader) !important;
    padding: 1.5rem !important;
}}

/* ── Scrollbar ─────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-scrollbar); }}
::-webkit-scrollbar-thumb {{ background: var(--bg-thumb); border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--bg-thumb-h); }}

/* ── Cards ─────────────────────────────────────────────────────────── */
.stcard {{
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 1.25rem;
    transition: all 0.2s ease;
    cursor: pointer;
    box-shadow: 0 1px 2px var(--shadow-card);
    color: var(--text-primary);
}}
.stcard:hover {{
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px var(--shadow-card);
}}

.thumbnail-container {{
    width: 100%;
    aspect-ratio: 16/9;
    background: var(--bg-thumbnail);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 0.75rem;
    border: 1px solid var(--border-card);
}}
.thumbnail-container img {{ width: 100%; height: 100%; object-fit: cover; }}

/* ── STAC Metadata Table ────────────────────────────────────────────── */
.stac-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.88rem;
}}
.stac-table tr {{ border-bottom: 1px solid var(--border-card); }}
.stac-table td {{ padding: 0.6rem 0.5rem; color: var(--text-muted); }}
.stac-table td:first-child {{ font-weight: 600; color: var(--text-primary); width: 35%; }}

/* ── Map Container ─────────────────────────────────────────────────── */
.map-container {{
    border: 1px solid var(--border-main);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px var(--shadow-card);
    margin-bottom: 1.5rem;
}}

/* ── Status Cards ─────────────────────────────────────────────────── */
.status-card {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 12px;
    padding: 0.8rem 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
    box-shadow: 0 1px 3px var(--shadow-card);
}}

.status-name {{
    font-weight: 700;
    font-size: 0.85rem;
    color: var(--text-primary) !important;
    margin-bottom: 1px;
}}

.status-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}}

@keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.6; transform: scale(0.95); }}
}}

/* ── Gradient Text ────────────────────────────────────────────────── */
.gradient-text {{
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: inline-block;
}}

/* ── Spacing overrides ────────────────────────────────────────────────── */
.stTabs {{ margin-top: 1rem; }}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{ color: var(--text-head) !important; }}
</style>
""", unsafe_allow_html=True)
