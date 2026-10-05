"""Detector de batallas: pares de coches rodando pegados de forma sostenida.

Ventana maximal donde |LapDistPct_a - LapDistPct_b| ≤ gap_pct, ambos en pista,
misma vuelta y velocidad estimada > 5 m/s. Solo se emiten batallas de ≥4 s.
"""
from __future__ import annotations

from core.models import Event, EventType, SessionModel

from engines.analyzer.events.base import EventDetector
from engines.analyzer.events.util import BASE_IMPORTANCE, clamp01, on_track
from engines.analyzer.frames import Frame, speed_at

GAP_PCT = 0.004  # ≈ 0.4% de vuelta (≈ 28 m en 7 km)
MIN_DURATION_S = 4.0
MAX_EVENTS = 40


class BattleDetector(EventDetector):
    name = "battle"

    def detect(self, frames: list[Frame], model: SessionModel) -> list[Event]:
        if len(frames) < 10:
            return []
        track_len = model.session.track_length_m
        car_indices = sorted({c for f in frames for c in f.cars})
        speeds = {c: speed_at(c, frames, track_len) if track_len else {} for c in car_indices}

        candidates: list[tuple[float, float, int, int, float]] = []  # t0, t1, a, b, gap_min
        n = len(car_indices)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = car_indices[i], car_indices[j]
                run_start: float | None = None
                gap_min = 1.0
                for fi, f in enumerate(frames):
                    sa, sb = f.get(a), f.get(b)
                    close = (
                        sa is not None
                        and sb is not None
                        and on_track(f, a)
                        and on_track(f, b)
                        and sa.laps == sb.laps
                        and abs(sa.lap_dist_pct - sb.lap_dist_pct) <= GAP_PCT
                        and speeds[a].get(fi, 99.0) > 5.0
                        and speeds[b].get(fi, 99.0) > 5.0
                    )
                    if close:
                        if run_start is None:
                            run_start = f.t_s
                        gap_min = min(gap_min, abs(sa.lap_dist_pct - sb.lap_dist_pct))
                    else:
                        if run_start is not None and f.t_s - run_start >= MIN_DURATION_S:
                            candidates.append((run_start, f.t_s, a, b, gap_min))
                        run_start = None
                if run_start is not None and frames[-1].t_s - run_start >= MIN_DURATION_S:
                    candidates.append((run_start, frames[-1].t_s, a, b, gap_min))

        # quedarse con las más largas y cercanas
        candidates.sort(key=lambda c: (-(c[1] - c[0]), c[4]))
        events: list[Event] = []
        for (t0, t1, a, b, gap_min) in candidates[:MAX_EVENTS]:
            dur = t1 - t0
            events.append(
                Event(
                    id=f"{self.name}-{len(events):04d}",
                    type=EventType.BATTLE,
                    start_s=t0,
                    end_s=t1,
                    drivers=[a, b],
                    target=a,
                    importance=clamp01(
                        BASE_IMPORTANCE[EventType.BATTLE] + 0.15 * min(1.0, dur / 20.0)
                    ),
                    metadata={
                        "duracion_s": round(dur, 1),
                        "gap_pct_min": round(gap_min * 100, 3),
                    },
                )
            )
        return events
