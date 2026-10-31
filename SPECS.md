# SPECS.md — Radar de Empleos JPTN (Especificación Técnica de Construcción)

## 1. Visión General del Proyecto
- **Nombre:** `radar-empleos-jptn`
- **Autor/Candidato:** Jaime Patricio Tapia Navia
- **Entorno de Ejecución:** Local en macOS (Apple Silicon M3) vía Google Antigravity.
- **Objetivo:** Sistema automatizado de descubrimiento, extracción, deduplicación en Supabase y evaluación semántica asistida por IA (Gemini 2.5 Flash) de ofertas laborales en Chile frente al Currículum Maestro Exhaustivo en PDF, con visualización y gestión en un dashboard ejecutivo de Streamlit.

---

## 2. Reglas Arquitectónicas Innegociables (5 Capas)

1. **Capa 1 — Única Fuente de Verdad (Lectura Dinámica del PDF Local):**
   - **Prohibido** hardcodear o resumir el currículum en el código fuente.
   - El sistema debe localizar y leer dinámicamente el currículum en PDF desde la ruta configurada en macOS:
     `/Users/jaimetapia/Documents/Postulaciones/Curriculums Vitae/Curriculum General Exhaustivo`
   - Debe extraer el texto íntegro con `pypdf`, calcular la huella digital SHA-256 binaria (`cv_hash`) y consultar a `gemini-2.5-flash` para auto-detectar los cargos objetivo, keywords técnicas y notas restrictivas declaradas en el documento. Esta estrategia se cachea en `data/cache_estrategia_cv.json` y solo se recalcula si el hash del PDF cambia.

2. **Capa 2 — Ingesta Híbrida Anti-Bloqueo (Local en Mac M3):**
   - **Vía A (`python-jobspy`):** Búsqueda pública sin credenciales en LinkedIn, Indeed y Google Jobs para proteger la cuenta personal de LinkedIn contra bloqueos algorítmicos.
   - **Vía B (`playwright` con Sesión Persistente):** Navegación en portales chilenos (Laborum y Trabajando.com) usando `./browser_session/` local para inicio de sesión manual único (`--modo login`) y scraping posterior reutilizando cookies con pausas humanas aleatorias (5 a 11 segundos) (`--modo buscar`).

3. **Capa 3 — Memoria Central y Filtro de Costos (`Supabase PostgreSQL`):**
   - Cada oferta genera un `job_hash` único (SHA-256 de la URL normalizada sin parámetros de tracking o combinación de `portal + titulo + empresa`).
   - **Regla de Ahorro de Tokens:** Antes de llamar a Gemini, se consulta `oferta_ya_existe(job_hash)` en Supabase. Si la oferta ya existe, se descarta inmediatamente consumiendo 0 tokens de IA.

4. **Capa 4 — Motor Evaluador Semántico (`Gemini 2.5 Flash` + `Pydantic`):**
   - Compara las ofertas nuevas contra el texto íntegro del PDF. Devuelve un JSON estructurado (`EvaluacionOferta`) con puntaje de calce, veredicto pragmático, fortalezas, brechas, keywords ATS y tasación salarial anclada al cargo.

5. **Capa 5 — Dashboard de Control Operativo (`Streamlit`):**
   - Interfaz en tema oscuro con métricas KPI, diagnóstico del estado del PDF, selector dinámico de cargos, filtros avanzados y tarjetas de ofertas con cambio de estado (`NUEVA`, `GUARDADA`, `POSTULADO`, `DESCARTADA`).

---

## 3. Estructura de Directorios

```text
radar-empleos-jptn/
├── .gitignore
├── .env.example
├── requirements.txt
├── schema_supabase.sql
├── data/
│   └── cache_estrategia_cv.json    # Generado automáticamente
├── src/
│   ├── __init__.py
│   ├── lector_cv.py
│   ├── database.py
│   ├── evaluador_ia.py
│   ├── ingesta_jobspy.py
│   └── ingesta_playwright.py
├── app.py
├── test_pipeline.py
└── SPECS.md
```

---

## 4. Especificación Detallada por Componente

### 4.1 `.gitignore`
Debe ignorar estrictamente:
```gitignore
.env
.venv/
venv/
browser_session/
data/cache_*.json
__pycache__/
*.pyc
.DS_Store
```

### 4.2 `.env.example`
```env
GEMINI_API_KEY=tu_api_key_de_google_ai_studio
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu_service_role_o_anon_key
CV_PDF_PATH="/Users/jaimetapia/Documents/Postulaciones/Curriculums Vitae/Curriculum General Exhaustivo"
```

### 4.3 `requirements.txt`
```text
google-genai>=1.0.0
supabase>=2.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
python-jobspy>=1.1.0
playwright>=1.40.0
streamlit>=1.35.0
pandas>=2.0.0
pypdf>=4.0.0
```

### 4.4 `schema_supabase.sql`
DDL para ejecutar en el SQL Editor de Supabase:
```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS ofertas_laborales (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_hash TEXT UNIQUE NOT NULL,
    portal TEXT NOT NULL,
    titulo TEXT NOT NULL,
    empresa TEXT,
    ubicacion TEXT,
    modalidad TEXT,
    url TEXT NOT NULL,
    descripcion_cruda TEXT NOT NULL,
    score_match INTEGER,
    veredicto TEXT CHECK (veredicto IN ('POSTULAR', 'POSTULAR CON RESERVAS', 'DESCARTAR')),
    rol_detectado TEXT,
    enfoque_cv_sugerido TEXT,
    fortalezas JSONB DEFAULT '[]'::jsonb,
    brechas JSONB DEFAULT '[]'::jsonb,
    keywords_ats JSONB DEFAULT '[]'::jsonb,
    renta_estimada_empresa TEXT,
    pretension_sugerida TEXT,
    estado_postulacion TEXT DEFAULT 'NUEVA' CHECK (estado_postulacion IN ('NUEVA', 'GUARDADA', 'POSTULADO', 'DESCARTADA')),
    fecha_publicacion TEXT,
    fecha_extraccion TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ofertas_score ON ofertas_laborales(score_match DESC);
CREATE INDEX IF NOT EXISTS idx_ofertas_veredicto ON ofertas_laborales(veredicto);
CREATE INDEX IF NOT EXISTS idx_ofertas_estado ON ofertas_laborales(estado_postulacion);
CREATE INDEX IF NOT EXISTS idx_ofertas_fecha ON ofertas_laborales(fecha_extraccion DESC);
```

### 4.5 `src/lector_cv.py`
Módulo encargado de interactuar con el archivo físico del CV en macOS.
- **`localizar_archivo_cv_pdf(ruta_configurada: str = None) -> Path`:**
  - Toma la ruta desde `CV_PDF_PATH` o parámetro.
  - Verifica si es un archivo directo, si falta la extensión `.pdf`, si es un directorio (busca el `.pdf` más reciente ignorando archivos temporales `._*`), o busca en la carpeta padre coincidencias con `"Exhaustivo"`, `"Maestro"` o `"Curriculum"`.
  - Lanza `FileNotFoundError` si no lo encuentra.
- **`leer_cv_pdf_integro(ruta_pdf: Path = None) -> dict`:**
  - Extrae el texto completo con `pypdf.PdfReader`.
  - Calcula el hash SHA-256 de los bytes del PDF.
  - Retorna `{"texto": str, "hash": str, "nombre_archivo": str, "ruta": str, "actualizado": str}`.
- **`obtener_estrategia_busqueda_desde_cv(forzar_recalculo: bool = False) -> dict`:**
  - Modela la salida con Pydantic:
    ```python
    class EstrategiaBusquedaCV(BaseModel):
        resumen_ejecutivo_detectado: str
        cargos_objetivo_busqueda: list[str]  # 8 a 10 cargos
        keywords_tecnicas: list[str]
        lineas_rojas_detectadas: list[str]
    ```
  - Si el hash coincide con `data/cache_estrategia_cv.json` y no se fuerza el recálculo, lee el caché.
  - De lo contrario, invoca `gemini-2.5-flash` usando el SDK `google-genai` con salida estructurada para extraer los cargos y reglas del documento. Guarda en JSON y retorna.

### 4.6 `src/database.py`
Módulo de capa de datos con `supabase-py`.
- **`generar_job_hash(url: str, titulo: str = "", empresa: str = "", portal: str = "") -> str`:**
  - Elimina query params de tracking (`utm_*`, `refId`, `trackingId`, etc.).
  - Genera hash SHA-256 de la URL limpia. Si es genérica, usa `f"{portal}_{titulo}_{empresa}_{url}"`.
- **`oferta_ya_existe(job_hash: str) -> bool`:**
  - Ejecuta un `select("id").eq("job_hash", job_hash).limit(1)`. Retorna booleano.
- **`guardar_oferta_evaluada(oferta_raw: dict, evaluacion: dict) -> dict`:**
  - Une ambos diccionarios e inserta en la tabla `ofertas_laborales`.
- **`obtener_ofertas_filtradas(veredictos: list = None, score_minimo: int = 0, estados: list = None, portales: list = None) -> list`:**
  - Consulta registros con filtros dinámicos, ordenados por `score_match DESC, fecha_extraccion DESC`.
- **`obtener_metricas_resumen() -> dict`:**
  - Calcula conteos: `ofertas_totales`, `recomendadas_postular` (veredicto POSTULAR), `postulados` (estado POSTULADO), `por_revisar` (estado NUEVA y veredicto POSTULAR o POSTULAR CON RESERVAS).
- **`actualizar_estado_oferta(oferta_id: str, nuevo_estado: str) -> bool`:**
  - Actualiza la columna `estado_postulacion`.

### 4.7 `src/evaluador_ia.py`
Módulo de evaluación semántica mediante `google-genai`.
- **Esquema Pydantic:**
  ```python
  class EvaluacionOferta(BaseModel):
      score_match: int = Field(ge=0, le=100)
      veredicto: Literal["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"]
      rol_detectado: str
      renta_estimada_empresa: str
      pretension_sugerida: str
      enfoque_cv_sugerido: str
      fortalezas: list[str]
      brechas: list[str]
      keywords_ats: list[str]
  ```
- **Reglas del System Prompt:**
  1. Carga el texto íntegro del PDF desde `src/lector_cv.py`.
  2. **Modo Sobrevivencia:** No descartar por menor seniority (Analista Funcional, Control de Gestión, Coordinador, etc.). Si el candidato puede ejecutar el trabajo, clasificar como `POSTULAR` o `POSTULAR CON RESERVAS`.
  3. **Exclusiones Duras:** Marcar `DESCARTAR` solo ante programación pura de carrera (Software Engineer Senior tradicional), Arquitecto Cloud puro, DevOps puro o inglés conversacional excluyente.
  4. **Tasación Salarial:** Calcular el rango estimado evaluando el presupuesto real del cargo en Chile y fijar la pretensión sugerida en el punto dulce (mitad inferior a media).

### 4.8 `src/ingesta_jobspy.py`
- Utiliza la función `scrape_jobs` de `python-jobspy`.
- Función `ejecutar_busqueda_jobspy(cargos: list[str], portales: list[str], resultados_por_cargo: int = 15, callback_progreso=None) -> dict`:
  - Itera sobre los cargos en `"Santiago, Chile"` y `"Chile"`.
  - Normaliza la salida a una lista de diccionarios (`titulo`, `empresa`, `ubicacion`, `modalidad`, `url`, `portal`, `descripcion_cruda`, `fecha_publicacion`).
  - Por cada oferta: verifica `oferta_ya_existe(job_hash)`. Si es nueva, la evalúa con `evaluar_oferta_con_gemini` y la guarda en Supabase.

### 4.9 `src/ingesta_playwright.py`
- Utiliza `playwright.sync_api` con `launch_persistent_context(user_data_dir="./browser_session", headless=False)`.
- **Modo CLI `--modo login`:** Abre ventana de navegador persistente para iniciar sesión manualmente en Laborum y Trabajando.com.
- **Función `ejecutar_busqueda_playwright(cargos: list[str], portales: list[str])`:**
  - Navega con pausas humanas aleatorias (5 a 11 segundos).
  - Extrae avisos, verifica en Supabase por hash y envía las ofertas nuevas a evaluar.

### 4.10 `app.py` (Dashboard en Streamlit)
Configuración de página: `st.set_page_config(page_title="Radar de Empleos JPTN", page_icon="🔍", layout="wide")`.
- **Barra Lateral (`st.sidebar`):**
  - Card de **Diagnóstico del CV Maestro**: nombre de archivo, badge verde `● Activo`, fecha de última actualización, primeros caracteres del hash SHA-256 y botón `🔄 Re-analizar PDF`.
  - Sección **Estrategia de Búsqueda (Auto-Detección)**: checkboxes para cada cargo extraído automáticamente del PDF y botón principal `🔍 Ejecutar Búsqueda en Portales`.
  - Sección **Opciones de Portales**: selección múltiple de plataformas.
  - Sección **Filtros Rápidos**: selector de veredicto, slider de score mínimo (default 70%) y selector de estado.
- **Área Principal:**
  - Encabezado con título y subtítulo descriptivo.
  - Fila superior con 4 tarjetas KPI estilizadas con CSS:
    1. Ofertas Totales
    2. Recomendadas (Postular) (Verde)
    3. Postulados (Azul)
    4. Por Revisar (Naranja)
  - Listado de ofertas renderizadas en tarjetas con borde izquierdo según semáforo de veredicto.
  - Contenido de cada tarjeta:
    - Encabezado con `% Match`, título, empresa, ubicación, modalidad y portal.
    - Banda salarial estimada vs. Pretensión sugerida (punto dulce).
    - Viñetas de enfoque sugerido, fortalezas, brechas y keywords ATS.
    - Botones de acción: `Ver Oferta 🔗`, `Copiar Ficha para CV 📋` (con bloque `st.code`) y selector de estado para actualización directa en Supabase.

### 4.11 `test_pipeline.py`
Script CLI de verificación con 4 pruebas secuenciales:
1. Localización y lectura del PDF en `/Users/jaimetapia/Documents/Postulaciones/Curriculums Vitae/Curriculum General Exhaustivo`.
2. Extracción o lectura en caché de la estrategia de búsqueda con Gemini.
3. Conexión y consulta a Supabase.
4. Evaluación de una oferta simulada y almacenamiento en Supabase.

---

## 5. Instrucciones de Despliegue Local en Mac M3

1. **Crear y activar entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Instalar dependencias:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   playwright install chromium
   ```
3. **Configurar base de datos:**
   - Copiar el contenido de `schema_supabase.sql` y ejecutarlo en el **SQL Editor** del dashboard de Supabase.
4. **Configurar variables de entorno:**
   - Crear `.env` a partir de `.env.example` con las credenciales correspondientes.
5. **Verificar pipeline:**
   ```bash
   python test_pipeline.py
   ```
6. **Ejecutar dashboard:**
   ```bash
   streamlit run app.py
   ```