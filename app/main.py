"""Ventana principal: navegación por pasos + orquestación de workers."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai.provider import provider_from_config
from app.screens.connect import ConnectScreen
from app.screens.director import DirectorScreen
from app.screens.editor import EditorScreen
from app.screens.export import ExportScreen
from app.screens.welcome import WelcomeScreen
from app.state import AppState
from app.theme import QSS
from app.workers import (
    CaptureWorker,
    ExportWorker,
    PlanWorker,
    ScanWorker,
    make_capture_backend,
)

STEPS = ["Conectar", "Director", "Editar", "Render"]


def _project_dir(state: AppState) -> Path:
    info = state.session_info
    name = (info.track_name or "sesion").strip().replace(" ", "-")
    return Path("Projects") / f"{name}-{info.session_num}"


class MainWindow(QMainWindow):
    def __init__(self, state: AppState | None = None):
        super().__init__()
        self.setWindowTitle("iRacing AI Cinematic Studio")
        self.resize(1080, 720)
        self.state = state or AppState()
        self._worker = None

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── cabecera ────────────────────────────────────────────────────────
        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(28, 18, 28, 14)
        brand = QLabel("iRacing AI Cinematic Studio")
        brand.setObjectName("Title")
        h.addWidget(brand)
        h.addStretch()
        self.step_labels: list[QLabel] = []
        for i, name in enumerate(STEPS):
            chip = QLabel(name)
            chip.setObjectName("StepInactive")
            self.step_labels.append(chip)
            h.addWidget(chip)
            if i < len(STEPS) - 1:
                sep = QLabel("·")
                sep.setObjectName("Muted")
                h.addWidget(sep)
        outer.addWidget(header)

        # ── pantallas ───────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.welcome = WelcomeScreen()
        ai_ok = provider_from_config(self.state.config.ai) is not None
        self.connect_screen = ConnectScreen()
        self.director_screen = DirectorScreen(ai_available=ai_ok)
        self.editor_screen = EditorScreen(self.state)
        self.export_screen = ExportScreen()
        for s in (self.welcome, self.connect_screen, self.director_screen,
                  self.editor_screen, self.export_screen):
            self.stack.addWidget(s)
        outer.addWidget(self.stack, 1)

        self.statusBar().showMessage("Listo")

        # ── señales de pantallas ────────────────────────────────────────────
        self.welcome.new_project.connect(self.go_connect)
        self.connect_screen.connect_requested.connect(self._connect)
        self.connect_screen.scan_requested.connect(self._scan)
        self.connect_screen.scan_cancelled.connect(self._cancel_scan)
        self.connect_screen.back_requested.connect(self.go_welcome)
        self.director_screen.plan_requested.connect(self._plan)
        self.director_screen.back_requested.connect(self.go_connect)
        self.editor_screen.next_requested.connect(self.go_export)
        self.editor_screen.back_requested.connect(self.go_director)
        self.export_screen.capture_requested.connect(self._capture)
        self.export_screen.export_requested.connect(self._export)
        self.export_screen.new_project_requested.connect(self._new_project)
        self.export_screen.back_requested.connect(self.go_editor)

        # ── señales del estado ──────────────────────────────────────────────
        self.state.status.connect(self.statusBar().showMessage)
        self.state.session_ready.connect(self._on_session)
        self.state.model_ready.connect(self._on_model)
        self.state.plan_ready.connect(self._on_plan)
        self.state.captures_ready.connect(self._on_captures)
        self.state.export_done.connect(self._on_export_done)
        self.state.error.connect(self._on_error)

    # ── navegación ─────────────────────────────────────────────────────────

    def _set_step(self, index: int) -> None:
        for i, chip in enumerate(self.step_labels):
            chip.setObjectName("StepActive" if i == index else
                               "StepDone" if i < index else "StepInactive")
            chip.style().unpolish(chip)
            chip.style().polish(chip)

    def go_welcome(self) -> None:
        self._set_step(-1)
        self.stack.setCurrentWidget(self.welcome)

    def go_connect(self) -> None:
        self._set_step(0)
        self.stack.setCurrentWidget(self.connect_screen)

    def go_director(self) -> None:
        self._set_step(1)
        self.stack.setCurrentWidget(self.director_screen)

    def go_editor(self) -> None:
        self._set_step(2)
        self.editor_screen.set_plan(self.state.plan)
        self.stack.setCurrentWidget(self.editor_screen)

    def go_export(self) -> None:
        self._set_step(3)
        self.stack.setCurrentWidget(self.export_screen)

    # ── acciones ───────────────────────────────────────────────────────────

    def _connect(self) -> None:
        self.connect_screen.set_scanning(False)
        if self.state.connect_sim():
            self.go_director()

    def _scan(self, replay_path: Path | None, speed: int) -> None:
        self.connect_screen.set_scanning(True)
        scan_cfg = self.state.config.scan.model_copy(update={"speed": speed})
        worker = ScanWorker(
            self.state.controller, scan_cfg,
            self.state.session_info, replay_path,
            _project_dir(self.state) / "analysis",
        )
        self._start_worker(worker)
        worker.progress.connect(self.connect_screen.set_progress)
        worker.done.connect(self._scan_done)
        worker.cancelled.connect(self._scan_cancelled)
        worker.failed.connect(self._worker_failed)

    def _cancel_scan(self) -> None:
        if isinstance(self._worker, ScanWorker):
            self._worker.cancel()
            self.statusBar().showMessage("Deteniendo escaneo…")

    def _scan_cancelled(self) -> None:
        self.connect_screen.set_scanning(False)
        self.connect_screen.set_scan_cancelled()
        self.statusBar().showMessage("Escaneo cancelado")

    def _scan_done(self, model, frames) -> None:
        self.connect_screen.set_scanning(False)
        self.connect_screen.set_progress(1.0, "✓ análisis completado")
        self.state.model = model
        self.state.model_ready.emit(model)

    def _plan(self, hero, style, duration_s: int, use_ai: bool) -> None:
        self.director_screen.set_generating(True)
        worker = PlanWorker(self.state, hero, style, duration_s, use_ai)
        self._start_worker(worker)
        worker.done.connect(self._plan_done)
        worker.failed.connect(self._worker_failed)

    def _plan_done(self, plan) -> None:
        self.director_screen.set_generating(False)
        self.state.plan = plan
        self.state.plan_ready.emit(plan)

    def _capture(self, offline: bool) -> None:
        self.export_screen.set_capturing(True)
        backend = make_capture_backend(self.state.controller, offline)
        worker = CaptureWorker(
            self.state.controller, backend,
            _project_dir(self.state) / "captures",
            self.state.session_info.session_num, self.state.plan,
        )
        self._start_worker(worker)
        worker.progress.connect(self.export_screen.set_capture_progress)
        worker.done.connect(self._captures_done)
        worker.failed.connect(self._worker_failed)

    def _captures_done(self, captures: dict) -> None:
        self.export_screen.set_capturing(False)
        self.state.captures = captures
        self.state.captures_ready.emit(captures)

    def _export(self) -> None:
        self.export_screen.set_exporting(True)
        timeline = self.state.build_timeline()
        out = _project_dir(self.state) / "renders" / f"final-{len(timeline.clips)}p.mp4"
        worker = ExportWorker(timeline, self.state.captures, out)
        self._start_worker(worker)
        worker.progress.connect(self.export_screen.set_export_progress)
        worker.done.connect(self._export_done)
        worker.failed.connect(self._worker_failed)

    def _export_done(self, path: Path) -> None:
        self.export_screen.set_exporting(False)
        self.state.output_path = path
        self.state.export_done.emit(path)

    # ── manejo interno ─────────────────────────────────────────────────────

    def _start_worker(self, worker) -> None:
        self._worker = worker
        worker.start()

    def _worker_failed(self, msg: str) -> None:
        self.connect_screen.set_scanning(False)
        self.director_screen.set_generating(False)
        self.export_screen.set_capturing(False)
        self.export_screen.set_exporting(False)
        self._on_error(msg)

    def _on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        QMessageBox.warning(self, "Error", msg)

    def _on_session(self, info) -> None:
        self.director_screen.set_drivers(info.drivers)
        self.connect_screen.set_session(info)

    def _on_model(self, model) -> None:
        self.director_screen.set_model(model)
        self.go_director()

    def _on_plan(self, plan) -> None:
        self.director_screen.set_plan(plan)
        self.go_editor()

    def _on_captures(self, captures) -> None:
        self.export_screen.set_captures(captures)

    def _on_export_done(self, path: Path) -> None:
        self.export_screen.set_done(path)
        self.statusBar().showMessage(f"Vídeo listo: {path}")

    def _new_project(self) -> None:
        self.state.reset()
        self.go_welcome()
        self.statusBar().showMessage("Proyecto nuevo listo")


def _setup_logging() -> None:
    """Logs a archivo: un .exe con ventana no tiene consola donde ver warnings."""
    log_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "iRacingCinematicStudio"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_dir / "app.log"),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError:
        pass  # sin logging no es fatal


def main() -> int:
    _setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("iRacing AI Cinematic Studio")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
