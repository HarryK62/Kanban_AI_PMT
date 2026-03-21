import os

import httpx
from fastapi import HTTPException


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
CONNECTIVITY_PROMPT = "What is 2+2? Reply with just the number."


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENROUTER_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.http_client = http_client

    async def connectivity_test(self) -> str:
        return await self.complete(CONNECTIVITY_PROMPT)

    async def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY is not configured.",
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.http_client is not None:
            response = await self.http_client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
            )
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail="OpenRouter request failed.",
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            raise HTTPException(
                status_code=502,
                detail="OpenRouter response was malformed.",
            ) from None
