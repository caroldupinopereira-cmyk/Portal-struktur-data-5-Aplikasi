"""AntreanKu: aplikasi Streamlit. Jalankan: python -m streamlit run app_pages/antrean.py"""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from portal.sidebar import sidebar_header, sidebar_menu, sidebar_refresh
from portal.theme import apply_theme
from portal.ui import app_header, empty_state, metric_row, page_header

WIB = timezone(timedelta(hours=7))
BASE_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = Path(os.environ.get('ANTREAN_DB_PATH', BASE_DIR / 'antrean_mahasiswa_streamlit.sqlite3'))
JSON_PATH = Path(os.environ.get('ANTREAN_IMPORT_JSON', BASE_DIR / 'antrean_mahasiswa_data.json'))


def sekarang():
    return datetime.now(WIB)


class AntreanError(ValueError):
    pass


def waktu():
    return sekarang().isoformat(timespec='seconds')


def tiket(m):
    return f"A{m['nomor']:03d}"


class QueueMahasiswa:
    """Queue FIFO: list + indeks depan, tanpa mengurutkan ulang prioritas."""
    def __init__(self):
        self._data = []
        self._depan = 0
        self._nomor_berikutnya = 1

    def isEmpty(self):
        return self._depan == len(self._data)

    def enqueue(self, nama, nim='', layanan='Administrasi Akademik'):
        nama, nim = nama.strip(), nim.strip()
        if not nama:
            raise AntreanError('Nama mahasiswa wajib diisi.')
        if nim and any(m['nim'].casefold() == nim.casefold() for m in self._data[self._depan:]):
            raise AntreanError('NIM tersebut masih berada dalam antrean.')
        m = {'nomor': self._nomor_berikutnya, 'nama': nama, 'nim': nim, 'layanan': layanan,
             'daftar': waktu(), 'mulai': None, 'selesai': None}
        self._data.append(m)
        self._nomor_berikutnya += 1
        return m.copy()

    def dequeue(self):
        if self.isEmpty():
            return None
        m = self._data[self._depan]
        self._data[self._depan] = None
        self._depan += 1
        if self.isEmpty():
            self._data, self._depan = [], 0
        return m.copy()

    def peek(self):
        return None if self.isEmpty() else self._data[self._depan].copy()

    def semua(self):
        return [m.copy() for m in self._data[self._depan:]]

    def jumlah(self):
        return len(self._data) - self._depan


def tampilkan_mahasiswa(m):
    return f"{tiket(m)} — {m['nama']}"


class SistemAntrean:
    LAYANAN = ('Administrasi Akademik', 'Surat Keterangan', 'KRS / KHS', 'Legalisasi Dokumen', 'Informasi Umum')

    def __init__(self, lokasi=None):
        self.lokasi = Path(lokasi) if lokasi is not None else None
        self.antrean = QueueMahasiswa()
        self.sedang = None
        self.riwayat = []
        if self.lokasi is not None and self.lokasi.exists():
            try:
                self.pulihkan(json.loads(self.lokasi.read_text(encoding='utf-8')))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise AntreanError(f'Data tidak dapat dibaca. File tidak dihapus atau ditimpa: {exc}') from exc

    def daftar(self, nama, nim, layanan):
        if not nim.strip():
            raise AntreanError('NIM wajib diisi.')
        if layanan not in self.LAYANAN:
            raise AntreanError('Pilih jenis layanan yang tersedia.')
        if self.sedang and self.sedang['nim'].casefold() == nim.strip().casefold():
            raise AntreanError('Mahasiswa dengan NIM ini sedang dilayani.')
        return self.antrean.enqueue(nama, nim, layanan)

    def panggil(self):
        if self.sedang:
            raise AntreanError('Selesaikan pelayanan saat ini sebelum memanggil berikutnya.')
        m = self.antrean.dequeue()
        if m is None:
            raise AntreanError('Antrean masih kosong.')
        m['mulai'] = waktu()
        self.sedang = m
        return m.copy()

    def selesaikan(self):
        if self.sedang is None:
            raise AntreanError('Tidak ada mahasiswa yang sedang dilayani.')
        m = self.sedang.copy()
        m['selesai'] = waktu()
        self.riwayat.append(m)
        self.sedang = None
        return m.copy()

    def data(self):
        return {'versi': 1, 'nomor_berikutnya': self.antrean._nomor_berikutnya,
                'menunggu': self.antrean.semua(), 'sedang': copy.deepcopy(self.sedang),
                'riwayat': copy.deepcopy(self.riwayat)}

    def pulihkan(self, data):
        if data['versi'] != 1:
            raise AntreanError('Versi data tidak didukung.')
        menunggu, sedang, riwayat = data['menunggu'], data['sedang'], data['riwayat']
        if not isinstance(menunggu,list) or not isinstance(riwayat,list) or (sedang is not None and not isinstance(sedang,dict)):
            raise AntreanError('Format data antrean tidak valid.')
        semua = menunggu + ([sedang] if sedang else []) + riwayat
        nomor = []
        for m in semua:
            if not isinstance(m,dict) or not {'nomor','nama','nim','layanan','daftar','mulai','selesai'} <= set(m):
                raise AntreanError('Data mahasiswa tidak lengkap.')
            if type(m['nomor']) is not int or m['nomor'] < 1 or not isinstance(m['nama'],str) or not m['nama'].strip() or not isinstance(m['nim'],str) or not m['nim'].strip() or m['layanan'] not in self.LAYANAN:
                raise AntreanError('Isi data mahasiswa tidak valid.')
            for key in ('daftar','mulai','selesai'):
                if m[key] is not None: datetime.fromisoformat(m[key])
            if not m['daftar']:
                raise AntreanError('Waktu pendaftaran wajib ada.')
            nomor.append(m['nomor'])
        if len(nomor) != len(set(nomor)):
            raise AntreanError('Nomor antrean ganda.')
        if [m['nomor'] for m in menunggu] != sorted(m['nomor'] for m in menunggu):
            raise AntreanError('Urutan FIFO tersimpan tidak valid.')
        if any(m['mulai'] is not None or m['selesai'] is not None for m in menunggu):
            raise AntreanError('Status antrean menunggu tidak valid.')
        if sedang and (not sedang['mulai'] or sedang['selesai'] is not None):
            raise AntreanError('Status pelayanan tidak valid.')
        if any(not m['mulai'] or not m['selesai'] for m in riwayat):
            raise AntreanError('Status riwayat tidak valid.')
        aktif = menunggu + ([sedang] if sedang else [])
        nim = [m['nim'].casefold() for m in aktif]
        if len(nim) != len(set(nim)):
            raise AntreanError('NIM aktif ganda.')
        berikut = data['nomor_berikutnya']
        if type(berikut) is not int or berikut <= max(nomor,default=0):
            raise AntreanError('Nomor berikutnya tidak valid.')
        q = QueueMahasiswa()
        q._data = copy.deepcopy(menunggu)
        q._nomor_berikutnya = berikut
        self.antrean, self.sedang, self.riwayat = q, copy.deepcopy(sedang), copy.deepcopy(riwayat)


class AntreanStore:
    """Transaksi SQLite menyimpan snapshot queue; logika FIFO tetap di QueueMahasiswa."""
    def __init__(self, lokasi=DB_PATH, sumber=JSON_PATH):
        self.lokasi = Path(lokasi)
        with closing(self.koneksi()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                conn.execute('CREATE TABLE IF NOT EXISTS antrean (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)')
                if conn.execute('SELECT 1 FROM antrean WHERE id=1').fetchone() is None:
                    sistem = SistemAntrean(sumber) if sumber is not None else SistemAntrean()
                    conn.execute('INSERT INTO antrean (id,data) VALUES (1,?)', (json.dumps(sistem.data(),ensure_ascii=False),))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def koneksi(self):
        return sqlite3.connect(self.lokasi,timeout=15)

    def baca(self):
        with closing(self.koneksi()) as conn:
            row=conn.execute('SELECT data FROM antrean WHERE id=1').fetchone()
        if row is None:
            raise AntreanError('Data antrean tidak ditemukan.')
        try:
            sistem=SistemAntrean()
            sistem.pulihkan(json.loads(row[0]))
            return sistem
        except (KeyError,TypeError,ValueError) as exc:
            raise AntreanError(f'Data tersimpan tidak valid: {exc}') from exc

    def ubah(self, aksi, *, nama='', nim='', layanan='', nomor=None):
        with closing(self.koneksi()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                sistem=SistemAntrean()
                row=conn.execute('SELECT data FROM antrean WHERE id=1').fetchone()
                sistem.pulihkan(json.loads(row[0]))
                if aksi=='daftar':
                    hasil=sistem.daftar(nama,nim,layanan)
                elif aksi=='panggil':
                    depan=sistem.antrean.peek()
                    if depan is None or depan['nomor']!=nomor:
                        raise AntreanError('Antrean sudah berubah. Perbarui halaman dan periksa mahasiswa berikutnya.')
                    hasil=sistem.panggil()
                elif aksi=='selesai':
                    if sistem.sedang is None or sistem.sedang['nomor']!=nomor:
                        raise AntreanError('Pelayanan sudah berubah. Perbarui halaman sebelum menyelesaikan.')
                    hasil=sistem.selesaikan()
                else:
                    raise AntreanError('Operasi tidak dikenal.')
                conn.execute('UPDATE antrean SET data=? WHERE id=1',(json.dumps(sistem.data(),ensure_ascii=False),))
                conn.commit()
                return hasil
            except Exception:
                conn.rollback()
                raise


def tabel_antrean(daftar):
    return [{'Urutan':i,'Tiket':tiket(m),'Nama':m['nama'],'NIM':m['nim'],
             'Layanan':m['layanan'],'Waktu daftar':m['daftar'].replace('T',' ')} for i,m in enumerate(daftar,1)]


def csv_riwayat(daftar):
    buffer=io.StringIO(newline='')
    writer=csv.writer(buffer)
    writer.writerow(['Tiket','Nama','NIM','Layanan','Daftar','Mulai','Selesai'])
    for m in daftar:
        values=[tiket(m),m['nama'],m['nim'],m['layanan'],m['daftar'],m['mulai'],m['selesai']]
        writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
    return buffer.getvalue().encode('utf-8-sig')


def proses(store,aksi,**kwargs):
    try:
        hasil=store.ubah(aksi,**kwargs)
    except (AntreanError,sqlite3.Error,OSError,ValueError,KeyError,TypeError) as exc:
        st.session_state['pesan']=('error',str(exc))
        return False
    pesan={'daftar':'Terdaftar','panggil':'Dipanggil','selesai':'Pelayanan selesai'}[aksi]
    st.session_state['pesan']=('success',f'{pesan}: {tampilkan_mahasiswa(hasil)}')
    if aksi=='daftar':
        st.session_state['tiket_terakhir']=hasil
        st.session_state['nama_daftar']=''
        st.session_state['nim_daftar']=''
    return True


def kirim_form(store):
    proses(store,'daftar',nama=st.session_state.get('nama_daftar',''),
           nim=st.session_state.get('nim_daftar',''),layanan=st.session_state.get('layanan_daftar',''))


def pindah_menu(menu):
    st.session_state['menu']=menu


def kartu_mahasiswa(m,label):
    with st.container(border=True):
        st.caption(label)
        if m is None:
            st.subheader('Belum ada mahasiswa')
            return
        st.subheader(tiket(m))
        st.text(m['nama'])
        st.caption(f"NIM {m['nim']} · {m['layanan']}")


def halaman_dashboard(sistem):
    page_header('Pusat pelayanan mahasiswa', 'Satu loket · Semua jenis layanan mengikuti satu antrean FIFO.')
    kiri,kanan=st.columns(2)
    with kiri:kartu_mahasiswa(sistem.antrean.peek(),'BERIKUTNYA DILAYANI')
    with kanan:kartu_mahasiswa(sistem.sedang,'SEDANG DILAYANI')
    with st.container(horizontal=True):
        st.button('Daftar mahasiswa',icon=':material/person_add:',type='primary',
                  on_click=pindah_menu,args=('Pendaftaran',))
        st.button('Buka pelayanan',icon=':material/support_agent:',on_click=pindah_menu,args=('Pelayanan',))
    st.subheader('Antrean terbaru')
    rows=tabel_antrean(sistem.antrean.semua()[:5])
    if rows:st.dataframe(rows,hide_index=True,width='stretch')
    else:empty_state('Belum ada mahasiswa menunggu.', 'Tambahkan melalui menu Pendaftaran.')
    st.caption('Alur: pendaftaran → menunggu → panggil berikutnya → sedang dilayani → selesai.')


def halaman_daftar(sistem,store):
    page_header('Pendaftaran antrean', 'Nomor tiket diterbitkan otomatis. Nama dan NIM wajib diisi.')
    with st.form('form_pendaftaran',border=True):
        st.text_input('Nama mahasiswa',key='nama_daftar',max_chars=150)
        st.text_input('NIM',key='nim_daftar',max_chars=40)
        st.selectbox('Jenis layanan',sistem.LAYANAN,key='layanan_daftar')
        st.form_submit_button('Tambah ke antrean',type='primary',icon=':material/add:',
                              on_click=kirim_form,args=(store,))
    if st.session_state.get('tiket_terakhir'):
        kartu_mahasiswa(st.session_state['tiket_terakhir'],'TIKET TERAKHIR YANG ANDA DAFTARKAN')
    st.caption('NIM yang masih menunggu atau sedang dilayani ditolak. Setelah selesai, mahasiswa boleh mendaftar kembali.')


def halaman_antrean(sistem):
    page_header('Daftar antrean')
    cari=st.text_input('Cari tiket, nama atau NIM',key='pencarian_antrean')
    rows=tabel_antrean(sistem.antrean.semua())
    query=cari.strip().casefold()
    filtered=[r for r in rows if not query or query in f"{r['Tiket']} {r['Nama']} {r['NIM']}".casefold()]
    st.caption(f'{len(filtered)} dari {len(rows)} mahasiswa ditampilkan. Pencarian dan pengurutan tabel tidak mengubah urutan pelayanan.')
    if filtered:st.dataframe(filtered,hide_index=True,width='stretch')
    elif query:empty_state('Tidak ada hasil untuk pencarian ini.')
    else:empty_state('Antrean masih kosong.')
    with st.expander('Lihat antrean terdepan (peek)',expanded=True):
        kartu_mahasiswa(sistem.antrean.peek(),'PEEK: HANYA MEMBACA, TIDAK MENGHAPUS')


def halaman_pelayanan(sistem,store):
    page_header('Loket pelayanan')
    depan=sistem.antrean.peek()
    kiri,kanan=st.columns(2)
    with kiri:
        kartu_mahasiswa(sistem.sedang,'SEDANG DILAYANI')
        if sistem.sedang:st.caption('Mulai: '+sistem.sedang['mulai'].replace('T',' '))
    with kanan:kartu_mahasiswa(depan,'ANTREAN BERIKUTNYA')
    with st.container(horizontal=True):
        st.button('Panggil berikutnya',icon=':material/campaign:',type='primary',
            disabled=depan is None or sistem.sedang is not None,on_click=proses,
            args=(store,'panggil'),kwargs={'nomor':depan['nomor'] if depan else None})
        st.button('Selesaikan pelayanan',icon=':material/check_circle:',disabled=sistem.sedang is None,
            on_click=proses,args=(store,'selesai'),kwargs={'nomor':sistem.sedang['nomor'] if sistem.sedang else None})
    st.caption('Panggil selalu mengambil antrean terdepan. Selesaikan pelayanan sebelum memanggil berikutnya.')


def halaman_riwayat(sistem):
    page_header('Riwayat pelayanan')
    cari=st.text_input('Cari nama, NIM atau tiket',key='pencarian_riwayat')
    query=cari.strip().casefold()
    data=[m for m in reversed(sistem.riwayat) if not query or query in f"{tiket(m)} {m['nama']} {m['nim']}".casefold()]
    rows=[{'Tiket':tiket(m),'Nama':m['nama'],'NIM':m['nim'],'Layanan':m['layanan'],
           'Mulai dilayani':m['mulai'].replace('T',' '),'Selesai':m['selesai'].replace('T',' ')} for m in data]
    if rows:st.dataframe(rows,hide_index=True,width='stretch')
    else:empty_state('Belum ada riwayat yang cocok.')
    st.download_button('Unduh riwayat CSV',data=csv_riwayat(data),file_name='Riwayat_Pelayanan_Mahasiswa.csv',
                       mime='text/csv',icon=':material/download:',disabled=not data,on_click='ignore')
    st.caption(f'{len(data)} pelayanan ditampilkan. Unduhan mengikuti hasil pencarian.')


def halaman_visual(sistem):
    page_header('Visualisasi queue FIFO')
    q=sistem.antrean
    depan=q.peek()
    metric_row([('isEmpty()',str(q.isEmpty())),('jumlah()',q.jumlah()),('peek()',tiket(depan) if depan else 'None')])
    st.caption('Enqueue: masuk dari REAR. Dequeue: keluar dari FRONT. Peek tidak menghapus data.')
    rows=q.semua()
    if not rows:
        empty_state('Queue kosong.', 'Tambahkan mahasiswa di Pendaftaran.', ikon='account_tree')
        return
    halaman_max=max(1,(len(rows)+11)//12)
    if st.session_state.get('halaman_fifo',1)>halaman_max:st.session_state['halaman_fifo']=halaman_max
    nomor=st.number_input('Halaman visualisasi',min_value=1,max_value=halaman_max,value=1,step=1,key='halaman_fifo')
    awal=(nomor-1)*12
    with st.container(horizontal=True):
        for i,m in enumerate(rows[awal:awal+12],awal):
            with st.container(border=True,width=220):
                label='FRONT / REAR' if len(rows)==1 else 'FRONT' if i==0 else 'REAR' if i==len(rows)-1 else f'Urutan {i+1}'
                st.badge(label,color='blue' if i==0 else 'green' if i==len(rows)-1 else 'gray')
                st.subheader(tiket(m))
                st.text(m['nama'])
                st.caption('NIM '+m['nim'])
    st.caption(f'Halaman {nomor}/{halaman_max} · Urutan kiri ke kanan mengikuti pendaftaran.')


def main():
    st.set_page_config(page_title='AntreanKu | Pelayanan mahasiswa',page_icon=':material/groups:',layout='wide')
    apply_theme()
    try:
        store=AntreanStore()
        sistem=store.baca()
    except (AntreanError,sqlite3.Error,OSError,ValueError,KeyError,TypeError) as exc:
        st.error(f'Aplikasi belum dapat membaca data: {exc}')
        st.caption('File sumber dipertahankan. Periksa file JSON sumber dan izin lokasi database sebelum mencoba kembali.')
        st.stop()
    with st.sidebar:
        with st.container(key='app-sidebar-antrean'):
            sidebar_header('antrean', 'AntreanKu', 'Queue · FIFO', 'Kelola antrean dan pelayanan mahasiswa dalam satu loket.')
            menu=sidebar_menu(['Dashboard','Pendaftaran','Daftar antrean','Pelayanan','Riwayat','Visualisasi FIFO'],key='menu',icons={
                'Dashboard':'dashboard','Pendaftaran':'person_add','Daftar antrean':'format_list_numbered',
                'Pelayanan':'support_agent','Riwayat':'history','Visualisasi FIFO':'account_tree'})
            sidebar_refresh('antrean_refresh')
            st.caption('Satu loket · FIFO · Waktu Indonesia Barat')
    app_header('antrean', 'Pelayanan mahasiswa', 'Queue · FIFO',
               'Daftar, pantau antrean, dan selesaikan pelayanan dalam satu tempat.')
    hari=sekarang().date().isoformat()
    metric_row([
        ('Menunggu',sistem.antrean.jumlah()),
        ('Sedang dilayani',1 if sistem.sedang else 0),
        ('Selesai hari ini',sum(m['selesai'][:10]==hari for m in sistem.riwayat)),
        ('Total pendaftaran',sistem.antrean.jumlah()+(1 if sistem.sedang else 0)+len(sistem.riwayat)),
    ])
    if 'pesan' in st.session_state:
        jenis,pesan=st.session_state.pop('pesan')
        if jenis=='success':st.success(pesan)
        else:st.error(pesan)
    if menu=='Dashboard':halaman_dashboard(sistem)
    elif menu=='Pendaftaran':halaman_daftar(sistem,store)
    elif menu=='Daftar antrean':halaman_antrean(sistem)
    elif menu=='Pelayanan':halaman_pelayanan(sistem,store)
    elif menu=='Riwayat':halaman_riwayat(sistem)
    else:halaman_visual(sistem)
    st.caption('Data tersimpan otomatis. Klik Perbarui data untuk membaca perubahan dari tab atau perangkat lain.')


if __name__=='__main__':
    main()
