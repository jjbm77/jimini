-- 004: Plantillas de recurrencia + extensiones de config y buffer

ALTER TABLE configuracion_sistema ADD COLUMN IF NOT EXISTS valor_texto TEXT;

INSERT INTO configuracion_sistema (clave, valor_texto)
VALUES ('zona_horaria_default', 'America/Lima')
ON CONFLICT (clave) DO UPDATE SET valor_texto = EXCLUDED.valor_texto;

CREATE TABLE IF NOT EXISTS plantillas_recurrencia (
    id                  SERIAL PRIMARY KEY,
    titulo              VARCHAR(255) NOT NULL,
    ambito              VARCHAR(12) NOT NULL CHECK (ambito IN ('laboral', 'personal')),
    proyecto            VARCHAR(100),
    prioridad           VARCHAR(10) NOT NULL CHECK (prioridad IN ('alta', 'media', 'baja')),
    origen              VARCHAR(100) NOT NULL,

    tipo_recurrencia    VARCHAR(20) NOT NULL CHECK (tipo_recurrencia IN (
        'diaria', 'semanal', 'mensual', 'anual'
    )),
    intervalo           INT NOT NULL DEFAULT 1 CHECK (intervalo >= 1),
    dia_del_mes         INT CHECK (
        dia_del_mes IS NULL OR (dia_del_mes >= 0 AND dia_del_mes <= 31)
    ),
    mes_del_anio        INT CHECK (
        mes_del_anio IS NULL OR (mes_del_anio >= 1 AND mes_del_anio <= 12)
    ),
    dia_de_semana       INT CHECK (
        dia_de_semana IS NULL OR (dia_de_semana >= 0 AND dia_de_semana <= 6)
    ),

    dias_para_vencer    INT NOT NULL DEFAULT 0 CHECK (dias_para_vencer >= 0),

    activa              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_inicio        DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_fin           DATE,
    ultima_generacion   DATE,

    creado_en           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_recurrencia_consistencia CHECK (
        (tipo_recurrencia = 'diaria')
        OR (tipo_recurrencia = 'semanal' AND dia_de_semana IS NOT NULL)
        OR (tipo_recurrencia = 'mensual' AND dia_del_mes IS NOT NULL)
        OR (tipo_recurrencia = 'anual' AND dia_del_mes IS NOT NULL
            AND mes_del_anio IS NOT NULL)
    )
);

ALTER TABLE buffer_ingesta_contingencia
ADD COLUMN IF NOT EXISTS tipo_mensaje VARCHAR(20) NOT NULL DEFAULT 'tarea'
    CHECK (tipo_mensaje IN ('tarea', 'recurrencia'));
