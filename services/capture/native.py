"""Captura nativa de iRacing (broadcast video_capture, sin OBS).

iRacing escribe el vídeo en su carpeta de capturas con nombre propio; al parar
movemos el archivo más reciente a la ruta del plano. Requiere tener activada la
captura de vídeo en las opciones del sim (app.ini: [Video] vidCaptureEnable=1,
o Graphics → Enable video capture).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from engines.replay.sdk_controller import VC_START, VC_STOP

from services.capture.base import CaptureBackend
from utils.config import default_videos_dir

VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov"}

log = logging.getLogger(__name__)


def default_app_ini() -> Path:
    return Path.home() / "Documents" / "iRacing" / "app.ini"


def video_capture_enabled(app_ini: Path | None = None) -> bool | None:
    """¿Tiene iRacing activada su captura de vídeo? (None si no se puede saber)."""
    path = app_ini or default_app_ini()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^\s*vidCaptureEnable\s*=\s*(\d+)", text, re.M)
    if not m:
        return None
    return int(m.group(1)) == 1


class CaptureError(RuntimeError):
    pass


class NativeCapture(CaptureBackend):
    name = "native"

    def __init__(
        self,
        controller,
        videos_dir: Path | None = None,
        settle_s: float = 0.6,
        app_ini: Path | None = None,
    ):
        self.controller = controller
        self.videos_dir = videos_dir or default_videos_dir()
        self.settle_s = settle_s
        self.app_ini = app_ini or default_app_ini()
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
        if video_capture_enabled(self.app_ini) is False:
            raise CaptureError(
                "La captura de vídeo de iRacing está desactivada. Actívala en "
                "Opciones → Gráficos → 'Enable video capture' (o pon "
                "vidCaptureEnable=1 en Documents/iRacing/app.ini) y reinicia "
                "iRacing."
            )
        self._before = {p for p in self.videos_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS}
        self._target = target
        self.controller.video_capture(VC_START)

    def stop(self) -> Path | None:
        self.controller.video_capture(VC_STOP)
        assert self.videos_dir is not None and self._target is not None
        # iRacing escribe el archivo de forma asíncrona: esperamos hasta ~5 s
        # a que aparezca un archivo nuevo antes de rendirnos.
        deadline = time.monotonic() + self.settle_s + 4.0
        newest: tuple[float, Path] | None = None
        while time.monotonic() < deadline:
            newest = self._find_newest()
            if newest is not None:
                break
            time.sleep(0.3)
        if newest is None:
            log.warning(
                "no apareció ningún archivo en %s tras %.1fs (antes había %d vídeos)",
                self.videos_dir, self.settle_s + 4.0, len(self._before),
            )
            raise CaptureError(
                "iRacing no produjo ningún archivo de captura. Causas habituales:\n"
                "1) La captura de vídeo está desactivada (Opciones → Gráficos → "
                "'Enable video capture'). Si la acabas de activar, REINICIA iRacing.\n"
                "2) La carpeta de capturas no es Documents/iRacing/videos "
                "(configúrala en capture.videos_dir)."
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

    def _find_newest(self) -> tuple[float, Path] | None:
        assert self.videos_dir is not None
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
        return newest
