"""Pantalla de bienvenida."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class WelcomeScreen(QWidget):
    new_project = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)

        title = QLabel("iRacing AI Cinematic Studio")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel(
            "Convierte tus replays en vídeo vertical cinematográfico:\n"
            "abre la replay en iRacing y deja que el director haga el resto."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        start = QPushButton("Nueva carrera")
        start.setObjectName("Primary")
        start.setMinimumWidth(260)
        start.clicked.connect(self.new_project.emit)

        hint = QLabel(
            "1 · Abre iRacing y carga la replay\n"
            "2 · Conecta el estudio\n"
            "3 · Genera tu vídeo 9:16"
        )
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignCenter)

        lay.addStretch(2)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addSpacing(18)
        lay.addWidget(start, 0, Qt.AlignHCenter)
        lay.addSpacing(26)
        lay.addWidget(hint)
        lay.addStretch(3)
