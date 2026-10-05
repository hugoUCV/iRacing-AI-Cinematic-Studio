"""CaptureRunner: ejecuta un ShotPlan contra el replay abierto.

Por cada plano (ordenado por tiempo): seek con margen → cámara → verificar →
grabar → reproducir a 1x hasta el final del plano → parar. Los saltos hacia
atrás solo ocurren entre planos, nunca dentro de una toma.
"""
from __future__ import annotations

# ruff: noqa: BLE001  — captura tolerante a fallos: cada `except Exception`
# registra el error y continúa (degradación elegante, nunca debe crashear).
import logging
import time
from pathlib import Path

from core.models import ShotPlan
from engines.replay.base import ReplayController
from services.capture.base import CaptureBackend

log = logging.getLogger(__name__)

SEEK_MARGIN_S = 0.5  # coincide con CAPTURE_MARGIN_S del export


class CaptureRunner:
    def __init__(
        self,
        controller: ReplayController,
        backend: CaptureBackend,
        captures_dir: Path,
        session_num: int,
        verify_retries: int = 2,
        wait_timeout_s: float | None = None,
        ui_pilot=None,
    ):
        self.controller = controller
        self.backend = backend
        self.captures_dir = Path(captures_dir)
        self.session_num = session_num
        self.verify_retries = verify_retries
        self.wait_timeout_s = wait_timeout_s  # None → dur*2+15 por plano
        self.ui_pilot = ui_pilot  # None → no tocar la UI

    def run(self, plan: ShotPlan, on_progress=None) -> dict[str, Path]:
        """Captura todos los planos. Devuelve {shot_id: archivo} para los que
        se capturaron correctamente (los fallos se registran y se saltan).

        on_progress(current: int, total: int, message: str) opcional."""
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Path] = {}
        shots = sorted(plan.shots, key=lambda s: s.source_start_s)
        if self.ui_pilot is not None:
            try:
                self.ui_pilot.hide()
            except Exception as exc:
                log.warning("no se pudo ocultar la UI: %s", exc)
        try:
            for i, shot in enumerate(shots):
                if on_progress:
                    on_progress(i + 1, len(shots), f"plano {shot.id} ({shot.camera.group_name})")
                try:
                    produced = self._capture_shot(shot)
                    if produced:
                        result[shot.id] = produced
                        log.info("capturado %s → %s", shot.id, produced)
                except Exception as exc:
                    log.warning("falló la captura de %s: %s", shot.id, exc)
        finally:
            if self.ui_pilot is not None:
                try:
                    self.ui_pilot.restore()
                except Exception as exc:
                    log.warning("no se pudo restaurar la UI: %s", exc)
        return result

    # ── un plano ──────────────────────────────────────────────────────────

    def _capture_shot(self, shot) -> Path | None:
        ctrl = self.controller
        t_seek = max(0.0, shot.source_start_s - SEEK_MARGIN_S)
        ctrl.seek_session_time(self.session_num, int(t_seek * 1000))
        ctrl.set_camera(shot.camera)
        self._verify_camera(shot.camera)

        target = self.captures_dir / f"{shot.id}.mp4"
        self.backend.start(target)
        ctrl.play(1.0)
        try:
            dur = shot.source_end_s - shot.source_start_s
            timeout = self.wait_timeout_s if self.wait_timeout_s is not None else dur * 2 + 15
            ctrl.wait_until_session_time(
                shot.source_end_s + SEEK_MARGIN_S, timeout_s=timeout
            )
        finally:
            produced = self.backend.stop()
            ctrl.pause()
        return produced

    def _verify_camera(self, spec) -> None:
        """Confirma que la cámara cambió; reintenta si el sim va lento."""
        for _ in range(self.verify_retries + 1):
            v = self.controller.verify()
            if v.get("cam_group") == spec.group:
                return
            self.controller.set_camera(spec)
            time.sleep(0.3)
        log.warning(
            "la cámara no confirmó el cambio (grupo %s): se continúa igualmente",
            spec.group,
        )
