"""Tests del pipeline de exportación FFmpeg.

Incluye un test de integración REAL: genera clips de prueba con testsrc y
renderiza el montaje 9:16, verificando el resultado con ffprobe. Si FFmpeg no
está instalado, ese test se salta.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.models import (
    CameraSpec,
    Clip,
    RenderJob,
    Shot,
    Timeline,
    Transition,
)

from engines.video.export import build_export_command, crop_9x16, export_timeline
from services.ffmpeg import FFmpeg, find_ffmpeg

FF = FFmpeg()


def shot(sid: str, s: float, e: float) -> Shot:
    return Shot(
        id=sid, source_start_s=s, source_end_s=e,
        camera=CameraSpec(group=3, number=0, target=0, group_name="TV1"),
        transition=Transition.CUT,
    )


def test_crop_math():
    # fuente 1920x1080 → ventana vertical centrada 608×1080
    cw, cx = crop_9x16(1920, 1080)
    assert cw == 608 and cx == 656
    assert cw % 2 == 0
    # 2560x1440 → 810x1440 centrado
    cw2, cx2 = crop_9x16(2560, 1440)
    assert cw2 == 810 and cx2 == 875


def test_build_command_structure(tmp_path: Path):
    clips = [Clip(shot=shot("s1", 10.0, 15.0)), Clip(shot=shot("s2", 40.0, 44.0))]
    inputs = {"s1": tmp_path / "a.mp4", "s2": tmp_path / "b.mp4"}
    job = RenderJob(project=tmp_path, output=tmp_path / "out.mp4")
    args = build_export_command(clips, inputs, tmp_path / "out.mp4", job)
    text = " ".join(args)
    assert text.count("-i") == 2
    assert "trim=start=0.500:end=5.500" in text  # margen 0.5 + 5 s de plano
    assert "concat=n=2:v=1:a=0" in text
    assert "crop=608:1080:656:0" in text
    assert "scale=1080:1920" in text
    assert "h264_nvenc" in text


def test_build_command_requires_captures(tmp_path: Path):
    clips = [Clip(shot=shot("s1", 0.0, 5.0))]
    job = RenderJob(project=tmp_path, output=tmp_path / "out.mp4")
    with pytest.raises(ValueError, match="Faltan capturas"):
        build_export_command(clips, {}, tmp_path / "out.mp4", job)
    with pytest.raises(ValueError, match="Ningún clip"):
        build_export_command([], {}, tmp_path / "out.mp4", job)


@pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg no instalado")
def test_export_integration_real(tmp_path: Path):
    """Pipeline completo con FFmpeg real: testsrc → montaje → 9:16."""
    n = 2
    inputs: dict[str, Path] = {}
    for i in range(n):
        p = tmp_path / f"clip{i}.mp4"
        FF.run([
            "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=30:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p),
        ])
        inputs[f"s{i}"] = p

    clips = [
        Clip(shot=shot("s0", 0.0, 2.0)),
        Clip(shot=shot("s1", 0.0, 2.0), trim_in_s=0.5),
    ]
    tl = Timeline(clips=clips)
    out = export_timeline(
        tl, inputs, tmp_path / "final.mp4",
        job=RenderJob(project=tmp_path, output=tmp_path / "final.mp4"),
        margin_s=0.0,  # los clips de testsrc ya coinciden con los shots
    )
    assert out.exists() and out.stat().st_size > 10_000
    info = FF.probe(out)
    assert info["width"] == 1080 and info["height"] == 1920
    # clip 0 completo (2 s) + clip 1 recortado (1.5 s)
    assert 3.2 < info["duration_s"] < 3.8


@pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg no instalado")
def test_export_missing_capture_fails_cleanly(tmp_path: Path):
    clips = [Clip(shot=shot("s0", 0.0, 2.0))]
    with pytest.raises(ValueError):
        export_timeline(
            Timeline(clips=clips), {}, tmp_path / "x.mp4",
            job=RenderJob(project=tmp_path, output=tmp_path / "x.mp4"),
        )
