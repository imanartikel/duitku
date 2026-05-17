import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from config import GOOGLE_CREDS_JSON, SPREADSHEET_NAME

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Tanggal", "Waktu", "Tipe", "Kategori", "Nominal", "Deskripsi", "Catatan"]


def get_worksheet():
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_JSON, scopes=SCOPES)
    client = gspread.authorize(creds)
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(SPREADSHEET_NAME)
        spreadsheet.share(None, perm_type="anyone", role="writer")

    try:
        ws = spreadsheet.worksheet("Transaksi")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Transaksi", rows=5000, cols=10)
        ws.append_row(HEADERS)
        ws.format("A1:G1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
        })
    return ws


def append_transaction(data: dict):
    ws = get_worksheet()
    now = datetime.now()
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        data.get("tipe", "pengeluaran").capitalize(),
        data.get("kategori", "Lain-lain"),
        data.get("nominal", 0),
        data.get("deskripsi", ""),
        data.get("catatan", ""),
    ]
    ws.append_row(row)
    return row


def append_transactions_bulk(items: list):
    """Catat multiple transaksi sekaligus."""
    ws = get_worksheet()
    now = datetime.now()
    rows = []
    for data in items:
        rows.append([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M"),
            data.get("tipe", "pengeluaran").capitalize(),
            data.get("kategori", "Lain-lain"),
            data.get("nominal", 0),
            data.get("deskripsi", ""),
            data.get("catatan", ""),
        ])
    ws.append_rows(rows)
    return rows


def get_all_transactions():
    ws = get_worksheet()
    return ws.get_all_records()


def get_monthly_summary(year: int, month: int):
    records = get_all_transactions()
    filtered = []
    for r in records:
        try:
            d = datetime.strptime(r["Tanggal"], "%Y-%m-%d")
            if d.year == year and d.month == month:
                filtered.append(r)
        except Exception:
            continue

    total_masuk = sum(r["Nominal"] for r in filtered if str(r["Tipe"]).lower() == "pemasukan")
    total_keluar = sum(r["Nominal"] for r in filtered if str(r["Tipe"]).lower() == "pengeluaran")

    kategori_map = {}
    for r in filtered:
        kat = r.get("Kategori", "Lain-lain")
        nom = r.get("Nominal", 0)
        tipe = str(r.get("Tipe", "")).lower()
        if kat not in kategori_map:
            kategori_map[kat] = {"pemasukan": 0, "pengeluaran": 0}
        kategori_map[kat][tipe] = kategori_map[kat].get(tipe, 0) + nom

    return {
        "bulan": f"{year}-{month:02d}",
        "total_masuk": total_masuk,
        "total_keluar": total_keluar,
        "saldo": total_masuk - total_keluar,
        "per_kategori": kategori_map,
        "jumlah_transaksi": len(filtered),
    }


def get_category_summary():
    records = get_all_transactions()
    kategori_map = {}
    for r in records:
        kat = r.get("Kategori", "Lain-lain")
        nom = r.get("Nominal", 0)
        tipe = str(r.get("Tipe", "")).lower()
        if kat not in kategori_map:
            kategori_map[kat] = {"pemasukan": 0, "pengeluaran": 0}
        kategori_map[kat][tipe] = kategori_map[kat].get(tipe, 0) + nom
    return kategori_map
