import logging
import io
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import TELEGRAM_TOKEN, ALLOWED_USERS
from llm import parse_message, answer_query, format_transaction_confirm, verify_payment_ss
from sheets import append_transaction, append_transactions_bulk, get_monthly_summary, get_category_summary
from budget import set_budget, get_budget, check_budget_warnings, get_budget_status, KATEGORI_VALID

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *DuitTracker aktif!*\n\n"
        "*Catat transaksi:*\n"
        "• `makan siang 25` → Rp 25.000\n"
        "• `bayar listrik 200rb`\n"
        "• `gaji masuk 5jt`\n"
        "• `sayur 30 daging 80 telur 20`\n\n"
        "*Tanya:*\n"
        "• `berapa pengeluaran bulan ini?`\n"
        "• `paling boros di mana?`\n\n"
        "*Commands:*\n"
        "/summary — ringkasan bulan ini\n"
        "/kategori — total per kategori\n"
        "/budget — lihat budget\n"
        "/setbudget — atur budget\n"
        "/menu — semua command",
        parse_mode="Markdown",
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Menu DuitTracker*\n\n"
        "/summary — ringkasan bulan ini\n"
        "/kategori — total per kategori all-time\n"
        "/budget — lihat status budget bulan ini\n"
        "/setbudget `[kategori] [nominal]` — set budget\n\n"
        "Contoh set budget:\n"
        "`/setbudget Makan 1500000`\n"
        "`/setbudget Groceries 800000`\n"
        "`/setbudget Transport 500000`\n\n"
        "Kategori valid:\n"
        f"{', '.join(KATEGORI_VALID)}",
        parse_mode="Markdown",
    )


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    now = datetime.now()
    await update.message.reply_text("⏳ Ambil data...")
    try:
        s = get_monthly_summary(now.year, now.month)
        text = (
            f"📊 *Ringkasan {now.strftime('%B %Y')}*\n\n"
            f"💰 Masuk: Rp {s['total_masuk']:,.0f}\n"
            f"💸 Keluar: Rp {s['total_keluar']:,.0f}\n"
            f"📈 Saldo: Rp {s['saldo']:,.0f}\n"
            f"🧾 Transaksi: {s['jumlah_transaksi']}x\n\n"
            "*Per Kategori:*\n"
        )
        for kat, vals in sorted(s["per_kategori"].items(), key=lambda x: x[1]["pengeluaran"], reverse=True):
            if vals["pengeluaran"] > 0:
                text += f"• {kat}: Rp {vals['pengeluaran']:,.0f}\n"

        # Cek budget warnings
        warnings = check_budget_warnings(s)
        if warnings:
            text += "\n*⚠️ Budget Alert:*\n" + "\n".join(warnings)

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    now = datetime.now()
    await update.message.reply_text("⏳ Ambil data...")
    try:
        s = get_monthly_summary(now.year, now.month)
        per_kat = s.get("per_kategori", {})
        text = f"📂 *Kategori {now.strftime('%B %Y')}*\n\n"
        for kat, vals in sorted(per_kat.items(), key=lambda x: x[1]["pengeluaran"], reverse=True):
            if vals["pengeluaran"] > 0 or vals["pemasukan"] > 0:
                text += f"*{kat}*\n"
                if vals["pengeluaran"] > 0:
                    text += f"  💸 Rp {vals['pengeluaran']:,.0f}\n"
                if vals["pemasukan"] > 0:
                    text += f"  💰 Rp {vals['pemasukan']:,.0f}\n"
        if not per_kat:
            text += "_Belum ada transaksi bulan ini._"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    now = datetime.now()
    try:
        budget = get_budget()
        if not budget:
            await update.message.reply_text(
                "Belum ada budget yang diset.\n\n"
                "Gunakan: `/setbudget Makan 1500000`",
                parse_mode="Markdown"
            )
            return

        s = get_monthly_summary(now.year, now.month)
        per_kat = s.get("per_kategori", {})

        text = f"💰 *Budget {now.strftime('%B %Y')}*\n\n"
        for kat, limit in sorted(budget.items()):
            spent = per_kat.get(kat, {}).get("pengeluaran", 0)
            sisa = limit - spent
            pct = int(spent / limit * 100) if limit > 0 else 0

            if pct >= 100:
                bar = "🔴"
            elif pct >= 80:
                bar = "🟡"
            else:
                bar = "🟢"

            text += (
                f"{bar} *{kat}*\n"
                f"   {pct}% — Rp {spent:,.0f} / Rp {limit:,.0f}\n"
                f"   Sisa: Rp {sisa:,.0f}\n\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_setbudget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Format: `/setbudget [kategori] [nominal]`\n\n"
            "Contoh:\n"
            "`/setbudget Makan 1500000`\n"
            "`/setbudget Groceries 800000`\n\n"
            "Kategori valid: " + ", ".join(KATEGORI_VALID),
            parse_mode="Markdown"
        )
        return

    kategori = args[0].capitalize()
    if kategori not in KATEGORI_VALID:
        await update.message.reply_text(
            f"❌ Kategori `{kategori}` tidak valid.\n\n"
            "Kategori valid: " + ", ".join(KATEGORI_VALID),
            parse_mode="Markdown"
        )
        return

    try:
        raw = args[1].lower().replace("rb", "000").replace("k", "000").replace("jt", "000000")
        nominal = int(float(raw))
        if nominal < 1000:
            nominal *= 1000  # auto ribuan
        set_budget(kategori, nominal)
        await update.message.reply_text(
            f"✅ Budget *{kategori}* diset: Rp {nominal:,.0f}/bulan",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Nominal tidak valid: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    await update.message.reply_text("⏳ Lagi baca gambarnya...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        image_bytes = buf.getvalue()

        result = verify_payment_ss(image_bytes)

        if not result.get("valid"):
            await update.message.reply_text(
                "❌ Ga kebaca sebagai dokumen keuangan.\n"
                "Coba foto yang lebih jelas atau ketik manual aja."
            )
            return

        nominal = result.get("nominal", 0)
        keterangan = result.get("keterangan", "")
        tipe_doc = result.get("tipe", "lain")

        if nominal > 0:
            tipe_transaksi = "pengeluaran" if tipe_doc in ("struk", "tagihan") else "pemasukan"
            append_transaction({
                "tipe": tipe_transaksi,
                "kategori": "Lain-lain",
                "nominal": nominal,
                "deskripsi": keterangan,
                "catatan": "dari foto",
            })
            await update.message.reply_text(
                f"📸 *Foto terbaca!*\n"
                f"├ {keterangan}\n"
                f"├ Nominal: Rp {nominal:,.0f}\n"
                f"└ Dicatat sebagai *{tipe_transaksi}*\n\n"
                f"_Salah kategori? Ketik koreksinya._",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"📸 Terbaca: _{keterangan}_\n"
                f"Nominalnya ga kedeteksi. Ketik manual ya.",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"handle_photo error: {e}")
        await update.message.reply_text(f"❌ Error baca foto: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    text = update.message.text.strip()
    if not text:
        return

    parsed = parse_message(text)
    intent = parsed.get("intent", "unknown")

    if intent == "transaksi":
        try:
            items = parsed.get("items", [])
            if not items:
                await update.message.reply_text("❌ Ga ada transaksi yang terdeteksi.")
                return
            if len(items) == 1:
                append_transaction(items[0])
            else:
                append_transactions_bulk(items)

            reply = format_transaction_confirm(parsed)
            await update.message.reply_text(reply, parse_mode="Markdown")

            # Cek budget warning setelah catat
            now = datetime.now()
            s = get_monthly_summary(now.year, now.month)
            warnings = check_budget_warnings(s)
            if warnings:
                await update.message.reply_text(
                    "\n".join(warnings),
                    parse_mode="Markdown"
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Gagal catat: {e}")

    elif intent == "query":
        await update.message.reply_text("⏳ Bentar...")
        try:
            now = datetime.now()
            bulan = parsed.get("bulan") or now.month
            tahun = parsed.get("tahun") or now.year
            tipe_query = parsed.get("tipe_query", "umum")

            data_ctx = {}
            if tipe_query in ("ringkasan_bulanan", "umum"):
                s = get_monthly_summary(tahun, bulan)
                data_ctx["summary"] = s
                budget_status = get_budget_status(s)
                if budget_status:
                    data_ctx["budget"] = budget_status
            if tipe_query in ("per_kategori", "umum"):
                data_ctx["kategori"] = get_category_summary()

            await update.message.reply_text(answer_query(text, data_ctx))
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    else:
        await update.message.reply_text(
            "🤔 Ga ngerti. Ketik /menu untuk lihat panduan.",
            parse_mode="Markdown"
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("kategori", cmd_kategori))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("setbudget", cmd_setbudget))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
