"""Tests del director de reglas con catálogo y eventos sintéticos."""
from __future__ import annotations

import pytest

from core.models import (
    CameraSpec,
    Event,
    EventType,
    SessionInfo,
    SessionModel,
    StylePreset,
)

from engines.camera.catalog import CameraCatalog
from engines.director.rules import RulesDirector

GROUPS = [
    (1, "cockpit"), (2, "chase"), (3, "TV1"), (4, "TV2"),
    (8, "blimp"), (10, "chopper"),
]


def catalog() -> CameraCatalog:
    return CameraCatalog(GROUPS)


def model(duration_s: float = 600.0, n_drivers: int = 2) -> SessionModel:
    from core.models import DriverInfo

    drivers = [
        DriverInfo(car_idx=i, car_number=str(i + 1), name=f"Piloto {i}", car_number_raw=i + 1)
        for i in range(n_drivers)
    ]
    return SessionModel(
        session=SessionInfo(
            session_num=1, session_type="Race", track_name="spa",
            duration_s=duration_s, track_length_m=7000.0, drivers=drivers,
        )
    )


def ev(etype, t0, t1, cars, target=None, importance=0.7) -> Event:
    return Event(
        id=f"ev-{t0}", type=etype, start_s=t0, end_s=t1, drivers=cars,
        target=target if target is not None else (cars[0] if cars else None),
        importance=importance,
    )


def test_plan_selects_events_sorted_and_non_overlapping():
    events = [
        ev(EventType.OVERTAKE, 200.0, 203.0, [0, 1], target=0, importance=0.9),
        ev(EventType.OFF_TRACK, 215.0, 219.0, [1], target=1, importance=0.6),
        ev(EventType.BATTLE, 202.0, 250.0, [0, 1], target=0, importance=0.5),  # solapa
    ]
    plan = RulesDirector(catalog=catalog()).build_plan(
        model(), events, StylePreset.BROADCAST, target_duration_s=30, hero_driver=0
    )
    # la batalla solapa con el adelantamiento → descartada
    n_event_shots = sum(1 for s in plan.shots if s.id.startswith("shot"))
    assert n_event_shots == 2
    times = [s.source_start_s for s in plan.shots]
    assert times == sorted(times)
    # no hay solapamiento entre shots
    for a, b in zip(plan.shots, plan.shots[1:]):
        assert b.source_start_s >= a.source_end_s - 0.01


def test_hero_boost_breaks_ties():
    events = [
        ev(EventType.OFF_TRACK, 100.0, 103.0, [1], target=1, importance=0.8),
        ev(EventType.OFF_TRACK, 101.0, 104.0, [0], target=0, importance=0.8),  # solapa
    ]
    plan = RulesDirector(catalog=catalog()).build_plan(
        model(), events, StylePreset.CINEMATIC, target_duration_s=15, hero_driver=0
    )
    chosen = next(s for s in plan.shots if s.id.startswith("shot"))
    # gana el evento del héroe (mayor score); su ventana es [101-3, 104+2]
    assert chosen.camera.target == 0
    assert 97.5 <= chosen.source_start_s <= 98.5


def test_camera_fallback_without_tv1():
    cat = CameraCatalog([(1, "cockpit"), (2, "chase"), (4, "TV2")])
    events = [ev(EventType.OVERTAKE, 50.0, 53.0, [0, 1], target=0, importance=0.9)]
    plan = RulesDirector(catalog=cat).build_plan(
        model(), events, StylePreset.BROADCAST, target_duration_s=10, hero_driver=0
    )
    shot = next(s for s in plan.shots if s.id.startswith("shot"))
    assert shot.camera.group_name == "TV2"  # fallback desde TV1


def test_start_uses_static_blimp():
    events = [ev(EventType.START, 0.0, 3.0, [], target=None, importance=0.5)]
    plan = RulesDirector(catalog=catalog()).build_plan(
        model(), events, StylePreset.BROADCAST, target_duration_s=8, hero_driver=None
    )
    start_shot = next(s for s in plan.shots if s.id.startswith("shot"))
    assert start_shot.camera.group_name == "blimp"
    assert start_shot.camera.target is None


def test_plan_fills_to_target_duration():
    events = [ev(EventType.OVERTAKE, 60.0, 63.0, [0, 1], target=0, importance=0.9)]
    plan = RulesDirector(catalog=catalog()).build_plan(
        model(), events, StylePreset.HYPE, target_duration_s=30, hero_driver=0
    )
    total = sum(s.source_end_s - s.source_start_s for s in plan.shots)
    assert total >= 29.0, f"esperaba ≥29 s, total {total}"
    # hay planos de relleno con cámaras rotadas
    fills = [s for s in plan.shots if s.id.startswith("fill")]
    assert fills
    cam_names = [f.camera.group_name for f in fills]
    assert len(set(cam_names)) >= 2  # rotación de variedad


def test_plan_without_catalog_raises():
    director = RulesDirector(catalog=None)
    with pytest.raises(RuntimeError):
        director.build_plan(model(), [], StylePreset.CINEMATIC, 10, None)


def test_clips_never_exceed_session_duration():
    events = [ev(EventType.FINISH, 595.0, 600.0, [0], target=0, importance=0.8)]
    plan = RulesDirector(catalog=catalog()).build_plan(
        model(duration_s=600.0), events, StylePreset.CINEMATIC, target_duration_s=20,
        hero_driver=0,
    )
    assert all(s.source_end_s <= 600.0 for s in plan.shots)
