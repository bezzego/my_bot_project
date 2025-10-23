import logging
from typing import Optional

from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import bot, dp
from database import (
    fetch_channel,
    get_user_reward_channels,
    record_reward_delivery,
)
from handlers.start import send_channel_menu
from messages import (
    NO_REWARDS_YET,
    REWARD_NAVIGATION_PROMPT,
    REWARD_READY_MESSAGE,
    REWARDS_LIST_TITLE,
    SUBSCRIPTION_CONFIRMED,
    SUBSCRIPTION_NOT_CONFIRMED,
    SUBSCRIPTION_PROMPT,
)


def _resolve_chat_identifier(channel_row) -> int | str:
    raw_value = channel_row["chat_identifier"]
    try:
        return int(raw_value)
    except (ValueError, TypeError):
        return raw_value


def _resolve_invite_link(channel_row) -> Optional[str]:
    link = channel_row["invite_link"]
    if link:
        return link
    identifier = channel_row["chat_identifier"]
    if isinstance(identifier, str) and identifier.startswith("@"):
        return f"https://t.me/{identifier[1:]}"
    return None


def _open_channel_keyboard(channel_id: int, invite_link: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    if invite_link:
        rows.append([InlineKeyboardButton(text="🔗 Открыть канал", url=invite_link)])
    rows.append([InlineKeyboardButton(text="✅ Я подписался — проверить", callback_data=f"channel:check:{channel_id}")])
    rows.append([InlineKeyboardButton(text="🔝 В меню", callback_data="channel:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Посмотреть все файлы", callback_data="channel:view_rewards")],
            [InlineKeyboardButton(text="🔝 Вернуться к меню", callback_data="channel:menu")],
        ]
    )


async def _is_user_subscribed(channel_row, user_id: int) -> bool:
    chat_identifier = _resolve_chat_identifier(channel_row)
    try:
        member = await bot.get_chat_member(chat_identifier, user_id)
        return member.status in {"member", "administrator", "creator"}
    except TelegramBadRequest as exc:
        logging.warning("Не удалось проверить подписку для канала %s: %s", channel_row["title"], exc)
    except Exception as exc:
        logging.error("Неожиданная ошибка при проверке подписки: %s", exc)
    return False


async def _send_lead_magnet(user_id: int, channel_row) -> bool:
    channel_title = channel_row["button_title"] or channel_row["title"]
    magnet_type = channel_row["magnet_type"]
    payload = channel_row["magnet_payload"]
    caption = channel_row["magnet_caption"]

    try:
        if magnet_type == "link":
            parts = [REWARD_READY_MESSAGE.format(channel_title=channel_title)]
            if caption:
                parts.append(caption)
            parts.append(f"🔗 {payload}")
            await bot.send_message(user_id, "\n\n".join(parts))
        else:
            await bot.send_message(user_id, REWARD_READY_MESSAGE.format(channel_title=channel_title))
            if magnet_type == "document":
                await bot.send_document(user_id, payload, caption=caption)
            elif magnet_type == "photo":
                await bot.send_photo(user_id, payload, caption=caption)
            elif magnet_type == "text":
                text_message = payload
                if caption:
                    text_message += f"\n\n{caption}"
                await bot.send_message(user_id, text_message)
            else:
                await bot.send_message(
                    user_id,
                    "Пока не могу отправить этот тип литмагнита. Свяжитесь с администратором.",
                )
                return False
    except TelegramBadRequest as exc:
        logging.error("Не удалось отправить литмагнит пользователю %s: %s", user_id, exc)
        await bot.send_message(
            user_id,
            "Не удалось отправить файл. Сообщите администратору, чтобы он проверил настройки канала.",
        )
        return False

    record_reward_delivery(user_id, channel_row["id"])
    await bot.send_message(user_id, REWARD_NAVIGATION_PROMPT, reply_markup=_navigation_keyboard())
    return True


@dp.callback_query(F.data == "channel:menu")
async def handle_menu_callback(call: types.CallbackQuery):
    await send_channel_menu(call)


@dp.callback_query(F.data == "channel:view_rewards")
async def handle_view_rewards(call: types.CallbackQuery):
    user_id = call.from_user.id
    rewards = get_user_reward_channels(user_id)
    await call.answer()

    if not rewards:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔝 Вернуться к меню", callback_data="channel:menu")]]
        )
        await call.message.answer(NO_REWARDS_YET, reply_markup=keyboard)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(row["button_title"] or row["title"]),
                    callback_data=f"channel:reward:{row['id']}",
                )
            ]
            for row in rewards
        ]
        + [[InlineKeyboardButton(text="🔝 В меню", callback_data="channel:menu")]]
    )
    await call.message.answer(REWARDS_LIST_TITLE, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("channel:open:"))
async def handle_channel_open(call: types.CallbackQuery):
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось найти канал.", show_alert=True)
        return

    channel = fetch_channel(channel_id)
    if not channel or not channel["is_active"]:
        await call.answer("Канал недоступен.", show_alert=True)
        return

    invite_link = _resolve_invite_link(channel)
    await call.answer()
    await call.message.answer(
        SUBSCRIPTION_PROMPT.format(channel_title=channel["title"]),
        reply_markup=_open_channel_keyboard(channel_id, invite_link),
    )


@dp.callback_query(F.data.startswith("channel:check:"))
async def handle_channel_check(call: types.CallbackQuery):
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось проверить канал.", show_alert=True)
        return

    channel = fetch_channel(channel_id)
    if not channel or not channel["is_active"]:
        await call.answer("Канал недоступен.", show_alert=True)
        return

    user_id = call.from_user.id
    is_subscribed = await _is_user_subscribed(channel, user_id)
    if not is_subscribed:
        await call.answer("Подписка не подтверждена.")
        await call.message.answer(SUBSCRIPTION_NOT_CONFIRMED.format(channel_title=channel["title"]))
        return

    await call.answer("Подписка подтверждена!")
    await call.message.answer(SUBSCRIPTION_CONFIRMED.format(channel_title=channel["title"]))
    await _send_lead_magnet(user_id, channel)


@dp.callback_query(F.data.startswith("channel:reward:"))
async def handle_reward_repeat(call: types.CallbackQuery):
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось определить канал.", show_alert=True)
        return

    channel = fetch_channel(channel_id)
    if not channel:
        await call.answer("Канал недоступен.", show_alert=True)
        return

    await call.answer()
    await _send_lead_magnet(call.from_user.id, channel)
