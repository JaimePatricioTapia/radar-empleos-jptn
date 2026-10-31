"""
src/ingesta_portales.py — Conectores directos para portales estratégicos chilenos:
- Get on Board (API Pública JSON)
- ChileTrabajos (Scraping HTTP directo)
"""

import html
import re
import traceback
import urllib.parse
import requests
from bs4 import BeautifulSoup

from src.database import generar_job_hash, oferta_ya_existe, guardar_oferta_evaluada
from src.evaluador_ia import evaluar_oferta_con_gemini
from src.lector_cv import leer_cv_pdf_integro

HEADERS_DEFAULT = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}


# ===========================================================================
# 1. GET ON BOARD (API REST Pública)
# ===========================================================================

def ejecutar_busqueda_getonbrd(
    cargos: list[str],
    limite_por_cargo: int = 15,
    callback_progreso=None,
) -> dict:
    """Busca ofertas en Get on Board mediante su API pública JSON.

    Excelente para roles de Product Owner, Scrum Master, Business Analyst,
    IA, Datos y Transformación Digital en Chile / Remoto.
    """
    stats = {
        "portal": "getonbrd",
        "total_encontradas": 0,
        "nuevas": 0,
        "duplicadas": 0,
        "errores": 0,
        "detalle_errores": [],
    }

    try:
        cv_data = leer_cv_pdf_integro()
        texto_cv = cv_data["texto"]
    except Exception as e:
        stats["detalle_errores"].append(f"Error leyendo CV: {e}")
        return stats

    base_url = "https://www.getonbrd.com/api/v0/search/jobs"

    for cargo in cargos:
        if callback_progreso:
            callback_progreso(f"🚀 Buscando '{cargo}' en Get on Board...")

        try:
            params = {"query": cargo, "per_page": limite_por_cargo}
            resp = requests.get(base_url, params=params, headers=HEADERS_DEFAULT, timeout=15)

            if resp.status_code != 200:
                stats["errores"] += 1
                stats["detalle_errores"].append(
                    f"Get on Board status {resp.status_code} para '{cargo}'"
                )
                continue

            data = resp.json().get("data", [])

            for item in data:
                try:
                    stats["total_encontradas"] += 1
                    attrs = item.get("attributes", {})
                    links = item.get("links", {})

                    titulo = attrs.get("title", "Sin título").strip()
                    url_oferta = links.get("public_url") or attrs.get("url") or ""

                    # Limpiar descripción (viene en HTML)
                    desc_html = attrs.get("description", "") + " " + attrs.get("functions", "")
                    soup = BeautifulSoup(desc_html, "html.parser")
                    descripcion_limpia = soup.get_text(separator="\n").strip()

                    # Modalidad y ubicación
                    modalidad = attrs.get("remote_modality", "")
                    if attrs.get("remote"):
                        modalidad = f"Remoto ({modalidad})" if modalidad else "Remoto"
                    elif attrs.get("modality"):
                        modalidad = attrs.get("modality")

                    # Empresa
                    empresa = ""
                    company_data = attrs.get("company", {}).get("data", {})
                    if isinstance(company_data, dict):
                        empresa = company_data.get("attributes", {}).get("name", "")
                    if not empresa and url_oferta:
                        # Extraer del slug si no viene en attributes
                        slug_parts = url_oferta.rstrip("/").split("/")[-1].split("-")
                        if len(slug_parts) >= 2:
                            empresa = slug_parts[-2].capitalize()

                    # Renta declarada si existe
                    renta = ""
                    min_sal = attrs.get("min_salary")
                    max_sal = attrs.get("max_salary")
                    if min_sal and max_sal:
                        renta = f"USD ${min_sal:,} - ${max_sal:,}"

                    fecha_pub = attrs.get("published_at", "")

                    # Generar hash único
                    job_hash = generar_job_hash(
                        url=url_oferta,
                        titulo=titulo,
                        empresa=empresa,
                        portal="getonbrd",
                    )

                    # REGLA DE AHORRO: verificar en Supabase ANTES de Gemini
                    if oferta_ya_existe(job_hash):
                        stats["duplicadas"] += 1
                        continue

                    if not descripcion_limpia:
                        descripcion_limpia = f"{titulo} en {empresa}. Modalidad: {modalidad}."

                    oferta = {
                        "job_hash": job_hash,
                        "portal": "getonbrd",
                        "titulo": titulo,
                        "empresa": empresa or "Empresa Confidencial",
                        "ubicacion": "Chile / Remoto",
                        "modalidad": modalidad,
                        "url": url_oferta,
                        "descripcion_cruda": descripcion_limpia,
                        "fecha_publicacion": fecha_pub,
                    }

                    if callback_progreso:
                        callback_progreso(f"🤖 Evaluando (Get on Board): {titulo}")

                    evaluacion = evaluar_oferta_con_gemini(oferta, texto_cv)
                    guardar_oferta_evaluada(oferta, evaluacion)
                    stats["nuevas"] += 1

                except Exception as e:
                    stats["errores"] += 1
                    stats["detalle_errores"].append(f"Error procesando oferta Get on Board: {e}")

        except Exception as e:
            stats["errores"] += 1
            stats["detalle_errores"].append(f"Error buscando '{cargo}' en Get on Board: {e}")

    return stats


# ===========================================================================
# 2. CHILETRABAJOS (Scraping HTTP Público)
# ===========================================================================

def ejecutar_busqueda_chiletrabajos(
    cargos: list[str],
    limite_por_cargo: int = 15,
    callback_progreso=None,
) -> dict:
    """Busca ofertas en ChileTrabajos mediante scraping HTTP directo sin login.

    Excelente para cargos en Santiago, regiones, minería y analistas en general.
    """
    stats = {
        "portal": "chiletrabajos",
        "total_encontradas": 0,
        "nuevas": 0,
        "duplicadas": 0,
        "errores": 0,
        "detalle_errores": [],
    }

    try:
        cv_data = leer_cv_pdf_integro()
        texto_cv = cv_data["texto"]
    except Exception as e:
        stats["detalle_errores"].append(f"Error leyendo CV: {e}")
        return stats

    for cargo in cargos:
        if callback_progreso:
            callback_progreso(f"🇨🇱 Buscando '{cargo}' en ChileTrabajos...")

        try:
            query_encoded = urllib.parse.quote_plus(cargo)
            search_url = f"https://www.chiletrabajos.cl/encuentra-un-empleo?f=2&q={query_encoded}"
            resp = requests.get(search_url, headers=HEADERS_DEFAULT, timeout=15)

            if resp.status_code != 200:
                stats["errores"] += 1
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.job-item, div.destacado")

            procesados = 0
            for card in cards:
                if procesados >= limite_por_cargo:
                    break

                try:
                    title_a = card.select_one("h2.title a, h3.title a, a[href*='/trabajo/']")
                    if not title_a:
                        continue

                    titulo = title_a.get_text(strip=True)
                    url_oferta = title_a.get("href", "")

                    if not url_oferta.startswith("http"):
                        url_oferta = f"https://www.chiletrabajos.cl{url_oferta}"

                    stats["total_encontradas"] += 1

                    # Descripción preliminar en la tarjeta
                    desc_el = card.select_one("p, .text, .description")
                    desc_resumen = desc_el.get_text(strip=True) if desc_el else ""

                    # Empresa y ubicación
                    empresa_el = card.select_one(".company, .empresa, a[href*='/empresa/']")
                    empresa = empresa_el.get_text(strip=True) if empresa_el else "Empresa Destacada"

                    ubicacion_el = card.select_one(".city, .ciudad, a[href*='/ciudad/']")
                    ubicacion = ubicacion_el.get_text(strip=True) if ubicacion_el else "Chile"

                    # Hash único
                    job_hash = generar_job_hash(
                        url=url_oferta,
                        titulo=titulo,
                        empresa=empresa,
                        portal="chiletrabajos",
                    )

                    # Deduplicación previa
                    if oferta_ya_existe(job_hash):
                        stats["duplicadas"] += 1
                        continue

                    # Obtener detalle completo de la oferta
                    descripcion_completa = desc_resumen
                    try:
                        detail_resp = requests.get(url_oferta, headers=HEADERS_DEFAULT, timeout=10)
                        if detail_resp.status_code == 200:
                            d_soup = BeautifulSoup(detail_resp.text, "html.parser")
                            body_desc = d_soup.select_one(".job-description, .descripcion, article, .content")
                            if body_desc:
                                descripcion_completa = body_desc.get_text(separator="\n").strip()
                    except Exception:
                        pass

                    if not descripcion_completa.strip():
                        descripcion_completa = f"{titulo} en {empresa}, {ubicacion}."

                    oferta = {
                        "job_hash": job_hash,
                        "portal": "chiletrabajos",
                        "titulo": titulo,
                        "empresa": empresa,
                        "ubicacion": ubicacion,
                        "modalidad": "Presencial / Híbrido",
                        "url": url_oferta,
                        "descripcion_cruda": descripcion_completa,
                        "fecha_publicacion": "",
                    }

                    if callback_progreso:
                        callback_progreso(f"🤖 Evaluando (ChileTrabajos): {titulo}")

                    evaluacion = evaluar_oferta_con_gemini(oferta, texto_cv)
                    guardar_oferta_evaluada(oferta, evaluacion)
                    stats["nuevas"] += 1
                    procesados += 1

                except Exception as e:
                    stats["errores"] += 1
                    stats["detalle_errores"].append(f"Error procesando oferta ChileTrabajos: {e}")

        except Exception as e:
            stats["errores"] += 1
            stats["detalle_errores"].append(f"Error buscando '{cargo}' en ChileTrabajos: {e}")

    return stats
