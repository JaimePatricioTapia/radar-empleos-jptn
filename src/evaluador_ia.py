"""
src/evaluador_ia.py — Capa 4: Motor Evaluador Semántico (Gemini 2.5 Flash + Pydantic)

Compara ofertas nuevas contra el texto íntegro del PDF del CV.
Devuelve evaluación estructurada con puntaje, veredicto y recomendaciones.
"""

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# Esquema Pydantic de la evaluación
# ---------------------------------------------------------------------------

class EvaluacionOferta(BaseModel):
    """Estructura de la evaluación semántica de una oferta laboral."""
    score_match: int = Field(ge=0, le=100, description="Porcentaje de calce 0-100")
    veredicto: Literal["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"]
    rol_detectado: str = Field(description="Rol/cargo real que solicita la oferta")
    renta_estimada_empresa: str = Field(description="Rango salarial estimado del cargo en Chile")
    pretension_sugerida: str = Field(description="Pretensión salarial sugerida (punto dulce)")
    enfoque_cv_sugerido: str = Field(description="Cómo enfocar el CV para esta postulación")
    fortalezas: list[str] = Field(description="Fortalezas del candidato frente a la oferta")
    brechas: list[str] = Field(description="Brechas o debilidades frente a la oferta")
    keywords_ats: list[str] = Field(description="Keywords ATS que debe incluir en el CV")


# ---------------------------------------------------------------------------
# System Prompt del evaluador
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres un evaluador experto en empleabilidad del mercado laboral chileno.
Tu tarea es comparar una oferta laboral contra el Currículum Vitae íntegro del candidato
y producir una evaluación estructurada en JSON.

REGLAS OBLIGATORIAS:

1. MODO SOBREVIVENCIA — NO descartar por menor seniority:
   - Si el candidato puede ejecutar el trabajo (aunque la oferta sea de nivel Analista,
     Coordinador, Ejecutivo, Control de Gestión, Analista Funcional, etc.), clasificar
     como POSTULAR o POSTULAR CON RESERVAS.
   - El candidato busca empleo activamente y necesita oportunidades reales.

2. EXCLUSIONES DURAS — Marcar DESCARTAR únicamente ante:
   - Programación pura de carrera (Software Engineer Senior tradicional / desarrollo backend-frontend puro)
   - Arquitecto Cloud puro (AWS/Azure/GCP Solutions Architect de carrera)
   - DevOps puro (SRE, Infrastructure Engineer de carrera)
   - Inglés conversacional excluyente (cuando la oferta requiere inglés avanzado/nativo como requisito eliminatorio)

3. BONIFICACIÓN SECTOR MINERO-TECNOLÓGICO:
   - El candidato es Ingeniero Civil de Minas con experiencia comprobada en transformación
     digital, Business Analysis, IA y gestión ágil. Este perfil híbrido es EXTREMADAMENTE
     RARO en el mercado chileno.
   - Si la oferta combina MINERÍA + TECNOLOGÍA (transformación digital, IA, automatización,
     sistemas de información, gestión de proyectos TI en minería), otorgar un BONUS de
     +10 a +15 puntos en el score_match, ya que el candidato tiene una ventaja competitiva
     diferenciadora sobre otros postulantes.
   - Ejemplos de roles bonificados: Business Analyst en minería, Ingeniero de Transformación
     Digital minero, Especialista TI en faena, Project Manager TI en compañías mineras,
     Analista Funcional para proyectos de integración en minería, Coordinador de proyectos
     tecnológicos en minería.
   - Empresas del sector donde aplicar bonus: consultoras que prestan servicios a mineras
     (VMICA, Turner & Townsend, Arcadis, CyD Ingeniería, Bechtel, Worley, Hatch, Ausenco),
     mineras directas (CODELCO, BHP, Antofagasta Minerals, SQM, Anglo American, Teck,
     Freeport-McMoRan, Lundin Mining), y proveedores tecnológicos mineros (ABB, Siemens,
     Schneider Electric, Hexagon Mining, Epiroc, Komatsu, Caterpillar/Finning).

4. TASACIÓN SALARIAL:
   - `renta_estimada_empresa`: Estima el rango salarial real que la empresa pagaría por
     este cargo en Chile (líquido mensual CLP), considerando el mercado, tamaño de empresa
     y responsabilidades.
   - `pretension_sugerida`: Fija la pretensión del candidato en el "punto dulce"
     (mitad inferior a media del rango), para maximizar competitividad.
   - Para cargos en MINERÍA: considerar que los salarios del sector minero en Chile son
     típicamente 20-40% superiores al promedio del mercado TI general, especialmente en
     roles presenciales en faena o con turnos rotativos.

5. KEYWORDS ATS: Extrae las keywords que los sistemas ATS buscarán en el CV del candidato
   para pasar los filtros automáticos de esta oferta específica.

6. ENFOQUE CV SUGERIDO: Indica específicamente qué experiencias, logros y competencias
   del CV debe destacar el candidato para esta oferta particular.
   - Para ofertas del SECTOR MINERO: destacar explícitamente el título de Ingeniero Civil
     de Minas, la comprensión de procesos operacionales mineros, y la capacidad de traducir
     necesidades del negocio minero a soluciones tecnológicas.

7. El score_match debe reflejar honestamente el calce real: 0-30 bajo, 31-50 parcial,
   51-70 moderado, 71-85 alto, 86-100 excelente. Aplicar la bonificación minera DESPUÉS
   de la evaluación base, sin superar 100.
"""


# ---------------------------------------------------------------------------
# Función principal de evaluación
# ---------------------------------------------------------------------------

def evaluar_oferta_con_gemini(
    oferta_raw: dict,
    texto_cv: str | None = None,
) -> dict:
    """Evalúa una oferta laboral contra el CV usando Gemini 2.5 Flash.

    Args:
        oferta_raw: dict con la oferta (titulo, empresa, descripcion_cruda, etc.)
        texto_cv: Texto íntegro del CV. Si es None, se lee desde el PDF.

    Returns:
        dict con la estructura de EvaluacionOferta.
    """
    # Cargar texto del CV si no se proporciona
    if texto_cv is None:
        from src.lector_cv import leer_cv_pdf_integro
        cv_data = leer_cv_pdf_integro()
        texto_cv = cv_data["texto"]

    # Construir prompt del usuario
    user_prompt = f"""CURRÍCULUM VITAE DEL CANDIDATO:
{texto_cv}

---

OFERTA LABORAL A EVALUAR:
- Título: {oferta_raw.get('titulo', 'No especificado')}
- Empresa: {oferta_raw.get('empresa', 'No especificada')}
- Ubicación: {oferta_raw.get('ubicacion', 'No especificada')}
- Modalidad: {oferta_raw.get('modalidad', 'No especificada')}
- Portal: {oferta_raw.get('portal', 'No especificado')}
- Descripción completa:
{oferta_raw.get('descripcion_cruda', 'Sin descripción disponible')}

Evalúa esta oferta contra el CV del candidato siguiendo las reglas establecidas.
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
        raise ValueError(
            "No se encontró GEMINI_API_KEY. Si estás en Streamlit Cloud, "
            "configúrala en el menú 'Settings > Secrets' de tu aplicación."
        )

    client = genai.Client(api_key=api_key)

    # Modelos con alta disponibilidad y cuota generosa
    modelos = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
    ]
    ultimo_error = None

    for m in modelos:
        try:
            response = client.models.generate_content(
                model=m,
                contents=user_prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": EvaluacionOferta,
                },
            )
            evaluacion = EvaluacionOferta.model_validate_json(response.text)
            return evaluacion.model_dump()
        except Exception as e:
            ultimo_error = e
            continue

    raise ultimo_error
