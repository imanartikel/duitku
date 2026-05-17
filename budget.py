import json
from pathlib import Path

BUDGET_FILE = "budget.json"

KATEGORI_VALID = [
    "Makan", "Groceries", "Transport", "Belanja",
    "Hiburan", "Kesehatan", "Tagihan", "Gaji",
    "Freelance", "Investasi", "Edukasi", "Rumah",
    "Kendaraan", "Amal", "Hadiah", "Lain-lain"
]


def load_budget() -> dict:
    path = Path(BUDGET_FILE)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_budget(data: dict):
    Path(BUDGET_FILE).write_text(json.dumps(data, indent=2))


def set_budget(kategori: str, nominal: int):
    data = load_budget()
    data[kategori] = nominal
    save_budget(data)


def get_budget() -> dict:
    return load_budget()


def check_budget_warnings(summary: dict) -> list:
    """
    Cek kategori yang udah lewat 80% atau over budget.
    Return list warning string.
    """
    budget = load_budget()
    warnings = []
    per_kat = summary.get("per_kategori", {})

    for kat, limit in budget.items():
        spent = per_kat.get(kat, {}).get("pengeluaran", 0)
        if limit <= 0:
            continue
        pct = spent / limit * 100
        if pct >= 100:
            warnings.append(f"🚨 *{kat}* over budget! Rp {spent:,.0f} / Rp {limit:,.0f} ({int(pct)}%)")
        elif pct >= 80:
            warnings.append(f"⚠️ *{kat}* udah {int(pct)}% — Rp {spent:,.0f} dari Rp {limit:,.0f}")

    return warnings


def get_budget_status(summary: dict) -> dict:
    """Return dict status budget per kategori untuk LLM context."""
    budget = load_budget()
    per_kat = summary.get("per_kategori", {})
    result = {}
    for kat, limit in budget.items():
        spent = per_kat.get(kat, {}).get("pengeluaran", 0)
        pct = (spent / limit * 100) if limit > 0 else 0
        result[kat] = {"spent": spent, "limit": limit, "pct": pct}
    return result
