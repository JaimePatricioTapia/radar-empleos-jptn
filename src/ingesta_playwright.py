"""
src/ingesta_playwright.py — Capa 2 Vía B: Ingesta con Playwright (Sesión Persistente)

Navegación en portales chilenos (Laborum, Trabajando.com) usando sesión
persistente para login manual único y scraping posterior con pausas humanas.
"""

import argparse
import random
import re
import sys
import time
import traceback

from src.database import generar_job_hash, oferta_ya_existe, guardar_oferta_evaluada
from src.evaluador_ia import evaluar_oferta_con_gemini
from src.lector_cv import leer_cv_pdf_integro

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
BROWSER_SESSION_DIR = "./browser_session"

PORTALES_CONFIG = {
    "laborum": {
        "login_url": "https://www.laborum.cl/login",
        "search_url_template": "https://www.laborum.cl/empleos-busqueda-{cargo}.html",
        "selectors": {
            "job_card": '[class*="aviso"], [data-testid="search-result"]',
            "titulo": 'h2 a, [class*="titulo"] a',
            "empresa": '[class*="empresa"], [class*="company"]',
            "ubicacion": '[class*="ubicacion"], [class*="location"]',
            "url": 'h2 a, [class*="titulo"] a',
            "descripcion": '[class*="descripcion"], [class*="description"]',
        },
    },
    "trabajando": {
        "login_url": "https://www.trabajando.cl/login",
        "search_url_template": "https://www.trabajando.cl/trabajo-empleo/{cargo}",
        "selectors": {
            "job_card": '[class*="job-card"], [class*="aviso"]',
            "titulo": 'h2 a, [class*="title"] a',
            "empresa": '[class*="company"], [class*="empresa"]',
            "ubicacion": '[class*="location"], [class*="ubicacion"]',
            "url": 'h2 a, [class*="title"] a',
            "descripcion": '[class*="description"], [class*="descripcion"]',
        },
    },
}


def _pausa_humana(min_seg: float = 5.0, max_seg: float = 11.0):
    """Pausa aleatoria entre acciones para simular comportamiento humano."""
    espera = random.uniform(min_seg, max_seg)
    time.sleep(espera)


def _normalizar_cargo_url(cargo: str) -> str:
    """Convierte un cargo a formato URL-friendly."""
    cargo_limpio = re.sub(r"[^a-záéíóúñü\s]", "", cargo.lower())
    return cargo_limpio.strip().replace(" ", "-")


# ---------------------------------------------------------------------------
# Modo LOGIN: sesión persistente para inicio de sesión manual
# ---------------------------------------------------------------------------

def ejecutar_modo_login(portales: list[str] | None = None):
    """Abre navegador persistente para login manual en portales.

    Uso: python -m src.ingesta_playwright --modo login
    El usuario inicia sesión manualmente. Las cookies se guardan en
    ./browser_session/ para reutilizarse en modo búsqueda.
    """
    from playwright.sync_api import sync_playwright

    if portales is None:
        portales = list(PORTALES_CONFIG.keys())

    print("=" * 60)
    print("🔑 MODO LOGIN — Sesión Persistente")
    print("=" * 60)
    print(f"📁 Directorio de sesión: {BROWSER_SESSION_DIR}")
    print(f"🌐 Portales: {', '.join(portales)}")
    print()
    print("Instrucciones:")
    print("1. Se abrirá un navegador para cada portal.")
    print("2. Inicia sesión manualmente en cada uno.")
    print("3. Cierra el navegador cuando termines.")
    print("=" * 60)

    with sync_playwright() as p:
        for portal_name in portales:
            config = PORTALES_CONFIG.get(portal_name)
            if not config:
                print(f"⚠️  Portal '{portal_name}' no configurado. Saltando...")
                continue

            print(f"\n🔓 Abriendo {portal_name.upper()}...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_SESSION_DIR,
                headless=False,
                viewport={"width": 1280, "height": 800},
            )

            page = context.new_page()
            page.goto(config["login_url"], wait_until="domcontentloaded")
            print(f"   → Navega a {config['login_url']}")
            print(f"   → Inicia sesión y luego CIERRA el navegador para continuar.")

            # Esperar a que el usuario cierre
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass

            context.close()
            print(f"   ✅ Sesión de {portal_name.upper()} guardada.")

    print("\n✅ Login completado. Usa --modo buscar para iniciar el scraping.")


# ---------------------------------------------------------------------------
# Modo BUSCAR: scraping con sesión reutilizada
# ---------------------------------------------------------------------------

def ejecutar_busqueda_playwright(
    cargos: list[str],
    portales: list[str] | None = None,
    callback_progreso=None,
) -> dict:
    """Ejecuta scraping en portales chilenos con sesión persistente.

    Args:
        cargos: Lista de cargos a buscar.
        portales: Lista de portales (default: todos los configurados).
        callback_progreso: Función opcional para reportar progreso.

    Returns:
        dict con estadísticas: total_encontradas, nuevas, duplicadas, errores.
    """
    from playwright.sync_api import sync_playwright

    if portales is None:
        portales = list(PORTALES_CONFIG.keys())

    stats = {
        "total_encontradas": 0,
        "nuevas": 0,
        "duplicadas": 0,
        "errores": 0,
        "detalle_errores": [],
    }

    # Pre-cargar CV
    try:
        cv_data = leer_cv_pdf_integro()
        texto_cv = cv_data["texto"]
    except Exception as e:
        stats["detalle_errores"].append(f"Error leyendo CV: {e}")
        return stats

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_SESSION_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        for portal_name in portales:
            config = PORTALES_CONFIG.get(portal_name)
            if not config:
                continue

            for cargo in cargos:
                cargo_url = _normalizar_cargo_url(cargo)
                search_url = config["search_url_template"].format(cargo=cargo_url)

                if callback_progreso:
                    callback_progreso(
                        f"🔎 Buscando '{cargo}' en {portal_name.upper()}..."
                    )

                try:
                    page = context.new_page()
                    _pausa_humana(3.0, 6.0)

                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    _pausa_humana()

                    # Extraer tarjetas de ofertas
                    selectors = config["selectors"]
                    cards = page.query_selector_all(selectors["job_card"])

                    for card in cards:
                        try:
                            stats["total_encontradas"] += 1

                            # Extraer datos de la tarjeta
                            titulo_el = card.query_selector(selectors["titulo"])
                            empresa_el = card.query_selector(selectors["empresa"])
                            ubicacion_el = card.query_selector(selectors["ubicacion"])
                            url_el = card.query_selector(selectors["url"])

                            titulo = titulo_el.inner_text().strip() if titulo_el else ""
                            empresa = empresa_el.inner_text().strip() if empresa_el else ""
                            ubicacion = ubicacion_el.inner_text().strip() if ubicacion_el else ""
                            url_oferta = url_el.get_attribute("href") if url_el else ""

                            if not titulo or not url_oferta:
                                continue

                            # Completar URL relativa
                            if url_oferta.startswith("/"):
                                from urllib.parse import urlparse
                                base = urlparse(search_url)
                                url_oferta = f"{base.scheme}://{base.netloc}{url_oferta}"

                            # Obtener descripción visitando la página de detalle
                            descripcion = ""
                            try:
                                _pausa_humana(2.0, 5.0)
                                detail_page = context.new_page()
                                detail_page.goto(
                                    url_oferta,
                                    wait_until="domcontentloaded",
                                    timeout=20000,
                                )
                                _pausa_humana(2.0, 4.0)

                                desc_el = detail_page.query_selector(
                                    selectors["descripcion"]
                                )
                                if desc_el:
                                    descripcion = desc_el.inner_text().strip()
                                else:
                                    # Fallback: tomar texto principal
                                    descripcion = (
                                        detail_page.query_selector("main")
                                        or detail_page.query_selector("body")
                                    )
                                    if descripcion:
                                        descripcion = descripcion.inner_text().strip()[:3000]
                                    else:
                                        descripcion = ""

                                detail_page.close()
                            except Exception:
                                descripcion = titulo  # Fallback mínimo

                            oferta = {
                                "titulo": titulo,
                                "empresa": empresa,
                                "ubicacion": ubicacion,
                                "modalidad": "",
                                "url": url_oferta,
                                "portal": portal_name,
                                "descripcion_cruda": descripcion,
                                "fecha_publicacion": "",
                            }

                            # Hash y deduplicación
                            job_hash = generar_job_hash(
                                url=url_oferta,
                                titulo=titulo,
                                empresa=empresa,
                                portal=portal_name,
                            )
                            oferta["job_hash"] = job_hash

                            if oferta_ya_existe(job_hash):
                                stats["duplicadas"] += 1
                                continue

                            if not descripcion.strip():
                                stats["errores"] += 1
                                continue

                            if callback_progreso:
                                callback_progreso(
                                    f"🤖 Evaluando: {titulo} - {empresa}"
                                )

                            evaluacion = evaluar_oferta_con_gemini(oferta, texto_cv)
                            guardar_oferta_evaluada(oferta, evaluacion)
                            stats["nuevas"] += 1

                        except Exception as e:
                            stats["errores"] += 1
                            stats["detalle_errores"].append(
                                f"Error en tarjeta {portal_name}: {e}"
                            )

                    page.close()

                except Exception as e:
                    stats["errores"] += 1
                    stats["detalle_errores"].append(
                        f"Error navegando {portal_name}/{cargo}: {e}\n"
                        f"{traceback.format_exc()}"
                    )

        context.close()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingesta de portales chilenos con Playwright"
    )
    parser.add_argument(
        "--modo",
        choices=["login", "buscar"],
        required=True,
        help="'login' para iniciar sesión manual, 'buscar' para scraping.",
    )
    parser.add_argument(
        "--portales",
        nargs="+",
        default=None,
        help="Portales a usar (default: todos).",
    )
    parser.add_argument(
        "--cargos",
        nargs="+",
        default=None,
        help="Cargos a buscar (solo modo buscar).",
    )

    args = parser.parse_args()

    if args.modo == "login":
        ejecutar_modo_login(args.portales)
    elif args.modo == "buscar":
        if not args.cargos:
            print("⚠️  Debes especificar --cargos en modo buscar.")
            print("Ejemplo: python -m src.ingesta_playwright --modo buscar --cargos 'Analista de Datos'")
            sys.exit(1)

        def _print_progreso(msg):
            print(f"  {msg}")

        result = ejecutar_busqueda_playwright(
            cargos=args.cargos,
            portales=args.portales,
            callback_progreso=_print_progreso,
        )
        print(f"\n📊 Resultados: {result}")
