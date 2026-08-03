"""
utils.py
Modul bantu untuk aplikasi Pencatatan Keuangan Bendahara KKN.
Backend penyimpanan data: Google Sheets (via gspread + Service Account).
Mendukung 2 kas: Kas Umum & Kas Proker, plus transfer antar kas.
Berisi juga: kategori default, format rupiah, dan export laporan ke Excel & PDF.
"""

import io
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from fpdf import FPDF

# ----------------------------------------------------------------------
# KONFIGURASI GOOGLE SHEETS
# ----------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TRANSAKSI_SHEET = "Transaksi"
PROKER_SHEET = "Proker"
ANGGOTA_SHEET = "Anggota"
PENGATURAN_SHEET = "Pengaturan"
IURAN_SHEET = "Iuran Kas"

TRANSAKSI_COLUMNS = ["ID", "Tanggal", "Jenis", "Kas", "Proker", "Kategori", "Keterangan", "Jumlah"]
PROKER_COLUMNS = ["Nama Proker"]
ANGGOTA_COLUMNS = ["Nama Anggota"]
PENGATURAN_COLUMNS = ["Key", "Value"]
IURAN_COLUMNS = ["ID", "Minggu", "Nama Anggota", "Tanggal Bayar", "ID Transaksi"]

KEY_NOMINAL_KAS_MINGGUAN = "Nominal Kas Mingguan"

KAS_OPTIONS = ["Kas Umum", "Kas Proker"]
KATEGORI_TRANSFER = "Transfer Antar Kas"

KATEGORI_DEFAULT = {
    "Pemasukan": [
        "Kas Anggota",
        "Sponsor",
        "Donasi",
        "Dana Desa/Kelurahan",
        "Dana Kampus",
        KATEGORI_TRANSFER,
        "Lainnya",
    ],
    "Pengeluaran": [
        "Konsumsi",
        "Transportasi",
        "ATK & Perlengkapan",
        "Dekorasi & Perlengkapan Acara",
        "Sewa Tempat/Alat",
        "Dokumentasi & Publikasi",
        "Honorarium/Konsumsi Narasumber",
        KATEGORI_TRANSFER,
        "Lainnya",
    ],
}

# Kategori yang boleh dipilih manual di form Input Transaksi (tanpa kategori transfer,
# karena transfer wajib lewat menu "Transfer Antar Kas" agar saldo tetap seimbang).
KATEGORI_INPUT_MANUAL = {
    jenis: [k for k in daftar if k != KATEGORI_TRANSFER]
    for jenis, daftar in KATEGORI_DEFAULT.items()
}

PROKER_DEFAULT = ["Umum / Operasional Kelompok"]
PROKER_UMUM_PLACEHOLDER = PROKER_DEFAULT[0]


def _retry(func, *args, max_retries=4, base_delay=2, **kwargs):
    """Panggil fungsi gspread dengan retry otomatis (exponential backoff) jika kena rate limit (429)."""
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            msg = str(e)
            if ("429" in msg or "Quota exceeded" in msg) and attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise


def _get_records_safe(ws, expected_columns):
    """Ambil isi worksheet sebagai list of dict TANPA memakai ws.get_all_records().

    ws.get_all_records() bawaan gspread memvalidasi baris header secara ketat dan akan
    melempar GSpreadException jika ada header kosong/duplikat/tidak konsisten (misalnya
    akibat sheet pernah diedit manual, atau proses migrasi skema lama). Fungsi ini
    membaca nilai mentah lalu memetakan setiap baris ke `expected_columns` (kolom yang
    KITA definisikan di kode), sehingga tidak bergantung pada isi baris header di sheet
    dan lebih tahan terhadap data yang sedikit berantakan.
    """
    all_values = _retry(ws.get_all_values)
    if len(all_values) < 2:
        return []
    rows = all_values[1:]
    n = len(expected_columns)
    records = []
    for row in rows:
        if not any(str(v).strip() for v in row):
            continue  # lewati baris yang benar-benar kosong
        row = (row + [""] * n)[:n]
        records.append(dict(zip(expected_columns, row)))
    return records


# ----------------------------------------------------------------------
# KONEKSI GOOGLE SHEETS
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gspread_client()
    # Prioritaskan SPREADSHEET_ID (unik, tidak mungkin salah sasaran file).
    spreadsheet_id = st.secrets.get("SPREADSHEET_ID", "").strip()
    if spreadsheet_id:
        return _retry(client.open_by_key, spreadsheet_id)
    # Fallback: cari berdasarkan nama (kurang aman jika ada file dengan nama sama).
    spreadsheet_name = st.secrets.get("SPREADSHEET_NAME", "Keuangan KKN")
    return _retry(client.open, spreadsheet_name)


@st.cache_resource(show_spinner=False)
def get_worksheet(name, headers):
    sh = get_spreadsheet()
    try:
        ws = _retry(sh.worksheet, name)
    except WorksheetNotFound:
        ws = _retry(sh.add_worksheet, title=name, rows=1000, cols=max(len(headers), 2))
        _retry(ws.append_row, headers, value_input_option="USER_ENTERED")
    return ws


def _migrate_transaksi_schema():
    """Migrasi otomatis jika header sheet Transaksi lama (belum ada kolom 'Kas')."""
    ws = get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    all_values = _retry(ws.get_all_values)
    if not all_values:
        return
    header = all_values[0]
    if header == TRANSAKSI_COLUMNS:
        return  # sudah sesuai skema terbaru

    old_rows = all_values[1:]
    old_df = pd.DataFrame(old_rows, columns=header) if old_rows else pd.DataFrame(columns=header)

    if "Kas" not in old_df.columns:
        old_df["Kas"] = "Kas Umum"  # data lama dianggap Kas Umum secara default

    for col in TRANSAKSI_COLUMNS:
        if col not in old_df.columns:
            old_df[col] = ""

    old_df = old_df[TRANSAKSI_COLUMNS]

    _retry(ws.clear)
    _retry(ws.append_row, TRANSAKSI_COLUMNS, value_input_option="USER_ENTERED")
    if not old_df.empty:
        _retry(ws.append_rows, old_df.values.tolist(), value_input_option="USER_ENTERED")


def init_data():
    """Pastikan koneksi ke Google Sheets berhasil, worksheet & skema tersedia.
    Hanya dijalankan sekali per sesi browser untuk menghemat kuota Google Sheets API,
    karena Streamlit menjalankan ulang seluruh skrip setiap ada interaksi."""
    if st.session_state.get("_init_data_done"):
        return

    try:
        get_spreadsheet()
    except SpreadsheetNotFound:
        identifier = st.secrets.get("SPREADSHEET_ID", "") or st.secrets.get("SPREADSHEET_NAME", "Keuangan KKN")
        st.error(
            f"Spreadsheet **'{identifier}'** tidak ditemukan, "
            "atau belum di-share ke email service account. "
            "Silakan cek langkah setup di README.md."
        )
        st.stop()
    except KeyError:
        st.error(
            "Konfigurasi `gcp_service_account` belum ditemukan di secrets. "
            "Silakan lengkapi file `.streamlit/secrets.toml` sesuai README.md."
        )
        st.stop()
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets: {e}")
        st.stop()

    get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    _migrate_transaksi_schema()

    ws_proker = get_worksheet(PROKER_SHEET, PROKER_COLUMNS)
    if not _get_records_safe(ws_proker, PROKER_COLUMNS):
        _retry(ws_proker.append_row, PROKER_DEFAULT, value_input_option="USER_ENTERED")

    get_worksheet(ANGGOTA_SHEET, ANGGOTA_COLUMNS)
    get_worksheet(PENGATURAN_SHEET, PENGATURAN_COLUMNS)
    get_worksheet(IURAN_SHEET, IURAN_COLUMNS)

    st.session_state["_init_data_done"] = True


# ----------------------------------------------------------------------
# DATA TRANSAKSI
# ----------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_transaksi() -> pd.DataFrame:
    ws = get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    records = _get_records_safe(ws, TRANSAKSI_COLUMNS)
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=TRANSAKSI_COLUMNS)
    else:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)

    if "Kas" not in df.columns:
        df["Kas"] = "Kas Umum"
    df["Kas"] = df["Kas"].replace("", "Kas Umum").fillna("Kas Umum")

    df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors="coerce")
    df["Jumlah"] = pd.to_numeric(df["Jumlah"], errors="coerce").fillna(0)
    return df


def next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["ID"].max()) + 1


def add_transaksi(tanggal, jenis, kas, proker, kategori, keterangan, jumlah):
    ws = get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    df = load_transaksi()
    new_id = next_id(df)
    row = [new_id, str(tanggal), jenis, kas, proker, kategori, keterangan, float(jumlah)]
    _retry(ws.append_row, row, value_input_option="USER_ENTERED")
    load_transaksi.clear()
    return load_transaksi()


def add_transfer(tanggal, arah, proker, jumlah, keterangan=""):
    """
    Catat transfer antar kas sebagai sepasang transaksi (saling menyeimbangkan):
    - arah "Kas Umum ke Kas Proker": Kas Umum berkurang, Kas Proker (proker terkait) bertambah
    - arah "Kas Proker ke Kas Umum": Kas Proker (proker terkait) berkurang, Kas Umum bertambah
    """
    jumlah = float(jumlah)
    catatan = keterangan.strip()
    tambahan = f" - {catatan}" if catatan else ""

    if arah == "Kas Umum ke Kas Proker":
        add_transaksi(
            tanggal, "Pengeluaran", "Kas Umum", PROKER_UMUM_PLACEHOLDER, KATEGORI_TRANSFER,
            f"Transfer ke Kas Proker ({proker}){tambahan}", jumlah,
        )
        add_transaksi(
            tanggal, "Pemasukan", "Kas Proker", proker, KATEGORI_TRANSFER,
            f"Transfer dari Kas Umum{tambahan}", jumlah,
        )
    else:  # "Kas Proker ke Kas Umum"
        add_transaksi(
            tanggal, "Pengeluaran", "Kas Proker", proker, KATEGORI_TRANSFER,
            f"Transfer ke Kas Umum{tambahan}", jumlah,
        )
        add_transaksi(
            tanggal, "Pemasukan", "Kas Umum", PROKER_UMUM_PLACEHOLDER, KATEGORI_TRANSFER,
            f"Transfer dari Kas Proker ({proker}){tambahan}", jumlah,
        )
    load_transaksi.clear()
    return load_transaksi()


def _find_row_index(ws, id_) -> int | None:
    """Cari nomor baris (1-indexed, termasuk header) berdasarkan ID di kolom A."""
    ids = _retry(ws.col_values, 1)[1:]  # lewati header
    target = str(int(id_))
    for i, val in enumerate(ids):
        if str(val).strip() == target:
            return i + 2  # +1 utk header, +1 utk index 0-based -> 1-based
    return None


def update_transaksi(id_, tanggal, jenis, kas, proker, kategori, keterangan, jumlah):
    ws = get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    row_idx = _find_row_index(ws, id_)
    if row_idx is None:
        return load_transaksi()
    new_row = [int(id_), str(tanggal), jenis, kas, proker, kategori, keterangan, float(jumlah)]
    _retry(ws.update, f"A{row_idx}:H{row_idx}", [new_row], value_input_option="USER_ENTERED")
    load_transaksi.clear()
    return load_transaksi()


def delete_transaksi(id_):
    ws = get_worksheet(TRANSAKSI_SHEET, TRANSAKSI_COLUMNS)
    row_idx = _find_row_index(ws, id_)
    if row_idx is not None:
        _retry(ws.delete_rows, row_idx)
    load_transaksi.clear()
    return load_transaksi()


# ----------------------------------------------------------------------
# DATA PROKER / KEGIATAN
# ----------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_proker() -> list:
    ws = get_worksheet(PROKER_SHEET, PROKER_COLUMNS)
    records = _get_records_safe(ws, PROKER_COLUMNS)
    if not records:
        return PROKER_DEFAULT.copy()
    hasil = [str(r.get("Nama Proker", "")).strip() for r in records]
    return [p for p in hasil if p]


def save_proker(list_proker: list):
    ws = get_worksheet(PROKER_SHEET, PROKER_COLUMNS)
    bersih = sorted(set([p.strip() for p in list_proker if p.strip()]))
    _retry(ws.clear)
    _retry(ws.append_row, PROKER_COLUMNS, value_input_option="USER_ENTERED")
    if bersih:
        _retry(ws.append_rows, [[p] for p in bersih], value_input_option="USER_ENTERED")
    load_proker.clear()


def add_proker(nama: str):
    nama = nama.strip()
    daftar = load_proker()
    if nama and nama not in daftar:
        ws = get_worksheet(PROKER_SHEET, PROKER_COLUMNS)
        _retry(ws.append_row, [nama], value_input_option="USER_ENTERED")
        load_proker.clear()
    return load_proker()


def delete_proker(nama: str):
    daftar = [p for p in load_proker() if p != nama]
    save_proker(daftar)
    return load_proker()


# ----------------------------------------------------------------------
# DATA ANGGOTA
# ----------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_anggota() -> list:
    ws = get_worksheet(ANGGOTA_SHEET, ANGGOTA_COLUMNS)
    records = _get_records_safe(ws, ANGGOTA_COLUMNS)
    hasil = [str(r.get("Nama Anggota", "")).strip() for r in records]
    return [a for a in hasil if a]


def save_anggota(list_anggota: list):
    ws = get_worksheet(ANGGOTA_SHEET, ANGGOTA_COLUMNS)
    bersih = sorted(set([a.strip() for a in list_anggota if a.strip()]))
    _retry(ws.clear)
    _retry(ws.append_row, ANGGOTA_COLUMNS, value_input_option="USER_ENTERED")
    if bersih:
        _retry(ws.append_rows, [[a] for a in bersih], value_input_option="USER_ENTERED")
    load_anggota.clear()


def add_anggota(nama: str):
    nama = nama.strip()
    daftar = load_anggota()
    if nama and nama not in daftar:
        ws = get_worksheet(ANGGOTA_SHEET, ANGGOTA_COLUMNS)
        _retry(ws.append_row, [nama], value_input_option="USER_ENTERED")
        load_anggota.clear()
    return load_anggota()


def delete_anggota(nama: str):
    daftar = [a for a in load_anggota() if a != nama]
    save_anggota(daftar)
    return load_anggota()


# ----------------------------------------------------------------------
# PENGATURAN (KEY-VALUE)
# ----------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_pengaturan() -> dict:
    ws = get_worksheet(PENGATURAN_SHEET, PENGATURAN_COLUMNS)
    records = _get_records_safe(ws, PENGATURAN_COLUMNS)
    return {str(r.get("Key", "")): r.get("Value", "") for r in records}


def set_pengaturan(key: str, value):
    ws = get_worksheet(PENGATURAN_SHEET, PENGATURAN_COLUMNS)
    keys = _retry(ws.col_values, 1)[1:]
    if key in keys:
        row_idx = keys.index(key) + 2
        _retry(ws.update, f"B{row_idx}", [[value]], value_input_option="USER_ENTERED")
    else:
        _retry(ws.append_row, [key, value], value_input_option="USER_ENTERED")
    load_pengaturan.clear()


def get_nominal_kas_mingguan() -> float:
    pengaturan = load_pengaturan()
    try:
        return float(pengaturan.get(KEY_NOMINAL_KAS_MINGGUAN, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def set_nominal_kas_mingguan(value):
    set_pengaturan(KEY_NOMINAL_KAS_MINGGUAN, float(value))


# ----------------------------------------------------------------------
# IURAN KAS ANGGOTA (MINGGUAN)
# ----------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def load_iuran() -> pd.DataFrame:
    ws = get_worksheet(IURAN_SHEET, IURAN_COLUMNS)
    records = _get_records_safe(ws, IURAN_COLUMNS)
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=IURAN_COLUMNS)
    else:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
        df["ID Transaksi"] = pd.to_numeric(df["ID Transaksi"], errors="coerce").fillna(0).astype(int)
    return df


def _next_iuran_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["ID"].max()) + 1


def mark_iuran_paid(minggu_label: str, nama: str, tanggal_bayar):
    """Tandai anggota sudah bayar iuran minggu tsb: buat transaksi Pemasukan + catatan iuran."""
    nominal = get_nominal_kas_mingguan()
    df_trans = add_transaksi(
        tanggal_bayar, "Pemasukan", "Kas Umum", PROKER_UMUM_PLACEHOLDER, "Kas Anggota",
        f"Iuran kas mingguan - {nama} - Minggu {minggu_label}", nominal,
    )
    new_trans_id = int(df_trans["ID"].max()) if not df_trans.empty else 0

    ws = get_worksheet(IURAN_SHEET, IURAN_COLUMNS)
    df_iuran = load_iuran()
    new_id = _next_iuran_id(df_iuran)
    row = [new_id, minggu_label, nama, str(tanggal_bayar), new_trans_id]
    _retry(ws.append_row, row, value_input_option="USER_ENTERED")
    load_iuran.clear()
    return load_iuran()


def unmark_iuran_paid(minggu_label: str, nama: str):
    """Batalkan status sudah bayar: hapus transaksi terkait + catatan iuran."""
    df_iuran = load_iuran()
    match = df_iuran[(df_iuran["Minggu"] == minggu_label) & (df_iuran["Nama Anggota"] == nama)]
    if match.empty:
        return load_iuran()

    row = match.iloc[0]
    id_transaksi = int(row["ID Transaksi"])
    id_iuran = int(row["ID"])

    if id_transaksi:
        delete_transaksi(id_transaksi)

    ws = get_worksheet(IURAN_SHEET, IURAN_COLUMNS)
    row_idx = _find_row_index(ws, id_iuran)
    if row_idx is not None:
        _retry(ws.delete_rows, row_idx)
    load_iuran.clear()
    return load_iuran()


# ----------------------------------------------------------------------
# FORMAT & PERHITUNGAN
# ----------------------------------------------------------------------
def format_rupiah(value) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    minus = "-" if value < 0 else ""
    return f"{minus}Rp {abs(value):,.0f}".replace(",", ".")


def hitung_ringkasan(df: pd.DataFrame) -> dict:
    total_masuk = df.loc[df["Jenis"] == "Pemasukan", "Jumlah"].sum()
    total_keluar = df.loc[df["Jenis"] == "Pengeluaran", "Jumlah"].sum()
    saldo = total_masuk - total_keluar
    return {
        "total_pemasukan": total_masuk,
        "total_pengeluaran": total_keluar,
        "saldo": saldo,
    }


def hitung_ringkasan_per_kas(df: pd.DataFrame) -> dict:
    """Kembalikan ringkasan saldo terpisah untuk Kas Umum, Kas Proker, dan totalnya."""
    hasil = {}
    for kas in KAS_OPTIONS:
        hasil[kas] = hitung_ringkasan(df[df["Kas"] == kas])
    hasil["Total"] = hitung_ringkasan(df)
    return hasil


# ----------------------------------------------------------------------
# EXPORT EXCEL
# ----------------------------------------------------------------------
def generate_excel(df: pd.DataFrame, judul="Laporan Keuangan KKN") -> bytes:
    output = io.BytesIO()
    df_export = df.copy().sort_values("Tanggal")
    df_export["Tanggal"] = pd.to_datetime(df_export["Tanggal"]).dt.strftime("%d-%m-%Y")

    ringkasan_kas = hitung_ringkasan_per_kas(df)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, sheet_name="Detail Transaksi", index=False)

        ringkasan_rows = []
        for kas_label, r in ringkasan_kas.items():
            ringkasan_rows.append({
                "Kas": kas_label,
                "Total Pemasukan": r["total_pemasukan"],
                "Total Pengeluaran": r["total_pengeluaran"],
                "Saldo": r["saldo"],
            })
        pd.DataFrame(ringkasan_rows).to_excel(writer, sheet_name="Ringkasan", index=False)

        if not df.empty:
            rekap_kategori = (
                df.groupby(["Kas", "Jenis", "Kategori"])["Jumlah"].sum().reset_index()
            )
            rekap_kategori.to_excel(writer, sheet_name="Rekap per Kategori", index=False)

            rekap_proker = df.groupby(["Kas", "Proker", "Jenis"])["Jumlah"].sum().reset_index()
            rekap_proker.to_excel(writer, sheet_name="Rekap per Proker", index=False)

    return output.getvalue()


# ----------------------------------------------------------------------
# EXPORT PDF
# ----------------------------------------------------------------------
class LaporanPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "Laporan Keuangan KKN", ln=True, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, f"Dicetak: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Halaman {self.page_no()}", align="C")


def generate_pdf(df: pd.DataFrame, filter_info: str = "") -> bytes:
    pdf = LaporanPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    ringkasan_kas = hitung_ringkasan_per_kas(df)

    if filter_info:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, filter_info, ln=True)
        pdf.ln(1)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Ringkasan per Kas", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for kas_label in ["Kas Umum", "Kas Proker", "Total"]:
        r = ringkasan_kas[kas_label]
        pdf.cell(
            0, 6,
            f"{kas_label:<12} | Pemasukan: {format_rupiah(r['total_pemasukan'])}  "
            f"| Pengeluaran: {format_rupiah(r['total_pengeluaran'])}  "
            f"| Saldo: {format_rupiah(r['saldo'])}",
            ln=True,
        )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 9)
    col_widths = [20, 18, 22, 38, 40, 55, 27]
    headers = ["Tanggal", "Jenis", "Kas", "Proker", "Kategori", "Keterangan", "Jumlah"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    df_sorted = df.sort_values("Tanggal")
    for _, row in df_sorted.iterrows():
        tgl = pd.to_datetime(row["Tanggal"]).strftime("%d-%m-%Y")
        keterangan = str(row["Keterangan"])[:34]
        proker = str(row["Proker"])[:20]
        kategori = str(row["Kategori"])[:20]
        pdf.cell(col_widths[0], 6, tgl, border=1)
        pdf.cell(col_widths[1], 6, str(row["Jenis"]), border=1)
        pdf.cell(col_widths[2], 6, str(row["Kas"]), border=1)
        pdf.cell(col_widths[3], 6, proker, border=1)
        pdf.cell(col_widths[4], 6, kategori, border=1)
        pdf.cell(col_widths[5], 6, keterangan, border=1)
        pdf.cell(col_widths[6], 6, format_rupiah(row["Jumlah"]), border=1, align="R")
        pdf.ln()

    return bytes(pdf.output())
