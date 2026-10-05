"""CLI del iRacing AI Cinematic Studio (MVP 1).

Flujo completo: replay abierta en iRacing → scan (cacheado) → shot plan
(reglas o IA) → captura guiada → montaje 9:16 con FFmpeg.

Uso básico:
    uv run python -m app.cli status
    uv run python -m app.cli generate --driver "Hugo Ferrer" --duration 20 --style hype
    uv run python -m app.cli scan --out analisis.json
    uv run python -m app.cli export --plan plan.json --captures capturas/ -o salida.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai.provider import provider_from_config
from core.models import (
    Clip,
    RenderJob,
    SessionModel,
    ShotPlan,
    StylePreset,
    Timeline,
)
from engines.analyzer.scanner import Scanner
from engines.camera.catalog import CameraCatalog
from engines.director.ai_director import AIDirector
from engines.director.rules import RulesDirector
from engines.replay.sdk_controller import SDKController
from engines.video.export import export_timeline
from services.capture.native import CaptureError, NativeCapture
from services.capture.offline import OfflineCapture
from services.capture.runner import CaptureRunner
from services.capture.ui import UIPilot
from utils.config import AppConfig, load_config


def _print_session(info) -> None:
    print(f"\nSESIÓN: {info.track_display or info.track_name}")
    print(f"  tipo: {info.session_type} (#{info.session_num})")
    print(f"  duración: {info.duration_s or '?'} s · vueltas: {info.laps_total or '?'} · "
          f"longitud: {info.track_length_m or '?'} m")
    print(f"  pilotos: {len(info.drivers)}")
    for d in info.drivers[:8]:
        print(f"    [{d.car_idx:2d}] #{d.car_number:<3} {d.name:<28} {d.car_name or ''}")
    if len(info.drivers) > 8:
        print(f"    ... y {len(info.drivers) - 8} más")


def _hero_from_args(info, driver: str | None, driver_idx: int | None) -> int | None:
    if driver_idx is not None:
        return driver_idx
    if driver:
        match = next(
            (d for d in info.drivers if driver.lower() in d.name.lower()),
            None,
        )
        if match is None:
            print(f"Piloto '{driver}' no encontrado. Disponibles: "
                  f"{[d.name for d in info.drivers]}")
            sys.exit(2)
        return match.car_idx
    return None


# ── comandos ──────────────────────────────────────────────────────────────


def cmd_status(args) -> int:
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: no se pudo conectar con iRacing. Abre una replay en el sim.")
        return 1
    info = ctrl.session_info()
    _print_session(info)
    groups = ctrl.camera_groups()
    print(f"\nCÁMARAS ({len(groups)}): " + ", ".join(f"{n}:{name}" for n, name in groups))
    v = ctrl.verify()
    print(f"\nREPLAY: t={v['session_time_s']} s · play={v['play_speed']}x · "
          f"cámara={v['cam_group']}")
    return 0


def cmd_scan(args) -> int:
    cfg: AppConfig = load_config()
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: abre una replay en iRacing primero.")
        return 1
    info = ctrl.session_info()
    _print_session(info)
    cache_dir = Path(args.project) / "analysis" if args.project else None
    scanner = Scanner(ctrl, cfg.scan, cache_dir=cache_dir)
    replay_path = Path(args.replay) if args.replay else None
    print(f"\nEscaneando sesión a {cfg.scan.speed}x (esto puede tardar unos minutos)...")
    model, frames = scanner.scan(info, replay_path=replay_path)
    print(f"frames: {len(frames)} · vueltas registradas: {len(model.laps)} · "
          f"eventos: {len(model.events)}")
    for e in sorted(model.events, key=lambda x: -x.importance)[:10]:
        print(f"  {e.type.value:<14} t={e.start_s:8.2f}→{e.end_s:8.2f} "
              f"imp={e.importance:.2f} coches={e.drivers}")
    if args.out:
        out = Path(args.out)
        out.write_text(model.model_dump_json(indent=1), encoding="utf-8")
        print(f"\nAnálisis guardado en {out}")
    return 0


def _build_plan(cfg, ctrl, model, args):
    catalog = CameraCatalog.from_controller(ctrl)
    style = StylePreset(args.style)
    provider = provider_from_config(cfg.ai) if args.ai else None
    director = (
        AIDirector(provider, catalog, cfg.director)
        if provider is not None
        else RulesDirector(cfg.director, catalog)
    )
    return director.build_plan(
        model, model.events, style, args.duration,
        _hero_from_args(model.session, args.driver, args.driver_idx),
    )


def cmd_plan(args) -> int:
    cfg: AppConfig = load_config()
    if not Path(args.analysis).exists():
        print(f"ERROR: no existe el análisis {args.analysis}. Ejecuta `scan` primero.")
        return 1
    model = SessionModel.model_validate_json(
        Path(args.analysis).read_text(encoding="utf-8")
    )
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: se necesita iRacing con la replay abierta (catálogo de cámaras).")
        return 1
    plan = _build_plan(cfg, ctrl, model, args)
    print(f"\nPLAN: {len(plan.shots)} planos")
    for s in plan.shots:
        print(f"  {s.id} [{s.source_start_s:7.2f} → {s.source_end_s:7.2f}] "
              f"{s.camera.group_name} → coche {s.camera.target}")
    for n in plan.notes:
        print(f"  · {n}")
    if args.out:
        Path(args.out).write_text(plan.model_dump_json(indent=1), encoding="utf-8")
        print(f"\nPlan guardado en {args.out}")
    return 0


def cmd_capture(args) -> int:
    cfg: AppConfig = load_config()
    plan = ShotPlan.model_validate_json(
        Path(args.plan).read_text(encoding="utf-8")
    )
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: abre la replay en iRacing antes de capturar.")
        return 1
    captures_dir = Path(args.out_dir)
    backend = (
        OfflineCapture()
        if args.offline
        else NativeCapture(ctrl, cfg.capture.videos_dir)
    )
    session_num = ctrl.session_info().session_num
    ui_pilot = None if args.offline else UIPilot()
    runner = CaptureRunner(ctrl, backend, captures_dir, session_num=session_num,
                           ui_pilot=ui_pilot)
    print(f"Capturando {len(plan.shots)} planos (backend: {backend.name})...")
    try:
        result = runner.run(plan)
    except CaptureError as exc:
        print(f"ERROR de captura: {exc}")
        return 1
    print(f"Capturados {len(result)}/{len(plan.shots)} planos → {captures_dir}")
    for sid, p in result.items():
        print(f"  {sid}: {p}")
    return 0 if result else 1


def cmd_export(args) -> int:
    plan = ShotPlan.model_validate_json(
        Path(args.plan).read_text(encoding="utf-8")
    )
    captures_dir = Path(args.captures)
    captures = {
        sid: (captures_dir / f"{sid}.mp4") for sid in (s.id for s in plan.shots)
    }
    missing = [sid for sid, p in captures.items() if not p.exists()]
    if missing:
        print(f"ERROR: faltan capturas: {missing}")
        return 1
    timeline = Timeline(clips=[Clip(shot=s) for s in plan.shots])
    out = Path(args.output)
    print(f"Renderizando {len(plan.shots)} planos → {out} (1080×1920@60, NVENC)...")
    export_timeline(timeline, captures, out, RenderJob(project=Path("."), output=out))
    print(f"Listo: {out} ({out.stat().st_size // 1024} KB)")
    return 0


def cmd_generate(args) -> int:
    """Pipeline completo: scan → plan → captura → export."""
    cfg: AppConfig = load_config()
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: abre la replay en iRacing primero (Replays → Load).")
        return 1
    info = ctrl.session_info()
    _print_session(info)

    project_dir = Path(args.project)
    analysis_dir = project_dir / "analysis"
    captures_dir = project_dir / "captures"
    renders_dir = project_dir / "renders"
    for d in (project_dir, analysis_dir, captures_dir, renders_dir):
        d.mkdir(parents=True, exist_ok=True)

    scanner = Scanner(ctrl, cfg.scan, cache_dir=analysis_dir)
    replay_path = Path(args.replay) if args.replay else None
    print(f"\n[1/4] Escaneando a {cfg.scan.speed}x...")
    model, frames = scanner.scan(info, replay_path=replay_path)
    print(f"      {len(frames)} frames, {len(model.events)} eventos")

    print("[2/4] Generando plan...")
    plan = _build_plan(cfg, ctrl, model, args)
    for s in plan.shots:
        print(f"      {s.id} [{s.source_start_s:7.2f}→{s.source_end_s:7.2f}] {s.camera.group_name}")
    (project_dir / "plan.json").write_text(plan.model_dump_json(indent=1), encoding="utf-8")

    print("[3/4] Capturando planos...")
    backend = OfflineCapture() if args.offline else NativeCapture(ctrl, cfg.capture.videos_dir)
    ui_pilot = None if args.offline else UIPilot()
    runner = CaptureRunner(ctrl, backend, captures_dir, session_num=info.session_num,
                           ui_pilot=ui_pilot)
    try:
        captures = runner.run(plan)
    except CaptureError as exc:
        print(f"      ERROR de captura: {exc}")
        return 1
    print(f"      {len(captures)}/{len(plan.shots)} planos capturados")
    if not captures:
        return 1

    print("[4/4] Renderizando 9:16...")
    timeline = Timeline(clips=[Clip(shot=s) for s in plan.shots if s.id in captures])
    out = renders_dir / f"{project_dir.name}-{args.style}.mp4"
    export_timeline(timeline, captures, out, RenderJob(project=project_dir, output=out))
    print(f"\nLISTO → {out}")
    return 0


def cmd_config(args) -> int:
    cfg = load_config()
    if args.show:
        print(json.dumps(cfg.model_dump(mode="json"), indent=2, default=str))
        return 0
    if args.set_provider:
        cfg.ai.provider = args.set_provider
    if args.set_model:
        cfg.ai.model = args.set_model
    if args.set_base_url:
        cfg.ai.base_url = args.set_base_url
    if args.set_api_key:
        from utils.secrets import set_api_key

        set_api_key(cfg.ai.provider, args.set_api_key)
        print(f"Clave guardada para '{cfg.ai.provider}' (Windows Credential Manager).")
    from utils.config import save_config

    save_config(cfg)
    print("Configuración guardada.")
    return 0


# ── parser ────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iracing-cinematic", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="estado de la conexión y sesión abierta")

    s = sub.add_parser("scan", help="escanea la replay abierta")
    s.add_argument("--replay", help="ruta del .rpy (para la caché)")
    s.add_argument("--project", default="Projects/default", help="carpeta de proyecto")
    s.add_argument("--out", help="guarda el análisis JSON aquí")
    s.set_defaults(func=cmd_scan)

    pl = sub.add_parser("plan", help="genera un shot plan desde un análisis")
    pl.add_argument("--analysis", required=True, help="JSON del análisis (scan --out)")
    pl.add_argument("--style", default="cinematic",
                    choices=[e.value for e in StylePreset])
    pl.add_argument("--duration", type=int, default=20)
    pl.add_argument("--driver", help="piloto protagonista (nombre)")
    pl.add_argument("--driver-idx", type=int, help="piloto protagonista (car_idx)")
    pl.add_argument("--ai", action="store_true", help="usar director IA (si hay clave)")
    pl.add_argument("--out", help="guarda el plan JSON aquí")
    pl.set_defaults(func=cmd_plan)

    c = sub.add_parser("capture", help="ejecuta la captura guiada de un plan")
    c.add_argument("--plan", required=True, help="JSON del shot plan")
    c.add_argument("--out-dir", default="Projects/default/captures")
    c.add_argument("--offline", action="store_true", help="modo dry-run (sin grabar)")
    c.set_defaults(func=cmd_capture)

    e = sub.add_parser("export", help="monta el vídeo 9:16 con FFmpeg")
    e.add_argument("--plan", required=True, help="JSON del shot plan")
    e.add_argument("--captures", required=True, help="carpeta con las capturas")
    e.add_argument("-o", "--output", required=True)
    e.set_defaults(func=cmd_export)

    g = sub.add_parser("generate", help="pipeline completo: scan→plan→captura→export")
    g.add_argument("--replay", help="ruta del .rpy (para la caché)")
    g.add_argument("--project", default="Projects/mi-carrera", help="carpeta de proyecto")
    g.add_argument("--style", default="cinematic",
                   choices=[x.value for x in StylePreset])
    g.add_argument("--duration", type=int, default=20)
    g.add_argument("--driver", help="piloto protagonista (nombre)")
    g.add_argument("--driver-idx", type=int, help="piloto protagonista (car_idx)")
    g.add_argument("--ai", action="store_true", help="usar director IA (si hay clave)")
    g.add_argument("--offline", action="store_true", help="captura dry-run (sin grabar)")
    g.set_defaults(func=cmd_generate)

    cf = sub.add_parser("config", help="ver/editar la configuración")
    cf.add_argument("--show", action="store_true")
    cf.add_argument("--set-provider", help="none | openai_compat")
    cf.add_argument("--set-model")
    cf.add_argument("--set-base-url")
    cf.add_argument("--set-api-key", help="guarda la clave en Credential Manager")
    cf.set_defaults(func=cmd_config)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
