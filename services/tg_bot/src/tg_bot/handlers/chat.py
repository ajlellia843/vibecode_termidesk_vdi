"""Chat handler: forward to orchestrator and reply."""
from aiogram import Router
from aiogram.types import Message

from tg_bot.api import OrchestratorClient

router = Router(name="chat")


@router.message()
async def handle_message(message: Message, orchestrator_client: OrchestratorClient) -> None:
    if not message.text or not message.from_user:
        return
    user_id = str(message.from_user.id)
    chat_id = message.chat.id if message.chat else 0
    try:
        reply, sources, _ = await orchestrator_client.chat(
            user_id=user_id,
            message=message.text.strip(),
            conversation_id=None,
        )
        text = reply
        if sources:
            text += "\n\nИсточники: " + ", ".join(s.get("source", "?") for s in sources[:3])
        await message.answer(text[:4096])
    except Exception as e:
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте позже или обратитесь в поддержку."
        )
