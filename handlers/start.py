from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import dp
from database import add_user
from messages import WELCOME_MESSAGE

# Inline keyboard with two buttons for the guides
guide_menu = InlineKeyboardMarkup(row_width=1)
btn_gastro = InlineKeyboardButton(text="Гайд гастропутешествия", callback_data="guide_gastro")
btn_spb   = InlineKeyboardButton(text="Петербург до 1000 рублей", callback_data="guide_spb")
guide_menu.add(btn_gastro, btn_spb)  # Each button on its own row (row_width=1)

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    """Handler for the /start command. Sends a welcome message with an inline menu."""
    # Save user to database (store ID and username)
    user_id = message.from_user.id
    username = message.from_user.username or ""
    add_user(user_id, username)
    # Send welcome message with the inline keyboard menu
    await message.answer(WELCOME_MESSAGE, reply_markup=guide_menu)