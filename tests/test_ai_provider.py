"""Tests del proveedor OpenAI-compatible (httpx con MockTransport)."""
from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from ai.provider import AIProviderError, Message
from ai.providers.openai_compat import OpenAICompatProvider
from ai.schemas import LLMShotPlan


class Item(BaseModel):
    name: str
    value: int


def provider(responses: list[str], **kw) -> OpenAICompatProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        content = responses.pop(0)
        body = {"choices": [{"message": {"content": content}}]}
        return httpx.Response(200, json=body)

    client = httpx.Client(
        base_url="https://test.local/v1", transport=httpx.MockTransport(handler)
    )
    return OpenAICompatProvider(
        base_url="https://test.local/v1", model="test-model",
        api_key="k", client=client, **kw,
    )


def test_chat_json_valid_first_try():
    p = provider(['{"name": "hola", "value": 42}'])
    out = p.chat_json([Message(role="user", content="di algo")], Item)
    assert out == Item(name="hola", value=42)


def test_chat_json_retries_once_on_invalid_json():
    p = provider(['esto no es json', '{"name": "ok", "value": 1}'])
    out = p.chat_json([Message(role="user", content="x")], Item)
    assert out == Item(name="ok", value=1)


def test_chat_json_raises_after_two_bad_answers():
    p = provider(['{"name": 1}', '{"name": 2}'])
    with pytest.raises(AIProviderError):
        p.chat_json([Message(role="user", content="x")], Item)


def test_chat_json_validates_schema_semantics():
    """El plan LLM con duración < 0.5 s no valida (model_validator)."""
    p = provider(['{"shots": [{"start_s": 0, "end_s": 0.1}]}'])
    with pytest.raises(AIProviderError):
        p.chat_json([Message(role="user", content="x")], LLMShotPlan)


def test_chat_text_and_available():
    p = provider(["hola mundo"])
    assert p.chat_text([Message(role="user", content="x")]) == "hola mundo"
    assert p.available() is True
    assert OpenAICompatProvider(base_url="u", model="m").available() is False


def test_http_error_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = httpx.Client(
        base_url="https://test.local/v1", transport=httpx.MockTransport(handler)
    )
    p = OpenAICompatProvider(
        base_url="https://test.local/v1", model="m", api_key="k", client=client
    )
    with pytest.raises(AIProviderError):
        p.chat_text([Message(role="user", content="x")])
