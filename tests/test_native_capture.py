"""Tests del backend de captura nativo (detección de vidCaptureEnable)."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.capture.native import (
    CaptureError,
    NativeCapture,
    video_capture_enabled,
)


class FakeCtrl:
    def __init__(self):
        self.calls: list[int] = []

    def video_capture(self, mode: int) -> None:
        self.calls.append(mode)


def test_video_capture_enabled_parses_ini(tmp_path: Path):
    ini = tmp_path / "app.ini"
    ini.write_text("[Video]\nvidCaptureEnable=1\n", encoding="utf-8")
    assert video_capture_enabled(ini) is True
    ini.write_text("[Video]\nvidCaptureEnable=0\n", encoding="utf-8")
    assert video_capture_enabled(ini) is False
    assert video_capture_enabled(tmp_path / "noexiste.ini") is None


def test_start_raises_when_capture_disabled(tmp_path: Path):
    videos = tmp_path / "videos"
    videos.mkdir()
    ini = tmp_path / "app.ini"
    ini.write_text("[Video]\nvidCaptureEnable=0\n", encoding="utf-8")
    cap = NativeCapture(FakeCtrl(), videos_dir=videos, app_ini=ini)
    with pytest.raises(CaptureError, match="desactivada"):
        cap.start(videos / "shot.mp4")


def test_start_sends_start_when_enabled(tmp_path: Path):
    videos = tmp_path / "videos"
    videos.mkdir()
    ini = tmp_path / "app.ini"
    ini.write_text("[Video]\nvidCaptureEnable=1\n", encoding="utf-8")
    ctrl = FakeCtrl()
    cap = NativeCapture(ctrl, videos_dir=videos, app_ini=ini, settle_s=0.0)
    cap.start(videos / "shot.mp4")
    assert ctrl.calls == [1]  # VC_START
