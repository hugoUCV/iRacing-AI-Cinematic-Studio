"""Construye el .exe standalone con PyInstaller.

Uso: uv run python tools/build_exe.py

Genera `dist/iRacingCinematicStudio.exe` (un solo archivo, sin consola).
Los imports dinámicos (irsdk, keyring, certifi) se declaran explícitamente
porque PyInstaller no los detecta con análisis estático.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HIDDEN_IMPORTS = [
    "irsdk",                        # importado lazy en SDKController._get_ir
    "ai.providers.openai_compat",   # importado en provider_from_config
    "utils.secrets",
    "keyring.backends.Windows",     # backend del Credential Manager
]


def main() -> int:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "iRacingCinematicStudio",
        "--paths", str(ROOT),
    ]
    for mod in HIDDEN_IMPORTS:
        args += ["--hidden-import", mod]
    # certifi: CA bundle para httpx (https)
    args += ["--collect-data", "certifi"]
    args += [str(ROOT / "app" / "main.py")]

    print("Ejecutando PyInstaller… (esto tarda unos minutos)")
    return subprocess.call(args, cwd=str(ROOT))


if __name__ == "__main__":
    sys.exit(main())
