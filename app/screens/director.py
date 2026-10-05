"""Pantalla 2: el director — protagonista, estilo, duración y plan."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.models import SessionModel, StylePreset

from app.widgets.event_timeline import EventTimelineWidget, LABELS

STYLES = {
    StylePreset.CINEMATIC: "Cinematic · planos largos y suaves",
    StylePreset.HYPE: "Hype · cortes rápidos y energía",
    StylePreset.BROADCAST: "Broadcast · retransmisión de TV",
    StylePreset.AESTHETIC: "Aesthetic · detalles y composición vertical",
    StylePreset.STORY: "Story · narrativa intro→acción→cierre",
}


class DirectorScreen(QWidget):
    plan_requested = Signal(object, object, int, bool)  # hero, style, dur, use_ai
    back_requested = Signal()

    def __init__(self, ai_available: bool = False, parent=None):
        super().__init__(parent)
        self.ai_available = ai_available
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(12)

        title = QLabel("Director")
        title.setObjectName("Title")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 18, 22, 18)
        c.setSpacing(12)

        hero_row = QHBoxLayout()
        hero_row.addWidget(QLabel("Piloto protagonista:"))
        self.hero_combo = QComboBox()
        self.hero_combo.setMinimumWidth(260)
        hero_row.addWidget(self.hero_combo)
        hero_row.addStretch()
        c.addLayout(hero_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Estilo:"))
        self.style_combo = QComboBox()
        for s, label in STYLES.items():
            self.style_combo.addItem(label, userData=s)
        self.style_combo.setCurrentIndex(0)
        style_row.addWidget(self.style_combo)
        c.addLayout(style_row)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duración objetivo:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 180)
        self.duration_spin.setValue(20)
        self.duration_spin.setSuffix(" s")
        dur_row.addWidget(self.duration_spin)
        self.ai_check = QCheckBox("Usar director IA (si hay clave configurada)")
        self.ai_check.setEnabled(ai_available)
        self.ai_check.setToolTip(
            "Configura el proveedor con `python -m app.cli config --set-api-key …`"
            if not ai_available else ""
        )
        dur_row.addSpacing(24)
        dur_row.addWidget(self.ai_check)
        dur_row.addStretch()
        c.addLayout(dur_row)

        self.events_label = QLabel("Eventos detectados")
        self.events_label.setObjectName("Section")
        c.addWidget(self.events_label)
        self.timeline = EventTimelineWidget()
        c.addWidget(self.timeline)

        self.notes_label = QLabel("")
        self.notes_label.setObjectName("Muted")
        self.notes_label.setWordWrap(True)
        c.addWidget(self.notes_label)

        lay.addWidget(card)

        self.generate_btn = QPushButton("Generar plan de planos")
        self.generate_btn.setObjectName("Primary")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self._emit_plan)
        lay.addWidget(self.generate_btn)

        back = QPushButton("← Volver")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested.emit)
        lay.addWidget(back, 0, Qt.AlignLeft)
        lay.addStretch()

    # ── API ────────────────────────────────────────────────────────────────

    def set_drivers(self, drivers: list) -> None:
        self.hero_combo.clear()
        for d in drivers:
            self.hero_combo.addItem(f"{d.name}  ·  #{d.car_number}", userData=d.car_idx)
        self.hero_combo.addItem("(protagonista más destacado)", userData=None)

    def set_model(self, model: SessionModel) -> None:
        self.timeline.set_data(model.events, model.session.duration_s or 1.0)
        counts: dict[str, int] = {}
        for e in model.events:
            counts[LABELS.get(e.type, e.type.value)] = counts.get(
                LABELS.get(e.type, e.type.value), 0
            ) + 1
        summary = " · ".join(f"{k}: {v}" for k, v in counts.items())
        self.events_label.setText(f"Eventos detectados — {len(model.events)} ({summary})")
        self.generate_btn.setEnabled(True)

    def set_plan(self, plan) -> None:
        notes = "\n".join(f"· {n}" for n in plan.notes) if plan.notes else ""
        self.notes_label.setText(
            f"Plan generado: {len(plan.shots)} planos.\n{notes}"
        )

    def set_generating(self, active: bool) -> None:
        has_events = bool(self.timeline.events)
        self.generate_btn.setEnabled(not active and has_events)
        self.generate_btn.setText("Generando…" if active else "Generar plan de planos")

    def _emit_plan(self) -> None:
        hero = self.hero_combo.currentData()
        style = self.style_combo.currentData()
        dur = self.duration_spin.value()
        use_ai = self.ai_check.isChecked()
        self.plan_requested.emit(hero, style, dur, use_ai)
