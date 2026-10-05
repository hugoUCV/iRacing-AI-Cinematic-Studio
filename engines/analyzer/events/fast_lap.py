"""Detector de vueltas rápidas: mejor vuelta personal por piloto.

En cada cruce de línea (wrap de LapDistPct) se lee CarIdxLastLapTime; si mejora
el mejor tiempo personal del piloto (o es su primera vuelta válida) se emite un
evento fast_lap, con bonus si además es la vuelta más rápida de la sesión.
"""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import BASE_IMPORTANCE, clamp01
from engines.analyzer.frames import Frame


class FastLapDetector(EventDetector):
    name = "fast_lap"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        events: list[Event] = []
        best: dict[int, float] = {}
        session_best = 1e9
        prev: dict[int, float] = {}
        laps: dict[int, int] = {}

        for f in frames:
            for car, s in f.cars.items():
                if s.position < 0:
                    continue
                d = s.lap_dist_pct
                crossing = car in prev and prev[car] > 0.9 and d < 0.1
                prev[car] = d
                if not crossing:
                    continue
                lap = laps.get(car, 0) + 1
                laps[car] = lap
                t_lap = s.last_lap_s
                if t_lap is None or t_lap <= 0.0:
                    continue  # vuelta inválida o aún sin dato
                if car not in best or t_lap < best[car] - 0.005:
                    is_session_best = t_lap < session_best
                    if is_session_best:
                        session_best = t_lap
                    best[car] = t_lap
                    imp = BASE_IMPORTANCE[EventType.FAST_LAP]
                    if is_session_best:
                        imp += 0.25
                    events.append(
                        Event(
                            id=f"{self.name}-{len(events):04d}",
                            type=EventType.FAST_LAP,
                            start_s=max(0.0, f.t_s - 2.0),
                            end_s=f.t_s + 1.0,
                            drivers=[car],
                            target=car,
                            lap=lap,
                            importance=clamp01(imp),
                            metadata={
                                "vuelta_s": round(t_lap, 3),
                                "mejor_de_sesion": is_session_best,
                            },
                        )
                    )
        return events
