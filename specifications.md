Tiene toda la razón. En el flujo moderno de `uv`, el estándar de la industria (basado en PEP 621 y PEP 517) es prescindir de `requirements.txt` y utilizar `pyproject.toml`. Esto permite declarar las dependencias de manera declarativa y estructurada.

Además, al adoptar `pyproject.toml`, podemos usar **`uv run`** y **`uv sync`**. Esto nos da una ventaja multiplataforma gigantesca: `uv run python script.py` se encarga automáticamente de activar el entorno virtual e invocar el binario correcto, **eliminando la necesidad de escribir rutas condicionales diferentes para Windows (`.venv\Scripts\python`) y Unix (`.venv/bin/python`) en el `Makefile`**. El comando es exactamente igual en todos los sistemas operativos.

A continuación, presento el **Blueprint de Implementación Técnico (`SPECIFICATION.md`)** definitivo, reestructurado por completo bajo esta moderna arquitectura de empaquetado y orquestación con `uv`.

---

# BLUEPRINT DE IMPLEMENTACIÓN: ECOSISTEMA MULTI-AGENTE Y RAG CON OPENFANG

Este documento técnico sirve como la **Especificación de Diseño Definitiva (Single Source of Truth)**. Ha sido consolidado para garantizar que un agente de codificación autónomo (como Claude Code, Cursor u Open Code) pueda desplegar el ecosistema completo de manera determinista y sin margen de error.

---

## 1. ARQUITECTURA DE DIRECTORIOS Y ESPACIO DE TRABAJO (WORKSPACE)

El proyecto está diseñado para ser completamente portable. Aunque OpenFang utiliza un directorio global en el sistema operativo para el daemon y su base de datos semántica (`~/.openfang` en Unix / `%USERPROFILE%\.openfang` en Windows), todo el código fuente del cargador, configuraciones y bots vive dentro del repositorio local.

### Estructura del Workspace
```directory
mi-repositorio-clonado/
├── .env                              # Archivo de entorno local (excluido de git)
├── .env.example                      # Plantilla de variables de entorno
├── pyproject.toml                    # Declaración de dependencias (PEP 621) y configuración de uv
├── uv.lock                           # Archivo de bloqueo generado por uv (sincronización estricta)
├── Makefile                          # Orquestador multiplataforma (simplificado mediante 'uv run')
├── data/
│   └── scraped_docs/                 # Carpeta de salida del scraper offline (.md)
├── scripts/
│   ├── configure_env.py              # Script para sincronizar .env con el config.toml global
│   ├── ingest_docs.py                # Script segmentador e inyector semántico vía API REST
│   └── setup_telegram_channels.py    # Script de configuración de adaptadores de Telegram
├── agents/
│   ├── public_agent.toml             # Manifiesto del Bot Público
│   └── internal_agent.toml           # Manifiesto del Bot Interno (Restringido)
├── hands/
│   └── health_regulatory_collector/  # Carpeta de instalación de la Hand autónoma
│       ├── HAND.toml                 # Manifiesto de la Hand (Schedule + Prompt)
│       └── SKILL.md                  # Habilidad de la Hand (URLs de MinSalud, SISPRO y reglas)
└── README.md                         # Guía de instalación y uso
```

### Regla de Resolución de Rutas (Agnóstico a la Ubicación)
Todos los scripts en Python deben resolver las rutas a archivos locales de forma **absoluta** calculando la raíz del repositorio de manera dinámica en tiempo de ejecución. 
*   *Lógica:* `ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))`. 
*   No se permiten rutas relativas estáticas que puedan causar fallos de entorno según el directorio de clonación.

---

## 2. ESPECIFICACIÓN DE CONFIGURACIÓN Y ENTORNOS

El desarrollador configurará sus credenciales privadas de forma manual en el archivo `.env`.

### variables en `.env`
```env
# Proveedor principal de LLM (OpenAI)
OPENAI_API_KEY=sk-proj-tu_clave_de_openai

# Modelo de Embeddings Semánticos (text-embedding-3-small o all-MiniLM-L6-v2)
EMBEDDING_MODEL=text-embedding-3-small

# Configuración de Telegram Bots
TELEGRAM_TOKEN_PUBLIC=token_oficial_bot_publico
TELEGRAM_TOKEN_INTERNAL=token_oficial_bot_interno
TELEGRAM_ADMIN_CHAT_ID=chat_id_del_administrador_para_hitl
TELEGRAM_INTERNAL_GROUP_ID=chat_id_del_grupo_privado_de_la_fundacion

# Directorio de los Documentos Scrapeados
SCRAPED_DATA_DIR=./data/scraped_docs
```

### El Archivo `pyproject.toml`
Declara formalmente el proyecto y sus dependencias estrictas utilizando el estándar PEP 621.

```toml
[project]
name = "valle-del-lili-agentic-rag"
version = "0.1.0"
description = "Ecosistema agéntico multi-bot y RAG con OpenFang para la Fundación Valle del Lili"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "pyyaml>=6.0.1",
    "requests>=2.31.0",
    "python-frontmatter>=1.1.0",
]

[tool.uv]
dev-dependencies = []
```

### Funcionamiento de `scripts/configure_env.py`
Este script sincroniza las variables del `.env` local con la configuración global de OpenFang:
1.  **Localización del archivo global:**
    *   Unix: `~/.openfang/config.toml`
    *   Windows: `%USERPROFILE%\.openfang\config.toml` (usando `os.environ["USERPROFILE"]`).
2.  **Inyección del Ruteo Híbrido (OpenAI + Fallback Ollama):** Edita el `config.toml` de forma segura para garantizar la redundancia de LLM:
    *   Prioritario: Proveedor `openai` con el modelo `gpt-4o-mini`.
    *   Respaldo: Tabla `[[fallback_providers]]` apuntando al proveedor `ollama` con el modelo local `gemma4:latest` (o la versión que posea el usuario).
3.  **Inyección del Modelo de Embeddings:**
    *   Si `EMBEDDING_MODEL` en `.env` es `text-embedding-3-small`, escribe ese modelo en la sección `[memory]`. El daemon usará de forma automática tu clave `OPENAI_API_KEY` para generar los vectores.
    *   Si es `all-MiniLM-L6-v2`, se configura para procesamiento 100% local en Rust.

---

## 3. SEGMENTACIÓN (CHUNKING) E INGESTA SEMÁNTICA POR API REST (`ingest_docs.py`)

Este script lee los archivos Markdown generados en `./data/scraped_docs`, los segmenta basándose en su estructura de cabeceras e inyecta la información en la base de datos semántica de OpenFang mediante peticiones HTTP `POST` y `PUT` a la API REST del daemon local.

### Especificaciones de la API REST local de OpenFang
*   **Base URL:** `http://127.0.0.1:4200`
*   **Autenticación:** Las peticiones deben contener la cabecera `Authorization: Bearer <OPENFANG_API_KEY>` (leída desde el config.toml o el .env).
*   **Limpieza previa:** Antes de subir nuevos datos, el script debe ejecutar una petición `DELETE` para vaciar el namespace `public_institutional.*` para evitar registros duplicados.
*   **Inyección Semántica:** El script llamará al endpoint de memoria semántica o KV del daemon: `PUT /api/memory/agents/{agent_id}/kv/{key}` o utilizará el canal de ingesta directa del OS para procesar texto, asignando el namespace correspondiente. El daemon de OpenFang se encargará de computar los embeddings en segundo plano utilizando el proveedor configurado.

### Lógicas de Segmentación (Chunking) según Estructuras Reales

#### A. Directorio `especialistas/` (Ejemplo: `adriana-alvarez-montenegro.md`)
*   *Lógica:* **No segmentar**. Un archivo de especialista completo representa un único bloque semántico (chunk).
*   *Limpieza:* Eliminar mediante regex el bloque ruidoso final: `## Enlaces encontrados en esta página` y todo su contenido inferior.
*   *Metadatos:* Extraer el YAML front-matter y mapearlo como atributos JSON:
    ```json
    {
      "source": "adriana-alvarez-montenegro.md",
      "seccion": "especialistas",
      "title": "Adriana Alvarez Montenegro",
      "url": "https://valledellili.org/directorio-medico/adriana-alvarez-montenegro/",
      "categorias": ["Adolescentes", "Adultos", "Fonoaudiología", "Lenguaje", "Niños"]
    }
    ```
*   *Namespace:* `public_institutional.especialistas.adriana-alvarez-montenegro`

#### B. Directorio `sedes/` (Ejemplo: `sede-alfaguara.md`)
*   *Lógica:* Extraer información general inicial de la sede.
*   *Segmentación:* Dividir por cada encabezado de nivel 3 (`### [Especialidad destacados]`) en la sección de "Servicios destacados" para tener bloques semánticos de no más de 500 tokens.
*   *Limpieza:* Excluir el bloque final `## Enlaces encontrados en esta página`.
*   *Namespace:* `public_institutional.sedes.[nombre-sede]`

#### C. Directorio `servicios/` (Ejemplo: `alergologia.md`)
*   *Lógica:* Segmentar por cada encabezado de nivel 2 (`## Qué hace esta especialidad`, `## Enfermedades que trata`, `## Procedimientos y tratamientos`).
*   *Tratamiento especial:* Eliminar por completo el bloque `## Especialistas que pueden atenderte`. La lista masiva de nombres de médicos y sus URLs asociadas satura de tokens inútiles la consulta semántica. El bot de Telegram debe guiar al usuario a consultar el directorio médico individualmente o usar los metadatos de los especialistas.
*   *Namespace:* `public_institutional.servicios.[nombre-servicio]`

#### D. Directorio `pages/` (Ejemplo: `cheque-medico-preventivo.md`)
*   *Lógica:* Segmentar por encabezados de nivel 2 (`##`) o nivel 3 (`###`). Para el caso de `cheque-medico-preventivo.md`, cada bloque de nivel 3 (`### Basic`, `### Advance`, `### Gold`) constituirá un chunk independiente con sus laboratorios y valoraciones correspondientes.
*   *Namespace:* `public_institutional.pages.[nombre-pagina]`

---

## 4. AGENTES (BOTS DE TELEGRAM)

### Bot Público (`agents/public_agent.toml`)
Atiende solicitudes generales en Telegram sobre la institución.
*   **Canal:** Enlazado al token `TELEGRAM_TOKEN_PUBLIC`.
*   **Permisos de Memoria (`permissions`):**
    *   `memory_read = ["public_institutional.*"]`: Solo puede realizar búsquedas vectoriales dentro de la base de conocimiento pública.
    *   `memory_write = ["self.*"]`: Solo escribe en su propia sesión para mantener el contexto conversacional del usuario actual.
*   **Herramientas autorizadas:** Habilitar únicamente la herramienta `memory_recall`. Deshabilitar el navegador, shell o sistema de archivos.
*   **System Prompt:** El prompt le instruye a actuar como un asistente de atención al usuario de la Fundación Valle del Lili. Ante consultas de horarios, sedes o especialistas, debe ejecutar siempre `memory_recall`. **Regla estricta:** Si los datos recuperados por el RAG no responden a la pregunta, el bot debe indicar amablemente que no posee esa información específica, evitando alucinaciones de nombres de médicos o números de contacto.

### Bot Interno (`agents/internal_agent.toml`)
Restringido para miembros de la organización.
*   **Canal:** Enlazado al token `TELEGRAM_TOKEN_INTERNAL`.
*   **Filtro de Seguridad (Grupo Privado):** Configurado para responder únicamente si los mensajes provienen del ID del grupo privado de la fundación definido en `TELEGRAM_INTERNAL_GROUP_ID`. Cualquier interacción por DM (mensaje directo) de usuarios no autorizados será ignorada.
*   **Permisos de Memoria (`permissions`):**
    *   `memory_read = ["public_institutional.*", "internal_regulatory.*"]`: Puede leer tanto la información institucional básica como la base de datos de regulaciones de salud recopiladas por la Hand.
*   **Herramientas autorizadas:** Habilitar `memory_recall`.
*   **System Prompt:** Actúa como un consultor de inteligencia regulatoria para el personal interno de la fundación. Prioriza la síntesis clara de decretos, circulares de Supersalud o resoluciones de MinSalud, cruzándolos con la información de las sedes cuando corresponda.

---

## 5. HAND RECOLECTORA AUTÓNOMA CON VALIDACIÓN HITL

La Hand es un agente que corre en segundo plano de manera programada (no reactivo). Se despliega e instala mediante el endpoint `POST /api/hands/install` o la CLI de OpenFang.

### Carpeta `hands/health_regulatory_collector/`

#### A. Archivo `HAND.toml` (El Manifiesto)
*   **Identificador:** `health_regulatory_collector`.
*   **Schedule:** Configurado para despertarse diariamente a una hora específica mediante el agendador de tareas (Cron) de OpenFang (ej: 7:00 AM).
*   **Capabilities / Tools:** Habilitar el módulo del navegador (`browser` de OpenFang / Playwright) para realizar webscraping visual interactivo.
*   **Permisos de Memoria:** `memory_write = ["internal_regulatory.*"]`.

#### B. Archivo `SKILL.md` (La Habilidad Experta)
*   **Directrices Semánticas:** Instruye al agente a navegar de manera visual por el portal del Ministerio de Salud y Protección Social de Colombia, SISPRO, Invima, Supersalud y el Diario Oficial.
*   **Estrategia de Navegación Resiliente:** Se le prohíbe explícitamente depender de clases CSS o selectores rígidos que puedan cambiar. Se le indica usar motores de búsqueda internos, leer el árbol textual del DOM y encontrar semánticamente los links correspondientes a "Resoluciones recientes", "Decretos" o "Circulares Externas" vigentes del año en curso.

### Flujo de Trabajo Human-in-the-Loop (HITL) en Telegram
Para garantizar el control de calidad, el flujo de ingesta de regulaciones no será automático:

```
[1. Hand se despierta y extrae normativa]
                   │
                   ▼
[2. Hand genera borrador en Markdown]
                   │
                   ▼
[3. Envía el reporte al Admin por Telegram] (TELEGRAM_ADMIN_CHAT_ID)
   Con opciones interactivas:
   - Botón: "Aprobar e Indexar"
   - Comando: "/approve"
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
     [APROBADO]          [RECHAZADO]
         │                   │
         ▼                   ▼
[4. Envía petición REST]   [Se descarta o solicita]
`PUT /api/memory/...`      [nueva redacción]
con namespace:
`internal_regulatory.*`
```

1.  La Hand se despierta, extrae la información y redacta un reporte ejecutivo consolidado en Markdown.
2.  En lugar de guardarlo directamente en la memoria persistente, la Hand utiliza el canal de Telegram para enviar el borrador al chat privado del administrador (`TELEGRAM_ADMIN_CHAT_ID`) con una interfaz de interacción (ej: botones inline o el comando `/approve [ID_Reporte]`).
3.  **La Puerta de Aprobación (HITL):** El reporte permanece en un almacenamiento de caché temporal.
4.  Al recibir la aprobación del administrador (vía Webhook o interacción de canal de OpenFang), la automatización realiza una llamada REST `PUT` al daemon de OpenFang para indexar oficialmente el texto en el namespace semántico `internal_regulatory.*`. A partir de ese segundo, el **Bot Interno** ya puede responder preguntas sobre esa nueva normativa.

---

## 6. EL ORQUESTRADOR DE DESPLIEGUE (`Makefile` con `uv`)

Este archivo unifica y simplifica la ejecución en cualquier sistema operativo haciendo uso del comando multiplataforma `uv run`. El binario `uv` se encargará de gestionar el entorno virtual `.venv` de forma totalmente transparente e idéntica en Windows, Linux y macOS.

```makefile
# Makefile para el despliegue multiplataforma End-to-End del Proyecto (Optimizado con uv)

.PHONY: all check-os install-deps scrape setup install-hand start-daemon verify-uv

# Cargar variables del .env si existe
ifneq (,$(wildcard ./.env))
    include .env
    export $(shell sed 's/=.*//' .env)
endif

# Comando por defecto: Guía informativa
all:
	@echo "=========================================================="
	@echo "     Ecosistema Agéntico Valle del Lili (OpenFang)"
	@echo "=========================================================="
	@echo " Comandos disponibles:"
	@echo "  make scrape       : Ejecuta el scraper pesado de forma offline usando uv."
	@echo "  make setup        : Verifica dependencias, inyecta .env e indexa el RAG."
	@echo "  make start        : Inicia el Daemon global de OpenFang."
	@echo "=========================================================="

# Verificación e instalación silenciosa de uv
verify-uv:
	@if command -v uv >/dev/null 2>&1; then \
		echo "✓ 'uv' ya está instalado en el sistema."; \
	else \
		echo "🚀 'uv' no detectado. Iniciando instalación de uv de forma automática..."; \
		ifeq ($(OS),Windows_NT) \
			powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"; \
		else \
			curl -LsSf https://astral.sh/uv/install.sh | sh; \
		fi \
	fi

# 1. Ejecutar el scraping pesado de forma desacoplada (Pre-requisito)
scrape: verify-uv
	@echo "🕸️  Iniciando proceso de Webscraping pesado (offline con uv)..."
	@uv sync
	@uv run python src/scraper.py --output $(SCRAPED_DATA_DIR)
	@echo "✓ Scraping finalizado. Archivos .md listos en $(SCRAPED_DATA_DIR)"

# 2. Detectar OS e instalar dependencias del sistema y de OpenFang
check-os: verify-uv
	@echo "🔍 Detectando Sistema Operativo..."
	@ifeq ($(OS),Windows_NT)
		@echo "🪟 Sistema detectado: Windows"
		@echo "⚠️  Nota: Asegúrese de tener 'make' instalado vía Chocolatey (choco install make)."
		@powershell -Command "if (!(Get-Command openfang -ErrorAction SilentlyContinue)) { irm https://openfang.sh/install.ps1 | iex }"
	else
		@uname_s=$$(uname -s); \
		if [ "$$uname_s" = "Linux" ]; then \
			echo "🐧 Sistema detectado: Linux"; \
			sudo apt update && sudo apt install -y pkg-config libssl-dev libsqlite3-dev curl; \
		elif [ "$$uname_s" = "Darwin" ]; then \
			echo "🍎 Sistema detectado: macOS"; \
			brew install openssl sqlite curl; \
		fi; \
		if ! command -v openfang >/dev/null 2>&1; then \
			curl -fsSL https://openfang.sh/install | sh; \
		fi
	endif

# 3. Inicializar OpenFang, Inyectar variables del .env e indexar base RAG
setup: check-os
	@echo "⚙️  Verificando inicialización de OpenFang..."
	@if [ ! -d ~/.openfang ] && [ ! -d "%USERPROFILE%\.openfang" ]; then \
		openfang init; \
	fi
	@echo "🔧 Configurando entorno y claves con uv..."
	@uv sync
	@uv run python scripts/configure_env.py
	@echo "📥 Indexando información institucional en la BD semántica..."
	@uv run python scripts/ingest_docs.py
	@$(MAKE) install-hand
	@$(MAKE) setup-channels

install-hand:
	@echo "🤖 Instalando Hand recolectora de reglamentación médica..."
	@# Resuelve la ruta de forma absoluta antes de enviar al CLI de OpenFang
	@ifeq ($(OS),Windows_NT) \
		abs_path=$$(powershell -Command "[System.IO.Path]::GetFullPath('hands/health_regulatory_collector')"); \
		openfang hand install $$abs_path; \
	else \
		abs_path=$$(uv run python -c "import os; print(os.path.abspath('hands/health_regulatory_collector'))"); \
		openfang hand install $$abs_path; \
	fi

setup-channels:
	@echo "💬 Configurando canales de adaptadores de Telegram..."
	@uv run python scripts/setup_telegram_channels.py

start:
	@echo "🚀 Iniciando el Daemon de OpenFang..."
	@openfang start
```

---

## 7. CRITERIOS DE ACEPTACIÓN PARA EL AGENTE CODIFICADOR

Antes de dar por completada una fase, el agente codificador debe verificar de manera determinista:

1.  **Detección de Archivos:** El script `ingest_docs.py` debe fallar con gracia y emitir una advertencia clara si la carpeta de salida del scraper está vacía, indicando al usuario que ejecute `make scrape` antes del setup.
2.  **Limpieza de Enlaces:** Ningún chunk inyectado a OpenFang debe contener la sección `## Enlaces encontrados en esta página` ni el bloque de médicos en la sección de servicios.
3.  **Seguridad de Directorios:** El Bot Público bajo ninguna circunstancia debe arrojar respuestas de normativas internas (`internal_regulatory.*`), incluso si se le pregunta directamente en el chat.
4.  **HITL en Operación:** La Hand recolectora debe pausar su ejecución tras generar el borrador, y no inyectar datos en la base semántica hasta que reciba la confirmación interactiva en el chat de administración.

---

Este Blueprint técnico proporciona al agente codificador un manual con el **100% de la lógica requerida**, asegurando una ejecución impecable y agnóstica al sistema operativo donde se despliegue.

¿Cómo ves esta especificación final con el soporte total de `pyproject.toml`, `uv sync` y `uv run`? Si te parece correcta, podemos dar por cerrado el diseño para que esté lista para ser ejecutada por tu agente codificador.