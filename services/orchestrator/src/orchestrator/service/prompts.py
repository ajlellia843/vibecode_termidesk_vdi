"""Prompt assembly for RAG + dialog."""
from orchestrator.clients.retrieval_client import RetrievalResultItem

SYSTEM_PROMPT_TEMPLATE = """Ты — саппорт Termidesk VDI.
Отвечай строго по версии продукта: {version}.
Используй ТОЛЬКО информацию из предоставленных источников; не выдумывай.
Если в источниках нет ответа — честно скажи и предложи шаги диагностики или уточняющие вопросы (что за ошибка, на каком шаге, клиент или сервер, логи).
Отвечай кратко и по делу."""


def get_system_prompt(version: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(version=version or "не указана")


def build_rag_context(chunks: list[RetrievalResultItem]) -> str:
    if not chunks:
        return "(Релевантных фрагментов в базе знаний не найдено.)"
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Источник {i}: {c.source}]\n{c.text}")
    return "\n\n---\n\n".join(parts)


def build_messages_context(messages: list[tuple[str, str]]) -> str:
    if not messages:
        return ""
    parts = []
    for role, content in messages:
        prefix = "Пользователь" if role == "user" else "Ассистент"
        parts.append(f"{prefix}: {content}")
    return "\n".join(parts)


def build_full_prompt(
    user_message: str,
    rag_chunks: list[RetrievalResultItem],
    history: list[tuple[str, str]],
    version: str | None = None,
) -> str:
    system_prompt = get_system_prompt(version or "не указана")
    rag_context = build_rag_context(rag_chunks)
    history_context = build_messages_context(history)
    prompt_parts = [
        system_prompt,
        "",
        "Контекст из базы знаний Termidesk:",
        rag_context,
        "",
    ]
    if history_context:
        prompt_parts.extend(["История диалога:", history_context, ""])
    prompt_parts.extend(["Текущий вопрос пользователя:", user_message, "", "Ответ:"])
    return "\n".join(prompt_parts)
