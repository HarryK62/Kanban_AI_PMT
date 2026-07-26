import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
CONNECTIVITY_PROMPT = "What is 2+2? Reply with just the number."
ROOT_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from project root for local runs.
load_dotenv(ROOT_DIR / ".env")


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENROUTER_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY") if api_key is None else api_key
        self.model = model
        self.http_client = http_client

    async def connectivity_test(self) -> str:
        return await self.complete(CONNECTIVITY_PROMPT)

    async def complete(self, prompt: str) -> str:
        return await self.complete_messages([{"role": "user", "content": prompt}])

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY is not configured.",
            )

        payload = {
            "model": self.model,
            "messages": messages,
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


def build_chat_messages(
    history: list[dict[str, str]],
    board_json: dict[str, Any],
) -> list[dict[str, str]]:
    system_prompt = (
        "You are helping manage a kanban board. "
        "Treat the prior messages as an ongoing conversation. "
        "If the user refers to earlier changes, use the prior messages and current board state to resolve them. "
        "Do not invent prior actions or explanations. "
        "If the conversation history does not establish what happened, reply with 'I don't know.' "
        "Do not infer a past action only from the current board state. "
        "The board has exactly five fixed columns with these ids in this order: "
        "col-backlog, col-discovery, col-progress, col-review, col-done. "
        "You may rename those columns, but you must not add, remove, reorder, or change their ids. "
        "Return only JSON with this shape: "
        '{"reply":"string","board_update":null} or '
        '{"reply":"string","board_update":{"kind":"replace_board","board":{...}}}. '
        "If you change the board, return the full next board. "
        "If you do not change the board, set board_update to null. "
        "The board must remain valid: column ids unique, each referenced card must exist, "
        "each card appears in exactly one column, and each card key must match its id."
    )
    board_context = {
        "role": "system",
        "content": f"Current board JSON: {json_dumps(board_json)}",
    }
    return [{"role": "system", "content": system_prompt}, board_context, *history]


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))
