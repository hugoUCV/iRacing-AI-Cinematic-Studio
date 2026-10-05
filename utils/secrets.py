"""Secretos: claves API en Windows Credential Manager (keyring).

Regla (spec §26): la clave nunca se almacena de forma insegura. En Windows,
keyring delega en el Windows Credential Locker. La variable de entorno
IRACING_AI_API_KEY (configurable) tiene prioridad y permite CI/local sin
Credential Manager.
"""
from __future__ import annotations

import os

SERVICE = "iRacingCinematicStudio"
ENV_KEY = "IRACING_AI_API_KEY"


def get_api_key(provider: str, env_key: str = ENV_KEY) -> str | None:
    """Clave del proveedor: variable de entorno primero, keyring después."""
    env = os.environ.get(env_key)
    if env:
        return env.strip()
    try:
        import keyring

        return keyring.get_password(SERVICE, provider)
    except Exception:  # sin backend disponible
        return None


def set_api_key(provider: str, key: str) -> None:
    import keyring

    keyring.set_password(SERVICE, provider, key)


def delete_api_key(provider: str) -> None:
    try:
        import keyring

        keyring.delete_password(SERVICE, provider)
    except Exception:
        pass
