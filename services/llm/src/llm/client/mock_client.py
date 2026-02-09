"""Mock LLM client for MVP: returns RAG context as answer when present."""
import re
from llm.client.base import LLMClient


def _extract_rag_answer(prompt: str) -> str | None:
    """Extract first chunk text from orchestrator prompt (Контекст из базы знаний)."""
    marker = "Контекст из базы знаний Termidesk:"
    end_markers = ("История диалога:", "Текущий вопрос пользователя:")
    idx = prompt.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    end = len(prompt)
    for em in end_markers:
        pos = prompt.find(em, start)
        if pos != -1:
            end = min(end, pos)
    block = prompt[start:end].strip()
    if not block or "(Релевантных фрагментов" in block:
        return None
    # First chunk: [Источник 1: faq.md]\n<text> (optional --- separator)
    m = re.search(r"\[Источник \d+:[^\]]+\]\s*\n(.+?)(?=\n\n---|\n\n\[Источник|\Z)", block, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: whole block up to first ---
    if "---" in block:
        block = block.split("---")[0].strip()
    if re.match(r"\[Источник \d+:", block):
        first_line_break = block.find("\n")
        return block[first_line_break + 1 :].strip() if first_line_break != -1 else block
    return block if len(block) < 2000 else block[:2000].rstrip() + "…"


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        answer = _extract_rag_answer(prompt)
        if answer:
            return answer
        return (
            "Это ответ в режиме mock. По вашему запросу по Termidesk VDI: "
            "проверьте документацию и при необходимости соберите логи для поддержки."
        )
