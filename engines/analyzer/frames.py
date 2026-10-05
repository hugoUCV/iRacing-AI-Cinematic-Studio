"""Frames del scan: muestras por coche en un instante de sesión.

Estructuras ligeras (dataclasses): el scan produce miles de frames y no
queremos el coste de Pydantic por muestra.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CarSample:
    position: int = -1
    lap_dist_pct: float = 0.0
    track_loc: int = -1  # TrkLoc: -1 not_in_world, 0 off_track, 3 on_track
    surface: int = 0  # TrkSurf: material
    last_lap_s: float = 0.0
    laps: int = 0
    f2_s: float = 0.0
    on_pit: bool = False


@dataclass
class Frame:
    t_s: float
    cars: dict[int, CarSample] = field(default_factory=dict)

    def get(self, car_idx: int) -> CarSample | None:
        return self.cars.get(car_idx)


def speed_at(
    car_idx: int,
    frames: list[Frame],
    track_length_m: float | None,
    window_s: float = 1.0,
) -> dict[int, float]:
    """Velocidad estimada por coche (m/s) en cada frame, derivada de
    LapDistPct y la longitud de pista (no hay velocidad por coche remoto en
    el SDK). Maneja el wrap de vuelta (dist pct 1.0 → 0.0).

    Devuelve {índice_de_frame: velocidad} para los frames donde es calculable.
    """
    if not track_length_m:
        return {}
    out: dict[int, float] = {}
    prev: dict[int, tuple[float, float]] = {}  # car_idx → (t, dist_pct)
    for i, f in enumerate(frames):
        sample = f.get(car_idx)
        if sample is None or sample.position < 0:
            continue
        if car_idx in prev:
            t0, d0 = prev[car_idx]
            dt = f.t_s - t0
            if dt >= 1e-3:
                dd = sample.lap_dist_pct - d0
                if dd < -0.9:  # wrap de vuelta
                    dd += 1.0
                if abs(dd) < 0.3 and dt <= window_s * 3:  # filtro de ruido
                    out[i] = dd * track_length_m / dt
        prev[car_idx] = (f.t_s, sample.lap_dist_pct)
    return out
