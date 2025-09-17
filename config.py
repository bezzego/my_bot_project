import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

# Load environment variables from .env file
load_dotenv()

# Bot and API configuration
BOT_TOKEN = os.getenv("TOKEN_BOT")  # Telegram Bot API token
ADMIN_IDS = os.getenv("ADMIN_IDS")  # Comma-separated admin IDs from .env
if ADMIN_IDS:
    ADMIN_IDS = [int(uid) for uid in ADMIN_IDS.split(",")]
else:
    ADMIN_IDS = []

# Channel IDs and usernames for subscription checks
CHANNEL_ID_GASTRO_PETER = int(os.getenv("CHANNEL_ID_GASTRO_PETER"))
CHANNEL_ID_SMALL_PETER = int(os.getenv("CHANNEL_ID_SMALL_PETER"))
CHANNEL_USERNAME_GASTRO_PETER = "@gorbilet_travel"
CHANNEL_USERNAME_SMALL_PETER  = "@gorbilet_deti"

# File IDs of the PDF guides to send (replace these with actual file_ids obtained from Telegram)
GASTRO_GUIDE_FILE_ID = "BQACAgIAAxkBAAMOaMpx34E1-CLMhVgCXedLTeKHcScAAtJ0AAJVyVBK34g87qVQlEk2BA"
SMALL_PETER_FILE_ID  = "BQACAgIAAxkBAAM4aMqwjJyvQt2PF05-g4usEKMAAdh-AAIIeAACVclQSjI0V8cPyvI3NgQ"

# Initialize bot and dispatcher for aiogram 3.x
# В aiogram 3.x parse_mode передается через DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
# Dispatcher создается без аргументов, бот передаем при запуске polling
dp = Dispatcher()