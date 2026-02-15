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
    ) -> tuple[str, list[dict[str, str]], UUID | None, str | None]:
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
        version = data.get("version")
        return reply, sources, conv_id, version

    async def users_upsert(self, telegram_id: str) -> dict:
        url = f"{self._base_url}/api/v1/users/upsert"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json={"telegram_id": telegram_id})
            resp.raise_for_status()
            return resp.json()

    async def users_get(self, telegram_id: str) -> dict:
        url = f"{self._base_url}/api/v1/users/{telegram_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def users_set_version(self, telegram_id: str, version: str) -> dict:
        url = f"{self._base_url}/api/v1/users/{telegram_id}/version"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json={"version": version})
            resp.raise_for_status()
            return resp.json()
