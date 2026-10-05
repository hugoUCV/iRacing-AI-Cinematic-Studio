"""Sanidad de los modelos de dominio y contratos (MVP 0).

Verifica que los modelos Pydantic se construyen/serializan y que las ABC
definen el contrato mínimo entre módulos.
"""
from __future__ import annotations

import pytest

from core.models import (
    CameraSpec,
    Event,
    EventType,
    SessionInfo,
    SessionModel,
    Shot,
    ShotPlan,
    StylePreset,
    Transition,
)


def test_event_roundtrip():
    ev = Event(
        id="ev1",
        type=EventType.OVERTAKE,
        start_s=128.4,
        end_s=130.9,
        drivers=[3, 7],
        target=3,
        importance=0.91,
        metadata={"corner": "Les Combes", "speed_kmh": 218},
    )
    data = ev.model_dump_json()
    assert Event.model_validate_json(data) == ev
    assert ev.importance == 0.91


def test_session_model_defaults():
    m = SessionModel(
        session=SessionInfo(session_num=0, session_type="Race", track_name="spa")
    )
    assert m.events == [] and m.sample_rate_hz == 60
    assert SessionModel.model_validate_json(m.model_dump_json()) == m


def test_shot_plan():
    shot = Shot(
        id="s1",
        source_start_s=100.0,
        source_end_s=105.0,
        camera=CameraSpec(group=3, number=0, target=3, group_name="TV1"),
        transition=Transition.CUT,
    )
    plan = ShotPlan(shots=[shot], style=StylePreset.HYPE, hero_driver=3)
    assert plan.model_dump_json()


def test_timeline_clips():
    """El timeline envuelve shots en clips editables (trim, enabled, orden)."""
    from core.models import Clip, Timeline

    shot = Shot(
        id="s1",
        source_start_s=0.0,
        source_end_s=5.0,
        camera=CameraSpec(group=1, number=0, target=3, group_name="chase"),
    )
    clip = Clip(shot=shot, trim_in_s=0.5, trim_out_s=0.25, enabled=True)
    tl = Timeline(clips=[clip])
    data = tl.model_dump_json()
    rt = Timeline.model_validate_json(data)
    assert rt.clips[0].trim_in_s == 0.5
    assert rt.clips[0].shot.camera.group_name == "chase"


def test_abcs_defined():
    """Las ABC del contrato existen y son importables."""
    from ai.provider import AIProvider, AIProviderError, Message
    from engines.director.base import Director
    from engines.replay.base import ReplayController
    from services.capture.base import CaptureBackend

    for cls in (AIProvider, Director, ReplayController, CaptureBackend):
        assert hasattr(cls, "__abstractmethods__")
    assert Message(role="user", content="hola")
    # Las ABC no se pueden instanciar: los consumidores dependen del contrato,
    # las implementaciones concretas llegan en MVP 1.
    with pytest.raises(TypeError):
        AIProvider()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        ReplayController()  # type: ignore[abstract]
