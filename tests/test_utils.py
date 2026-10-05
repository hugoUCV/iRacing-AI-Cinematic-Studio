"""Tests de utilidades: config, cache, secrets."""
from __future__ import annotations

from pathlib import Path

from utils import cache, config, secrets


def test_config_defaults_and_roundtrip(tmp_path: Path):
    cfg = config.AppConfig()
    cfg.ai.provider = "openai_compat"
    cfg.ai.model = "gpt-4o-mini"
    cfg.director.default_style = "hype"
    p = config.save_config(cfg, tmp_path / "config.json")
    loaded = config.load_config(p)
    assert loaded.ai.provider == "openai_compat"
    assert loaded.ai.model == "gpt-4o-mini"
    assert loaded.director.default_style == "hype"
    # valores no tocados mantienen el default
    assert loaded.capture.backend == "native"
    assert loaded.scan.speed == 4


def test_config_missing_file_returns_defaults(tmp_path: Path):
    cfg = config.load_config(tmp_path / "noexiste.json")
    assert cfg.ai.provider == "none"
    assert cfg.director.anticipation_s == 3.0


def test_cache_roundtrip(tmp_path: Path):
    c = cache.JsonCache(tmp_path / "cache")
    key = cache.content_hash("session", 42, ["a", "b"])
    data = {"eventos": [1, 2, 3], "texto": "ñandú"}
    c.save(key, data)
    assert c.load(key) == data
    assert c.load("clave-inexistente") is None
    # mismo contenido ⇒ misma clave
    assert key == cache.content_hash("session", 42, ["a", "b"])
    # contenido distinto ⇒ clave distinta
    assert key != cache.content_hash("session", 43, ["a", "b"])


def test_secrets_env_override(monkeypatch):
    monkeypatch.setenv(secrets.ENV_KEY, "clave-de-entorno")
    assert secrets.get_api_key("openai_compat") == "clave-de-entorno"


def test_secrets_keyring_absent_returns_none(monkeypatch):
    """Sin variable de entorno y sin backend de keyring → None, sin excepción."""
    monkeypatch.delenv(secrets.ENV_KEY, raising=False)

    def boom(*a, **k):
        raise RuntimeError("no backend")

    monkeypatch.setattr("keyring.get_password", boom)
    assert secrets.get_api_key("openai_compat") is None
