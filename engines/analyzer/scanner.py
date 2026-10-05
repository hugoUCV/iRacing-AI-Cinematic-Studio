"""Scanner: convierte el replay abierto en SessionModel (cacheado) + frames.

Flujo: seek al inicio de la sesión objetivo → reproducir a velocidad alta →
samplear la memoria compartida → detectar eventos → cachear el modelo.
"""
from __future__ import annotations

import time
from pathlib import Path

from core.models import Event, LapRecord, SessionModel
from core.models import SessionInfo

from engines.analyzer.events import get_detectors
from engines.analyzer.frames import CarSample, Frame
from engines.replay.base import ReplayController
from utils.cache import JsonCache, content_hash
from utils.config import ScanConfig

STALL_TIMEOUT_S = 6.0  # sin avance de replay durante este tiempo → fin del scan


class ScanCancelled(Exception):
    """El usuario canceló el escaneo."""


def _fmt(t: float) -> str:
    return f"{int(t // 60):d}:{int(t % 60):02d}"


def replay_fingerprint(replay_path: Path) -> str:
    """Identidad estable de la replay: ruta + tamaño + mtime. El contenido del
    .rpy no se parsea (ver docs/01-analisis-tecnico.md)."""
    try:
        st = replay_path.stat()
        return content_hash(str(replay_path), st.st_size, st.st_mtime_ns, "v1")
    except OSError:
        return content_hash(str(replay_path), "v1")


class Scanner:
    def __init__(
        self,
        controller: ReplayController,
        config: ScanConfig | None = None,
        cache_dir: Path | None = None,
        stall_timeout_s: float = STALL_TIMEOUT_S,
    ):
        self.controller = controller
        self.config = config or ScanConfig()
        self.cache = JsonCache(cache_dir) if cache_dir else None
        self.stall_timeout_s = stall_timeout_s

    # ── API ───────────────────────────────────────────────────────────────

    def scan(
        self,
        session: SessionInfo,
        replay_path: Path | None = None,
        detectors: list | None = None,
        on_progress=None,
        cancel=None,
    ) -> tuple[SessionModel, list[Frame]]:
        """Escanea la sesión. Si hay caché válida, devuelve el modelo cacheado
        (frames vacíos) sin tocar el simulador.

        on_progress(fraction: float, message: str) se llama durante el scan
        (0.0–1.0); None si no interesa (CLI/tests).

        `cancel` (threading.Event) permite abortar: se lanza ScanCancelled.
        """
        key = None
        if self.cache and replay_path is not None:
            key = content_hash(
                replay_fingerprint(replay_path), session.session_num, "modelo-v1"
            )
            cached = self.cache.load(key)
            if cached:
                if on_progress:
                    on_progress(1.0, "análisis recuperado de caché")
                return SessionModel.model_validate(cached), []

        frames = self._collect_frames(session, on_progress, cancel)
        model = self._build_model(session, frames, detectors or get_detectors(), on_progress)
        if self.cache and key:
            self.cache.save(key, model.model_dump(mode="json"))
        return model, frames

    # ── recolección ───────────────────────────────────────────────────────

    def _collect_frames(
        self, session: SessionInfo, on_progress=None, cancel=None
    ) -> list[Frame]:
        ctrl = self.controller
        frames: list[Frame] = []
        seen_times: set[int] = set()
        last_report_s = -1.0

        ctrl.seek_session_time(session.session_num, 0)
        ctrl.play(speed=self.config.speed)

        limit_s = min(
            self.config.max_duration_s,
            session.duration_s + 30 if session.duration_s else self.config.max_duration_s,
        )
        last_advance = time.monotonic()
        last_t = -1.0
        poll = 1.0 / max(self.config.poll_hz, 1.0)

        try:
            while True:
                if cancel is not None and cancel.is_set():
                    raise ScanCancelled()
                snap = ctrl.read()
                t = snap.get("ReplaySessionTime")
                if t is None:
                    break
                t = float(t)
                # dedupe por centésima de segundo
                key_t = int(t * 100)
                if t > last_t and key_t not in seen_times:
                    seen_times.add(key_t)
                    frame = self._extract_frame(snap, t)
                    if frame.cars:
                        frames.append(frame)
                    last_t = t
                    last_advance = time.monotonic()
                if on_progress and t - last_report_s >= 1.0 and limit_s > 0:
                    on_progress(
                        min(t / limit_s, 1.0),
                        f"Escaneando… {_fmt(t)} / {_fmt(limit_s)} "
                        f"({min(int(t / limit_s * 100), 100)}%)",
                    )
                    last_report_s = t
                if t >= limit_s:
                    break
                if time.monotonic() - last_advance > self.stall_timeout_s:
                    break  # la replay terminó (o quedó en pausa)
                time.sleep(poll)
        finally:
            ctrl.pause()

        return frames

    def _extract_frame(self, snap: dict, t: float) -> Frame:
        """Convierte el snapshot del SDK en un Frame (arrays CarIdx*)."""
        cars: dict[int, CarSample] = {}

        def arr(name: str):
            v = snap.get(name)
            return v if isinstance(v, list) else []

        positions = arr("CarIdxPosition")
        dist = arr("CarIdxLapDistPct")
        loc = arr("CarIdxTrackSurface")
        surf = arr("CarIdxTrackSurfaceMaterial")
        last_lap = arr("CarIdxLastLapTime")
        laps = arr("CarIdxLapCompleted")
        f2 = arr("CarIdxF2Time")
        pit = arr("CarIdxOnPitRoad")

        n = len(positions)
        for i in range(n):
            pos = positions[i]
            if pos is None or pos < 0:
                continue
            cars[i] = CarSample(
                position=int(pos),
                lap_dist_pct=float(dist[i]) if i < len(dist) and dist[i] is not None else 0.0,
                track_loc=int(loc[i]) if i < len(loc) and loc[i] is not None else -1,
                surface=int(surf[i]) if i < len(surf) and surf[i] is not None else 0,
                last_lap_s=float(last_lap[i]) if i < len(last_lap) and last_lap[i] is not None else 0.0,
                laps=int(laps[i]) if i < len(laps) and laps[i] is not None else 0,
                f2_s=float(f2[i]) if i < len(f2) and f2[i] is not None else 0.0,
                on_pit=bool(pit[i]) if i < len(pit) and pit[i] is not None else False,
            )
        return Frame(t_s=t, cars=cars)

    # ── construcción del modelo ───────────────────────────────────────────

    def _build_model(
        self, session: SessionInfo, frames: list[Frame], detectors: list,
        on_progress=None,
    ) -> SessionModel:
        model = SessionModel(
            session=session,
            sample_rate_hz=60,
            source=content_hash("frames", len(frames)),
        )
        model.laps = self._collect_laps(frames)
        events: list[Event] = []
        total = len(detectors)
        for i, det in enumerate(detectors):
            if on_progress:
                on_progress(
                    0.90 + 0.10 * i / max(total, 1),
                    f"Analizando eventos ({i + 1}/{total}): {det.name}…",
                )
            try:
                events.extend(det.detect(frames, model))
            except Exception as exc:  # un detector roto no hunde el scan
                events.append(
                    Event(
                        id=f"detector-error-{det.name}",
                        type="position_change",  # placeholder; se filtra luego
                        start_s=0.0,
                        end_s=0.0,
                        importance=0.0,
                        metadata={"error": str(exc)},
                    )
                )
        if on_progress:
            on_progress(1.0, "Análisis completado")
        # filtrar eventos marcados como error interno
        model.events = [e for e in events if e.importance > 0.0]
        model.events.sort(key=lambda e: e.start_s)
        return model

    @staticmethod
    def _collect_laps(frames: list[Frame]) -> list[LapRecord]:
        """Cruces de línea de meta por coche (wrap de LapDistPct)."""
        records: list[LapRecord] = []
        prev: dict[int, float] = {}
        laps: dict[int, int] = {}
        for f in frames:
            for idx, s in f.cars.items():
                d = s.lap_dist_pct
                if idx in prev and prev[idx] > 0.9 and d < 0.1:
                    lap = laps.get(idx, 0) + 1
                    laps[idx] = lap
                    records.append(
                        LapRecord(driver_id=idx, lap=lap, time_s=f.t_s, valid=True)
                    )
                prev[idx] = d
        return records
