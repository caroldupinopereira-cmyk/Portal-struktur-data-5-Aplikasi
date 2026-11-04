# Data aplikasi

Folder ini menyimpan database HotelKu dan AntreanKu. Database lama sudah dipindahkan ke sini, sehingga data tetap digunakan.

- `hotelku_streamlit.sqlite3`: kamar, tamu, transaksi, dan aktivitas hotel.
- `antrean_mahasiswa_streamlit.sqlite3`: antrean dan riwayat pelayanan.
- `hotelku_100_kamar.json`: sumber impor awal hotel (opsional).
- `antrean_mahasiswa_data.json`: sumber impor awal antrean (opsional).

Database dibuat otomatis saat aplikasi terkait pertama kali dibuka. JSON hanya dibaca saat database pertama kali diinisialisasi. Jangan menghapus database bila masih membutuhkan datanya.

Lokasi khusus tetap dapat diatur melalui `HOTELKU_DB_PATH`, `HOTELKU_IMPORT_JSON`, `ANTREAN_DB_PATH`, dan `ANTREAN_IMPORT_JSON`. Pastikan folder tujuan sudah tersedia.
