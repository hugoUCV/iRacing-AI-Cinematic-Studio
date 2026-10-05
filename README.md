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

**MVP 0** — análisis técnico, arquitectura e interfaces definidas.
La implementación (MVP 1: scan → eventos → shot plan → captura → export
vertical) arranca a continuación.

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
- Opcional: OBS 28+ (captura con audio), una API key OpenAI/Gemini/Pollinations
  u Ollama local (IA)

## Desarrollo

```bash
uv sync            # entorno + dependencias
uv run pytest      # tests
uv run ruff check  # lint
```
