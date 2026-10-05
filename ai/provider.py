"""Interfaz del proveedor de IA.

Regla: nada fuera de ai/ habla con un LLM. El director y el content generator
consumen únicamente AIProvider.chat_json / chat_text.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Message(BaseModel):
    role: str  # system | user | assistant
    content: str


class AIProviderError(Exception):
    """Error de proveedor de IA (red, auth, schema inválido...)."""


class AIProvider(ABC):
    """Proveedor de IA genérico (OpenAI, Gemini, Pollinations, Ollama...)."""

    name: str = "base"

    @abstractmethod
    def chat_json(self, messages: list[Message], schema: type[T]) -> T:
        """Devuelve JSON validado contra `schema`. Lanza AIProviderError si el
        modelo no produce un JSON conforme (el llamador aplica fallback)."""
        ...

    @abstractmethod
    def chat_text(self, messages: list[Message]) -> str:
        ...

    @abstractmethod
    def available(self) -> bool:
        """True si hay clave configurada / endpoint accesible."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AIProvider {self.name}>"


def provider_from_config(config) -> AIProvider | None:
    """Factory: crea el proveedor activo según la configuración.

    Devuelve None si el proveedor está desactivado (el llamador usa el
    director de reglas como fallback)."""
    if config is None or config.provider in (None, "none"):
        return None
    if config.provider == "openai_compat":
        from ai.providers.openai_compat import OpenAICompatProvider
        from utils.secrets import get_api_key

        key = get_api_key(config.provider, config.key_env) or ""
        return OpenAICompatProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=key,
            temperature=config.temperature,
        )
    raise ValueError(f"proveedor desconocido: {config.provider}")
