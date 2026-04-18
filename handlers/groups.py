from aiogram import F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import dp
from database import fetch_subscription_groups, get_user_group_ids, toggle_user_group

_HEADER = (
    "<b>Выберите, какие скидки вам интересно получать</b>\n\n"
    "<i>Будем присылать только горящие предложения и билеты по сниженной цене</i>"
)
_NO_GROUPS = "Группы рассылок пока не настроены. Загляните позже!"


def _groups_keyboard(groups, subscribed_ids: set) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if g["id"] in subscribed_ids else "◻️ ") + g["name"],
                callback_data=f"subs:toggle:{g['id']}",
            )
        ]
        for g in groups
    ]
    rows.append([InlineKeyboardButton(text="Готово ✔️", callback_data="subs:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "subs:menu")
async def handle_subs_menu(call: types.CallbackQuery):
    groups = fetch_subscription_groups()
    if not groups:
        await call.answer(_NO_GROUPS, show_alert=True)
        return
    subscribed = set(get_user_group_ids(call.from_user.id))
    await call.answer()
    await call.message.answer(_HEADER, reply_markup=_groups_keyboard(groups, subscribed))


@dp.callback_query(F.data.startswith("subs:toggle:"))
async def handle_subs_toggle(call: types.CallbackQuery):
    try:
        group_id = int(call.data.split(":")[-1])
    except (ValueError, IndexError):
        await call.answer("Ошибка.", show_alert=True)
        return

    now_on = toggle_user_group(call.from_user.id, group_id)
    groups = fetch_subscription_groups()
    subscribed = set(get_user_group_ids(call.from_user.id))
    keyboard = _groups_keyboard(groups, subscribed)

    await call.answer("Подписка оформлена ✅" if now_on else "Подписка отменена")
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass


@dp.callback_query(F.data == "subs:done")
async def handle_subs_done(call: types.CallbackQuery):
    await call.answer("Настройки сохранены!")
    try:
        await call.message.delete()
    except Exception:
        pass
