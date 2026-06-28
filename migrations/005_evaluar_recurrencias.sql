-- 005: Función evaluar_plantillas_recurrencia + pg_cron schedule

CREATE OR REPLACE FUNCTION evaluar_plantillas_recurrencia()
RETURNS TABLE (generada_id VARCHAR, plantilla_id INT)
LANGUAGE plpgsql
AS $$
DECLARE
    tz VARCHAR;
    fecha_hoy DATE;
    r RECORD;
    meses_transcurridos INT;
    semanas_transcurridas INT;
    anios_transcurridos INT;
    coincide_boolean BOOLEAN;
    ultimo_dia_mes INT;
    tarea_id VARCHAR;
BEGIN
    SELECT valor_texto INTO tz
    FROM configuracion_sistema
    WHERE clave = 'zona_horaria_default'
    LIMIT 1;

    IF tz IS NULL THEN
        tz := 'America/Lima';
    END IF;

    fecha_hoy := (NOW() AT TIME ZONE tz)::DATE;

    FOR r IN
        SELECT id, titulo, ambito, proyecto, prioridad, origen,
               tipo_recurrencia, intervalo, dia_del_mes, mes_del_anio,
               dia_de_semana, dias_para_vencer, fecha_inicio
        FROM plantillas_recurrencia
        WHERE activa = true
          AND fecha_inicio <= fecha_hoy
          AND (fecha_fin IS NULL OR fecha_fin >= fecha_hoy)
          AND ultima_generacion IS DISTINCT FROM fecha_hoy
    LOOP
        coincide_boolean := false;

        IF r.tipo_recurrencia = 'diaria' THEN
            coincide_boolean := true;

        ELSIF r.tipo_recurrencia = 'semanal' THEN
            IF EXTRACT(DOW FROM fecha_hoy)::INT = r.dia_de_semana THEN
                semanas_transcurridas := (
                    (fecha_hoy - r.fecha_inicio)::INT / 7
                );
                coincide_boolean := (semanas_transcurridas % r.intervalo = 0);
            END IF;

        ELSIF r.tipo_recurrencia = 'mensual' THEN
            IF r.dia_del_mes = 0 THEN
                ultimo_dia_mes := EXTRACT(DAY FROM
                    (DATE_TRUNC('month', fecha_hoy) + INTERVAL '1 month - 1 day'))::INT;
                coincide_boolean := (EXTRACT(DAY FROM fecha_hoy)::INT = ultimo_dia_mes);
            ELSE
                coincide_boolean := (EXTRACT(DAY FROM fecha_hoy)::INT = r.dia_del_mes);
            END IF;

            IF coincide_boolean AND r.intervalo > 1 THEN
                meses_transcurridos := (
                    (EXTRACT(YEAR FROM fecha_hoy)::INT - EXTRACT(YEAR FROM r.fecha_inicio)::INT) * 12
                    + (EXTRACT(MONTH FROM fecha_hoy)::INT - EXTRACT(MONTH FROM r.fecha_inicio)::INT)
                );
                coincide_boolean := (meses_transcurridos % r.intervalo = 0);
            END IF;

        ELSIF r.tipo_recurrencia = 'anual' THEN
            IF EXTRACT(DAY FROM fecha_hoy)::INT = r.dia_del_mes
               AND EXTRACT(MONTH FROM fecha_hoy)::INT = r.mes_del_anio THEN
                anios_transcurridos := (
                    EXTRACT(YEAR FROM fecha_hoy)::INT - EXTRACT(YEAR FROM r.fecha_inicio)::INT
                );
                coincide_boolean := (anios_transcurridos % r.intervalo = 0);
            END IF;
        END IF;

        IF coincide_boolean THEN
            tarea_id := 'rec-' || r.id || '-' || fecha_hoy::TEXT;

            INSERT INTO tareas (
                id, ambito, titulo, proyecto, origen,
                fecha_vence, prioridad, estado
            ) VALUES (
                tarea_id, r.ambito, r.titulo, r.proyecto, 'recurrencia',
                fecha_hoy + r.dias_para_vencer, r.prioridad, 'pendiente'
            )
            ON CONFLICT (id) DO NOTHING;

            UPDATE plantillas_recurrencia
            SET ultima_generacion = fecha_hoy,
                ultima_modificacion = NOW()
            WHERE id = r.id;

            RETURN QUERY SELECT tarea_id, r.id;
        END IF;
    END LOOP;
END;
$$;

SELECT cron.schedule(
    'evaluar-recurrencias',
    '1 5 * * *',
    $$SELECT evaluar_plantillas_recurrencia()$$
);
