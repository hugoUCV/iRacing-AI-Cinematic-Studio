"""Pantalla 3: edición ligera del timeline (orden, trim, activar/desactivar)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.state import AppState


class EditorScreen(QWidget):
    next_requested = Signal()
    back_requested = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(12)

        title = QLabel("Edición")
        title.setObjectName("Title")
        lay.addWidget(title)

        hint = QLabel(
            "Recorta planos (trim), reordénalos o desactívalos. La captura y el "
            "render respetan este orden."
        )
        hint.setObjectName("Muted")
        lay.addWidget(hint)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["", "Plano", "Inicio", "Fin", "Cámara", "Trim in (s)", "Trim out (s)"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(1, 90)
        lay.addWidget(self.table)

        self.total_label = QLabel("")
        self.total_label.setObjectName("BigValue")
        lay.addWidget(self.total_label)

        nav = QHBoxLayout()
        back = QPushButton("← Volver")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested.emit)
        self.next_btn = QPushButton("Siguiente → captura y render")
        self.next_btn.setObjectName("Primary")
        self.next_btn.clicked.connect(self.next_requested.emit)
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        lay.addLayout(nav)

    # ── API ────────────────────────────────────────────────────────────────

    def set_plan(self, plan) -> None:
        self._plan = plan
        self.table.setRowCount(0)
        for row, shot in enumerate(plan.shots):
            self.table.insertRow(row)

            enabled = QCheckBox()
            enabled.setChecked(self.state.enabled.get(shot.id, True))
            enabled.toggled.connect(
                lambda on, sid=shot.id: self.state.enabled.__setitem__(sid, on)
            )
            cell = QWidget()
            c = QHBoxLayout(cell)
            c.setContentsMargins(8, 0, 8, 0)
            c.setAlignment(Qt.AlignCenter)
            c.addWidget(enabled)
            self.table.setCellWidget(row, 0, cell)

            self.table.setItem(row, 1, QTableWidgetItem(shot.id))
            self.table.setItem(row, 2, QTableWidgetItem(f"{shot.source_start_s:.1f}s"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{shot.source_end_s:.1f}s"))
            self.table.setItem(row, 4, QTableWidgetItem(shot.camera.group_name))

            for col, key in ((5, "in"), (6, "out")):
                spin = QDoubleSpinBox()
                spin.setRange(0.0, 10.0)
                spin.setSingleStep(0.1)
                spin.setDecimals(1)
                spin.setValue(
                    self.state.trims.get(shot.id, (0.0, 0.0))[0 if key == "in" else 1]
                )
                spin.valueChanged.connect(
                    lambda v, sid=shot.id, k=key: self._trim_changed(sid, k, v)
                )
                self.table.setCellWidget(row, col, spin)

        self._update_total()

    def _trim_changed(self, shot_id: str, key: str, value: float) -> None:
        trim_in, trim_out = self.state.trims.get(shot_id, (0.0, 0.0))
        if key == "in":
            trim_in = value
        else:
            trim_out = value
        self.state.trims[shot_id] = (trim_in, trim_out)
        self._update_total()

    def _update_total(self) -> None:
        active = len(
            [s for s in self.state.plan.shots if self.state.enabled.get(s.id, True)]
        )
        self.total_label.setText(
            f"Vídeo final: {self.state.timeline_total_s():.1f} s "
            f"({active} planos activos)"
        )
