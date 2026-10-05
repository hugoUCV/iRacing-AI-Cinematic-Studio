"""Configuración de tests: plataforma offscreen ANTES de importar PySide6."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
