"""Tests del AIDirector con un provider fake."""
from __future__ import annotations

import pytest

from ai.provider import AIProvider, AIProviderError, Message
from ai.schemas import LLMShot, LLMShotPlan
from core.models import DriverInfo, Event, EventType, SessionInfo, SessionModel, StylePreset

from engines.camera.catalog import CameraCatalog
from engines.director.ai_director import AIDirector

GROUPS = [(1, "cockpit"), (2, "chase"), (3, "TV1"), (10, "chopper")]


class FakeProvider(AIProvider):
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls: list[list[Message]] = []

    def available(self):
        return True

    def chat_json(self, messages, schema):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.result

    def chat_text(self, messages):
        return ""


def model() -> SessionModel:
    return SessionModel(
        session=SessionInfo(
            session_num=1, session_type="Race", track_name="spa",
            track_display="Spa-Francorchamps", duration_s=600.0,
            drivers=[
                DriverInfo(car_idx=0, car_number="7", name="Hugo", car_number_raw=7),
                DriverInfo(car_idx=1, car_number="21", name="Rival", car_number_raw=21),
            ],
        )
    )


def events() -> list[Event]:
    return [
        Event(id="e1", type=EventType.OVERTAKE, start_s=128.0, end_s=131.0,
              drivers=[0, 1], target=0, importance=0.9),
        Event(id="e2", type=EventType.OFF_TRACK, start_s=300.0, end_s=304.0,
              drivers=[1], target=1, importance=0.6),
    ]


def test_ai_plan_conversion_and_camera_resolution():
    provider = FakeProvider(
        result=LLMShotPlan(
            shots=[
                LLMShot(start_s=125.0, end_s=133.0, group_name="TV1", target=0),
                LLMShot(start_s=297.0, end_s=306.0, group_name="no-existe", target=None),
            ],
            notes=["buen plano"],
        )
    )
    director = AIDirector(provider, CameraCatalog(GROUPS))
    plan = director.build_plan(model(), events(), StylePreset.HYPE, 20, hero_driver=0)

    assert len(plan.shots) == 2
    s1, s2 = plan.shots
    assert s1.camera.group == 3 and s1.camera.group_name == "TV1"
    assert s1.camera.target == 0
    # cámara desconocida → fallback a la primera disponible
    assert s2.camera.group_name in {g for _, g in GROUPS}
    assert s2.camera.target == 0  # hereda el héroe al no indicar target
    assert [s.source_start_s for s in plan.shots] == sorted(s.source_start_s for s in plan.shots)
    assert plan.notes == ["buen plano"]


def test_ai_director_receives_compact_events():
    provider = FakeProvider(result=LLMShotPlan(shots=[LLMShot(start_s=0, end_s=5)]))
    director = AIDirector(provider, CameraCatalog(GROUPS))
    director.build_plan(model(), events(), StylePreset.CINEMATIC, 10, hero_driver=0)
    user_msg = provider.calls[0][1].content
    assert '"overtake"' in user_msg
    assert '"Hugo"' in user_msg or "hero" in user_msg
    system = provider.calls[0][0].content
    assert "Spa-Francorchamps" in system and "hype" not in system


def test_ai_director_falls_back_to_rules_on_error():
    provider = FakeProvider(error=AIProviderError("sin conexión"))
    director = AIDirector(provider, CameraCatalog(GROUPS))
    plan = director.build_plan(model(), events(), StylePreset.BROADCAST, 15, hero_driver=0)
    # el fallback (reglas) produce planos deterministas desde los eventos
    assert plan.shots
    assert any(s.id.startswith("shot-") for s in plan.shots)


def test_ai_director_falls_back_when_plan_empty():
    provider = FakeProvider(result=LLMShotPlan(shots=[]))
    director = AIDirector(provider, CameraCatalog(GROUPS))
    plan = director.build_plan(model(), events(), StylePreset.BROADCAST, 15, hero_driver=0)
    assert plan.shots


def test_ai_director_clamps_to_session_duration():
    provider = FakeProvider(
        result=LLMShotPlan(shots=[LLMShot(start_s=595.0, end_s=610.0, group_name="TV1")])
    )
    director = AIDirector(provider, CameraCatalog(GROUPS))
    plan = director.build_plan(model(), events(), StylePreset.CINEMATIC, 10, hero_driver=None)
    assert plan.shots[0].source_end_s <= 600.0


def test_ai_director_unavailable_provider_uses_rules():
    provider = FakeProvider()
    provider.available = lambda: False  # type: ignore[method-assign]
    director = AIDirector(provider, CameraCatalog(GROUPS))
    plan = director.build_plan(model(), events(), StylePreset.CINEMATIC, 10, hero_driver=None)
    assert not provider.calls  # ni siquiera se consultó al LLM
    assert plan.shots
