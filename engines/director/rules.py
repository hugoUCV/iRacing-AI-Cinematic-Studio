"""RulesDirector: director determinista (sin IA).

Flujo: puntuar eventos (importancia + boost de héroe) → selección greedy sin
solapamiento (min_gap) → cámara por evento/estilo → relleno de huecos con
planos de variedad rotando cámaras hasta la duración objetivo.
"""
from __future__ import annotations

from core.models import Event, EventType, SessionModel, Shot, ShotPlan, StylePreset

from engines.camera.catalog import CameraCatalog
from engines.camera.shot_library import pick_camera
from engines.director.base import Director
from utils.config import DirectorConfig


class RulesDirector(Director):
    def __init__(self, config: DirectorConfig | None = None, catalog: CameraCatalog | None = None):
        self.config = config or DirectorConfig()
        self.catalog = catalog

    # ── API ───────────────────────────────────────────────────────────────

    def build_plan(
        self,
        model: SessionModel,
        events: list[Event],
        style: StylePreset,
        target_duration_s: int,
        hero_driver: int | None,
    ) -> ShotPlan:
        cfg = self.config
        catalog = self.catalog
        if catalog is None or len(catalog) == 0:
            raise RuntimeError("Se necesita el catálogo de cámaras (conectar con iRacing)")

        session_duration = model.session.duration_s

        # 1) puntuar y ordenar
        scored = sorted(
            ((self._score(e, hero_driver), e) for e in events),
            key=lambda x: (-x[0], x[1].start_s),
        )

        # 2) selección greedy sin solapamiento
        selected: list[tuple[float, float, Event]] = []
        for score, ev in scored:
            if score < 0.25:
                continue
            s = max(0.0, ev.start_s - cfg.anticipation_s)
            e = ev.end_s + cfg.after_s
            if e - s < 1.0:
                e = s + 1.0
            if session_duration:
                e = min(e, session_duration)
            if any(
                not (e <= p_s - cfg.min_gap_s or s >= p_e + cfg.min_gap_s)
                for (p_s, p_e, _) in selected
            ):
                continue
            selected.append((s, e, ev))

        # 3) shots de eventos
        shots: list[Shot] = []
        for s, e, ev in selected:
            target = hero_driver or ev.target
            cam = pick_camera(ev.type, style, catalog, target)
            shots.append(
                Shot(
                    id=f"shot-{len(shots) + 1:03d}",
                    source_start_s=round(s, 2),
                    source_end_s=round(e, 2),
                    camera=cam,
                )
            )

        # 4) relleno de variedad
        shots = self._fill_gaps(
            shots, model, style, target_duration_s, hero_driver, session_duration
        )
        shots.sort(key=lambda sh: sh.source_start_s)

        total = sum(sh.source_end_s - sh.source_start_s for sh in shots)
        notes = [
            f"{len(selected)} eventos seleccionados de {len(events)}",
            f"{len(shots) - len(selected)} planos de relleno",
            f"duración total ≈ {total:.1f} s (objetivo {target_duration_s} s)",
        ]
        if total < target_duration_s * 0.9:
            notes.append("no hay material suficiente para la duración objetivo")
        return ShotPlan(
            shots=shots, style=style, hero_driver=hero_driver, notes=notes
        )

    # ── internos ──────────────────────────────────────────────────────────

    @staticmethod
    def _score(ev: Event, hero: int | None) -> float:
        s = ev.importance
        if hero is not None and hero in ev.drivers:
            s += 0.15
        if hero is not None and hero == ev.target:
            s += 0.05
        return min(1.0, s)

    def _fill_gaps(
        self,
        shots: list[Shot],
        model: SessionModel,
        style: StylePreset,
        target_duration_s: int,
        hero_driver: int | None,
        session_duration: float | None,
    ) -> list[Shot]:
        cfg = self.config
        limit = session_duration or (
            max([sh.source_end_s for sh in shots], default=0.0) + target_duration_s
        )

        # huecos libres entre shots
        intervals: list[tuple[float, float]] = []
        cursor = 0.0
        for sh in sorted(shots, key=lambda x: x.source_start_s):
            if sh.source_start_s - cursor >= cfg.variety_len_s + 1.0:
                intervals.append((cursor, sh.source_start_s))
            cursor = max(cursor, sh.source_end_s)
        if limit - cursor >= cfg.variety_len_s + 1.0:
            intervals.append((cursor, limit))

        # coche del relleno: héroe o primer piloto
        car = hero_driver
        if car is None:
            car = model.session.drivers[0].car_idx if model.session.drivers else None

        out = list(shots)
        current_total = sum(sh.source_end_s - sh.source_start_s for sh in out)
        variety_index = 0
        for (lo, hi) in intervals:
            t = lo
            while t + cfg.variety_len_s <= hi:
                if current_total >= target_duration_s:
                    return out
                cam = pick_camera(
                    EventType.POSITION_CHANGE,  # tipo neutro; se usa is_variety
                    style,
                    self.catalog,
                    car,
                    variety_index=variety_index,
                    is_variety=True,
                )
                out.append(
                    Shot(
                        id=f"fill-{len(out) + 1:03d}",
                        source_start_s=round(t, 2),
                        source_end_s=round(t + cfg.variety_len_s, 2),
                        camera=cam,
                    )
                )
                current_total += cfg.variety_len_s
                variety_index += 1
                t += cfg.variety_len_s + cfg.min_gap_s
            if current_total >= target_duration_s:
                return out
        return out
