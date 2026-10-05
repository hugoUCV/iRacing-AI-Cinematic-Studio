"""Pantalla 1: conexión con iRacing y escaneo de la sesión."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ConnectScreen(QWidget):
    connect_requested = Signal()
    scan_requested = Signal(Path)  # ruta del .rpy (o None)
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._replay_path: Path | None = None
        self._connected = False
        self._session_duration = 0.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(14)

        title = QLabel("Conectar con iRacing")
        title.setObjectName("Title")
        lay.addWidget(title)

        # tarjeta de conexión
        card = QFrame()
        card.setObjectName("Card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 18, 22, 18)
        c.setSpacing(10)

        self.status_label = QLabel(
            "Pendiente · abre iRacing con la replay cargada y pulsa Conectar"
        )
        self.status_label.setObjectName("Muted")
        c.addWidget(self.status_label)

        self.session_label = QLabel("")
        self.session_label.setWordWrap(True)
        c.addWidget(self.session_label)

        row = QHBoxLayout()
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.setObjectName("Primary")
        self.connect_btn.clicked.connect(self.connect_requested.emit)
        row.addWidget(self.connect_btn)
        row.addStretch()
        c.addLayout(row)

        replay_row = QHBoxLayout()
        self.replay_label = QLabel("Replay (.rpy) para caché: (opcional)")
        self.replay_label.setObjectName("Muted")
        replay_row.addWidget(self.replay_label)
        self.browse_btn = QPushButton("Buscar…")
        self.browse_btn.clicked.connect(self._browse)
        replay_row.addWidget(self.browse_btn)
        replay_row.addStretch()
        c.addLayout(replay_row)

        lay.addWidget(card)

        # escaneo
        self.scan_btn = QPushButton("Escanear la sesión")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._scan)
        lay.addWidget(self.scan_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        lay.addWidget(self.progress)

        self.scan_label = QLabel("")
        self.scan_label.setObjectName("Muted")
        lay.addWidget(self.scan_label)

        back = QPushButton("← Volver")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested.emit)
        lay.addWidget(back, 0, Qt.AlignLeft)
        lay.addStretch()

    # ── API ────────────────────────────────────────────────────────────────

    def set_session(self, info) -> None:
        self._connected = True
        self.status_label.setText("✓ Conectado")
        self.status_label.setStyleSheet("color: #7fbf7f;")
        self.session_label.setText(
            f"<b>{info.track_display or info.track_name}</b> · {info.session_type} "
            f"· {len(info.drivers)} pilotos · duración {info.duration_s or '?'} s"
        )
        self._session_duration = float(info.duration_s or 0.0)
        self.scan_btn.setEnabled(True)

    def set_progress(self, fraction: float, msg: str) -> None:
        if fraction >= 0:
            self.progress.show()
            self.progress.setValue(int(fraction * 100))
        self.scan_label.setText(msg)

    def set_scanning(self, active: bool) -> None:
        self.scan_btn.setEnabled(not active and self._connected)
        self.connect_btn.setEnabled(not active)
        self.browse_btn.setEnabled(not active)
        if not active:
            self.scan_label.setText("")

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona la replay (.rpy)", "",
            "iRacing replay (*.rpy);;Todos (*.*)",
        )
        if path:
            self._replay_path = Path(path)
            self.replay_label.setText(f"Replay: {self._replay_path.name}")

    def _scan(self) -> None:
        self.progress.setValue(0)
        self.progress.show()
        self.scan_requested.emit(self._replay_path)
