"""Tests del SDKController con un fake del SDK (sin simulador).

El fake replica la superficie de pyirsdk que usa el controller: startup,
freeze_var_buffer_latest, __getitem__ (vars y YAML de sesión), var_headers_names
y los métodos broadcast.
"""
from __future__ import annotations

from core.models import CameraSpec

from engines.replay.sdk_controller import SDKController, VC_START


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
            "CarIdxLapDistPct": [0.5, 0.49, 0.0],
            "CarIdxTrackSurface": [3, 3, -1],
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


def make_controller() -> tuple[SDKController, FakeIR]:
    fake = FakeIR()
    return SDKController(ir=fake), fake


def test_connect_and_session_info():
    ctrl, fake = make_controller()
    assert ctrl.connect() is True
    info = ctrl.session_info()
    # elige la sesión Race aunque haya Practice antes
    assert info.session_type == "Race"
    assert info.session_num == 1
    assert info.track_name == "spa"
    assert info.track_display == "Circuit de Spa-Francorchamps"
    assert info.laps_total == 18
    # el pace car se excluye
    assert [d.car_idx for d in info.drivers] == [0, 1]
    assert info.drivers[0].name == "Hugo Ferrer"
    assert info.drivers[0].car_number_raw == 7


def test_camera_groups():
    ctrl, _ = make_controller()
    ctrl.session_info()  # rellena drivers
    groups = ctrl.camera_groups()
    assert ("TV1" in {g[1] for g in groups}) and (3, "TV1") in groups


def test_seek_play_pause_video_capture():
    ctrl, fake = make_controller()
    ctrl.seek_session_time(1, 128_420)
    assert fake.replay_time == 128.42
    ctrl.play(1.0)
    ctrl.pause()
    ctrl.video_capture(VC_START)
    assert fake.calls == [
        "seek:1:128420",
        "speed:1:0",
        "speed:0:0",
        "vcapture:1",
    ]


def test_set_camera_uses_raw_number_and_keeps_current_when_no_target():
    ctrl, fake = make_controller()
    ctrl.session_info()  # rellena drivers
    spec = CameraSpec(group=3, number=0, target=1, group_name="TV1")
    ctrl.set_camera(spec)
    assert fake.calls[-1] == "cam:21:3:0"  # CarNumberRaw del rival
    # sin target: usa el coche cámara actual (car_idx 0 → raw 7)
    ctrl.set_camera(CameraSpec(group=10, number=0, target=None, group_name="chopper"))
    assert fake.calls[-1] == "cam:7:10:0"


def test_wait_until_session_time():
    ctrl, fake = make_controller()
    fake.replay_time = 5.0
    fake.vars["ReplaySessionTime"] = 5.0
    assert ctrl.wait_until_session_time(5.0, 2.0) == 5.0
    # no llega → devuelve lo alcanzado sin bloquear mucho
    fake.replay_time = 4.2
    fake.vars["ReplaySessionTime"] = 4.2
    reached = ctrl.wait_until_session_time(100.0, 0.4)
    assert reached == 4.2


def test_verify_snapshot():
    ctrl, _ = make_controller()
    v = ctrl.verify()
    assert v["cam_group"] == 3 and v["session_time_s"] == 0.0
