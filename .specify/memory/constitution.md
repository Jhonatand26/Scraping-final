<!--
SYNC IMPACT REPORT
==================
Version change:      N/A → 1.0.0 (initial ratification from blank template)
Modified principles: None — first-time population
Added sections:
  - Core Principles (I – V)
  - Technical Constraints & Security
  - Development Workflow — Phased Implementation
  - Governance
Removed sections:    None
Templates reviewed:
  - .specify/templates/plan-template.md  ✅ no updates needed (Constitution Check
    gate is a per-feature placeholder; generic phrasing remains valid)
  - .specify/templates/spec-template.md  ✅ no updates needed
  - .specify/templates/tasks-template.md ✅ no updates needed
  - .specify/templates/commands/         ✅ no command files present in directory
  - README.md                            ⚠ currently a single-line stub;
    recommend expanding with project overview once Fase 1 is stable
Deferred TODOs:      None — all placeholders resolved
-->

# Agente OS RAG — Fundación Valle del Lili: Constitution

## Core Principles

### I. Desacoplamiento de Procesos Pesados (Decoupled Ingestion)

El proceso de webscraping masivo de datos institucionales es un paso previo y
completamente independiente de la inicialización del OS agéntico.

- Ningún agente o servicio del sistema operativo en producción DEBE ejecutar
  raspados pesados en su bucle principal.
- El scraper DEBE generar archivos locales estáticos (`.md` con YAML front-matter
  en `./data/scraped_docs`) antes del despliegue del pipeline RAG.
- La fase de datos es offline; su salida es la entrada inmutable para las fases
  de ingesta y chunking. Las dos fases no deben solaparse en tiempo de ejecución.

### II. Compatibilidad Multiplataforma Omnipresente (Cross-Platform Execution)

Toda lógica de automatización, scripts e instalaciones DEBE ejecutarse de forma
idéntica en Windows (CMD/PowerShell), Linux y macOS.

- Se PROHÍBE el uso de comandos de consola nativos que causen fallos de
  portabilidad entre sistemas operativos (e.g., `mkdir`, `cp`, `rm` en bash
  o sus equivalentes de PowerShell como lógica principal de automatización).
- La lógica de sistema (creación de carpetas, copiado de archivos, validación de
  rutas) DEBE delegarse a scripts en Python, invocados mediante `uv run`.
- Todo punto de entrada al proyecto DEBE funcionar sin modificación en los tres
  sistemas operativos objetivo. Se validará en CI con runners de cada plataforma.

### III. Aislamiento Semántico Estricto (Semantic Separation)

La seguridad de los datos se rige por el aislamiento estricto de namespaces de
memoria semántica. La contaminación de contextos está prohibida.

- El Bot Público SOLO TIENE autorización de lectura sobre el espacio
  `public_institutional.*`. Cualquier otro acceso está prohibido por código y
  configuración de manifiesto.
- El Bot Interno ES EL ÚNICO autorizado para leer concurrentemente
  `public_institutional.*` e `internal_regulatory.*`.
- Toda verificación de permisos de namespace DEBE ser auditada en PR antes de
  merge. Un test de aislamiento automatizado DEBE ejecutarse en Fase 7.

### IV. Puerta de Calidad Human-in-the-Loop (HITL Guardrail)

Ninguna información extraída autónomamente por la Hand recolectora puede ser
indexada en la memoria semántica del Bot Interno de forma directa.

- ES OBLIGATORIO un paso de aprobación manual interactivo en Telegram donde un
  administrador valide la estructura del reporte antes de disparar la
  persistencia.
- La persistencia DEBE realizarse exclusivamente mediante la API REST de OpenFang
  (`PUT /api/memory/agents/{id}/kv`) una vez emitida la aprobación del
  administrador en el chat.
- Este guardrail NO PUEDE ser deshabilitado, omitido ni cortocircuitado en ningún
  entorno de producción. Cualquier bypass constituye una violación crítica.

### V. Gestión Predictible de Entornos con uv (Deterministic Environments)

Se descarta el uso de `requirements.txt` y comandos `pip` tradicionales. El
entorno de Python DEBE ser reproducible de forma exacta y ultra-rápida.

- El entorno virtual DEBE gestionarse exclusivamente con `uv` mediante un archivo
  `pyproject.toml` declarativo que declara todas las dependencias y sus versiones.
- Todo script DEBE invocarse multiplataformamente a través de `uv run`,
  garantizando que las dependencias estén resueltas en su versión exacta antes
  de la ejecución.
- La incorporación de nuevas dependencias DEBE realizarse mediante
  `uv add <paquete>`. Se PROHÍBE la edición manual del lockfile o la instalación
  directa con `pip install`.

## Technical Constraints & Security

- **Resolución Dinámica de Rutas**: Toda ruta a recursos locales (carpetas de
  Markdown, manifiestos de agentes, scripts) DEBE calcularse de manera dinámica
  y absoluta en tiempo de ejecución por Python, usando `Path(__file__).resolve()`
  como anclaje desde la raíz del repositorio clonado. Se PROHÍBE el uso de rutas
  absolutas hardcodeadas que asuman una ubicación específica del clon local, para
  evitar conflictos con las rutas globales del daemon de OpenFang.

- **Integración por API REST**: Se PROHÍBE la manipulación directa a bajo nivel
  de la base de datos SQLite de OpenFang para inyectar vectores de embeddings.
  Toda ingesta, actualización, limpieza de namespaces y registro de agentes/hands
  DEBE realizarse exclusivamente consumiendo la API REST del daemon local
  (`http://127.0.0.1:4200`) mediante peticiones autenticadas con la cabecera
  `Authorization: Bearer <token>`.

- **Control de Acceso del Bot Interno**: El Bot Interno NO DEBE responder bajo
  ninguna circunstancia a mensajes directos (DMs) de usuarios de Telegram. Su
  ámbito de respuesta ESTÁ RESTRINGIDO por código y configuración de canal al
  identificador único del Grupo Privado de la fundación, referenciado por la
  variable de entorno `TELEGRAM_INTERNAL_GROUP_ID`. Esta restricción DEBE ser
  validada como parte de las pruebas de Fase 7.

## Development Workflow — Phased Implementation

El orden secuencial de desarrollo DEBE seguirse estrictamente. Ninguna fase puede
iniciarse antes de que la precedente esté completada y validada.

1. **Fase 1 — Datos (Offline)**: Ejecutar `make scrape`
   (`uv run python src/scraper.py`) para consolidar los archivos `.md`
   estructurados con YAML front-matter en `./data/scraped_docs`.

2. **Fase 2 — Entorno e Inyección**: Ejecutar `uv sync` y
   `uv run python configure_env.py` para sincronizar las credenciales del
   `.env` local con el `config.toml` global de OpenFang, incluyendo la
   redundancia OpenAI + Fallback Ollama.

3. **Fase 3 — Ingesta y Chunking RAG**: Implementar `ingest_docs.py` aplicando
   limpieza semántica (eliminar bloques de enlaces finales en sedes/servicios,
   omitir listas masivas de médicos en servicios), segmentar según encabezados de
   Markdown e inyectar mediante `PUT /api/memory/agents/{id}/kv` bajo el
   namespace `public_institutional.*`.

4. **Fase 4 — Despliegue de Canal Público**: Configurar el bot general a través
   del manifiesto `public_agent.toml`, limitando sus herramientas a
   `memory_recall` y sus permisos estrictamente al espacio
   `public_institutional.*`.

5. **Fase 5 — Desarrollo de la Hand con HITL**: Crear la Hand recolectora
   (`HAND.toml` y `SKILL.md`) con scraping visual resiliente (no dependiente de
   selectores rígidos) e implementar el flujo de aprobación interactiva en
   Telegram según el Principio IV.

6. **Fase 6 — Despliegue de Canal Interno**: Crear el bot privado restringido
   mediante `internal_agent.toml` enlazado al Grupo Privado, con permisos duales
   de lectura (`public_institutional.*` + `internal_regulatory.*`).

7. **Fase 7 — Pruebas de Integración**: Ejecutar pruebas de aislamiento de
   namespaces y control de alucinaciones en ambos bots de Telegram. Esta fase
   valida los Principios III y IV de forma end-to-end.

## Governance

- **Validación de Metadatos**: Cada archivo indexado DEBE conservar y mapear sus
  metadatos del YAML front-matter (especialmente `title`, `url` y `categorias`
  en especialistas) para enriquecer la precisión del filtro de búsqueda
  semántica. La ausencia de estos campos en un documento indexado constituye un
  defecto de calidad bloqueante.

- **No Duplicidad**: El flujo de ingesta DEBE incluir un paso previo obligatorio
  de limpieza del namespace afectado mediante la API del daemon antes de proceder
  con una nueva carga. Se PROHÍBE la ingesta sobre datos previos sin limpieza
  explícita del namespace destino.

- **Respeto al Sandbox de Permisos**: Todo PR o modificación en los manifiestos
  de los agentes DEBE ser auditado para asegurar que el Bot Público bajo ninguna
  circunstancia obtenga permisos de lectura o escritura sobre el espacio
  `internal_regulatory.*`. Esta auditoría es condición de merge.

- **Procedimiento de Enmienda**: Los cambios a esta constitución DEBEN ser
  propuestos mediante PR con justificación explícita, revisados por al menos un
  miembro del equipo y documentados actualizando `LAST_AMENDED_DATE`. La versión
  sigue semver: MAJOR para redefiniciones incompatibles de principios; MINOR para
  adición de principios o secciones; PATCH para clarificaciones y correcciones
  menores.

- **Revisión de Cumplimiento**: Todo PR que modifique manifiestos de agentes,
  scripts de ingesta o configuración de namespaces DEBE incluir una sección
  "Constitution Check" en su descripción, verificando que no viola los
  Principios I–V ni las restricciones de la sección Technical Constraints.

**Version**: 1.0.0 | **Ratified**: 2026-06-04 | **Last Amended**: 2026-06-04
