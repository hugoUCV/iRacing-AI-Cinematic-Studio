# iRacing AI Cinematic Studio

**Director cinematográfico y editor de vídeo impulsado por IA para iRacing.**

Convierte una replay de iRacing en contenido vertical listo para TikTok,
Instagram Reels y YouTube Shorts:

```
replay abierta en iRacing
        ↓
análisis automático de la sesión (eventos, batallas, adelantamientos...)
        ↓
AI Director → plan de planos (o director de reglas sin IA)
        ↓
captura guiada (seek + cámara + play, vía SDK)
        ↓
montaje FFmpeg: 9:16, rampas, transiciones, audio, texto
        ↓
MP4 1080×1920 + título/caption/hashtags
```

## Estado

**MVP 1 (backend)** — pipeline completo implementado y testeado (62 tests):

- `SDKController` (pyirsdk): seek por tiempo de sesión, cámaras, play/pausa,
  captura integrada de iRacing, verificación de comandos.
- Scanner del replay → `SessionModel` cacheado (eventos, vueltas).
- Detectores: salidas de pista, trompos, adelantamientos, batallas, vueltas
  rápidas, salida/llegada.
- Director de reglas (determinista) + AI Director (LLM con fallback a reglas).
- Captura guiada por plano (backend nativo iRacing u offline/dry-run).
- Export 1080×1920@60 con FFmpeg (NVENC, fallback libx264) — **verificado con
  render real** en tests de integración.
- CLI (`python -m app.cli`).

Pendiente de MVP 1: interfaz gráfica (PySide6, siguiente iteración) y la
verificación en vivo con una replay real (ver Spikes).

## Uso (CLI)

```bash
uv sync                                  # entorno
# 1) con una replay ABIERTA en iRacing:
uv run python -m app.cli status          # sesión + cámaras disponibles
uv run python -m app.cli scan            # escanea y muestra eventos (cacheado)
# 2) generar el vídeo completo:
uv run python -m app.cli generate \
    --driver "Hugo Ferrer" --style hype --duration 20 \
    --project "Projects/Spa GT3"
# 3) IA opcional (OpenAI/Gemini/Pollinations/Ollama — todos OpenAI-compatibles):
uv run python -m app.cli config --set-provider openai_compat \
    --set-base-url https://gen.pollinations.ai/v1 --set-model openai \
    --set-api-key TU_CLAVE        # se guarda en Windows Credential Manager
uv run python -m app.cli generate --ai ...
```

Modo dry-run (sin grabar, valida la orquestación):

```bash
uv run python -m app.cli capture --plan Projects/.../plan.json --offline
```

## Verificación en vivo (spikes)

Con una replay abierta en iRacing:

```bash
uv run python tools/spike_s1_s3.py
```

Valida S1 (¿`CarIdx*` trae todos los coches durante la replay?) y S3
(precisión del seek). El resultado se registra en el skill del proyecto.

## Documentos

- [`docs/01-analisis-tecnico.md`](docs/01-analisis-tecnico.md) — realidad del
  SDK/formatos de iRacing (verificado en código fuente), limitaciones,
  decisiones y plan de MVP.
- [`docs/02-arquitectura.md`](docs/02-arquitectura.md) — módulos, interfaces,
  modelos de dominio, estructura de carpetas.

## Decisiones clave

1. **El motor gráfico de iRacing ES el renderer**: la app dirige el reproductor
   de replays vía SDK (`replay_search_session_time`, `cam_switch_num`,
   `video_capture`) y monta el material con FFmpeg. No se parsea el `.rpy`.
2. **La IA decide, el software ejecuta**: los LLM solo producen JSON validado
   (shot plan, textos); nunca controlan el sim ni FFmpeg.
3. **Funciona sin API key**: el director determinista garantiza el pipeline;
   la IA lo mejora.

## Requisitos

- Windows + iRacing instalado (misma máquina)
- Python 3.11+ y [uv](https://docs.astral.sh/uv/)
- FFmpeg en PATH (para exportar)
- Para capturar: activar **Enable video capture** en las opciones gráficas de
  iRacing (o usar `--offline` para probar)
- Opcional: OBS 28+ (captura con audio, MVP 3), una API key
  OpenAI/Gemini/Pollinations u Ollama local (IA)

## Desarrollo

```bash
uv sync                          # entorno + dependencias
uv run pytest                    # tests
uv run ruff check                # lint
uv sync --group gui              # + PySide6 (UI)
```
