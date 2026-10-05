"""Replay Engine: única puerta de acceso al simulador.

Regla: nada fuera de engines/replay habla con pyirsdk. La implementación real
(sdk_controller.py) llega en MVP 1; aquí queda el contrato verificado contra el
SDK oficial:

    cam_switch_num(car, group, camera)         → set_camera()
    replay_search_session_time(session, ms)    → seek_session_time()
    replay_set_play_speed(speed, slow_motion)  → play()
    video_capture(start/end)                   → services/capture (no aquí)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.models import CameraSpec, SessionInfo


class ReplayController(ABC):
    """Control y lectura del replay abierto en iRacing (vía IRSDK)."""

    @abstractmethod
    def connect(self) -> bool:
        """Conecta con el sim. False si iRacing no está corriendo."""

    @abstractmethod
    def is_replay_playing(self) -> bool: ...

    @abstractmethod
    def session_info(self) -> SessionInfo:
        """Metadatos de la sesión (desde WeekendInfo/SessionInfo/DriverInfo)."""

    @abstractmethod
    def camera_groups(self) -> list[tuple[int, str]]:
        """Grupos de cámara disponibles: [(GroupNum, GroupName)] desde
        CameraInfo (nada se hardcodea)."""

    @abstractmethod
    def read(self) -> dict[str, Any]:
        """Snapshot de las variables telemetría (CarIdx*, Replay*, Cam*)."""

    @abstractmethod
    def seek_session_time(self, session_num: int, session_time_ms: int) -> None:
        """Posiciona la replay por tiempo de sesión (broadcast verificado)."""

    @abstractmethod
    def set_camera(self, spec: CameraSpec) -> None:
        """cam_switch_num/pos según spec.target."""

    @abstractmethod
    def play(self, speed: float = 1.0, slow_motion: bool = False) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def video_capture(self, mode: int) -> None:
        """Captura integrada de iRacing (broadcast video_capture).
        mode: VideoCaptureMode.start_video_capture=1 / end_video_capture=2
        / toggle_video_capture=3 (verificado en pyirsdk irsdk.py L255)."""

    @abstractmethod
    def wait_until_session_time(self, target_s: float, timeout_s: float) -> float:
        """Bloquea sondeando ReplaySessionTime hasta alcanzar `target_s`
        (o timeout). Devuelve el tiempo alcanzado. Usado por scanner y runner."""

    @abstractmethod
    def verify(self) -> dict[str, Any]:
        """Estado observado tras un comando: CamCarIdx, CamGroupNumber,
        ReplaySessionTime, ReplayPlaySpeed. El llamador compara con lo pedido
        y reintenta si no coincide."""
