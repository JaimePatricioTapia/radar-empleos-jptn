"""
app.py — Capa 5: Dashboard de Control Operativo (Streamlit)

Interfaz ejecutiva en tema oscuro con métricas KPI, diagnóstico del PDF,
selector dinámico de cargos, filtros avanzados y tarjetas de ofertas con
cambio de estado directo en Supabase.
"""

import json
import streamlit as st

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Radar de Empleos JPTN",
    page_icon="🔍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS personalizado (tema oscuro + tarjetas estilizadas)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #3d3d5c;
        margin-bottom: 10px;
    }
    .kpi-card .kpi-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 5px 0;
    }
    .kpi-card .kpi-label {
        font-size: 0.85rem;
        color: #a0a0b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .kpi-green .kpi-value { color: #4ade80; }
    .kpi-blue .kpi-value { color: #60a5fa; }
    .kpi-orange .kpi-value { color: #fb923c; }
    .kpi-white .kpi-value { color: #e2e8f0; }

    /* Offer Cards */
    .offer-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        border-left: 5px solid #666;
        border-top: 1px solid #3d3d5c;
        border-right: 1px solid #3d3d5c;
        border-bottom: 1px solid #3d3d5c;
    }
    .offer-card.postular { border-left-color: #4ade80; }
    .offer-card.reservas { border-left-color: #fb923c; }
    .offer-card.descartar { border-left-color: #f87171; }

    .offer-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
    }
    .offer-score {
        font-size: 1.8rem;
        font-weight: 700;
        min-width: 70px;
        text-align: center;
    }
    .offer-score.high { color: #4ade80; }
    .offer-score.medium { color: #fb923c; }
    .offer-score.low { color: #f87171; }

    .offer-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 4px;
    }
    .offer-meta {
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .offer-salary {
        background: #2d2d44;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 10px 0;
        display: flex;
        justify-content: space-between;
        font-size: 0.9rem;
    }
    .offer-section-title {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 10px;
        margin-bottom: 5px;
    }
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 2px;
    }
    .badge-green { background: #166534; color: #4ade80; }
    .badge-red { background: #7f1d1d; color: #fca5a5; }
    .badge-blue { background: #1e3a5f; color: #93c5fd; }

    /* CV Diagnostic Card */
    .cv-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 12px 14px;
        border: 1px solid #3d3d5c;
        margin-bottom: 12px;
    }
    .cv-status {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #166534;
        color: #4ade80;
    }

    /* Radar Scanning Active Banner */
    .radar-scanning {
        background: linear-gradient(90deg, #1e3a5f 0%, #1e1e2e 50%, #1e3a5f 100%);
        border: 1px solid #3b82f6;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 16px 0;
        text-align: center;
        animation: pulse-glow 2s infinite ease-in-out;
    }
    @keyframes pulse-glow {
        0% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.2); }
        50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
        100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.2); }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Imports del sistema (cargados después del config)
# ---------------------------------------------------------------------------
from src.lector_cv import (
    localizar_archivo_cv_pdf,
    leer_cv_pdf_integro,
    obtener_estrategia_busqueda_desde_cv,
)
from src.database import (
    obtener_metricas_resumen,
    obtener_ofertas_filtradas,
    actualizar_estado_oferta,
    generar_job_hash,
    guardar_oferta_evaluada,
)
from src.evaluador_ia import evaluar_oferta_con_gemini
from src.ingesta_jobspy import ejecutar_busqueda_jobspy
from src.ingesta_portales import (
    ejecutar_busqueda_getonbrd,
    ejecutar_busqueda_chiletrabajos,
    ejecutar_busqueda_bne,
)


# ---------------------------------------------------------------------------
# Inicialización de estado
# ---------------------------------------------------------------------------
if "cv_data" not in st.session_state:
    st.session_state.cv_data = None
if "estrategia" not in st.session_state:
    st.session_state.estrategia = None
if "busqueda_activa" not in st.session_state:
    st.session_state.busqueda_activa = False
if "undo_accion" not in st.session_state:
    st.session_state.undo_accion = None
if "pagina_actual" not in st.session_state:
    st.session_state.pagina_actual = 1


# ---------------------------------------------------------------------------
# Funciones auxiliares y Caché de Alto Rendimiento
# ---------------------------------------------------------------------------

@st.cache_data(ttl=25, show_spinner=False)
def _cargar_metricas_cache():
    return obtener_metricas_resumen()


@st.cache_data(ttl=25, show_spinner=False)
def _cargar_ofertas_cache(veredictos_tuple, score_minimo, estados_tuple, portales_tuple):
    veredictos = list(veredictos_tuple) if veredictos_tuple else None
    estados = list(estados_tuple) if estados_tuple else None
    portales = list(portales_tuple) if portales_tuple else None
    return obtener_ofertas_filtradas(
        veredictos=veredictos,
        score_minimo=score_minimo,
        estados=estados,
        portales=portales,
    )


def ejecutar_cambio_estado(oferta: dict, nuevo_estado: str):
    """Actualiza el estado de una oferta en Supabase, guarda la acción previa
    para deshacer en 1 clic y limpia la caché para una respuesta visual instantánea."""
    oferta_id = oferta.get("id")
    estado_previo = oferta.get("estado_postulacion", "NUEVA")
    if nuevo_estado == estado_previo:
        return

    try:
        actualizar_estado_oferta(oferta_id, nuevo_estado)
        # Registrar para deshacer inmediatamente
        st.session_state["undo_accion"] = {
            "id": oferta_id,
            "titulo": oferta.get("titulo", "Sin título"),
            "empresa": oferta.get("empresa", "Empresa no especificada"),
            "estado_anterior": estado_previo,
            "nuevo_estado": nuevo_estado,
        }
        # Invalidar caché local para reflejar el cambio en milisegundos
        _cargar_ofertas_cache.clear()
        _cargar_metricas_cache.clear()
        st.toast(f"✅ Oferta marcada como: {nuevo_estado}")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al actualizar estado: {e}")


def cargar_cv():
    """Carga el CV y la estrategia de búsqueda."""
    try:
        st.session_state.cv_data = leer_cv_pdf_integro()
        st.session_state.estrategia = obtener_estrategia_busqueda_desde_cv()
        return True
    except Exception as e:
        st.error(f"❌ Error cargando CV: {e}")
        return False


def es_oferta_mineria(oferta: dict) -> bool:
    """Detecta si una oferta pertenece al sector minero o afines.

    Estrategia por niveles para evitar falsos positivos:
    - Nivel 1 (título + empresa): términos amplios con word-boundary regex
    - Nivel 2 (descripción cruda): solo términos altamente específicos de minería
    - EXCLUYE: enfoque_cv_sugerido (sesgado por CV del usuario)
    """
    import re

    titulo = str(oferta.get("titulo", "")).lower()
    empresa = str(oferta.get("empresa", "")).lower()
    rol = str(oferta.get("rol_detectado", "")).lower()
    descripcion = str(oferta.get("descripcion_cruda", "")).lower()[:800]

    # --- Nivel 1: Título + Empresa + Rol (alta confianza) ---
    texto_nivel1 = f"{titulo} {empresa} {rol}"

    # Términos generales de minería (con word-boundary para evitar falsos positivos)
    terminos_generales_wb = [
        r"\bminería\b", r"\bmineria\b", r"\bminero\b", r"\bminera\b",
        r"\bmining\b", r"\bfaena\b", r"\brajo\b", r"\bmina\b",
    ]

    # Empresas mineras conocidas (match exacto en empresa, sin word-boundary)
    empresas_mineras = [
        "codelco", "bhp", "antofagasta minerals", "sqm", "anglo american",
        "teck", "collahuasi", "escondida", "pelambres", "centinela",
        "candelaria", "freeport", "albemarle", "vmica", "ausenco",
        "bechtel", "flsmidth", "metso", "komatsu", "finning", "liebherr",
        "veridapt", "cyd ingeniería", "cyd ingenieria",
        "turner & townsend", "turner and townsend",
    ]

    # Empresas ambiguas: solo matchear si aparecen en el campo "empresa"
    empresas_ambiguas = ["hatch", "wood", "worley", "cyd"]

    # Check nivel 1: términos generales con word-boundary en título+empresa+rol
    for patron in terminos_generales_wb:
        if re.search(patron, texto_nivel1):
            return True

    # Check nivel 1: empresas mineras conocidas en empresa
    for emp in empresas_mineras:
        if emp in empresa:
            return True

    # Check nivel 1: empresas ambiguas SOLO en campo empresa (no en descripción)
    for emp in empresas_ambiguas:
        if re.search(rf"\b{re.escape(emp)}\b", empresa):
            return True

    # --- Nivel 2: Descripción (baja confianza, solo términos muy específicos) ---
    terminos_especificos = [
        r"\bconcentradora\b", r"\blixiviación\b", r"\blixiviacion\b",
        r"\bfundición\b", r"\bfundicion\b", r"\brelave[s]?\b",
        r"\bflotación\b", r"\bflotacion\b", r"\bchancado\b",
        r"\bsubterránea\b", r"\bsubterranea\b", r"\brajo\b",
        r"\bcodelco\b", r"\bbhp\b", r"\bsqm\b", r"\bescondida\b",
        r"\bcollahuasi\b", r"\bpelambres\b", r"\bantofagasta minerals\b",
        r"\bgeología\b", r"\bgeologia\b", r"\bmetalurgia\b",
        r"\bhidrometalurgia\b", r"\bpirometalurgia\b",
        r"\bplanta minera\b", r"\bsector minero\b",
        r"\bindustria minera\b", r"\boperación minera\b",
        r"\boperacion minera\b", r"\bproyecto minero\b",
    ]

    for patron in terminos_especificos:
        if re.search(patron, descripcion):
            return True

    return False


def render_kpi_card(label: str, value, css_class: str = "kpi-white"):
    """Renderiza una tarjeta KPI con estilos."""
    html_kpi = (
        f'<div class="kpi-card {css_class}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>'
    )
    st.markdown(html_kpi, unsafe_allow_html=True)


def render_offer_card(oferta: dict):
    """Renderiza una tarjeta de oferta laboral estilizada."""
    score = oferta.get("score_match", 0) or 0
    veredicto = str(oferta.get("veredicto", "")).upper()

    # Clases CSS según veredicto
    card_class = "descartar"
    if "POSTULAR" == veredicto:
        card_class = "postular"
    elif "RESERVAS" in veredicto:
        card_class = "reservas"

    score_class = "low"
    if score >= 70:
        score_class = "high"
    elif score >= 50:
        score_class = "medium"

    # Datos
    titulo = oferta.get("titulo", "Sin título")
    empresa = oferta.get("empresa", "No especificada")
    ubicacion = oferta.get("ubicacion", "")
    modalidad = oferta.get("modalidad", "")
    portal = oferta.get("portal", "")
    url = oferta.get("url", "")
    renta_est = oferta.get("renta_estimada_empresa", "No estimada")
    pretension = oferta.get("pretension_sugerida", "No estimada")
    enfoque = oferta.get("enfoque_cv_sugerido", "")
    fortalezas = oferta.get("fortalezas", [])
    brechas = oferta.get("brechas", [])
    keywords = oferta.get("keywords_ats", [])

    # Parsear JSON si es string
    if isinstance(fortalezas, str):
        try:
            fortalezas = json.loads(fortalezas)
        except json.JSONDecodeError:
            fortalezas = []
    if isinstance(brechas, str):
        try:
            brechas = json.loads(brechas)
        except json.JSONDecodeError:
            brechas = []
    if isinstance(keywords, str):
        try:
            keywords = json.loads(keywords)
        except json.JSONDecodeError:
            keywords = []

    # Construir Badges
    fortalezas_html = "".join(
        f'<span class="badge badge-green">✓ {f}</span> ' for f in fortalezas[:5]
    )
    brechas_html = "".join(
        f'<span class="badge badge-red">✗ {b}</span> ' for b in brechas[:5]
    )
    keywords_html = "".join(
        f'<span class="badge badge-blue">{k}</span> ' for k in keywords[:8]
    )

    # Limpiar metadata (evitar "nan")
    meta_parts = [
        str(p).strip() for p in [empresa, ubicacion, modalidad, portal.upper()]
        if p and str(p).lower() not in ("nan", "none", "")
    ]
    meta_str = " · ".join(meta_parts)

    mineria_badge = (
        '<span class="badge" style="background:#78350f; color:#fef3c7; border:1px solid #d97706; font-size:0.75rem; vertical-align:middle; margin-right:6px;">⛏️ MINERÍA</span>'
        if es_oferta_mineria(oferta) else ""
    )

    card_html = (
        f'<div class="offer-card {card_class}">'
        f'<div class="offer-header">'
        f'<div><div class="offer-title">{mineria_badge}{titulo}</div><div class="offer-meta">{meta_str}</div></div>'
        f'<div class="offer-score {score_class}">{score}%</div>'
        f'</div>'
        f'<div class="offer-salary">'
        f'<span>💰 Renta estimada: <strong>{renta_est}</strong></span>'
        f'<span>🎯 Pretensión sugerida: <strong>{pretension}</strong></span>'
        f'</div>'
        f'<div class="offer-section-title">🎯 Enfoque CV sugerido</div>'
        f'<div style="font-size: 0.88rem; color: #cbd5e1; margin-bottom: 8px;">{enfoque}</div>'
        f'<div class="offer-section-title">✅ Fortalezas</div>'
        f'<div>{fortalezas_html or "<span style=\'color:#666;\'>—</span>"}</div>'
        f'<div class="offer-section-title">⚠️ Brechas</div>'
        f'<div>{brechas_html or "<span style=\'color:#666;\'>—</span>"}</div>'
        f'<div class="offer-section-title">🔑 Keywords ATS</div>'
        f'<div>{keywords_html or "<span style=\'color:#666;\'>—</span>"}</div>'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

    return url


# =====================================================================
# BARRA LATERAL (Panel Ergonómico de Control)
# =====================================================================
with st.sidebar:
    st.title("⚙️ Radar de Control")

    # ----- 1. SECCIÓN INGESTA & RASTREO -----
    st.markdown("### 🚀 Rastreo e Ingesta")

    # Diagnóstico del CV Maestro
    if st.session_state.cv_data is None:
        with st.spinner("Cargando CV..."):
            cargar_cv()

    if st.session_state.cv_data:
        cv = st.session_state.cv_data
        cv_hash_short = cv["hash"][:12]

        cv_html = (
            f'<div class="cv-card">'
            f'<strong>📁 {cv["nombre_archivo"]}</strong><br>'
            f'<span class="cv-status">● Activo</span><br>'
            f'<span style="font-size:0.75rem; color:#94a3b8;">'
            f'Actualizado: {cv["actualizado"][:10]} · '
            f'Hash: <code>{cv_hash_short}</code>'
            f'</span></div>'
        )
        st.markdown(cv_html, unsafe_allow_html=True)

        if st.button("🔄 Re-analizar PDF con IA", use_container_width=True):
            with st.spinner("Re-analizando CV con Gemini..."):
                try:
                    st.session_state.cv_data = leer_cv_pdf_integro()
                    st.session_state.estrategia = obtener_estrategia_busqueda_desde_cv(
                        forzar_recalculo=True
                    )
                    st.success("✅ CV re-analizado")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ No se pudo re-analizar el CV: {e}")
    else:
        st.error("❌ No se pudo cargar el CV. Verifica CV_PDF_PATH")

    # Cargos Objetivo (Selector ergonómico)
    cargos_disponibles = []
    if st.session_state.estrategia:
        cargos_disponibles = list(st.session_state.estrategia.get("cargos_objetivo_busqueda", []))

    # Incorporar cargos aprendidos desde el perfil de calibración si existen
    from src.calibrador_aprendizaje import (
        obtener_perfil_aprendizaje_cache,
        ejecutar_analisis_aprendizaje,
        cambiar_estado_activacion_aprendizaje,
    )
    perfil_aprendido = obtener_perfil_aprendizaje_cache()
    if perfil_aprendido and perfil_aprendido.get("nuevos_cargos_recomendados_busqueda"):
        for nc in perfil_aprendido["nuevos_cargos_recomendados_busqueda"]:
            if nc not in cargos_disponibles:
                cargos_disponibles.append(nc)

    st.markdown("#### 🎯 Cargos Objetivo")
    cargos_seleccionados = st.multiselect(
        "Cargos activos para la búsqueda:",
        options=cargos_disponibles,
        default=cargos_disponibles,
        placeholder="Selecciona uno o más cargos...",
        help="Cargos extraídos automáticamente por IA desde tu CV. Puedes remover o agregar."
    )

    # Opciones de Portales
    st.markdown("#### 🌐 Portales de Empleo")
    portales_disponibles = [
        "linkedin",
        "indeed",
        "google",
        "glassdoor",
        "bne",
        "chiletrabajos",
        "getonbrd",
        "laborum",
        "trabajando",
    ]
    portales_seleccionados = st.multiselect(
        "Plataformas activas:",
        options=portales_disponibles,
        default=["linkedin", "indeed", "google", "bne", "chiletrabajos", "getonbrd"],
        placeholder="Elige portales...",
    )

    # Botón Principal de Acción (CTA Prominente)
    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    btn_buscar = st.button(
        "🔍 Ejecutar Búsqueda en Portales",
        use_container_width=True,
        type="primary",
        disabled=not cargos_seleccionados or not portales_seleccionados,
    )
    if btn_buscar:
        st.session_state.busqueda_activa = True

    st.divider()

    # ----- 2. SECCIÓN FILTROS DE BIBLIOTECA -----
    st.markdown("### 📂 Filtros de Biblioteca")
    st.caption("Filtra las ofertas ya evaluadas y guardadas")

    filtro_veredicto = st.multiselect(
        "Veredicto",
        options=["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"],
        default=["POSTULAR", "POSTULAR CON RESERVAS"],
    )

    filtro_score = st.slider(
        "Score mínimo de calce (%)",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
    )

    filtro_estado = st.multiselect(
        "Estado de postulación",
        options=["NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"],
        default=["NUEVA", "GUARDADA"],
    )

    st.markdown("#### ⛏️ Priorización Sectorial")
    priorizar_mineria = st.checkbox(
        "⛏️ Priorizar Minería primero",
        value=True,
        help="Muestra primero las ofertas del sector minero ordenadas por afinidad (% match descendente), seguidas del resto también en afinidad descendente.",
    )
    solo_mineria = st.checkbox(
        "Solo sector Minero",
        value=False,
        help="Filtra y muestra exclusivamente oportunidades vinculadas a minería.",
    )


# =====================================================================
# ÁREA PRINCIPAL (Dashboard Ejecutivo)
# =====================================================================

# ----- 1. Encabezado -----
st.markdown("# 🔍 Radar de Empleos JPTN")
st.markdown(
    "*Sistema automatizado de descubrimiento, evaluación semántica "
    "y gestión de ofertas laborales asistido por IA*"
)

# ----- 2. Métricas KPI Siempre Visibles (Embudo de Conversión) -----
try:
    metricas = _cargar_metricas_cache()
except Exception:
    metricas = {
        "ofertas_totales": 0,
        "recomendadas_postular": 0,
        "postulados": 0,
        "descartadas": 0,
        "guardadas": 0,
        "por_revisar": 0,
    }

kcol1, kcol2, kcol3, kcol4 = st.columns(4)
with kcol1:
    render_kpi_card("Ofertas Totales", metricas.get("ofertas_totales", 0), "kpi-white")
with kcol2:
    render_kpi_card("Recomendadas (Postular)", metricas.get("recomendadas_postular", 0), "kpi-green")
with kcol3:
    render_kpi_card("Postulados", metricas.get("postulados", 0), "kpi-blue")
with kcol4:
    render_kpi_card("Por Revisar", metricas.get("por_revisar", 0), "kpi-orange")

st.divider()

# ----- 2.1 Ingesta Rápida / Evaluar Oferta Manual -----
with st.expander("📥 Evaluar Oferta Directa (Pegar URL o Texto de LinkedIn / Portal)", expanded=False):
    st.markdown(
        "¿Encontraste una oferta en LinkedIn, WhatsApp u otro portal? Pega los datos aquí "
        "para que Gemini la evalúe semánticamente contra tu CV completo y la guarde en tu radar."
    )
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        manual_titulo = st.text_input("Título del Cargo*", placeholder="Ej: Senior Business Analyst")
        manual_empresa = st.text_input("Empresa*", placeholder="Ej: BHP")
        manual_portal = st.selectbox("Portal de origen", ["linkedin", "indeed", "bne", "chiletrabajos", "getonbrd", "laborum", "trabajando", "otro"], index=0)
    with col_in2:
        manual_url = st.text_input("URL de la oferta (opcional)", placeholder="https://www.linkedin.com/jobs/view/...")
        manual_ubicacion = st.text_input("Ubicación", value="Santiago / Antofagasta, Chile", placeholder="Ej: Santiago, Antofagasta, Remoto")
        manual_modalidad = st.selectbox("Modalidad", ["Híbrido", "Remoto", "Presencial"], index=0)

    manual_descripcion = st.text_area(
        "Descripción o Requisitos de la Oferta*",
        placeholder="Pega aquí el texto de la oferta (responsabilidades, requisitos, acerca del empleo)...",
        height=150,
    )

    if st.button("🤖 Evaluar y Agregar al Radar con IA", key="btn_evaluar_manual", type="primary"):
        if not manual_titulo.strip() or not manual_empresa.strip() or not manual_descripcion.strip():
            st.warning("⚠️ Debes ingresar al menos el Título, Empresa y la Descripción de la oferta.")
        else:
            with st.spinner("🤖 Comparando oferta contra tu CV íntegro con Gemini..."):
                try:
                    cv_data = leer_cv_pdf_integro()
                    texto_cv = cv_data["texto"]

                    url_para_hash = manual_url.strip() if manual_url.strip() else f"manual_{manual_titulo}_{manual_empresa}"
                    job_hash = generar_job_hash(
                        url=url_para_hash,
                        titulo=manual_titulo.strip(),
                        empresa=manual_empresa.strip(),
                        portal=manual_portal,
                    )

                    oferta_manual = {
                        "job_hash": job_hash,
                        "portal": manual_portal,
                        "titulo": manual_titulo.strip(),
                        "empresa": manual_empresa.strip(),
                        "ubicacion": manual_ubicacion.strip(),
                        "modalidad": manual_modalidad,
                        "url": manual_url.strip(),
                        "descripcion_cruda": manual_descripcion.strip(),
                        "fecha_publicacion": "",
                    }

                    evaluacion = evaluar_oferta_con_gemini(oferta_manual, texto_cv)
                    guardar_oferta_evaluada(oferta_manual, evaluacion)

                    st.success(
                        f"🎉 ¡Oferta evaluada con éxito! Calce: {evaluacion.get('score_match', 0)}% "
                        f"({evaluacion.get('veredicto', '')}). Ya está en tu biblioteca."
                    )
                    _cargar_ofertas_cache.clear()
                    _cargar_metricas_cache.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al evaluar la oferta: {e}")

# ----- 2.2 Aprendizaje del Radar y Calibración Inteligente -----
with st.expander("🧠 Aprendizaje del Radar (Patrones de tus Postulaciones y Calibración)", expanded=False):
    perfil_apr = obtener_perfil_aprendizaje_cache()

    st.markdown(
        "El sistema analiza tus decisiones históricas (**POSTULADO** vs **DESCARTADA**) "
        "para descubrir tus verdaderas preferencias y calibrar automáticamente tanto las directrices de Gemini "
        "como los cargos sugeridos para búsqueda, sin necesidad de modelos pesados de Deep Learning."
    )

    col_ap1, col_ap2, col_ap3 = st.columns([1.5, 1.5, 2])
    with col_ap1:
        st.metric("Postuladas analizadas", perfil_apr.get("total_postuladas_analizadas", 0) if perfil_apr else 0)
    with col_ap2:
        st.metric("Descartadas analizadas", perfil_apr.get("total_descartadas_analizadas", 0) if perfil_apr else 0)
    with col_ap3:
        estado_activo = perfil_apr.get("activo", True) if perfil_apr else True
        toggle_calib = st.toggle(
            "Aplicar reglas aprendidas al evaluar",
            value=estado_activo,
            help="Si está activo, Gemini inyecta estas directrices al evaluar nuevas ofertas para premiar lo que te gusta y penalizar lo que sueles descartar.",
        )
        if perfil_apr and toggle_calib != estado_activo:
            cambiar_estado_activacion_aprendizaje(toggle_calib)
            st.toast("✅ Configuración de calibración actualizada")
            st.rerun()

    if st.button("🔄 Ejecutar Calibración / Re-analizar mis patrones con IA", type="primary", use_container_width=True):
        with st.spinner("🤖 Analizando ofertas postuladas vs descartadas con Gemini..."):
            try:
                perfil_apr = ejecutar_analisis_aprendizaje(forzar=True)
                st.success("🎉 ¡Calibración completada con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al calibrar: {e}")

    if perfil_apr:
        st.markdown("---")
        st.markdown("**💡 Diagnóstico de tus Hábitos y Preferencias Reales:**")
        st.info(perfil_apr.get("resumen_habitos_postulacion", ""))

        c_fav, c_desc = st.columns(2)
        with c_fav:
            st.markdown("#### 🎯 Criterios y Factores Favoritos")
            for crit in perfil_apr.get("criterios_favoritos", []):
                st.markdown(f"- ✅ **{crit}**")
            kw_pos = perfil_apr.get("keywords_clave_postuladas", [])
            if kw_pos:
                st.markdown("**Keywords clave postuladas:**")
                st.markdown(" ".join([f"`{k}`" for k in kw_pos]))

        with c_desc:
            st.markdown("#### 🛑 Factores de Descarte")
            for crit in perfil_apr.get("criterios_descarte", []):
                st.markdown(f"- ❌ {crit}")
            kw_desc = perfil_apr.get("keywords_asociadas_descarte", [])
            if kw_desc:
                st.markdown("**Keywords asociadas a descarte:**")
                st.markdown(" ".join([f"`{k}`" for k in kw_desc]))

        st.markdown("#### 📋 Directrices Inyectadas al Evaluador:")
        for idx_d, d in enumerate(perfil_apr.get("directrices_calibracion_evaluador", []), 1):
            st.markdown(f"**{idx_d}.** {d}")

        if perfil_apr.get("nuevos_cargos_recomendados_busqueda"):
            st.markdown("#### 🔎 Nuevos Cargos Sugeridos para Portales:")
            st.markdown(" ".join([f"`{c}`" for c in perfil_apr["nuevos_cargos_recomendados_busqueda"]]))

st.divider()

# ----- 3. Ejecución de Búsqueda Activa (Estado de Carga y Feedback) -----
if st.session_state.busqueda_activa:
    st.session_state.busqueda_activa = False

    banner_holder = st.empty()
    banner_holder.markdown("""
    <div class="radar-scanning">
        <h3 style="margin: 0 0 6px 0; color: #60a5fa;">📡 Radar en Operación — Escaneando Portales</h3>
        <p style="margin: 0; font-size: 0.88rem; color: #cbd5e1;">
            Rastreando avisos en Chile, aplicando filtro anti-duplicados (0 tokens) y evaluando con IA...
        </p>
    </div>
    """, unsafe_allow_html=True)

    status_ticker = st.empty()

    def _update_progress(msg):
        status_ticker.info(msg)

    portales_jobspy = [
        p for p in portales_seleccionados
        if p in ["linkedin", "indeed", "google", "glassdoor"]
    ]
    buscar_getonbrd = "getonbrd" in portales_seleccionados
    buscar_chiletrabajos = "chiletrabajos" in portales_seleccionados
    buscar_bne = "bne" in portales_seleccionados
    portales_playwright = [
        p for p in portales_seleccionados
        if p in ["laborum", "trabajando"]
    ]

    total_nuevas = 0
    total_duplicadas = 0

    # JobSpy
    if portales_jobspy:
        with st.spinner(f"🔎 Rastreando en {', '.join(portales_jobspy).upper()}..."):
            stats_jobspy = ejecutar_busqueda_jobspy(
                cargos=cargos_seleccionados,
                portales=portales_jobspy,
                callback_progreso=_update_progress,
            )
            total_nuevas += stats_jobspy.get("nuevas", 0)
            total_duplicadas += stats_jobspy.get("duplicadas", 0)

    # Bolsa Nacional de Empleo (BNE)
    if buscar_bne:
        with st.spinner("🇨🇱 Rastreando en BNE (Bolsa Nacional de Empleo)..."):
            stats_bne = ejecutar_busqueda_bne(
                cargos=cargos_seleccionados,
                limite_por_cargo=10,
                callback_progreso=_update_progress,
            )
            total_nuevas += stats_bne.get("nuevas", 0)
            total_duplicadas += stats_bne.get("duplicadas", 0)

    # Get on Board
    if buscar_getonbrd:
        with st.spinner("🚀 Rastreando en GET ON BOARD (API)..."):
            stats_gob = ejecutar_busqueda_getonbrd(
                cargos=cargos_seleccionados,
                limite_por_cargo=10,
                callback_progreso=_update_progress,
            )
            total_nuevas += stats_gob.get("nuevas", 0)
            total_duplicadas += stats_gob.get("duplicadas", 0)

    # ChileTrabajos
    if buscar_chiletrabajos:
        with st.spinner("🇨🇱 Rastreando en CHILETRABAJOS..."):
            stats_ct = ejecutar_busqueda_chiletrabajos(
                cargos=cargos_seleccionados,
                limite_por_cargo=10,
                callback_progreso=_update_progress,
            )
            total_nuevas += stats_ct.get("nuevas", 0)
            total_duplicadas += stats_ct.get("duplicadas", 0)

    # Laborum / Trabajando
    if portales_playwright:
        st.info(
            "ℹ️ Para Laborum/Trabajando en tu Mac ejecuta:\n"
            "```bash\npython -m src.ingesta_playwright --modo buscar --cargos 'Senior Business Analyst'\n```"
        )

    banner_holder.empty()
    status_ticker.empty()
    _cargar_ofertas_cache.clear()
    _cargar_metricas_cache.clear()
    st.toast(f"🎉 Barrido completado: {total_nuevas} nuevas ofertas evaluadas ({total_duplicadas} duplicadas)")
    st.rerun()

# ----- 4. Listado de Ofertas Laborales -----
st.markdown("### 📋 Ofertas Laborales")

# 4.1 Banner de Deshacer (Undo) si hubo una acción reciente
if st.session_state.get("undo_accion"):
    undo = st.session_state["undo_accion"]
    u_col1, u_col2 = st.columns([3.6, 1.4])
    with u_col1:
        st.warning(
            f"⚠️ Oferta marcada como **{undo['nuevo_estado']}**: *{undo['titulo']}* ({undo['empresa']})"
        )
    with u_col2:
        if st.button(
            f"↩️ Deshacer ({undo['estado_anterior']})",
            key="btn_undo_global",
            type="primary",
            use_container_width=True,
            help="Restaura inmediatamente esta oferta a su estado anterior",
        ):
            actualizar_estado_oferta(undo["id"], undo["estado_anterior"])
            estado_restaurado = undo["estado_anterior"]
            st.session_state["undo_accion"] = None
            _cargar_ofertas_cache.clear()
            _cargar_metricas_cache.clear()
            st.toast(f"✅ Oferta restaurada a {estado_restaurado}")
            st.rerun()

# 4.2 Selector de Vista Rápida por Estado (1 clic)
vista_seleccionada = st.segmented_control(
    "Filtrar por estado:",
    options=["🔥 Por Revisar", "📮 Postuladas", "🗑️ Descartadas", "⭐ Guardadas", "🌐 Todas"],
    default="🔥 Por Revisar",
    label_visibility="collapsed",
)

if "vista_anterior" not in st.session_state or st.session_state.vista_anterior != vista_seleccionada:
    st.session_state.vista_anterior = vista_seleccionada
    st.session_state.pagina_actual = 1

# Mapeo de la vista seleccionada a los estados de la base de datos
if vista_seleccionada == "🔥 Por Revisar":
    estados_activos = ["NUEVA", "GUARDADA"]
elif vista_seleccionada == "📮 Postuladas":
    estados_activos = ["POSTULADO"]
elif vista_seleccionada == "🗑️ Descartadas":
    estados_activos = ["DESCARTADA"]
elif vista_seleccionada == "⭐ Guardadas":
    estados_activos = ["GUARDADA"]
else:
    estados_activos = filtro_estado if filtro_estado else None

try:
    ofertas = _cargar_ofertas_cache(
        veredictos_tuple=tuple(filtro_veredicto) if filtro_veredicto else None,
        score_minimo=filtro_score,
        estados_tuple=tuple(estados_activos) if estados_activos else None,
        portales_tuple=tuple(portales_seleccionados) if portales_seleccionados else None,
    )
except Exception as e:
    ofertas = []
    st.warning(f"⚠️ Error cargando ofertas: {e}")

if ofertas:
    # Filtro opcional: solo minería
    if solo_mineria:
        ofertas = [o for o in ofertas if es_oferta_mineria(o)]

    # Ordenamiento por prioridad:
    # 1. Minería primero
    # 2. Porcentaje de afinidad (% score_match) DESCENDENTE
    # 3. Fecha de extracción más reciente
    if priorizar_mineria:
        ofertas = sorted(
            ofertas,
            key=lambda o: (
                1 if es_oferta_mineria(o) else 0,
                o.get("score_match", 0) or 0,
                str(o.get("fecha_extraccion", "")),
            ),
            reverse=True,
        )
    else:
        ofertas = sorted(
            ofertas,
            key=lambda o: (
                o.get("score_match", 0) or 0,
                str(o.get("fecha_extraccion", "")),
            ),
            reverse=True,
        )

    total_ofertas = len(ofertas)
    cant_mineria = sum(1 for o in ofertas if es_oferta_mineria(o))
    detalle_mineria = f"⛏️ {cant_mineria} del sector minero · " if cant_mineria > 0 else ""
    orden_msg = "Minería y afinidad alta primero" if priorizar_mineria else "mayor afinidad primero"

    # Configuración de paginación (15 ofertas por página para carga instantánea)
    tamano_pagina = 15
    total_paginas = max(1, (total_ofertas + tamano_pagina - 1) // tamano_pagina)

    if st.session_state.pagina_actual > total_paginas:
        st.session_state.pagina_actual = total_paginas
    if st.session_state.pagina_actual < 1:
        st.session_state.pagina_actual = 1

    inicio = (st.session_state.pagina_actual - 1) * tamano_pagina
    fin = min(inicio + tamano_pagina, total_ofertas)
    ofertas_pagina = ofertas[inicio:fin]

    st.caption(
        f"Mostrando **{total_ofertas}** ofertas en {vista_seleccionada} "
        f"({detalle_mineria}ordenadas por {orden_msg})"
    )

    # Navegación superior de páginas
    if total_paginas > 1:
        pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
        with pcol1:
            if st.button("⬅️ Anterior", disabled=(st.session_state.pagina_actual <= 1), key="btn_pag_prev_top", use_container_width=True):
                st.session_state.pagina_actual -= 1
                st.rerun()
        with pcol2:
            st.markdown(
                f"<div style='text-align: center; color: #94a3b8; padding-top: 6px; font-size: 0.9rem;'>"
                f"Página <strong>{st.session_state.pagina_actual}</strong> de <strong>{total_paginas}</strong> "
                f"(Ofertas {inicio + 1}–{fin} de {total_ofertas})"
                f"</div>",
                unsafe_allow_html=True,
            )
        with pcol3:
            if st.button("Siguiente ➡️", disabled=(st.session_state.pagina_actual >= total_paginas), key="btn_pag_next_top", use_container_width=True):
                st.session_state.pagina_actual += 1
                st.rerun()

    for oferta in ofertas_pagina:
        url = render_offer_card(oferta)
        oferta_id = oferta.get("id", "")
        estado_actual = oferta.get("estado_postulacion", "NUEVA")

        # Fila de acciones ergonómica y rápida
        acol1, acol2, acol3, acol4 = st.columns([1, 1.2, 1, 1.2])

        with acol1:
            if url:
                st.link_button("Ver Oferta 🔗", url, use_container_width=True)

        with acol2:
            if st.button("📋 Copiar Ficha", key=f"copy_{oferta_id}", use_container_width=True):
                ats_list = oferta.get('keywords_ats', [])
                if isinstance(ats_list, str):
                    try:
                        ats_list = json.loads(ats_list)
                    except Exception:
                        ats_list = []

                ficha = (
                    f"CARGO: {oferta.get('titulo', '')}\n"
                    f"EMPRESA: {oferta.get('empresa', '')}\n"
                    f"MATCH: {oferta.get('score_match', '')}%\n"
                    f"VEREDICTO: {oferta.get('veredicto', '')}\n"
                    f"PRETENSIÓN SUGERIDA: {oferta.get('pretension_sugerida', '')}\n"
                    f"ENFOQUE CV: {oferta.get('enfoque_cv_sugerido', '')}\n"
                    f"KEYWORDS ATS: {', '.join(ats_list)}\n"
                    f"URL: {url}\n"
                )
                st.code(ficha, language="text")

        with acol3:
            # Acción principal de descarte o restauración según el estado
            if estado_actual == "DESCARTADA":
                if st.button("↩️ Restaurar", key=f"btn_rest_{oferta_id}", type="primary", use_container_width=True, help="Restaura esta oferta a Por Revisar"):
                    ejecutar_cambio_estado(oferta, "NUEVA")
            elif estado_actual == "POSTULADO":
                if st.button("↩️ Reabrir", key=f"btn_reopen_{oferta_id}", use_container_width=True, help="Regresa la oferta a Por Revisar"):
                    ejecutar_cambio_estado(oferta, "NUEVA")
            else:
                if st.button("🗑️ Descartar", key=f"btn_desc_{oferta_id}", use_container_width=True, help="Descarta la oferta y la saca de la vista actual"):
                    ejecutar_cambio_estado(oferta, "DESCARTADA")

        with acol4:
            if estado_actual in ("NUEVA", "GUARDADA"):
                if st.button("📮 Postulé", key=f"btn_post_{oferta_id}", type="primary", use_container_width=True, help="Marca que postulaste a esta oferta"):
                    ejecutar_cambio_estado(oferta, "POSTULADO")
            else:
                estados_opciones = ["NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"]
                idx = estados_opciones.index(estado_actual) if estado_actual in estados_opciones else 0
                nuevo_st = st.selectbox(
                    "Estado",
                    options=estados_opciones,
                    index=idx,
                    key=f"sel_st_{oferta_id}",
                    label_visibility="collapsed",
                )
                if nuevo_st != estado_actual:
                    ejecutar_cambio_estado(oferta, nuevo_st)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Navegación inferior de páginas
    if total_paginas > 1:
        bcol1, bcol2, bcol3 = st.columns([1, 2, 1])
        with bcol1:
            if st.button("⬅️ Anterior", disabled=(st.session_state.pagina_actual <= 1), key="btn_pag_prev_bottom", use_container_width=True):
                st.session_state.pagina_actual -= 1
                st.rerun()
        with bcol2:
            st.markdown(
                f"<div style='text-align: center; color: #94a3b8; padding-top: 6px; font-size: 0.9rem;'>"
                f"Página <strong>{st.session_state.pagina_actual}</strong> de <strong>{total_paginas}</strong>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with bcol3:
            if st.button("Siguiente ➡️", disabled=(st.session_state.pagina_actual >= total_paginas), key="btn_pag_next_bottom", use_container_width=True):
                st.session_state.pagina_actual += 1
                st.rerun()
else:
    st.info(
        f"🔍 **No hay ofertas en la vista '{vista_seleccionada}' que coincidan con los filtros actuales.**\n\n"
        "• Puedes cambiar de vista ('🔥 Por Revisar', '📮 Postuladas', '🗑️ Descartadas') con las pestañas superiores.\n"
        "• Ajusta el score mínimo en la barra lateral o ejecuta una nueva búsqueda."
    )
