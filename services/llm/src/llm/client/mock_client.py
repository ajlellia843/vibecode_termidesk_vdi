"""Mock LLM client for MVP."""
from llm.client.base import LLMClient


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        return (
            "Это ответ в режиме mock. По вашему запросу по Termidesk VDI: "
            "проверьте документацию и при необходимости соберите логи для поддержки."
        )
