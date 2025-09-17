import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

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
CHANNEL_USERNAME_GASTRO_PETER = "@Gorbilet_puteshestviya_so_skidkoy"
CHANNEL_USERNAME_SMALL_PETER  = "@Malenkiy_Peterburzhec"

# File IDs of the PDF guides to send (replace these with actual file_ids obtained from Telegram)
GASTRO_GUIDE_FILE_ID = "<file_id_for_gastro_pdf>"
SMALL_PETER_FILE_ID  = "<file_id_for_small_peter_pdf>"

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)