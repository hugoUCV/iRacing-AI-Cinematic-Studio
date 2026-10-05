"""Genera capturas PNG de todas las pantallas (offscreen) para revisar el diseño.

Uso: uv run python tools/preview_screens.py [carpeta_salida]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main import MainWindow  # noqa: E402
from app.state import AppState  # noqa: E402
from app.theme import QSS  # noqa: E402
from core.models import (  # noqa: E402
    DriverInfo,
    Event,
    EventType,
    SessionInfo,
    SessionModel,
    StylePreset,
)
from engines.replay.sdk_controller import SDKController  # noqa: E402
from tests.fakes import ScanFakeIR  # noqa: E402


def build_state() -> AppState:
    ctrl = SDKController(ir=ScanFakeIR(duration_s=600.0))
    state = AppState(controller=ctrl)
    state.connect_sim()
    session = state.session_info.model_copy(
        update={
            "track_display": "Spa-Francorchamps",
            "duration_s": 600.0,
            "drivers": [
                DriverInfo(car_idx=0, car_number="7", name="Hugo Ferrer",
                           car_number_raw=7),
                DriverInfo(car_idx=1, car_number="21", name="Rival GT3",
                           car_number_raw=21),
                DriverInfo(car_idx=2, car_number="3", name="Juanra",
                           car_number_raw=3),
            ],
        }
    )
    state.session_info = session
    state.session_ready.emit(session)
    state.model = SessionModel(
        session=session, sample_rate_hz=60, laps=[], source="preview",
        events=[
            Event(id="e1", type=EventType.START, start_s=0.5, end_s=2.0,
                  drivers=[0, 1, 2], importance=0.3),
            Event(id="e2", type=EventType.BATTLE, start_s=118.0, end_s=150.0,
                  drivers=[0, 1], target=0, importance=0.85),
            Event(id="e3", type=EventType.OVERTAKE, start_s=126.0, end_s=130.0,
                  drivers=[0, 1], target=0, lap=2, importance=0.95),
            Event(id="e4", type=EventType.FAST_LAP, start_s=215.0, end_s=218.0,
                  drivers=[0], target=0, lap=4, importance=0.5),
            Event(id="e5", type=EventType.OFF_TRACK, start_s=340.0, end_s=345.0,
                  drivers=[1], target=1, importance=0.7),
            Event(id="e6", type=EventType.SPIN, start_s=411.0, end_s=416.0,
                  drivers=[1], target=1, importance=0.8),
            Event(id="e7", type=EventType.OVERTAKE, start_s=510.0, end_s=514.0,
                  drivers=[0, 1], target=0, lap=9, importance=0.9),
            Event(id="e8", type=EventType.FINISH, start_s=599.0, end_s=600.0,
                  drivers=[0], target=0, importance=0.6),
        ],
    )
    state.model_ready.emit(state.model)
    return state


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("TMPDIR", ".")) / "screens-preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    state = build_state()
    win = MainWindow(state=state)
    win.resize(1080, 720)
    win.show()

    grabs = {
        "1-welcome": win.welcome,
        "2-connect": win.connect_screen,
        "3-director": win.director_screen,
        "4-editor": win.editor_screen,
        "5-export": win.export_screen,
    }
    # plan para editor/export
    state.plan = state.build_plan_sync(0, StylePreset.CINEMATIC, 25, use_ai=False)
    state.trims[state.plan.shots[0].id] = (0.6, 0.4)
    win.editor_screen.set_plan(state.plan)
    win.export_screen.set_captures({s.id: Path(f"{s.id}.mp4") for s in state.plan.shots})
    # resultado simulado (sin archivo real: se evita set_done, que hace stat())
    win.export_screen._output = Path("Projects") / "spa-1" / "renders" / "final.mp4"
    win.export_screen.result_label.setText(
        "✓ Vídeo listo:\nProjects/spa-1/renders/final.mp4\n(24.1 MB)"
    )
    win.export_screen.result_label.show()
    win.export_screen.open_btn.show()

    app.processEvents()
    for name, widget in grabs.items():
        widget.resize(1080, 720)
        app.processEvents()
        pix = widget.grab()
        target = out_dir / f"{name}.png"
        pix.save(str(target))
        print(f"guardado {target}")

    print(f"\nTotal: {len(grabs)} pantallas en {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
