"""Prompt assembly for RAG + dialog."""
from orchestrator.clients.retrieval_client import RetrievalResultItem

SYSTEM_PROMPT = """Ты — бот поддержки Termidesk VDI. Отвечай только на основе предоставленного контекста и базы знаний.
Если информации недостаточно для ответа — честно скажи и задай 1–2 уточняющих вопроса (режим диагностики).
Не выдумывай решения. Если не нашёл ответ в контексте — предложи пользователю собрать логи и обратиться в поддержку.
Отвечай кратко и по делу."""


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
) -> str:
    rag_context = build_rag_context(rag_chunks)
    history_context = build_messages_context(history)
    prompt_parts = [
        f"{SYSTEM_PROMPT}",
        "",
        "Контекст из базы знаний Termidesk:",
        rag_context,
        "",
    ]
    if history_context:
        prompt_parts.extend(["История диалога:", history_context, ""])
    prompt_parts.extend(["Текущий вопрос пользователя:", user_message, "", "Ответ:"])
    return "\n".join(prompt_parts)
