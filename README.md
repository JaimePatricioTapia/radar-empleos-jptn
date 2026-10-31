# 🔍 Radar de Empleos JPTN

Sistema inteligente de descubrimiento, evaluación semántica y gestión ejecutiva de ofertas laborales en Chile frente al Currículum Maestro Exhaustivo, con IA (Gemini) y base de datos centralizada en Supabase.

---

## 🚀 Características Principales

- **📄 Capa 1 — Fuente de Verdad:** Lectura dinámica del CV Maestro en PDF con hash SHA-256 y auto-detección de estrategia (cargos objetivo, keywords ATS y notas restrictivas).
- **🔎 Capa 2 — Ingesta Híbrida:** Búsqueda en LinkedIn, Indeed y Google Jobs (JobSpy) y portales chilenos (Laborum, Trabajando.com).
- **🗃️ Capa 3 — Deduplicación y Ahorro de Tokens:** Filtrado en Supabase por `job_hash` antes de llamar a la IA (0 tokens consumidos en ofertas ya conocidas).
- **🤖 Capa 4 — Motor Semántico:** Evaluación con Gemini, puntuación de calce (0-100%), veredicto (`POSTULAR`, `POSTULAR CON RESERVAS`, `DESCARTAR`), tasación salarial estimada vs. pretensión sugerida (punto dulce) y recomendaciones ATS.
- **📊 Capa 5 — Dashboard Ejecutivo:** Interfaz Streamlit con métricas KPI, diagnóstico del CV, filtros y selector de estado (`NUEVA`, `GUARDADA`, `POSTULADO`, `DESCARTADA`).

---

## ☁️ Deploy en Streamlit Community Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io).
2. Haz clic en **Create app**.
3. Selecciona tu repositorio: `JaimePatricioTapia/radar-empleos-jptn`.
4. En **Main file path**, ingresa: `app.py`.
5. En **Advanced settings > Secrets**, agrega:
   ```toml
   GEMINI_API_KEY = "tu_api_key"
   SUPABASE_URL = "https://tu-proyecto.supabase.co"
   SUPABASE_KEY = "tu_service_role_o_anon_key"
   ```
6. Haz clic en **Deploy!**

---

## 💻 Ejecución Local en Mac

```bash
# 1. Clonar
git clone https://github.com/JaimePatricioTapia/radar-empleos-jptn.git
cd radar-empleos-jptn

# 2. Entorno virtual e instalar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurar .env a partir de .env.example
cp .env.example .env

# 4. Probar pipeline
python test_pipeline.py

# 5. Iniciar dashboard
streamlit run app.py
```
