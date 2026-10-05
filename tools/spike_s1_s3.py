"""Spike S1+S3: verificación real contra iRacing con una replay abierta.

S1 (bloqueante de diseño): ¿los arrays CarIdx* contienen datos de TODOS los
coches durante la reproducción de la replay?
S3: ¿qué precisión tiene replay_search_session_time?

Uso (con una replay abierta en iRacing, en el escritorio):
    uv run python tools/spike_s1_s3.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.replay.sdk_controller import SDKController  # noqa: E402


def main() -> int:
    ctrl = SDKController()
    if not ctrl.connect():
        print("ERROR: iRacing no está corriendo. Abre una replay primero.")
        return 1
    info = ctrl.session_info()
    drivers = {d.car_idx: d.name for d in info.drivers}
    print(f"Sesión: {info.track_display or info.track_name} "
          f"({info.session_type}, {len(drivers)} pilotos)")

    # ── S3: precisión del seek ─────────────────────────────────────────────
    print("\n[S3] Precisión de replay_search_session_time:")
    results = []
    for target in (30.0, 120.0, 300.0):
        ctrl.seek_session_time(info.session_num, int(target * 1000))
        time.sleep(1.2)  # el sim tarda en cargar la zona
        t = ctrl.read().get("ReplaySessionTime")
        delta = abs(float(t) - target) if t is not None else None
        print(f"  pedido {target:7.1f}s → leído {t}  (Δ = {delta})")
        results.append(delta)
    if all(d is not None and d < 1.5 for d in results):
        print("  S3 OK: el seek por tiempo de sesión es preciso (<1.5 s)")
    else:
        print("  S3 WARN: revisar márgenes de anticipación en el runner")

    # ── S1: todos los coches durante la reproducción ───────────────────────
    print("\n[S1] ¿CarIdx* trae todos los coches durante la replay?")
    ctrl.seek_session_time(info.session_num, 10_000)
    time.sleep(1.0)
    ctrl.play(speed=1.0)
    samples: dict[int, int] = {}
    car_count = set()
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < 5.0:
            snap = ctrl.read()
            pos = snap.get("CarIdxPosition")
            if isinstance(pos, list):
                for i, p in enumerate(pos):
                    if p is not None and p > 0:
                        samples[i] = samples.get(i, 0) + 1
                        car_count.add(i)
            time.sleep(0.1)
    finally:
        ctrl.pause()

    print(f"  coches con datos: {len(car_count)} de {len(drivers)} pilotos")
    for idx in sorted(samples)[:10]:
        print(f"    car_idx {idx:2d} ({drivers.get(idx, '?'):<28}) "
              f"muestras={samples[idx]}")
    if len(car_count) >= max(1, len(drivers) - 1):
        print("  S1 OK: todos los coches están disponibles durante la replay")
    else:
        print(f"  S1 FAIL: faltan {len(drivers) - len(car_count)} coches "
              "→ el scanner necesitará alternar el coche cámara")
    return 0


if __name__ == "__main__":
    sys.exit(main())
