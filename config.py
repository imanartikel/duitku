import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "DuitTracker")

# Telegram user ID lo — biar bot cuma bisa dipakai lo sendiri
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()]
