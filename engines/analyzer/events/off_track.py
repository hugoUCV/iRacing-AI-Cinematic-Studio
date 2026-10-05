"""Detector de salidas de pista (TrkLoc: on_track → off_track)."""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import (
    BASE_IMPORTANCE,
    LOC_OFF_TRACK,
    LOC_ON_TRACK,
    clamp01,
    mean_dt,
)
from engines.analyzer.frames import Frame


class OffTrackDetector(EventDetector):
    name = "off_track"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        events: list[Event] = []
        dt = mean_dt(frames)
        min_frames = max(2, int(0.3 / dt)) if dt > 0 else 2

        # estado por coche: None = en pista, valor = frame de inicio de salida
        active: dict[int, float] = {}
        for f in frames:
            for car, s in f.cars.items():
                if s.track_loc == LOC_OFF_TRACK:
                    if car not in active:
                        active[car] = f.t_s
                elif s.track_loc == LOC_ON_TRACK:
                    if car in active:
                        start = active.pop(car)
                        # filtrar parpadeos de 1 frame
                        frame_count = max(1, int((f.t_s - start) / dt)) if dt > 0 else 1
                        if frame_count >= min_frames:
                            events.append(
                                Event(
                                    id=f"{self.name}-{len(events):04d}",
                                    type=EventType.OFF_TRACK,
                                    start_s=start,
                                    end_s=f.t_s,
                                    drivers=[car],
                                    target=car,
                                    importance=clamp01(BASE_IMPORTANCE[EventType.OFF_TRACK]),
                                    metadata={
                                        "surface": s.surface,
                                        "duracion_s": round(f.t_s - start, 2),
                                    },
                                )
                            )
        # salidas aún activas al final del scan
        for car, start in active.items():
            end = frames[-1].t_s
            if end - start >= 0.3:
                events.append(
                    Event(
                        id=f"{self.name}-{len(events):04d}",
                        type=EventType.OFF_TRACK,
                        start_s=start,
                        end_s=end,
                        drivers=[car],
                        target=car,
                        importance=clamp01(BASE_IMPORTANCE[EventType.OFF_TRACK]),
                        metadata={"surface": 0, "duracion_s": round(end - start, 2)},
                    )
                )
        return events
