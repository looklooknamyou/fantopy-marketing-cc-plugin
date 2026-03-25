"""Shared theme injection for all dashboard pages."""

import streamlit as st

TURQUOISE = "#00D4B2"
DARK_BG   = "#0A0A0F"
CARD_BG   = "#111118"
TEXT      = "#E8E8F0"
MUTED     = "#6B7280"

CSS = """
<style>
/* ── Base ─────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0A0A0F;
    color: #E8E8F0;
}
[data-testid="stSidebar"] {
    background-color: #08080D;
    border-right: 1px solid #1E1E2E;
}
[data-testid="stSidebar"] * {
    color: #E8E8F0 !important;
}

/* ── Headers ──────────────────────────────────────────────────────── */
h1, h2, h3, h4 {
    color: #00D4B2 !important;
    font-weight: 700 !important;
}
.stCaption, .stMarkdown p small {
    color: #6B7280 !important;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #00D4B2 0%, #0099AA 100%);
    color: #000 !important;
    border: none;
    font-weight: 700;
    border-radius: 6px;
    transition: opacity 0.2s;
}
.stButton > button:hover {
    opacity: 0.85;
    color: #000 !important;
}
.stButton > button[kind="secondary"] {
    background: #1E1E2E;
    color: #E8E8F0 !important;
    border: 1px solid #2E2E3E;
}

/* ── Inputs / Selects ─────────────────────────────────────────────── */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    background-color: #111118 !important;
    border: 1px solid #2E2E3E !important;
    color: #E8E8F0 !important;
    border-radius: 6px !important;
}
.stSelectbox svg { color: #00D4B2 !important; }

/* ── Metrics ──────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #111118;
    border: 1px solid #1E2E2A;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="stMetricValue"] {
    color: #00D4B2 !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #9CA3AF !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Dataframes / Tables ──────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #1E2E2A;
    border-radius: 8px;
    overflow: hidden;
}
.dvn-scroller { background-color: #111118 !important; }

/* ── Expanders ────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background-color: #111118 !important;
    border: 1px solid #1E1E2E !important;
    border-radius: 6px !important;
    color: #00D4B2 !important;
}

/* ── Alerts ───────────────────────────────────────────────────────── */
[data-testid="stAlert"][data-baseweb="notification"][kind="info"] {
    background: #0A1F1C !important;
    border-left: 4px solid #00D4B2 !important;
}
[data-testid="stAlert"][data-baseweb="notification"][kind="success"] {
    background: #0A1F12 !important;
    border-left: 4px solid #00CC66 !important;
}
[data-testid="stAlert"][data-baseweb="notification"][kind="error"] {
    background: #1F0A0A !important;
    border-left: 4px solid #FF4444 !important;
}

/* ── Dividers ─────────────────────────────────────────────────────── */
hr { border-color: #1E1E2E !important; }

/* ── Code blocks ──────────────────────────────────────────────────── */
.stCodeBlock, pre {
    background-color: #08080D !important;
    border: 1px solid #1E2E2A !important;
    border-radius: 6px !important;
    color: #00D4B2 !important;
}
code { color: #00D4B2 !important; }

/* ── Spinner ──────────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: #00D4B2 !important; }

/* ── Sidebar nav links ────────────────────────────────────────────── */
[data-testid="stSidebarNavLink"] {
    border-radius: 6px;
    transition: background 0.15s;
}
[data-testid="stSidebarNavLink"]:hover,
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: #0A2E28 !important;
    color: #00D4B2 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] * {
    color: #00D4B2 !important;
}

/* ── Progress bar ─────────────────────────────────────────────────── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #00D4B2, #0099AA);
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #111118;
    border-bottom: 2px solid #1E1E2E;
}
.stTabs [data-baseweb="tab"] {
    color: #6B7280 !important;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    color: #00D4B2 !important;
    border-bottom: 2px solid #00D4B2 !important;
}
</style>
"""


def inject():
    """Inject the dark turquoise theme CSS into the current Streamlit page."""
    st.markdown(CSS, unsafe_allow_html=True)
