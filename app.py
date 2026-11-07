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
)
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


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

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
        cargos_disponibles = st.session_state.estrategia.get("cargos_objetivo_busqueda", [])

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
    metricas = obtener_metricas_resumen()
except Exception:
    metricas = {
        "ofertas_totales": 0,
        "recomendadas_postular": 0,
        "postulados": 0,
        "por_revisar": 0,
    }

kcol1, kcol2, kcol3, kcol4 = st.columns(4)
with kcol1:
    render_kpi_card("Ofertas Totales", metricas["ofertas_totales"], "kpi-white")
with kcol2:
    render_kpi_card("Recomendadas (Postular)", metricas["recomendadas_postular"], "kpi-green")
with kcol3:
    render_kpi_card("Postulados", metricas["postulados"], "kpi-blue")
with kcol4:
    render_kpi_card("Por Revisar", metricas["por_revisar"], "kpi-orange")

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
    st.toast(f"🎉 Barrido completado: {total_nuevas} nuevas ofertas evaluadas ({total_duplicadas} duplicadas)")
    st.rerun()

# ----- 4. Listado de Ofertas Laborales -----
st.markdown("### 📋 Ofertas Laborales Evaluadas")

try:
    ofertas = obtener_ofertas_filtradas(
        veredictos=filtro_veredicto if filtro_veredicto else None,
        score_minimo=filtro_score,
        estados=filtro_estado if filtro_estado else None,
        portales=portales_seleccionados if portales_seleccionados else None,
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

    cant_mineria = sum(1 for o in ofertas if es_oferta_mineria(o))
    detalle_mineria = f"⛏️ {cant_mineria} del sector minero · " if cant_mineria > 0 else ""
    orden_msg = "Minería y afinidad alta primero" if priorizar_mineria else "mayor afinidad primero"
    st.caption(f"Mostrando **{len(ofertas)}** ofertas ({detalle_mineria}ordenadas por {orden_msg})")

    for oferta in ofertas:
        url = render_offer_card(oferta)
        oferta_id = oferta.get("id", "")

        # Fila de acciones ergonómica
        acol1, acol2, acol3 = st.columns([1, 1.2, 1])

        with acol1:
            if url:
                st.link_button("Ver Oferta 🔗", url, use_container_width=True)

        with acol2:
            if st.button("📋 Copiar Ficha para CV", key=f"copy_{oferta_id}", use_container_width=True):
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
            estado_actual = oferta.get("estado_postulacion", "NUEVA")
            estados_opciones = ["NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"]
            idx = estados_opciones.index(estado_actual) if estado_actual in estados_opciones else 0

            nuevo_estado = st.selectbox(
                "Estado de la postulación",
                options=estados_opciones,
                index=idx,
                key=f"estado_{oferta_id}",
                label_visibility="collapsed",
            )
            if nuevo_estado != estado_actual:
                try:
                    actualizar_estado_oferta(oferta_id, nuevo_estado)
                    st.toast(f"✅ Estado actualizado a: {nuevo_estado}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
else:
    st.info(
        "🔍 **No hay ofertas que coincidan con los filtros actuales.**\n\n"
        "• Ajusta los filtros de veredicto o el score mínimo en la barra lateral.\n"
        "• O haz clic en **'🔍 Ejecutar Búsqueda en Portales'** para rastrear nuevas oportunidades."
    )
