"""Detectores de eventos: contrato común.

Cada detector consume series temporales (muestras del scan a 60 Hz) y emite
Event[]. El scoring de importance (importance.py) normaliza 0..1 antes de
entregar la lista al director.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import Event, SessionModel

from engines.analyzer.frames import Frame


class EventDetector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        """Produce eventos a partir de las muestras del scan.

        `model` aporta contexto (sesión, pilotos); los eventos referencian
        car_idx y tiempos de sesión (ReplaySessionTime).
        """
