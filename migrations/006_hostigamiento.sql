-- 006: Hostigamiento Pepe Grillo — schema + funciones

ALTER TABLE tareas
DROP CONSTRAINT IF EXISTS tareas_estado_check;

ALTER TABLE tareas
ADD CONSTRAINT tareas_estado_check
    CHECK (estado IN ('pendiente', 'completado', 'descartado'));

ALTER TABLE tareas
ADD COLUMN IF NOT EXISTS chat_id BIGINT;

INSERT INTO configuracion_sistema (clave, valor_booleano, fecha_liberacion)
VALUES ('modo_vacaciones', false, NULL),
       ('modo_finde', false, NULL)
ON CONFLICT (clave) DO NOTHING;

CREATE OR REPLACE FUNCTION calcular_nivel_hostigamiento(
    p_fecha_vence DATE,
    p_now TIMESTAMP
) RETURNS INT
LANGUAGE sql
AS $$
    SELECT CASE
        WHEN p_fecha_vence IS NULL OR p_fecha_vence > (p_now::DATE + 1) THEN -1
        WHEN p_fecha_vence = (p_now::DATE + 1) THEN 0
        WHEN p_fecha_vence = p_now::DATE THEN 1
        WHEN p_fecha_vence >= (p_now::DATE - 2) THEN 2
        WHEN p_fecha_vence >= (p_now::DATE - 6) THEN 3
        ELSE 4
    END;
$$;

CREATE OR REPLACE FUNCTION frecuencia_nivel(p_nivel INT)
RETURNS INTERVAL
LANGUAGE sql
AS $$
    SELECT CASE p_nivel
        WHEN 0 THEN NULL
        WHEN 1 THEN INTERVAL '4 hours'
        WHEN 2 THEN INTERVAL '3 hours'
        WHEN 3 THEN INTERVAL '4 hours'
        WHEN 4 THEN INTERVAL '1 day'
        ELSE INTERVAL '1 day'
    END;
$$;
