from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import dp
from database import add_user, fetch_channels, get_user_reward_channels
from messages import MENU_PROMPT, NO_CHANNELS_MESSAGE, WELCOME_MESSAGE


def _build_channel_keyboard(channels, include_rewards_button: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=channel["title"], callback_data=f"channel:open:{channel['id']}")]
        for channel in channels
    ]
    if include_rewards_button:
        rows.append([InlineKeyboardButton(text="🔄 Мои материалы", callback_data="channel:view_rewards")])
    rows.append([InlineKeyboardButton(text="🔝 Обновить меню", callback_data="channel:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_channel_menu(target: types.Message | types.CallbackQuery):
    """Отправляет пользователю главное меню с доступными каналами."""
    user_id = target.from_user.id
    channels = fetch_channels()
    has_rewards = bool(get_user_reward_channels(user_id))

    if channels:
        keyboard = _build_channel_keyboard(channels, has_rewards)
        text = f"{WELCOME_MESSAGE}\n\n{MENU_PROMPT}"
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔁 Обновить", callback_data="channel:menu")]]
        )
        text = f"{WELCOME_MESSAGE}\n\n{NO_CHANNELS_MESSAGE}"

    if isinstance(target, types.CallbackQuery):
        await target.message.answer(text, reply_markup=keyboard)
        await target.answer()
    else:
        await target.answer(text, reply_markup=keyboard)


async def send_welcome(message: types.Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    add_user(user_id, username)
    await send_channel_menu(message)


dp.message.register(send_welcome, Command("start"))
