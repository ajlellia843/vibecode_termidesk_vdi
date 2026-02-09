"""Telegram bot entrypoint - long polling, proxies to orchestrator."""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from shared.logging import configure_logging

from tg_bot.api import OrchestratorClient
from tg_bot.config import TgBotSettings
from tg_bot.handlers import chat_router
from tg_bot.middleware import OrchestratorClientMiddleware

configure_logging(json_logs=True)
logging.getLogger("aiogram").setLevel(logging.INFO)


def get_settings() -> TgBotSettings:
    return TgBotSettings()


def create_bot() -> tuple[Bot, Dispatcher]:
    settings = get_settings()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.telegram_bot_token
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN or TG_BOT_TELEGRAM_BOT_TOKEN is required")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    orchestrator_client = OrchestratorClient(settings.orchestrator_url)
    dp.include_router(chat_router)
    dp.message.outer_middleware(OrchestratorClientMiddleware(orchestrator_client))
    return bot, dp


async def main() -> None:
    bot, dp = create_bot()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
