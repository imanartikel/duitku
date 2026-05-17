import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN or not TELEGRAM_TOKEN.strip():
    raise ValueError(
        "\n❌ [ERROR] TELEGRAM_TOKEN kosong atau tidak diset!\n"
        "Silakan buka Railway Dashboard -> tab 'Variables', lalu tambahkan:\n"
        "TELEGRAM_TOKEN = (Token bot Telegram dari BotFather Anda)\n"
    )

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
    raise ValueError(
        "\n❌ [ERROR] OPENAI_API_KEY kosong atau tidak diset!\n"
        "Silakan buka Railway Dashboard -> tab 'Variables', lalu tambahkan:\n"
        "OPENAI_API_KEY = (API key OpenAI Anda)\n"
    )

GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON", "credentials.json")
GOOGLE_CREDS_JSON_DATA = os.getenv("GOOGLE_CREDS_JSON_DATA")
if not GOOGLE_CREDS_JSON_DATA and not os.path.exists(GOOGLE_CREDS_JSON):
    raise ValueError(
        "\n❌ [ERROR] Kredensial Google Sheets tidak ditemukan!\n"
        "Silakan buka Railway Dashboard -> tab 'Variables', lalu tambahkan:\n"
        "GOOGLE_CREDS_JSON_DATA = (buka file credentials.json lokal, copy semua isinya, dan paste di sini)\n"
    )

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "DuitTracker")

# Telegram user ID lo — biar bot cuma bisa dipakai lo sendiri
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()]
