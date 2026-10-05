"""Widget de línea de tiempo de eventos (pintado a medida).

Barra horizontal 0 → duración de sesión con marcas coloreadas por tipo de
evento. Clic → signal event_selected(Event).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.models import Event, EventType

COLORS = {
    EventType.OVERTAKE: "#4caf50",
    EventType.BATTLE: "#ff9800",
    EventType.OFF_TRACK: "#f44336",
    EventType.SPIN: "#e91e63",
    EventType.FAST_LAP: "#2196f3",
    EventType.START: "#9e9e9e",
    EventType.FINISH: "#b39ddb",
    EventType.POSITION_CHANGE: "#00bcd4",
}

LABELS = {
    EventType.OVERTAKE: "adelantamiento",
    EventType.BATTLE: "batalla",
    EventType.OFF_TRACK: "salida",
    EventType.SPIN: "trompo",
    EventType.FAST_LAP: "vuelta rápida",
    EventType.START: "salida",
    EventType.FINISH: "llegada",
    EventType.POSITION_CHANGE: "posición",
}


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


class EventTimelineWidget(QWidget):
    event_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events: list[Event] = []
        self.duration_s = 0.0
        self.setMinimumHeight(64)
        self.setMouseTracking(True)
        self._hover: Event | None = None

    def set_data(self, events: list[Event], duration_s: float) -> None:
        self.events = sorted(events, key=lambda e: e.start_s)
        self.duration_s = max(duration_s, 1.0)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        m = 12  # margen
        bar_x, bar_w = m, w - 2 * m
        bar_y, bar_h = 18, h - 42

        # fondo de la barra
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1e2027"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 6, 6)

        # eventos
        for e in self.events:
            color = QColor(COLORS.get(e.type, "#f5b942"))
            if self._hover is e:
                color = color.lighter(140)
            x = bar_x + int(bar_w * (e.start_s / self.duration_s))
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRect(x - 2, bar_y + 2, 4, bar_h - 4)

        # eje de tiempos
        p.setPen(QColor("#8b8d96"))
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        p.drawText(m, h - 8, "0:00")
        mid = _fmt(self.duration_s / 2)
        p.drawText(bar_x + bar_w // 2 - 14, h - 8, mid)
        end = _fmt(self.duration_s)
        p.drawText(bar_x + bar_w - 30, h - 8, end)

        # info del evento bajo el cursor
        if self._hover is not None:
            e = self._hover
            label = f"{LABELS.get(e.type, e.type.value)} · t={e.start_s:.1f}s · " \
                    f"coches {e.drivers}"
            p.drawText(m, 14, label)

    def mouseMoveEvent(self, event) -> None:
        self._hover = self._event_at(event.position())
        self.update()

    def mousePressEvent(self, event) -> None:
        e = self._event_at(event.position())
        if e is not None:
            self.event_selected.emit(e)

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    def _event_at(self, pos: QPointF) -> Event | None:
        w = self.width()
        m = 12
        bar_x, bar_w = m, w - 2 * m
        if not (bar_x <= pos.x() <= bar_x + bar_w):
            return None
        frac = (pos.x() - bar_x) / bar_w
        best: Event | None = None
        best_d = float("inf")
        for e in self.events:
            d = abs(e.start_s / self.duration_s - frac)
            if d < best_d:
                best_d, best = d, e
        return best if best_d < 0.03 else None
