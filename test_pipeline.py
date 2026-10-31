"""
test_pipeline.py — Script CLI de verificación del pipeline completo

Ejecuta 4 pruebas secuenciales:
1. Localización y lectura del PDF del CV.
2. Extracción/lectura en caché de la estrategia de búsqueda con Gemini.
3. Conexión y consulta a Supabase.
4. Evaluación de una oferta simulada y almacenamiento en Supabase.
"""

import json
import sys

from dotenv import load_dotenv

load_dotenv()


def separador(titulo: str):
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}")


def test_1_lectura_pdf():
    """Prueba 1: Localizar y leer el PDF del CV."""
    separador("PRUEBA 1: Lectura del PDF del CV")

    from src.lector_cv import localizar_archivo_cv_pdf, leer_cv_pdf_integro

    try:
        ruta = localizar_archivo_cv_pdf()
        print(f"  ✅ PDF localizado: {ruta}")
        print(f"     Nombre: {ruta.name}")
        print(f"     Tamaño: {ruta.stat().st_size:,} bytes")

        cv_data = leer_cv_pdf_integro(ruta)
        print(f"  ✅ Texto extraído: {len(cv_data['texto']):,} caracteres")
        print(f"     Hash SHA-256: {cv_data['hash'][:16]}...")
        print(f"     Actualizado: {cv_data['actualizado']}")
        print(f"     Primeros 200 chars: {cv_data['texto'][:200]}...")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_2_estrategia_busqueda():
    """Prueba 2: Obtener estrategia de búsqueda (caché o Gemini)."""
    separador("PRUEBA 2: Estrategia de Búsqueda (CV → Gemini)")

    from src.lector_cv import obtener_estrategia_busqueda_desde_cv

    try:
        estrategia = obtener_estrategia_busqueda_desde_cv()
        print(f"  ✅ Estrategia obtenida:")
        print(f"     Resumen: {estrategia['resumen_ejecutivo_detectado'][:100]}...")
        print(f"     Cargos objetivo ({len(estrategia['cargos_objetivo_busqueda'])}):")
        for i, cargo in enumerate(estrategia["cargos_objetivo_busqueda"], 1):
            print(f"       {i}. {cargo}")
        print(f"     Keywords técnicas: {len(estrategia['keywords_tecnicas'])}")
        print(f"       → {', '.join(estrategia['keywords_tecnicas'][:5])}...")
        print(f"     Líneas rojas: {len(estrategia['lineas_rojas_detectadas'])}")
        for lr in estrategia["lineas_rojas_detectadas"]:
            print(f"       ⚠️  {lr}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_3_conexion_supabase():
    """Prueba 3: Conexión y consulta a Supabase."""
    separador("PRUEBA 3: Conexión a Supabase")

    from src.database import obtener_metricas_resumen, obtener_ofertas_filtradas

    try:
        metricas = obtener_metricas_resumen()
        print(f"  ✅ Conexión exitosa a Supabase")
        print(f"     Métricas actuales:")
        print(f"       • Ofertas totales: {metricas['ofertas_totales']}")
        print(f"       • Recomendadas (Postular): {metricas['recomendadas_postular']}")
        print(f"       • Postulados: {metricas['postulados']}")
        print(f"       • Por revisar: {metricas['por_revisar']}")

        ofertas = obtener_ofertas_filtradas(score_minimo=0)
        print(f"     Ofertas en base de datos: {len(ofertas)}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_4_evaluacion_simulada():
    """Prueba 4: Evaluación de una oferta simulada con Gemini."""
    separador("PRUEBA 4: Evaluación Simulada (Gemini + Supabase)")

    from src.evaluador_ia import evaluar_oferta_con_gemini
    from src.database import generar_job_hash, oferta_ya_existe, guardar_oferta_evaluada

    oferta_simulada = {
        "titulo": "Analista de Gestión y Control de Proyectos TI",
        "empresa": "Empresa Simulada Test SpA",
        "ubicacion": "Santiago, Chile",
        "modalidad": "Híbrido",
        "url": "https://test-pipeline.example.com/oferta-simulada-12345",
        "portal": "test_pipeline",
        "descripcion_cruda": (
            "Buscamos un profesional con experiencia en gestión de proyectos TI, "
            "control de gestión, análisis de indicadores KPI, elaboración de reportes "
            "ejecutivos, seguimiento presupuestario y coordinación con equipos técnicos. "
            "Requisitos: Ingeniería Civil Industrial, Informática o carrera afín. "
            "Experiencia mínima de 3 años en roles similares. Conocimiento en metodologías "
            "ágiles, PMO, herramientas como Jira, Confluence, Excel avanzado, Power BI. "
            "Deseable experiencia en el sector financiero o telecomunicaciones. "
            "Ofrecemos: Renta competitiva de mercado, beneficios de salud, "
            "trabajo híbrido 3 días presencial / 2 remoto."
        ),
        "fecha_publicacion": "2025-01-15",
    }

    try:
        # Generar hash
        job_hash = generar_job_hash(
            url=oferta_simulada["url"],
            titulo=oferta_simulada["titulo"],
            empresa=oferta_simulada["empresa"],
            portal=oferta_simulada["portal"],
        )
        oferta_simulada["job_hash"] = job_hash
        print(f"  📝 Job hash: {job_hash[:16]}...")

        # Verificar existencia
        if oferta_ya_existe(job_hash):
            print(f"  ℹ️  La oferta simulada ya existe en Supabase (deduplicación OK)")
            return True

        # Evaluar con Gemini
        print(f"  🤖 Enviando a Gemini para evaluación...")
        evaluacion = evaluar_oferta_con_gemini(oferta_simulada)
        print(f"  ✅ Evaluación recibida:")
        print(f"     Score: {evaluacion['score_match']}%")
        print(f"     Veredicto: {evaluacion['veredicto']}")
        print(f"     Rol detectado: {evaluacion['rol_detectado']}")
        print(f"     Renta estimada: {evaluacion['renta_estimada_empresa']}")
        print(f"     Pretensión sugerida: {evaluacion['pretension_sugerida']}")
        print(f"     Fortalezas: {len(evaluacion['fortalezas'])}")
        print(f"     Brechas: {len(evaluacion['brechas'])}")
        print(f"     Keywords ATS: {evaluacion['keywords_ats']}")

        # Guardar en Supabase
        print(f"  💾 Guardando en Supabase...")
        registro = guardar_oferta_evaluada(oferta_simulada, evaluacion)
        print(f"  ✅ Oferta guardada exitosamente")
        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------------------

def main():
    print("\n" + "🔍" * 20)
    print("  RADAR DE EMPLEOS JPTN — Pipeline de Verificación")
    print("🔍" * 20)

    resultados = {}
    resultados["1_PDF"] = test_1_lectura_pdf()
    resultados["2_Estrategia"] = test_2_estrategia_busqueda()
    resultados["3_Supabase"] = test_3_conexion_supabase()
    resultados["4_Evaluacion"] = test_4_evaluacion_simulada()

    # Resumen
    separador("RESUMEN DE RESULTADOS")
    todas_ok = True
    for nombre, resultado in resultados.items():
        emoji = "✅" if resultado else "❌"
        print(f"  {emoji} {nombre}: {'PASS' if resultado else 'FAIL'}")
        if not resultado:
            todas_ok = False

    print()
    if todas_ok:
        print("  🎉 ¡Todas las pruebas pasaron! El pipeline está listo.")
        print("  Ejecuta: streamlit run app.py")
    else:
        print("  ⚠️  Algunas pruebas fallaron. Revisa la configuración.")

    return 0 if todas_ok else 1


if __name__ == "__main__":
    sys.exit(main())
