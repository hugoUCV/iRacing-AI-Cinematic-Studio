"""Tests del backend de captura nativo (detección de vidCaptureEnable)."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.capture.native import (
    CaptureError,
    NativeCapture,
    video_capture_enabled,
)
from services.capture.ui import UIPilot


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


def test_stop_finds_and_moves_new_file(tmp_path: Path):
    videos = tmp_path / "videos"
    videos.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    ini = tmp_path / "app.ini"
    ini.write_text("[Video]\nvidCaptureEnable=1\n", encoding="utf-8")
    ctrl = FakeCtrl()
    cap = NativeCapture(ctrl, videos_dir=videos, app_ini=ini, settle_s=0.0)
    cap.start(out / "shot.mp4")

    # simula que iRacing escribe el archivo tras parar la captura
    new_file = videos / "iRacing_2026.mp4"
    new_file.write_bytes(b"video")
    result = cap.stop()

    assert result == out / "shot.mp4"
    assert (out / "shot.mp4").exists()
    assert not new_file.exists()  # se movió a la carpeta del plano
    assert ctrl.calls == [1, 2]  # VC_START, VC_STOP


def test_ui_pilot_hide_and_restore():
    """El UIPilot busca la ventana una vez y envía la tecla en hide/restore."""
    calls: list[str] = []

    def finder() -> int:
        calls.append("find")
        return 12345

    def sender(hwnd: int) -> bool:
        calls.append(f"send:{hwnd}")
        return True

    pilot = UIPilot(finder=finder, sender=sender)
    assert pilot.hide() is True
    assert pilot.restore() is True
    assert calls == ["find", "send:12345", "send:12345"]
