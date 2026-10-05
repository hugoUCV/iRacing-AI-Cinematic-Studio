# ARQUITECTURA — iRacing AI Cinematic Studio

> Complemento del análisis técnico (`01-analisis-tecnico.md`).
> Aquí: módulos, interfaces entre ellos, modelos de datos, estructura de carpetas
> y el formato del shot plan. Todo lo definido aquí tiene un archivo real en el
> esqueleto del repositorio (MVP 0).

---

## 1. Diagrama de flujo

```
                         ┌─────────────────────────────┐
                         │        iRacing (sim)        │
                         │  replay abierta · memoria   │
                         │  compartida · broadcast     │
                         └──────────────┬──────────────┘
                                        │ pyirsdk
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               ▼                               │
        │                    engines/replay (SDKBridge)                 │
        │                     seek · cámara · play · leer              │
        │                               │                               │
        │         ┌─────────────────────┼──────────────────────┐        │
        │         ▼                     ▼                      ▼        │
        │  engines/analyzer      services/capture       engines/camera │
        │  (scan → SessionModel)  (nativo | OBS)       (catálogo,      │
        │         │                     │               shot library)   │
        │         ▼                     │                      ▲        │
        │  engines/analyzer/events      │                      │        │
        │  (detectores → Event[])       │                      │        │
        │         │                     │                      │        │
        │         └──────────┬──────────┘                      │        │
        │                    ▼                                 │        │
        │            engines/director                          │        │
        │      (reglas o AIProvider → ShotPlan)                 │        │
        │                    │                                 │        │
        │                    ▼                                 │        │
        │            core/timeline (proyecto editable)          │        │
        │                    │                                 │        │
        │        ┌───────────┼───────────────┐                 │        │
        │        ▼           ▼               ▼                 │        │
        │  engines/video  engines/audio  engines/content       │        │
        │  (FFmpeg: montaje, reframe, rampas, export)          │        │
        │        └───────────┴───────────────┘                 │        │
        │                    ▼                                 │        │
        │            MP4 1080×1920 · metadatos sociales         │        │
        └───────────────────────────────────────────────────────┘
```

## 2. Módulos

| Módulo | Ruta | Responsabilidad | Depende de |
|---|---|---|---|
| **Replay Engine** | `engines/replay/` | puente con pyirsdk: conexión, lectura, seek, cámara, play/pausa, verificación de comandos | pyirsdk |
| **Analyzer** | `engines/analyzer/` | escaneo de la sesión → `SessionModel`; caché por hash | Replay Engine |
| **Event Detection** | `engines/analyzer/events/` | detectores por tipo → `Event[]` con `importance` | SessionModel |
| **Camera Engine** | `engines/camera/` | catálogo de grupos (runtime), shot library, presets de cámara, especificación de plano | — |
| **AI Director** | `engines/director/` | eventos + estilo + duración → `ShotPlan` (reglas o LLM) | Events, Camera, AIProvider |
| **Timeline / Project** | `core/` | modelo del proyecto: clips, pistas, config, persistencia | — |
| **Video Engine** | `engines/video/` | pipeline FFmpeg: trim, crop 9:16, reframe, rampas, transiciones, concat, NVENC | FFmpeg, Timeline |
| **Audio Engine** | `engines/audio/` | música/SFX, ducking, mezcla de volúmenes | FFmpeg |
| **AI Editor** | `engines/director/editor.py` | lenguaje natural → operaciones sobre el Timeline (MVP 4+) | AIProvider, Timeline |
| **Content Generator** | `engines/content/` | título/descripción/hashtags/hook con personalidades (MVP 4) | AIProvider |
| **Project Manager** | `core/project.py` + `utils/` | carpetas de proyecto, cachés, configuración, secretos | keyring |
| **UI** | `app/` | pantallas: Dashboard, New Project, Event Timeline, Director, Editor, Export | PySide6, todos |

## 3. Modelos de dominio (Pydantic — contrato entre módulos)

```python
# core/models.py

class DriverInfo(BaseModel):
    car_idx: int; car_number: str; name: str; team: str | None
    irating: int | None; car_class: str | None; car_name: str | None

class SessionInfo(BaseModel):
    session_num: int; session_type: str          # 'Race', 'Qualify'...
    track_name: str; track_display: str | None
    duration_s: float | None; laps_total: int | None
    drivers: list[DriverInfo]; start_utc: datetime | None

class LapRecord(BaseModel):
    driver_id: int; lap: int; time_s: float; valid: bool

class Event(BaseModel):
    id: str
    type: EventType                              # overtake, off_track, spin,
                                                 # battle, fast_lap, contact,
                                                 # close_call, position_change,
                                                 # start, finish, pit_stop
    start_s: float; end_s: float                 # ReplaySessionTime
    drivers: list[int]                           # car_idx implicados
    target: int | None                           # car_idx principal
    lap: int | None; position: int | None
    importance: float                            # 0..1
    metadata: dict[str, Any]                     # gaps, velocidades, superficie...

class SessionModel(BaseModel):                   # resultado del scan (cacheado)
    session: SessionInfo
    laps: list[LapRecord]
    events: list[Event]
    sample_rate_hz: int
    source: str                                  # hash de la replay + build

class CameraSpec(BaseModel):
    group: int; number: int = 0
    target: int | None                           # car_idx o None (estática)
    group_name: str = ""                         # informativo (cockpit, TV1...)

class Shot(BaseModel):
    id: str
    source_start_s: float; source_end_s: float   # en tiempo de sesión
    camera: CameraSpec
    transition: Transition = Transition.CUT
    speed: SpeedCurve = ...                      # rampa de velocidad (MVP 2+)
    reframe: ReframeSpec | None                  # ventana 9:16 (MVP 2+)
    caption: str | None                          # overlay de texto (MVP 3+)

class ShotPlan(BaseModel):
    shots: list[Shot]
    style: StylePreset
    hero_driver: int | None
    notes: list[str]                             # lo que la IA decidió y por qué

class Timeline(BaseModel):
    shots: list[Shot]                            # orden final editable
    audio_track: AudioTrack | None
    overlays: list[Overlay]

class ProjectConfig(BaseModel):
    name: str; replay_path: Path
    format: ExportFormat; fps: int = 60
    style: StylePreset; target_duration_s: int = 20
    ai_enabled: bool = True
    project_dir: Path                            # Projects/<nombre>/

class RenderJob(BaseModel):
    project: Path; output: Path
    resolution: tuple[int, int]; fps: int
    codec: str; bitrate_kbps: int
    include_audio: bool; include_captions: bool
```

## 4. Interfaces abstractas (dependencia invertida)

```python
# engines/replay/base.py
class ReplayController(ABC):
    def connect(self) -> bool: ...
    def session_info(self) -> SessionInfo: ...
    def read(self) -> dict[str, Any]: ...            # snapshot vars
    def seek_session_time(self, session: int, ms: int) -> None: ...
    def set_camera(self, spec: CameraSpec) -> None: ...
    def play(self, speed: float = 1.0, slow_motion: bool = False) -> None: ...
    def pause(self) -> None: ...
    def verify(self) -> CameraState: ...             # CamCarIdx/Group/ReplaySessionTime

# services/capture/base.py
class CaptureBackend(ABC):
    def start(self, target: Path) -> None: ...
    def stop(self) -> Path | None: ...
    def supports_audio(self) -> bool: ...

# ai/provider.py
class AIProvider(ABC):
    def chat_json(self, messages: list[Message], schema: type[T]) -> T: ...
    def chat_text(self, messages: list[Message]) -> str: ...
```

Regla transversal: **nada fuera de `engines/replay` habla con pyirsdk;
nada fuera de `engines/video|audio` habla con FFmpeg; nada fuera de `ai/`
habla con un LLM.** Cada subsistema se sustituye sin tocar al resto.

## 5. Flujo del shot plan (IA con fallback determinista)

1. `Director.build_plan(session, events, style, duration, hero)` →
   - sin IA: heurística event-driven (anticipación 3 s, corte mínimo 4 s,
     relleno con planos de variedad hasta la duración objetivo);
   - con IA: prompt con eventos JSON compacto (solo los top-N por importance,
     con sus campos mínimos) → `ShotPlan` validado por Pydantic; si el schema
     falla → reintento una vez → fallback determinista.
2. El plan se cachea por `hash(events + style + duration + hero)`.
3. El plan se convierte en comandos de captura ordenados por tiempo.

## 6. Estructura de carpetas

```
iRacing-AI-Cinematic-Studio/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/
│   ├── 01-analisis-tecnico.md
│   └── 02-arquitectura.md            ← este documento
├── app/                              # UI PySide6 (MVP 1+)
│   ├── main.py
│   ├── screens/                      # dashboard, new_project, analyze,
│   │                                 # events, director, editor, export
│   └── theme/                        # QSS oscuro + acento configurable
├── core/                             # modelos de dominio y timeline
│   ├── __init__.py
│   ├── models.py
│   ├── project.py                    # Project Manager
│   └── timeline.py
├── engines/
│   ├── __init__.py
│   ├── replay/
│   │   ├── base.py                   # ReplayController (ABC)
│   │   └── sdk_controller.py         # impl pyirsdk (MVP 1)
│   ├── analyzer/
│   │   ├── scanner.py                # scan → SessionModel + caché
│   │   └── events/
│   │       ├── base.py               # EventDetector (ABC)
│   │       ├── overtake.py  off_track.py  spin.py  battle.py
│   │       ├── fast_lap.py  start_finish.py  pit_stop.py
│   │       └── importance.py         # scoring y ranking
│   ├── camera/
│   │   ├── catalog.py                # grupos desde CameraInfo
│   │   ├── shot_library.py           # TRACKING/STATIC/LOW/HIGH/...
│   │   └── presets.py                # cámaras guardadas por usuario
│   ├── director/
│   │   ├── base.py                   # Director (ABC)
│   │   ├── rules.py                  # director determinista
│   │   ├── ai_director.py            # director LLM
│   │   ├── styles.py                 # CINEMATIC/HYPE/BROADCAST/AESTHETIC/STORY
│   │   └── editor.py                 # AI Editor (MVP 4+)
│   ├── video/
│   │   ├── ffmpeg.py                 # wrapper subprocess
│   │   ├── pipeline.py               # trim/concat/crop/rampas/xfade
│   │   ├── reframe.py                # tracking 9:16 (MVP 2)
│   │   └── export.py                 # RenderJob → MP4 (NVENC)
│   ├── audio/
│   │   ├── mixer.py                  # ducking, volúmenes
│   │   └── library.py                # SFX/música local
│   └── content/
│       ├── generator.py              # título/caption/hashtags (MVP 4)
│       └── personalities.py
├── ai/
│   ├── __init__.py
│   ├── provider.py                   # AIProvider (ABC) + OpenAI-compat
│   ├── schemas.py                    # contratos JSON de la IA
│   └── prompts/
├── services/
│   ├── __init__.py
│   ├── capture/
│   │   ├── base.py                   # CaptureBackend (ABC)
│   │   ├── native.py                 # video_capture broadcast
│   │   └── obs.py                    # obs-websocket
│   └── ffmpeg.py                     # localización/versión FFmpeg
├── utils/
│   ├── __init__.py
│   ├── config.py                     # configuración global
│   ├── cache.py                      # cachés (análisis, IA, thumbnails)
│   └── secrets.py                    # keyring
├── resources/
│   ├── sfx/  music/  overlays/  fonts/
├── tests/
│   └── ...                           # pytest por módulo
└── Projects/                         # (gitignored) un dir por proyecto
    └── Spa Porsche/
        ├── project.json
        ├── analysis/<hash>.json
        ├── captures/
        ├── renders/
        └── assets/
```

## 7. Principios de implementación

1. **Interfaces primero**: cada módulo expone un ABC o modelo Pydantic; la
   implementación concreta se sustituye sin romper a los demás.
2. **Caché por hash**: análisis (hash de replay+build), decisiones de IA (hash de
   entrada+estilo), thumbnails. Nunca se re-trabaja lo ya pagado.
3. **Verificar cada comando al sim**: tras seek/cámara, leer y confirmar estado
   antes de continuar; reintento acotado y error claro si el sim no responde.
4. **La IA decide, el software ejecuta**: el LLM nunca controla el sim ni FFmpeg;
   solo produce JSON validado.
5. **Degradación elegante**: sin API key el producto sigue funcionando (director
   de reglas); sin FFmpeg no exporta pero edita; sin replay abierta, solo navega
   proyectos guardados.
6. **Incremental**: un cambio pequeño por commit (estilo de trabajo del usuario
   en iRvc), commits en español.
