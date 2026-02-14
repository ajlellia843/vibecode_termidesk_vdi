"""Mock LLM client for MVP: returns best-matching RAG chunk as answer when present."""
import re
from llm.client.base import LLMClient


def _word_set(text: str) -> set[str]:
    """Lowercased words of length >= 2 for overlap scoring."""
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 2}


def _extract_rag_answer(prompt: str) -> str | None:
    """Extract chunk that best matches the user question (by word overlap)."""
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
    # User question for overlap
    user_marker = "Текущий вопрос пользователя:"
    uidx = prompt.find(user_marker)
    question = prompt[uidx + len(user_marker) :].split("\n")[0].strip() if uidx != -1 else ""
    q_words = _word_set(question) if question else set()
    # Parse all chunks: [Источник N: source]\n<text> separated by ---
    chunk_pat = re.compile(r"\[Источник \d+:[^\]]+\]\s*\n(.+?)(?=\n\n---|\n\n\[Источник|\Z)", re.DOTALL)
    chunks = chunk_pat.findall(block)
    if not chunks:
        if "---" in block:
            chunks = [b.strip() for b in block.split("---") if b.strip() and "[Источник" in b]
            chunks = [b[b.find("\n") + 1 :].strip() if "\n" in b else b for b in chunks]
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
