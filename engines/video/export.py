"""Video Engine: pipeline de exportación FFmpeg.

MVP 1: por cada clip habilitado → trim (con margen de captura y recortes
editoriales) → normalizar a 1920×1080@60 → concat → crop centrado 9:16 →
escalar a 1080×1920 → NVENC (fallback libx264).

Los recortes de timeline (trim_in/out) son relativos al rango del shot; las
capturas empiezan `margin_s` antes del inicio del shot, así que el trim real
sobre el archivo es `margin + trim_in` por delante y `margin + trim_out` por
detrás.
"""
from __future__ import annotations

from pathlib import Path

from core.models import Clip, RenderJob, Timeline

from services.ffmpeg import FFmpeg, FFmpegError

CAPTURE_MARGIN_S = 0.5


def crop_9x16(width: int, height: int) -> tuple[int, int]:
    """Ventana vertical centrada en una fuente 16:9: (crop_w, crop_x)."""
    crop_w = round(height * 9 / 16 / 2) * 2  # par más cercano (NVENC)
    x = (width - crop_w) // 2
    return crop_w, x


def _clip_filter(i: int, clip: Clip, margin_s: float) -> str:
    """Cadena de filtros para el input i."""
    s = clip.shot.source_start_s
    e = clip.shot.source_end_s
    start = max(0.0, margin_s + clip.trim_in_s)
    end = max(start + 0.1, margin_s + (e - s) - clip.trim_out_s)
    return (
        f"[{i}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
        f"scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080,setsar=1,fps=60[v{i}]"
    )


def build_export_command(
    clips: list[Clip],
    inputs: dict[str, Path],
    output: Path,
    job: RenderJob,
    margin_s: float = CAPTURE_MARGIN_S,
) -> list[str]:
    """Argumentos completos de ffmpeg para el montaje (sin binario)."""
    # la fuente ya está normalizada a 1920x1080 en el filtro por clip
    cw, cx = crop_9x16(1920, 1080)
    enabled = [c for c in clips if c.enabled]
    if not enabled:
        raise ValueError("Ningún clip habilitado para exportar")
    missing = [c.shot.id for c in enabled if c.shot.id not in inputs]
    if missing:
        raise ValueError(f"Faltan capturas para los shots: {missing}")

    args: list[str] = ["-y"]
    for c in enabled:
        args += ["-i", str(inputs[c.shot.id])]

    filters = [_clip_filter(i, c, margin_s) for i, c in enumerate(enabled)]
    concat = "".join(f"[v{i}]" for i in range(len(enabled)))
    filters.append(
        f"{concat}concat=n={len(enabled)}:v=1:a=0[catv];"
        f"[catv]crop={cw}:1080:{cx}:0,scale={job.resolution[0]}:{job.resolution[1]}:flags=lanczos,"
        f"format=yuv420p[vout]"
    )
    args += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    args += ["-r", str(job.fps)]
    args += ["-c:v", job.codec]
    if job.codec == "h264_nvenc":
        args += ["-preset", "p5", "-b:v", f"{job.bitrate_kbps}k"]
    else:
        args += ["-crf", "18", "-preset", "medium"]
    args += ["-movflags", "+faststart", str(output)]
    return args


def export_timeline(
    timeline: Timeline,
    captures: dict[str, Path],
    output: Path,
    job: RenderJob | None = None,
    ffmpeg: FFmpeg | None = None,
    margin_s: float = CAPTURE_MARGIN_S,
    on_progress=None,
) -> Path:
    """Renderiza el timeline a `output`. Devuelve la ruta del archivo.

    Si NVENC no está disponible en la máquina, reintenta con libx264.
    on_progress(fraction | None, message) usa `-progress` de ffmpeg."""
    job = job or RenderJob(project=Path("."), output=output)
    ff = ffmpeg or FFmpeg()
    if not ff.available():
        raise FFmpegError("FFmpeg no encontrado en el PATH")

    clips = [c for c in timeline.clips if c.enabled]
    output.parent.mkdir(parents=True, exist_ok=True)
    total = sum(
        max(0.0, (c.shot.source_end_s - c.shot.source_start_s) - c.trim_in_s - c.trim_out_s)
        for c in clips
    )

    args = build_export_command(clips, captures, output, job, margin_s)
    try:
        ff.run(args, on_progress=on_progress, total_s=total or None)
    except FFmpegError as first:
        if job.codec != "h264_nvenc":
            raise
        # fallback: codificador software
        fallback = job.model_copy(update={"codec": "libx264"})
        args2 = build_export_command(clips, captures, output, fallback, margin_s)
        ff.run(args2, on_progress=on_progress, total_s=total or None)
    if on_progress:
        on_progress(1.0, "render completado")
    return output
