"""Tests del CaptureRunner (orquestación seek → cámara → grabar → parar)."""
from __future__ import annotations

import time
from pathlib import Path

from core.models import CameraSpec, Shot, ShotPlan, StylePreset
from engines.replay.sdk_controller import SDKController
from services.capture.offline import OfflineCapture
from services.capture.runner import CaptureRunner
from tests.fakes import ScanFakeIR


class RecordingCapture(OfflineCapture):
    def __init__(self):
        super().__init__()
        self.events: list[tuple[str, str]] = []

    def start(self, target: Path) -> None:
        self.events.append(("start", target.stem))
        super().start(target)

    def stop(self) -> Path | None:
        self.events.append(("stop", self._target.stem))
        return super().stop()


class BoomCapture(RecordingCapture):
    """Backend que falla al parar (simula captura rota)."""

    def stop(self) -> Path | None:
        raise RuntimeError("captura rota")


def make_plan() -> ShotPlan:
    return ShotPlan(
        shots=[
            Shot(
                id="s2",
                source_start_s=20.0,
                source_end_s=24.0,
                camera=CameraSpec(group=4, number=0, target=0, group_name="TV2"),
            ),
            Shot(
                id="s1",
                source_start_s=3.0,
                source_end_s=7.0,
                camera=CameraSpec(group=3, number=0, target=0, group_name="TV1"),
            ),
        ],
        style=StylePreset.CINEMATIC,
    )


def make_env(duration_s: float = 30.0, backend=None, **runner_kw):
    fake = ScanFakeIR(duration_s=duration_s, speed_mult=4.0)
    ctrl = SDKController(ir=fake)
    ctrl.session_info()  # poblar drivers (cam_switch por CarNumberRaw)
    backend = backend or RecordingCapture()
    runner = CaptureRunner(ctrl, backend, Path("capturas"), session_num=1, **runner_kw)
    return runner, fake, backend


def test_runner_captures_shots_in_time_order(tmp_path: Path):
    runner, fake, backend = make_env()
    runner.captures_dir = tmp_path
    result = runner.run(make_plan())

    # ambos planos capturados, aunque el plan venía desordenado
    assert set(result) == {"s1", "s2"}
    assert (tmp_path / "s1.mp4").exists() and (tmp_path / "s2.mp4").exists()

    # orden temporal de la orquestación
    seeks = [c for c in fake.calls if c.startswith("seek")]
    assert seeks == ["seek:1:2500", "seek:1:19500"]  # margen de 0.5 s
    cams = [c for c in fake.calls if c.startswith("cam:")]
    assert cams == ["cam:7:3:0", "cam:7:4:0"]  # héroe raw 7, grupos TV1/TV2

    # por cada plano: start de captura antes del play, stop después
    ops = backend.events
    assert ops[0] == ("start", "s1")
    assert ops[-1] == ("stop", "s2")
    # el replay queda en pausa al final
    assert fake.speed == 0


def test_runner_skips_failed_shot_and_continues(tmp_path: Path):
    runner, _, backend = make_env(backend=BoomCapture())
    runner.captures_dir = tmp_path
    result = runner.run(make_plan())
    # ningún archivo pero tampoco excepción: el runner es tolerante
    assert result == {}
    # solo dos "start": el stop de cada plano falló antes de registrarse
    assert backend.events == [("start", "s1"), ("start", "s2")]


def test_runner_verifies_camera_change():
    """Si el sim no confirma el grupo, el runner reintenta set_camera."""
    runner, fake, _ = make_env()

    def no_confirm(car, group, camera):
        fake.calls.append(f"cam:{car}:{group}:{camera}")  # nunca confirma

    fake.cam_switch_num = no_confirm
    fake.vars["CamGroupNumber"] = 99

    runner._capture_shot(make_plan().shots[0])
    cam_calls = [c for c in fake.calls if c.startswith("cam:")]
    assert len(cam_calls) == runner.verify_retries + 2  # 1 inicial + reintentos


def test_runner_does_not_overflow_shot_time():
    """El wait_until usa timeout; con un sim lento no se cuelga."""
    t0 = time.monotonic()
    runner, fake, _ = make_env(duration_s=3.0, backend=RecordingCapture(),
                               wait_timeout_s=1.0)
    fake.duration_s = 2.0  # la replay termina antes que el plano
    runner._capture_shot(make_plan().shots[0])
    elapsed = time.monotonic() - t0
    assert elapsed < 6, f"esperaba timeout breve, tardó {elapsed:.1f}s"


def test_runner_hides_and_restores_ui(tmp_path: Path):
    """El UIPilot oculta la UI antes del primer plano y la restaura al final."""
    calls: list[str] = []

    class Pilot:
        def hide(self) -> None:
            calls.append("hide")

        def restore(self) -> None:
            calls.append("restore")

    runner, _, _ = make_env(ui_pilot=Pilot())
    runner.captures_dir = tmp_path
    runner.run(make_plan())
    assert calls == ["hide", "restore"]


def test_runner_ui_pilot_optional():
    """Sin ui_pilot el runner funciona igual (sin tocar la UI)."""
    runner, _, _ = make_env()  # sin ui_pilot
    runner.captures_dir = Path("capturas")
    assert runner.ui_pilot is None
