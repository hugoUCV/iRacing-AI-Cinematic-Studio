"""Control de la ventana de iRacing en Windows (ctypes, sin dependencias).

Para ocultar la UI de la replay (HUD + nombres + controles) iRacing usa la
barra espaciadora como toggle. No hay broadcast SDK para ello, así que
inyectamos la tecla vía SendInput tras traer la ventana al frente.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

VK_SPACE = 0x20
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 24)]

    _anonymous_ = ("_i",)
    _fields_ = [("type", wintypes.DWORD), ("_i", _I)]


def find_window_by_title(contains: str) -> int | None:
    """Busca una ventana de nivel superior cuyo título contenga `contains`."""
    result: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if contains.lower() in buf.value.lower():
            result.append(hwnd)
            return False  # encontrada: parar
        return True

    user32.EnumWindows(_cb, 0)
    return result[0] if result else None


def find_iracing_window() -> int | None:
    """Ventana del simulador de iRacing (título contiene 'iRacing')."""
    return find_window_by_title("iRacing")


def send_key(hwnd: int, vk: int = VK_SPACE) -> bool:
    """Envía una tecla (down+up) a la ventana, trayéndola al frente."""
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)  # dejar que la ventana tome el foco
    down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, dwFlags=0))
    up = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, dwFlags=KEYEVENTF_KEYUP))
    arr = (INPUT * 2)(down, up)
    sent = user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT))
    return sent == 2
