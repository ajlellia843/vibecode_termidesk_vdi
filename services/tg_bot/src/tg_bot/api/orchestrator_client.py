"""HTTP client to orchestrator chat API."""
from uuid import UUID

import httpx


class OrchestratorClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(
        self,
        user_id: str,
        message: str,
        conversation_id: UUID | None = None,
    ) -> tuple[str, list[dict[str, str]], UUID | None]:
        url = f"{self._base_url}/api/v1/chat"
        payload: dict = {"user_id": user_id, "message": message}
        if conversation_id is not None:
            payload["conversation_id"] = str(conversation_id)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        reply = data.get("reply", "")
        sources = data.get("sources", [])
        cid = data.get("conversation_id")
        conv_id = UUID(cid) if cid else None
        return reply, sources, conv_id
