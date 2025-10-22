import asyncio
import logging
from typing import Optional, Tuple

from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_IDS, bot, dp
from database import (
    add_channel,
    fetch_channel,
    fetch_channels,
    get_all_user_ids,
    get_reward_stats,
    get_user_count,
    set_channel_active,
    update_channel,
)


class AddChannelStates(StatesGroup):
    waiting_for_chat_identifier = State()
    waiting_for_invite_link = State()
    waiting_for_magnet_type = State()
    waiting_for_magnet_payload = State()
    waiting_for_caption = State()


class EditMagnetStates(StatesGroup):
    waiting_for_channel_choice = State()
    waiting_for_magnet_type = State()
    waiting_for_magnet_payload = State()
    waiting_for_caption = State()


class DeleteChannelStates(StatesGroup):
    waiting_for_channel_choice = State()
    waiting_for_confirmation = State()


class BroadcastStates(StatesGroup):
    waiting_for_content_type = State()
    waiting_for_content = State()
    waiting_for_button = State()
    waiting_for_confirmation = State()


MAGNET_TYPES = {
    "document": "📎 Файл",
    "link": "🔗 Ссылка",
    "text": "📝 Текст",
    "photo": "🖼 Изображение",
}

BROADCAST_TYPES = {
    "text": "📝 Текст",
    "photo": "🖼 Фото",
    "video": "🎥 Видео",
    "document": "📎 Файл",
}


async def send_admin_menu(event: types.Message | types.CallbackQuery):
    """Отправляет или обновляет главное меню администратора."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin:add")],
            [InlineKeyboardButton(text="✏️ Изменить литмагнит", callback_data="admin:edit")],
            [InlineKeyboardButton(text="🗑 Удалить канал", callback_data="admin:delete")],
            [InlineKeyboardButton(text="📋 Список каналов", callback_data="admin:list")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin:broadcast")],
        ]
    )

    text = "Меню администратора:"
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(handler):
    async def wrapper(event: types.Message | types.CallbackQuery, *args, **kwargs):
        user_id = event.from_user.id
        if not is_admin(user_id):
            if isinstance(event, types.Message):
                await event.answer("Эта команда доступна только администраторам.")
            else:
                await event.answer("Недостаточно прав.")
            return
        return await handler(event, *args, **kwargs)

    return wrapper


def is_cancel_text(text: Optional[str]) -> bool:
    return text is not None and text.strip().lower() in {"отмена", "cancel", "/cancel"}


def is_skip_text(text: Optional[str]) -> bool:
    return text is not None and text.strip().lower() in {"пропустить", "skip", "нет"}


def magnet_type_keyboard(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"{prefix}:{key}")]
        for key, label in MAGNET_TYPES.items()
    ]
    buttons.append([InlineKeyboardButton(text="🔝 В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"admin:broadcast:type:{key}")]
        for key, label in BROADCAST_TYPES.items()
    ]
    buttons.append([InlineKeyboardButton(text="🔝 В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_channel_list_keyboard(action: str, include_inactive: bool = False) -> InlineKeyboardMarkup:
    channels = fetch_channels(active_only=not include_inactive)
    if not channels:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔝 В меню", callback_data="admin:menu")]]
        )

    inline_keyboard = []
    for channel in channels:
        label = channel["title"]
        if not channel["is_active"]:
            label += " (отключен)"
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{action}:{channel['id']}",
                )
            ]
        )
    inline_keyboard.append([InlineKeyboardButton(text="🔝 В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def parse_chat_reference(value: str) -> Tuple[Optional[str | int], Optional[str]]:
    """Пытается выделить идентификатор чата и ссылку из пользовательского ввода."""
    text = value.strip()
    invite_link: Optional[str] = None

    if text.startswith("@"):
        chat_identifier: Optional[str | int] = text
        invite_link = f"https://t.me/{text[1:]}"
        return chat_identifier, invite_link

    if text.startswith("http://") or text.startswith("https://"):
        invite_link = text
        slug = text.rstrip("/").split("/")[-1]
        slug = slug.split("?")[0]
        if slug.startswith("+") or not slug:
            # Для приватных ссылок требуется явный ID
            return None, invite_link
        chat_identifier = f"@{slug}"
        return chat_identifier, invite_link

    try:
        chat_identifier = int(text)
        return chat_identifier, invite_link
    except ValueError:
        return None, invite_link


def extract_magnet_payload(message: types.Message, magnet_type: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Возвращает (payload, caption, error_message) для заданного типа литмагнита."""
    if magnet_type == "document":
        if message.document:
            return message.document.file_id, message.caption, None
        return None, None, "Пожалуйста, отправьте документ."
    if magnet_type == "photo":
        if message.photo:
            return message.photo[-1].file_id, message.caption, None
        return None, None, "Пожалуйста, отправьте изображение."
    if magnet_type == "video":
        if message.video:
            return message.video.file_id, message.caption, None
        return None, None, "Пожалуйста, отправьте видео."
    if magnet_type == "link":
        if message.text:
            return message.text.strip(), None, None
        return None, None, "Пожалуйста, отправьте ссылку текстом."
    if magnet_type == "text":
        if message.text:
            return message.text, None, None
        return None, None, "Пожалуйста, отправьте текстовое сообщение."
    return None, None, "Неизвестный тип литмагнита. Начните заново."


@dp.message(Command("admin"))
@admin_only
async def handle_admin_command(message: types.Message, **_):
    await send_admin_menu(message)


@dp.callback_query(F.data == "admin:menu")
@admin_only
async def handle_admin_menu_callback(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    await send_admin_menu(call)


@dp.callback_query(F.data == "admin:add")
@admin_only
async def start_add_channel(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    await call.answer()
    await call.message.answer(
        "Шаг 1/3. Отправьте ID или @username канала, который нужно добавить.\n"
        "Можно также отправить прямую ссылку, но для приватных ссылок потребуется числовой ID.\n"
        "Напишите 'Отмена' для выхода."
    )
    await state.set_state(AddChannelStates.waiting_for_chat_identifier)


@dp.message(AddChannelStates.waiting_for_chat_identifier)
async def process_add_chat_identifier(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текст с ID или ссылкой на канал.")
        return

    if is_cancel_text(message.text):
        await message.answer("Добавление канала отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    chat_identifier, invite_link = parse_chat_reference(message.text)
    if chat_identifier is None:
        await message.answer(
            "Не удалось определить канал. Отправьте username в формате @channel или числовой ID.\n"
            "Если у вас только приватная ссылка-приглашение, сначала получите ID канала и повторите попытку."
        )
        return

    try:
        chat = await bot.get_chat(chat_identifier)
    except TelegramBadRequest:
        await message.answer(
            "Не удалось получить информацию о канале. Убедитесь, что бот добавлен в канал как администратор "
            "и что указан корректный ID/username."
        )
        return

    title = getattr(chat, "title", None) or getattr(chat, "full_name", None) or chat.username or "Без названия"
    if not invite_link:
        username = getattr(chat, "username", None)
        if username:
            invite_link = f"https://t.me/{username}"
        elif message.text.startswith("http://") or message.text.startswith("https://"):
            invite_link = message.text.strip()

    await state.update_data(
        chat_identifier=str(chat_identifier),
        channel_title=title,
        invite_link=invite_link,
    )

    if invite_link:
        await message.answer(
            f"Будет использована ссылка для кнопки:\n{invite_link}\n"
            "Если нужно указать другую, отправьте новую ссылку. Для пропуска напишите 'пропустить'."
        )
    else:
        await message.answer(
            "Отправьте ссылку, которую будем показывать пользователям (например, приглашение) "
            "или напишите 'пропустить', чтобы оставить поле пустым."
        )

    await state.set_state(AddChannelStates.waiting_for_invite_link)


@dp.message(AddChannelStates.waiting_for_invite_link)
async def process_add_invite_link(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовую ссылку или напишите 'пропустить'.")
        return

    if is_cancel_text(message.text):
        await message.answer("Добавление канала отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    data = await state.get_data()
    current_link = data.get("invite_link")

    if is_skip_text(message.text):
        invite_link = current_link
    else:
        link = message.text.strip()
        if not (link.startswith("http://") or link.startswith("https://")):
            await message.answer("Ссылка должна начинаться с http:// или https://. Повторите ввод.")
            return
        invite_link = link

    await state.update_data(invite_link=invite_link)
    await message.answer(
        "Шаг 2/3. Выберите тип литмагнита для этого канала:",
        reply_markup=magnet_type_keyboard("admin:add:type"),
    )
    await state.set_state(AddChannelStates.waiting_for_magnet_type)


@dp.callback_query(AddChannelStates.waiting_for_magnet_type, F.data.startswith("admin:add:type:"))
@admin_only
async def process_add_magnet_type(call: types.CallbackQuery, state: FSMContext, **_):
    _, _, _, magnet_type = call.data.split(":")
    if magnet_type not in MAGNET_TYPES:
        await call.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(magnet_type=magnet_type)
    await call.answer()

    if magnet_type == "document":
        prompt = (
            "Шаг 3/3. Отправьте файл (документ). Можно сразу добавить подпись — она станет описанием литмагнита."
        )
    elif magnet_type == "photo":
        prompt = (
            "Шаг 3/3. Отправьте изображение. Можно сразу добавить подпись — она станет описанием литмагнита."
        )
    elif magnet_type == "link":
        prompt = "Шаг 3/3. Отправьте ссылку, которую получат пользователи."
    else:
        prompt = "Шаг 3/3. Отправьте текст литмагнита."

    await call.message.answer(prompt + "\nНапишите 'Отмена' для выхода.")
    await state.set_state(AddChannelStates.waiting_for_magnet_payload)


@dp.message(AddChannelStates.waiting_for_magnet_payload)
async def process_add_magnet_payload(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    cancel_candidate = message.text or message.caption
    if is_cancel_text(cancel_candidate):
        await message.answer("Добавление канала отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    data = await state.get_data()
    magnet_type = data.get("magnet_type")
    if not magnet_type:
        await message.answer("Тип литмагнита не выбран. Начните процесс заново.")
        await state.clear()
        await send_admin_menu(message)
        return

    magnet_payload, caption, error = extract_magnet_payload(message, magnet_type)
    if error:
        await message.answer(error)
        if error.startswith("Неизвестный"):
            await state.clear()
            await send_admin_menu(message)
        return

    await state.update_data(magnet_payload=magnet_payload)

    needs_caption = magnet_type in {"document", "photo", "link"}

    if caption:
        await state.update_data(magnet_caption=caption)
        await finalize_channel_creation(message, state)
    elif needs_caption:
        await message.answer(
            "Отправьте текст, который прикрепим к литмагниту, или напишите 'пропустить', если он не нужен."
        )
        await state.set_state(AddChannelStates.waiting_for_caption)
    else:
        await state.update_data(magnet_caption=None)
        await finalize_channel_creation(message, state)


@dp.message(AddChannelStates.waiting_for_caption)
async def process_add_caption(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текст или напишите 'пропустить'.")
        return

    if is_cancel_text(message.text):
        await message.answer("Добавление канала отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    caption = None if is_skip_text(message.text) else message.text
    await state.update_data(magnet_caption=caption)
    await finalize_channel_creation(message, state)
def magnet_type_label(value: str) -> str:
    return MAGNET_TYPES.get(value, value)


def build_link_keyboard(text: Optional[str], url: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    if text and url:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])
    return None


def shorten_text(value: str, limit: int = 120) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


async def finalize_channel_creation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_title = data.get("channel_title", "Без названия")
    chat_identifier = data.get("chat_identifier")
    invite_link = data.get("invite_link")
    magnet_type = data.get("magnet_type")
    magnet_payload = data.get("magnet_payload")
    magnet_caption = data.get("magnet_caption")

    if not all([channel_title, chat_identifier, magnet_type, magnet_payload]):
        await message.answer("Не удалось сохранить канал — данные заполнены не полностью. Попробуйте снова.")
        return

    channel_id = add_channel(
        title=channel_title,
        chat_identifier=str(chat_identifier),
        invite_link=invite_link,
        magnet_type=magnet_type,
        magnet_payload=magnet_payload,
        magnet_caption=magnet_caption,
    )

    await state.clear()
    summary_lines = [
        f"Канал «{channel_title}» успешно добавлен (ID записи: {channel_id}).",
        f"Тип литмагнита: {magnet_type_label(magnet_type)}",
    ]
    if invite_link:
        summary_lines.append(f"Ссылка для кнопки: {invite_link}")

    await message.answer("\n".join(summary_lines))
    await send_admin_menu(message)


@dp.callback_query(F.data == "admin:list")
@admin_only
async def handle_admin_list(call: types.CallbackQuery, state: FSMContext, **_):
    channels = fetch_channels(active_only=False)
    await call.answer()

    if not channels:
        await call.message.answer("Каналы ещё не добавлены.")
        return

    lines = []
    for channel in channels:
        status = "✅ Активен" if channel["is_active"] else "🚫 Отключен"
        lines.append(f"{channel['id']}. {channel['title']} — {status}")
        lines.append(f"   Идентификатор: {channel['chat_identifier']}")
        lines.append(f"   Тип: {magnet_type_label(channel['magnet_type'])}")
        if channel["invite_link"]:
            lines.append(f"   Ссылка: {channel['invite_link']}")
        if channel["magnet_caption"]:
            lines.append(f"   Описание: {shorten_text(channel['magnet_caption'])}")
        lines.append("")

    await call.message.answer("\n".join(lines).strip())


@dp.callback_query(F.data == "admin:edit")
@admin_only
async def start_edit_magnet(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    channels = fetch_channels()
    await call.answer()

    if not channels:
        await call.message.answer("Активных каналов нет. Сначала добавьте канал.")
        return

    await call.message.answer(
        "Выберите канал, для которого нужно изменить литмагнит:",
        reply_markup=build_channel_list_keyboard("admin:edit"),
    )
    await state.set_state(EditMagnetStates.waiting_for_channel_choice)


@dp.callback_query(EditMagnetStates.waiting_for_channel_choice, F.data.startswith("admin:edit:"))
@admin_only
async def choose_channel_for_edit(call: types.CallbackQuery, state: FSMContext, **_):
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось определить канал.", show_alert=True)
        return

    channel = fetch_channel(channel_id)
    if not channel:
        await call.answer("Канал не найден.", show_alert=True)
        return

    await state.update_data(
        channel_id=channel_id,
        channel_title=channel["title"],
    )
    await call.answer()
    await call.message.answer(
        f"Изменяем литмагнит для «{channel['title']}».\n"
        f"Текущий тип: {magnet_type_label(channel['magnet_type'])}.",
        reply_markup=magnet_type_keyboard("admin:edit:type"),
    )
    await state.set_state(EditMagnetStates.waiting_for_magnet_type)


@dp.callback_query(EditMagnetStates.waiting_for_magnet_type, F.data.startswith("admin:edit:type:"))
@admin_only
async def process_edit_magnet_type(call: types.CallbackQuery, state: FSMContext, **_):
    try:
        magnet_type = call.data.split(":")[-1]
    except IndexError:
        await call.answer("Не удалось распознать тип.", show_alert=True)
        return

    if magnet_type not in MAGNET_TYPES:
        await call.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(magnet_type=magnet_type)
    await call.answer()

    if magnet_type == "document":
        prompt = "Отправьте новый файл-документ. Подпись при желании станет описанием."
    elif magnet_type == "photo":
        prompt = "Отправьте новое изображение. Подпись при желании станет описанием."
    elif magnet_type == "link":
        prompt = "Отправьте новую ссылку для пользователей."
    else:
        prompt = "Отправьте новый текст литмагнита."

    await call.message.answer(prompt + "\nНапишите 'Отмена' для отмены.")
    await state.set_state(EditMagnetStates.waiting_for_magnet_payload)


@dp.message(EditMagnetStates.waiting_for_magnet_payload)
async def process_edit_magnet_payload(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    cancel_candidate = message.text or message.caption
    if is_cancel_text(cancel_candidate):
        await message.answer("Изменение литмагнита отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    data = await state.get_data()
    magnet_type = data.get("magnet_type")
    if not magnet_type:
        await message.answer("Не выбран тип литмагнита. Начните заново.")
        await state.clear()
        await send_admin_menu(message)
        return

    magnet_payload, caption, error = extract_magnet_payload(message, magnet_type)
    if error:
        await message.answer(error)
        if error.startswith("Неизвестный"):
            await state.clear()
            await send_admin_menu(message)
        return

    await state.update_data(magnet_payload=magnet_payload)
    needs_caption = magnet_type in {"document", "photo", "link"}

    if caption:
        await state.update_data(magnet_caption=caption)
        await finalize_magnet_update(message, state)
    elif needs_caption:
        await message.answer(
            "Отправьте текст-описание для литмагнита или напишите 'пропустить', чтобы оставить поле пустым."
        )
        await state.set_state(EditMagnetStates.waiting_for_caption)
    else:
        await state.update_data(magnet_caption=None)
        await finalize_magnet_update(message, state)


@dp.message(EditMagnetStates.waiting_for_caption)
async def process_edit_caption(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текст или напишите 'пропустить'.")
        return

    if is_cancel_text(message.text):
        await message.answer("Изменение литмагнита отменено.")
        await state.clear()
        await send_admin_menu(message)
        return

    caption = None if is_skip_text(message.text) else message.text
    await state.update_data(magnet_caption=caption)
    await finalize_magnet_update(message, state)


async def finalize_magnet_update(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data.get("channel_id")
    channel_title = data.get("channel_title", "неизвестный канал")
    magnet_type = data.get("magnet_type")
    magnet_payload = data.get("magnet_payload")
    magnet_caption = data.get("magnet_caption")

    if not channel_id or not magnet_type or not magnet_payload:
        await message.answer("Не удалось обновить литмагнит — недостаточно данных. Попробуйте снова.")
        await state.clear()
        await send_admin_menu(message)
        return

    updated = update_channel(
        channel_id,
        magnet_type=magnet_type,
        magnet_payload=magnet_payload,
        magnet_caption=magnet_caption,
    )

    await state.clear()
    if updated:
        await message.answer(
            f"Литмагнит для «{channel_title}» обновлён.\nТип: {magnet_type_label(magnet_type)}."
        )
    else:
        await message.answer("Не удалось обновить запись. Проверьте данные и повторите попытку.")

    await send_admin_menu(message)


@dp.callback_query(F.data == "admin:delete")
@admin_only
async def start_delete_channel(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    channels = fetch_channels()
    await call.answer()

    if not channels:
        await call.message.answer("Активных каналов нет.")
        return

    await call.message.answer(
        "Выберите канал, который нужно отключить:",
        reply_markup=build_channel_list_keyboard("admin:delete"),
    )
    await state.set_state(DeleteChannelStates.waiting_for_channel_choice)


@dp.callback_query(DeleteChannelStates.waiting_for_channel_choice, F.data.startswith("admin:delete:"))
@admin_only
async def confirm_delete_channel(call: types.CallbackQuery, state: FSMContext, **_):
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось определить канал.", show_alert=True)
        return

    channel = fetch_channel(channel_id)
    if not channel:
        await call.answer("Канал не найден.", show_alert=True)
        return

    await state.update_data(channel_id=channel_id, channel_title=channel["title"])
    await call.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, отключить",
                    callback_data=f"admin:delete:confirm:{channel_id}",
                )
            ],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data="admin:menu")],
        ]
    )
    await call.message.answer(
        f"Вы уверены, что хотите отключить канал «{channel['title']}»?\n"
        "Его кнопка исчезнет из меню пользователей, но данные можно будет восстановить вручную.",
        reply_markup=keyboard,
    )
    await state.set_state(DeleteChannelStates.waiting_for_confirmation)


@dp.callback_query(DeleteChannelStates.waiting_for_confirmation, F.data.startswith("admin:delete:confirm:"))
@admin_only
async def complete_delete_channel(call: types.CallbackQuery, state: FSMContext, **_):
    data = await state.get_data()
    stored_id = data.get("channel_id")
    try:
        channel_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Не удалось определить канал.", show_alert=True)
        return

    if stored_id and stored_id != channel_id:
        await call.answer("Канал не совпадает с выбранным ранее. Повторите процедуру.", show_alert=True)
        await state.clear()
        await send_admin_menu(call)
        return

    channel = fetch_channel(channel_id)
    if not channel:
        await call.answer("Канал не найден.", show_alert=True)
        await state.clear()
        await send_admin_menu(call)
        return

    await call.answer()
    await state.clear()

    if set_channel_active(channel_id, False):
        await call.message.answer(f"Канал «{channel['title']}» отключён и исчезнет из меню пользователей.")
    else:
        await call.message.answer("Не удалось обновить статус канала. Повторите попытку.")

    await send_admin_menu(call)


@dp.callback_query(F.data == "admin:stats")
@admin_only
async def handle_admin_stats(call: types.CallbackQuery, state: FSMContext, **_):
    await call.answer()
    total_users = get_user_count()
    stats = get_reward_stats()

    lines = [f"Общее количество пользователей: {total_users}"]
    if stats:
        lines.append("")
        lines.append("Выданные литмагниты по каналам:")
        for row in stats:
            lines.append(f"- {row['title']}: {row['delivered']}")
    else:
        lines.append("Литмагниты пока не выдавались.")

    await call.message.answer("\n".join(lines))


@dp.callback_query(F.data == "admin:broadcast")
@admin_only
async def start_broadcast(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    await call.answer()
    await call.message.answer(
        "Выберите тип сообщения для рассылки:",
        reply_markup=broadcast_type_keyboard(),
    )
    await state.set_state(BroadcastStates.waiting_for_content_type)


@dp.callback_query(BroadcastStates.waiting_for_content_type, F.data.startswith("admin:broadcast:type:"))
@admin_only
async def set_broadcast_type(call: types.CallbackQuery, state: FSMContext, **_):
    try:
        broadcast_type = call.data.split(":")[-1]
    except IndexError:
        await call.answer("Не удалось распознать тип.", show_alert=True)
        return

    if broadcast_type not in BROADCAST_TYPES:
        await call.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(broadcast_type=broadcast_type)
    await call.answer()

    prompts = {
        "text": "Отправьте текст сообщения, которое получат все пользователи.",
        "photo": "Отправьте фотографию с подписью (по желанию).",
        "video": "Отправьте видео с подписью (по желанию).",
        "document": "Отправьте документ с подписью (по желанию).",
    }
    await call.message.answer(
        prompts.get(broadcast_type, "Отправьте содержимое сообщения.") + "\nНапишите 'Отмена' для отмены.",
    )
    await state.set_state(BroadcastStates.waiting_for_content)


@dp.message(BroadcastStates.waiting_for_content)
async def process_broadcast_content(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    cancel_candidate = message.text or message.caption
    if is_cancel_text(cancel_candidate):
        await message.answer("Рассылка отменена.")
        await state.clear()
        await send_admin_menu(message)
        return

    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")
    if not broadcast_type:
        await message.answer("Тип сообщения не выбран. Начните процедуру заново.")
        await state.clear()
        await send_admin_menu(message)
        return

    payload, caption, error = extract_magnet_payload(message, broadcast_type)
    if error:
        await message.answer(error)
        if error.startswith("Неизвестный"):
            await state.clear()
            await send_admin_menu(message)
        return

    await state.update_data(broadcast_payload=payload, broadcast_caption=caption)
    await message.answer(
        "Хотите добавить кнопку с ссылкой? Отправьте текст кнопки и ссылку через разделитель `|||`,\n"
        "например: Открыть сайт|||https://example.com\n"
        "Если кнопка не нужна, напишите 'пропустить'."
    )
    await state.set_state(BroadcastStates.waiting_for_button)


@dp.message(BroadcastStates.waiting_for_button)
async def process_broadcast_button(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        await state.clear()
        return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текст или напишите 'пропустить'.")
        return

    if is_cancel_text(message.text):
        await message.answer("Рассылка отменена.")
        await state.clear()
        await send_admin_menu(message)
        return

    data = await state.get_data()

    if is_skip_text(message.text):
        await state.update_data(button_text=None, button_url=None)
    else:
        parts = [part.strip() for part in message.text.split("|||")]
        if len(parts) != 2 or not all(parts):
            await message.answer(
                "Некорректный формат. Используйте `Текст кнопки|||https://example.com` или напишите 'пропустить'."
            )
            return
        text_part, url_part = parts
        if not (url_part.startswith("http://") or url_part.startswith("https://")):
            await message.answer("Ссылка должна начинаться с http:// или https://.")
            return
        await state.update_data(button_text=text_part, button_url=url_part)

    await show_broadcast_preview(message, state)
    await state.set_state(BroadcastStates.waiting_for_confirmation)


async def show_broadcast_preview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")
    payload = data.get("broadcast_payload")
    caption = data.get("broadcast_caption")
    button_text = data.get("button_text")
    button_url = data.get("button_url")

    if not broadcast_type or not payload:
        await message.answer("Не удалось подготовить предварительный просмотр. Рассылка отменена.")
        await state.clear()
        await send_admin_menu(message)
        return

    markup = build_link_keyboard(button_text, button_url)

    try:
        if broadcast_type == "text":
            await message.answer(payload, reply_markup=markup)
        elif broadcast_type == "photo":
            await message.answer_photo(payload, caption=caption, reply_markup=markup)
        elif broadcast_type == "video":
            await message.answer_video(payload, caption=caption, reply_markup=markup)
        elif broadcast_type == "document":
            await message.answer_document(payload, caption=caption, reply_markup=markup)
        else:
            await message.answer("Неизвестный тип сообщения. Рассылка отменена.")
            await state.clear()
            await send_admin_menu(message)
            return
    except TelegramBadRequest as exc:
        logging.error("Не удалось отправить предпросмотр: %s", exc)
        await message.answer("Не удалось сформировать предпросмотр. Проверьте данные и попробуйте снова.")
        return

    total_users = get_user_count()
    summary = [
        "Предпросмотр отправлен выше.",
        f"Тип: {BROADCAST_TYPES.get(broadcast_type, broadcast_type)}",
        f"Получателей: {total_users}",
    ]
    if button_text and button_url:
        summary.append(f"Кнопка: {button_text} → {button_url}")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="admin:broadcast:send")],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data="admin:broadcast:cancel")],
        ]
    )
    await message.answer("\n".join(summary), reply_markup=keyboard)


async def dispatch_broadcast_to_user(
    user_id: int,
    broadcast_type: str,
    payload: str,
    caption: Optional[str],
    markup: Optional[InlineKeyboardMarkup],
):
    if broadcast_type == "text":
        await bot.send_message(user_id, payload, reply_markup=markup)
    elif broadcast_type == "photo":
        await bot.send_photo(user_id, payload, caption=caption, reply_markup=markup)
    elif broadcast_type == "video":
        await bot.send_video(user_id, payload, caption=caption, reply_markup=markup)
    elif broadcast_type == "document":
        await bot.send_document(user_id, payload, caption=caption, reply_markup=markup)
    else:
        raise ValueError(f"Unsupported broadcast type: {broadcast_type}")


@dp.callback_query(BroadcastStates.waiting_for_confirmation, F.data == "admin:broadcast:send")
@admin_only
async def execute_broadcast(call: types.CallbackQuery, state: FSMContext, **_):
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")
    payload = data.get("broadcast_payload")
    caption = data.get("broadcast_caption")
    button_text = data.get("button_text")
    button_url = data.get("button_url")

    if not broadcast_type or not payload:
        await call.answer("Недостаточно данных для рассылки.", show_alert=True)
        await state.clear()
        await send_admin_menu(call)
        return

    markup = build_link_keyboard(button_text, button_url)
    recipients = list(get_all_user_ids())

    await call.answer("Рассылка запущена.")
    status_message = await call.message.answer(f"Отправляю сообщение {len(recipients)} пользователям…")

    success = 0
    failed = 0

    for user_id in recipients:
        try:
            await dispatch_broadcast_to_user(user_id, broadcast_type, payload, caption, markup)
            success += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            try:
                await dispatch_broadcast_to_user(user_id, broadcast_type, payload, caption, markup)
                success += 1
            except Exception as inner_exc:
                logging.warning("Не удалось отправить сообщение пользователю %s после паузы: %s", user_id, inner_exc)
                failed += 1
        except TelegramForbiddenError:
            failed += 1
        except TelegramBadRequest as exc:
            logging.warning("Ошибка отправки пользователю %s: %s", user_id, exc)
            failed += 1
        except Exception as exc:
            logging.error("Неожиданная ошибка при рассылке пользователю %s: %s", user_id, exc)
            failed += 1

        await asyncio.sleep(0.05)

    await state.clear()

    summary = (
        f"Рассылка завершена.\n"
        f"Успешно: {success}\n"
        f"Не доставлено: {failed}"
    )
    await status_message.edit_text(summary)
    await send_admin_menu(call)


@dp.callback_query(BroadcastStates.waiting_for_confirmation, F.data == "admin:broadcast:cancel")
@admin_only
async def cancel_broadcast(call: types.CallbackQuery, state: FSMContext, **_):
    await state.clear()
    await call.answer("Рассылка отменена.")
    await call.message.answer("Рассылка отменена.")
    await send_admin_menu(call)
