"""Localización y envoltura de FFmpeg.

Todo el post-proceso (trim, concat, crop 9:16, xfade, setpts, sidechaincompress,
NVENC) pasa por aquí; los módulos de engines/video y engines/audio no invocan
FFmpeg directamente.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class FFmpegError(RuntimeError):
    pass


class FFmpeg:
    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    def available(self) -> bool:
        return shutil.which(self.ffmpeg) is not None

    def run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Ejecuta ffmpeg con los argumentos dados (sin -y: añadirlo si hace
        falta sobrescribir)."""
        cmd = [self.ffmpeg, "-hide_banner"] + args
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if check and proc.returncode != 0:
            raise FFmpegError(
                f"ffmpeg falló (rc={proc.returncode}):\n{' '.join(cmd)}\n{proc.stderr[-2000:]}"
            )
        return proc

    def probe(self, path: Path) -> dict[str, Any]:
        """Dimensiones, fps y duración del primer stream de vídeo."""
        cmd = [
            self.ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json", str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if proc.returncode != 0:
            raise FFmpegError(f"ffprobe falló para {path}: {proc.stderr[-500:]}")
        stream = json.loads(proc.stdout)["streams"][0]
        num, den = (stream.get("r_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
        return {
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "fps": round(fps, 3),
            "duration_s": float(stream.get("duration") or 0.0),
        }


def find_ffmpeg() -> Path | None:
    p = shutil.which("ffmpeg")
    return Path(p) if p else None
