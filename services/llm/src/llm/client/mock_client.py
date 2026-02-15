"""Mock LLM client for MVP: returns best-matching RAG chunk as answer when present."""
import re
from llm.client.base import LLMClient


def _word_set(text: str) -> set[str]:
    """Lowercased words of length >= 2 for overlap scoring."""
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 2}


def _extract_rag_answer(prompt: str) -> str | None:
    """Extract chunk that best matches the user question (by word overlap)."""
    for marker in ("Источники:", "Контекст из базы знаний Termidesk:"):
        idx = prompt.find(marker)
        if idx != -1:
            break
    else:
        return None
    end_markers = ("История диалога:", "Текущий вопрос пользователя:")
    start = idx + len(marker)
    end = len(prompt)
    for em in end_markers:
        pos = prompt.find(em, start)
        if pos != -1:
            end = min(end, pos)
    block = prompt[start:end].strip()
    if not block or "(Релевантных фрагментов" in block:
        return None
    user_marker = "Текущий вопрос пользователя:"
    uidx = prompt.find(user_marker)
    question = prompt[uidx + len(user_marker) :].split("\n")[0].strip() if uidx != -1 else ""
    q_words = _word_set(question) if question else set()
    chunks: list[str] = []
    # Parse chunks: "[1] header\ntext" or "[Источник 1: source]\ntext", separated by ---
    for part in re.split(r"\n---\n", block):
        part = part.strip()
        if not part:
            continue
        first_nl = part.find("\n")
        if first_nl != -1:
            chunks.append(part[first_nl + 1 :].strip())
        else:
            chunks.append(part)
    if not chunks and block:
        first_nl = block.find("\n")
        chunks = [block[first_nl + 1 :].strip()] if first_nl != -1 else [block]
    if not chunks:
        return None
    # Pick chunk with highest word overlap with question; else first
    if not q_words or len(chunks) == 1:
        t = chunks[0].strip()
        return t if len(t) <= 2000 else t[:2000].rstrip() + "…"
    best_idx = 0
    best_overlap = len(_word_set(chunks[0]) & q_words)
    for i in range(1, len(chunks)):
        overlap = len(_word_set(chunks[i]) & q_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = i
    t = chunks[best_idx].strip()
    return t if len(t) <= 2000 else t[:2000].rstrip() + "…"


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        answer = _extract_rag_answer(prompt)
        if answer:
            return answer
        return (
            "Это ответ в режиме mock. По вашему запросу по Termidesk VDI: "
            "проверьте документацию и при необходимости соберите логи для поддержки."
        )
