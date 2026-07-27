import json

import httpx
import pytest

from app.ai import (
    CONNECTIVITY_PROMPT,
    OPENROUTER_API_URL,
    OpenRouterClient,
    OpenRouterConfigurationError,
    OpenRouterRequestError,
    build_chat_messages,
)


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

    with pytest.raises(OpenRouterConfigurationError) as excinfo:
        await client.connectivity_test()

    assert str(excinfo.value) == "OPENROUTER_API_KEY is not configured."


@pytest.mark.anyio
async def test_complete_rejects_bad_upstream_response() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenRouterClient(api_key="test-key", http_client=http_client)

        with pytest.raises(OpenRouterRequestError) as excinfo:
            await client.connectivity_test()

    assert str(excinfo.value) == "OpenRouter response was malformed."


def test_build_chat_messages_adds_system_and_board_context() -> None:
    messages = build_chat_messages(
        history=[{"role": "user", "content": "Move the card."}],
        board_json={"version": 1, "title": "Kanban Studio", "columns": [], "cards": {}},
    )

    assert messages[0]["role"] == "system"
    assert "Return only JSON" in messages[0]["content"]
    assert "Treat the prior messages as an ongoing conversation." in messages[0]["content"]
    assert "If the conversation history does not establish what happened, reply with 'I don't know.'" in messages[0]["content"]
    assert "You may rename those columns, but you must not add, remove, reorder, or change their ids." in messages[0]["content"]
    assert messages[1]["role"] == "system"
    assert "Current board JSON:" in messages[1]["content"]
    assert messages[2] == {"role": "user", "content": "Move the card."}
