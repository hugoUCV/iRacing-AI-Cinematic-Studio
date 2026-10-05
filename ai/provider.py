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


def provider_from_config(config: dict[str, Any]) -> AIProvider:
    """Factory: crea el proveedor activo según la configuración.

    Implementación real en MVP 1 (OpenAI-compatible vía httpx). Aquí solo el
    contrato, para que el resto del código no dependa de un proveedor concreto.
    """
    raise NotImplementedError("provider_from_config se implementa en MVP 1")
