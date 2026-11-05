"""Shared page chrome so every application presents the same structure."""
from html import escape

import streamlit as st

from portal.icons import app_icon


def app_header(slug, judul, konsep, deskripsi=None, *, aksi=None):
    """Main application header: icon, title, concept badge, and optional action."""
    meta = f'<span class="app-page-badge">{escape(konsep)}</span>'
    if deskripsi:
        meta += f'<span class="app-page-desc">{escape(deskripsi)}</span>'
    blok = (
        '<section class="app-page-header">'
        f'<span class="app-page-icon" aria-hidden="true">{app_icon(slug)}</span>'
        '<div class="app-page-copy">'
        f'<h1 class="app-page-title">{escape(judul)}</h1>'
        f'<div class="app-page-meta">{meta}</div>'
        '</div></section>'
    )
    if aksi is None:
        st.html(blok)
        return
    kiri, kanan = st.columns([5, 1], vertical_alignment="center")
    kiri.html(blok)
    with kanan:
        aksi()


def page_header(judul, deskripsi=None, *, ikon=None):
    """Subpage heading used consistently across applications."""
    label = f":material/{ikon}: {judul}" if ikon else judul
    st.subheader(label)
    if deskripsi:
        st.caption(deskripsi)


def metric_row(items):
    """Render a horizontal row of bordered metrics."""
    with st.container(horizontal=True):
        for label, nilai in items:
            st.metric(label, nilai, border=True)


def card():
    """Bordered container for one logical section."""
    return st.container(border=True)


def empty_state(judul, petunjuk=None, *, ikon="inbox"):
    teks = f"**{judul}**"
    if petunjuk:
        teks += f" — {petunjuk}"
    st.info(teks, icon=f":material/{ikon}:")
