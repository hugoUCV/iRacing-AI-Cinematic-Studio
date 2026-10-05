"""Detectores de eventos."""
from __future__ import annotations

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.battle import BattleDetector
from engines.analyzer.events.fast_lap import FastLapDetector
from engines.analyzer.events.off_track import OffTrackDetector
from engines.analyzer.events.overtake import OvertakeDetector
from engines.analyzer.events.spin import SpinDetector
from engines.analyzer.events.start_finish import StartFinishDetector


def get_detectors() -> list[EventDetector]:
    """Registro de detectores activos (orden de ejecución)."""
    return [
        StartFinishDetector(),
        OffTrackDetector(),
        SpinDetector(),
        OvertakeDetector(),
        BattleDetector(),
        FastLapDetector(),
    ]
