"""
src/database.py — Capa 3: Memoria Central y Filtro de Costos (Supabase PostgreSQL)

Manejo de deduplicación por job_hash, CRUD de ofertas y métricas KPI.
REGLA DE AHORRO DE TOKENS: antes de llamar a Gemini, verificar oferta_ya_existe().
"""

import hashlib
import json
import os
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ---------------------------------------------------------------------------
# Conexión Supabase (singleton)
# ---------------------------------------------------------------------------
_supabase_client: Client | None = None

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "refid", "refId", "trackingid", "trackingId", "trk", "src",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid",
}


def _get_client() -> Client:
    """Obtiene o crea el cliente Supabase singleton."""
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        # Fallback a st.secrets para Streamlit Community Cloud
        if not url or not key:
            try:
                import streamlit as st
                url = url or st.secrets.get("SUPABASE_URL")
                key = key or st.secrets.get("SUPABASE_KEY")
            except Exception:
                pass

        if not url or not key:
            raise EnvironmentError(
                "Faltan SUPABASE_URL y/o SUPABASE_KEY en las variables de entorno o st.secrets. "
                "Configura tu archivo .env o los Secrets en Streamlit Cloud."
            )
        _supabase_client = create_client(url, key)
    return _supabase_client


# ---------------------------------------------------------------------------
# Generación de job_hash (deduplicación)
# ---------------------------------------------------------------------------

def _limpiar_url(url: str) -> str:
    """Elimina parámetros de tracking de una URL."""
    parsed = urlparse(url.strip())
    params = parse_qs(parsed.query)
    params_limpios = {
        k: v for k, v in params.items()
        if k.lower() not in TRACKING_PARAMS
    }
    query_limpio = urlencode(params_limpios, doseq=True)
    url_limpia = urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, query_limpio, ""
    ))
    return url_limpia.rstrip("/").lower()


def _es_url_generica(url: str) -> bool:
    """Detecta URLs genéricas que no identifican una oferta específica."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    partes = [p for p in path.split("/") if p]
    # Si el path tiene menos de 2 segmentos, probablemente es genérica
    return len(partes) < 2


def generar_job_hash(
    url: str,
    titulo: str = "",
    empresa: str = "",
    portal: str = "",
) -> str:
    """Genera un hash SHA-256 único para deduplicar ofertas.

    - Si la URL es específica: hash de la URL limpia (sin tracking params).
    - Si la URL es genérica: hash de portal + titulo + empresa + url.
    """
    url_limpia = _limpiar_url(url)

    if _es_url_generica(url_limpia) and titulo:
        cadena = f"{portal}_{titulo}_{empresa}_{url_limpia}".lower().strip()
    else:
        cadena = url_limpia

    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verificación de existencia (REGLA DE AHORRO DE TOKENS)
# ---------------------------------------------------------------------------

def oferta_ya_existe(job_hash: str) -> bool:
    """Verifica si una oferta con ese job_hash ya está en Supabase.

    Esta función DEBE llamarse antes de invocar a Gemini para evitar
    consumo innecesario de tokens en ofertas duplicadas.

    Returns:
        True si la oferta ya existe, False si es nueva.
    """
    client = _get_client()
    result = (
        client.table("ofertas_laborales")
        .select("id")
        .eq("job_hash", job_hash)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


# ---------------------------------------------------------------------------
# Almacenamiento de ofertas evaluadas
# ---------------------------------------------------------------------------

def guardar_oferta_evaluada(oferta_raw: dict, evaluacion: dict) -> dict:
    """Combina datos crudos de la oferta con la evaluación de Gemini y los
    inserta en la tabla `ofertas_laborales`.

    Args:
        oferta_raw: dict con campos de la oferta (titulo, empresa, url, etc.)
        evaluacion: dict con la evaluación de Gemini (score_match, veredicto, etc.)

    Returns:
        El registro insertado como dict.
    """
    client = _get_client()

    # Construir registro para inserción
    registro = {
        "job_hash": oferta_raw.get("job_hash"),
        "portal": oferta_raw.get("portal", "desconocido"),
        "titulo": oferta_raw.get("titulo", "Sin título"),
        "empresa": oferta_raw.get("empresa"),
        "ubicacion": oferta_raw.get("ubicacion"),
        "modalidad": oferta_raw.get("modalidad"),
        "url": oferta_raw.get("url", ""),
        "descripcion_cruda": oferta_raw.get("descripcion_cruda", ""),
        "fecha_publicacion": oferta_raw.get("fecha_publicacion"),
        # Campos de la evaluación IA
        "score_match": evaluacion.get("score_match"),
        "veredicto": evaluacion.get("veredicto"),
        "rol_detectado": evaluacion.get("rol_detectado"),
        "enfoque_cv_sugerido": evaluacion.get("enfoque_cv_sugerido"),
        "fortalezas": json.dumps(evaluacion.get("fortalezas", []), ensure_ascii=False),
        "brechas": json.dumps(evaluacion.get("brechas", []), ensure_ascii=False),
        "keywords_ats": json.dumps(evaluacion.get("keywords_ats", []), ensure_ascii=False),
        "renta_estimada_empresa": evaluacion.get("renta_estimada_empresa"),
        "pretension_sugerida": evaluacion.get("pretension_sugerida"),
        "estado_postulacion": "NUEVA",
    }

    result = (
        client.table("ofertas_laborales")
        .insert(registro)
        .execute()
    )

    if result.data:
        return result.data[0]
    return registro


# ---------------------------------------------------------------------------
# Consultas y filtros
# ---------------------------------------------------------------------------

def obtener_ofertas_filtradas(
    veredictos: list | None = None,
    score_minimo: int = 0,
    estados: list | None = None,
    portales: list | None = None,
) -> list:
    """Recupera ofertas con filtros dinámicos.

    Args:
        veredictos: Lista de veredictos a incluir (ej: ['POSTULAR']).
        score_minimo: Score mínimo de match (0-100).
        estados: Lista de estados (ej: ['NUEVA', 'GUARDADA']).
        portales: Lista de portales a filtrar.

    Returns:
        Lista de registros ordenados por score_match DESC, fecha_extraccion DESC.
    """
    client = _get_client()
    query = client.table("ofertas_laborales").select("*")

    if veredictos:
        query = query.in_("veredicto", veredictos)

    if score_minimo > 0:
        query = query.gte("score_match", score_minimo)

    if estados:
        query = query.in_("estado_postulacion", estados)

    if portales:
        query = query.in_("portal", portales)

    query = query.order("score_match", desc=True).order("fecha_extraccion", desc=True)

    result = query.execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Métricas KPI
# ---------------------------------------------------------------------------

def obtener_metricas_resumen() -> dict:
    """Calcula métricas resumen para el dashboard en una sola consulta optimizada.

    Returns:
        dict con métricas agregadas.
    """
    client = _get_client()

    # Consulta única agregada para máxima velocidad (evita 4 round trips HTTP)
    res = (
        client.table("ofertas_laborales")
        .select("id, estado_postulacion, veredicto")
        .execute()
    )
    data = res.data or []

    totales = len(data)
    recomendadas = sum(1 for o in data if o.get("veredicto") == "POSTULAR")
    postulados = sum(1 for o in data if o.get("estado_postulacion") == "POSTULADO")
    descartadas = sum(1 for o in data if o.get("estado_postulacion") == "DESCARTADA")
    guardadas = sum(1 for o in data if o.get("estado_postulacion") == "GUARDADA")
    por_revisar = sum(
        1 for o in data
        if o.get("estado_postulacion") == "NUEVA"
        and o.get("veredicto") in ("POSTULAR", "POSTULAR CON RESERVAS")
    )

    return {
        "ofertas_totales": totales,
        "recomendadas_postular": recomendadas,
        "postulados": postulados,
        "descartadas": descartadas,
        "guardadas": guardadas,
        "por_revisar": por_revisar,
    }


# ---------------------------------------------------------------------------
# Actualización de estado
# ---------------------------------------------------------------------------

def actualizar_estado_oferta(oferta_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de postulación de una oferta.

    Args:
        oferta_id: UUID de la oferta.
        nuevo_estado: Uno de 'NUEVA', 'GUARDADA', 'POSTULADO', 'DESCARTADA'.

    Returns:
        True si se actualizó correctamente.
    """
    estados_validos = {"NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"}
    if nuevo_estado not in estados_validos:
        raise ValueError(
            f"Estado inválido: '{nuevo_estado}'. "
            f"Debe ser uno de: {estados_validos}"
        )

    client = _get_client()
    result = (
        client.table("ofertas_laborales")
        .update({"estado_postulacion": nuevo_estado})
        .eq("id", oferta_id)
        .execute()
    )

    return len(result.data) > 0


# ---------------------------------------------------------------------------
# Extracción de datos para Aprendizaje y Calibración
# ---------------------------------------------------------------------------

def obtener_ofertas_aprendizaje(limite: int = 50) -> dict:
    """Recupera ofertas con estado POSTULADO y DESCARTADA para análisis de patrones.

    Args:
        limite: Número máximo de ofertas por categoría a recuperar.

    Returns:
        dict con listas 'postuladas' y 'descartadas'.
    """
    client = _get_client()
    postuladas = (
        client.table("ofertas_laborales")
        .select("id, titulo, empresa, modalidad, ubicacion, rol_detectado, score_match, keywords_ats, fortalezas, brechas, veredicto")
        .eq("estado_postulacion", "POSTULADO")
        .order("fecha_extraccion", desc=True)
        .limit(limite)
        .execute()
    )
    descartadas = (
        client.table("ofertas_laborales")
        .select("id, titulo, empresa, modalidad, ubicacion, rol_detectado, score_match, keywords_ats, fortalezas, brechas, veredicto")
        .eq("estado_postulacion", "DESCARTADA")
        .order("fecha_extraccion", desc=True)
        .limit(limite)
        .execute()
    )
    return {
        "postuladas": postuladas.data or [],
        "descartadas": descartadas.data or [],
    }

