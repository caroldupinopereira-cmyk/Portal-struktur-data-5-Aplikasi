import os
import shutil
import sqlite3
import tempfile
import webbrowser
import streamlit as st


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
def get_chrome_history(limit=20):
    history_path = os.path.expanduser(
        r"~\AppData\Local\Google\Chrome\User Data\Default\History"
    )

    if not os.path.exists(history_path):
        return []

    temp_dir = tempfile.gettempdir()
    temp_history = os.path.join(temp_dir, "Chrome_History_Streamlit")
    shutil.copyfile(history_path, temp_history)

    history_data = []
    try:
        conn = sqlite3.connect(temp_history)
        cursor = conn.cursor()
        query = """
            SELECT url, title 
            FROM urls 
            ORDER BY last_visit_time DESC 
            LIMIT ?
        """
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        for url, title in rows:
            display_title = title if title else url
            history_data.append((url, display_title))

        conn.close()
    finally:
        if os.path.exists(temp_history):
            os.remove(temp_history)

    return history_data


# ==========================================
# 3. TAMPILAN STREAMLIT WEB APP
# ==========================================
st.set_page_config(
    page_title="Simulasi Browser Stack", page_icon=":material/layers:", layout="wide"
)

stack = Stack()

st.title(":material/layers: Simulasi Browser Back Button dengan Stack (LIFO)")
st.caption(
    "Aplikasi web interaktif untuk memvisualisasikan struktur data Stack pada riwayat penelusuran web."
)

# --- TOP BAR: Navigasi & Input ---
col_back, col_input, col_btn = st.columns([1, 4, 1])

with col_back:
    if st.button(
        "◀ Back (Pop)", width="stretch", disabled=stack.size() <= 1
    ):
        popped_url, popped_title = stack.pop()
        st.toast(f"POP: Keluar dari '{popped_title}'", icon="⬅️")
        st.rerun()

with col_input:
    user_url = st.text_input(
        "URL Manual",
        placeholder="Ketik URL (misal: google.com)...",
        label_visibility="collapsed",
    )

with col_btn:
    if st.button("Push URL", width="stretch"):
        if user_url.strip():
            full_url = (
                user_url
                if user_url.startswith("http")
                else "https://" + user_url
            )
            stack.push((full_url, user_url))
            st.toast(f"PUSH: {user_url}", icon="➡️")
            st.rerun()

st.divider()

# --- HALAMAN AKTIF DISPLAY ---
top_item = stack.peek()
if top_item:
    st.info(f"🌐 **Halaman Aktif Saat Ini (Top of Stack):** {top_item[1]}")
else:
    st.warning("🌐 **Halaman Aktif Saat Ini:** (Stack Kosong)")

# --- BODY AREA (2 KOLOM) ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader(":material/layers: Isi Tumpukan Stack (LIFO)")

    if st.button("⚡ Muat Riwayat Chrome ke Stack", width="stretch"):
        history = get_chrome_history(limit=15)
        if history:
            stack.clear()
            for url, title in reversed(history):
                stack.push((url, title))
            st.success("Berhasil memuat riwayat Chrome ke Stack!")
            st.rerun()
        else:
            st.error("Gagal membaca riwayat Chrome.")

    items = stack.to_list()
    if items:
        for idx, (url, title) in enumerate(reversed(items)):
            is_top = idx == 0
            prefix = "🔥 [TOP] " if is_top else "📍 "

            col_item, col_open = st.columns([4, 1])
            with col_item:
                if is_top:
                    st.markdown(f"**{prefix}{title}**")
                else:
                    st.write(f"{prefix}{title}")

            with col_open:
                st.link_button("Buka 🔗", url=url, width="stretch")
    else:
        st.write("*Stack masih kosong.*")

    st.caption(f"Ukuran Stack saat ini: **{stack.size()}**")

with col_right:
    st.subheader(":material/tune: Aksi & Kontrol")
    if st.button("🗑️ Reset Stack", type="primary", width="stretch"):
        stack.clear()
        st.toast("Stack berhasil dikosongkan!")
        st.rerun()
