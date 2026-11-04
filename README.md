# Portal Struktur Data

Portal untuk membuka KasirKu (array), daftar tunggu pasien (single linked list), browser stack (LIFO), AntreanKu (FIFO), dan HotelKu (referensi objek).

## Menjalankan

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Pilih **Buka** pada kartu aplikasi. Gunakan **Kembali ke portal** untuk keluar dari aplikasi, atau menu **Aplikasi** di bagian atas untuk langsung berpindah. **Beranda** selalu tersedia pada navigasi utama.

Berpindah halaman dalam sesi yang sama mempertahankan rak produk, daftar pasien, dan stack. Menutup atau memuat ulang sesi dapat menghilangkan data ketiganya; simpan daftar pasien ke Excel/CSV bila diperlukan. Isian formulir dapat kembali ke nilai awal saat berganti halaman.

Hotel dan antrean mahasiswa menyimpan data otomatis ke file SQLite di `data/`. Riwayat Chrome hanya dapat dibaca dari profil Chrome lokal pada komputer yang menjalankan Streamlit.

## Struktur folder

```text
app.py                  # Titik masuk dan navigasi
portal/
    __init__.py
    catalog.py          # Daftar dan keterangan aplikasi
    home.py             # Kartu pilihan di beranda
    icons.py            # Ikon SVG yang disematkan sebagai gambar lokal
    theme.py            # Pemuat CSS
    templates/          # HTML judul, kartu, dan footer
assets/                 # Token Kumo dan CSS portal
.streamlit/config.toml  # Tema kontrol Streamlit
app_pages/
    kasir.py            # Array rak produk
    pasien.py           # Single linked list pasien
    browser_stack.py    # Stack riwayat browser
    antrean.py          # Queue pelayanan mahasiswa
    hotel.py            # Hotel dan referensi objek
data/
    README.md           # Keterangan penyimpanan
    *.sqlite3           # Database aktif (tidak masuk Git)
requirements.txt
.gitignore
README.md
```

Jalankan perintah dari folder utama proyek. `app.py` hanya mendaftarkan halaman; kode aplikasi dijalankan ketika halamannya dipilih. Beranda tidak membaca database hotel/antrean atau mengimpor pandas dan openpyxl. Tidak diperlukan lima proses Streamlit terpisah.

Logika masing-masing aplikasi tetap berada di file halamannya agar mudah ditelusuri untuk tugas kuliah. Pindah folder tidak dengan sendirinya mempercepat algoritma di dalam aplikasi.

## Tampilan

- `assets/kumo-tokens.css`: token desain Kumo/OpenDesign yang diberikan sebagai referensi, termasuk atribusi sumber.
- `assets/portal.css`: gaya kartu, tombol, tipografi, dan penyesuaian layar kecil pada portal.
- `portal/theme.py`: memuat CSS lokal dengan cache. Token CSS mengikuti color-scheme Streamlit agar pergantian tema langsung berlaku.
- `portal/templates/`: HTML untuk judul, isi kartu aplikasi, dan footer halaman utama.
- `portal/icons.py`: ikon SVG lokal untuk kartu HTML; ikon navigasi tetap memakai Material Symbols.
- `portal/sidebar.py` dan `assets/sidebar.css`: identitas, navigasi, dan kontrol sidebar bersama untuk KasirKu, AntreanKu, serta HotelKu. Menu tetap menggunakan kontrol Streamlit yang bisa diakses dengan keyboard.
- `.streamlit/config.toml`: tema kontrol bawaan untuk mode terang dan gelap.

CSS kartu dibatasi ke portal. Visualisasi di aplikasi tetap memiliki warna untuk menjelaskan operasi struktur data. Font memakai Inter jika tersedia di perangkat, dengan fallback font sistem; tidak ada unduhan font atau framework CSS eksternal.

Tombol **Siang** dan **Malam** tampil di atas halaman portal dan kelima aplikasi. Keduanya memakai pemilih tema asli Streamlit, sehingga tabel dan formulir ikut berubah tanpa memuat ulang sesi. `portal/appearance.py`, `portal/templates/theme-switcher.html`, dan `assets/theme-switcher.js` menyediakan pintasan ini. JavaScript hanya menjalankan kode lokal tepercaya; integrasi menargetkan kontrol tema Streamlit 1.58 dan perlu diperiksa kembali setelah peningkatan versi Streamlit. Menu tiga titik tetap dapat dipakai sebagai alternatif.
