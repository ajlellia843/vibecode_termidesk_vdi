"""LLM client interface."""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate completion for prompt. Returns generated text."""
        ...
