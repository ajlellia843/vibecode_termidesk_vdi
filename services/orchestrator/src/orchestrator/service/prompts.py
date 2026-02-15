"""Prompt assembly for RAG + dialog."""
from orchestrator.clients.retrieval_client import RetrievalResultItem

SYSTEM_PROMPT_TEMPLATE = """Ты — техническая поддержка Termidesk VDI.
Отвечай строго по источникам.
Если информации нет — скажи честно."""


def get_system_prompt(version: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(version=version or "не указана")


def build_rag_context(chunks: list[RetrievalResultItem]) -> str:
    if not chunks:
        return "(Релевантных фрагментов в базе знаний не найдено.)"
    parts = []
    for i, c in enumerate(chunks, 1):
        title = (c.document_title or c.source or "").strip()
        section = (c.section_title or "").strip()
        header = f"{title} – {section}" if section else title
        parts.append(f"[{i}] {header}\n{c.text}")
    return "\n---\n".join(parts)


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
    strict_mode: bool = False,
) -> str:
    system_prompt = get_system_prompt(version or "не указана")
    rag_context = build_rag_context(rag_chunks)
    prompt_parts = [
        system_prompt,
        "",
        "Версия: " + (version or "не указана"),
        "",
        "Источники:",
        rag_context,
        "",
    ]
    if not strict_mode:
        history_context = build_messages_context(history)
        if history_context:
            prompt_parts.extend(["История диалога:", history_context, ""])
    prompt_parts.extend(["Текущий вопрос пользователя:", user_message, "", "Ответ:"])
    return "\n".join(prompt_parts)
