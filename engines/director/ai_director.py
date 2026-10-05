"""AIDirector: shot plan por LLM con fallback al director de reglas.

La IA recibe eventos JSON compactos (top-N por importancia) y devuelve un
LLMShotPlan validado. El software resuelve nombres de cámara con el catálogo,
recorta a la duración de la sesión y ordena por tiempo. Cualquier fallo del
proveedor degrada al RulesDirector.
"""
from __future__ import annotations

import json
import logging

from ai.provider import AIProvider, AIProviderError, Message
from ai.schemas import LLMShotPlan
from core.models import CameraSpec, Event, SessionModel, Shot, ShotPlan, StylePreset

from engines.camera.catalog import CameraCatalog
from engines.director.base import Director
from engines.director.rules import RulesDirector
from utils.config import DirectorConfig

log = logging.getLogger(__name__)

FALLBACK_CAMERAS = ["TV1", "TV2", "chopper", "blimp", "chase", "cockpit"]
MAX_EVENTS_IN_PROMPT = 25


class AIDirector(Director):
    def __init__(
        self,
        provider: AIProvider,
        catalog: CameraCatalog,
        config: DirectorConfig | None = None,
        fallback: Director | None = None,
    ):
        self.provider = provider
        self.catalog = catalog
        self.config = config or DirectorConfig()
        self.fallback = fallback or RulesDirector(config=self.config, catalog=catalog)

    def build_plan(
        self,
        model: SessionModel,
        events: list[Event],
        style: StylePreset,
        target_duration_s: int,
        hero_driver: int | None,
    ) -> ShotPlan:
        if not self.provider.available():
            log.info("sin proveedor de IA disponible → director de reglas")
            return self.fallback.build_plan(model, events, style, target_duration_s, hero_driver)

        system = self._system_prompt(model, style, target_duration_s, hero_driver)
        user = json.dumps(self._compact(model, events, hero_driver), ensure_ascii=False)
        try:
            llm = self.provider.chat_json(
                [
                    Message(role="system", content=system),
                    Message(role="user", content=user),
                ],
                LLMShotPlan,
            )
            shots = self._convert(llm, model, hero_driver)
            if not shots:
                raise AIProviderError("el plan de la IA quedó vacío")
            return ShotPlan(
                shots=shots,
                style=style,
                hero_driver=hero_driver,
                notes=llm.notes or ["plan generado por IA"],
            )
        except (AIProviderError, ValueError) as exc:
            log.warning("fallo el director IA (%s) → director de reglas", exc)
            return self.fallback.build_plan(model, events, style, target_duration_s, hero_driver)

    # ── prompt ────────────────────────────────────────────────────────────

    def _system_prompt(
        self, model: SessionModel, style: StylePreset, target_duration_s: int,
        hero_driver: int | None,
    ) -> str:
        hero = (
            next((d.name for d in model.session.drivers if d.car_idx == hero_driver), None)
            if hero_driver is not None else None
        )
        cams = ", ".join(n for _, n in self.catalog.groups)
        return (
            "Eres el director de una retransmisión cinematográfica de simracing "
            "(iRacing). Recibes eventos detectados de una carrera y eliges los "
            "planos para un vídeo vertical para redes sociales.\n"
            f"Sesión: {model.session.track_display or model.session.track_name}, "
            f"{model.session.session_type}. Duración objetivo: {target_duration_s} s.\n"
            f"Piloto protagonista: {hero or 'el más destacado'}.\n"
            f"Estilo: {style.value}.\n"
            f"Cámaras disponibles: {cams}.\n"
            "Reglas: cada plano tiene start_s y end_s en segundos de sesión; "
            "empieza ~3 s ANTES del evento para captar la anticipación; deja al "
            "menos 4 s entre planos; prioriza los eventos con mayor importance y "
            "los que implican al protagonista; usa cámaras variadas (TV para "
            "acción, chopper/blimp para contexto, cockpit para intensidad); si "
            "el material es escaso, rellena con planos del protagonista.\n"
            "Responde SOLO con un objeto JSON: {\"shots\": [{\"start_s\": <n>, "
            "\"end_s\": <n>, \"group_name\": \"<cámara>\", \"target\": <car_idx o "
            "null>}], \"notes\": [\"...\"]}."
        )

    def _compact(self, model: SessionModel, events: list[Event], hero: int | None) -> dict:
        top = sorted(events, key=lambda e: -e.importance)[:MAX_EVENTS_IN_PROMPT]
        return {
            "session": {
                "track": model.session.track_name,
                "duration_s": model.session.duration_s,
                "drivers": [
                    {"car_idx": d.car_idx, "name": d.name}
                    for d in model.session.drivers[:40]
                ],
            },
            "hero": hero,
            "events": [
                {
                    "type": e.type.value,
                    "t0": round(e.start_s, 2),
                    "t1": round(e.end_s, 2),
                    "drivers": e.drivers,
                    "target": e.target,
                    "importance": round(e.importance, 2),
                    "lap": e.lap,
                }
                for e in top
            ],
        }

    # ── conversión ────────────────────────────────────────────────────────

    def _convert(
        self, llm: LLMShotPlan, model: SessionModel, hero: int | None
    ) -> list[Shot]:
        duration = model.session.duration_s
        shots: list[Shot] = []
        for i, s in enumerate(llm.shots):
            resolved = self.catalog.resolve(s.group_name) or self.catalog.resolve_first(
                FALLBACK_CAMERAS
            )
            if resolved is None:
                continue
            num, name = resolved
            start = max(0.0, s.start_s)
            end = s.end_s if duration is None else min(s.end_s, duration)
            if end - start < 0.5:
                continue
            target = s.target if s.target is not None else hero
            shots.append(
                Shot(
                    id=f"ai-{i + 1:03d}",
                    source_start_s=round(start, 2),
                    source_end_s=round(end, 2),
                    camera=CameraSpec(
                        group=num, number=0, target=target, group_name=name
                    ),
                )
            )
        shots.sort(key=lambda x: x.source_start_s)
        return shots
