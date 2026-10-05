"""Cachés por contenido: análisis de sesión, decisiones de IA, thumbnails.

Principio (spec §28): nunca se re-trabaja lo ya pagado. Las claves son hashes
de los contenidos de entrada, así que reutilizar entrada ⇒ reutilizar salida.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def content_hash(*parts: object) -> str:
    """Hash estable de los contenidos de entrada (el orden importa)."""
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()[:20]


class JsonCache:
    """Caché JSON en disco: una clave → un archivo."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def path(self, key: str) -> Path:
        safe = _SAFE.sub("_", key)[:80]
        return self.base_dir / f"{safe}.json"

    def load(self, key: str) -> Any | None:
        p = self.path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, key: str, data: Any) -> Path:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )
        return p
