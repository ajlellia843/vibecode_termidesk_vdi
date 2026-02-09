"""Middleware to inject orchestrator client."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from tg_bot.api import OrchestratorClient


class OrchestratorClientMiddleware(BaseMiddleware):
    def __init__(self, client: OrchestratorClient) -> None:
        self._client = client

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        data["orchestrator_client"] = self._client
        return await handler(event, data)
