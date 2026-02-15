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
    try:
        reply, sources, _, version = await orchestrator_client.chat(
            user_id=user_id,
            message=message.text.strip(),
            conversation_id=None,
        )
        text = reply
        if sources:
            seen: list[str] = []
            for s in sources:
                name = s.get("source", "?")
                if name not in seen:
                    seen.append(name)
            text += "\n\nИсточники: " + ", ".join(seen)
        if version:
            text += f"\nВерсия: {version}"
        await message.answer(text[:4096])
    except Exception:
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте позже или обратитесь в поддержку."
        )
