"""Captura de vídeo: contrato común.

Implementaciones (MVP 1):
  - NativeCapture: video_capture(start/end) broadcast → la captura integrada
    de iRacing (NVENC/AMF/QSV) escribe el archivo. Sin dependencias externas.
  - ObsCapture: obs-websocket (OBS 28+) → añade audio de escritorio y overlays.

Regla: el ReplayController nunca habla con el backend de captura ni al revés;
la orquestación vive en el servicio de captura guiada (MVP 1).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class CaptureBackend(ABC):
    name: str = "base"

    @abstractmethod
    def start(self, target: Path) -> None:
        """Inicia la captura hacia `target` (extensión según backend)."""

    @abstractmethod
    def stop(self) -> Path | None:
        """Detiene la captura y devuelve el archivo producido."""

    @abstractmethod
    def supports_audio(self) -> bool: ...
