"""Shot library: qué cámara usar según el evento y el estilo.

Mapea (tipo de evento, estilo) → nombre de grupo preferido, con cadenas de
fallback. Los números los resuelve el catálogo en runtime. El movimiento
cinematográfico se añade en post (MVP 2); aquí solo se elige la cámara base.
"""
from __future__ import annotations

from core.models import CameraSpec, EventType, StylePreset

# Preferencias por evento (de más a menos deseable).
EVENT_PREFS: dict[EventType, list[str]] = {
    EventType.OVERTAKE: ["TV1", "TV2", "chopper", "chase"],
    EventType.OFF_TRACK: ["TV2", "TV1", "blimp", "chase"],
    EventType.SPIN: ["TV2", "TV1", "chase", "blimp"],
    EventType.BATTLE: ["TV1", "chopper", "TV2", "chase"],
    EventType.FAST_LAP: ["cockpit", "chase", "TV1"],
    EventType.CONTACT: ["TV2", "TV1", "chase"],
    EventType.CLOSE_CALL: ["TV1", "TV2", "chopper"],
    EventType.POSITION_CHANGE: ["TV1", "TV2", "chase"],
    EventType.PIT_STOP: ["chase", "TV1", "TV2"],
    EventType.START: ["blimp", "chopper", "TV1"],  # plano estático amplio
    EventType.FINISH: ["TV1", "chopper", "blimp"],
}

# Grupos sin coche objetivo (planos estáticos/de pista).
STATIC_GROUPS = {"blimp"}

# Relleno entre eventos: rotación de variedad según estilo.
VARIETY_PREFS: dict[StylePreset, list[str]] = {
    StylePreset.CINEMATIC: ["chopper", "TV1", "chase", "blimp"],
    StylePreset.HYPE: ["cockpit", "chase", "TV1", "cockpit"],
    StylePreset.BROADCAST: ["TV1", "TV2", "chopper", "chase"],
    StylePreset.AESTHETIC: ["chase", "cockpit", "TV1", "chopper"],
    StylePreset.STORY: ["TV1", "chopper", "chase", "cockpit"],
}

# Preferencias genéricas por estilo (cola de fallback).
STYLE_PREFS: dict[StylePreset, list[str]] = {
    StylePreset.CINEMATIC: ["chopper", "blimp", "TV1", "chase", "cockpit"],
    StylePreset.HYPE: ["cockpit", "chase", "TV1", "TV2"],
    StylePreset.BROADCAST: ["TV1", "TV2", "chopper", "blimp", "chase"],
    StylePreset.AESTHETIC: ["chase", "cockpit", "TV1", "blimp"],
    StylePreset.STORY: ["TV1", "chopper", "chase", "cockpit", "blimp"],
}


def pick_camera(
    event_type: EventType,
    style: StylePreset,
    catalog,
    hero_driver: int | None,
    variety_index: int = 0,
    is_variety: bool = False,
) -> CameraSpec:
    """Elige la cámara para un plano. Lanza RuntimeError si no hay ningún
    grupo disponible (nunca debe pasar en una sesión real)."""
    if is_variety:
        prefs = list(VARIETY_PREFS.get(style, ["TV1"]))
        # rotar según el índice de relleno para no repetir cámara
        prefs = prefs[variety_index % len(prefs) :] + prefs[: variety_index % len(prefs)]
    else:
        prefs = list(EVENT_PREFS.get(event_type, ["TV1"]))
    prefs += [p for p in STYLE_PREFS.get(style, []) if p not in prefs]

    resolved = catalog.resolve_first(prefs)
    if not resolved:
        raise RuntimeError("No hay grupos de cámara disponibles")
    num, name = resolved
    static = name.lower() in STATIC_GROUPS
    return CameraSpec(
        group=num,
        number=0,
        target=None if static else hero_driver,
        group_name=name,
    )
