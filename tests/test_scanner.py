"""Tests del Scanner con el fake que avanza el tiempo de replay."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from core.models import SessionModel

from engines.analyzer.scanner import ScanCancelled, Scanner, replay_fingerprint
from engines.replay.sdk_controller import SDKController
from tests.fakes import ScanFakeIR
from utils.config import ScanConfig


def make_scanner(duration_s: float = 6.0, **cfg) -> tuple[Scanner, ScanFakeIR, SDKController]:
    fake = ScanFakeIR(duration_s=duration_s)
    ctrl = SDKController(ir=fake)
    params = {"speed": 16, "poll_hz": 60, "max_duration_s": 30.0}
    params.update(cfg)
    config = ScanConfig(**params)
    scanner = Scanner(ctrl, config=config, stall_timeout_s=0.4)
    return scanner, fake, ctrl


def test_scan_collects_frames_until_end():
    scanner, fake, ctrl = make_scanner(duration_s=4.0)
    info = ctrl.session_info()
    t0 = time.monotonic()
    model, frames = scanner.scan(info, replay_path=Path("falsa.rpy"))
    wall = time.monotonic() - t0

    assert isinstance(model, SessionModel)
    # duración simulada 4 s a 16x + stall → el scan termina rápido
    assert wall < 6.0, f"scan demasiado lento: {wall:.1f}s"
    assert frames, "debería haber frames recogidos"
    assert frames[0].t_s >= 0.0
    assert frames[-1].t_s >= 3.9, f"no llegó al final: {frames[-1].t_s}"
    # los frames tienen datos por coche
    assert 0 in frames[0].cars and 1 in frames[0].cars
    assert frames[0].cars[0].position == 1
    # el scan pausa la replay al terminar
    assert ctrl.verify()["play_speed"] == 0
    # track length parseado: 7.004 km
    assert info.track_length_m == 7004.0


def test_scan_detects_lap_crossings():
    scanner, _, ctrl = make_scanner(duration_s=16.0)
    info = ctrl.session_info()
    model, frames = scanner.scan(info, replay_path=None)
    # 1 vuelta cada 7 s simulados → ~2 cruces del coche 0
    laps0 = [l for l in model.laps if l.driver_id == 0]
    assert 1 <= len(laps0) <= 3, f"cruces esperados ~2, got {len(laps0)}"
    assert laps0[0].time_s > 6.0  # primera vuelta completa a los ~7 s


def test_scan_cache_roundtrip(tmp_path: Path):
    scanner, _, ctrl = make_scanner(duration_s=4.0)
    scanner.cache = __import__("utils.cache", fromlist=["JsonCache"]).JsonCache(tmp_path)
    info = ctrl.session_info()
    fake_path = tmp_path / "replay.rpy"
    fake_path.write_bytes(b"x" * 100)
    model1, frames1 = scanner.scan(info, replay_path=fake_path)
    assert frames1
    # segunda pasada: cacheado → frames vacíos, mismo modelo
    model2, frames2 = scanner.scan(info, replay_path=fake_path)
    assert frames2 == []
    assert model2.events == model1.events
    assert len(model2.laps) == len(model1.laps)


def test_fingerprint_changes_with_content():
    p1 = Path("a.rpy")
    p2 = Path("b.rpy")
    assert replay_fingerprint(p1) != replay_fingerprint(p2)


def test_scan_stops_at_max_duration_guardrail():
    # sesión muy larga + max_duration corto → corta por el guardrail
    scanner, _, ctrl = make_scanner(duration_s=100.0, max_duration_s=2.0)
    info = ctrl.session_info()
    model, frames = scanner.scan(info, replay_path=None)
    assert frames and frames[-1].t_s < 3.0


def test_scan_can_be_cancelled():
    scanner, _, ctrl = make_scanner(duration_s=60.0)
    info = ctrl.session_info()
    cancel = threading.Event()
    cancel.set()  # ya cancelado antes de empezar

    with pytest.raises(ScanCancelled):
        scanner.scan(info, replay_path=None, cancel=cancel)
    # el scan pausa la replay aunque se cancele
    assert ctrl.verify()["play_speed"] == 0
