"""Backend de captura offline: para pruebas y modo dry-run.

No graba nada: simula la captura creando un archivo vacío en la ruta del plano.
Útil para validar la orquestación (runner) sin simulador ni captura real.
"""
from __future__ import annotations

from pathlib import Path

from services.capture.base import CaptureBackend


class OfflineCapture(CaptureBackend):
    name = "offline"

    def __init__(self, created: list[Path] | None = None):
        self.created = created if created is not None else []

    def supports_audio(self) -> bool:
        return False

    def start(self, target: Path) -> None:
        self._target = target

    def stop(self) -> Path | None:
        self._target.parent.mkdir(parents=True, exist_ok=True)
        self._target.touch()
        self.created.append(self._target)
        return self._target
