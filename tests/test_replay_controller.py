"""Tests del SDKController con un fake del SDK (sin simulador).

El fake replica la superficie de pyirsdk que usa el controller (vive en
tests.fakes, compartido con el scanner).
"""
from __future__ import annotations

from core.models import CameraSpec

from engines.replay.sdk_controller import SDKController, VC_START
from tests.fakes import FakeIR


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
    assert info.track_length_m == 7004.0  # "7.004 km"
    # el pace car se excluye
    assert [d.car_idx for d in info.drivers] == [0, 1]
    assert info.drivers[0].name == "Hugo Ferrer"
    assert info.drivers[0].car_number_raw == 7


def test_camera_groups():
    ctrl, _ = make_controller()
    ctrl.session_info()  # rellena drivers
    groups = ctrl.camera_groups()
    assert (3, "TV1") in groups


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
