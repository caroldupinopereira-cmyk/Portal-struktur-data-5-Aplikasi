"""Load small local stylesheets; no JavaScript or external UI framework."""
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[1] / "assets"


@st.cache_data(show_spinner=False)
def _stylesheet(name: str, modified: int) -> str:
    """The modification time refreshes the cache after a stylesheet edit."""
    return (ASSETS / name).read_text(encoding="utf-8")


def apply_theme():
    styles = []
    for name in ("kumo-tokens.css", "portal.css", "app.css"):
        path = ASSETS / name
        styles.append(_stylesheet(name, path.stat().st_mtime_ns))
    css = "\n".join(styles)
    st.html(f"<style>{css}</style>")
