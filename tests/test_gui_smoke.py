"""Tests de humo de la GUI (offscreen, sin simulador real)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.main import MainWindow
from app.state import AppState
from app.widgets.event_timeline import EventTimelineWidget

from core.models import (
    DriverInfo,
    Event,
    EventType,
    SessionInfo,
    SessionModel,
    StylePreset,
)

from engines.replay.sdk_controller import SDKController
from tests.fakes import ScanFakeIR


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def make_session() -> SessionInfo:
    return SessionInfo(
        session_num=1, session_type="Race", track_name="spa",
        track_display="Spa-Francorchamps", duration_s=120.0,
        drivers=[
            DriverInfo(car_idx=0, car_number="7", name="Hugo", car_number_raw=7),
            DriverInfo(car_idx=1, car_number="21", name="Rival", car_number_raw=21),
        ],
    )


def make_model() -> SessionModel:
    return SessionModel(
        session=make_session(),
        sample_rate_hz=60,
        events=[
            Event(id="e1", type=EventType.OVERTAKE, start_s=20.0, end_s=24.0,
                  drivers=[0, 1], target=0, importance=0.9),
            Event(id="e2", type=EventType.OFF_TRACK, start_s=80.0, end_s=84.0,
                  drivers=[1], target=1, importance=0.6),
        ],
        laps=[],
        source="test",
    )


def test_window_builds_and_starts_at_welcome(qtbot):
    win = MainWindow(state=AppState())
    qtbot.addWidget(win)
    win.show()
    assert win.stack.currentWidget() is win.welcome
    assert win.step_labels[0].text() == "Conectar"


def test_welcome_button_goes_to_connect(qtbot):
    from PySide6.QtWidgets import QPushButton

    win = MainWindow(state=AppState())
    qtbot.addWidget(win)
    win.show()
    btn = win.welcome.findChild(QPushButton)
    assert btn is not None
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert win.stack.currentWidget() is win.connect_screen


def test_state_connects_with_fake_controller(qtbot):
    ctrl = SDKController(ir=ScanFakeIR(duration_s=60.0))
    state = AppState(controller=ctrl)
    with qtbot.waitSignal(state.session_ready, timeout=2000):
        assert state.connect_sim() is True
    assert state.session_info is not None
    assert state.session_info.track_name == "spa"


def test_full_director_flow_with_fakes(qtbot):
    """session → model → plan (reglas) → timeline con trims, todo sin SDK real."""
    ctrl = SDKController(ir=ScanFakeIR(duration_s=120.0))
    state = AppState(controller=ctrl)
    assert state.connect_sim()
    state.model = make_model()

    win = MainWindow(state=state)
    qtbot.addWidget(win)
    win.show()
    win.go_director()

    # el director genera el plan por reglas (síncrono en este test)
    plan = state.build_plan_sync(0, StylePreset.CINEMATIC, 15, use_ai=False)
    state.plan = plan
    assert len(plan.shots) >= 1

    # edición: trim y desactivación se reflejan en el timeline
    first = plan.shots[0]
    state.trims[first.id] = (1.0, 0.5)
    state.enabled[first.id] = False
    timeline = state.build_timeline()
    enabled = [c for c in timeline.clips if c.enabled]
    assert len(enabled) == max(len(plan.shots) - 1, 0)
    # el shot desactivado queda con su trim guardado
    assert state.trims[first.id] == (1.0, 0.5)


def test_editor_screen_updates_state_trims(qtbot):
    ctrl = SDKController(ir=ScanFakeIR(duration_s=120.0))
    state = AppState(controller=ctrl)
    state.connect_sim()
    state.model = make_model()
    plan = state.build_plan_sync(0, StylePreset.HYPE, 15, use_ai=False)
    state.plan = plan

    win = MainWindow(state=state)
    qtbot.addWidget(win)
    win.go_editor()

    editor = win.editor_screen
    assert editor.table.rowCount() == len(plan.shots)
    # el total inicial no está vacío
    assert state.timeline_total_s() > 0.0


def test_event_timeline_renders(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(600, 64)
    model = make_model()
    widget.set_data(model.events, model.session.duration_s or 1.0)
    widget.show()
    qtbot.wait(30)
    assert widget.grab().width() == 600  # pintado sin crash


def test_director_generate_button_state(qtbot):
    """Regresión: set_generating debe recibir un bool, no una lista de eventos."""
    from app.screens.director import DirectorScreen

    screen = DirectorScreen(ai_available=False)
    qtbot.addWidget(screen)
    assert screen.generate_btn.isEnabled() is False  # sin eventos aún
    screen.set_model(make_model())
    assert screen.generate_btn.isEnabled() is True
    screen.set_generating(True)
    assert screen.generate_btn.isEnabled() is False
    assert screen.generate_btn.text() == "Generando…"
    screen.set_generating(False)
    assert screen.generate_btn.isEnabled() is True
    assert screen.generate_btn.text() == "Generar plan de planos"


def test_scan_worker_with_fake(qtbot):
    from app.workers import ScanWorker
    from utils.config import ScanConfig

    ctrl = SDKController(ir=ScanFakeIR(duration_s=10.0, speed_mult=60.0))
    worker = ScanWorker(
        ctrl, ScanConfig(speed=8, poll_hz=60, max_duration_s=10.0),
        make_session(), None, None,
    )
    results = {}
    worker.done.connect(lambda m, f: results.update(model=m, frames=f))
    worker.run()  # síncrono: mismo hilo, sin event loop
    assert "model" in results
    assert results["model"].session.track_name == "spa"
