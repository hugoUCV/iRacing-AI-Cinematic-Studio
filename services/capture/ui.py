"""Ocultar/restaurar la UI de la replay de iRacing durante la captura.

Toggle de la barra espaciadora (no hay broadcast SDK). La UI se asume visible
antes de capturar: hide() la oculta y restore() la vuelve a mostrar.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class UIPilot:
    """Piloto de UI inyectable (los tests pasan un fake)."""

    def __init__(self, finder=None, sender=None):
        if finder is None or sender is None:
            from utils.win32_ui import find_iracing_window, send_key

            finder = finder or find_iracing_window
            sender = sender or send_key
        self._finder = finder
        self._sender = sender
        self._hwnd: int | None = None

    def hide(self) -> bool:
        """Oculta la UI (asume que estaba visible)."""
        self._hwnd = self._finder()
        if self._hwnd is None:
            log.warning("no se encontró la ventana de iRacing: la UI no se ocultará")
            return False
        ok = self._sender(self._hwnd)
        log.info("UI ocultada (%s)", "ok" if ok else "falló el envío de tecla")
        return ok

    def restore(self) -> bool:
        """Restaura la UI."""
        if self._hwnd is None:
            return False
        ok = self._sender(self._hwnd)
        log.info("UI restaurada (%s)", "ok" if ok else "falló el envío de tecla")
        return ok
