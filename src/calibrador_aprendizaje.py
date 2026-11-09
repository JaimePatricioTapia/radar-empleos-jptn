"""
src/calibrador_aprendizaje.py — Módulo de Aprendizaje Continuo y Calibración del Radar

Analiza ofertas con estado POSTULADO vs DESCARTADA en Supabase para extraer
patrones de comportamiento, calibrar la evaluación de Gemini y refinar
los cargos/keywords de búsqueda automáticamente sin necesidad de Deep Learning pesado.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.database import obtener_ofertas_aprendizaje

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_APRENDIZAJE_PATH = DATA_DIR / "cache_aprendizaje.json"


# ---------------------------------------------------------------------------
# Esquema Pydantic del perfil aprendido
# ---------------------------------------------------------------------------

class PerfilAprendizaje(BaseModel):
    """Estructura de patrones aprendidos a partir del historial del candidato."""
    resumen_habitos_postulacion: str = Field(
        description="Diagnóstico ejecutivo en 2-3 frases de qué tipo de ofertas prefiere el usuario según sus postulaciones reales."
    )
    criterios_favoritos: list[str] = Field(
        description="Factores que impulsan la postulación (ej: roles estratégicos, banca, metodologías ágiles, minería, liderazgo funcional)."
    )
    criterios_descarte: list[str] = Field(
        description="Factores o anti-patrones que provocan el descarte de la oferta (ej: programación pura, analítica pesada/Big Data, consultoría outsourcing genérica)."
    )
    keywords_clave_postuladas: list[str] = Field(
        description="Keywords técnicas o metodológicas recurrentes en las ofertas a las que efectivamente postuló."
    )
    keywords_asociadas_descarte: list[str] = Field(
        description="Keywords o términos que aparecen frecuentemente en ofertas descartadas."
    )
    nuevos_cargos_recomendados_busqueda: list[str] = Field(
        description="5 a 8 títulos de cargos específicos y afinados para agregar a las búsquedas de los portales."
    )
    directrices_calibracion_evaluador: list[str] = Field(
        description="5 a 6 instrucciones precisas para que el evaluador Gemini ajuste el score y veredicto de futuras ofertas según las preferencias demostradas."
    )


# ---------------------------------------------------------------------------
# Lectura y persistencia de caché
# ---------------------------------------------------------------------------

def obtener_perfil_aprendizaje_cache() -> Optional[dict]:
    """Carga el perfil de aprendizaje almacenado en caché si existe."""
    if not CACHE_APRENDIZAJE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_APRENDIZAJE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def cambiar_estado_activacion_aprendizaje(activo: bool) -> bool:
    """Activa o desactiva la aplicación de los patrones aprendidos en el evaluador."""
    cache = obtener_perfil_aprendizaje_cache()
    if not cache:
        return False
    cache["activo"] = activo
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_APRENDIZAJE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return True


def obtener_directrices_para_evaluador() -> list[str]:
    """Retorna las directrices aprendidas si están activas en caché."""
    cache = obtener_perfil_aprendizaje_cache()
    if not cache or not cache.get("activo", True):
        return []
    return cache.get("directrices_calibracion_evaluador", [])


# ---------------------------------------------------------------------------
# Ejecución del análisis con Gemini (Meta-Prompting / In-Context Learning)
# ---------------------------------------------------------------------------

def ejecutar_analisis_aprendizaje(forzar: bool = False, limite: int = 50) -> dict:
    """Extrae las ofertas postuladas y descartadas desde Supabase,
    analiza los patrones con Gemini y guarda el perfil resultante en caché.

    Args:
        forzar: Si es True, recalcula aunque no hayan cambiado las cantidades.
        limite: Máximo de ofertas de cada tipo a enviar a Gemini.

    Returns:
        dict con el perfil de aprendizaje completo y metadatos.
    """
    datos = obtener_ofertas_aprendizaje(limite=limite)
    postuladas = datos.get("postuladas", [])
    descartadas = datos.get("descartadas", [])

    total_postuladas = len(postuladas)
    total_descartadas = len(descartadas)

    if total_postuladas == 0 and total_descartadas == 0:
        raise ValueError(
            "No se encontraron ofertas marcadas como POSTULADO ni DESCARTADA en Supabase. "
            "Cambia el estado de algunas ofertas en el Radar para que el sistema pueda aprender."
        )

    # Verificar caché si no se fuerza
    cache_previo = obtener_perfil_aprendizaje_cache()
    if not forzar and cache_previo:
        if (
            cache_previo.get("total_postuladas_analizadas") == total_postuladas
            and cache_previo.get("total_descartadas_analizadas") == total_descartadas
        ):
            return cache_previo

    # Preparar resumen compacto de las ofertas para el prompt (optimización de tokens)
    def _resumir_ofertas(lista: list) -> list[dict]:
        resumen = []
        for o in lista:
            resumen.append({
                "titulo": o.get("titulo"),
                "empresa": o.get("empresa"),
                "rol_detectado": o.get("rol_detectado"),
                "modalidad": o.get("modalidad"),
                "score_inicial": o.get("score_match"),
                "veredicto_inicial": o.get("veredicto"),
                "keywords": o.get("keywords_ats")[:6] if isinstance(o.get("keywords_ats"), list) else [],
            })
        return resumen

    postuladas_resumen = _resumir_ofertas(postuladas)
    descartadas_resumen = _resumir_ofertas(descartadas)

    prompt = f"""Eres un experto en analítica de mercado laboral, selección de talento y sistemas de recomendación.
Analiza el comportamiento real de postulación de un candidato que está utilizando un radar de empleos.

HISTORIAL DE POSTULACIONES DEL CANDIDATO:
El candidato revisó ofertas recomendadas por un evaluador y tomó decisiones humanas:

1. OFERTAS A LAS QUE SÍ POSTULÓ ({total_postuladas} ofertas evaluadas positivamente por el candidato):
{json.dumps(postuladas_resumen, ensure_ascii=False, indent=2)}

2. OFERTAS QUE EL CANDIDATO DESCARTÓ ({total_descartadas} ofertas rechazadas):
{json.dumps(descartadas_resumen, ensure_ascii=False, indent=2)}

TU TAREA:
1. Compara las ofertas donde POSTULÓ contra las que DESCARTÓ.
2. Identifica los criterios sutiles del candidato: ¿Qué sectores (ej: banca, minería, retail), qué tipo de responsabilidades (estratégicas, metodológicas vs programación dura o analítica técnica pesada), qué tecnologías y qué tipo de empresas realmente prefiere?
3. Extrae directrices concretas para calibrar el evaluador de IA para que no recomiende en el futuro ofertas similares a las descartadas y premie las similares a las postuladas.
4. Sugiere variaciones de títulos de cargo para que el radar capture mejores oportunidades en los portales chilenos.
"""

    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key:
        raise ValueError("No se encontró GEMINI_API_KEY para ejecutar la calibración de aprendizaje.")

    client = genai.Client(api_key=api_key)

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
                    "response_schema": PerfilAprendizaje,
                },
            )
            break
        except Exception as e:
            ultimo_error = e
            continue

    if response is None:
        raise ultimo_error

    perfil = PerfilAprendizaje.model_validate_json(response.text)

    resultado = {
        "actualizado_el": datetime.now(timezone.utc).isoformat(),
        "total_postuladas_analizadas": total_postuladas,
        "total_descartadas_analizadas": total_descartadas,
        "activo": True,
        **perfil.model_dump(),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_APRENDIZAJE_PATH.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return resultado
