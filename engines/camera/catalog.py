"""Camera Engine: catálogo runtime de grupos de cámara.

El catálogo se lee del sim (CameraInfo) — nada se hardcodea. Los nombres de
grupo (cockpit, chase, TV1...) se resuelven a números en tiempo de ejecución
porque los grupos personalizados del usuario desplazan la numeración.
"""
from __future__ import annotations


class CameraCatalog:
    def __init__(self, groups: list[tuple[int, str]]):
        self.groups = groups
        self._by_name: dict[str, tuple[int, str]] = {}
        for num, name in groups:
            self._by_name[name.lower()] = (num, name)

    @classmethod
    def from_controller(cls, controller) -> "CameraCatalog":
        return cls(controller.camera_groups())

    def resolve(self, name: str) -> tuple[int, str] | None:
        """(GroupNum, GroupName) para un nombre, o None si no existe."""
        return self._by_name.get(name.lower())

    def resolve_first(self, names: list[str]) -> tuple[int, str] | None:
        """Primer grupo disponible de una lista de preferencias."""
        for name in names:
            r = self.resolve(name)
            if r:
                return r
        return None

    def __len__(self) -> int:
        return len(self.groups)

    def __repr__(self) -> str:  # pragma: no cover
        return f"CameraCatalog({[g[1] for g in self.groups]})"
