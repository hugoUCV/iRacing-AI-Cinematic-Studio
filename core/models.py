"""Modelos de dominio: el contrato entre módulos.

Todo lo que cruza un límite de módulo (scan → eventos → director → timeline →
render) viaja como una de estas estructuras Pydantic. Nada más las define.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────── sesión ───────────────────────────


class DriverInfo(BaseModel):
    car_idx: int
    car_number: str
    name: str
    team: str | None = None
    irating: int | None = None
    car_class: str | None = None
    car_name: str | None = None
    car_number_raw: int | None = None  # valor numérico para cam_switch_num


class SessionInfo(BaseModel):
    session_num: int
    session_type: str  # 'Race', 'Qualify', 'Practice'...
    track_name: str
    track_display: str | None = None
    duration_s: float | None = None
    laps_total: int | None = None
    drivers: list[DriverInfo] = Field(default_factory=list)
    start_utc: datetime | None = None


class LapRecord(BaseModel):
    driver_id: int
    lap: int
    time_s: float
    valid: bool = True


# ─────────────────────────── eventos ───────────────────────────


class EventType(str, Enum):
    START = "start"
    FINISH = "finish"
    OVERTAKE = "overtake"
    OFF_TRACK = "off_track"
    SPIN = "spin"
    BATTLE = "battle"
    FAST_LAP = "fast_lap"
    CONTACT = "contact"
    CLOSE_CALL = "close_call"
    POSITION_CHANGE = "position_change"
    PIT_STOP = "pit_stop"


class Event(BaseModel):
    id: str
    type: EventType
    start_s: float  # tiempo de sesión (ReplaySessionTime)
    end_s: float
    drivers: list[int] = Field(default_factory=list)  # car_idx implicados
    target: int | None = None  # car_idx protagonista
    lap: int | None = None
    position: int | None = None
    importance: float = 0.0  # 0..1
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionModel(BaseModel):
    """Resultado del scan de una replay. Se cachea en analysis/<hash>.json."""

    session: SessionInfo
    laps: list[LapRecord] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    sample_rate_hz: int = 60
    source: str = ""  # hash de la replay + build


# ─────────────────────────── cámaras / planos ───────────────────────────


class ShotType(str, Enum):
    TRACKING = "tracking"
    STATIC = "static"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    FRONT = "front"
    REAR = "rear"
    SIDE = "side"
    WHEEL = "wheel"
    COCKPIT = "cockpit"
    HELICOPTER = "helicopter"
    CLOSE_UP = "close_up"
    WIDE = "wide"
    FOLLOW = "follow"
    ORBIT = "orbit"


class CameraSpec(BaseModel):
    """Cámara real de iRacing (grupo + número + coche objetivo).

    Nota: por SDK solo se puede SELECCIONAR cámaras existentes; el movimiento
    cinematográfico se añade en post (reframe/speed).
    """

    group: int
    number: int = 0
    target: int | None = None  # car_idx o None (cámara estática)
    group_name: str = ""  # informativo: cockpit, chase, TV1...


class Transition(str, Enum):
    CUT = "cut"
    FADE = "fade"
    WHIP = "whip"  # barrido (xfade personalizado)


class SpeedCurve(BaseModel):
    """Rampa de velocidad aplicada en post (MVP 2+). keyframes 0..1."""

    keyframes: list[tuple[float, float]] = [(0.0, 1.0), (1.0, 1.0)]


class ReframeSpec(BaseModel):
    """Ventana de reencuadre 9:16 (MVP 2+). x_norm: 0..1 sobre el ancho 16:9."""

    track: bool = True
    keep_centered: bool = True
    smooth: bool = True
    predict: bool = True
    x_norm: float = 0.5  # fallback: centro


class Shot(BaseModel):
    id: str
    source_start_s: float  # en tiempo de sesión de la replay
    source_end_s: float
    camera: CameraSpec
    transition: Transition = Transition.CUT
    speed: SpeedCurve = Field(default_factory=SpeedCurve)
    reframe: ReframeSpec | None = None
    caption: str | None = None


# ─────────────────────────── proyecto / timeline ───────────────────────────


class StylePreset(str, Enum):
    CINEMATIC = "cinematic"
    HYPE = "hype"
    BROADCAST = "broadcast"
    AESTHETIC = "aesthetic"
    STORY = "story"


class ExportFormat(BaseModel):
    platform: str = "tiktok"  # tiktok | reels | shorts | youtube | cinematic
    width: int = 1080
    height: int = 1920
    fps: int = 60


class AudioTrack(BaseModel):
    music: str | None = None
    music_volume: float = 0.35
    engine_volume: float = 1.0
    sfx_volume: float = 0.5
    ducking: bool = True


class ShotPlan(BaseModel):
    shots: list[Shot] = Field(default_factory=list)
    style: StylePreset = StylePreset.CINEMATIC
    hero_driver: int | None = None
    notes: list[str] = Field(default_factory=list)


class Clip(BaseModel):
    """Plano tal y como vive en el timeline (editable).

    Envuelve el Shot del director y añade edición editorial: recortes de
    entrada/salida (relativos al rango del shot) y activación. El orden de la
    lista Timeline.clips ES el orden del montaje.
    """

    shot: Shot
    trim_in_s: float = 0.0
    trim_out_s: float = 0.0
    enabled: bool = True


class Timeline(BaseModel):
    clips: list[Clip] = Field(default_factory=list)
    audio: AudioTrack | None = None


class ProjectConfig(BaseModel):
    name: str
    replay_path: Path
    format: ExportFormat = Field(default_factory=ExportFormat)
    style: StylePreset = StylePreset.CINEMATIC
    target_duration_s: int = 20
    hero_driver: int | None = None
    ai_enabled: bool = True
    project_dir: Path | None = None  # Projects/<nombre>/


class RenderJob(BaseModel):
    project: Path
    output: Path
    resolution: tuple[int, int] = (1080, 1920)
    fps: int = 60
    codec: str = "h264_nvenc"
    bitrate_kbps: int = 12000
    include_audio: bool = False
    include_captions: bool = True
