"""Pantalla 4: captura guiada y render."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class ExportScreen(QWidget):
    capture_requested = Signal(bool)   # offline: bool
    export_requested = Signal()
    new_project_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output: Path | None = None
        self._captures: dict = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(12)

        title = QLabel("Captura y render")
        title.setObjectName("Title")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 18, 22, 18)
        c.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Backend de captura:"))
        self.native_radio = QRadioButton("iRacing (video_capture)")
        self.native_radio.setChecked(True)
        self.offline_radio = QRadioButton("Dry-run (sin grabar)")
        group = QButtonGroup(self)
        group.addButton(self.native_radio)
        group.addButton(self.offline_radio)
        mode_row.addWidget(self.native_radio)
        mode_row.addWidget(self.offline_radio)
        mode_row.addStretch()
        c.addLayout(mode_row)

        hint = QLabel(
            "La captura reproduce cada plano en iRacing a 1x (tiempo real). "
            "Activa «Enable video capture» en las opciones gráficas de iRacing."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        c.addWidget(hint)

        self.capture_btn = QPushButton("Capturar planos")
        self.capture_btn.setObjectName("Primary")
        self.capture_btn.clicked.connect(
            lambda: self.capture_requested.emit(self.offline_radio.isChecked())
        )
        c.addWidget(self.capture_btn)

        self.capture_progress = QProgressBar()
        self.capture_progress.setRange(0, 100)
        self.capture_progress.hide()
        c.addWidget(self.capture_progress)
        self.capture_label = QLabel("")
        self.capture_label.setObjectName("Muted")
        c.addWidget(self.capture_label)

        self.export_btn = QPushButton("Renderizar vídeo 9:16")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_requested.emit)
        c.addWidget(self.export_btn)

        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 100)
        self.export_progress.hide()
        c.addWidget(self.export_progress)
        self.export_label = QLabel("")
        self.export_label.setObjectName("Muted")
        c.addWidget(self.export_label)

        self.result_label = QLabel("")
        self.result_label.setObjectName("BigValue")
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        c.addWidget(self.result_label)

        self.open_btn = QPushButton("Abrir carpeta del vídeo")
        self.open_btn.hide()
        self.open_btn.clicked.connect(self._open_folder)
        c.addWidget(self.open_btn)

        lay.addWidget(card)

        nav = QHBoxLayout()
        back = QPushButton("← Volver")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested.emit)
        self.new_btn = QPushButton("Nueva carrera")
        self.new_btn.clicked.connect(self.new_project_requested.emit)
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(self.new_btn)
        lay.addLayout(nav)
        lay.addStretch()

    # ── API ────────────────────────────────────────────────────────────────

    def set_capturing(self, active: bool) -> None:
        self.capture_btn.setEnabled(not active)
        self.export_btn.setEnabled(False)
        self.native_radio.setEnabled(not active)
        self.offline_radio.setEnabled(not active)
        if active:
            self.capture_progress.setValue(0)
            self.capture_progress.show()

    def set_capture_progress(self, current: int, total: int, msg: str) -> None:
        self.capture_progress.setValue(int(current * 100 / max(total, 1)))
        self.capture_label.setText(msg)

    def set_captures(self, captures: dict) -> None:
        self._captures = captures
        self.capture_label.setText(
            f"✓ {len(captures)} planos capturados → listos para render"
        )
        self.export_btn.setEnabled(bool(captures))

    def set_exporting(self, active: bool) -> None:
        self.export_btn.setEnabled(not active and bool(self._captures))
        self.capture_btn.setEnabled(not active)
        if active:
            self.export_progress.setValue(0)
            self.export_progress.show()

    def set_export_progress(self, fraction: float, msg: str) -> None:
        if fraction >= 0:
            self.export_progress.setValue(int(fraction * 100))
        self.export_label.setText(msg)

    def set_done(self, path: Path) -> None:
        self._output = path
        self.export_progress.setValue(100)
        self.result_label.setText(
            f"✓ Vídeo listo:\n{path}\n({path.stat().st_size // 1024} KB)"
        )
        self.result_label.show()
        self.open_btn.show()

    def _open_folder(self) -> None:
        if self._output is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._output.parent)))
