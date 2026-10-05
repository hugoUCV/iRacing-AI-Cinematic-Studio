"""Configuración global de la aplicación.

Se guarda en %APPDATA%/iRacingCinematicStudio/config.json. Cualquier valor
puede venir de ahí; si no existe el archivo, se usan los valores por defecto.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "iRacingCinematicStudio"


class AIConfig(BaseModel):
    provider: str = "none"  # none | openai_compat (OpenAI/Gemini/Pollinations/Ollama)
    base_url: str = "https://gen.pollinations.ai/v1"
    model: str = "openai"
    temperature: float = 0.4
    key_env: str = "IRACING_AI_API_KEY"  # override por variable de entorno


class CaptureConfig(BaseModel):
    backend: str = "native"  # native | obs | offline
    videos_dir: Path | None = None  # None → Documents/iRacing/videos
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""


class ScanConfig(BaseModel):
    speed: int = 4  # velocidad de reproducción durante el escaneo (1-16)
    poll_hz: float = 30.0  # frecuencia de muestreo en reloj real
    max_duration_s: float = 3 * 3600  # guardrail de seguridad


class DirectorConfig(BaseModel):
    default_style: str = "cinematic"
    anticipation_s: float = 3.0  # segundos antes del evento
    after_s: float = 2.0  # segundos después del evento
    min_gap_s: float = 4.0  # separación mínima entre shots
    variety_len_s: float = 3.5  # duración de los planos de relleno


class FFmpegConfig(BaseModel):
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


class AppConfig(BaseModel):
    ai: AIConfig = Field(default_factory=AIConfig)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    director: DirectorConfig = Field(default_factory=DirectorConfig)
    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)


def config_path() -> Path:
    return CONFIG_DIR / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    """Carga la configuración; si no existe el archivo, devuelve defaults."""
    path = path or config_path()
    if path.exists():
        data = AppConfig.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        data = AppConfig()
    return data


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    return path


def default_videos_dir() -> Path | None:
    """Carpeta de capturas de vídeo integradas de iRacing."""
    p = Path.home() / "Documents" / "iRacing" / "videos"
    return p if p.is_dir() else None
