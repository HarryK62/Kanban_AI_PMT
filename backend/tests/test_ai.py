import json

import httpx
import pytest
from fastapi import HTTPException

from app.ai import CONNECTIVITY_PROMPT, OPENROUTER_API_URL, OpenRouterClient


@pytest.mark.anyio
async def test_complete_sends_openrouter_request() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(OPENROUTER_API_URL)
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content.decode("utf-8")) == {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": CONNECTIVITY_PROMPT}],
            "temperature": 0,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenRouterClient(api_key="test-key", http_client=http_client)
        reply = await client.connectivity_test()

    assert reply == "4"


@pytest.mark.anyio
async def test_complete_requires_api_key() -> None:
    client = OpenRouterClient(api_key="")

    with pytest.raises(HTTPException) as excinfo:
        await client.connectivity_test()

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "OPENROUTER_API_KEY is not configured."


@pytest.mark.anyio
async def test_complete_rejects_bad_upstream_response() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenRouterClient(api_key="test-key", http_client=http_client)

        with pytest.raises(HTTPException) as excinfo:
            await client.connectivity_test()

    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "OpenRouter response was malformed."
