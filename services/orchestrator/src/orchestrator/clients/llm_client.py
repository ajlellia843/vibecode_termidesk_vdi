"""HTTP client for LLM service."""
import httpx


class LLMClient:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        url = f"{self._base_url}/generate"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                json={"prompt": prompt, "max_tokens": max_tokens},
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("text", "")
