"""Handlers for /start and /version: welcome and version selection."""
import json
import os
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from tg_bot.api import OrchestratorClient

router = Router(name="commands")

# #region agent log
def _dlog(msg: str, data: dict, hid: str) -> None:
    try:
        path = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"location": "commands.py", "message": msg, "data": data, "hypothesisId": hid, "timestamp": __import__("time").time() * 1000}, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion

TERMIDESK_VERSIONS = (
    "6.1 (latest)",
    "6.0.2",
    "6.0.1",
    "6.0",
    "5.1.2",
    "5.1.1",
    "5.1",
)

WELCOME_TEXT = """Привет! Я бот поддержки Termidesk VDI.

Отвечаю на вопросы по подключению, настройке и устранению неполадок на основе базы знаний. Могу задавать уточняющие вопросы, если информации недостаточно.

Выберите версию Termidesk — от этого зависят подсказки."""

WELCOME_TEXT_HAVE_VERSION = """Текущая версия: {version}

Можете сменить её кнопкой ниже или задать вопрос в чат."""

VERSION_SELECT_PROMPT = "Выберите версию Termidesk:"


def _version_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=v, callback_data=f"ver:{v}") for v in TERMIDESK_VERSIONS[:4]],
        [InlineKeyboardButton(text=v, callback_data=f"ver:{v}") for v in TERMIDESK_VERSIONS[4:]],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _change_version_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Сменить версию", callback_data="ver:change")]]
    )


@router.message(F.text == "/start")
async def cmd_start(message: Message, orchestrator_client: OrchestratorClient) -> None:
    if not message.from_user:
        return
    telegram_id = str(message.from_user.id)
    version = None
    try:
        await orchestrator_client.users_upsert(telegram_id)
        user = await orchestrator_client.users_get(telegram_id)
        version = user.get("termidesk_version") if isinstance(user, dict) else None
    except Exception:
        pass
    if version:
        text = WELCOME_TEXT_HAVE_VERSION.format(version=version)
        await message.answer(text, reply_markup=_change_version_keyboard())
    else:
        await message.answer(WELCOME_TEXT, reply_markup=_version_keyboard())


@router.message(F.text == "/version")
async def cmd_version(message: Message) -> None:
    await message.answer(VERSION_SELECT_PROMPT, reply_markup=_version_keyboard())


@router.callback_query(F.data.startswith("ver:"))
async def callback_version(callback: CallbackQuery, orchestrator_client: OrchestratorClient) -> None:
    if not callback.data or not callback.from_user:
        return
    if callback.data == "ver:change":
        await callback.message.edit_text(VERSION_SELECT_PROMPT, reply_markup=_version_keyboard())
        await callback.answer()
        return
    version = callback.data[4:]
    telegram_id = str(callback.from_user.id)
    try:
        await orchestrator_client.users_set_version(telegram_id, version)
        await callback.answer()
        await callback.message.answer(f"Ок, установил версию {version}.")
    except Exception as e:
        # #region agent log
        data = {"type": type(e).__name__, "message": str(e)[:300]}
        if hasattr(e, "response"):
            try:
                data["status"] = getattr(e.response, "status_code", None)
                data["body"] = (e.response.text or "")[:200]
            except Exception:
                pass
        _dlog("callback_version error", data, "H2")
        # #endregion
        await callback.answer("Ошибка сохранения. Попробуйте ещё раз.", show_alert=True)
