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

# TrkSurf (verificado en pyirsdk irsdk.py L85-114): materiales que indican
# una salida REAL de pista. Los pianos (rumble 11-14), pintura (9-10) y
# asfalto/hormigón (1-6) son "off_track" en TrkLoc pero no son una salida:
# pasar por un piano o la zona verde no es un incidente.
REAL_OFF_SURFACES = frozenset({
    15, 16, 17, 18,  # grass_1..4
    19, 20, 21, 22,  # dirt_1..4
    23,              # sand
    24, 25,          # gravel_1..2
    26,              # grasscrete
})


def is_real_off_track(sample) -> bool:
    """¿Salida de pista real (hierba/grava/tierra/arena), no piano ni pintura?"""
    return sample.track_loc == LOC_OFF_TRACK and sample.surface in REAL_OFF_SURFACES


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
    "is_real_off_track",
    "REAL_OFF_SURFACES",
]
