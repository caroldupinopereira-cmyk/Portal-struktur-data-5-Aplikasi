"""Tampilan beranda portal."""
import streamlit as st
from html import escape
from pathlib import Path, PurePosixPath
from string import Template

from portal.catalog import APLIKASI
from portal.icons import app_icon

TEMPLATES = Path(__file__).resolve().parent / "templates"


@st.cache_data(show_spinner=False)
def _template(name: str, modified: int) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def render_html(name: str, **values) -> str:
    path = TEMPLATES / name
    return Template(_template(name, path.stat().st_mtime_ns)).substitute(values)


def beranda():
    with st.container(key="portal-home"):
        jumlah = f"{len(APLIKASI):02d}"
        st.html(render_html("header.html", jumlah=jumlah, brand_icon=app_icon("portal")))
        for awal in range(0, len(APLIKASI), 3):
            kolom = st.columns(3, gap="medium")
            for nomor, (tempat, (file, nama, _, konsep, deskripsi)) in enumerate(zip(kolom, APLIKASI[awal:awal + 3]), awal + 1):
                slug = PurePosixPath(file).stem
                with tempat.container(key=f"app-card-{slug}"):
                    st.html(render_html("card.html", slug=escape(slug), konsep=escape(konsep),
                                        nomor=f"{nomor:02d}", jumlah=jumlah, nama=escape(nama),
                                        deskripsi=escape(deskripsi), ikon=app_icon(slug)))
                    st.page_link(file, label=f"Buka {nama}", icon=":material/arrow_forward:", width="stretch")
        st.html(render_html("footer.html"))

