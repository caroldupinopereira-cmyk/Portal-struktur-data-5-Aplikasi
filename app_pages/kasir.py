"""
KasirKu: Rak Produk dengan Array (versi Streamlit)
Tugas Kelompok Struktur Data, Tahap 1: Array

Cara menjalankan aplikasi web:
    pip install streamlit
    streamlit run app_pages/kasir.py

Cara menjalankan uji logika lewat teks (tanpa tampilan, hasilnya bisa dipakai di laporan):
    python app_pages/kasir.py

Library yang dipakai:
    csv         membaca file CSV baris demi baris (fitur Muat CSV)
    streamlit   tampilan web: tab, kolom isian, tombol, unggah file
    tempfile    menyimpan sementara file CSV yang diunggah
    dataclasses kelas data singkat untuk Produk (nama, harga, stok)
"""
import csv
import html as _html
import os
import re
import tempfile
import time
from dataclasses import dataclass

import streamlit as st
from portal.sidebar import sidebar_header

# Simulasi alamat memori: tiap produk dianggap memakai 24 byte (hanya untuk peraga).
ALAMAT_BASIS = 0x1000
UKURAN_ELEMEN = 24
MIN_KOTAK, MAKS_KOTAK = 3, 20
KOLOM = 10   # satu baris maksimal 10 kotak, sisanya turun ke baris kedua


@dataclass
class Produk:
    nama: str
    harga: int = None
    stok: int = None


KUNCI_URUT = {
    "nama":  lambda p: p.nama.lower(),
    "harga": lambda p: (p.harga is None, p.harga or 0),
    "stok":  lambda p: (p.stok is None, p.stok or 0),
}

CSV_CONTOH = """nama,harga,stok
Sabun Mandi,4500,60
Biskuit,abc,10
Sampo Sachet,1500,100
Pasta Gigi,12000,25
Mie Instan,3500,120
Tepung Terigu,13000
Garam,
Kecap Manis,15000,18
Sarden Kaleng,9500,2
Roti Tawar,16000,8
"""


# =====================================================================
# LOGIKA ARRAY (tidak bergantung pada tampilan)
# =====================================================================
def angka(teks):
    teks = teks.strip()
    if not teks:
        return None
    if "." in teks:   # titik hanya boleh sebagai pemisah ribuan, misalnya 4.500
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+", teks):
            raise ValueError("titik hanya untuk ribuan")
        teks = teks.replace(".", "")
    n = int(teks)
    if n < 0:
        raise ValueError("tidak boleh negatif")
    return n


class Rak:
    def __init__(self, kapasitas=8):
        self.kapasitas = kapasitas          # ditetapkan sekali, tidak pernah diubah
        self.data = [None] * kapasitas      # kotak kosong = None
        self.jumlah = 0                     # banyaknya kotak yang ada isinya
        self.skor = [0, 0, 0]               # cari biasa, tebak tengah, lewat nomor

    def alamat(self, i):
        return ALAMAT_BASIS + i * UKURAN_ELEMEN

    def rumus(self, i):
        return f"alamat = {ALAMAT_BASIS:#x} + {i} × {UKURAN_ELEMEN} = 0x{self.alamat(i):04X}"

    def di_luar(self, i):
        return i < 0 or i >= self.kapasitas

    def kosong_pertama(self):
        """Nomor kotak kosong paling kiri, atau -1 jika rak penuh."""
        for i in range(self.kapasitas):
            if self.data[i] is None:
                return i
        return -1

    def rapat(self):
        """True jika semua isi berjajar dari kotak [0] tanpa lubang di tengah."""
        return all(self.data[i] is not None for i in range(self.jumlah))

    def cari_indeks(self, nama):
        for i in range(self.kapasitas):
            p = self.data[i]
            if p is not None and p.nama.lower() == nama.strip().lower():
                return i
        return -1

    def tambah(self, produk):
        if self.jumlah == self.kapasitas:
            return -1, (f"Rak penuh! Array hanya punya {self.kapasitas} kotak dan ukurannya tetap sejak dibuat, "
                        "jadi tidak bisa ditambah. Kosongkan satu kotak dulu (Hapus), atau klik Mulai Ulang untuk memesan memori baru.")
        if self.cari_indeks(produk.nama) != -1:
            return -1, f"'{produk.nama}' sudah ada di rak."
        i = self.kosong_pertama()           # lubang bekas Hapus diisi lebih dulu
        self.data[i] = produk
        self.jumlah += 1
        return i, f"'{produk.nama}' ditaruh di kotak [{i}]."

    def nama_dipakai(self, nama, kecuali=-1):
        """True jika nama itu sudah dimiliki produk di kotak lain (kotak 'kecuali' tidak dihitung)."""
        j = self.cari_indeks(nama)
        return j != -1 and j != kecuali

    def ubah_indeks(self, i, harga=None, stok=None, nama=None):
        p = self.data[i]
        p.nama = p.nama if not nama else nama.strip()
        p.harga = p.harga if harga is None else harga
        p.stok = p.stok if stok is None else stok

    def ubah(self, nama, harga=None, stok=None):
        i = self.cari_indeks(nama)
        if i != -1:
            self.ubah_indeks(i, harga, stok)
        return i

    def terurut(self):
        nama = [p.nama.lower() for p in self.data if p is not None]
        return nama == sorted(nama)

    def buka_langkah(self, i):
        if self.di_luar(i):
            yield "gagal", [], (f"Nomor [{i}] di luar rak! Kotak hanya bernomor 0 sampai {self.kapasitas - 1}. "
                                "Inilah yang disebut index out of bounds.")
            return
        if self.data[i] is None:
            yield "periksa", [i], f"Kotak [{i}] dibuka langsung ({self.rumus(i)}). Isinya masih kosong (dipesan)."
            return
        yield "ketemu", [i], f"Kotak [{i}] dibuka langsung dalam 1 langkah: {self.data[i].nama}. ({self.rumus(i)})"

    def cari_langkah(self, kata):
        for i in range(self.kapasitas):
            if self.data[i] is None:
                yield "periksa", [i], f"Periksa kotak [{i}]: kosong, dilewati"
                continue
            yield "periksa", [i], f"Periksa kotak [{i}]: {self.data[i].nama}"
            if kata.strip().lower() in self.data[i].nama.lower():
                yield "ketemu", [i], f"Ketemu! '{self.data[i].nama}' di kotak [{i}] setelah {i + 1} pemeriksaan."
                return
        yield "gagal", [], f"'{kata}' tidak ditemukan."

    def tampil_langkah(self):
        for i in range(self.kapasitas):
            if self.data[i] is None:
                yield "periksa", [i], f"[{i}] kosong (dilewati)"
            else:
                yield "periksa", [i], f"[{i}] {self.data[i].nama}"
        yield "info", [], f"Selesai menelusuri {self.kapasitas} kotak: {self.jumlah} terisi, {self.kapasitas - self.jumlah} kosong."

    def sisip_langkah(self, idx, produk):
        if self.jumlah == self.kapasitas:
            yield "gagal", [], (f"Rak penuh! Tidak ada kotak kosong untuk menampung geseran, dan array tidak bisa "
                                f"dibesarkan (tetap {self.kapasitas} kotak). Kosongkan satu kotak dulu (Hapus) atau klik Mulai Ulang.")
            return
        if self.di_luar(idx):
            yield "gagal", [], (f"Nomor [{idx}] di luar rak! Kotak hanya bernomor 0 sampai {self.kapasitas - 1} "
                                "(index out of bounds).")
            return
        if self.cari_indeks(produk.nama) != -1:
            yield "gagal", [], f"'{produk.nama}' sudah ada di rak."
            return
        if self.data[idx] is None:      # kotak tujuan kosong: langsung diisi, tidak ada yang digeser
            self.data[idx] = produk
            self.jumlah += 1
            yield "ketemu", [idx], f"'{produk.nama}' disisipkan di kotak [{idx}] yang masih kosong, jadi 0 geseran."
            return
        akhir = -1                       # cari kotak kosong pertama di sebelah KANAN nomor tujuan
        for k in range(idx + 1, self.kapasitas):
            if self.data[k] is None:
                akhir = k
                break
        if akhir == -1:
            yield "gagal", [], (f"Sisip di [{idx}] ditolak: tidak ada kotak kosong di sebelah kanan [{idx}], jadi isi "
                                "tidak punya tempat untuk bergeser ke kanan. Coba nomor lain, atau kosongkan kotak di kanan dulu (Hapus).")
            return
        geser = 0
        for i in range(akhir, idx, -1):
            self.data[i], self.data[i - 1] = self.data[i - 1], None
            geser += 1
            yield "geser", [i], f"Isi kotak [{i - 1}] digeser ke kanan, ke kotak [{i}]."
        self.data[idx] = produk
        self.jumlah += 1
        yield "ketemu", [idx], (f"'{produk.nama}' disisipkan di kotak [{idx}] setelah {geser} geseran. "
                                "Makin jauh kotak kosong di kanan, makin banyak geseran  ->  O(n).")

    def hapus_langkah(self, nama):
        idx = self.cari_indeks(nama)
        if idx == -1:
            yield "gagal", [], f"'{nama}' tidak ditemukan."
            return
        yield from self.hapus_indeks_langkah(idx)

    def hapus_indeks_langkah(self, idx):
        if self.di_luar(idx) or self.data[idx] is None:
            yield "gagal", [], f"Kotak [{idx}] kosong atau di luar rak, tidak ada yang bisa dihapus."
            return
        yield "hapus", [idx], f"Mengosongkan kotak [{idx}]: menghapus '{self.data[idx].nama}'."
        self.data[idx] = None            # hanya isinya yang hilang, kotaknya tetap ada
        self.jumlah -= 1
        yield "info", [], (f"Selesai: kotak [{idx}] sekarang kosong tapi tetap dipesan. Kotak lain TIDAK bergeser dan "
                           f"nomornya tidak berubah. Sekarang terisi {self.jumlah} dari {self.kapasitas} kotak. "
                           "Tambah berikutnya akan mengisi kotak kosong paling kiri.")

    def urutkan_langkah(self, kunci):
        if not self.rapat():             # bubble sort butuh isi yang berjajar, jadi rapatkan ke kiri dulu
            yield "info", [], "Ada kotak kosong di tengah. Isi digeser rapat ke kiri dulu sebelum diurutkan."
            tujuan = 0
            for i in range(self.kapasitas):
                if self.data[i] is not None:
                    if i != tujuan:
                        self.data[tujuan], self.data[i] = self.data[i], None
                        yield "geser", [tujuan], f"Isi kotak [{i}] digeser ke kotak [{tujuan}]."
                    tujuan += 1
        n = self.jumlah
        for i in range(n - 1):
            tukar = False
            for j in range(n - i - 1):
                a, b = self.data[j], self.data[j + 1]
                yield "bandingkan", [j, j + 1], f"Bandingkan [{j}] {a.nama} dengan [{j + 1}] {b.nama}"
                if KUNCI_URUT[kunci](a) > KUNCI_URUT[kunci](b):
                    self.data[j], self.data[j + 1], tukar = b, a, True
                    yield "tukar", [j, j + 1], "Urutan salah, kedua kotak ditukar."
            yield "terurut", [n - i - 1], ""
            if not tukar:
                break
        yield "terurut", list(range(n)), f"Selesai! Rak terurut berdasarkan {kunci}."

    def impor_langkah(self, path):
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                baris = list(csv.reader(f))
        except (OSError, UnicodeDecodeError):
            yield "gagal", [], "File tidak bisa dibuka atau bukan file teks CSV (UTF-8)."
            return
        masuk = 0
        for no, b in enumerate(baris, start=1):
            b = [c.strip() for c in b] + ["", "", ""]
            if not any(b) or (no == 1 and b[0].lower() == "nama"):
                continue
            if self.jumlah == self.kapasitas:
                yield "gagal", [], (f"Rak penuh! Baris {no} dan seterusnya tidak muat, karena jumlah kotak array "
                                    "tetap dan tidak bisa ditambah.")
                return
            try:
                i, pesan = self.tambah(Produk(b[0], angka(b[1]), angka(b[2])))
            except ValueError:
                i, pesan = -1, f"Baris {no} dilewati: harga/stok harus angka (tidak negatif)."
            masuk += i >= 0
            yield ("ketemu", [i], pesan) if i >= 0 else ("gagal", [], pesan)
        yield "info", [], f"Selesai impor: {masuk} produk masuk ke rak."

    def balap_langkah(self, nama):
        # Syarat (dijaga tombolnya): rak rapat tanpa lubang, terurut nama, isi minimal 2.
        kunci, n = nama.strip().lower(), self.jumlah
        lo, hi, i, babak = 0, n - 1, 0, 0
        biasa = tengah = 0
        sel_b = sel_t = False
        hasil = -1
        self.skor = [0, 0, 0]
        while not (sel_b and sel_t):
            babak += 1
            sorot = {} if sel_t else {k: "pudar" for k in range(n) if k < lo or k > hi}
            teks = f"Babak {babak}: "
            if not sel_b:
                biasa += 1
                sorot[i] = "emas"
                teks += f"cari biasa buka [{i}]; "
                if self.data[i].nama.lower() == kunci:
                    sel_b, hasil = True, i
                i += 1
                sel_b = sel_b or i == n
            if not sel_t:
                mid = (lo + hi) // 2
                tengah += 1
                sorot[mid] = "ungu"
                teks += f"tebak tengah buka [{mid}] (sisa [{lo}] sampai [{hi}])"
                nama_tengah = self.data[mid].nama.lower()
                lo, hi = (lo, hi) if nama_tengah == kunci else (mid + 1, hi) if nama_tengah < kunci else (lo, mid - 1)
                sel_t = nama_tengah == kunci or lo > hi
            self.skor = [biasa, tengah, 0]
            yield "balap", sorot, teks.rstrip("; ")
        self.skor = [biasa, tengah, 1 if hasil >= 0 else 0]
        menang = "Tebak tengah menang." if tengah < biasa else "Cari biasa menang." if biasa < tengah else "Seri."
        awal = f"'{nama}' ada di kotak [{hasil}]. " if hasil >= 0 else f"'{nama}' tidak ada di rak. "
        akhir = (" Lewat nomor: 1 pemeriksaan, tapi hanya bisa kalau nomor kotaknya sudah diketahui."
                 if hasil >= 0 else "")
        yield (("ketemu" if hasil >= 0 else "gagal"), ({hasil: "hijau"} if hasil >= 0 else {}),
               awal + f"Cari biasa: {biasa} pemeriksaan. Tebak tengah: {tengah} pemeriksaan. {menang}{akhir} "
               "Makin banyak data, makin jauh selisihnya.")


# =====================================================================
# UJI LEWAT TEKS (jalankan dengan: python app_pages/kasir.py)
# =====================================================================
def uji_teks():
    def cetak(langkah):
        for _, _, pesan in langkah:
            if pesan:
                print("  ", pesan)

    def isi_rak(rak):
        return [p.nama if p else "-" for p in rak.data]

    rak = Rak(kapasitas=5)

    print("--- 1. Tambah (cukup nama, harga dan stok boleh menyusul; kotak ke-6 pasti ditolak) ---")
    for p in [Produk("Beras", 65000, 20), Produk("Gula", 16000), Produk("Kopi"),
              Produk("Telur", 28000, 3), Produk("Teh", 12000, 40), Produk("Susu")]:
        print("  ", rak.tambah(p)[1])

    print("\n--- 2. Isi array beserta alamat memorinya ---")
    for i, p in enumerate(rak.data):
        print(f"  [{i}] 0x{rak.alamat(i):04X}", p if p else "kosong (dipesan)")

    print("\n--- 3. Buka kotak lewat nomor, O(1) (nomor 9 di luar rak) ---")
    cetak(rak.buka_langkah(2))
    cetak(rak.buka_langkah(9))

    print("\n--- 4. Cari 'gula' (cari biasa) ---")
    cetak(rak.cari_langkah("gula"))

    print("\n--- 5. Hapus 'Gula': hanya isinya yang kosong, kotak lain tidak bergeser ---")
    cetak(rak.hapus_langkah("Gula"))
    print("   Isi rak:", isi_rak(rak), f"(terisi {rak.jumlah} dari {rak.kapasitas})")

    print("\n--- 6. Tambah 'Susu': mengisi kotak kosong paling kiri (lubang bekas Gula) ---")
    print("  ", rak.tambah(Produk("Susu", 14000, 15))[1])
    print("   Isi rak:", isi_rak(rak))

    print("\n--- 7. Kosongkan 'Teh', lalu Sisip 'Mentega' di nomor 1 (isi bergeser ke kanan sampai kotak kosong) ---")
    cetak(rak.hapus_langkah("Teh"))
    cetak(rak.sisip_langkah(1, Produk("Mentega", 9000, 12)))
    print("   Isi rak:", isi_rak(rak))

    print("\n--- 8. Sisip saat rak penuh (harus ditolak) ---")
    cetak(rak.sisip_langkah(0, Produk("Lada")))

    print("\n--- 9. Kosongkan 'Beras', lalu Sisip di nomor 2 (tidak ada kotak kosong di kanannya, ditolak) ---")
    cetak(rak.hapus_langkah("Beras"))
    print("   Isi rak:", isi_rak(rak))
    cetak(rak.sisip_langkah(2, Produk("Lada")))

    print("\n--- 10. Urutkan berdasarkan nama (isi dirapatkan dulu karena ada lubang) ---")
    cetak(m for m in rak.urutkan_langkah("nama") if m[2])
    print("   Isi rak:", isi_rak(rak))

    print("\n--- 11. Balapan cari 'Telur': cari biasa, tebak tengah, lewat nomor ---")
    cetak(rak.balap_langkah("Telur"))

    print("\n--- 12. Ubah nama langsung lewat nomor kotak (nama kembar ditolak) ---")
    r = Rak(kapasitas=3)
    r.tambah(Produk("Beras", 65000, 5))
    r.tambah(Produk("Gula", 16000, 9))
    print("   'gula' dipakai produk lain? ", r.nama_dipakai("gula", kecuali=0), "(jadi ganti nama kotak [0] jadi 'gula' ditolak)")
    print("   'Beras' dipakai produk lain? ", r.nama_dipakai("Beras", kecuali=0), "(kotak [0] sendiri tidak dihitung)")
    r.ubah_indeks(0, nama="Beras Premium", harga=70000)
    print("   Isi rak:", [str(p) for p in r.data if p])

    print("\n--- 13. Impor file CSV ke rak berkapasitas 8 ---")
    with open("contoh_supplier.csv", "w", encoding="utf-8") as f:
        f.write(CSV_CONTOH)
    cetak(Rak(kapasitas=8).impor_langkah("contoh_supplier.csv"))


# =====================================================================
# TAMPILAN STREAMLIT
# =====================================================================
FONT = "Segoe UI"
WARNA = {
    "latar": "#0f1626", "panel": "#172033", "kotak": "#212c44", "garis": "#33415e",
    "teks": "#e7eaf0", "redup": "#8a94a6", "gelap": "#0e1422", "tombol": "#222d45",
    "tombol_h": "#2f3d5c", "emas": "#d9bd8c", "hijau": "#84baa7", "mawar": "#cc8f94",
    "ungu": "#a59dcb", "pudar": "#182134", "biru": "#7fa8d6", "abu": "#6b7385", "tosca": "#5fc9c0",
}
WARNA_JENIS = {"periksa": "emas", "bandingkan": "emas", "hapus": "mawar", "ketemu": "hijau",
               "geser": "ungu", "tukar": "ungu", "terurut": "hijau"}
WARNA_LOG = {**WARNA_JENIS, "gagal": "mawar"}
CONTOH = [Produk("Beras 5kg", 65000, 20), Produk("Minyak Goreng", 18000, 35),
          Produk("Gula Pasir", 16000, 40), Produk("Telur", 28000, 3),
          Produk("Kopi Sachet"), Produk("Teh Celup", 12000)]
PERHATIAN = ("PERHATIAN:  jumlah kotak TETAP setelah dikunci.  Nomor kotak mulai dari 0.  "
             "Hapus hanya mengosongkan isi, kotaknya tetap ada.  Bingung? Buka Panduan di bagian bawah halaman.")
RUMUS_AWAL = "Alamat memori: pilih kotak / Cari Nomor untuk lihat rumusnya"

# kolom isian tiap tab: kunci_kolom -> (judul, lebar relatif)
FIELDS = {
    "tambah": ["nama", "harga", "stok"],
    "sisip": ["nomor", "nama", "harga", "stok"],
    "cari": ["nomor", "nama"],
    "ubah": ["nomor", "nama", "baru", "harga", "stok"],
    "hapus": ["nomor", "nama"],
    "balap": ["nama"],
}

CSS = """<style>
.block-container{padding-top:2rem;max-width:1200px}
.kk-judul{font-size:30px;font-weight:800;background:linear-gradient(90deg,#5fc9c0,#7fa8d6);
  -webkit-background-clip:text;background-clip:text;color:transparent;display:inline-block;line-height:1.3}
.kk-mem{color:#84baa7;font-weight:700;font-size:14px;margin:2px 0 6px}
.kk-bn{border-radius:6px;padding:8px 12px;font-size:13px;font-weight:700;margin:4px 0;font-family:"Segoe UI",system-ui,sans-serif}
.kk-bn.info{background:#3b3220;color:#d9bd8c}
.kk-bn.gagal{background:#3a2226;color:#cc8f94}
.kk-saran{color:#84baa7;font-weight:700;font-size:14px;margin:6px 0 4px}
.kk-rak{background:#172033;border-radius:10px;padding:14px 10px;margin:6px 0;font-family:"Segoe UI",system-ui,sans-serif}
.kk-grid{display:grid;justify-content:center;gap:8px}
.kk-sl{text-align:center;min-width:0}
.kk-no{color:#e7eaf0;font:700 13px Consolas,Menlo,monospace}
.kk-ad{color:#8a94a6;font:10px Consolas,Menlo,monospace;margin-bottom:3px}
.kk-bx{position:relative;height:92px;box-sizing:border-box;border:1px solid #33415e;background:#212c44;color:#e7eaf0;
  overflow:hidden;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:4px 4px 10px;line-height:1.25}
.kk-bx .nm{font-weight:700;font-size:12px;word-break:break-word;margin-bottom:8px}
.kk-bx .tx{font-size:11px}
.kk-bx .st{position:absolute;left:0;right:0;bottom:0;height:6px}
.kk-bx.kosong{background:#172033;border-style:dashed;color:#8a94a6;font-style:italic;font-size:11px;text-align:center}
%STATUS%
.kk-bx.pudar{border-color:#182134}
.kk-bx.pudar:not(.kosong){background:#182134;color:#8a94a6}
.kk-bx.pilih{outline:2px solid #e7eaf0;outline-offset:1px}
.kk-info{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px;font-size:12px;margin:6px 2px 0;color:#8a94a6}
.kk-rumus{color:#7fa8d6;font:700 12px Consolas,Menlo,monospace}
.kk-pap{margin-top:12px;padding:0 6px;font-size:13px;color:#e7eaf0}
.kk-pp{display:flex;align-items:center;gap:10px;margin:5px 0}
.kk-pn{width:110px;font-weight:700}
.kk-pb{flex:1;max-width:380px;height:16px;border:1px solid #33415e;display:block}
.kk-pb span{display:block;height:100%}
.kk-pesan{text-align:center;font-weight:700;margin-top:12px;font-size:14px}
.kk-konsep{background:#172033;color:#d9bd8c;font-weight:700;font-size:14px;padding:10px 14px;border-radius:6px;
  margin:8px 0;min-height:44px;font-family:"Segoe UI",system-ui,sans-serif}
.kk-log{background:#0f1626;color:#e7eaf0;border:1px solid #33415e;border-radius:4px;padding:8px 10px;
  height:170px;overflow-y:auto;font:13px Consolas,Menlo,monospace;line-height:1.5}
</style>"""
CSS = CSS.replace("%STATUS%", "".join(
    f".kk-bx.{k}{{border-color:{WARNA[k]};border-width:2px}}"
    f".kk-bx.{k}:not(.kosong){{background:{WARNA[k]};color:#0e1422}}"
    for k in ("emas", "hijau", "mawar", "ungu", "biru")))

S = st.session_state
PH = {}   # placeholder yang diisi ulang saat animasi (dibuat ulang tiap kali skrip dijalankan)


def esc(t):
    return _html.escape(str(t), quote=True).replace("$", "&#36;")


def rupiah(n):
    return "Rp " + f"{n:,}".replace(",", ".")


def aturan_array(n):
    return [
        ("Ukuran tetap",
         f"Jumlah kotak dipesan sekali di awal (rakmu {n} kotak) dan tidak bisa ditambah. Kalau rak penuh, kosongkan "
         "satu kotak (Hapus) atau klik Mulai Ulang untuk memesan array baru."),
        ("Nomor mulai dari 0",
         f"Kotak pertama bernomor 0, bukan 1. Rakmu bernomor 0 sampai {n - 1}. Nomor di luar itu disebut index out of bounds."),
        ("Boleh ada kotak kosong di tengah",
         "Hapus hanya mengosongkan isi satu kotak. Kotaknya tetap ada dan kotak lain tidak bergeser, jadi nomor produk "
         "lain tidak berubah. Kotak kosong di tengah disebut 'lubang'. Tambah akan mengisi lubang paling kiri lebih dulu."),
        ("Tahu nomor = cepat, tahu nama = lambat",
         "Kalau nomor kotaknya diketahui, kotak dibuka langsung dalam 1 langkah. Kalau yang diketahui hanya nama, kotak "
         "harus diperiksa satu per satu."),
        ("Sisip menggeser isi ke kanan",
         "Kalau kotak tujuan kosong, produk langsung diisi. Kalau sudah berisi, isinya digeser ke kanan sampai kotak "
         "kosong pertama di sebelah kanan, baru kotak tujuan diisi. Kalau di kanan tidak ada kotak kosong, Sisip ditolak."),
        ("Tebak tengah butuh rak rapat dan urut",
         "Tebak tengah (binary search) hanya jalan kalau tidak ada lubang dan rak sudah urut nama. Tombol Urutkan "
         "otomatis merapatkan isi ke kiri dulu."),
    ]


ARTI_WARNA = [
    ("emas", "Emas: kotak sedang diperiksa atau dibandingkan, juga jalur cari biasa."),
    ("hijau", "Hijau: ketemu, berhasil ditambah, atau sudah terurut."),
    ("mawar", "Mawar: kotak dikosongkan atau terjadi kesalahan."),
    ("ungu", "Ungu: kotak bergeser atau ditukar, juga jalur tebak tengah."),
    ("biru", "Biru: jalur lewat nomor di papan skor."),
    ("hijau", "Strip hijau di dasar kotak: stok aman (5 atau lebih)."),
    ("emas", "Strip emas: stok menipis (kurang dari 5)."),
    ("mawar", "Strip mawar: stok habis (0)."),
    ("abu", "Strip abu: stok belum diisi."),
]


def panduan(n):
    """Isi Panduan: daftar (judul bagian, warna, [(sub judul, isi), ...])."""
    return [
        ("Mulai dari sini", "hijau", [
            ("Aplikasi ini untuk apa?",
             "KasirKu adalah simulasi rak produk di sebuah toko. Setiap kotak di rak menyimpan satu produk (nama, harga, "
             "stok). Yang dipelajari adalah ARRAY: cara komputer menyimpan data berurutan di memori. Setiap kali kamu "
             "menekan tombol, aplikasi menggambar langkah demi langkah apa yang dikerjakan komputer, supaya kamu bisa "
             "melihat sendiri kenapa sebuah pekerjaan terasa cepat atau lambat."),
            ("Array itu apa? (perumpamaan loker)",
             "Bayangkan lemari loker bernomor. Jumlah lokernya sudah ditentukan di awal dan tidak bisa ditambah. Tiap "
             "loker punya nomor yang dimulai dari 0 (bukan 1). Kalau kamu tahu nomornya, kamu bisa langsung membuka "
             "loker itu tanpa membuka loker lain. Kalau kamu hanya tahu isinya, kamu harus membuka loker satu per satu "
             "sampai ketemu. Hampir semua yang kamu lihat di aplikasi ini adalah akibat dari dua hal itu."),
            ("Coba dalam 4 langkah",
             "1. Di tab 'Data & File' (deretan tab di bawah rak), klik Data Contoh. Rak terisi beberapa produk.\n"
             "2. Pilih salah satu kotak berisi lewat menu 'Pilih kotak' di bawah rak. Nomornya otomatis terisi di tab yang "
             "memakainya, dan rumus alamat memorinya muncul di bawah rak.\n"
             "3. Di tab 'Cari', klik Cari saat Nomor terisi: kotak langsung terbuka dalam 1 langkah. Lalu kosongkan "
             "Nomor, ketik nama produk, klik Cari lagi: kotak diperiksa satu per satu. Bandingkan banyaknya langkah di "
             "Catatan langkah.\n"
             "4. Di tab 'Urutkan', klik Urutkan Nama. Setelah itu tab 'Balapan Cari' bisa dipakai."),
        ]),
        ("Mengenal layar", "biru", [
            ("Bagian paling atas",
             "Ada judul, tulisan hijau 'Memori terkunci: N kotak (terisi M)' yang menunjukkan jumlah kotak dan berapa "
             "yang sudah ada isinya, dan tombol Mulai Ulang."),
            ("Banner kuning dan merah",
             "Banner kuning berisi pengingat aturan penting. Banner merah muncul ketika sebuah aksi ditolak, lengkap "
             "dengan alasannya, dan hilang saat kamu menjalankan aksi berikutnya."),
            ("Baris Saran (tulisan hijau)",
             "Satu kalimat yang memberi tahu langkah berikutnya yang masuk akal sesuai isi rak saat ini."),
            ("Rak (gambar kotak-kotak)",
             "Di atas tiap kotak ada nomor [indeks] dan alamat memori kecil. Di dalamnya ada nama, harga, dan stok "
             "produk. Kotak bergaris putus-putus bertuliskan 'kosong (dipesan)' artinya kotak itu sudah ada tetapi belum "
             "ada isinya. Garis tipis berwarna di dasar kotak (strip) menunjukkan keadaan stok."),
            ("Pilih kotak dan baris alamat memori",
             "Menu 'Pilih kotak' di bawah rak menandai sebuah kotak dan mengisi Nomor di tab Sisip, Cari, Ubah, dan Hapus. "
             "Baris alamat menampilkan rumus alamat kotak itu, misalnya: alamat = 0x1000 + 2 × 24 = 0x1030. Artinya "
             "komputer cukup menghitung alamatnya lalu melompat ke sana, tanpa mencari."),
            ("Tab aksi",
             "Di bawah rak ada deretan tab: Tambah, Sisip, Cari, Ubah, Hapus, Urutkan, Balapan Cari, dan Data & File. Satu tab "
             "= satu jenis pekerjaan, lengkap dengan kolom isian dan tombolnya sendiri. Tekan Enter di kolom isian sama "
             "dengan menekan tombolnya. Tombol yang tampak pudar belum bisa dipakai, misalnya Hapus saat rak masih kosong."),
            ("Kotak penjelasan dan Catatan langkah",
             "Kotak penjelasan menerangkan konsep dari aksi terakhir dan seberapa cepatnya (kompleksitas). Catatan langkah "
             "adalah daftar tertulis tiap langkah yang dikerjakan komputer (yang terbaru di paling atas). Tulisan merah "
             "berarti aksi ditolak."),
            ("Kecepatan animasi",
             "Geser slider 'Kecepatan animasi' di panel kiri (sidebar). Makin ke kanan, makin cepat."),
        ]),
        ("Tab aksi satu per satu", "emas", [
            ("Tab Tambah",
             "Isi Nama (wajib), lalu Harga dan Stok (boleh dikosongkan), klik Tambah. Produk masuk ke kotak kosong paling "
             "kiri, termasuk lubang bekas Hapus. Ditolak kalau rak penuh atau nama sudah ada (huruf besar/kecil dianggap "
             "sama). Harga dan stok ditulis angka bulat, boleh memakai titik ribuan seperti 4.500.\n"
             "Seberapa cepat: menaruh isi ke kotak itu O(1). Mencari kotak kosong dan mengecek nama kembar adalah aturan "
             "tambahan aplikasi, O(n)."),
            ("Tab Sisip",
             "Dipakai kalau produk harus masuk di nomor tertentu, bukan sekadar kotak kosong pertama. Isi Nomor kotak "
             "tujuan dan Nama (harga, stok boleh kosong), klik Sisip.\n"
             "• Kalau kotak tujuan kosong, produk langsung diisi tanpa menggeser apa pun.\n"
             "• Kalau kotak tujuan berisi, isi kotak itu dan kotak di kanannya digeser satu kotak ke kanan, sampai tepat "
             "di kotak kosong pertama di sebelah kanan. Setelah itu kotak tujuan diisi.\n"
             "• Kalau di sebelah kanan tidak ada kotak kosong, Sisip ditolak karena isi tidak punya tempat untuk bergeser.\n"
             "Seberapa cepat: O(n), karena bisa banyak kotak yang harus digeser."),
            ("Tab Cari",
             "Ada dua cara, pilih salah satu:\n"
             "• Isi Nomor kotak: kotak langsung terbuka dalam 1 langkah, O(1). Nomor di luar rak (misalnya 25 pada rak 20 "
             "kotak) memunculkan peringatan index out of bounds.\n"
             "• Kosongkan Nomor, isi Nama (boleh sebagian, misalnya 'ber' untuk Beras): kotak diperiksa dari nomor 0 satu "
             "per satu, kotak kosong dilewati, berhenti saat ketemu. O(n).\n"
             "Kalau Nomor dan Nama keduanya diisi, yang dipakai Nomor."),
            ("Tab Ubah",
             "Mengganti nama, harga, dan/atau stok produk yang sudah ada. Pilih produknya lewat Nomor kotak (langsung, O(1)) "
             "atau Nama lama (dicari dulu, O(n)). Lalu isi Nama baru, Harga baru, dan/atau Stok baru. Kolom yang dikosongkan "
             "tidak diubah, jadi untuk ganti nama saja cukup isi Nomor dan Nama baru.\n"
             "Ditolak kalau Nama baru sudah dipakai produk lain, atau kalau Nomor dan Nama lama diisi tetapi tidak cocok. "
             "Setelah nama diganti, urutan nama bisa berubah, jadi klik Urutkan lagi sebelum Balapan Cari."),
            ("Tab Hapus",
             "Mengosongkan satu kotak. Pilih lewat Nomor (O(1)) atau Nama (dicari dulu, O(n)), klik Hapus.\n"
             "Yang hilang hanya ISINYA. Kotaknya tetap ada (menjadi 'kosong (dipesan)'), kotak lain tidak bergeser, dan "
             "nomor kotak lain tidak berubah. Akibatnya bisa muncul lubang di tengah rak. Contoh: rak berisi [0] Beras, "
             "[1] Gula, [2] Kopi. Hapus Gula, maka hasilnya [0] Beras, [1] kosong, [2] Kopi. Kopi tetap di nomor 2."),
            ("Tab Urutkan",
             "Urutkan: klik Nama, Harga, atau Stok. Kalau ada lubang, isi digeser rapat ke kiri dulu. "
             "Sesudah itu dua kotak bersebelahan dibandingkan dan ditukar kalau salah urutan, diulang sampai urut "
             "(bubble sort). Produk tanpa harga atau stok ditaruh paling belakang. O(n²).\n"
             "Tampilkan: membaca semua kotak dari nomor 0 sampai terakhir satu per satu (traversal). O(n)."),
            ("Tab Balapan Cari",
             "Mengadu tiga cara mencari. Ketik nama lengkap produk (persis seperti di rak), klik Balapan Cari. Papan skor "
             "menghitung berapa kotak yang dibuka tiap cara:\n"
             "• Cari biasa (emas): membuka kotak satu per satu.\n"
             "• Tebak tengah (ungu): membuka kotak di tengah, lalu mencoret separuh yang pasti salah, diulang. Cepat, tapi "
             "hanya bisa kalau rak urut nama dan tidak ada lubang.\n"
             "• Lewat nomor (biru): 1 langkah saja, tapi hanya kalau nomornya sudah diketahui.\n"
             "Tombol baru menyala kalau rak punya minimal 2 produk, tidak ada lubang, dan sudah urut Nama. Kalau belum, "
             "klik Urutkan > Nama dulu."),
            ("Tab Data & File",
             "• Data Contoh: mengisi rak dengan produk contoh (isi lama dibuang). Kalau kotak kurang, sisanya ditolak.\n"
             "• Muat CSV: unggah file CSV berformat nama,harga,stok dengan baris pertama sebagai judul, lalu klik Muat CSV. "
             "Tombol Unduh contoh_supplier.csv memberi file contoh. Baris yang salah dilewati, dan kalau rak penuh, sisa "
             "baris ditolak. O(n).\n"
             "• Kosongkan Semua: membuang isi semua kotak, tapi jumlah kotak tetap."),
            ("Tombol Mulai Ulang (di atas)",
             "Membuang semua data dan kembali ke layar Pesan Memori untuk memilih jumlah kotak yang baru, sama seperti "
             "membuat array baru dengan ukuran lain."),
        ]),
        ("Aturan array yang perlu diingat", "ungu", aturan_array(n)),
        ("Arti istilah", "biru", [
            ("Indeks", "Nomor sebuah kotak. Dimulai dari 0. Tertulis [0], [1], [2], dan seterusnya."),
            ("Kotak kosong (dipesan)", "Kotak yang sudah disediakan sejak array dibuat tetapi belum ada isinya."),
            ("Alamat memori", "Letak kotak di memori komputer. Di sini hanya simulasi: alamat = basis + nomor × ukuran satu kotak."),
            ("Index out of bounds", "Kesalahan karena memakai nomor di luar rak, misalnya nomor 25 pada rak 20 kotak."),
            ("Linear search (cari biasa)", "Memeriksa kotak satu per satu dari awal sampai ketemu."),
            ("Binary search (tebak tengah)", "Membuka kotak di tengah, lalu membuang separuh yang pasti salah, diulang. Syaratnya data sudah urut."),
            ("Bubble sort", "Cara mengurutkan dengan membandingkan dua kotak bersebelahan dan menukarnya kalau salah urutan."),
            ("Traversal", "Membaca semua kotak satu per satu dari awal sampai akhir."),
            ("CSV", "File teks berisi data yang dipisahkan koma, bisa dibuat dari Excel (Save As CSV)."),
            ("Notasi O (kompleksitas)",
             "Menggambarkan seberapa banyak langkah bertambah kalau datanya bertambah.\n"
             "• O(1): selalu sekitar 1 langkah, berapa pun banyak datanya.\n"
             "• O(log n): data jadi dua kali lipat, langkah hanya bertambah 1.\n"
             "• O(n): data jadi dua kali lipat, langkah ikut dua kali lipat.\n"
             "• O(n²): data jadi dua kali lipat, langkah jadi empat kali lipat."),
        ]),
        ("Pesan yang sering muncul", "mawar", [
            ("'Rak penuh!'", "Semua kotak sudah berisi. Kosongkan satu kotak lewat tab Hapus, atau klik Mulai Ulang untuk memesan rak yang lebih besar."),
            ("'Nomor [x] di luar rak'", f"Nomor yang diketik tidak ada. Pakai nomor 0 sampai {n - 1}."),
            ("'Kotak [x] masih kosong'", "Kotak yang dipilih belum ada isinya, jadi tidak bisa diubah atau dihapus. Pilih kotak yang berisi produk."),
            ("'sudah ada di rak'", "Nama produk kembar. Pakai nama lain."),
            ("'Nomor dan nama tidak cocok'", "Nomor menunjuk produk lain dari nama yang diketik. Isi salah satunya saja, cukup Nomor."),
            ("'Harga dan stok harus angka'", "Tulis angka bulat tidak negatif, atau kosongkan. Titik hanya untuk ribuan, contoh 4.500."),
            ("'Sisip ... tidak ada kotak kosong di sebelah kanan'", "Isi tidak punya tempat untuk bergeser ke kanan. Pilih nomor lain, atau kosongkan kotak di sebelah kanan dulu."),
            ("Tombol Balapan Cari pudar", "Syaratnya belum terpenuhi (minimal 2 produk, tidak ada lubang, urut Nama). Baca baris Saran, lalu klik Urutkan > Nama."),
        ]),
    ]


# ---------- keadaan (session state) ----------
def init_state():
    awal = dict(rak=None, sorot={}, tetap={}, terpilih=None, papan=False, log=[], banner=None,
                konsep="", rumus=RUMUS_AWAL, kecepatan=6, v_pesan=10, bersih=[])
    for k, v in awal.items():
        S.setdefault(k, v)
    S.sibuk = False


def proses_bersih():
    """Mengosongkan kolom isian. Harus dilakukan sebelum widget dibuat, jadi dijadwalkan lalu dijalankan di awal run."""
    for kartu, kolom in S.bersih:
        if kartu == "pilih":
            S.pilih_kotak = "-"
        else:
            S[f"{kartu}_{kolom}"] = ""
    S.bersih = []


def bersih_isian(kartu=None, kolom=None):
    if kartu is None:
        S.bersih = S.bersih + [(k, c) for k, cs in FIELDS.items() for c in cs] + [("pilih", "")]
    else:
        S.bersih = S.bersih + [(kartu, c) for c in (kolom or FIELDS[kartu])]


# ---------- menggambar ----------
def saran():
    r = S.rak
    if S.sibuk:
        return "Animasi sedang berjalan, tunggu sampai selesai."
    if r.jumlah == 0:
        return "Saran: semua kotak masih 'kosong (dipesan)'. Buka tab Data & File lalu klik Data Contoh, atau isi nama di tab Tambah."
    if r.jumlah == r.kapasitas and r.terurut():
        return "Rak penuh dan sudah urut. Array tidak bisa ditambah. Coba Balapan Cari, atau kosongkan satu kotak / Mulai Ulang."
    if r.jumlah == r.kapasitas:
        return "Rak penuh, array tidak bisa ditambah. Klik Urutkan Nama agar Balapan Cari menyala, atau kosongkan satu kotak / Mulai Ulang."
    if not r.rapat():
        return ("Saran: ada kotak kosong di tengah rak (lubang). Tambah akan mengisi lubang paling kiri. Balapan Cari menyala "
                "setelah rak rapat dan urut: klik Urutkan Nama.")
    if not r.terurut():
        return "Saran: klik Urutkan Nama di tab Urutkan, maka Balapan Cari akan menyala."
    return "Rak sudah urut. Ketik nama produk di tab Balapan Cari, lalu klik Balapan Cari."


def html_kotak(i, p, status, dipilih):
    kelas = ["kk-bx"] + ([status] if status else []) + (["pilih"] if dipilih else [])
    if p is None:
        kelas.append("kosong")
        isi = "kosong<br>(dipesan)"
    else:
        harga = "Harga: -" if p.harga is None else rupiah(p.harga)
        stok = "Stok: -" if p.stok is None else f"Stok: {p.stok}"
        strip = ("abu" if p.stok is None else "mawar" if p.stok == 0 else "emas" if p.stok < 5 else "hijau")
        isi = (f'<div class="nm">{esc(p.nama)}</div><div class="tx">{esc(harga)}</div>'
               f'<div class="tx">{stok}</div><div class="st" style="background:{WARNA[strip]}"></div>')
    return (f'<div class="kk-sl"><div class="kk-no">[{i}]</div><div class="kk-ad">0x{S.rak.alamat(i):04X}</div>'
            f'<div class="{" ".join(kelas)}">{isi}</div></div>')


def html_papan():
    r, baris = S.rak, ""
    for k, (nama, warna) in enumerate([("Cari biasa", "emas"), ("Tebak tengah", "ungu"), ("Lewat nomor", "biru")]):
        skor = r.skor[k]
        pct = min(100, 100 * skor / max(1, r.jumlah))
        baris += (f'<div class="kk-pp"><span class="kk-pn" style="color:{WARNA[warna]}">{nama}</span>'
                  f'<span class="kk-pb"><span style="width:{pct}%;background:{WARNA[warna]}"></span></span>'
                  f'<b>{skor} pemeriksaan</b></div>')
    return f'<div class="kk-pap">{baris}</div>'


def gambar():
    """Menggambar ulang rak (dan banner, saran, papan skor) ke dalam satu placeholder."""
    r = S.rak
    status = {**S.tetap, **S.sorot}
    kotak = "".join(html_kotak(i, r.data[i], status.get(i), i == S.terpilih) for i in range(r.kapasitas))
    kolom = min(r.kapasitas, KOLOM)
    grid = f'<div class="kk-grid" style="grid-template-columns:repeat({kolom},minmax(0,88px))">{kotak}</div>'
    if S.papan:
        bawah = html_papan()
    elif r.jumlah < r.kapasitas:
        catatan = "" if r.rapat() else "  (lubang bekas Hapus diisi lebih dulu)"
        bawah = (f'<div class="kk-pesan" style="color:{WARNA["hijau"]}">'
                 f'Tambah berikutnya masuk ke kotak [{r.kosong_pertama()}]{esc(catatan)}</div>')
    else:
        bawah = (f'<div class="kk-pesan" style="color:{WARNA["mawar"]}">'
                 'RAK PENUH: semua kotak sudah terisi dan array tidak bisa ditambah.</div>')
    legenda = "".join(f'<span style="color:{WARNA[w]};margin-left:10px">■ {t}</span>'
                      for t, w in [("belum diisi", "abu"), ("habis (0)", "mawar"), ("menipis (&lt;5)", "emas"), ("aman (5+)", "hijau")])
    banner = f'<div class="kk-bn gagal">{esc(S.banner)}</div>' if S.banner else ""
    PH["rak"].markdown(
        f'{banner}<div class="kk-mem">Memori terkunci: {r.kapasitas} kotak (terisi {r.jumlah})</div>'
        f'<div class="kk-saran">{esc(saran())}</div>'
        f'<div class="kk-rak">{grid}{bawah}'
        f'<div class="kk-info"><span class="kk-rumus">{esc(S.rumus)}</span><span>Strip stok:{legenda}</span></div></div>',
        unsafe_allow_html=True)


def render_konsep():
    PH["konsep"].markdown(f'<div class="kk-konsep">{esc(S.konsep)}</div>', unsafe_allow_html=True)


def render_log():
    baris = "".join(f'<div style="color:{WARNA[WARNA_LOG.get(j, "teks")]}">{esc(p)}</div>' for j, p in reversed(S.log))
    PH["log"].markdown(f'<div class="kk-log">{baris or "&nbsp;"}</div>', unsafe_allow_html=True)


def set_konsep(teks, tampil=True):
    S.konsep = teks
    if tampil and "konsep" in PH:
        render_konsep()


def catat(pesan, jenis="info", tampil=True):
    S.log = (S.log + [(jenis, pesan)])[-300:]
    if jenis == "gagal":
        S.banner = pesan
    if tampil and "log" in PH:
        render_log()


def tampil_rumus(i, tampil=True):
    S.rumus = f"Kotak [{i}]: {S.rak.rumus(i)}"


# ---------- menjalankan langkah (animasi) ----------
def kilat(indeks, warna, lama=1.3):
    S.sorot, S.papan = {i: warna for i in indeks}, False
    gambar()
    time.sleep(lama)
    S.sorot = {}


def mulai(gen, konsep, papan=False, selesai=None):
    """Menjalankan generator langkah demi langkah dan menggambar tiap langkahnya."""
    S.sorot, S.tetap, S.terpilih, S.papan, S.sibuk = {}, {}, None, papan, True
    bersih_isian_pilih()
    set_konsep(konsep)
    jeda = (1100 - S.kecepatan * 100) / 1000
    for jenis, data, pesan in gen:
        if pesan:
            catat(pesan, jenis)
        S.sorot = data if isinstance(data, dict) else {i: WARNA_JENIS[jenis] for i in data if jenis in WARNA_JENIS}
        if jenis in ("ketemu", "terurut"):
            S.tetap.update(S.sorot)
        gambar()
        time.sleep(jeda / 3 if jenis == "terurut" else jeda)
    S.sibuk = False
    gambar()
    if selesai:
        selesai()
    time.sleep(1.5)
    S.sorot, S.tetap = {}, {}


def bersih_isian_pilih():
    S.bersih = S.bersih + [("pilih", "")]


def jalankan_aksi(fungsi, *arg):
    """Menjalankan satu aksi, lalu memuat ulang halaman agar status tombol ikut diperbarui."""
    S.banner = None
    fungsi(*arg)
    st.rerun()


# ---------- membaca isian ----------
def baca(kartu):
    try:
        return S[f"{kartu}_nama"].strip(), angka(S[f"{kartu}_harga"]), angka(S[f"{kartu}_stok"])
    except ValueError:
        catat("Harga dan stok harus angka bulat tidak negatif (atau dikosongkan). Titik hanya untuk ribuan, contoh 4.500.", "gagal")


def baca_nomor(kartu):
    teks = S[f"{kartu}_nomor"].strip()
    if not teks:
        return None, True
    try:
        return int(teks), True
    except ValueError:
        catat("Nomor kotak harus berupa angka bulat, misalnya 0, 1, 2.", "gagal")
        return None, False


def perlu_nama(kartu, pesan):
    nama = S[f"{kartu}_nama"].strip()
    if not nama:
        catat(pesan, "gagal")
    return nama or None


def target_kotak(kartu, nama, kata):
    nomor, sah = baca_nomor(kartu)
    if not sah:
        return None
    if nomor is not None:
        if S.rak.di_luar(nomor):
            catat(f"Nomor [{nomor}] di luar rak! Kotak hanya bernomor 0 sampai {S.rak.kapasitas - 1} "
                  "(index out of bounds).", "gagal")
            return None
        p = S.rak.data[nomor]
        if p is None:
            catat(f"Kotak [{nomor}] masih kosong, tidak ada produk yang bisa {kata}.", "gagal")
            return None
        if nama and nama.lower() != p.nama.lower():
            catat(f"Nomor [{nomor}] dan nama tidak cocok, kotak itu berisi '{p.nama}'. Cukup isi nomornya saja (kosongkan kolom Nama).", "gagal")
            return None
        return nomor, True
    if not nama:
        catat("Isi Nomor kotak (cepat, O(1)) atau Nama produk (kotak dicari dulu, O(n)).", "gagal")
        return None
    i = S.rak.cari_indeks(nama)
    if i == -1:
        catat(f"'{nama}' tidak ditemukan.", "gagal")
        return None
    return i, False


# ---------- aksi tombol ----------
def aksi_tambah():
    isi = baca("tambah")
    if not isi:
        return
    if not isi[0]:
        catat("Isi nama produk dulu ya.", "gagal")
        return
    r = S.rak
    i, pesan = r.tambah(Produk(*isi))
    if i < 0 and r.jumlah == r.kapasitas:
        set_konsep(f"ARRAY TIDAK BISA DIBESARKAN: ukuran ditetapkan saat array dibuat (di C: int a[{r.kapasitas}], di Java: "
                   f"new int[{r.kapasitas}]). Untuk ukuran lain, buat array baru lewat Mulai Ulang.")
    else:
        set_konsep("TAMBAH: produk ditaruh di kotak kosong paling kiri tanpa menggeser isi lain (menaruh = O(1)). "
                   "Mencari kotak kosong dan cek nama kembar adalah aturan tambahan aplikasi  ->  O(n)")
    catat(pesan, "ketemu" if i >= 0 else "gagal")
    if i >= 0:
        bersih_isian("tambah")
    kilat([i] if i >= 0 else range(r.kapasitas), "hijau" if i >= 0 else "mawar")


def aksi_sisip():
    isi = baca("sisip")
    if not isi:
        return
    nomor, sah = baca_nomor("sisip")
    if not sah:
        return
    if not isi[0]:
        catat("Isi nama produk dulu ya.", "gagal")
        return
    if nomor is None:
        catat("Sisip butuh nomor kotak tujuan. Isi kolom Nomor tujuan.", "gagal")
        return
    sebelum = S.rak.jumlah
    mulai(S.rak.sisip_langkah(nomor, Produk(*isi)),
          "SISIP: kalau kotak tujuan berisi, isi di kanannya digeser ke kanan satu per satu sampai kotak kosong pertama, "
          "baru kotak tujuan diisi. Makin banyak yang bergeser, makin lama  ->  O(n)",
          selesai=lambda: bersih_isian("sisip") if S.rak.jumlah > sebelum else None)


def aksi_buka(nomor):
    if S.rak.di_luar(nomor):
        S.rumus = f"Nomor [{nomor}] tidak punya alamat di rak ini (hanya 0 sampai {S.rak.kapasitas - 1})"
    else:
        tampil_rumus(nomor)
    mulai(S.rak.buka_langkah(nomor),
          "CARI NOMOR: nomor sudah diketahui, jadi komputer menghitung alamatnya lalu melompat langsung ke sana, "
          "tanpa memeriksa kotak lain  ->  O(1)")


def aksi_cari():
    nomor, sah = baca_nomor("cari")
    if not sah:
        return
    if nomor is not None:
        aksi_buka(nomor)
    elif nama := perlu_nama("cari", "Isi Nomor kotak (cepat) atau ketik nama / sebagian nama yang dicari."):
        mulai(S.rak.cari_langkah(nama),
              "CARI LEWAT NAMA (linear search): kotak diperiksa satu per satu dari nomor 0  ->  O(n). "
              "Isi Nomor kotak agar langsung O(1).")


def aksi_ubah():
    isi = baca("ubah")
    if not isi:
        return
    nama, harga, stok = isi
    baru = S["ubah_baru"].strip()
    if harga is None and stok is None and not baru:
        catat("Isi Nama baru, Harga baru, dan/atau Stok baru.", "gagal")
        return
    hasil = target_kotak("ubah", nama, "diubah")
    if not hasil:
        return
    i, lewat_nomor = hasil
    if baru and S.rak.nama_dipakai(baru, kecuali=i):
        catat(f"Nama '{baru}' sudah dipakai produk di kotak [{S.rak.cari_indeks(baru)}]. Pilih nama lain.", "gagal")
        return
    lama = S.rak.data[i].nama
    S.rak.ubah_indeks(i, harga, stok, baru)
    diubah = ([f"nama '{lama}' menjadi '{baru}'"] if baru else []) + (["harga"] if harga is not None else []) \
        + (["stok"] if stok is not None else [])
    catat(f"Kotak [{i}] diperbarui ({', '.join(diubah)}) lewat "
          f"{'nomor (1 langkah)' if lewat_nomor else 'nama (kotak dicari dulu)'}.", "ketemu")
    set_konsep("UBAH LEWAT NOMOR: kotak langsung diganti isinya, produknya tetap di kotak yang sama  ->  O(1)" if lewat_nomor else
               "UBAH LEWAT NAMA: kotak dicari dulu satu per satu  ->  O(n). Isi Nomor kotak agar langsung O(1).")
    bersih_isian("ubah", ["nama", "baru"])    # nama lama sudah tidak berlaku, nama baru sudah dipakai
    kilat([i], "hijau")


def aksi_hapus():
    hasil = target_kotak("hapus", S["hapus_nama"].strip(), "dihapus")
    if hasil:
        idx, lewat_nomor = hasil
        mulai(S.rak.hapus_indeks_langkah(idx),
              "HAPUS: hanya isi kotak yang dikosongkan, kotaknya tetap ada dan kotak lain tidak bergeser. "
              + ("Lewat nomor langsung  ->  O(1)" if lewat_nomor else "Lewat nama, kotak dicari dulu  ->  O(n)"),
              selesai=lambda: bersih_isian("hapus"))


def aksi_balap():
    if nama := perlu_nama("balap", "Ketik nama produk yang mau dicari (pakai nama yang ada di rak)."):
        mulai(S.rak.balap_langkah(nama),
              "BALAPAN: cari biasa (emas) membuka kotak satu per satu, tebak tengah (ungu) membuka kotak di tengah lalu "
              "mencoret separuh yang pasti salah (hanya bisa karena rak rapat dan urut). Lewat nomor (biru) cuma 1 langkah, "
              "tapi butuh nomor yang sudah diketahui.", True)


def aksi_tampil():
    mulai(S.rak.tampil_langkah(), "TRAVERSAL: membaca semua kotak dari nomor 0 sampai terakhir, kotak kosong dilewati  ->  O(n)")


def aksi_urut(kunci):
    mulai(S.rak.urutkan_langkah(kunci), "BUBBLE SORT: (isi dirapatkan ke kiri bila ada lubang), lalu bandingkan dua kotak "
          "bersebelahan, tukar jika salah urutan, ulangi  ->  O(n^2)")


def aksi_impor(unggahan):
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(unggahan.getvalue())
        path = f.name
    try:
        mulai(S.rak.impor_langkah(path), "IMPOR CSV: isi file dimasukkan ke kotak satu per satu (baris pertama judul: nama,harga,stok; "
              "harga dan stok boleh kosong). Jika kotak habis, sisanya ditolak karena jumlah kotak array tetap.")
    finally:
        os.remove(path)


def ganti_rak(pesan):
    S.rak = Rak(S.rak.kapasitas)
    S.sorot, S.tetap, S.terpilih, S.papan = {}, {}, None, False
    bersih_isian_pilih()
    catat(pesan)


def kosongkan():
    set_konsep("KOSONGKAN: isi semua kotak dibuang, tapi jumlah kotaknya tetap karena ukuran array tidak bisa berubah.")
    ganti_rak("Semua kotak dikosongkan. Jumlah kotak tetap ada, hanya isinya yang dibuang.")


def isi_contoh():
    ganti_rak("Rak diisi data contoh. Kopi Sachet hanya punya nama, dan itu tidak apa-apa.")
    for p in CONTOH[:S.rak.kapasitas]:
        S.rak.tambah(Produk(p.nama, p.harga, p.stok))
    set_konsep("DATA CONTOH: produk masuk satu per satu ke kotak kosong paling kiri.")
    sisa = len(CONTOH) - S.rak.kapasitas
    if sisa > 0:
        catat(f"Data contoh berisi {len(CONTOH)} produk, tapi rak hanya punya {S.rak.kapasitas} kotak. "
              f"{sisa} produk terakhir ditolak karena ukuran array tetap dan tidak bisa ditambah.", "gagal")


def pilih_kotak():
    """Dipanggil saat menu 'Pilih kotak' berubah (menggantikan klik pada kotak di versi tkinter)."""
    v = S.pilih_kotak
    if v == "-":
        S.terpilih = None
        return
    i = int(v)
    S.terpilih = i
    for k in ("sisip", "cari", "ubah", "hapus"):    # nomor terisi otomatis di tab yang memakainya
        S[f"{k}_nomor"] = str(i)
    for k in ("cari", "ubah", "hapus"):             # nama dikosongkan supaya tidak bentrok dengan nomor
        S[f"{k}_nama"] = ""
    S.banner = None
    tampil_rumus(i)
    if S.rak.data[i] is None:
        catat(f"Kotak [{i}] masih kosong (dipesan). Tambah akan mengisi kotak kosong paling kiri "
              f"(kotak [{S.rak.kosong_pertama()}]); Sisip bisa mengisi kotak [{i}] ini lewat nomornya.", tampil=False)
        set_konsep(f"KOTAK KOSONG: kotak [{i}] sudah dipesan sejak array dibuat, hanya belum ada isinya.", tampil=False)
    else:
        set_konsep(f"AKSES LANGSUNG: kotak [{i}] dibuka lewat nomornya tanpa memeriksa kotak lain  ->  O(1). "
                   "Nomor sudah terisi di tab Cari, Ubah, Hapus, dan Sisip.", tampil=False)


# ---------- layar Pesan Memori ----------
def kunci_memori(n):
    S.rak = Rak(n)
    S.sorot, S.tetap, S.terpilih, S.papan, S.banner, S.log = {}, {}, None, False, None, []
    S.rumus = RUMUS_AWAL
    bersih_isian()
    catat(f"Memori dikunci: {n} kotak dipesan, bernomor [0] sampai [{n - 1}]. Ukuran ini tidak bisa diubah lagi.", tampil=False)
    set_konsep(f"MEMORI TERKUNCI: {n} kotak sudah dipesan dan ukurannya tidak bisa diubah. Kotak yang belum terisi "
               "tetap ada ('kosong (dipesan)'). Buka tab Data & File lalu klik Data Contoh untuk mengisinya.", tampil=False)


def mulai_ulang():
    S.v_pesan = S.rak.kapasitas
    S.rak, S.sorot, S.tetap, S.terpilih, S.papan, S.banner = None, {}, {}, None, False, None
    st.rerun()


def set_pesan(n):
    S.v_pesan = n


def layar_pesan():
    st.markdown('<span class="kk-judul">Pesan Memori</span>', unsafe_allow_html=True)
    st.markdown("**Sebelum mulai, kita harus memesan memori dulu.**")
    st.write("Array itu seperti rak loker: jumlah lokernya ditentukan SEKALI di awal dan TIDAK bisa ditambah atau "
             "dikurangi lagi. Pilih berapa kotak yang kamu butuhkan, lalu kunci.")
    st.caption("Setelah dikunci, kamu hanya bisa mengisi, mengubah, dan mengosongkan isi kotak. Mau ukuran lain? Klik Mulai Ulang "
               "untuk memesan array baru (sama seperti membuat array baru di C atau Java).")
    cols = st.columns([1, 1, 1, 4])
    for c, n in zip(cols, (5, 10, 20)):
        c.button(f"{n} kotak", key=f"cepat{n}", on_click=set_pesan, args=(n,), width="stretch")
    n = st.number_input(f"Atau ketik sendiri ({MIN_KOTAK} sampai {MAKS_KOTAK})", MIN_KOTAK, MAKS_KOTAK, step=1, key="v_pesan")
    kotak = "".join(f'<div class="kk-sl"><div class="kk-no">[{i}]</div>'
                    f'<div class="kk-bx kosong">kosong<br>(dipesan)</div></div>' for i in range(n))
    st.markdown(f'<div class="kk-rak"><div class="kk-grid" style="grid-template-columns:'
                f'repeat({min(n, KOLOM)},minmax(0,70px))">{kotak}</div></div>', unsafe_allow_html=True)
    if st.button("🔒 Kunci Memori", type="primary"):
        kunci_memori(int(n))
        st.rerun()


# ---------- layar utama ----------
def header():
    a, b = st.columns([5, 1])
    a.markdown('<span class="kk-judul">KasirKu: Rak Produk</span>', unsafe_allow_html=True)
    if S.rak.jumlah:
        with b.popover("Mulai Ulang", width="stretch"):
            st.write("Semua data di rak akan dibuang dan kamu kembali memesan memori baru (seperti membuat array baru). Lanjutkan?")
            if st.button("Ya, mulai ulang", key="ya_ulang"):
                mulai_ulang()
    elif b.button("Mulai Ulang", width="stretch"):
        mulai_ulang()
    st.markdown(f'<div class="kk-bn info">{esc(PERHATIAN)}</div>', unsafe_allow_html=True)


def isian(kartu, daftar):
    """Deretan kolom isian milik satu tab. Nilainya tersimpan di S[f'{kartu}_{kolom}']."""
    for c, (k, judul, _) in zip(st.columns([lebar for _, _, lebar in daftar]), daftar):
        c.text_input(judul, key=f"{kartu}_{k}")


def kartu_form(kunci, judul, ket, daftar, tombol, aksi, aktif=True, petunjuk=None):
    st.markdown(f"**{judul}**")
    st.caption(ket)
    with st.form(f"f_{kunci}", clear_on_submit=False):
        isian(kunci, daftar)
        kirim = st.form_submit_button(tombol, disabled=not aktif)
    if petunjuk and not aktif:
        st.caption(petunjuk)
    if kirim:
        jalankan_aksi(aksi)


def isi_tab(tabs):
    r = S.rak
    ada = r.jumlah > 0
    bisa_balap = r.jumlah >= 2 and r.rapat() and r.terurut()

    with tabs[0]:
        kartu_form("tambah", "Tambah produk", "Menaruh produk baru di kotak kosong paling kiri. Hanya Nama yang wajib diisi.",
                   [("nama", "Nama produk", 22), ("harga", "Harga (boleh kosong)", 14), ("stok", "Stok (boleh kosong)", 12)],
                   "Tambah", aksi_tambah)
    with tabs[1]:
        kartu_form("sisip", "Sisip di nomor tertentu",
                   "Menaruh produk tepat di nomor kotak pilihanmu. Kalau kotaknya sudah berisi, isi di kanannya digeser ke kanan dulu.",
                   [("nomor", "Nomor tujuan", 8), ("nama", "Nama produk", 16), ("harga", "Harga", 10), ("stok", "Stok", 8)],
                   "Sisip", aksi_sisip)
    with tabs[2]:
        kartu_form("cari", "Cari produk",
                   "Isi Nomor: kotak langsung dibuka (cepat). Kosongkan Nomor dan isi Nama: kotak diperiksa satu per satu "
                   "(lebih lambat). Tip: pilih kotak lewat menu 'Pilih kotak' di bawah rak untuk mengisi Nomor otomatis.",
                   [("nomor", "Nomor kotak", 10), ("nama", "atau Nama (boleh sebagian)", 24)], "Cari", aksi_cari)
    with tabs[3]:
        kartu_form("ubah", "Ubah nama / harga / stok",
                   "Pilih produk lewat Nomor atau Nama lama, lalu isi Nama baru, Harga baru, dan/atau Stok baru. Kolom yang "
                   "kosong tidak diubah (ganti nama saja? cukup isi Nomor dan Nama baru).",
                   [("nomor", "Nomor kotak", 9), ("nama", "atau Nama lama", 13), ("baru", "Nama baru", 16),
                    ("harga", "Harga baru", 11), ("stok", "Stok baru", 9)],
                   "Ubah", aksi_ubah, aktif=ada)
    with tabs[4]:
        kartu_form("hapus", "Kosongkan satu kotak", "Hanya isinya yang dihapus. Kotaknya tetap ada dan kotak lain tidak bergeser.",
                   [("nomor", "Nomor kotak", 10), ("nama", "atau Nama", 24)], "Hapus", aksi_hapus, aktif=ada)
    with tabs[5]:
        st.markdown("**Urutkan & Tampilkan**")
        st.caption("Urutkan: kotak dibandingkan dan ditukar sampai urut (isi dirapatkan ke kiri dulu bila ada lubang). "
                   "Tampilkan: membaca semua kotak satu per satu.")
        c = st.columns(4)
        for kol, (kunci, teks) in zip(c, (("nama", "Urutkan Nama"), ("harga", "Urutkan Harga"), ("stok", "Urutkan Stok"))):
            if kol.button(teks, key=f"urut_{kunci}", disabled=not ada, width="stretch"):
                jalankan_aksi(aksi_urut, kunci)
        if c[3].button("Tampilkan", key="tampil", disabled=not ada, width="stretch"):
            jalankan_aksi(aksi_tampil)
    with tabs[6]:
        kartu_form("balap", "Balapan Cari",
                   "Mengadu cari biasa, tebak tengah, dan lewat nomor. Aktif jika rak tanpa lubang dan sudah urut Nama.",
                   [("nama", "Nama produk (lengkap)", 30)], "Balapan Cari", aksi_balap, aktif=bisa_balap,
                   petunjuk="Belum aktif: butuh minimal 2 produk, tidak ada lubang, dan urut Nama. Klik Urutkan Nama dulu.")
    with tabs[7]:
        st.markdown("**Data & File**")
        st.caption("Mengisi rak dari data contoh atau file CSV supplier, atau membuang semua isinya.")
        a, b, c = st.columns(3)
        if a.button("Data Contoh", key="contoh", width="stretch"):
            jalankan_aksi(isi_contoh)
        with c.popover("Kosongkan Semua", width="stretch", disabled=not ada):
            st.write("Semua isi rak akan dibuang (jumlah kotak tetap). Lanjutkan?")
            if st.button("Ya, kosongkan", key="ya_kosong"):
                jalankan_aksi(kosongkan)
        unggahan = st.file_uploader("File CSV dari supplier (format: nama,harga,stok)", type=["csv"], key="csv_upload")
        d, e = st.columns([1, 1])
        if d.button("Muat CSV", key="muat", disabled=unggahan is None, width="stretch"):
            jalankan_aksi(aksi_impor, unggahan)
        e.download_button("Unduh contoh_supplier.csv", CSV_CONTOH, file_name="contoh_supplier.csv",
                          mime="text/csv", width="stretch")


def tampil_panduan(n):
    with st.expander("📖 Panduan (ditulis untuk pemula)"):
        st.caption("Tidak perlu paham pemrograman dulu. Klik tab di bawah untuk pindah bagian.")
        tabs = st.tabs(["Mulai", "Layar", "Aksi", "Aturan", "Istilah", "Pesan", "Warna"])
        for tab, (judul, warna, isi) in zip(tabs, panduan(n)):
            with tab:
                st.markdown(f'<h4 style="color:{WARNA[warna]}">{esc(judul)}</h4>', unsafe_allow_html=True)
                for sub, uraian in isi:
                    st.markdown(f"**{sub}**")
                    st.markdown(uraian.replace("\n", "\n\n"))
        with tabs[6]:
            st.markdown('<h4 style="color:#d9bd8c">Arti warna</h4>', unsafe_allow_html=True)
            for warna, arti in ARTI_WARNA:
                st.markdown(f'<span style="color:{WARNA[warna]}">■</span> {esc(arti)}', unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="KasirKu - Rak Produk (Array)", page_icon=":material/inventory_2:", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    proses_bersih()
    with st.sidebar:
        with st.container(key="app-sidebar-kasir"):
            sidebar_header("kasir", "KasirKu", "Array · Rak produk", "Amati operasi array melalui simulasi rak produk toko.")
            st.caption("PENGATURAN SIMULASI")
            with st.container(key="sidebar-speed"):
                st.slider("Kecepatan animasi", 1, 10, key="kecepatan",
                          help="Makin ke kanan, makin cepat.")
                st.caption("1 = pelan · 10 = cepat")
            st.caption("Pilih operasi melalui tab di area utama. Ukuran rak ditentukan saat memesan memori.")
    if S.rak is None:
        layar_pesan()
        tampil_panduan(S.v_pesan)
        return
    header()
    PH["rak"] = st.empty()
    st.selectbox("Pilih kotak (mengisi Nomor di tab Sisip, Cari, Ubah, Hapus dan menampilkan alamat memorinya)",
                 ["-"] + list(range(S.rak.kapasitas)), key="pilih_kotak", on_change=pilih_kotak)
    tabs = st.tabs(["Tambah", "Sisip", "Cari", "Ubah", "Hapus", "Urutkan", "Balapan Cari", "Data & File"])
    PH["konsep"] = st.empty()
    st.caption("Catatan langkah (yang terbaru di paling atas)")
    PH["log"] = st.empty()
    gambar()
    render_konsep()
    render_log()
    isi_tab(tabs)
    tampil_panduan(S.rak.kapasitas)


def dalam_streamlit():
    try:
        from streamlit.runtime import exists
        return exists()
    except Exception:
        return False


if dalam_streamlit():
    main()
elif __name__ == "__main__":
    print("Menjalankan uji logika lewat teks. Untuk membuka aplikasi web: streamlit run app_pages/kasir.py\n")
    uji_teks()
