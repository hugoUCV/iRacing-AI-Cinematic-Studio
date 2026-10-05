"""Workers de la GUI: scan, plan, captura y export en QThread."""
from __future__ import annotations

# ruff: noqa: BLE001  — los workers capturan cualquier excepción para emitirla
# como señal failed; si no, el error se perdería dentro del QThread.
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.models import RenderJob, SessionInfo, StylePreset
from engines.analyzer.scanner import ScanCancelled, Scanner
from engines.video.export import export_timeline
from services.capture.native import NativeCapture
from services.capture.offline import OfflineCapture
from services.capture.runner import CaptureRunner
from utils.config import ScanConfig


class ScanWorker(QThread):
    progress = Signal(float, str)
    done = Signal(object, object)  # (SessionModel, frames)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(
        self,
        controller,
        config: ScanConfig,
        session: SessionInfo,
        replay_path: Path | None,
        cache_dir: Path | None,
        parent=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.config = config
        self.session = session
        self.replay_path = replay_path
        self.cache_dir = cache_dir
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Pide detener el escaneo (se procesa en el siguiente sondeo)."""
        self._cancel.set()

    def run(self) -> None:
        try:
            scanner = Scanner(
                self.controller, self.config,
                cache_dir=self.cache_dir, stall_timeout_s=8.0,
            )
            model, frames = scanner.scan(
                self.session, replay_path=self.replay_path,
                on_progress=self._p, cancel=self._cancel,
            )
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(model, frames)

    def _p(self, fraction: float, msg: str) -> None:
        self.progress.emit(fraction, msg)


class PlanWorker(QThread):
    done = Signal(object)   # ShotPlan
    failed = Signal(str)

    def __init__(self, state, hero_idx, style: StylePreset, duration_s: int,
                 use_ai: bool, parent=None):
        super().__init__(parent)
        self.state = state
        self.hero_idx = hero_idx
        self.style = style
        self.duration_s = duration_s
        self.use_ai = use_ai

    def run(self) -> None:
        try:
            plan = self.state.build_plan_sync(
                self.hero_idx, self.style, self.duration_s, self.use_ai
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(plan)


class CaptureWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)   # dict[str, Path]
    failed = Signal(str)

    def __init__(self, controller, backend, captures_dir: Path,
                 session_num: int, plan, ui_pilot=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.backend = backend
        self.captures_dir = captures_dir
        self.session_num = session_num
        self.plan = plan
        self.ui_pilot = ui_pilot

    def run(self) -> None:
        try:
            runner = CaptureRunner(
                self.controller, self.backend, self.captures_dir,
                session_num=self.session_num, wait_timeout_s=None,
                ui_pilot=self.ui_pilot,
            )
            result = runner.run(self.plan, on_progress=self._p)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)

    def _p(self, current: int, total: int, msg: str) -> None:
        self.progress.emit(current, total, msg)


class ExportWorker(QThread):
    progress = Signal(float, str)
    done = Signal(object)   # Path
    failed = Signal(str)

    def __init__(self, timeline, captures: dict, output: Path, parent=None):
        super().__init__(parent)
        self.timeline = timeline
        self.captures = captures
        self.output = output

    def run(self) -> None:
        try:
            job = RenderJob(project=Path("."), output=self.output)
            out = export_timeline(
                self.timeline, self.captures, self.output, job,
                on_progress=self._p,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(out)

    def _p(self, fraction, msg: str) -> None:
        self.progress.emit(fraction if fraction is not None else -1.0, msg)


def make_capture_backend(controller, offline: bool):
    if offline:
        return OfflineCapture()
    return NativeCapture(controller)
