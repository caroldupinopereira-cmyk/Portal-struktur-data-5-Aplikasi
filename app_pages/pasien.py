"""
Program Daftar Tunggu Pasien Klinik (Streamlit)
Mata Kuliah : Struktur Data
Struktur data: Single Linked List

Cara menjalankan:
    pip install streamlit pandas openpyxl
    streamlit run app_pages/pasien.py
"""
import csv
import html
import io
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
except ImportError:          # openpyxl belum terpasang
    openpyxl = None

st.set_page_config(page_title="Daftar Tunggu Pasien", page_icon=":material/medical_services:", layout="wide")


# =====================================================================
# 1. NODE
# =====================================================================
class Node:
    """Satu node: data pasien + pointer 'next'."""

    def __init__(self, no_antrian, nama, keluhan):
        self.no_antrian = no_antrian
        self.nama = nama
        self.keluhan = keluhan
        self.next = None


# =====================================================================
# 2. CLASS DaftarTunggu (SINGLE LINKED LIST)
# =====================================================================
class DaftarTunggu:
    """Single Linked List daftar tunggu pasien."""

    def __init__(self):
        self.head = None
        self.counter = 0

    def kosong(self):
        return self.head is None

    def hitung(self):
        jumlah = 0
        bantu = self.head
        while bantu is not None:
            jumlah += 1
            bantu = bantu.next
        return jumlah

    def semua_node(self):
        """Traversal: mengembalikan semua node berurutan dari head."""
        hasil = []
        bantu = self.head
        while bantu is not None:
            hasil.append(bantu)
            bantu = bantu.next
        return hasil

    def _node_di(self, posisi):
        bantu = self.head
        for _ in range(posisi - 1):
            bantu = bantu.next
        return bantu

    def _lepas(self, posisi):
        if posisi == 1:
            node = self.head
            self.head = node.next
        else:
            sebelum = self._node_di(posisi - 1)
            node = sebelum.next
            sebelum.next = node.next
        node.next = None
        return node

    def _sisip(self, posisi, node):
        if posisi == 1:
            node.next = self.head
            self.head = node
        else:
            sebelum = self._node_di(posisi - 1)
            node.next = sebelum.next
            sebelum.next = node

    def tambah(self, posisi, nama, keluhan):
        self.counter += 1
        baru = Node(self.counter, nama, keluhan)
        self._sisip(posisi, baru)
        return baru

    def hapus(self, posisi):
        return self._lepas(posisi)

    def panggil(self):
        return self._lepas(1)

    def pindahkan(self, dari, ke):
        node = self._lepas(dari)
        self._sisip(ke, node)
        return node

    def ubah_keluhan(self, posisi, keluhan_baru):
        node = self._node_di(posisi)
        node.keluhan = keluhan_baru
        return node

    def ke_baris(self):
        """Traversal: isi list sebagai baris (urutan, tiket, nama, keluhan)."""
        return [(i, n.no_antrian, n.nama, n.keluhan)
                for i, n in enumerate(self.semua_node(), start=1)]

    def muat(self, data):
        """Mengganti isi list dengan data [(tiket, nama, keluhan), ...]."""
        self.head = None
        ekor = None
        self.counter = 0
        for tiket, nama, keluhan in data:
            node = Node(tiket, nama, keluhan)
            if self.head is None:
                self.head = node          # node pertama menjadi head
            else:
                ekor.next = node          # sambungkan ke node terakhir
            ekor = node
            self.counter = max(self.counter, tiket)

    def cari(self, nama):
        """Mengembalikan daftar urutan pasien yang namanya cocok."""
        hasil = []
        bantu = self.head
        urutan = 1
        while bantu is not None:
            if nama.lower() in bantu.nama.lower():
                hasil.append(urutan)
            bantu = bantu.next
            urutan += 1
        return hasil


# =====================================================================
# 3. PENYIMPANAN KE EXCEL / CSV (dan konversi format file luar)
# =====================================================================
JUDUL_KOLOM = ("Urutan", "No. Tiket", "Nama Pasien", "Keluhan")


def simpan_xlsx(path, baris):
    """Menyimpan ke file Excel (.xlsx), lengkap dengan header berwarna."""
    if openpyxl is None:
        raise RuntimeError("Library openpyxl belum terpasang.\n"
                           "Jalankan:  pip install openpyxl\n"
                           "atau simpan sebagai CSV.")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daftar Tunggu"
    ws.append(JUDUL_KOLOM)
    for b in baris:
        ws.append(list(b))
    for sel in ws[1]:
        sel.font = Font(bold=True, color="FFFFFF")
        sel.fill = PatternFill("solid", fgColor="1F4E79")
        sel.alignment = Alignment(horizontal="center")
    for huruf, lebar in zip("ABCD", (9, 12, 28, 36)):
        ws.column_dimensions[huruf].width = lebar
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def simpan_csv(path, baris):
    """Menyimpan ke CSV. Pemisah ';' dan BOM UTF-8 agar langsung rapi di Excel."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        f.write("sep=;\r\n")             # memberi tahu Excel pemisah kolomnya
        w = csv.writer(f, delimiter=";")
        w.writerow(JUDUL_KOLOM)
        w.writerows(baris)


def baca_file(path):
    """Membaca file .xlsx / .csv hasil simpanan. Mengembalikan [(tiket, nama, keluhan)]."""
    if path.lower().endswith(".xlsx"):
        if openpyxl is None:
            raise RuntimeError("Library openpyxl belum terpasang.\n"
                               "Jalankan:  pip install openpyxl")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        baris = [list(r) for r in wb.active.iter_rows(values_only=True)]
        wb.close()
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            teks = f.read()
        if teks.lower().startswith("sep="):
            teks = teks.split("\n", 1)[1] if "\n" in teks else ""
        awal = teks.split("\n", 1)[0]
        pemisah = ";" if awal.count(";") >= awal.count(",") else ","
        baris = list(csv.reader(io.StringIO(teks), delimiter=pemisah))

    if not baris or len(baris[0]) < 4 or "nama" not in str(baris[0][2]).lower():
        raise ValueError("Format file tidak dikenali.\n"
                         "Gunakan file hasil simpanan program ini.")
    data = []
    for r in baris[1:]:
        if len(r) < 4 or r[2] is None or str(r[2]).strip() == "":
            continue
        try:
            tiket = int(float(r[1]))
        except (TypeError, ValueError):
            raise ValueError(f"No. Tiket tidak valid pada baris: {r}")
        data.append((tiket, str(r[2]).strip(), str(r[3] or "").strip()))
    return data


KATA_NAMA = ("nama", "name", "pasien", "patient")
KATA_KELUHAN = ("keluhan", "komplain", "complaint", "gejala", "symptom",
                "diagnosa", "diagnosis", "penyakit", "sakit", "keterangan")


def baca_fleksibel(path):
    """Membaca file Excel/CSV berformat apa pun, lalu mengubahnya ke [(tiket, nama, keluhan)].
    Kolom dikenali dari judulnya; urutan dan nomor tiket dibuat otomatis."""
    # 1. ambil semua baris mentah, ubah menjadi teks
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig", newline="") as f:
            teks = f.read()
        try:
            dialek = csv.Sniffer().sniff(teks[:2000], delimiters=",;\t|")
        except csv.Error:
            dialek = csv.excel
        mentah = list(csv.reader(io.StringIO(teks), dialek))
    else:
        if openpyxl is None:
            raise RuntimeError("Library openpyxl belum terpasang.\n"
                               "Jalankan:  pip install openpyxl")
        wb = openpyxl.load_workbook(path, data_only=True)
        mentah = []
        for ws in wb.worksheets:              # pakai sheet pertama yang ada isinya
            mentah = [list(r) for r in ws.iter_rows(values_only=True)]
            if any(any(c is not None and str(c).strip() for c in r) for r in mentah):
                break
    baris = [["" if c is None else str(c).strip() for c in r] for r in mentah]
    baris = [r for r in baris if any(r)]       # buang baris kosong
    if not baris:
        raise ValueError("File kosong.")

    # 2. cari baris judul (10 baris pertama) lalu tentukan kolom nama dan keluhan
    i_nama = i_kel = awal = None
    for n, r in enumerate(baris[:10]):
        kecil = [c.lower() for c in r]
        cocok_nama = [j for j, c in enumerate(kecil) if any(k in c for k in KATA_NAMA)]
        if cocok_nama:
            i_nama = cocok_nama[0]
            cocok_kel = [j for j, c in enumerate(kecil)
                         if j != i_nama and any(k in c for k in KATA_KELUHAN)]
            i_kel = cocok_kel[0] if cocok_kel else None
            awal = n + 1
            break

    # 3. tidak ada judul: tebak dari isi, kolom angka (No/Urutan) dilewati
    if i_nama is None:
        lebar = max(len(r) for r in baris)
        kolom_teks = [j for j in range(lebar)
                      if any(j < len(r) and r[j] and not r[j].replace(".", "").isdigit()
                             for r in baris)]
        if not kolom_teks:
            raise ValueError("Tidak ditemukan kolom nama.")
        i_nama = kolom_teks[0]
        i_kel = kolom_teks[1] if len(kolom_teks) > 1 else None
        awal = 0
    elif i_kel is None:                        # judul nama ada, keluhan tidak: ambil kolom berikutnya
        for j in range(len(baris[awal - 1])):
            if j != i_nama and baris[awal - 1][j]:
                i_kel = j
                break

    # 4. susun hasil dalam format program: nomor tiket dibuat otomatis (1, 2, 3, ...)
    data = []
    for r in baris[awal:]:
        nama = r[i_nama] if i_nama < len(r) else ""
        kel = r[i_kel] if i_kel is not None and i_kel < len(r) else ""
        if nama:
            data.append((len(data) + 1, nama, kel or "-"))
    if not data:
        raise ValueError("Tidak ada data pasien yang terbaca.")
    return data


# =====================================================================
# 4. TAMPILAN STREAMLIT
# =====================================================================
# Streamlit menjalankan ulang seluruh skrip setiap ada interaksi, jadi objek
# Single Linked List disimpan di st.session_state agar datanya tidak hilang.
if "sll" not in st.session_state:
    st.session_state.sll = DaftarTunggu()
    st.session_state.status = ("info", "Selamat datang. Tambahkan pasien atau buka file Excel/CSV.")


def daftar():
    return st.session_state.sll


def set_status(jenis, teks):
    """jenis: info / success / warning / error"""
    st.session_state.status = (jenis, teks)


def ke_bytes(fungsi_simpan, ekstensi, baris):
    """Menjalankan simpan_xlsx / simpan_csv ke file sementara, lalu mengembalikan isinya (bytes)."""
    fd, path = tempfile.mkstemp(suffix=ekstensi)
    os.close(fd)
    try:
        fungsi_simpan(path, baris)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.remove(path)


# ---------- aksi tombol (dijalankan sebelum halaman digambar ulang) ----------
def aksi_tambah():
    nama = st.session_state.f_nama.strip()
    keluhan = st.session_state.f_keluhan.strip()
    if not nama or not keluhan:
        set_status("warning", "Nama dan keluhan harus diisi.")
        return
    posisi = st.session_state.f_posisi
    baru = daftar().tambah(posisi, nama, keluhan)
    st.session_state.f_nama = ""
    st.session_state.f_keluhan = ""
    st.session_state.f_posisi = daftar().hitung() + 1
    st.session_state.pilih = posisi
    set_status("success", f"{nama} (Tiket {baru.no_antrian}) ditambahkan pada urutan ke-{posisi}.")


def aksi_hapus():
    posisi = st.session_state.get("pilih")
    if daftar().kosong() or posisi is None:
        return
    node = daftar().hapus(posisi)
    set_status("success", f"{node.nama} dihapus dari urutan ke-{posisi}.")


def aksi_geser(arah):
    posisi = st.session_state.get("pilih")
    if daftar().kosong() or posisi is None:
        return
    tujuan = posisi + arah
    if tujuan < 1 or tujuan > daftar().hitung():
        set_status("warning", "Tidak bisa digeser lagi.")
        return
    node = daftar().pindahkan(posisi, tujuan)
    st.session_state.pilih = tujuan
    set_status("success", f"{node.nama} dipindahkan dari urutan ke-{posisi} ke ke-{tujuan}.")


def aksi_pindah():
    posisi = st.session_state.get("pilih")
    if daftar().kosong() or posisi is None:
        return
    tujuan = int(st.session_state.tujuan)
    if tujuan == posisi:
        set_status("info", "Posisi asal dan tujuan sama, tidak ada perubahan.")
        return
    node = daftar().pindahkan(posisi, tujuan)
    st.session_state.pilih = tujuan
    set_status("success", f"{node.nama} dipindahkan dari urutan ke-{posisi} ke ke-{tujuan}.")


def aksi_ubah():
    posisi = st.session_state.get("pilih")
    if daftar().kosong() or posisi is None:
        return
    keluhan = st.session_state.keluhan_baru.strip()
    if not keluhan:
        set_status("warning", "Isi kolom keluhan baru dulu.")
        return
    node = daftar().ubah_keluhan(posisi, keluhan)
    st.session_state.keluhan_baru = ""
    set_status("success", f"Keluhan {node.nama} diubah menjadi '{keluhan}'.")


def aksi_panggil():
    if daftar().kosong():
        set_status("info", "Tidak ada pasien dalam daftar tunggu.")
        return
    node = daftar().panggil()
    pesan = (f"Memanggil Tiket No. {node.no_antrian} - {node.nama} ({node.keluhan}). "
             "Silakan masuk ke ruang periksa.")
    set_status("success", pesan)
    st.toast(pesan, icon="📢")


def aksi_cari():
    kata = st.session_state.cari.strip()
    if not kata:
        return
    hasil = daftar().cari(kata)
    if not hasil:
        set_status("warning", f"Pasien '{kata}' tidak ditemukan.")
        return
    st.session_state.pilih = hasil[0]
    set_status("success", f"Ditemukan {len(hasil)} pasien pada urutan: {', '.join(map(str, hasil))}.")


def aksi_buka():
    berkas = st.session_state.get("berkas")
    if berkas is None:
        set_status("warning", "Pilih file Excel/CSV dulu.")
        return
    ekstensi = os.path.splitext(berkas.name)[1].lower()
    fd, path = tempfile.mkstemp(suffix=ekstensi)
    with os.fdopen(fd, "wb") as f:
        f.write(berkas.getvalue())
    konversi = False
    try:
        try:
            data = baca_file(path)                 # format asli program
        except ValueError:
            data = baca_fleksibel(path)            # format lain: dikonversi otomatis
            konversi = True
    except Exception as e:
        set_status("error", f"Gagal membuka file: {e}")
        return
    finally:
        os.remove(path)
    daftar().muat(data)
    st.session_state.pilih = 1
    set_status("success", f"{len(data)} pasien dimuat dari {berkas.name}"
               + (" (format dikonversi otomatis, silakan simpan ulang)" if konversi else ""))


# ---------- gambar rantai node ----------
def html_rantai(node_list, terpilih):
    """Menggambar HEAD -> node -> node -> None sebagai HTML."""
    panah = "<div style='font-size:22px;color:#1F4E79;padding:0 6px'>&#10142;</div>"
    badge_head = ("<div style='background:#1F4E79;color:white;font-weight:bold;"
                  "padding:6px 12px;border-radius:8px'>HEAD</div>")
    badge_none = ("<div style='background:#FDECEA;color:#B3261E;border:2px solid #B3261E;"
                  "font-weight:bold;padding:6px 12px;border-radius:8px'>None</div>")
    bagian = [badge_head, panah]
    for i, node in enumerate(node_list, start=1):
        sorot = (i == terpilih)
        isi = "#2E89D4"" if sorot else "#E3F0FB"
        garis = "#54CED5" if sorot else "#1F4E79"
        nama = node.nama if len(node.nama) <= 12 else node.nama[:11] + "…"
        bagian.append(
            f"<div style='text-align:center'>"
            f"<div style='display:flex;border:2px solid {garis};background:{isi};"
            f"border-radius:10px;min-width:150px'>"
            f"<div style='padding:6px 10px;flex:1'>"
            f"<div style='font-size:11px;color:#6B7785'>#{node.no_antrian}</div>"
            f"<div style='font-weight:bold;color:#1F2933'>{html.escape(nama)}</div></div>"
            f"<div style='border-left:2px solid {garis};width:34px;display:flex;"
            f"align-items:center;justify-content:center'>"
            f"<div style='width:9px;height:9px;border-radius:50%;background:{garis}'></div></div>"
            f"</div><div style='font-size:11px;color:#6B7785'>Node {i}</div></div>")
        bagian.append(panah)
    bagian.append(badge_none)
    if not node_list:
        bagian.append("<div style='color:#6B7785;font-style:italic;padding-left:10px'>daftar kosong</div>")
    return ("<div style='display:flex;align-items:flex-start;overflow-x:auto;padding:8px 2px 12px'>"
            + "".join(bagian) + "</div>")


# ---------- susunan halaman ----------
sll = daftar()
n = sll.hitung()
node_list = sll.semua_node()

# nilai bawaan widget dijaga agar selalu berada dalam rentang yang valid
if st.session_state.get("f_posisi", n + 1) > n + 1 or "f_posisi" not in st.session_state:
    st.session_state.f_posisi = n + 1
if n:
    st.session_state.pilih = min(max(st.session_state.get("pilih", 1), 1), n)
    st.session_state.tujuan = min(max(int(st.session_state.get("tujuan", 1)), 1), n)

kiri, kanan = st.columns([4, 1])
kiri.title(":material/medical_services: Daftar Tunggu Pasien Klinik")
kiri.caption("Struktur Data  •  Single Linked List")
kanan.metric("Pasien menunggu", n)

jenis, teks = st.session_state.status
getattr(st, jenis)(teks)

# --- tambah pasien ---
with st.container(border=True):
    st.subheader("Tambah Pasien")
    with st.form("form_tambah"):
        c1, c2, c3, c4 = st.columns([3, 3, 1.2, 1.2], vertical_alignment="bottom")
        c1.text_input("Nama", key="f_nama")
        c2.text_input("Keluhan", key="f_keluhan")
        c3.selectbox("Posisi", range(1, n + 2), key="f_posisi")
        c4.form_submit_button("Tambah", type="primary", on_click=aksi_tambah, width="stretch")
    st.caption("Posisi 1 = paling depan, angka terakhir = paling belakang.")

# --- tabel ---
pilih = st.session_state.get("pilih") if n else None
df = pd.DataFrame(sll.ke_baris(), columns=["Urutan", "Tiket", "Nama", "Keluhan"])


def warnai(baris):
    # Set foreground and background together so dark-mode text stays readable.
    return (["background-color:#DBEAFE; color:#172554; font-weight:600"] * len(baris) if baris["Urutan"] == pilih
            else [""] * len(baris))


st.dataframe(df.style.apply(warnai, axis=1), hide_index=True, width="stretch",
             height=min(38 + 35 * max(n, 3), 320))

# --- aksi pada pasien terpilih ---
with st.container(border=True):
    st.subheader("Aksi pada Pasien")
    if n:
        st.selectbox("Pasien yang dipilih", range(1, n + 1), key="pilih",
                     format_func=lambda p: f"{p}. {node_list[p - 1].nama} (Tiket {node_list[p - 1].no_antrian})")
    else:
        st.caption("Belum ada pasien. Tambahkan pasien terlebih dahulu.")

    a1, a2, a3, a4, a5 = st.columns([1, 1, 1, 2.2, 2.6], vertical_alignment="bottom")
    a1.button("🗑 Hapus", on_click=aksi_hapus, disabled=(n == 0), width="stretch")
    a2.button("▲ Naik", on_click=aksi_geser, args=(-1,), disabled=(n == 0), width="stretch")
    a3.button("▼ Turun", on_click=aksi_geser, args=(1,), disabled=(n == 0), width="stretch")
    with a4:
        p1, p2 = st.columns([1, 1.4], vertical_alignment="bottom")
        p1.number_input("Pindah ke urutan", min_value=1, max_value=max(n, 1), step=1,
                        key="tujuan", disabled=(n == 0))
        p2.button("Pindahkan", on_click=aksi_pindah, disabled=(n == 0), width="stretch")
    with a5:
        u1, u2 = st.columns([1.6, 1], vertical_alignment="bottom")
        u1.text_input("Keluhan baru", key="keluhan_baru", disabled=(n == 0))
        u2.button("Ubah keluhan", on_click=aksi_ubah, disabled=(n == 0), width="stretch")

    b1, b2, b3 = st.columns([3, 1, 3], vertical_alignment="bottom")
    b1.text_input("Cari nama", key="cari", on_change=aksi_cari)
    b2.button("Cari", on_click=aksi_cari, width="stretch")
    b3.button("📢 Panggil pasien depan", type="primary", on_click=aksi_panggil,
              disabled=(n == 0), width="stretch")

# --- bentuk single linked list ---
with st.container(border=True):
    st.subheader("Bentuk Single Linked List")
    st.html(html_rantai(node_list, pilih))

# --- penyimpanan ---
with st.container(border=True):
    st.subheader("Penyimpanan Data (Excel / CSV)")
    d1, d2 = st.columns(2)
    waktu = f"{datetime.now():%Y%m%d_%H%M}"
    baris_data = sll.ke_baris()
    with d1:
        st.markdown("**Simpan**")
        if openpyxl is None:
            st.caption("Excel butuh `pip install openpyxl`. Gunakan CSV.")
        else:
            st.download_button("💾 Simpan ke Excel (.xlsx)",
                               data=ke_bytes(simpan_xlsx, ".xlsx", baris_data) if n else b"",
                               file_name=f"daftar_tunggu_{waktu}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               disabled=(n == 0), width="stretch")
        st.download_button("Simpan ke CSV",
                           data=ke_bytes(simpan_csv, ".csv", baris_data) if n else b"",
                           file_name=f"daftar_tunggu_{waktu}.csv", mime="text/csv",
                           disabled=(n == 0), width="stretch")
    with d2:
        st.markdown("**Buka dari file**")
        st.file_uploader("Pilih file Excel / CSV (format apa pun yang memuat kolom nama dan keluhan)",
                         type=["xlsx", "csv"], key="berkas")
        st.button("📂 Muat ke daftar", on_click=aksi_buka, width="stretch")
        st.caption("Data saat ini akan diganti dengan isi file.")
