from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from config import dp
from database import add_user
from messages import WELCOME_MESSAGE

# Inline keyboard with two buttons for the guides
guide_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Гайд гастропутешествия", callback_data="guide_gastro")],
    [InlineKeyboardButton(text="Петербург до 1000 рублей", callback_data="guide_spb")]
])

async def send_welcome(message: types.Message):
    """Handler for the /start command. Sends a welcome message with an inline menu."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    add_user(user_id, username)
    await message.answer(WELCOME_MESSAGE, reply_markup=guide_menu)

# ✅ Регистрация обработчика команды /start для aiogram 3.x
dp.message.register(send_welcome, Command("start"))
