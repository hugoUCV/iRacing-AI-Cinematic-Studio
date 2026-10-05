"""Proveedor OpenAI-compatible (httpx).

Un solo cliente cubre OpenAI, Gemini (endpoint compatible), Pollinations y
Ollama (expone /v1). chat_json pide response_format json_object, valida contra
el schema Pydantic y reintenta una vez con el error como feedback.
"""
from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ai.provider import AIProvider, AIProviderError, Message

T = TypeVar("T", bound=BaseModel)


class OpenAICompatProvider(AIProvider):
    name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.4,
        timeout: float = 90.0,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def available(self) -> bool:
        return bool(self.api_key)

    # ── API ───────────────────────────────────────────────────────────────

    def chat_text(self, messages: list[Message]) -> str:
        return self._post(self._payload(messages, json_mode=False))

    def chat_json(self, messages: list[Message], schema: type[T]) -> T:
        msgs = list(messages)
        last_error: Exception | None = None
        for _ in range(2):
            content = self._post(self._payload(msgs, json_mode=True))
            try:
                return schema.model_validate_json(content)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                # feedback: devolver el error para que corrija en el reintento
                msgs.append(Message(role="assistant", content=content[:2000]))
                msgs.append(
                    Message(
                        role="user",
                        content=(
                            "Tu respuesta no valida contra el schema. Error: "
                            f"{str(exc)[:500]}. Responde SOLO con JSON válido, "
                            "sin comentarios ni markdown."
                        ),
                    )
                )
        raise AIProviderError(f"El modelo no produjo JSON válido: {last_error}")

    # ── internos ──────────────────────────────────────────────────────────

    def _payload(self, messages: list[Message], json_mode: bool) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _post(self, payload: dict) -> str:
        try:
            resp = self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise AIProviderError(f"Error del proveedor ({self.base_url}): {exc}") from exc
