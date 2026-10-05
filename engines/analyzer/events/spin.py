"""Detector de trompos: salida de pista con pérdida drástica de velocidad.

Heurística (no hay yaw por coche remoto en el SDK): dentro de una salida de
pista, la velocidad estimada cae por debajo del 40% del máximo de los 3 s
previos en un tramo corto (≤1.5 s). La velocidad se deriva de LapDistPct
(frames.speed_at), ya que el SDK no expone velocidad por coche.
"""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import (
    BASE_IMPORTANCE,
    clamp01,
    is_real_off_track,
)
from engines.analyzer.frames import Frame, speed_at


class SpinDetector(EventDetector):
    name = "spin"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        track_len = model.session.track_length_m
        if not track_len or len(frames) < 4:
            return []
        events: list[Event] = []
        car_indices = sorted({c for f in frames for c in f.cars})

        for car in car_indices:
            speeds = speed_at(car, frames, track_len)
            # ventanas off-track REALES del coche (hierba/grava, no pianos)
            off_windows: list[tuple[float, float]] = []
            in_off = False
            start = 0.0
            for f in frames:
                s = f.get(car)
                if s is not None and is_real_off_track(s):
                    if not in_off:
                        start = f.t_s
                        in_off = True
                else:
                    if in_off:
                        off_windows.append((start, f.t_s))
                        in_off = False
            if in_off:
                off_windows.append((start, frames[-1].t_s))

            for (w_start, w_end) in off_windows:
                if w_end - w_start < 0.3:
                    continue
                # velocidades dentro de la ventana + máximo previo (3 s)
                win_speeds = [
                    (frames[i].t_s, v) for i, v in speeds.items() if w_start - 0.5 <= frames[i].t_s <= w_end
                ]
                prev_max = max(
                    (v for i, v in speeds.items() if w_start - 3.0 <= frames[i].t_s < w_start),
                    default=0.0,
                )
                if prev_max < 12.0 or not win_speeds:  # no iba rápido: no es trompo
                    continue
                # caída: de >70% del máximo previo a <40% en ≤1.5 s
                drop: tuple[float, float] | None = None
                for (t1, v1) in win_speeds:
                    if v1 > 0.7 * prev_max:
                        for (t2, v2) in win_speeds:
                            if 0 < t2 - t1 <= 1.5 and v2 < 0.4 * prev_max:
                                drop = (t1, t2)
                                break
                    if drop:
                        break
                if drop:
                    t1, t2 = drop
                    events.append(
                        Event(
                            id=f"{self.name}-{len(events):04d}",
                            type=EventType.SPIN,
                            start_s=max(w_start, t1 - 0.5),
                            end_s=min(w_end, t2 + 1.0),
                            drivers=[car],
                            target=car,
                            importance=clamp01(BASE_IMPORTANCE[EventType.SPIN]),
                            metadata={
                                "vel_max_previa_ms": round(prev_max, 1),
                                "caida_s": round(t2 - t1, 2),
                            },
                        )
                    )
        return events
