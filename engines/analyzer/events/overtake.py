"""Detector de adelantamientos: inversión de orden entre pares de coches.

Compara el orden por CarIdxPosition entre frames consecutivos. Un par (a, b)
que invierte el orden con la misma vuelta completada, ambos en pista y sin
pit ⇒ adelantamiento de a sobre b. Los cruces repetidos se fusionan en ≤1.5 s.
"""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import BASE_IMPORTANCE, clamp01, on_track
from engines.analyzer.frames import Frame


class OvertakeDetector(EventDetector):
    name = "overtake"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        events: list[Event] = []
        prev_order: list[int] | None = None
        pending: dict[tuple[int, int], float] = {}  # (ganador, perdedor) → t

        def flush_pending(t: float):
            for (a, b), t0 in list(pending.items()):
                if t - t0 > 1.5:  # ventana de fusión superada
                    events.append(self._make(a, b, t0, events))
                    del pending[(a, b)]

        for f in frames:
            order = [
                c
                for c, s in sorted(f.cars.items(), key=lambda kv: kv[1].position)
                if s.position > 0
            ]
            if prev_order is not None and set(order) == set(prev_order):
                # inversiones de pares adyacentes (o cercanos) entre frames
                pos = {c: i for i, c in enumerate(order)}
                prev_pos = {c: i for i, c in enumerate(prev_order)}
                for a in order:
                    for b in order:
                        if a == b:
                            continue
                        passed = prev_pos[a] > prev_pos[b] and pos[a] < pos[b]
                        if not passed:
                            continue
                        same_lap = (
                            f.get(a) is not None
                            and f.get(b) is not None
                            and f.get(a).laps == f.get(b).laps
                        )
                        if not same_lap:
                            continue
                        if on_track(f, a) and on_track(f, b):
                            pending[(a, b)] = pending.get((a, b), f.t_s)
            flush_pending(f.t_s)
            prev_order = order

        for (a, b), t0 in pending.items():
            events.append(self._make(a, b, t0, events))
        return events

    @staticmethod
    def _make(a: int, b: int, t: float, events: list[Event]) -> Event:
        return Event(
            id=f"overtake-{len(events):04d}",
            type=EventType.OVERTAKE,
            start_s=max(0.0, t - 1.0),
            end_s=t + 1.5,
            drivers=[a, b],
            target=a,
            importance=clamp01(BASE_IMPORTANCE[EventType.OVERTAKE]),
            metadata={"adelantador": a, "adelantado": b, "t_cruce_s": round(t, 2)},
        )
