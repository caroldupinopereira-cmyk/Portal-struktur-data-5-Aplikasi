"""HotelKu Kelompok 8 — jalankan: python -m streamlit run app_pages/hotel.py"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from contextlib import closing
import io
import sqlite3
import hashlib

import streamlit as st
from portal.sidebar import sidebar_header, sidebar_menu, sidebar_refresh

WIB = timezone(timedelta(hours=7))
BASE_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = Path(os.environ.get("HOTELKU_DB_PATH", BASE_DIR / "hotelku_streamlit.sqlite3"))
JSON_PATH = Path(os.environ.get("HOTELKU_IMPORT_JSON", BASE_DIR / "hotelku_100_kamar.json"))


class HotelError(ValueError):
    pass


def tanggal(teks):
    try:
        return date.fromisoformat(teks)
    except (ValueError, TypeError):
        raise HotelError('Tanggal harus valid: YYYY-MM-DD.') from None


def rupiah(angka):
    return 'Rp ' + f'{angka:,}'.replace(',', '.')


@dataclass
class Tamu:
    id: str
    nama: str
    telepon: str


@dataclass
class Menginap:
    id: str
    tamu: Tamu
    masuk: str
    rencana_keluar: str
    segmen: list
    layanan: list = field(default_factory=list)
    jumlah_orang: int = 1
    kode_import: str = ''


@dataclass
class Kamar:
    nomor: int
    lantai: int
    tipe: str
    harga: int
    status: str = 'Kosong'
    penghuni: Menginap | None = field(default=None, repr=False)

    @property
    def kapasitas(self):
        urutan = self.nomor % 100
        return 1 if urutan <= 4 else 2 if urutan <= 7 else 4



class Hotel:
    def __init__(self, lokasi=None):
        self.lokasi = Path(lokasi) if lokasi is not None else None
        self.kamar = {}
        for lantai in range(1, 11):
            tipe, harga = ('Standard', 250000) if lantai <= 5 else ('Deluxe', 400000) if lantai <= 8 else ('Suite', 650000)
            for urutan in range(1, 11):
                nomor = lantai * 100 + urutan
                self.kamar[nomor] = Kamar(nomor, lantai, tipe, harga)
        self.aktif, self.transaksi, self.riwayat = {}, [], []
        if self.lokasi is not None and self.lokasi.exists():
            try:
                self.pulihkan(json.loads(self.lokasi.read_text(encoding='utf-8')))
            except (OSError,ValueError,KeyError,TypeError) as exc:
                raise HotelError(f'Data sumber tidak dapat dibaca; file tidak diubah: {exc}') from exc

    def kamar_di(self, nomor, berisi=False):
        try:
            kamar = self.kamar[int(nomor)]
        except (KeyError, ValueError, TypeError):
            raise HotelError('Pilih nomor kamar yang valid.') from None
        if berisi and kamar.penghuni is None:
            raise HotelError('Kamar ini tidak memiliki tamu menginap.')
        return kamar

    def catat(self, aksi, detail):
        self.riwayat.append({'waktu': datetime.now(WIB).isoformat(timespec='seconds'), 'aksi': aksi, 'detail': detail})

    def checkin(self, nomor, nama, telepon, masuk, keluar, jumlah_orang=1):
        kamar = self.kamar_di(nomor)
        try:
            jumlah_orang = int(jumlah_orang)
        except (ValueError, TypeError):
            raise HotelError('Jumlah orang harus bilangan bulat.') from None
        if not 1 <= jumlah_orang <= kamar.kapasitas:
            raise HotelError(f'Kamar {kamar.nomor} hanya untuk 1 sampai {kamar.kapasitas} orang.')
        nama, telepon = nama.strip(), telepon.strip()
        if not nama or not telepon:
            raise HotelError('Nama dan telepon wajib diisi.')
        if not telepon.replace('+', '', 1).replace(' ', '').replace('-', '').isdigit():
            raise HotelError('Nomor telepon tidak valid.')
        if tanggal(keluar) <= tanggal(masuk):
            raise HotelError('Rencana keluar minimal satu hari setelah masuk.')
        if kamar.status != 'Kosong' or kamar.penghuni:
            raise HotelError('Kamar belum siap digunakan.')
        inap = Menginap(uuid.uuid4().hex, Tamu(uuid.uuid4().hex, nama, telepon), masuk, keluar,
                         [{'kamar': kamar.nomor, 'mulai': masuk, 'akhir': None, 'harga': kamar.harga}])
        inap.jumlah_orang = jumlah_orang
        self.aktif[inap.id] = inap
        kamar.penghuni, kamar.status = inap, 'Terisi'
        self.catat('Check-in', f'{nama} | {jumlah_orang} orang | kamar {kamar.nomor} | {masuk}')
        return inap

    def pindah(self, asal, tujuan, saat):
        lama, baru = self.kamar_di(asal, True), self.kamar_di(tujuan)
        if baru.status != 'Kosong' or baru.penghuni:
            raise HotelError('Kamar tujuan harus kosong dan siap digunakan.')
        inap = lama.penghuni
        if inap.jumlah_orang > baru.kapasitas:
            raise HotelError(f'Kamar tujuan hanya muat {baru.kapasitas} orang; rombongan berisi {inap.jumlah_orang} orang.')
        if tanggal(saat) < tanggal(inap.segmen[-1]['mulai']):
            raise HotelError('Tanggal pindah mendahului segmen kamar terakhir.')
        inap.segmen[-1]['akhir'] = saat
        inap.segmen.append({'kamar': baru.nomor, 'mulai': saat, 'akhir': None, 'harga': baru.harga})
        baru.penghuni, baru.status = inap, 'Terisi'
        lama.penghuni, lama.status = None, 'Dibersihkan'
        self.catat('Pindah kamar', f'{inap.tamu.nama} | {lama.nomor} -> {baru.nomor} | {saat}')

    def layanan(self, nomor, nama, harga, jumlah):
        inap = self.kamar_di(nomor, True).penghuni
        try:
            harga, jumlah = int(harga), int(jumlah)
        except (ValueError, TypeError):
            raise HotelError('Harga dan jumlah harus bilangan bulat.') from None
        if not nama.strip() or harga <= 0 or jumlah <= 0:
            raise HotelError('Isi nama layanan, harga dan jumlah positif.')
        inap.layanan.append({'nama': nama.strip(), 'harga': harga, 'jumlah': jumlah})
        self.catat('Layanan', f'{inap.tamu.nama} | {nama.strip()} x{jumlah} | {rupiah(harga * jumlah)}')

    def tagihan(self, nomor, keluar):
        inap = self.kamar_di(nomor, True).penghuni
        akhir = tanggal(keluar)
        if akhir <= tanggal(inap.masuk) or akhir < tanggal(inap.segmen[-1]['mulai']):
            raise HotelError('Check-out minimal sehari setelah check-in dan tidak sebelum pindah terakhir.')
        segmen = []
        for s in inap.segmen:
            selesai = s['akhir'] or keluar
            malam = (tanggal(selesai) - tanggal(s['mulai'])).days
            segmen.append({**s, 'akhir': selesai, 'malam': malam, 'subtotal': malam * s['harga']})
        kamar = sum(s['subtotal'] for s in segmen)
        layanan = sum(s['harga'] * s['jumlah'] for s in inap.layanan)
        return {'id': inap.id, 'tamu': asdict(inap.tamu), 'masuk': inap.masuk, 'keluar': keluar,
                'segmen': segmen, 'layanan': [dict(s) for s in inap.layanan],
                'biaya_kamar': kamar, 'biaya_layanan': layanan, 'total': kamar + layanan, 'jumlah_orang': inap.jumlah_orang, 'kode_import': inap.kode_import}

    def checkout(self, nomor, keluar, bayar):
        data = self.tagihan(nomor, keluar)
        try:
            bayar = int(bayar)
        except (ValueError, TypeError):
            raise HotelError('Pembayaran harus bilangan bulat rupiah.') from None
        if bayar < data['total']:
            raise HotelError('Pembayaran belum mencukupi total tagihan.')
        kamar = self.kamar_di(nomor, True)
        data.update(bayar=bayar, kembalian=bayar - data['total'])
        del self.aktif[kamar.penghuni.id]
        kamar.penghuni, kamar.status = None, 'Dibersihkan'
        self.transaksi.append(data)
        self.catat('Check-out', f"{data['tamu']['nama']} | {rupiah(data['total'])}")
        return data

    def ubah_status(self, nomor, status):
        k = self.kamar_di(nomor)
        if k.penghuni:
            raise HotelError('Kamar terisi harus melalui proses pindah kamar atau check-out.')
        if status not in ('Kosong', 'Dibersihkan', 'Perawatan'):
            raise HotelError('Status tidak valid.')
        k.status = status
        self.catat('Status kamar', f'{k.nomor} | {status}')

    def rencana_impor(self, baris):
        if not baris or len(baris)>100:
            raise HotelError('Impor harus berisi 1–100 rombongan.')
        terpakai={i.kode_import for i in self.aktif.values() if i.kode_import}
        terpakai.update(t.get('kode_import','') for t in self.transaksi if t.get('kode_import'))
        seen=set()
        kandidat={}
        errors=[]
        for i,r in enumerate(baris):
            kode=r['kode_import']
            if kode in seen or kode in terpakai:
                errors.append(f"Baris {r['baris']}: kode_import {kode} sudah digunakan.")
            seen.add(kode)
            pilihan=[k for k in self.kamar.values() if k.status=='Kosong' and k.penghuni is None
                and k.kapasitas>=r['jumlah_orang']
                and (r['lantai'] is None or k.lantai==r['lantai'])
                and (not r['tipe_kamar'] or k.tipe==r['tipe_kamar'])
                and (r['nomor_kamar'] is None or k.nomor==r['nomor_kamar'])]
            kandidat[i]=[k.nomor for k in sorted(pilihan,key=lambda k:(k.kapasitas,k.harga,k.nomor))]
            if not pilihan:errors.append(f"Baris {r['baris']}: tidak ada kamar kosong sesuai jumlah orang/lantai/tipe/nomor.")
        if errors:raise HotelError('\n'.join(errors))
        # Pencocokan bipartit: pilihan fleksibel dapat dialihkan agar syarat baris lain terpenuhi.
        pemilik={}
        def pasang(i,dikunjungi):
            for nomor in kandidat[i]:
                if nomor in dikunjungi:continue
                dikunjungi.add(nomor)
                if nomor not in pemilik or pasang(pemilik[nomor],dikunjungi):
                    pemilik[nomor]=i
                    return True
            return False
        for i in sorted(kandidat,key=lambda i:(len(kandidat[i]),-baris[i]['jumlah_orang'],baris[i]['baris'])):
            if not pasang(i,set()):
                raise HotelError(f"Kamar tidak cukup untuk seluruh baris, termasuk baris {baris[i]['baris']}. Ubah syarat pilihan atau kurangi rombongan. Tidak ada check-in disimpan.")
        penempatan={i:n for n,i in pemilik.items()}
        return [{**r,'kamar_dibagi':penempatan[i]} for i,r in enumerate(baris)]

    def terapkan_impor(self, baris, rencana):
        terbaru=self.rencana_impor(baris)
        if terbaru!=rencana:
            raise HotelError('Ketersediaan kamar berubah. Buka ulang file untuk melihat pratinjau terbaru.')
        sebelum=json.loads(json.dumps(self.data()))
        try:
            for r in terbaru:
                inap=self.checkin(r['kamar_dibagi'],r['nama'],r['telepon'],r['tanggal_masuk'],r['tanggal_keluar'],r['jumlah_orang'])
                inap.kode_import=r['kode_import']
            self.catat('Impor Excel',f'{len(terbaru)} check-in | {sum(r["jumlah_orang"] for r in terbaru)} orang')
        except Exception:
            self.pulihkan(sebelum)
            raise
        return len(terbaru)


    def data(self):
        return {'versi': 1, 'kamar': [{'nomor': k.nomor, 'status': k.status,
            'penghuni': k.penghuni.id if k.penghuni else None} for k in self.kamar.values()],
            'aktif': [asdict(x) for x in self.aktif.values()], 'transaksi': self.transaksi, 'riwayat': self.riwayat}

    def pulihkan(self, data):
        if data['versi'] != 1:
            raise HotelError('Versi penyimpanan tidak didukung.')
        aktif = {}
        for item in data['aktif']:
            item = dict(item)
            item['tamu'] = Tamu(**item['tamu'])
            inap = Menginap(**item)
            tanggal(inap.masuk)
            tanggal(inap.rencana_keluar)
            if not inap.segmen:
                raise HotelError('Segmen menginap kosong.')
            aktif[inap.id] = inap
        nomor = [item['nomor'] for item in data['kamar']]
        if len(nomor) != 100 or set(nomor) != set(self.kamar):
            raise HotelError('Data harus berisi 100 kamar di 10 lantai.')
        referensi = []
        for item in data['kamar']:
            penghuni = item['penghuni']
            if item['status'] not in ('Kosong', 'Terisi', 'Dibersihkan', 'Perawatan'):
                raise HotelError('Status tersimpan tidak valid.')
            if (item['status'] == 'Terisi') != (penghuni is not None):
                raise HotelError('Status dan referensi penghuni tidak sesuai.')
            if penghuni is not None:
                if penghuni not in aktif or aktif[penghuni].segmen[-1]['kamar'] != item['nomor']:
                    raise HotelError('Referensi kamar menginap tidak sesuai.')
                if not 1 <= aktif[penghuni].jumlah_orang <= self.kamar[item['nomor']].kapasitas:
                    raise HotelError('Jumlah tamu tersimpan melebihi kapasitas kamar.')
                referensi.append(penghuni)
        if len(referensi) != len(set(referensi)) or set(referensi) != set(aktif):
            raise HotelError('Referensi menginap ganda atau hilang.')
        for item in data['kamar']:
            k = self.kamar[item['nomor']]
            k.status = item['status']
            k.penghuni = aktif[item['penghuni']] if item['penghuni'] is not None else None
        self.aktif, self.transaksi, self.riwayat = aktif, data['transaksi'], data['riwayat']


def struk(data):
    baris = ['HOTELKU | 10 LANTAI - 100 KAMAR', '=' * 60, f"ID: {data['id']}",
             f"Tamu: {data['tamu']['nama']} | {data['tamu']['telepon']}",
             f"Menginap: {data['masuk']} s.d. {data['keluar']}", f"Jumlah tamu: {data.get('jumlah_orang', 1)} orang", '', 'KAMAR']
    for s in data['segmen']:
        baris += [f"{s['kamar']} | {s['mulai']} - {s['akhir']}",
                  f"  {s['malam']} malam x {rupiah(s['harga'])} = {rupiah(s['subtotal'])}"]
    baris += ['', 'LAYANAN']
    baris += [f"{s['nama']} x{s['jumlah']} = {rupiah(s['harga'] * s['jumlah'])}" for s in data['layanan']] or ['-']
    baris += ['', 'TOTAL: ' + rupiah(data['total'])]
    if 'bayar' in data:
        baris += ['Bayar: ' + rupiah(data['bayar']), 'Kembalian: ' + rupiah(data['kembalian'])]
    return '\n'.join(baris)


# Dukungan Excel dibaca saat fitur dipakai agar aplikasi utama tetap bisa dibuka tanpa openpyxl.
KOLOM_IMPOR = ['kode_import', 'nama', 'telepon', 'jumlah_orang', 'tanggal_masuk',
               'tanggal_keluar', 'lantai', 'tipe_kamar', 'nomor_kamar']
ATURAN_IMPOR = '''ATURAN IMPOR CHECK-IN EXCEL (.xlsx)

1. Gunakan template dari tombol Simpan Template. Sheet wajib bernama CheckIn.
2. Baris 1 berisi judul kolom persis seperti template. Jangan gabungkan sel atau gunakan formula.
3. Satu baris = satu rombongan dalam satu kamar. Nama adalah penanggung jawab.
4. Wajib: kode_import unik, nama, telepon (format Teks), jumlah_orang (1–4), tanggal_masuk, tanggal_keluar.
5. Tanggal berupa YYYY-MM-DD atau sel tanggal Excel. Keluar harus setelah masuk.
6. Opsional: lantai 1–10, tipe_kamar Standard/Deluxe/Suite, nomor_kamar. Kosong berarti bebas.
7. Nomor kamar yang diisi wajib memenuhi lantai, tipe, kapasitas dan status kosong.
8. Sistem membagi kamar KOSONG saat ini; bukan reservasi atau penjadwalan pemakaian kamar mendatang.
9. Satu kamar tidak dibagi dengan rombongan lain. Maksimal 100 baris data per impor.
10. kode_import tidak boleh sama dengan baris lain, check-in aktif, atau transaksi terdahulu.
11. Kapasitas per lantai: urutan 01–04 = 1 orang, 05–07 = 2 orang, 08–10 = 4 orang.
12. Seluruh baris harus valid dan mendapat kamar. Jika tidak, tidak ada check-in yang disimpan.
13. Periksa pratinjau pembagian, lalu klik Simpan Semua Check-in. Membuka file belum mengubah data hotel.

Nomor telepon wajib disimpan sebagai teks agar angka nol di depan tidak hilang.
Tarif mengikuti tipe kamar, per kamar per malam. Pilihan spesifik adalah syarat wajib, bukan sekadar saran.
'''


def pustaka_excel():
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        raise HotelError('Fitur Excel memerlukan openpyxl. Jalankan %pip install openpyxl pada sel notebook terpisah, lalu coba lagi.') from None


def tulis_teks(cell, nilai):
    cell.value = nilai
    if isinstance(nilai, str):
        cell.data_type = 's'  # nama/keterangan pengguna tetap teks, bukan formula Excel


def rapikan_excel(ws, lebar=None):
    from openpyxl.styles import Font, PatternFill, Alignment
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    for cell in ws[1]:
        cell.fill = PatternFill('solid', fgColor='17324D')
        cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        cell.alignment = Alignment(vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 32
    for kolom in ws.columns:
        letter = kolom[0].column_letter
        ws.column_dimensions[letter].width = (lebar or {}).get(letter, min(42, max(14, max(len(str(c.value or '')) for c in kolom) + 2)))
        for cell in kolom[1:]:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            cell.font = Font(name='Calibri', size=11, color='17324D')
            if cell.row % 2 == 0:
                cell.fill = PatternFill('solid', fgColor='F0F5FA')
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = '1:1'


def simpan_workbook(wb, lokasi):
    # File Excel dibuat di memori untuk unggahan/unduhan Streamlit.
    try:
        wb.save(lokasi)
    finally:
        wb.close()



def template_excel(lokasi):
    x = pustaka_excel()
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = x.Workbook()
    ws = wb.active
    ws.title = 'CheckIn'
    ws.append(KOLOM_IMPOR)
    for baris in range(2, 102):
        for kolom in ('A', 'B', 'C', 'E', 'F'):
            ws[f'{kolom}{baris}'].number_format = '@'
    for jenis,formula1,formula2,area in [('whole','1','4','D2:D101'), ('whole','1','10','G2:G101')]:
        dv = DataValidation(type=jenis,operator='between',formula1=formula1,formula2=formula2,allow_blank=True)
        dv.errorTitle = 'Periksa nilai'
        dv.error = 'Isi bilangan bulat sesuai batas pada petunjuk.'
        dv.showErrorMessage = True
        ws.add_data_validation(dv)
        dv.add(area)
    dv = DataValidation(type='list',formula1='"Standard,Deluxe,Suite"',allow_blank=True)
    dv.showErrorMessage = True
    ws.add_data_validation(dv)
    dv.add('H2:H101')
    rapikan_excel(ws, {'A':24,'B':28,'C':24,'D':18,'E':22,'F':22,'G':14,'H':20,'I':18})
    ws.auto_filter.ref = 'A1:I101'
    petunjuk = wb.create_sheet('Petunjuk')
    petunjuk.append(['Aturan / Contoh'])
    for baris in ATURAN_IMPOR.splitlines():
        petunjuk.append([baris])
    petunjuk.append(['Contoh (jangan salin baris ini sebagai judul kolom):'])
    petunjuk.append(['ROMB-001 | Budi | 08123456789 | 4 | 2026-11-04 | 2026-11-06 | 1 | Standard | 108'])
    petunjuk.append(['Kosongkan 3 kolom terakhir jika sistem bebas memilih kamar.'])
    rapikan_excel(petunjuk, {'A':110})
    for row in range(2,petunjuk.max_row+1): petunjuk.row_dimensions[row].height=36
    simpan_workbook(wb,lokasi)


def baca_excel(lokasi):
    nama = str(lokasi) if isinstance(lokasi,(str,Path)) else getattr(lokasi,'name','data.xlsx')
    if Path(nama).suffix.lower() != '.xlsx':
        raise HotelError('Gunakan file .xlsx sesuai template; .xls dan .xlsm tidak didukung.')
    x = pustaka_excel()
    try:
        wb = x.load_workbook(lokasi, read_only=False, data_only=False)
    except Exception as exc:
        raise HotelError(f'File Excel tidak dapat dibuka: {exc}') from exc
    try:
        if 'CheckIn' not in wb.sheetnames:
            raise HotelError('Sheet CheckIn tidak ditemukan. Gunakan template sistem.')
        ws = wb['CheckIn']
        if ws.merged_cells.ranges:
            raise HotelError('Sheet CheckIn tidak boleh menggunakan sel gabungan (merge).')
        if ws.max_row > 1001 or ws.max_column > 30:
            raise HotelError('Ukuran sheet melebihi batas. Gunakan template dengan maksimal 100 baris data.')
        iterator = ws.iter_rows()
        header_cells = next(iterator, ())
        header = [str(c.value).strip() if c.value is not None else '' for c in header_cells]
        while header and not header[-1]: header.pop()
        if header != KOLOM_IMPOR:
            raise HotelError('Judul/urutan kolom tidak sesuai template. Wajib: ' + ', '.join(KOLOM_IMPOR))
        hasil,errors,kode = [],[],set()
        def bilangan(value,label,minimum,maximum):
            if isinstance(value,bool): raise HotelError(label+' harus bilangan bulat.')
            try:
                angka = int(str(value).strip())
            except (ValueError,TypeError):
                if isinstance(value,float) and value.is_integer(): angka=int(value)
                else: raise HotelError(label+' harus bilangan bulat.') from None
            if not minimum <= angka <= maximum: raise HotelError(f'{label} harus {minimum}–{maximum}.')
            return angka
        def hari(value):
            if isinstance(value,datetime): return value.date().isoformat()
            if isinstance(value,date): return value.isoformat()
            value=str(value or '').strip()
            tanggal(value)
            return value
        for nomor,cells in enumerate(iterator,2):
            if all(c.value is None or c.value=='' for c in cells): continue
            try:
                if any(c.value not in (None,'') for c in cells[9:]): raise HotelError('Isi kolom di luar template tidak diperbolehkan.')
                if any(c.data_type=='f' for c in cells): raise HotelError('Formula tidak diperbolehkan.')
                vals=[c.value for c in cells[:9]]+[None]*max(0,9-len(cells))
                raw=dict(zip(KOLOM_IMPOR,vals))
                identitas=raw['kode_import']
                if not isinstance(identitas,str) or not identitas.strip(): raise HotelError('kode_import wajib berupa teks unik.')
                identitas=identitas.strip().casefold()
                if identitas in kode: raise HotelError('kode_import duplikat di file ini.')
                kode.add(identitas)
                if not isinstance(raw['nama'],str) or not raw['nama'].strip(): raise HotelError('nama wajib diisi teks.')
                if not isinstance(raw['telepon'],str): raise HotelError('telepon wajib berformat Teks, bukan angka Excel.')
                telepon=raw['telepon'].strip()
                if not telepon or not telepon.replace('+','',1).replace(' ','').replace('-','').isdigit(): raise HotelError('telepon tidak valid.')
                orang=bilangan(raw['jumlah_orang'],'jumlah_orang',1,4)
                masuk,keluar=hari(raw['tanggal_masuk']),hari(raw['tanggal_keluar'])
                if tanggal(keluar)<=tanggal(masuk): raise HotelError('tanggal_keluar harus setelah tanggal_masuk.')
                lantai=None if raw['lantai'] in (None,'') else bilangan(raw['lantai'],'lantai',1,10)
                tipe=str(raw['tipe_kamar'] or '').strip().title()
                if tipe not in ('','Standard','Deluxe','Suite'): raise HotelError('tipe_kamar harus Standard, Deluxe, atau Suite.')
                kamar=None if raw['nomor_kamar'] in (None,'') else bilangan(raw['nomor_kamar'],'nomor_kamar',101,1010)
                hasil.append({'baris':nomor,'kode_import':identitas,'nama':raw['nama'].strip(),'telepon':telepon,
                    'jumlah_orang':orang,'tanggal_masuk':masuk,'tanggal_keluar':keluar,'lantai':lantai,'tipe_kamar':tipe,'nomor_kamar':kamar})
            except HotelError as exc: errors.append(f'Baris {nomor}: {exc}')
        if len(hasil)>100: errors.append('Maksimal 100 rombongan per impor.')
        if errors: raise HotelError('\n'.join(errors))
        if not hasil: raise HotelError('Sheet CheckIn tidak memiliki baris data.')
        return hasil
    finally:
        wb.close()


def ekspor_laporan(hotel,lokasi,mulai,akhir):
    awal,selesai=tanggal(mulai),tanggal(akhir)
    if selesai<awal: raise HotelError('Akhir periode harus sama atau setelah awal periode.')
    x=pustaka_excel()
    wb=x.Workbook()
    wb.remove(wb.active)
    def sheet(nama,headers,rows,mata_uang=(),tanggal_cols=()):
        ws=wb.create_sheet(nama)
        ws.append(headers)
        for row in rows:
            for col,value in enumerate(row,1):
                cell=ws.cell(ws.max_row+1,col) if col==1 else ws.cell(ws.max_row,col)
                if col in tanggal_cols and value: value=tanggal(value)
                tulis_teks(cell,value)
                if col in mata_uang:cell.number_format='"Rp" #,##0'
                if col in tanggal_cols:cell.number_format='yyyy-mm-dd'
        rapikan_excel(ws)
        return ws
    transaksi=[t for t in hotel.transaksi if awal<=tanggal(t['keluar'])<=selesai]
    sekarang=datetime.now(WIB).isoformat(timespec='seconds')
    hitung=lambda s:sum(k.status==s for k in hotel.kamar.values())
    summary=[['Diekspor pada',sekarang],['Periode transaksi check-out',mulai+' s.d. '+akhir],
        ['Catatan','Kamar dan tamu aktif adalah snapshot saat ekspor, tidak difilter periode.'],
        ['Total kamar',100],['Kapasitas gedung (orang)',sum(k.kapasitas for k in hotel.kamar.values())],
        ['Kamar kosong saat ekspor',hitung('Kosong')],['Kamar terisi saat ekspor',hitung('Terisi')],
        ['Kamar dibersihkan saat ekspor',hitung('Dibersihkan')],['Kamar perawatan saat ekspor',hitung('Perawatan')],
        ['Tamu aktif saat ekspor (orang)',sum(i.jumlah_orang for i in hotel.aktif.values())],
        ['Transaksi selesai dalam periode',len(transaksi)],
        ['Tamu check-out dalam periode (orang)',sum(t.get('jumlah_orang',1) for t in transaksi)],
        ['Pendapatan kamar dalam periode',sum(t['biaya_kamar'] for t in transaksi)],
        ['Pendapatan layanan dalam periode',sum(t['biaya_layanan'] for t in transaksi)],
        ['Total pendapatan dalam periode',sum(t['total'] for t in transaksi)]]
    ws=sheet('Ringkasan',['Indikator','Nilai'],summary)
    ws.column_dimensions['A'].width=44;ws.column_dimensions['B'].width=95
    for row in range(14,17):ws.cell(row,2).number_format='"Rp" #,##0'
    sheet('Kamar Saat Ekspor',['Lantai','Kamar','Tipe','Kapasitas','Harga per malam','Status','Penanggung jawab','Orang'],
        [(k.lantai,k.nomor,k.tipe,k.kapasitas,k.harga,k.status,k.penghuni.tamu.nama if k.penghuni else '',k.penghuni.jumlah_orang if k.penghuni else 0)
         for k in hotel.kamar.values()],mata_uang=(5,))
    sheet('Tamu Aktif',['ID menginap','Kamar','Lantai','Nama','Telepon','Orang','Masuk','Rencana keluar','Kode impor'],
        [(k.penghuni.id,k.nomor,k.lantai,k.penghuni.tamu.nama,k.penghuni.tamu.telepon,k.penghuni.jumlah_orang,
          k.penghuni.masuk,k.penghuni.rencana_keluar,k.penghuni.kode_import) for k in hotel.kamar.values() if k.penghuni],tanggal_cols=(7,8))
    sheet('Transaksi Periode',['ID transaksi','Nama','Telepon','Orang','Masuk','Keluar','Biaya kamar','Biaya layanan','Total','Bayar','Kembalian','Kode impor'],
        [(t['id'],t['tamu']['nama'],t['tamu']['telepon'],t.get('jumlah_orang',1),t['masuk'],t['keluar'],t['biaya_kamar'],t['biaya_layanan'],t['total'],t['bayar'],t['kembalian'],t.get('kode_import','')) for t in transaksi],mata_uang=(7,8,9,10,11),tanggal_cols=(5,6))
    sheet('Rincian Kamar',['ID transaksi','Kamar','Mulai','Akhir','Malam','Tarif per malam','Subtotal'],
        [(t['id'],s['kamar'],s['mulai'],s['akhir'],s['malam'],s['harga'],s['subtotal']) for t in transaksi for s in t['segmen']],mata_uang=(6,7),tanggal_cols=(3,4))
    sheet('Rincian Layanan',['ID transaksi','Layanan','Harga satuan','Jumlah','Subtotal'],
        [(t['id'],s['nama'],s['harga'],s['jumlah'],s['harga']*s['jumlah']) for t in transaksi for s in t['layanan']],mata_uang=(3,5))
    sheet('Aktivitas Periode',['Waktu aktivitas','Aksi','Detail'],
        [(r['waktu'],r['aksi'],r['detail']) for r in hotel.riwayat if awal<=tanggal(r['waktu'][:10])<=selesai])
    simpan_workbook(wb,lokasi)



class HotelStore:
    """Snapshot hotel dalam transaksi SQLite; referensi objek dipulihkan saat dibaca."""
    def __init__(self, lokasi=DB_PATH, sumber=JSON_PATH):
        self.lokasi=Path(lokasi)
        with closing(self.koneksi()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                conn.execute('CREATE TABLE IF NOT EXISTS hotel (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)')
                if conn.execute('SELECT 1 FROM hotel WHERE id=1').fetchone() is None:
                    h=Hotel(sumber)
                    conn.execute('INSERT INTO hotel(id,data) VALUES(1,?)',(json.dumps(h.data(),ensure_ascii=False),))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def koneksi(self):
        return sqlite3.connect(self.lokasi,timeout=15)

    def baca(self):
        with closing(self.koneksi()) as conn:
            row=conn.execute('SELECT data FROM hotel WHERE id=1').fetchone()
        if row is None:raise HotelError('Data hotel tidak ditemukan.')
        try:
            h=Hotel()
            h.pulihkan(json.loads(row[0]))
            return h
        except (KeyError,TypeError,ValueError) as exc:
            raise HotelError(f'Data tersimpan tidak valid: {exc}') from exc

    def ubah(self,aksi,**v):
        with closing(self.koneksi()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                row=conn.execute('SELECT data FROM hotel WHERE id=1').fetchone()
                h=Hotel()
                h.pulihkan(json.loads(row[0]))
                if aksi in ('pindah','layanan','checkout'):
                    inap=h.kamar_di(v['nomor'],True).penghuni
                    if inap.id!=v['inap_id']:
                        raise HotelError('Penghuni kamar sudah berubah. Perbarui data sebelum melanjutkan.')
                if aksi=='checkin':
                    hasil=h.checkin(v['nomor'],v['nama'],v['telepon'],v['masuk'],v['keluar'],v['orang'])
                    pesan=f'Check-in berhasil: {hasil.tamu.nama} | kamar {v["nomor"]} | {hasil.jumlah_orang} orang.'
                elif aksi=='status':
                    h.ubah_status(v['nomor'],v['status'])
                    hasil=None
                    pesan=f'Kamar {v["nomor"]}: {v["status"]}.'
                elif aksi=='pindah':
                    h.pindah(v['nomor'],v['tujuan'],v['tanggal'])
                    hasil=None
                    pesan=f'Tamu dipindahkan dari {v["nomor"]} ke {v["tujuan"]}.'
                elif aksi=='layanan':
                    h.layanan(v['nomor'],v['nama'],v['harga'],v['jumlah'])
                    hasil=None
                    pesan='Layanan tambahan berhasil dicatat.'
                elif aksi=='checkout':
                    if h.tagihan(v['nomor'],v['keluar'])['total']!=v['total_dilihat']:
                        raise HotelError('Tagihan telah berubah. Periksa rincian terbaru sebelum membayar.')
                    hasil=h.checkout(v['nomor'],v['keluar'],v['bayar'])
                    pesan=f'Check-out berhasil. Kembalian: {rupiah(hasil["kembalian"])}.'
                elif aksi=='impor':
                    hasil=h.terapkan_impor(v['data'],v['rencana'])
                    pesan=f'Impor berhasil: {hasil} kamar / {sum(r["jumlah_orang"] for r in v["data"])} orang.'
                else:raise HotelError('Operasi tidak dikenal.')
                conn.execute('UPDATE hotel SET data=? WHERE id=1',(json.dumps(h.data(),ensure_ascii=False),))
                conn.commit()
                return pesan,hasil
            except Exception:
                conn.rollback()
                raise


def proses(store,aksi,**v):
    try:
        pesan,hasil=store.ubah(aksi,**v)
    except (HotelError,sqlite3.Error,OSError,ValueError,TypeError,KeyError) as exc:
        st.session_state['pesan']=('error',str(exc))
        return False
    st.session_state['pesan']=('success',pesan)
    if aksi=='checkout':st.session_state['struk_terakhir']=hasil
    if aksi=='checkin':
        st.session_state['ci_nama']=''
        st.session_state['ci_telepon']=''
    if aksi=='impor':st.session_state.pop('preview_excel',None)
    return True


def pindah_menu(menu,nomor=None):
    st.session_state['menu_hotel']=menu
    if nomor is not None:st.session_state['pilihan_kamar_hint']=nomor


def data_kamar(h):
    return [{'Lantai':k.lantai,'Kamar':k.nomor,'Tipe':k.tipe,'Kapasitas':k.kapasitas,'Harga per malam':k.harga,
             'Status':k.status,'Nama tamu':k.penghuni.tamu.nama if k.penghuni else '',
             'Orang':k.penghuni.jumlah_orang if k.penghuni else 0} for k in h.kamar.values()]


def format_kamar(h,n):
    k=h.kamar_di(n)
    return f'{k.nomor} · Lantai {k.lantai} · {k.tipe} · {k.kapasitas} orang · {rupiah(k.harga)}/malam'


def ringkasan(h):
    jumlah=lambda s:sum(k.status==s for k in h.kamar.values())
    with st.container(horizontal=True):
        st.metric('Kamar kosong',jumlah('Kosong'),border=True)
        st.metric('Kamar terisi',jumlah('Terisi'),border=True)
        st.metric('Tamu menginap',sum(i.jumlah_orang for i in h.aktif.values()),border=True)
        st.metric('Okupansi',f'{jumlah("Terisi")}% ',border=True)
    st.caption(f'10 lantai · 100 kamar · Kapasitas 220 orang · Dibersihkan {jumlah("Dibersihkan")} · Perawatan {jumlah("Perawatan")}')


def dashboard(h):
    st.header('Ringkasan hotel')
    with st.container(horizontal=True):
        st.metric('Pendapatan transaksi selesai',rupiah(sum(t['total'] for t in h.transaksi)),border=True)
        st.metric('Check-in aktif',len(h.aktif),border=True)
        st.metric('Transaksi selesai',len(h.transaksi),border=True)
    rekap=[]
    for lantai in range(1,11):
        ks=[k for k in h.kamar.values() if k.lantai==lantai]
        rekap.append({'Lantai':str(lantai),'Kosong':sum(k.status=='Kosong' for k in ks),
                      'Terisi':sum(k.status=='Terisi' for k in ks),'Dibersihkan':sum(k.status=='Dibersihkan' for k in ks),
                      'Perawatan':sum(k.status=='Perawatan' for k in ks)})
    st.subheader('Status kamar per lantai')
    st.bar_chart(rekap,x='Lantai',y=['Kosong','Terisi','Dibersihkan','Perawatan'],stack=True,
                 color=['#059669','#2563eb','#d97706','#dc2626'])
    with st.container(horizontal=True):
        st.button('Check-in tamu',type='primary',icon=':material/person_add:',on_click=pindah_menu,args=('Check-in',))
        st.button('Lihat denah',icon=':material/apartment:',on_click=pindah_menu,args=('Denah hotel',))


def denah(h):
    st.header('Denah hotel')
    lantai=st.selectbox('Pilih lantai',list(range(1,11)),key='denah_lantai')
    st.caption('Empat kamar single, tiga double, dan tiga family pada setiap lantai. Harga per kamar per malam.')
    warna={'Kosong':'green','Terisi':'blue','Dibersihkan':'orange','Perawatan':'red'}
    with st.container(horizontal=True):
        for k in h.kamar.values():
            if k.lantai!=lantai:continue
            with st.container(border=True,width=220):
                st.badge(k.status,color=warna[k.status])
                st.subheader(str(k.nomor))
                st.caption(f'{k.tipe} · Maks. {k.kapasitas} orang')
                st.text(rupiah(k.harga)+'/malam')
                if k.penghuni:
                    st.text(k.penghuni.tamu.nama)
                    st.caption(f'{k.penghuni.jumlah_orang} orang menginap')
                tujuan='Check-in' if k.status=='Kosong' else 'Tamu menginap' if k.penghuni else 'Data kamar'
                st.button(('Pilih ' if k.status=='Kosong' else 'Kelola ')+str(k.nomor),key=f'kamar_{k.nomor}',
                          on_click=pindah_menu,args=(tujuan,k.nomor),width='stretch')


def halaman_kamar(h,store):
    st.header('Data dan kesiapan kamar')
    kiri,kanan=st.columns(2)
    lantai=kiri.selectbox('Lantai',['Semua']+list(range(1,11)),key='filter_lantai_kamar')
    status=kanan.selectbox('Status',['Semua','Kosong','Terisi','Dibersihkan','Perawatan'],key='filter_status_kamar')
    rows=[r for r in data_kamar(h) if (lantai=='Semua' or r['Lantai']==lantai) and (status=='Semua' or r['Status']==status)]
    st.dataframe(rows,hide_index=True,column_config={'Harga per malam':st.column_config.NumberColumn(format='Rp %d')})
    kosong=[k.nomor for k in h.kamar.values() if k.penghuni is None]
    st.subheader('Ubah status kamar tanpa penghuni')
    if not kosong:
        st.info('Semua kamar sedang ditempati.')
        return
    hint=st.session_state.pop('pilihan_kamar_hint',None)
    if hint in kosong:st.session_state['status_nomor']=hint
    if st.session_state.get('status_nomor') not in kosong:st.session_state['status_nomor']=kosong[0]
    with st.form('status_kamar'):
        nomor=st.selectbox('Kamar',kosong,format_func=lambda n:format_kamar(h,n),key='status_nomor')
        target=st.selectbox('Status baru',['Kosong','Dibersihkan','Perawatan'],key='status_baru')
        st.form_submit_button('Simpan status',on_click=simpan_status,args=(store,))
    st.caption('Kamar terisi hanya boleh dikosongkan melalui pindah kamar atau check-out.')


def simpan_status(store):
    proses(store,'status',nomor=st.session_state['status_nomor'],status=st.session_state['status_baru'])


def kirim_checkin(store):
    nomor=st.session_state.get('ci_kamar')
    if nomor is None:
        st.session_state['pesan']=('error','Pilih nomor kamar terlebih dahulu.')
        return
    proses(store,'checkin',nomor=nomor,nama=st.session_state.get('ci_nama',''),
           telepon=st.session_state.get('ci_telepon',''),orang=st.session_state['ci_orang'],
           masuk=st.session_state['ci_masuk'].isoformat(),keluar=st.session_state['ci_keluar'].isoformat())


def checkin_manual(h,store):
    kiri,kanan,ketiga=st.columns(3)
    orang=kiri.number_input('Jumlah orang',min_value=1,max_value=4,value=1,step=1,key='ci_orang')
    lantai=kanan.selectbox('Lantai',['Semua']+list(range(1,11)),key='ci_lantai')
    tipe=ketiga.selectbox('Tipe kamar',['Semua','Standard','Deluxe','Suite'],key='ci_tipe')
    hint=st.session_state.pop('pilihan_kamar_hint',None)
    # Hint dari denah hanya memilih nomor; filter tetap harus dipenuhi.
    kandidat=[k.nomor for k in h.kamar.values() if k.status=='Kosong' and k.kapasitas>=orang
              and (lantai=='Semua' or k.lantai==lantai) and (tipe=='Semua' or k.tipe==tipe)]
    if hint in kandidat:st.session_state['ci_kamar']=hint
    elif hint is not None:st.warning('Kamar dari denah tidak cocok dengan jumlah orang/filter saat ini. Sesuaikan filter atau pilih kamar lain.')
    if st.session_state.get('ci_kamar') not in kandidat:st.session_state['ci_kamar']=None
    nomor=st.selectbox('Pilih kamar yang tersedia',kandidat,index=None,placeholder='Pilih nomor kamar',
                       format_func=lambda n:format_kamar(h,n),key='ci_kamar')
    st.caption(f'{len(kandidat)} kamar tersedia sesuai pilihan. Harga per kamar, bukan per orang.')
    with st.form('checkin_manual'):
        st.text_input('Nama penanggung jawab',key='ci_nama',max_chars=150)
        st.text_input('Nomor telepon',key='ci_telepon',max_chars=40)
        col1,col2=st.columns(2)
        col1.date_input('Tanggal masuk',value=datetime.now(WIB).date(),key='ci_masuk')
        col2.date_input('Rencana keluar',value=datetime.now(WIB).date()+timedelta(days=1),key='ci_keluar')
        st.form_submit_button('Simpan check-in',type='primary',icon=':material/check:',
                              disabled=nomor is None,on_click=kirim_checkin,args=(store,))


def workbook_bytes(fungsi,*args):
    buffer=io.BytesIO()
    fungsi(*args,buffer)
    return buffer.getvalue()


def impor_excel(h,store):
    st.subheader('Impor rombongan dari Excel')
    with st.expander('Aturan format yang wajib diikuti',expanded=True):
        st.text(ATURAN_IMPOR)
    try:
        st.download_button('Unduh template Excel',data=workbook_bytes(template_excel),file_name='Template_CheckIn_HotelKu.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',on_click='ignore')
    except (HotelError,OSError,ValueError) as exc:
        st.error(str(exc))
        return
    setuju=st.checkbox('Saya sudah membaca dan memahami aturan impor.',key='setuju_impor')
    unggahan=st.file_uploader('Pilih file .xlsx sesuai template',type=['xlsx'],disabled=not setuju,key='unggahan_excel')
    if not setuju or unggahan is None:return
    fingerprint=hashlib.sha256(unggahan.getvalue()).hexdigest()
    if st.button('Periksa dan buat pratinjau',type='primary',key='periksa_impor'):
        st.session_state.pop('preview_excel',None)
        try:
            data=baca_excel(io.BytesIO(unggahan.getvalue()))
            rencana=h.rencana_impor(data)
            st.session_state['preview_excel']={'hash':fingerprint,'data':data,'rencana':rencana}
        except (HotelError,OSError,ValueError) as exc:
            st.error(str(exc))
    preview=st.session_state.get('preview_excel')
    if not preview or preview['hash']!=fingerprint:return
    st.caption('Pratinjau saja: belum ada check-in disimpan.')
    rows=[]
    for r in preview['rencana']:
        k=h.kamar_di(r['kamar_dibagi'])
        rows.append({'Baris':r['baris'],'Kode impor':r['kode_import'],'Nama':r['nama'],'Orang':r['jumlah_orang'],
                     'Kamar':k.nomor,'Lantai':k.lantai,'Kapasitas':k.kapasitas,'Tarif/malam':k.harga,
                     'Masuk':r['tanggal_masuk'],'Keluar':r['tanggal_keluar']})
    st.dataframe(rows,hide_index=True)
    st.write(f'{len(rows)} rombongan/kamar · {sum(r["jumlah_orang"] for r in preview["data"])} orang')
    with st.container(horizontal=True):
        st.button('Simpan semua check-in',type='primary',on_click=proses,args=(store,'impor'),
                  kwargs={'data':preview['data'],'rencana':preview['rencana']},key='simpan_impor')
        st.button('Batalkan pratinjau',on_click=lambda:st.session_state.pop('preview_excel',None))


def halaman_checkin(h,store):
    st.header('Check-in tamu')
    manual,excel=st.tabs(['Pilih kamar & daftar','Impor Excel'])
    with manual:checkin_manual(h,store)
    with excel:impor_excel(h,store)


def kirim_pindah(store,nomor,inap_id):
    proses(store,'pindah',nomor=nomor,inap_id=inap_id,tujuan=st.session_state['pindah_tujuan'],
           tanggal=st.session_state['pindah_tanggal'].isoformat())


def kirim_layanan(store,nomor,inap_id):
    proses(store,'layanan',nomor=nomor,inap_id=inap_id,nama=st.session_state.get('layanan_nama',''),
           harga=st.session_state.get('layanan_harga',0),jumlah=st.session_state.get('layanan_jumlah',1))


def kirim_checkout(store,nomor,inap_id,total):
    if not st.session_state.get('konfirmasi_checkout',False):
        st.session_state['pesan']=('error','Centang konfirmasi pembayaran sebelum menyelesaikan check-out.')
        return
    proses(store,'checkout',nomor=nomor,inap_id=inap_id,keluar=st.session_state['checkout_tanggal'].isoformat(),
           bayar=st.session_state['checkout_bayar'],total_dilihat=total)


def tampilkan_struk(data,key):
    with st.expander('Struk pembayaran',expanded=True):
        st.text(struk(data))
        st.download_button('Unduh struk TXT',data=struk(data).encode('utf-8'),file_name=f'Struk_{data["id"][:10]}.txt',
                           mime='text/plain',key=key,on_click='ignore')


def halaman_tamu(h,store):
    st.header('Tamu menginap')
    if st.session_state.get('struk_terakhir'):tampilkan_struk(st.session_state['struk_terakhir'],'struk_baru')
    aktif=[k for k in h.kamar.values() if k.penghuni]
    cari=st.text_input('Cari nama atau nomor kamar',key='cari_tamu').strip().casefold()
    rows=[{'Kamar':k.nomor,'Lantai':k.lantai,'Nama':k.penghuni.tamu.nama,'Telepon':k.penghuni.tamu.telepon,
           'Orang':k.penghuni.jumlah_orang,'Masuk':k.penghuni.masuk,'Rencana keluar':k.penghuni.rencana_keluar} for k in aktif
          if not cari or cari in f'{k.nomor} {k.penghuni.tamu.nama}'.casefold()]
    if rows:st.dataframe(rows,hide_index=True)
    else:st.info('Tidak ada tamu yang cocok dengan pencarian.' if cari else 'Belum ada tamu menginap.')
    if not aktif:return
    nomor_aktif=[k.nomor for k in aktif]
    hint=st.session_state.pop('pilihan_kamar_hint',None)
    if hint in nomor_aktif:st.session_state['tamu_kamar']=hint
    if st.session_state.get('tamu_kamar') not in nomor_aktif:st.session_state['tamu_kamar']=nomor_aktif[0]
    nomor=st.selectbox('Pilih tamu yang akan dikelola',nomor_aktif,key='tamu_kamar',
        format_func=lambda n:f'{n} · {h.kamar_di(n).penghuni.tamu.nama}')
    k=h.kamar_di(nomor,True)
    inap=k.penghuni
    st.caption(f'{inap.jumlah_orang} orang · Kapasitas {k.kapasitas} · ID menginap {inap.id[:12]}')
    pindah,layanan,checkout=st.tabs(['Pindah kamar','Layanan tambahan','Tagihan & check-out'])
    with pindah:
        tujuan=[x.nomor for x in h.kamar.values() if x.status=='Kosong' and x.kapasitas>=inap.jumlah_orang]
        if not tujuan:st.info('Tidak ada kamar kosong yang kapasitasnya cukup.')
        else:
            if st.session_state.get('pindah_tujuan') not in tujuan:st.session_state['pindah_tujuan']=tujuan[0]
            with st.form('form_pindah'):
                st.selectbox('Kamar tujuan',tujuan,key='pindah_tujuan',format_func=lambda n:format_kamar(h,n))
                st.date_input('Tanggal pindah',value=datetime.now(WIB).date(),key='pindah_tanggal')
                st.form_submit_button('Simpan perpindahan',on_click=kirim_pindah,args=(store,nomor,inap.id))
            st.caption('Tarif dihitung sesuai jumlah malam pada setiap kamar. Kamar asal menjadi Dibersihkan.')
    with layanan:
        if inap.layanan:st.dataframe(inap.layanan,hide_index=True)
        with st.form('form_layanan'):
            st.text_input('Nama layanan',key='layanan_nama',max_chars=120)
            st.number_input('Harga satuan (rupiah)',min_value=0,value=0,step=1000,key='layanan_harga')
            st.number_input('Jumlah',min_value=1,value=1,step=1,key='layanan_jumlah')
            st.form_submit_button('Tambahkan layanan',on_click=kirim_layanan,args=(store,nomor,inap.id))
    with checkout:
        keluar=st.date_input('Tanggal check-out aktual',value=datetime.now(WIB).date(),key='checkout_tanggal')
        try:tagihan=h.tagihan(nomor,keluar.isoformat())
        except HotelError as exc:
            st.warning(str(exc))
            return
        with st.container(border=True):
            st.text(struk(tagihan))
        with st.form('form_checkout'):
            st.number_input('Uang diterima (rupiah)',min_value=0,value=0,step=10000,key='checkout_bayar')
            st.checkbox('Saya sudah memeriksa rincian dan menerima pembayaran.',key='konfirmasi_checkout')
            st.form_submit_button('Bayar & check-out',type='primary',on_click=kirim_checkout,
                                  args=(store,nomor,inap.id,tagihan['total']))


def halaman_transaksi(h):
    st.header('Transaksi dan riwayat')
    cari=st.text_input('Cari nama atau ID transaksi',key='cari_transaksi').strip().casefold()
    data=[t for t in reversed(h.transaksi) if not cari or cari in f'{t["id"]} {t["tamu"]["nama"]}'.casefold()]
    if data:
        st.dataframe([{'ID':t['id'][:12],'Nama':t['tamu']['nama'],'Orang':t.get('jumlah_orang',1),
            'Masuk':t['masuk'],'Keluar':t['keluar'],'Total':t['total'],'Kembalian':t['kembalian']} for t in data],
            hide_index=True,column_config={'Total':st.column_config.NumberColumn(format='Rp %d'),
                                           'Kembalian':st.column_config.NumberColumn(format='Rp %d')})
        ids=[t['id'] for t in data]
        if st.session_state.get('transaksi_id') not in ids:st.session_state['transaksi_id']=ids[0]
        identitas=st.selectbox('Pilih struk',ids,key='transaksi_id',format_func=lambda ident:next(
            f'{t["tamu"]["nama"]} · {t["keluar"]} · {rupiah(t["total"])}' for t in data if t['id']==ident))
        tampilkan_struk(next(t for t in data if t['id']==identitas),'struk_transaksi')
    else:st.info('Belum ada transaksi selesai yang cocok.')
    with st.expander('Aktivitas hotel terakhir'):
        if h.riwayat:st.dataframe(list(reversed(h.riwayat[-100:])),hide_index=True)
        else:st.caption('Belum ada aktivitas.')


def halaman_laporan(h):
    st.header('Laporan hotel')
    st.caption('Periode menyaring transaksi berdasarkan tanggal check-out. Kamar dan tamu aktif adalah snapshot saat ekspor.')
    kiri,kanan=st.columns(2)
    mulai=kiri.date_input('Awal periode',value=datetime.now(WIB).date().replace(day=1),key='laporan_mulai')
    akhir=kanan.date_input('Akhir periode',value=datetime.now(WIB).date(),key='laporan_akhir')
    if akhir<mulai:
        st.error('Akhir periode harus sama atau setelah awal periode.')
        return
    data=[t for t in h.transaksi if mulai<=tanggal(t['keluar'])<=akhir]
    with st.container(horizontal=True):
        st.metric('Transaksi selesai',len(data),border=True)
        st.metric('Tamu check-out',sum(t.get('jumlah_orang',1) for t in data),border=True)
        st.metric('Pendapatan periode',rupiah(sum(t['total'] for t in data)),border=True)
    st.caption('Ekspor berisi Ringkasan, Kamar Saat Ekspor, Tamu Aktif, Transaksi Periode, Rincian Kamar, Rincian Layanan, dan Aktivitas Periode.')
    fingerprint=hashlib.sha256(json.dumps(h.data(),sort_keys=True).encode()).hexdigest()
    signature=(mulai.isoformat(),akhir.isoformat(),fingerprint)
    if st.button('Buat laporan Excel',type='primary',icon=':material/description:'):
        st.session_state.pop('laporan_excel',None)
        try:
            buffer=io.BytesIO()
            ekspor_laporan(h,buffer,mulai.isoformat(),akhir.isoformat())
            st.session_state['laporan_excel']={'signature':signature,'bytes':buffer.getvalue(),
                'waktu':datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}
        except (HotelError,OSError,ValueError) as exc:st.error(str(exc))
    laporan=st.session_state.get('laporan_excel')
    if laporan and laporan['signature']==signature:
        st.download_button('Unduh laporan Excel',data=laporan['bytes'],file_name=f'Laporan_HotelKu_{mulai}_{akhir}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',on_click='ignore')
        st.caption('Dibuat pada '+laporan['waktu'])
    elif laporan:st.caption('Data atau periode berubah. Buat ulang laporan untuk mendapatkan versi terbaru.')


def halaman_referensi(h):
    st.header('Visualisasi referensi objek')
    lantai=st.selectbox('Lantai untuk visualisasi',list(range(1,11)),key='ref_lantai')
    st.caption('Kamar.penghuni → objek Menginap → objek Tamu. ID aplikasi bukan alamat memori asli.')
    nodes=['digraph hotel { rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#EFF6FF"];']
    rows=[]
    for k in h.kamar.values():
        if k.lantai!=lantai:continue
        nodes.append(f'k{k.nomor} [label={json.dumps(f"Kamar {k.nomor} | {k.status}")}];')
        if k.penghuni:
            i=k.penghuni
            nodes.append(f'i{k.nomor} [label={json.dumps("Menginap "+i.id[:10])}];')
            nodes.append(f't{k.nomor} [label={json.dumps(i.tamu.nama+" | "+str(i.jumlah_orang)+" orang")}];')
            nodes.append(f'k{k.nomor} -> i{k.nomor} -> t{k.nomor};')
            rows.append({'Kamar':k.nomor,'ID menginap':i.id[:12],'Tamu':i.tamu.nama,
                         'Referensi sama dengan daftar aktif':i is h.aktif[i.id]})
        else:
            nodes.append(f'n{k.nomor} [label="None",fillcolor="#F1F5F9"]; k{k.nomor} -> n{k.nomor};')
    nodes.append('}')
    st.graphviz_chart('\n'.join(nodes))
    if rows:st.dataframe(rows,hide_index=True)
    st.caption('Pindah kamar mengalihkan referensi objek yang sama. Check-out melepaskan referensi kamar menjadi None.')


def main():
    st.set_page_config(page_title='HotelKu | Kelompok 8',page_icon=':material/apartment:',layout='wide')
    try:
        store=HotelStore()
        h=store.baca()
    except (HotelError,sqlite3.Error,OSError,ValueError,KeyError,TypeError) as exc:
        st.error(f'Data hotel belum dapat dibaca: {exc}')
        st.caption('File sumber dipertahankan. Periksa JSON sumber dan izin lokasi database, lalu coba kembali.')
        st.stop()
    with st.sidebar:
        with st.container(key='app-sidebar-hotel'):
            sidebar_header('hotel', 'HotelKu', 'Referensi objek', 'Kelola kesiapan kamar, tamu, dan transaksi hotel.')
            menu=sidebar_menu(['Dashboard','Denah hotel','Data kamar','Check-in','Tamu menginap','Transaksi','Laporan','Referensi objek'],key='menu_hotel',icons={
                'Dashboard':'dashboard','Denah hotel':'apartment','Data kamar':'meeting_room','Check-in':'login',
                'Tamu menginap':'people','Transaksi':'receipt_long','Laporan':'bar_chart','Referensi objek':'account_tree'})
            sidebar_refresh('hotel_refresh')
            st.caption('Kelompok 8 · 10 lantai · 100 kamar')
    st.title('Manajemen hotel')
    ringkasan(h)
    if 'pesan' in st.session_state:
        jenis,pesan=st.session_state.pop('pesan')
        if jenis=='success':st.success(pesan)
        else:st.error(pesan)
    if menu=='Dashboard':dashboard(h)
    elif menu=='Denah hotel':denah(h)
    elif menu=='Data kamar':halaman_kamar(h,store)
    elif menu=='Check-in':halaman_checkin(h,store)
    elif menu=='Tamu menginap':halaman_tamu(h,store)
    elif menu=='Transaksi':halaman_transaksi(h)
    elif menu=='Laporan':halaman_laporan(h)
    else:halaman_referensi(h)
    st.caption('Tersimpan otomatis · Gunakan Perbarui data untuk membaca perubahan dari tab lain.')


if __name__=='__main__':
    main()
