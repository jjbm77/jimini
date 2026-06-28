-- 002: Buffer lease protocol functions + pg_cron schedule

CREATE OR REPLACE FUNCTION claim_next_buffer_message()
RETURNS SETOF buffer_ingesta_contingencia
LANGUAGE sql
AS $$
    UPDATE buffer_ingesta_contingencia
    SET estado_procesamiento = 'procesando',
        tomado_en = NOW()
    WHERE id = (
        SELECT id
        FROM buffer_ingesta_contingencia
        WHERE estado_procesamiento = 'pendiente'
          AND (proximo_intento_en IS NULL OR proximo_intento_en <= NOW())
        ORDER BY creado_en
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION mark_buffer_completed(p_id INT)
RETURNS VOID
LANGUAGE sql
AS $$
    UPDATE buffer_ingesta_contingencia
    SET estado_procesamiento = 'completado',
        procesado = true,
        tomado_en = NULL
    WHERE id = p_id;
$$;

CREATE OR REPLACE FUNCTION mark_buffer_failed(p_id INT, p_current_intentos INT)
RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    new_intentos INT;
    new_estado VARCHAR;
BEGIN
    new_intentos := p_current_intentos + 1;

    IF new_intentos >= 3 THEN
        UPDATE buffer_ingesta_contingencia
        SET estado_procesamiento = 'error_permanente',
            intentos_fallidos = new_intentos,
            tomado_en = NULL
        WHERE id = p_id;
        RETURN 'error_permanente';
    ELSE
        UPDATE buffer_ingesta_contingencia
        SET estado_procesamiento = 'pendiente',
            intentos_fallidos = new_intentos,
            proximo_intento_en = NOW() + (INTERVAL '10 seconds' * POWER(2, p_current_intentos)),
            tomado_en = NULL
        WHERE id = p_id;
        RETURN 'pendiente';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION get_idioma_config()
RETURNS VARCHAR
LANGUAGE sql
AS $$
    SELECT valor_booleano::VARCHAR FROM configuracion_sistema
    WHERE clave = 'transcripcion_idioma_default'
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION reclaim_stale_locks_buffer()
RETURNS TABLE (reclaimed_id INT, new_status VARCHAR, new_intentos INT)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT id, intentos_fallidos
        FROM buffer_ingesta_contingencia
        WHERE estado_procesamiento = 'procesando'
          AND tomado_en < NOW() - INTERVAL '5 minutes'
        FOR UPDATE SKIP LOCKED
    LOOP
        IF r.intentos_fallidos + 1 >= 3 THEN
            UPDATE buffer_ingesta_contingencia
            SET estado_procesamiento = 'error_permanente',
                intentos_fallidos = intentos_fallidos + 1,
                tomado_en = NULL
            WHERE id = r.id;

            RETURN QUERY SELECT r.id, 'error_permanente'::VARCHAR, (r.intentos_fallidos + 1)::INT;
        ELSE
            UPDATE buffer_ingesta_contingencia
            SET estado_procesamiento = 'pendiente',
                intentos_fallidos = intentos_fallidos + 1,
                proximo_intento_en = NOW() + INTERVAL '30 seconds',
                tomado_en = NULL
            WHERE id = r.id;

            RETURN QUERY SELECT r.id, 'pendiente'::VARCHAR, (r.intentos_fallidos + 1)::INT;
        END IF;
    END LOOP;
END;
$$;

SELECT cron.schedule(
    'reclaim-stale-locks',
    '* * * * *',
    $$SELECT reclaim_stale_locks_buffer()$$
);
