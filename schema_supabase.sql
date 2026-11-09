CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS ofertas_laborales (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_hash TEXT UNIQUE NOT NULL,
    portal TEXT NOT NULL,
    titulo TEXT NOT NULL,
    empresa TEXT,
    ubicacion TEXT,
    modalidad TEXT,
    url TEXT NOT NULL,
    descripcion_cruda TEXT NOT NULL,
    score_match INTEGER,
    veredicto TEXT CHECK (veredicto IN ('POSTULAR', 'POSTULAR CON RESERVAS', 'DESCARTAR')),
    rol_detectado TEXT,
    enfoque_cv_sugerido TEXT,
    fortalezas JSONB DEFAULT '[]'::jsonb,
    brechas JSONB DEFAULT '[]'::jsonb,
    keywords_ats JSONB DEFAULT '[]'::jsonb,
    renta_estimada_empresa TEXT,
    pretension_sugerida TEXT,
    estado_postulacion TEXT DEFAULT 'NUEVA' CHECK (estado_postulacion IN ('NUEVA', 'GUARDADA', 'POSTULADO', 'DESCARTADA', 'CADUCADA')),
    fecha_publicacion TEXT,
    fecha_extraccion TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ofertas_score ON ofertas_laborales(score_match DESC);
CREATE INDEX IF NOT EXISTS idx_ofertas_veredicto ON ofertas_laborales(veredicto);
CREATE INDEX IF NOT EXISTS idx_ofertas_estado ON ofertas_laborales(estado_postulacion);
CREATE INDEX IF NOT EXISTS idx_ofertas_fecha ON ofertas_laborales(fecha_extraccion DESC);
