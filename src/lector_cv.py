"""
src/lector_cv.py — Capa 1: Única Fuente de Verdad (Lectura Dinámica del PDF Local)

Localiza, lee y analiza el currículum maestro en PDF.
PROHIBIDO hardcodear o resumir el currículum en el código fuente.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pypdf import PdfReader

load_dotenv()

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = CACHE_DIR / "cache_estrategia_cv.json"

DEFAULT_CV_DIR = (
    "/Users/jaimetapia/Documents/Postulaciones/"
    "Curriculums Vitae/Curriculum General Exhaustivo"
)

# ---------------------------------------------------------------------------
# Esquema Pydantic para la estrategia de búsqueda
# ---------------------------------------------------------------------------

class EstrategiaBusquedaCV(BaseModel):
    """Estructura devuelta por Gemini al analizar el CV."""
    resumen_ejecutivo_detectado: str
    cargos_objetivo_busqueda: list[str]  # 15 a 18 cargos (priorizando sector minero)
    keywords_tecnicas: list[str]
    lineas_rojas_detectadas: list[str]


# ---------------------------------------------------------------------------
# 1. Localización inteligente del PDF
# ---------------------------------------------------------------------------

def localizar_archivo_cv_pdf(ruta_configurada: Optional[str] = None) -> Path:
    """Localiza el archivo PDF del currículum con múltiples estrategias de búsqueda.

    Estrategias en orden:
    1. Si `ruta_configurada` (o CV_PDF_PATH) apunta directamente a un archivo, lo usa.
    2. Si falta la extensión `.pdf`, la agrega e intenta de nuevo.
    3. Si es un directorio, busca el `.pdf` más reciente ignorando temporales (`._*`).
    4. Busca en la carpeta padre coincidencias con "Exhaustivo", "Maestro" o "Curriculum".

    Raises:
        FileNotFoundError: si ninguna estrategia localiza un PDF válido.
    """
    ruta_base = ruta_configurada or os.getenv("CV_PDF_PATH", DEFAULT_CV_DIR)
    ruta_base = ruta_base.strip().strip('"').strip("'")
    ruta = Path(ruta_base).expanduser()

    # Estrategia 1: archivo directo
    if ruta.is_file() and ruta.suffix.lower() == ".pdf":
        return ruta

    # Estrategia 2: falta extensión .pdf
    ruta_con_ext = ruta.with_suffix(".pdf")
    if ruta_con_ext.is_file():
        return ruta_con_ext

    # Estrategia 3: directorio → PDF más reciente (sin temporales)
    if ruta.is_dir():
        pdfs = sorted(
            [
                f
                for f in ruta.glob("*.pdf")
                if not f.name.startswith("._")
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if pdfs:
            return pdfs[0]

    # Estrategia 4: buscar en carpeta padre
    carpeta_padre = ruta.parent if not ruta.is_dir() else ruta.parent
    keywords_busqueda = ["exhaustivo", "maestro", "curriculum"]
    if carpeta_padre.is_dir():
        for pdf in carpeta_padre.glob("*.pdf"):
            if pdf.name.startswith("._"):
                continue
            nombre_lower = pdf.name.lower()
            if any(kw in nombre_lower for kw in keywords_busqueda):
                return pdf

    # Estrategia 5: buscar en carpeta data/ del proyecto (ideal para Streamlit Cloud)
    data_dir_proyecto = Path(__file__).resolve().parent.parent / "data"
    if data_dir_proyecto.is_dir():
        for pdf in sorted(data_dir_proyecto.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not pdf.name.startswith("._"):
                return pdf

    raise FileNotFoundError(
        f"No se encontró el CV en PDF. Rutas intentadas:\n"
        f"  • Directa: {ruta}\n"
        f"  • Con extensión: {ruta_con_ext}\n"
        f"  • Directorio: {ruta if ruta.is_dir() else '(no es directorio)'}\n"
        f"  • Carpeta padre: {carpeta_padre}\n"
        f"Configura CV_PDF_PATH en .env con la ruta correcta."
    )


# ---------------------------------------------------------------------------
# 2. Lectura íntegra del PDF
# ---------------------------------------------------------------------------

def leer_cv_pdf_integro(ruta_pdf: Optional[Path] = None) -> dict:
    """Lee el PDF completo y devuelve texto, hash SHA-256 y metadatos.

    Returns:
        dict con claves: texto, hash, nombre_archivo, ruta, actualizado
    """
    if ruta_pdf is None:
        ruta_pdf = localizar_archivo_cv_pdf()

    # Leer bytes para el hash
    contenido_bytes = ruta_pdf.read_bytes()
    cv_hash = hashlib.sha256(contenido_bytes).hexdigest()

    # Extraer texto con pypdf
    reader = PdfReader(ruta_pdf)
    paginas_texto = []
    for pagina in reader.pages:
        texto_pagina = pagina.extract_text()
        if texto_pagina:
            paginas_texto.append(texto_pagina)

    texto_completo = "\n\n".join(paginas_texto)

    if not texto_completo.strip():
        raise ValueError(
            f"El PDF '{ruta_pdf.name}' no contiene texto extraíble. "
            "¿Es un PDF escaneado? Considera usar OCR."
        )

    stat = ruta_pdf.stat()
    fecha_mod = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    return {
        "texto": texto_completo,
        "hash": cv_hash,
        "nombre_archivo": ruta_pdf.name,
        "ruta": str(ruta_pdf),
        "actualizado": fecha_mod,
    }


# ---------------------------------------------------------------------------
# 3. Estrategia de búsqueda desde el CV (con caché y Gemini)
# ---------------------------------------------------------------------------

def obtener_estrategia_busqueda_desde_cv(
    forzar_recalculo: bool = False,
) -> dict:
    """Extrae la estrategia de búsqueda laboral analizando el CV con Gemini.

    Usa un caché local (`data/cache_estrategia_cv.json`) indexado por el hash
    SHA-256 del PDF. Solo invoca a Gemini si el hash cambió o se fuerza el
    recálculo.

    Returns:
        dict con la estructura de EstrategiaBusquedaCV + metadatos del CV.
    """
    cv_data = leer_cv_pdf_integro()
    cv_hash = cv_data["hash"]

    # Verificar caché
    if not forzar_recalculo and CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if cache.get("cv_hash") == cv_hash:
                print("✅ Estrategia de búsqueda cargada desde caché (hash coincide).")
                return cache
        except (json.JSONDecodeError, KeyError):
            pass  # Caché corrupto, recalcular

    print("🤖 Analizando CV con Gemini 2.5 Flash para extraer estrategia de búsqueda...")

    # Importar google-genai
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key:
        raise ValueError(
            "No se encontró GEMINI_API_KEY. Si estás en Streamlit Cloud, "
            "configúrala en el menú 'Settings > Secrets' de tu aplicación."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""Analiza el siguiente Currículum Vitae completo y extrae la información
solicitada en formato JSON estructurado.

INSTRUCCIONES:
1. `resumen_ejecutivo_detectado`: Resumen de 2-3 oraciones del perfil profesional.
2. `cargos_objetivo_busqueda`: Lista de 15 a 18 cargos/títulos laborales reales
   que este candidato debería buscar en portales de empleo chilenos. Incluye
   variaciones en español e inglés según corresponda.
   PRIORIDAD MÁXIMA: Si el candidato tiene formación o experiencia en MINERÍA,
   los PRIMEROS 6-8 cargos DEBEN ser roles que combinen minería con tecnología,
   transformación digital, business analysis o gestión de proyectos TI en el
   sector minero. Ejemplos: "Business Analyst Minería", "Ingeniero Transformación
   Digital Minería", "Analista Funcional Minería", "Project Manager TI Minería",
   "Consultor Transformación Digital Mining", "Especialista TI Minería",
   "Coordinador Proyectos Tecnológicos Minería", "Ingeniero de Datos Minería".
   Los cargos restantes pueden ser genéricos del perfil profesional.
3. `keywords_tecnicas`: Lista de 15-30 keywords técnicas, herramientas,
   metodologías y competencias clave del candidato. Si tiene formación minera,
   incluir keywords sectoriales: minería, mining, faena, planta, MoC, TTO,
   sistema de control, SAP PM, PI System, OT, y nombres de empresas mineras
   relevantes en Chile.
4. `lineas_rojas_detectadas`: Restricciones, limitaciones o notas que el
   candidato declara explícitamente (ej: disponibilidad, ubicación, etc.).

CURRÍCULUM VITAE:
{cv_data['texto']}
"""

    modelos = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
    ]
    response = None
    ultimo_error = None

    for m in modelos:
        try:
            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": EstrategiaBusquedaCV,
                },
            )
            break
        except Exception as e:
            ultimo_error = e
            continue

    if response is None:
        raise ultimo_error

    # Parsear respuesta
    estrategia = EstrategiaBusquedaCV.model_validate_json(response.text)

    # Construir resultado con metadatos
    resultado = {
        "cv_hash": cv_hash,
        "nombre_archivo": cv_data["nombre_archivo"],
        "ruta_cv": cv_data["ruta"],
        "actualizado": cv_data["actualizado"],
        **estrategia.model_dump(),
    }

    # Guardar en caché
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"💾 Estrategia guardada en caché: {CACHE_PATH}")

    return resultado
