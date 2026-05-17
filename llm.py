from openai import OpenAI
import json
import base64
from datetime import datetime
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"

SYSTEM_PARSE = """Kamu adalah parser transaksi keuangan Indonesia.

Tentukan intent:
1. TRANSAKSI - user mencatat pengeluaran atau pemasukan
2. QUERY - user bertanya tentang keuangan
3. UNKNOWN - tidak relevan

Untuk TRANSAKSI, kembalikan JSON dengan array items:
{
  "intent": "transaksi",
  "items": [
    {
      "tipe": "pengeluaran" atau "pemasukan",
      "kategori": salah satu dari [Makan, Groceries, Transport, Belanja, Hiburan, Kesehatan, Tagihan, Gaji, Freelance, Investasi, Edukasi, Rumah, Kendaraan, Amal, Hadiah, Lain-lain],
      "nominal": angka tanpa titik/koma,
      "deskripsi": deskripsi singkat item ini
    }
  ]
}

Untuk QUERY, kembalikan JSON:
{
  "intent": "query",
  "tipe_query": "ringkasan_bulanan" atau "per_kategori" atau "umum",
  "bulan": angka bulan jika disebutkan (null jika tidak),
  "tahun": angka tahun jika disebutkan (null jika tidak)
}

Untuk UNKNOWN:
{"intent": "unknown"}

ATURAN NOMINAL (PENTING):
- Konversi: 15rb=15000, 500k=500000, 5jt=5000000, 1.5jt=1500000
- Jika nominal < 1000 dan tidak ada satuan, anggap ribuan. Contoh: "25" = 25000, "150" = 150000, "8" = 8000
- Jika nominal >= 1000, gunakan apa adanya

ATURAN KATEGORI & MULTIPLE ITEMS (SANGAT PENTING):
- Groceries = bahan makanan mentah: ayam, daging, sayur, buah, telur, beras, bumbu, ikan, dll
- Makan = makanan siap makan: warteg, restoran, jajan, kopi, bakso, dll
- Jika user menginput BANYAK transaksi dalam SATU pesan (misal: "sayur 20rb, ayam 30rb, bensin 15"), kamu WAJIB memecahnya menjadi BANYAK objek terpisah di dalam array `items`. Jangan digabungkan jadi satu!

Kembalikan HANYA JSON, tanpa penjelasan."""

SYSTEM_ANSWER = """Kamu asisten keuangan pribadi. Jawab singkat dan jelas pakai emoji secukupnya.
Format angka: Rp 1.500.000. Bahasa Indonesia."""

SYSTEM_VERIFY_SS = """Kamu verifikator screenshot keuangan. Analisis gambar dan kembalikan JSON:
{
  "valid": true atau false,
  "tipe": "bukti_transfer" atau "struk" atau "tagihan" atau "lain",
  "nominal": angka tanpa titik/koma (0 jika tidak ada),
  "keterangan": deskripsi singkat isi gambar (max 10 kata)
}
valid=true jika gambar adalah dokumen keuangan yang jelas terbaca.
Kembalikan HANYA JSON."""


def parse_message(text: str) -> dict:
    try:
        res = client.chat.completions.create(
            model=MODEL,
            max_tokens=400,
            messages=[
                {"role": "system", "content": SYSTEM_PARSE},
                {"role": "user", "content": text},
            ],
        )
        raw = res.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        return {"intent": "unknown", "error": str(e)}


def verify_payment_ss(image_bytes: bytes) -> dict:
    try:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        res = client.chat.completions.create(
            model=MODEL,
            max_tokens=200,
            messages=[
                {"role": "system", "content": SYSTEM_VERIFY_SS},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": "Analisis gambar ini."},
                    ],
                },
            ],
        )
        raw = res.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        return {"valid": False, "error": str(e)}


def answer_query(query_text: str, data: dict) -> str:
    now = datetime.now()
    context_parts = [f"Sekarang: {now.strftime('%d %B %Y')}"]

    if "summary" in data:
        s = data["summary"]
        context_parts.append(
            f"\nRingkasan bulan {s['bulan']}:\n"
            f"- Pemasukan: Rp {s['total_masuk']:,.0f}\n"
            f"- Pengeluaran: Rp {s['total_keluar']:,.0f}\n"
            f"- Saldo: Rp {s['saldo']:,.0f}\n"
            f"- Jumlah transaksi: {s['jumlah_transaksi']}"
        )
        if s["per_kategori"]:
            context_parts.append("\nPer kategori:")
            for kat, vals in s["per_kategori"].items():
                if vals["pengeluaran"] > 0:
                    context_parts.append(f"  {kat}: keluar Rp {vals['pengeluaran']:,.0f}")
                if vals["pemasukan"] > 0:
                    context_parts.append(f"  {kat}: masuk Rp {vals['pemasukan']:,.0f}")

    if "kategori" in data:
        context_parts.append("\nTotal all-time per kategori:")
        for kat, vals in data["kategori"].items():
            context_parts.append(f"  {kat}: keluar Rp {vals['pengeluaran']:,.0f} | masuk Rp {vals['pemasukan']:,.0f}")

    if "budget" in data:
        context_parts.append("\nBudget bulan ini:")
        for kat, info in data["budget"].items():
            pct = int(info["pct"])
            context_parts.append(f"  {kat}: {pct}% terpakai (Rp {info['spent']:,.0f} dari Rp {info['limit']:,.0f})")

    context = "\n".join(context_parts)
    try:
        res = client.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_ANSWER},
                {"role": "user", "content": f"Data keuangan saya:\n{context}\n\nPertanyaan: {query_text}"},
            ],
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


def format_transaction_confirm(data: dict) -> str:
    items = data.get("items", [])
    if not items:
        return "❌ Ga ada transaksi yang terdeteksi."

    if len(items) == 1:
        item = items[0]
        tipe = item.get("tipe", "pengeluaran")
        emoji = "💸" if tipe == "pengeluaran" else "💰"
        nominal = item.get("nominal", 0)
        return (
            f"{emoji} *Tercatat!*\n"
            f"├ {tipe.capitalize()} — {item.get('kategori', 'Lain-lain')}\n"
            f"├ Rp {nominal:,.0f}\n"
            f"└ {item.get('deskripsi', '')}"
        )
    else:
        total = sum(i.get("nominal", 0) for i in items)
        lines = [f"💸 *{len(items)} transaksi tercatat!*\n"]
        for item in items:
            nom = item.get("nominal", 0)
            lines.append(f"• {item.get('deskripsi', 'item')} — Rp {nom:,.0f}")
        lines.append(f"\n*Total: Rp {total:,.0f}*")
        return "\n".join(lines)
