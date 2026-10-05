"""Estado compartido de la GUI (patrón MVVM ligero).

Los workers (app.workers) ejecutan el trabajo pesado en QThread; el estado
solo guarda resultados y emite señales. Ninguna pantalla toca el SDK
directamente.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.models import (
    Clip,
    SessionInfo,
    SessionModel,
    ShotPlan,
    StylePreset,
    Timeline,
)

from ai.provider import provider_from_config
from engines.camera.catalog import CameraCatalog
from engines.director.ai_director import AIDirector
from engines.director.rules import RulesDirector
from utils.config import AppConfig, load_config


class AppState(QObject):
    status = Signal(str)             # barra de estado
    session_ready = Signal(object)   # SessionInfo
    model_ready = Signal(object)     # SessionModel (análisis)
    plan_ready = Signal(object)      # ShotPlan
    captures_ready = Signal(object)  # dict[str, Path]
    export_done = Signal(object)     # Path
    error = Signal(str)

    def __init__(
        self,
        config: AppConfig | None = None,
        controller=None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.config = config or load_config()
        self.controller = controller  # None → se crea al conectar (SDK real)
        self.session_info: SessionInfo | None = None
        self.model: SessionModel | None = None
        self.plan: ShotPlan | None = None
        self.trims: dict[str, tuple[float, float]] = {}
        self.enabled: dict[str, bool] = {}
        self.captures: dict[str, Path] = {}
        self.output_path: Path | None = None
        self.project_dir: Path | None = None

    # ── conexión ───────────────────────────────────────────────────────────

    def connect_sim(self) -> bool:
        if self.controller is None:
            from engines.replay.sdk_controller import SDKController

            self.controller = SDKController()
        if not self.controller.connect():
            self.error.emit(
                "No se pudo conectar con iRacing. Ábrelo y carga la replay primero."
            )
            return False
        self.session_info = self.controller.session_info()
        self.session_ready.emit(self.session_info)
        self.status.emit(
            f"Conectado: {self.session_info.track_display or self.session_info.track_name}"
        )
        return True

    def camera_groups(self) -> list[tuple[int, str]]:
        if self.controller is None:
            return []
        try:
            return self.controller.camera_groups()
        except Exception:
            return []

    # ── director ───────────────────────────────────────────────────────────

    def build_plan_sync(
        self,
        hero_idx: int | None,
        style: StylePreset,
        duration_s: int,
        use_ai: bool,
    ) -> ShotPlan:
        """Bloqueante (se ejecuta en un worker): construye el shot plan."""
        catalog = CameraCatalog.from_controller(self.controller)
        provider = provider_from_config(self.config.ai) if use_ai else None
        director = (
            AIDirector(provider, catalog, self.config.director)
            if provider is not None
            else RulesDirector(self.config.director, catalog)
        )
        return director.build_plan(
            self.model, self.model.events, style, duration_s, hero_idx
        )

    # ── edición ────────────────────────────────────────────────────────────

    def build_timeline(self) -> Timeline:
        clips: list[Clip] = []
        for s in self.plan.shots:
            if not self.enabled.get(s.id, True):
                continue
            trim_in, trim_out = self.trims.get(s.id, (0.0, 0.0))
            clips.append(Clip(shot=s, trim_in_s=trim_in, trim_out_s=trim_out))
        return Timeline(clips=clips)

    def timeline_total_s(self) -> float:
        t = self.build_timeline()
        return sum(
            max(0.0, (c.shot.source_end_s - c.shot.source_start_s)
                - c.trim_in_s - c.trim_out_s)
            for c in t.clips if c.enabled
        )

    def reset(self) -> None:
        self.session_info = None
        self.model = None
        self.plan = None
        self.trims = {}
        self.enabled = {}
        self.captures = {}
        self.output_path = None
        self.project_dir = None
