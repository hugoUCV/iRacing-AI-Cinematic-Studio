"""Constructor de escenarios sintéticos para los tests de detectores.

`scenario(segments, dt)` construye frames a partir de segmentos de estado
constante: [(duración_s, {car_idx: {campo: valor}})]. El campo especial
"dist_rate" avanza lap_dist_pct a esa velocidad (fracción de vuelta/s), lo que
permite simular movimiento y derivar velocidades.
"""
from __future__ import annotations

from engines.analyzer.frames import CarSample, Frame

DEFAULTS = dict(
    position=1,
    lap_dist_pct=0.0,
    track_loc=3,  # on_track
    surface=1,
    last_lap_s=0.0,
    laps=0,
    f2_s=0.0,
    on_pit=False,
)


def scenario(segments: list[tuple[float, dict[int, dict]]], dt: float = 0.1) -> list[Frame]:
    frames: list[Frame] = []
    state: dict[int, dict] = {}
    t = 0.0
    for dur, updates in segments:
        n = max(1, int(round(dur / dt)))
        for k in range(n):
            t += dt
            for car, upd in updates.items():
                st = state.setdefault(car, dict(DEFAULTS))
                for field, v in upd.items():
                    if field == "dist_rate":
                        st["lap_dist_pct"] = (st["lap_dist_pct"] + v * dt) % 1.0
                    elif k == 0:  # los campos fijos solo cambian al entrar
                        st[field] = v
            frames.append(
                Frame(t_s=round(t, 2), cars={c: CarSample(**state[c]) for c in state})
            )
    return frames


def set_last_lap_at_crossings(
    frames: list[Frame], car: int, lap_times: list[float]
) -> None:
    """Asigna CarIdxLastLapTime en cada cruce de línea (como haría el SDK)."""
    prev = -1.0
    idx = 0
    for f in frames:
        s = f.get(car)
        if s is None:
            continue
        d = s.lap_dist_pct
        if prev > 0.9 and d < 0.1 and idx < len(lap_times):
            s.last_lap_s = lap_times[idx]
            idx += 1
        prev = d
