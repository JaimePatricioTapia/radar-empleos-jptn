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
        padding: 14px;
        border: 1px solid #3d3d5c;
        margin-bottom: 16px;
    }
    .cv-status {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 10px;
        font-size: 0.78rem;
        font-weight: 600;
        background: #166534;
        color: #4ade80;
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


def render_kpi_card(label: str, value, css_class: str = "kpi-white"):
    """Renderiza una tarjeta KPI con estilos."""
    st.markdown(f"""
    <div class="kpi-card {css_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def render_offer_card(oferta: dict):
    """Renderiza una tarjeta de oferta laboral estilizada."""
    score = oferta.get("score_match", 0) or 0
    veredicto = oferta.get("veredicto", "").upper()

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

    # Construir HTML
    fortalezas_html = "".join(
        f'<span class="badge badge-green">✓ {f}</span> ' for f in fortalezas[:5]
    )
    brechas_html = "".join(
        f'<span class="badge badge-red">✗ {b}</span> ' for b in brechas[:5]
    )
    keywords_html = "".join(
        f'<span class="badge badge-blue">{k}</span> ' for k in keywords[:8]
    )

    meta_parts = [p for p in [empresa, ubicacion, modalidad, portal.upper()] if p]
    meta_str = " · ".join(meta_parts)

    st.markdown(f"""
    <div class="offer-card {card_class}">
        <div class="offer-header">
            <div>
                <div class="offer-title">{titulo}</div>
                <div class="offer-meta">{meta_str}</div>
            </div>
            <div class="offer-score {score_class}">{score}%</div>
        </div>

        <div class="offer-salary">
            <span>💰 Renta estimada: <strong>{renta_est}</strong></span>
            <span>🎯 Pretensión sugerida: <strong>{pretension}</strong></span>
        </div>

        <div class="offer-section-title">🎯 Enfoque CV sugerido</div>
        <div style="font-size: 0.88rem; color: #cbd5e1; margin-bottom: 8px;">{enfoque}</div>

        <div class="offer-section-title">✅ Fortalezas</div>
        <div>{fortalezas_html or '<span style="color:#666;">—</span>'}</div>

        <div class="offer-section-title">⚠️ Brechas</div>
        <div>{brechas_html or '<span style="color:#666;">—</span>'}</div>

        <div class="offer-section-title">🔑 Keywords ATS</div>
        <div>{keywords_html or '<span style="color:#666;">—</span>'}</div>
    </div>
    """, unsafe_allow_html=True)

    return url


# =====================================================================
# BARRA LATERAL
# =====================================================================
with st.sidebar:
    st.title("⚙️ Panel de Control")

    # ----- Diagnóstico del CV -----
    st.markdown("### 📄 Diagnóstico del CV Maestro")

    if st.session_state.cv_data is None:
        with st.spinner("Cargando CV..."):
            cargar_cv()

    if st.session_state.cv_data:
        cv = st.session_state.cv_data
        cv_hash_short = cv["hash"][:12]

        st.markdown(f"""
        <div class="cv-card">
            <strong>📁 {cv['nombre_archivo']}</strong><br>
            <span class="cv-status">● Activo</span><br>
            <span style="font-size:0.78rem; color:#94a3b8;">
                Actualizado: {cv['actualizado'][:10]}<br>
                Hash: <code>{cv_hash_short}...</code>
            </span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Re-analizar PDF", use_container_width=True):
            with st.spinner("Re-analizando CV con Gemini..."):
                st.session_state.cv_data = leer_cv_pdf_integro()
                st.session_state.estrategia = obtener_estrategia_busqueda_desde_cv(
                    forzar_recalculo=True
                )
            st.success("✅ CV re-analizado")
            st.rerun()
    else:
        st.error("❌ No se pudo cargar el CV. Verifica CV_PDF_PATH en .env")

    st.divider()

    # ----- Estrategia de Búsqueda -----
    st.markdown("### 🎯 Estrategia de Búsqueda")
    st.caption("Auto-detección desde el CV")

    cargos_seleccionados = []
    if st.session_state.estrategia:
        estrategia = st.session_state.estrategia
        cargos_disponibles = estrategia.get("cargos_objetivo_busqueda", [])

        for i, cargo in enumerate(cargos_disponibles):
            checked = st.checkbox(cargo, value=True, key=f"cargo_{i}")
            if checked:
                cargos_seleccionados.append(cargo)
    else:
        st.warning("⚠️ Carga el CV para ver los cargos detectados.")

    st.divider()

    # ----- Opciones de Portales -----
    st.markdown("### 🌐 Opciones de Portales")
    portales_disponibles = ["linkedin", "indeed", "google", "laborum", "trabajando"]
    portales_seleccionados = st.multiselect(
        "Plataformas",
        options=portales_disponibles,
        default=["linkedin", "indeed", "google"],
    )

    st.divider()

    # ----- Botón de Búsqueda -----
    if st.button(
        "🔍 Ejecutar Búsqueda en Portales",
        use_container_width=True,
        type="primary",
        disabled=not cargos_seleccionados,
    ):
        st.session_state.busqueda_activa = True

    st.divider()

    # ----- Filtros Rápidos -----
    st.markdown("### 🔧 Filtros Rápidos")

    filtro_veredicto = st.multiselect(
        "Veredicto",
        options=["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"],
        default=["POSTULAR", "POSTULAR CON RESERVAS"],
    )

    filtro_score = st.slider(
        "Score mínimo (%)",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
    )

    filtro_estado = st.multiselect(
        "Estado",
        options=["NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"],
        default=["NUEVA", "GUARDADA"],
    )


# =====================================================================
# ÁREA PRINCIPAL
# =====================================================================

# ----- Encabezado -----
st.markdown("# 🔍 Radar de Empleos JPTN")
st.markdown(
    "*Sistema automatizado de descubrimiento, evaluación semántica "
    "y gestión de ofertas laborales*"
)

st.divider()

# ----- Ejecución de búsqueda -----
if st.session_state.busqueda_activa:
    st.session_state.busqueda_activa = False

    portales_jobspy = [p for p in portales_seleccionados if p in ["linkedin", "indeed", "google"]]
    portales_playwright = [p for p in portales_seleccionados if p in ["laborum", "trabajando"]]

    progress_container = st.empty()
    status_text = st.empty()

    def _update_progress(msg):
        status_text.text(msg)

    if portales_jobspy:
        with st.spinner("🔎 Buscando en portales públicos (JobSpy)..."):
            stats_jobspy = ejecutar_busqueda_jobspy(
                cargos=cargos_seleccionados,
                portales=portales_jobspy,
                callback_progreso=_update_progress,
            )
            st.success(
                f"✅ JobSpy: {stats_jobspy['nuevas']} nuevas, "
                f"{stats_jobspy['duplicadas']} duplicadas, "
                f"{stats_jobspy['errores']} errores"
            )

    if portales_playwright:
        st.info(
            "ℹ️ Para buscar en Laborum/Trabajando, primero ejecuta el login:\n"
            "```bash\npython -m src.ingesta_playwright --modo login\n```"
        )

    status_text.empty()
    progress_container.empty()
    st.rerun()

# ----- KPIs -----
try:
    metricas = obtener_metricas_resumen()
except Exception:
    metricas = {
        "ofertas_totales": 0,
        "recomendadas_postular": 0,
        "postulados": 0,
        "por_revisar": 0,
    }

col1, col2, col3, col4 = st.columns(4)

with col1:
    render_kpi_card("Ofertas Totales", metricas["ofertas_totales"], "kpi-white")
with col2:
    render_kpi_card("Recomendadas (Postular)", metricas["recomendadas_postular"], "kpi-green")
with col3:
    render_kpi_card("Postulados", metricas["postulados"], "kpi-blue")
with col4:
    render_kpi_card("Por Revisar", metricas["por_revisar"], "kpi-orange")

st.divider()

# ----- Listado de Ofertas -----
st.markdown("### 📋 Ofertas Laborales")

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
    st.caption(f"Mostrando {len(ofertas)} ofertas")

    for oferta in ofertas:
        url = render_offer_card(oferta)
        oferta_id = oferta.get("id", "")

        # Fila de acciones
        acol1, acol2, acol3 = st.columns([1, 1, 1])

        with acol1:
            if url:
                st.link_button("Ver Oferta 🔗", url, use_container_width=True)

        with acol2:
            if st.button("📋 Copiar Ficha", key=f"copy_{oferta_id}"):
                ficha = (
                    f"TÍTULO: {oferta.get('titulo', '')}\n"
                    f"EMPRESA: {oferta.get('empresa', '')}\n"
                    f"MATCH: {oferta.get('score_match', '')}%\n"
                    f"VEREDICTO: {oferta.get('veredicto', '')}\n"
                    f"ROL: {oferta.get('rol_detectado', '')}\n"
                    f"ENFOQUE: {oferta.get('enfoque_cv_sugerido', '')}\n"
                    f"KEYWORDS ATS: {', '.join(oferta.get('keywords_ats', []) if isinstance(oferta.get('keywords_ats'), list) else [])}\n"
                    f"URL: {url}\n"
                )
                st.code(ficha, language="text")

        with acol3:
            estado_actual = oferta.get("estado_postulacion", "NUEVA")
            estados_opciones = ["NUEVA", "GUARDADA", "POSTULADO", "DESCARTADA"]
            idx = estados_opciones.index(estado_actual) if estado_actual in estados_opciones else 0

            nuevo_estado = st.selectbox(
                "Estado",
                options=estados_opciones,
                index=idx,
                key=f"estado_{oferta_id}",
                label_visibility="collapsed",
            )
            if nuevo_estado != estado_actual:
                try:
                    actualizar_estado_oferta(oferta_id, nuevo_estado)
                    st.toast(f"✅ Estado actualizado a {nuevo_estado}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
else:
    st.info(
        "🔍 No hay ofertas que coincidan con los filtros actuales.\n\n"
        "Usa el panel lateral para ejecutar una búsqueda o ajustar los filtros."
    )
