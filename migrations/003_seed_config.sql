-- 003: Seed configuration defaults
-- Run after configuracion_sistema table exists (V3 schema)

INSERT INTO configuracion_sistema (clave, valor_booleano)
VALUES ('transcripcion_idioma_default', NULL)
ON CONFLICT (clave) DO NOTHING;

-- The idioma_default is stored as valor_texto, but V3 schema doesn't have one.
-- We extend via un valor_booleano + fecha_liberacion hack or add valor_texto.
-- For now, use a convention: valor_booleano=true means "custom is set",
-- and we store the actual value in the app config.
-- App-level default: 'es'
