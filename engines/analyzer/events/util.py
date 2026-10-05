"""Utilidades compartidas por los detectores."""
from __future__ import annotations

from core.models import EventType
from engines.analyzer.frames import Frame, speed_at

# Importancia base por tipo (0..1), independiente del piloto protagonista.
# El boost por heroísmo lo aplica el director al planificar.
BASE_IMPORTANCE: dict[EventType, float] = {
    EventType.START: 0.50,
    EventType.FINISH: 0.80,
    EventType.OVERTAKE: 0.78,
    EventType.OFF_TRACK: 0.55,
    EventType.SPIN: 0.72,
    EventType.BATTLE: 0.50,
    EventType.FAST_LAP: 0.35,
    EventType.CONTACT: 0.85,
    EventType.CLOSE_CALL: 0.65,
    EventType.POSITION_CHANGE: 0.60,
    EventType.PIT_STOP: 0.30,
}

# TrkLoc (verificado en pyirsdk irsdk.py L78-83)
LOC_NOT_IN_WORLD = -1
LOC_OFF_TRACK = 0
LOC_ON_TRACK = 3


def mean_dt(frames: list[Frame]) -> float:
    """Separación media entre frames (s)."""
    if len(frames) < 2:
        return 0.0
    return (frames[-1].t_s - frames[0].t_s) / (len(frames) - 1)


def on_track(f: Frame, car: int) -> bool:
    s = f.get(car)
    return s is not None and s.track_loc == LOC_ON_TRACK and not s.on_pit


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


__all__ = [
    "BASE_IMPORTANCE",
    "LOC_NOT_IN_WORLD",
    "LOC_OFF_TRACK",
    "LOC_ON_TRACK",
    "mean_dt",
    "on_track",
    "clamp01",
    "speed_at",
]
