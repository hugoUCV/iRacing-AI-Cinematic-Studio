"""Captura nativa de iRacing (broadcast video_capture, sin OBS).

iRacing escribe el vídeo en su carpeta de capturas con nombre propio; al parar
movemos el archivo más reciente a la ruta del plano. Requiere tener activada la
captura de vídeo en las opciones del sim (Graphics → Enable video capture).
"""
from __future__ import annotations

import time
from pathlib import Path

from engines.replay.sdk_controller import VC_START, VC_STOP

from services.capture.base import CaptureBackend
from utils.config import default_videos_dir

VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov"}


class CaptureError(RuntimeError):
    pass


class NativeCapture(CaptureBackend):
    name = "native"

    def __init__(self, controller, videos_dir: Path | None = None, settle_s: float = 0.6):
        self.controller = controller
        self.videos_dir = videos_dir or default_videos_dir()
        self.settle_s = settle_s
        self._before: set[Path] = set()
        self._target: Path | None = None

    def supports_audio(self) -> bool:
        # Por verificar en spike S2 (docs/01-analisis-tecnico.md §6).
        return False

    def start(self, target: Path) -> None:
        if self.videos_dir is None:
            raise CaptureError(
                "No se encontró la carpeta de capturas de iRacing "
                "(Documents/iRacing/videos). Configúrala en capture.videos_dir."
            )
        self._before = {p for p in self.videos_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS}
        self._target = target
        self.controller.video_capture(VC_START)

    def stop(self) -> Path | None:
        self.controller.video_capture(VC_STOP)
        time.sleep(self.settle_s)  # dejar que iRacing cierre el archivo
        assert self.videos_dir is not None and self._target is not None
        newest: tuple[float, Path] | None = None
        for p in self.videos_dir.iterdir():
            if p.suffix.lower() not in VIDEO_EXTS or p in self._before:
                continue
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if newest is None or m > newest[0]:
                newest = (m, p)
        if newest is None:
            raise CaptureError(
                "iRacing no produjo ningún archivo de captura. Activa la captura "
                "de vídeo en las opciones del sim (Enable video capture)."
            )
        src = newest[1]
        self._target.parent.mkdir(parents=True, exist_ok=True)
        # mover (mismo disco) o copiar
        try:
            src.rename(self._target)
        except OSError:
            import shutil

            shutil.copy2(src, self._target)
        return self._target
