"""Portal lima aplikasi. Jalankan: python -m streamlit run app.py"""
import streamlit as st
from pathlib import Path

from portal.catalog import APLIKASI
from portal.home import beranda
from portal.theme import apply_theme
from portal.runtime import refresh_sidebar_module
from portal.appearance import theme_switcher

st.set_page_config(page_title="Portal Struktur Data", page_icon=":material/home:", layout="wide")
apply_theme()
refresh_sidebar_module()


portal = st.Page(beranda, title="Beranda", icon=":material/home:", default=True)
halaman = [st.Page(file, title=nama, icon=ikon) for file, nama, ikon, _, _ in APLIKASI]
navigasi = st.navigation({"": [portal], "Aplikasi": halaman}, position="top")
aplikasi_dengan_sidebar = {"KasirKu", "AntreanKu", "HotelKu"}

if navigasi.title not in aplikasi_dengan_sidebar:
    st.html(Path(__file__).resolve().parent / "assets" / "no-sidebar.css")

theme_switcher()

if navigasi != portal:
    with st.container(key="portal-return"):
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
            st.page_link(portal, label="Kembali ke portal", icon=":material/arrow_back:")
            st.caption(f"Portal Struktur Data / {navigasi.title}")

navigasi.run()

if navigasi.title in aplikasi_dengan_sidebar:
    with st.sidebar:
        with st.container(key="sidebar-portal-link"):
            st.page_link(portal, label="Kembali ke portal", icon=":material/arrow_back:")
