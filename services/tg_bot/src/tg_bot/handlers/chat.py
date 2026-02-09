"""Chat handler: forward to orchestrator and reply."""
import json
import os
import time

from aiogram import Router
from aiogram.types import Message

from tg_bot.api import OrchestratorClient

router = Router(name="chat")

# #region agent log
def _dlog(msg: str, data: dict, hypothesis_id: str) -> None:
    p = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"hypothesisId": hypothesis_id, "location": "chat.py", "message": msg, "data": data, "timestamp": int(time.time() * 1000)}, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion


@router.message()
async def handle_message(message: Message, orchestrator_client: OrchestratorClient) -> None:
    # #region agent log
    _dlog("handler entry", {"text": (message.text or "")[:80], "has_from_user": bool(message.from_user)}, "H4")
    # #endregion
    if not message.text or not message.from_user:
        return
    user_id = str(message.from_user.id)
    try:
        # #region agent log
        _dlog("before orchestrator_client.chat", {"user_id": user_id}, "H5")
        # #endregion
        reply, sources, _ = await orchestrator_client.chat(
            user_id=user_id,
            message=message.text.strip(),
            conversation_id=None,
        )
        text = reply
        if sources:
            text += "\n\nИсточники: " + ", ".join(s.get("source", "?") for s in sources[:3])
        await message.answer(text[:4096])
        # #region agent log
        _dlog("handler success", {"reply_len": len(reply)}, "H5")
        # #endregion
    except Exception as e:
        # #region agent log
        _dlog("handler except", {"exc_type": type(e).__name__, "exc_msg": str(e)[:200]}, "H5")
        # #endregion
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте позже или обратитесь в поддержку."
        )
