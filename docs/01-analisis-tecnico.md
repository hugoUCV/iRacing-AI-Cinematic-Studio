# ANÁLISIS TÉCNICO — iRacing AI Cinematic Studio

> Fase 0 del proyecto. Documento de decisiones, basado en verificación directa del
> código fuente de `kutu/pyirsdk` (SDK oficial de iRacing para Python) y de los
> proyectos existentes que resuelven partes del problema.
> Nada de lo que aquí se afirma sobre iRacing es inventado: cada capacidad crítica
> fue confirmada en el código del SDK (números de línea incluidos).

---

## 0. Resumen ejecutivo

**El producto es viable**, con un matiz arquitectónico fundamental que define todo:

> **El vídeo no se re-renderiza desde los datos de la replay. El motor gráfico de
> iRacing ES el renderer.** Nuestra aplicación dirige el reproductor de replays de
> iRacing a distancia (seek + cámara + velocidad), captura lo que iRacing dibuja, y
> después hace el montaje cinematográfico con FFmpeg.

Esto es exactamente lo que hacen los broadcasters reales de iRacing y las
herramientas de highlight existentes. Un `.rpy` **no contiene** el mundo 3D
(mallas, texturas, iluminación), así que "renderizar desde datos" exigiría
reconstruir un simulador entero — inviable. La captura guiada nos da calidad
cinematográfica real (el motor gráfico de iRacing) a cambio de que la captura
transcurre en tiempo real.

**Tres piezas independientes:**

1. **Análisis** — el replay se "escanea" (el SDK lee la memoria compartida del sim
   mientras la replay avanza) y produce un modelo JSON de sesión + eventos.
2. **Dirección** — la IA (o reglas deterministas) convierte eventos en un *shot
   plan*: lista ordenada de planos con cámara, coche y tiempos.
3. **Captura + post** — la app ejecuta el shot plan contra el replay (seek →
   cambiar cámara → grabar con la captura integrada de iRacing o OBS) y FFmpeg
   monta, recorta a 9:16, aplica rampas y exporta.

---

## 1. Realidad técnica de iRacing (lo que existe y lo que no)

### 1.1 El formato `.rpy` (replay)

- Es un **contenedor binario propietario**, no documentado, cuyo layout cambia
  entre builds de iRacing.
- Estado del ecosistema de parsing directo en 2026:
  - `hernancerm/iRacingReplayOverlay` (el parser más completo que existió) →
    **repo eliminado** (404 en la API de GitHub).
  - `vipoo/iRacingReplayOverlay.net` (C#) → último push **enero 2023**, abandonado.
  - No existe un parser Python mantenido.
- **Decisión:** no parsear `.rpy` directamente. El análisis se hace vía SDK con el
  replay abierto en el sim — el mismo camino que usan iSpeed y el Sequence
  Director desde hace años. Ventaja extra: el SDK es estable entre builds; el
  `.rpy` no.

**Consecuencia UX:** "Importar replay" = el usuario abre la replay en iRacing
(no hay comando SDK para abrir archivos) y la app se conecta al sim y lee la
sesión desde la memoria compartida. El flujo lo guía la app paso a paso.

### 1.2 El SDK (IRSDK) — superficie de control verificada

Fuente: `pyirsdk/irsdk.py` (kutu, implementación oficial MIT) y su `vars.txt`.

**Lectura (memoria compartida `Local\IRSDKMemMapFileName`, 60 Hz):**

| Variable | Uso en el producto |
|---|---|
| `ReplaySessionTime` | timestamp maestro de cada evento/shot |
| `ReplayFrameNum`, `ReplayFrameNumEnd` | frame exacto (60/s) y fin de cinta |
| `ReplayPlaySpeed`, `IsReplayPlaying` | confirmar velocidad/estado tras cada comando |
| `CarIdxPosition`, `CarIdxLapDistPct` | adelantamientos, orden en pista |
| `CarIdxTrackSurface` / `...Material` | **salidas de pista por coche** (grass/gravel) |
| `CarIdxF2Time`, `CarIdxEstTime` | batallas, gaps, presión |
| `CarIdxOnPitRoad` | pit stops |
| `CamCarIdx`, `CamGroupNumber`, `CamCameraNumber` | cámara activa (verificación de comandos) |
| `WeekendInfo`, `SessionInfo`, `CameraInfo`, `DriverInfo` (YAML) | metadatos, pilotos, grupos de cámara |

**Control (mensajes broadcast, verificado en `irsdk.py`):**

| Broadcast | Línea | Uso |
|---|---|---|
| `cam_switch_num(car, group, camera)` | 506 | cambiar cámara al coche X |
| `cam_switch_pos(pos, group, camera)` | 503 | cámara al líder/posición |
| `cam_set_state(CameraState.*)` | 509 | **ocultar UI** (`ui_hidden`), activar cam tool |
| `replay_search_session_time(session, ms)` | 545 | **seek exacto por tiempo de sesión** ← el evento/shot |
| `replay_set_play_speed(speed, slow_motion)` | 512 | play/pausa/slow-motion |
| `replay_search(RpySrchMode.*)` | 518 | saltar a start/end/incidente/lap/vuelta |
| `video_capture(VideoCaptureMode.*)` | 548 | **iniciar/parar la captura de vídeo integrada de iRacing** |
| `chat_command(...)` | 530 | macros de chat (marginal) |

**Hallazgos clave:**

1. `replay_search_session_time` permite posicionar la replay **por tiempo de
   sesión**, que es exactamente la unidad de nuestros eventos (timestamps). No
   necesitamos traducir tiempos ↔ frames a mano.
2. `video_capture` (start/end) permite usar la **captura de vídeo nativa de
   iRacing** (codificador hardware: NVENC/AMF/QSV configurado en las opciones del
   sim) sin depender de OBS. El equipo del usuario (RTX 3060 Ti) tiene NVENC.
3. `ui_hidden` permite grabar sin overlays del sim. También existe
   `use_auto_shot_selection` para delegar el encuadre a iRacing si interesa.
4. `RpySrchMode.prev_incident/next_incident` confirma que **iRacing indexa los
   incidentes** dentro de la replay — utilizable como detector secundario.

### 1.3 Cámaras

- Los grupos de cámara se leen en runtime de `CameraInfo.Groups` (cockpit, chase,
  far chase, TV1-3, TV cockpit, TV track, blimp, chopper, gyro, y los grupos
  personalizados que el usuario cree). Nada se hardcodea.
- **Se puede:** seleccionar grupo + número + coche objetivo.
- **No se puede:** crear, mover o cambiar FOV de cámaras por SDK. Las cámaras
  estáticas personalizadas se crean en el editor de iRacing (Ctrl+F12), se guardan
  por pista y **sí son seleccionables** vía `cam_switch` (aparecen como grupos
  extra).
- **Estrategia adoptada:** la cámara base siempre es una cámara real de iRacing
  (o una estática del usuario); todo el movimiento cinematográfico (push-ins,
  pan, zoom, reencuadre vertical) se hace **digitalmente en post** con FFmpeg.
  Esto resuelve a la vez la carencia de "cámara libre" y el formato 9:16.

### 1.4 Captura

| Backend | Control | Audio | Dependencias |
|---|---|---|---|
| **Nativo iRacing** (`video_capture`) | SDK | por verificar (spike) | ninguna (solo activar "captura de vídeo" en el sim) |
| **OBS** (obs-websocket, integrado en OBS 28+) | WebSocket | sí (audio de escritorio) | OBS instalado |
| FFmpeg gdigrab | subprocess | no (solo vídeo) | FFmpeg |

Recomendación: interfaz `CaptureBackend` con implementación nativa como primaria
y OBS como alternativa con audio.

### 1.5 Limitaciones que la arquitectura respeta

| Característica de la spec | Estado | Nota |
|---|---|---|
| Importar replay y analizarla | ✅ | requiere replay abierta en iRacing (no hay apertura por SDK) |
| Detectar salidas, trompos, batallas, adelantamientos | ✅ | telemetría `CarIdx*` durante el scan |
| Contactos/accidentes | ⚠️ heurística | golpe = velocidad relativa + `CarIdxTrackSurface` + marcadores de incidente; no hay feed directo |
| "Close calls" | ⚠️ heurística | distancia coche-coche < umbral sin incidente |
| Cámaras libres / mover cámara / FOV por SDK | ❌ | se sustituye por cámaras iRacing + movimiento digital en post |
| Click en evento → saltar ahí | ✅ | `replay_search_session_time` (solo con replay abierta) |
| 9:16 desde 16:9 | ✅ | crop + tracking de visión (MVP 2) o crop centrado (MVP 1) |
| Speed ramps | ✅ | `setpts` en FFmpeg (mejor que el slow-motion del sim: permite rampas continuas) |
| Música/SFX/ducking | ✅ | FFmpeg `sidechaincompress`; biblioteca local |
| Transcribir radio | ❌ | la replay no contiene el audio de radio/spotter del driver → los textos de pantalla los genera la IA desde los eventos |
| Formato de export vertical 60 fps | ✅ | FFmpeg + NVENC |

---

## 2. Decisiones de arquitectura

### 2.1 Pipeline en dos fases

```
FASE A — ANÁLISIS (offline, cacheada)        FASE B — CAPTURA GUIADA (tiempo real)
replay abierta en iRacing                     shot plan ordenado por tiempo
        │                                             │
app → replay_set_play_speed(alto)             para cada shot:
app → samplea shared memory 60 Hz             · replay_search_session_time(t_in)
        │                                     · cam_switch_num(coche, grupo, cam)
        ▼                                     · play → video_capture(start)
SessionModel JSON + eventos                    · ... video_capture(stop)
(cacheado por hash de la replay)                       │
                                               capturas por shot
                                                       │
                                        FASE C — POST (FFmpeg)
                                        trim → rampas → crop 9:16 → concat
                                        → audio → overlays → NVENC → MP4 final
```

Por qué: (1) el análisis y la captura tienen requisitos distintos (el primero
quiere velocidad, el segundo fidelidad); (2) el análisis se cachea y se reutiliza
para todos los estilos/duraciones; (3) la captura solo graba los tramos elegidos,
no toda la carrera — una carrera de 40 min genera ~30-60 s de material.

### 2.2 Análisis de sesión: escaneo del replay

- La app manda la replay a velocidad alta (o avanza por laps/frames) mientras
  samplea la memoria compartida. Una carrera de 40 min a 8-16x se escanea en
  ~2-5 min reales. Resultado cacheado → solo se paga una vez por replay.
- **Supuesto crítico a validar en el Spike 1:** durante la reproducción de una
  replay, los arrays `CarIdx*` contienen datos de **todos** los coches (es lo que
  asumen los overlays y el Sequence Director; si en algún build solo poblase el
  coche enfocado, el scan debería alternar el coche cámara). Riesgo mitigable,
  no bloqueante.
- Las replays multi-sesión (practice+qualy+race) se tratan con
  `ReplaySessionNum`; el análisis por defecto apunta a la sesión de carrera.

### 2.3 Captura guiada

- El shot plan llega ordenado por tiempo; la app ejecuta seeks secuenciales (los
  saltos hacia atrás solo ocurren entre shots, nunca dentro de una toma).
- Cada shot es un archivo (o una toma continua con cambios de cámara programados,
  modo "one-pass" — MVP 2). El modo por-shot es más robusto para el MVP 1.
- La velocidad de reproducción durante la captura es 1x (el slow-motion se aplica
  en post con `setpts`, lo que permite **rampas suaves** que el sim no puede).
- Verificación de cada comando: tras `cam_switch`/`replay_search`, la app lee
  `CamCarIdx`/`CamGroupNumber`/`ReplaySessionTime` y reintenta si no coinciden.

### 2.4 Post-proceso: FFmpeg como motor de render

- `trim`/`concat` (montaje), `crop` + `scale` (9:16), `setpts` (rampas), `xfade`
  (transiciones), `sidechaincompress` (ducking), overlays `drawtext`/PNG,
  encode `h264_nvenc`/`hevc_nvenc`.
- **Auto-reframe (MVP 2):** tracking de visión (YOLO/OpenCV) sobre el material
  16:9 → la ventana vertical sigue al coche protagonista con suavizado. Tenemos
  una ventaja única: la telemetría nos dice qué coche es el protagonista de cada
  shot (sin ambigüedad de detección) y el timestamp frame-a-frame.

### 2.5 IA: desacoplada, datos estructurados, decisiones JSON

- Interfaz `AIProvider` (ABC) con una única implementación *OpenAI-compatible*
  que cubre: OpenAI, Gemini (endpoint compat), Pollinations (gratis, ya usado en
  el proyecto de liveries) y cualquier local (Ollama expone `/v1`).
- Entradas: JSON compacto de eventos + contexto del shot plan. Salidas: JSON con
  schema estricto (Pydantic) — la IA **decide**, el software **ejecuta**.
- Fallback determinista (reglas event-driven, como el Auto Director del Sequence
  Director) → el producto funciona sin API key; la IA solo lo mejora.
- Caché de decisiones por hash (eventos + estilo + parámetros).
- Claves API en Windows Credential Manager vía `keyring` (nunca en disco plano).

### 2.6 GUI: PySide6

- Widget toolkit nativo, maduro para editores (timeline custom con
  `QGraphicsScene`, preview de vídeo con QtMultimedia, tema oscuro DaVinci-like
  con color de acento configurable). Misma base Python que el resto del stack.

---

## 3. Tecnologías

| Pieza | Elección | Por qué |
|---|---|---|
| Lenguaje / entorno | **Python 3.11+ con uv** | `pyirsdk` es Python; uv ya está instalado y es el estándar del usuario (lo usó en el proyecto de liveries) |
| Telemetría y control del sim | **pyirsdk** (kutu) | SDK oficial, MIT, 388★, API completa verificada línea a línea |
| UI | **PySide6** (Qt 6) | editor tipo timeline + preview + tema oscuro; alternativa web (Tauri/Electron) descartada: el control del sim es un proceso local Windows y Python lo integra nativamente |
| Captura | **Nativo iRacing (broadcast) + OBS/obs-websocket** | nativo = cero dependencias y calidad NVENC; OBS = audio + overlays; ambos tras `CaptureBackend` |
| Montaje y render | **FFmpeg** (subprocess) | todo el post en un solo motor: trim, concat, crop, xfade, setpts, ducking, NVENC; sin reinventar editores |
| Visión (MVP 2) | **OpenCV + YOLO (ONNX)** | tracking del coche para auto-reframe |
| Modelos de dominio | **Pydantic v2** | validación + serialización de SessionModel/Event/Shot/ShotPlan; misma lingua para caché y para la IA |
| IA | **httpx** (o SDK OpenAI) contra endpoints OpenAI-compat | un provider, todos los backends (OpenAI/Gemini/Pollinations/Ollama) |
| Secretos | **keyring** (Windows Credential Manager) | "la clave nunca almacenada de forma insegura" |
| Persistencia | **carpeta de proyecto + JSON cacheado** | spec §24/§28; SQLite solo si el scan crece demasiado |
| Tests/lint | pytest + ruff | disciplina desde el MVP 0 |

---

## 4. Proyectos existentes estudiados (ideas, no forks)

| Proyecto | Lo que valida | Lo que NO copiamos |
|---|---|---|
| `pwillia7/iRacingReplays` (Sequence Director, C#) | scan de replay → eventos (battles gap<2%, overtakes por posición, incidentes) → plan de cámaras con anticipación 3 s → reproducir/grabar; **modo LLM opcional** | C#, GUI WinForms, edición por nodos manuales; sin post/FFmpeg/9:16 |
| `yvon/iracing-replay-capture` (C#) | comandar replay (playhead+cámaras) + grabar un archivo por cámara vía OBS websocket | CLI C# de 2021; sin análisis ni IA |
| `MerlinCooper/iRacingReplayDirector` | captura completa + encode automático con FFmpeg y highlights | flujo de captura por hotkey (Alt-F9), sin shot plan fino |
| `ellettie/iracing-mcp-server` | el catálogo completo de control vía `pyirsdk` (cámaras, replay, pits) accesible a IA | es un servidor MCP genérico, no un producto de vídeo |
| `kutu/pyirsdk` | dependencia directa (SDK) | — |
| Overlays suites (halvar20000, simracing-hub) | la telemetría funciona durante replays (badge LIVE/REPLAY, detection de incidentes/overtakes en vivo) | — |

**Conclusión honesta:** el pipeline "scan → eventos → plan de cámaras → captura"
está demostrado por terceros. Ninguno existente hace lo que la spec pide en su
conjunto: **análisis completo + dirección por IA con estilos + montaje en timeline
+ post cinematográfico (9:16, rampas, audio, texto) + generación de contenido**.
Ahí está el producto.

---

## 5. Plan de MVP

### MVP 0 (esta entrega)
Documentos de análisis y arquitectura + esqueleto del repo con las interfaces
definidas. Criterio: `pytest` en verde y modelos Pydantic importables.

### MVP 1 — "Replay → TikTok vertical automático" (sin IA obligatoria)
1. Conectar con replay abierta (validación de sesión).
2. Escanear sesión → `SessionModel` cacheado.
3. Eventos básicos: salida, trompo, adelantamiento (cambio de `CarIdxPosition`),
   batalla (gap < umbral sostenido), vueltas rápidas, start/finish.
4. Elegir piloto protagonista.
5. Shot plan determinista (reglas event-driven con anticipación).
6. Captura guiada por-shot (seek → cámara → play → stop).
7. Timeline básico (ver/ordenar/recortar shots).
8. Export 1080×1920 60 fps NVENC (crop centrado) con FFmpeg.
9. (Opcional) ranking de momentos por IA y shot plan LLM si hay API key.

Criterio de aceptación: con la replay abierta y dos clics (elegir piloto y
generar), obtener un MP4 vertical de 15-30 s con 4-8 planos.

### MVP 2
AI Director completo (estilos CINEMATIC/HYPE/BROADCAST/AESTHETIC/STORY),
auto-reframe con tracking por visión, auto-cut, speed ramps, captura one-pass.

### MVP 3
Editor completo: transiciones, música/SFX con ducking y nivel de intensidad,
overlays minimalistas (LAP/POS/delta), biblioteca de planos, cámaras guardadas.

### MVP 4
AI Content Generator (título/descripción/hashtags/hook con personalidades),
textos en pantalla sincronizados, subtítulos.

### V5
Copiloto conversacional (chat que edita el proyecto), presets avanzados,
generación one-click de principio a fin.

---

## 6. Riesgos y spikes (antes de construir encima)

| # | Spike | Qué valida | Bloquea si falla |
|---|---|---|---|
| S1 | Scan: ¿`CarIdx*` trae **todos** los coches durante la replay? | análisis multi-coche | solo el diseño del scan (hay plan B: alternar cámara) |
| S2 | `video_capture` nativo: ¿archivo de salida, códecs, incluye audio, carpeta? | backend de captura sin OBS | captura (plan B: OBS) |
| S3 | Precisión y latencia de `replay_search_session_time` ± y velocidad máxima de scan | tiempos de corte exactos | márgenes de anticipación |
| S4 | `cam_switch_num` a grupos personalizados (cámaras estáticas del usuario) | uso de cámaras del usuario | catálogo de planos (plan B: solo grupos nativos) |

Riesgos globales:

- **Cambios de build de iRacing**: el análisis depende del SDK (estable), no del
  `.rpy` → exposición mínima. El único contrato frágil es la lista de variables,
  mitigada por revalidación en `startup()`.
- **Captura en tiempo real**: generar un vídeo cuesta ~la duración del material
  elegido. Mitigación: solo se captura lo seleccionado (30-60 s) y el scan se
  cachea. En V5 se puede paralelizar (cola de captura en segundo plano).
- **Audio en captura nativa** (si no lo incluye): MVP 1 exporta vídeo sin audio
  (el audio entra en MVP 3, que ya incorpora el backend OBS). Aceptable según el
  orden de MVP definido en la spec.
- **iRacing ToS**: la aplicación solo lee el SDK público y captura pantalla —
  el mismo patrón que OBS/overlays existentes. Sin inyección, sin lectura de
  memoria de procesos ajenos al contrato público del SDK.
