import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot and API configuration
BOT_TOKEN = os.getenv("TOKEN_BOT")
if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения TOKEN_BOT не установлена.")

admin_ids_raw = os.getenv("ADMIN_IDS")
if admin_ids_raw:
    ADMIN_IDS = [int(uid.strip()) for uid in admin_ids_raw.split(",") if uid.strip()]
else:
    ADMIN_IDS = []

# Initialize bot and dispatcher for aiogram 3.x
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
