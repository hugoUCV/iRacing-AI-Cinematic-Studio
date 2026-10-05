"""Fakes compartidos del SDK (sin simulador).

FakeIR replica la superficie de pyirsdk que usa SDKController. ScanFakeIR añade
avance de tiempo simulado durante la reproducción, para tests del scanner.
"""
from __future__ import annotations

import time


class FakeIR:
    """Cliente pyirsdk simulado."""

    def __init__(self, replay_time: float = 0.0):
        self.is_initialized = True
        self.is_connected = True
        self.calls: list[str] = []
        self.replay_time = replay_time
        self.speed = 0
        self.session_yaml = {
            "WeekendInfo": {
                "TrackName": "spa",
                "TrackDisplayName": "Circuit de Spa-Francorchamps",
                "TrackLength": "7.004 km",
            },
            "SessionInfo": {
                "Sessions": [
                    {"SessionNum": 0, "SessionType": "Practice", "SessionTime": "1800", "SessionLaps": "unlimited"},
                    {"SessionNum": 1, "SessionType": "Race", "SessionTime": "2340", "SessionLaps": "18 laps"},
                ]
            },
            "DriverInfo": {
                "Drivers": [
                    {"CarIdx": 0, "CarNumber": "7", "CarNumberRaw": 7, "UserName": "Hugo Ferrer",
                     "TeamName": "", "IRating": 2500, "CarClassShortName": "GT3",
                     "CarScreenName": "Porsche 911 GT3 R", "CarIsPaceCar": 0},
                    {"CarIdx": 1, "CarNumber": "21", "CarNumberRaw": 21, "UserName": "Rival",
                     "TeamName": "", "IRating": 2400, "CarClassShortName": "GT3",
                     "CarScreenName": "Porsche 911 GT3 R", "CarIsPaceCar": 0},
                    {"CarIdx": 2, "CarNumber": "1", "CarNumberRaw": 1, "UserName": "Pace Car",
                     "TeamName": "", "IRating": None, "CarClassShortName": "",
                     "CarScreenName": "", "CarIsPaceCar": 1},
                ]
            },
            "CameraInfo": {
                "Groups": [
                    {"GroupNum": 1, "GroupName": "cockpit"},
                    {"GroupNum": 2, "GroupName": "chase"},
                    {"GroupNum": 3, "GroupName": "TV1"},
                    {"GroupNum": 4, "GroupName": "TV2"},
                    {"GroupNum": 10, "GroupName": "chopper"},
                ]
            },
        }
        self.vars = {
            "ReplaySessionTime": self.replay_time,
            "ReplaySessionNum": 1,
            "ReplayFrameNum": int(self.replay_time * 60),
            "IsReplayPlaying": 1,
            "ReplayPlaySpeed": self.speed,
            "ReplayPlaySlowMotion": 0,
            "CamCarIdx": 0,
            "CamGroupNumber": 3,
            "CamCameraNumber": 0,
            "CarIdxPosition": [1, 2, 0],
            "CarIdxLapDistPct": [0.4, 0.39, 0.0],
            "CarIdxTrackSurface": [3, 3, -1],
            "CarIdxTrackSurfaceMaterial": [1, 1, -1],
            "CarIdxLastLapTime": [0.0, 0.0, 0.0],
            "CarIdxLapCompleted": [0, 0, 0],
            "CarIdxF2Time": [0.0, 1.2, 0.0],
            "CarIdxOnPitRoad": [False, False, False],
        }
        self.var_headers_names = list(self.vars.keys())

    # ── superficie pyirsdk ──
    def startup(self): ...

    def freeze_var_buffer_latest(self): ...

    def __getitem__(self, key):
        if key in self.vars:
            return self.vars[key]
        return self.session_yaml.get(key)

    def replay_search_session_time(self, session_num, ms):
        self.calls.append(f"seek:{session_num}:{ms}")
        self.replay_time = ms / 1000.0
        self.vars["ReplaySessionTime"] = self.replay_time

    def replay_set_play_speed(self, speed=0, slow_motion=False):
        self.calls.append(f"speed:{speed}:{1 if slow_motion else 0}")
        self.speed = speed
        self.vars["ReplayPlaySpeed"] = speed
        self.vars["IsReplayPlaying"] = 1 if speed > 0 else 0

    def cam_switch_num(self, car_number, group, camera):
        self.calls.append(f"cam:{car_number}:{group}:{camera}")
        self.vars["CamGroupNumber"] = group

    def video_capture(self, mode):
        self.calls.append(f"vcapture:{mode}")


class ScanFakeIR(FakeIR):
    """FakeIR que avanza el tiempo de replay durante la reproducción.

    La velocidad simulada aplica al avance (speed=4 ⇒ 4 s de replay por segundo
    real) y los coches avanzan por la pista (wrap de vuelta incluido). Al llegar
    a duration_s la replay "termina" (deja de avanzar).
    """

    def __init__(self, duration_s: float, speed_mult: float = 1.0):
        super().__init__()
        self.duration_s = duration_s
        self.speed_mult = speed_mult
        self._last_read = time.monotonic()

    def _advance(self):
        now = time.monotonic()
        dt = now - self._last_read
        self._last_read = now
        if self.speed > 0:
            self.replay_time = min(
                self.duration_s, self.replay_time + self.speed * dt * self.speed_mult
            )
            self.vars["ReplaySessionTime"] = self.replay_time
            self.vars["ReplayFrameNum"] = int(self.replay_time * 60)
            # los coches avanzan: 1 vuelta ≈ 7 s simulados
            for i in (0, 1):
                base = 0.0 if i == 0 else 0.01
                self.vars["CarIdxLapDistPct"][i] = (self.replay_time / 7.0 + base) % 1.0

    def freeze_var_buffer_latest(self):
        self._advance()

    def read_extra_frame(self) -> None:
        """Avanza explícitamente sin pasar por el freeze (útil en tests)."""
        self._advance()
