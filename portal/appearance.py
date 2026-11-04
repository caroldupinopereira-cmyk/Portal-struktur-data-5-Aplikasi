"""Visible shortcuts to Streamlit's native light and dark theme controls."""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def theme_switcher():
    html = (ROOT / "portal/templates/theme-switcher.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/theme-switcher.js").read_text(encoding="utf-8")
    # Only trusted local source is executed; application/user data is not inserted.
    st.html(html + "<script>" + js + "</script>", unsafe_allow_javascript=True)
