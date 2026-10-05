"""SDKController: implementación del ReplayController sobre pyirsdk.

Única puerta de acceso al simulador. Nada fuera de engines/replay importa
pyirsdk. Para tests se inyecta un cliente duck-typed (FakeIR).

Superficie verificada del SDK (pyirsdk irsdk.py):
  - ir.startup() / ir.is_initialized / ir.is_connected
  - ir.freeze_var_buffer_latest() + ir[var]  (arrays CarIdx*, Replay*)
  - ir['WeekendInfo' | 'SessionInfo' | 'DriverInfo' | 'CameraInfo'] (YAML)
  - ir.replay_search_session_time(session_num, ms)        (L545)
  - ir.replay_set_play_speed(speed, slow_motion)          (L512)
  - ir.cam_switch_num(car_number, group, camera)          (L506)
  - ir.video_capture(mode)                                (L548)
"""
from __future__ import annotations

import re
import time
from typing import Any

from core.models import DriverInfo, SessionInfo

from engines.replay.base import ReplayController

# Variables leídas en cada snapshot del scan.
SNAPSHOT_VARS = [
    "ReplaySessionTime",
    "ReplaySessionNum",
    "ReplayFrameNum",
    "IsReplayPlaying",
    "ReplayPlaySpeed",
    "ReplayPlaySlowMotion",
    "CamCarIdx",
    "CamGroupNumber",
    "CamCameraNumber",
    "CarIdxPosition",
    "CarIdxLapDistPct",
    "CarIdxTrackSurface",
    "CarIdxTrackSurfaceMaterial",
    "CarIdxLastLapTime",
    "CarIdxLapCompleted",
    "CarIdxF2Time",
    "CarIdxOnPitRoad",
]

# Broadcast video_capture (verificado en pyirsdk irsdk.py L255-261).
VC_START = 1
VC_STOP = 2
VC_TOGGLE = 3


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class SDKController(ReplayController):
    def __init__(self, ir: Any = None):
        self._ir = ir  # None → instancia real de pyirsdk (lazy)
        self._drivers: list[DriverInfo] = []

    # ── conexión ──────────────────────────────────────────────────────────

    def _get_ir(self) -> Any:
        if self._ir is None:
            import irsdk

            self._ir = irsdk.IRSDK()
        return self._ir

    def connect(self) -> bool:
        ir = self._get_ir()
        if not (getattr(ir, "is_initialized", False) and ir.is_connected):
            try:
                ir.startup()
            except Exception:
                return False
        return bool(ir.is_connected)

    def is_replay_playing(self) -> bool:
        return self.read().get("IsReplayPlaying") == 1

    # ── lectura ───────────────────────────────────────────────────────────

    def read(self) -> dict[str, Any]:
        """Snapshot de las variables de interés (freeze previo)."""
        ir = self._get_ir()
        out: dict[str, Any] = {}
        try:
            ir.freeze_var_buffer_latest()
        except Exception:
            pass
        names = getattr(ir, "var_headers_names", None) or []
        for var in SNAPSHOT_VARS:
            if var in names:
                try:
                    out[var] = ir[var]
                except Exception:
                    continue
        return out

    def session_info(self) -> SessionInfo:
        ir = self._get_ir()
        wi = ir["WeekendInfo"] or {}
        si = ir["SessionInfo"] or {}
        di = ir["DriverInfo"] or {}

        sessions = si.get("Sessions") or []
        if not sessions:
            raise RuntimeError("No hay sesiones en la replay (¿replay abierta?)")

        current = self.read().get("ReplaySessionNum")
        race = next((s for s in sessions if s.get("SessionType") == "Race"), None)
        session = race or next(
            (s for s in sessions if s.get("SessionNum") == current), sessions[0]
        )

        self._drivers = []
        for d in di.get("Drivers", []):
            if d.get("CarIsPaceCar") == 1:
                continue
            raw = d.get("CarNumberRaw")
            self._drivers.append(
                DriverInfo(
                    car_idx=int(d["CarIdx"]),
                    car_number=str(d.get("CarNumber", "")),
                    name=d.get("UserName") or d.get("DriverName") or f"#{d.get('CarNumber', '?')}",
                    team=d.get("TeamName"),
                    irating=d.get("IRating"),
                    car_class=d.get("CarClassShortName"),
                    car_name=d.get("CarScreenName"),
                    car_number_raw=int(raw) if raw is not None else None,
                )
            )

        return SessionInfo(
            session_num=int(session.get("SessionNum", 0)),
            session_type=str(session.get("SessionType", "Race")),
            track_name=str(wi.get("TrackName", "desconocido")),
            track_display=wi.get("TrackDisplayName"),
            duration_s=_num(session.get("SessionTime")),
            laps_total=self._parse_laps(session.get("SessionLaps")),
            track_length_m=self._parse_length(wi.get("TrackLength")),
            drivers=self._drivers,
        )

    @staticmethod
    def _parse_length(value: Any) -> float | None:
        """'4.352 km' | '2.5 miles' → metros."""
        if not value:
            return None
        m = re.match(r"\s*([\d.]+)\s*(km|mi|mile|miles)", str(value), re.I)
        if not m:
            return None
        n = float(m.group(1))
        return n * 1609.34 if m.group(2).lower().startswith("mi") else n * 1000.0

    @staticmethod
    def _parse_laps(value: Any) -> int | None:
        if value is None:
            return None
        m = re.match(r"\s*(\d+)", str(value))
        return int(m.group(1)) if m else None

    def camera_groups(self) -> list[tuple[int, str]]:
        ir = self._get_ir()
        ci = ir["CameraInfo"] or {}
        return [
            (int(g.get("GroupNum")), str(g.get("GroupName", f"grupo{g.get('GroupNum')}")))
            for g in (ci.get("Groups") or [])
        ]

    # ── control ───────────────────────────────────────────────────────────

    def seek_session_time(self, session_num: int, session_time_ms: int) -> None:
        self._get_ir().replay_search_session_time(int(session_num), int(session_time_ms))

    def set_camera(self, spec) -> None:
        ir = self._get_ir()
        if spec.target is not None:
            driver = next((d for d in self._drivers if d.car_idx == spec.target), None)
            raw = driver.car_number_raw if driver else None
        else:
            raw = None
        if raw is None:
            # sin coche objetivo: mantener el coche cámara actual
            cam = self.read().get("CamCarIdx", 0)
            driver = next((d for d in self._drivers if d.car_idx == cam), None)
            raw = driver.car_number_raw if driver else 1
        ir.cam_switch_num(str(raw), int(spec.group), int(spec.number))

    def play(self, speed: float = 1.0, slow_motion: bool = False) -> None:
        self._get_ir().replay_set_play_speed(int(speed), 1 if slow_motion else 0)

    def pause(self) -> None:
        self._get_ir().replay_set_play_speed(0)

    def video_capture(self, mode: int) -> None:
        self._get_ir().video_capture(int(mode))

    def wait_until_session_time(self, target_s: float, timeout_s: float) -> float:
        """Sondea ReplaySessionTime hasta `target_s` o timeout. Devuelve el
        tiempo alcanzado."""
        t0 = time.monotonic()
        while True:
            t = self.read().get("ReplaySessionTime")
            if t is not None and float(t) >= target_s:
                return float(t)
            if time.monotonic() - t0 >= timeout_s:
                return float(t) if t is not None else -1.0
            time.sleep(0.1)

    def verify(self) -> dict[str, Any]:
        snap = self.read()
        return {
            "cam_car_idx": snap.get("CamCarIdx"),
            "cam_group": snap.get("CamGroupNumber"),
            "cam_number": snap.get("CamCameraNumber"),
            "session_time_s": snap.get("ReplaySessionTime"),
            "play_speed": snap.get("ReplayPlaySpeed"),
            "playing": snap.get("IsReplayPlaying"),
        }
