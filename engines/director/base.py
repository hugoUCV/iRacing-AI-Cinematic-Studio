"""Director: convierte eventos en un ShotPlan.

Dos implementaciones detrás del mismo contrato:
  - RulesDirector (determinista, sin IA — MVP 1)
  - AIDirector (LLM vía AIProvider, con fallback a reglas — MVP 1 opcional/2)

La IA recibe eventos JSON compactos y devuelve el ShotPlan validado. La IA
nunca toca el sim ni FFmpeg: decide, el software ejecuta.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import Event, SessionModel, ShotPlan, StylePreset


class Director(ABC):
    @abstractmethod
    def build_plan(
        self,
        model: SessionModel,
        events: list[Event],
        style: StylePreset,
        target_duration_s: int,
        hero_driver: int | None,
    ) -> ShotPlan:
        """Construye el plan de planos para la sesión y eventos dados."""
