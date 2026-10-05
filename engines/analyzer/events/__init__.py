"""Detectores de eventos."""
from __future__ import annotations

from engines.analyzer.events.base import EventDetector


def get_detectors() -> list[EventDetector]:
    """Registro de detectores activos (orden de ejecución)."""
    # Los detectores reales llegan en los siguientes commits.
    return []
