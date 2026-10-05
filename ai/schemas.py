"""Contratos JSON entre la IA y el software.

La IA recibe datos estructurados compactos y devuelve decisiones validadas.
Ejemplo de entrada (director):

    {"events": [{"type": "overtake", "driver": "Hugo", "target": "#21",
                 "t": 128.4, "importance": 0.93}], ...}

La salida del director es LLMShotPlan: la IA elige planos por NOMBRE de grupo
de cámara (no sabe números) y el software resuelve con el catálogo.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class LLMShot(BaseModel):
    start_s: float = Field(ge=0, description="inicio del plano (tiempo de sesión, s)")
    end_s: float = Field(gt=0, description="fin del plano (tiempo de sesión, s)")
    group_name: str = Field(default="TV1", description="grupo de cámara (cockpit, TV1, chopper...)")
    target: int | None = Field(default=None, description="car_idx del coche protagonista; None = plano de pista")

    @model_validator(mode="after")
    def _check_duration(self):
        if self.end_s - self.start_s < 0.5:
            raise ValueError("el plano debe durar al menos 0.5 s")
        return self


class LLMShotPlan(BaseModel):
    shots: list[LLMShot] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
