import os
import shutil
import sqlite3
import tempfile
import webbrowser
import streamlit as st

from portal.theme import apply_theme
from portal.ui import app_header, empty_state, page_header


# ==========================================
# 1. STRUKTUR DATA STACK (LIFO)
# ==========================================
class Stack:
    def __init__(self):
        if "stack_items" not in st.session_state:
            st.session_state.stack_items = []

    def push(self, item):
        st.session_state.stack_items.append(item)

    def pop(self):
        if not self.is_empty():
            return st.session_state.stack_items.pop()
        return None

    def peek(self):
        if not self.is_empty():
            return st.session_state.stack_items[-1]
        return None

    def is_empty(self):
        return len(st.session_state.stack_items) == 0

    def size(self):
        return len(st.session_state.stack_items)

    def clear(self):
        st.session_state.stack_items.clear()

    def to_list(self):
        return list(st.session_state.stack_items)


# ==========================================
# 2. HELPER MEMBACA RIWAYAT CHROME
# ==========================================
CONTOH_RIWAYAT = [
    ("https://www.google.com", "Google"),
    ("https://www.youtube.com", "YouTube"),
    ("https://github.com", "GitHub"),
    ("https://www.wikipedia.org", "Wikipedia"),
    ("https://www.streamlit.io", "Streamlit"),
]


def get_local_history_path():
    return os.path.expanduser(
        r"~\AppData\Local\Google\Chrome\User Data\Default\History"
    )


def _query_history(db_path, limit):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        query = """
            SELECT url, title
            FROM urls
            ORDER BY last_visit_time DESC
            LIMIT ?
        """
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [(url, title if title else url) for url, title in rows]


def get_chrome_history(limit=20):
    history_path = get_local_history_path()

    if not os.path.exists(history_path):
        return []

    temp_history = os.path.join(tempfile.gettempdir(), "Chrome_History_Streamlit")
    try:
        shutil.copyfile(history_path, temp_history)
        return _query_history(temp_history, limit)
    except (OSError, sqlite3.Error):
        return []
    finally:
        if os.path.exists(temp_history):
            os.remove(temp_history)


def read_uploaded_history(uploaded_file, limit=20):
    fd, temp_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    try:
        with open(temp_path, "wb") as file:
            file.write(uploaded_file.getbuffer())
        return _query_history(temp_path, limit)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def load_history(stack, history):
    stack.clear()
    for url, title in reversed(history):
        stack.push((url, title))


# ==========================================
# 3. TAMPILAN STREAMLIT WEB APP
# ==========================================
st.set_page_config(
    page_title="Simulasi Browser Stack", page_icon=":material/layers:", layout="wide"
)
apply_theme()

stack = Stack()

app_header(
    "browser_stack",
    "Simulasi Browser Back Button dengan Stack (LIFO)",
    "Stack · LIFO",
    "Aplikasi web interaktif untuk memvisualisasikan struktur data Stack pada riwayat penelusuran web.",
)

# --- TOP BAR: Navigasi & Input ---
col_back, col_input, col_btn = st.columns([1, 4, 1])

with col_back:
    if st.button(
        "Back (Pop)", icon=":material/arrow_back:", width="stretch", disabled=stack.size() <= 1
    ):
        popped_url, popped_title = stack.pop()
        st.toast(f"POP: Keluar dari '{popped_title}'", icon=":material/arrow_back:")
        st.rerun()

with col_input:
    user_url = st.text_input(
        "URL Manual",
        placeholder="Ketik URL (misal: google.com)...",
        label_visibility="collapsed",
    )

with col_btn:
    if st.button("Push URL", icon=":material/add_link:", width="stretch"):
        if user_url.strip():
            full_url = (
                user_url
                if user_url.startswith("http")
                else "https://" + user_url
            )
            stack.push((full_url, user_url))
            st.toast(f"PUSH: {user_url}", icon=":material/arrow_forward:")
            st.rerun()

st.divider()

# --- HALAMAN AKTIF DISPLAY ---
top_item = stack.peek()
if top_item:
    st.info(f"**Halaman Aktif Saat Ini (Top of Stack):** {top_item[1]}", icon=":material/language:")
else:
    st.warning("**Halaman Aktif Saat Ini:** (Stack Kosong)", icon=":material/language:")

# --- BODY AREA (2 KOLOM) ---
col_left, col_right = st.columns(2)

with col_left:
    page_header("Isi Tumpukan Stack (LIFO)", ikon="layers")

    if os.path.exists(get_local_history_path()):
        if st.button("Muat Riwayat Chrome ke Stack", icon=":material/history:", width="stretch"):
            history = get_chrome_history(limit=15)
            if history:
                load_history(stack, history)
                st.success("Berhasil memuat riwayat Chrome ke Stack!")
                st.rerun()
            else:
                st.error("Gagal membaca riwayat Chrome.")
    else:
        st.caption(
            "Riwayat Chrome otomatis hanya tersedia saat aplikasi dijalankan "
            "di komputer sendiri. Di cloud, unggah file History atau pakai data contoh."
        )

    uploaded = st.file_uploader(
        "Unggah file History Chrome",
        help=(
            "Salin file History dari folder profil Chrome, lalu unggah di sini. "
            "Lokasi Windows: %LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\History"
        ),
    )
    if uploaded is not None:
        if st.button("Muat dari file yang diunggah", icon=":material/upload_file:", width="stretch"):
            try:
                history = read_uploaded_history(uploaded, limit=15)
            except (OSError, sqlite3.Error):
                history = []
            if history:
                load_history(stack, history)
                st.success("Berhasil memuat riwayat dari file yang diunggah!")
                st.rerun()
            else:
                st.error("File tidak valid atau tidak berisi riwayat Chrome.")

    if st.button("Muat data contoh", icon=":material/science:", width="stretch"):
        load_history(stack, CONTOH_RIWAYAT)
        st.success("Data contoh berhasil dimuat ke Stack!")
        st.rerun()

    items = stack.to_list()
    if items:
        for idx, (url, title) in enumerate(reversed(items)):
            is_top = idx == 0
            prefix = ":material/arrow_upward: " if is_top else ":material/link: "

            col_item, col_open = st.columns([4, 1])
            with col_item:
                if is_top:
                    st.markdown(f"**{prefix}[TOP] {title}**")
                else:
                    st.markdown(f"{prefix}{title}")

            with col_open:
                st.link_button("Buka", icon=":material/open_in_new:", url=url, width="stretch")
    else:
        empty_state("Stack masih kosong.", "Muat riwayat atau push URL baru.", ikon="layers")

    st.caption(f"Ukuran Stack saat ini: **{stack.size()}**")

with col_right:
    page_header("Aksi & Kontrol", ikon="tune")
    if st.button("Reset Stack", icon=":material/delete:", type="primary", width="stretch"):
        stack.clear()
        st.toast("Stack berhasil dikosongkan!")
        st.rerun()
