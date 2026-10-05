"""Tests de detectores con escenarios sintéticos."""
from __future__ import annotations

from core.models import EventType, SessionInfo, SessionModel

from engines.analyzer.events import get_detectors
from engines.analyzer.events.battle import BattleDetector
from engines.analyzer.events.fast_lap import FastLapDetector
from engines.analyzer.events.off_track import OffTrackDetector
from engines.analyzer.events.overtake import OvertakeDetector
from engines.analyzer.events.spin import SpinDetector
from engines.analyzer.events.start_finish import StartFinishDetector
from tests.synth import scenario, set_last_lap_at_crossings


def model(track_length_m: float = 7000.0) -> SessionModel:
    return SessionModel(
        session=SessionInfo(
            session_num=1, session_type="Race", track_name="spa",
            track_length_m=track_length_m,
        )
    )


def test_start_finish():
    frames = scenario([(5.0, {0: {}})])
    events = StartFinishDetector().detect(frames, model())
    types = {e.type for e in events}
    assert types == {EventType.START, EventType.FINISH}
    start = next(e for e in events if e.type == EventType.START)
    finish = next(e for e in events if e.type == EventType.FINISH)
    assert start.start_s == frames[0].t_s
    assert finish.end_s == frames[-1].t_s


def test_off_track_detection():
    frames = scenario(
        [
            (3.0, {0: {"position": 1, "dist_rate": 0.01}}),
            (1.0, {0: {"track_loc": 0, "dist_rate": 0.002}}),  # salida
            (3.0, {0: {"track_loc": 3, "dist_rate": 0.01}}),
        ]
    )
    events = OffTrackDetector().detect(frames, model())
    assert len(events) == 1
    ev = events[0]
    assert ev.type == EventType.OFF_TRACK
    assert ev.drivers == [0] and ev.target == 0
    assert 2.9 <= ev.start_s <= 3.1
    assert 3.9 <= ev.end_s <= 4.1
    assert ev.importance > 0.5


def test_no_off_track_when_clean():
    frames = scenario([(8.0, {0: {"dist_rate": 0.01}})])
    assert OffTrackDetector().detect(frames, model()) == []


def test_spin_detection():
    # coche rápido → sale de pista y casi se detiene (trompo)
    frames = scenario(
        [
            (4.0, {0: {"position": 1, "dist_rate": 0.02}}),  # ≈ 140 m/s
            (2.5, {0: {"track_loc": 0, "dist_rate": 0.0002}}),  # ≈ 1.4 m/s
            (2.0, {0: {"track_loc": 3, "dist_rate": 0.02}}),
        ]
    )
    events = SpinDetector().detect(frames, model())
    assert len(events) == 1
    ev = events[0]
    assert ev.type == EventType.SPIN
    assert ev.drivers == [0]
    assert ev.metadata["vel_max_previa_ms"] >= 100


def test_overtake_detection():
    # coche 1 delante, coche 0 le adelanta en t=5
    frames = scenario(
        [
            (5.0, {0: {"position": 2, "dist_rate": 0.012}, 1: {"position": 1, "dist_rate": 0.011}}),
            (5.0, {0: {"position": 1, "dist_rate": 0.012}, 1: {"position": 2, "dist_rate": 0.011}}),
        ]
    )
    events = OvertakeDetector().detect(frames, model())
    assert len(events) == 1
    ev = events[0]
    assert ev.type == EventType.OVERTAKE
    assert ev.target == 0  # el que adelantó
    assert ev.drivers == [0, 1]
    assert 3.5 <= ev.start_s <= 5.5
    assert ev.end_s - ev.start_s == 2.5


def test_battle_detection():
    # dos coches pegados (gap 0.2%) durante 6 s
    frames = scenario(
        [
            (6.0, {0: {"position": 1, "dist_rate": 0.01},
                   1: {"position": 2, "dist_rate": 0.01, "lap_dist_pct": 0.002}}),
        ],
        dt=0.1,
    )
    events = BattleDetector().detect(frames, model())
    assert len(events) == 1
    ev = events[0]
    assert ev.type == EventType.BATTLE
    assert set(ev.drivers) == {0, 1}
    assert ev.end_s - ev.start_s >= 4.0


def test_no_battle_when_far_apart():
    frames = scenario(
        [
            (6.0, {0: {"position": 1, "dist_rate": 0.01},
                   1: {"position": 2, "dist_rate": 0.01, "lap_dist_pct": 0.3}}),
        ]
    )
    assert BattleDetector().detect(frames, model()) == []


def test_fast_lap_detection():
    frames = scenario([(14.0, {0: {"position": 1, "dist_rate": 0.15}})])  # vuelta ~6.7 s
    set_last_lap_at_crossings(frames, 0, [92.0, 91.2])
    events = FastLapDetector().detect(frames, model())
    assert len(events) == 2  # primera vuelta válida + mejora
    assert all(e.type == EventType.FAST_LAP for e in events)
    # la segunda es mejor que la primera
    assert events[1].metadata["vuelta_s"] == 91.2
    assert events[1].metadata["mejor_de_sesion"] is True


def test_registry_runs_all_detectors():
    dets = get_detectors()
    assert len(dets) == 6
    frames = scenario(
        [
            (5.0, {0: {"position": 2, "dist_rate": 0.012}, 1: {"position": 1, "dist_rate": 0.011}}),
            (1.0, {0: {"track_loc": 0, "dist_rate": 0.0002}, 1: {"dist_rate": 0.011}}),
            (5.0, {0: {"track_loc": 3, "position": 1, "dist_rate": 0.012}, 1: {"position": 2, "dist_rate": 0.011}}),
        ]
    )
    m = model()
    all_events = []
    for det in dets:
        all_events.extend(det.detect(frames, m))
    types = {e.type for e in all_events}
    assert EventType.OFF_TRACK in types
    assert EventType.START in types and EventType.FINISH in types
    assert all(e.importance > 0 for e in all_events)
