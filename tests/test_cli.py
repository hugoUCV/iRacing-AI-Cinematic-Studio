"""Tests de humo del CLI (sin simulador: solo parser y errores claros)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.cli import build_parser, cmd_export, cmd_plan


def test_parser_commands_exist():
    p = build_parser()
    args = p.parse_args(["status"])
    assert args.cmd == "status"
    args = p.parse_args(["generate", "--style", "hype", "--duration", "30", "--driver", "Hugo"])
    assert args.style == "hype" and args.duration == 30


def test_plan_requires_analysis(tmp_path: Path, monkeypatch):
    p = build_parser()
    args = p.parse_args(["plan", "--analysis", str(tmp_path / "noexiste.json")])
    assert cmd_plan(args) == 1  # error claro sin excepción


def test_export_missing_captures(tmp_path: Path):
    from core.models import CameraSpec, Shot, ShotPlan, StylePreset

    plan = ShotPlan(
        shots=[Shot(id="s1", source_start_s=0.0, source_end_s=5.0,
                    camera=CameraSpec(group=1, number=0, target=0, group_name="chase"))],
        style=StylePreset.CINEMATIC,
    )
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(plan.model_dump_json(), encoding="utf-8")
    p = build_parser()
    args = p.parse_args([
        "export", "--plan", str(plan_file),
        "--captures", str(tmp_path / "vacio"),
        "-o", str(tmp_path / "out.mp4"),
    ])
    assert cmd_export(args) == 1  # faltan capturas → error claro


def test_generate_requires_sim(monkeypatch, capsys):
    """Sin iRacing corriendo, generate termina con mensaje claro."""
    from app import cli

    def no_connect(self):
        return False

    monkeypatch.setattr(cli.SDKController, "connect", no_connect)
    p = build_parser()
    args = p.parse_args(["generate"])
    assert cli.cmd_generate(args) == 1
    assert "abre la replay" in capsys.readouterr().out
