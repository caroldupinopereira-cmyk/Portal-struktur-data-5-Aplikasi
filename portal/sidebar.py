"""Shared sidebar presentation; application state and menu values stay unchanged."""
from html import escape
from pathlib import Path

import streamlit as st

from portal.icons import app_icon

SOURCE_VERSION = Path(__file__).stat().st_mtime_ns


def sidebar_header(slug, nama, konsep, deskripsi):
    st.html(Path(__file__).resolve().parents[1] / "assets" / "sidebar.css")
    st.html(
        f'<header class="app-sidebar-brand">'
        f'<span class="app-sidebar-icon" aria-hidden="true">{app_icon(slug)}</span>'
        f'<div><h2>{escape(nama)}</h2><span>{escape(konsep)}</span></div></header>'
    )


def _select_menu(key, label):
    st.session_state[key] = label


def sidebar_menu(options, *, key, icons):
    # Store the choice independently of widgets, including after a page switch.
    current = st.session_state.get(key, options[0])
    st.session_state[key] = current if current in options else options[0]
    with st.container(key=f"sidebar-navigation-{key}"):
        for index, label in enumerate(options):
            active = st.session_state[key] == label
            state = "active" if active else "item"
            with st.container(key=f"sidebar-nav-{state}-{key}-{index}"):
                st.button(label, icon=f":material/{icons[label]}:",
                          key=f"nav_{key}_{index}", width="stretch",
                          type="primary" if active else "tertiary",
                          on_click=_select_menu, args=(key, label))
    return st.session_state[key]


def sidebar_refresh(key):
    with st.container(key="sidebar-refresh"):
        st.button("Perbarui data", icon=":material/refresh:", width="stretch", key=key)
