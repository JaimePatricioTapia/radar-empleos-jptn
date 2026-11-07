"""
src/ingesta_jobspy.py — Capa 2 Vía A: Ingesta con python-jobspy

Búsqueda pública sin credenciales en LinkedIn, Indeed y Google Jobs.
Protege la cuenta personal de LinkedIn contra bloqueos algorítmicos.
"""

import traceback

from jobspy import scrape_jobs

from src.database import generar_job_hash, oferta_ya_existe, guardar_oferta_evaluada
from src.evaluador_ia import evaluar_oferta_con_gemini
from src.lector_cv import leer_cv_pdf_integro


def _normalizar_oferta_jobspy(row: dict, portal_origen: str) -> dict:
    """Normaliza una fila de jobspy al formato interno del sistema."""
    return {
        "titulo": str(row.get("title", "Sin título")),
        "empresa": str(row.get("company_name", row.get("company", ""))),
        "ubicacion": str(row.get("location", "")),
        "modalidad": str(row.get("job_type", "")),
        "url": str(row.get("job_url", row.get("link", ""))),
        "portal": portal_origen,
        "descripcion_cruda": str(row.get("description", "")),
        "fecha_publicacion": str(row.get("date_posted", "")),
    }


def ejecutar_busqueda_jobspy(
    cargos: list[str],
    portales: list[str] | None = None,
    resultados_por_cargo: int = 15,
    callback_progreso=None,
) -> dict:
    """Ejecuta búsqueda masiva en portales públicos vía python-jobspy.

    Args:
        cargos: Lista de cargos/títulos a buscar.
        portales: Lista de portales jobspy (default: linkedin, indeed, google).
        resultados_por_cargo: Máximo de resultados por combinación cargo/ubicación.
        callback_progreso: Función opcional para reportar progreso al UI.

    Returns:
        dict con estadísticas: total_encontradas, nuevas, duplicadas, errores.
    """
    if portales is None:
        portales = ["linkedin", "indeed", "google"]

    # Ubicaciones optimizadas: "Chile" cubre todo el país (incluye Santiago y remoto)
    # y "Antofagasta, Chile" refuerza el corazón minero sin saturar de peticiones
    ubicaciones = [
        "Chile",
        "Antofagasta, Chile",
    ]

    stats = {
        "total_encontradas": 0,
        "nuevas": 0,
        "duplicadas": 0,
        "errores": 0,
        "detalle_errores": [],
    }

    # Pre-cargar el texto del CV para no releerlo en cada evaluación
    try:
        cv_data = leer_cv_pdf_integro()
        texto_cv = cv_data["texto"]
    except Exception as e:
        stats["detalle_errores"].append(f"Error leyendo CV: {e}")
        return stats

    for cargo in cargos:
        for ubicacion in ubicaciones:
            if callback_progreso:
                callback_progreso(
                    f"🔎 Buscando '{cargo}' en {ubicacion} "
                    f"({', '.join(portales)})..."
                )

            try:
                jobs_df = scrape_jobs(
                    site_name=portales,
                    search_term=cargo,
                    location=ubicacion,
                    results_wanted=resultados_por_cargo,
                    country_indeed="Chile",
                )

                if jobs_df is None or jobs_df.empty:
                    continue

                # Procesar cada oferta
                for _, row in jobs_df.iterrows():
                    try:
                        stats["total_encontradas"] += 1
                        row_dict = row.to_dict()

                        # Detectar portal de origen
                        portal_real = str(
                            row_dict.get("site", row_dict.get("source", "jobspy"))
                        ).lower()

                        oferta = _normalizar_oferta_jobspy(row_dict, portal_real)

                        # Generar hash para deduplicación
                        job_hash = generar_job_hash(
                            url=oferta["url"],
                            titulo=oferta["titulo"],
                            empresa=oferta["empresa"],
                            portal=oferta["portal"],
                        )
                        oferta["job_hash"] = job_hash

                        # REGLA DE AHORRO: verificar existencia ANTES de Gemini
                        if oferta_ya_existe(job_hash):
                            stats["duplicadas"] += 1
                            continue

                        # Evaluar con Gemini (reutilizando texto_cv)
                        if not oferta["descripcion_cruda"].strip():
                            stats["errores"] += 1
                            stats["detalle_errores"].append(
                                f"Oferta sin descripción: {oferta['titulo']}"
                            )
                            continue

                        if callback_progreso:
                            callback_progreso(
                                f"🤖 Evaluando: {oferta['titulo']} - {oferta['empresa']}"
                            )

                        evaluacion = evaluar_oferta_con_gemini(oferta, texto_cv)

                        # Guardar en Supabase
                        guardar_oferta_evaluada(oferta, evaluacion)
                        stats["nuevas"] += 1

                    except Exception as e:
                        stats["errores"] += 1
                        stats["detalle_errores"].append(
                            f"Error procesando oferta: {e}"
                        )

            except Exception as e:
                stats["errores"] += 1
                stats["detalle_errores"].append(
                    f"Error en búsqueda '{cargo}' / {ubicacion}: {e}\n"
                    f"{traceback.format_exc()}"
                )

    return stats
