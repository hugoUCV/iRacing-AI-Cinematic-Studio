"""Detector de salida y llegada: primer y último frame de la sesión."""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import BASE_IMPORTANCE, clamp01
from engines.analyzer.frames import Frame


class StartFinishDetector(EventDetector):
    name = "start_finish"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        if not frames:
            return []
        t0 = frames[0].t_s
        t_end = frames[-1].t_s
        events = [
            Event(
                id="start-0000",
                type=EventType.START,
                start_s=t0,
                end_s=min(t0 + 3.0, t_end),
                importance=clamp01(BASE_IMPORTANCE[EventType.START]),
                metadata={},
            ),
            Event(
                id="finish-0000",
                type=EventType.FINISH,
                start_s=max(t0, t_end - 3.0),
                end_s=t_end,
                importance=clamp01(BASE_IMPORTANCE[EventType.FINISH]),
                metadata={},
            ),
        ]
        return events
