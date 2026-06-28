-- 001: Evolved buffer_ingesta_contingencia schema
-- V4 baseline + lease protocol columns + multi-media support + telegram_message_id

CREATE TABLE IF NOT EXISTS buffer_ingesta_contingencia (
    id                  SERIAL PRIMARY KEY,
    chat_id             BIGINT NOT NULL,
    telegram_message_id BIGINT NOT NULL,
    tipo_media          VARCHAR(10) NOT NULL,
    mensaje_raw         TEXT,
    file_id             VARCHAR(512),
    storage_path        VARCHAR(1024),
    signed_url          VARCHAR(2048),
    transcripcion       TEXT,
    procesado           BOOLEAN NOT NULL DEFAULT FALSE,
    intentos_fallidos   INT NOT NULL DEFAULT 0,
    estado_procesamiento VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    tomado_en           TIMESTAMP,
    proximo_intento_en  TIMESTAMP,
    creado_en           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_tipo_media CHECK (tipo_media IN ('texto', 'voz')),
    CONSTRAINT chk_estado_procesamiento CHECK (estado_procesamiento IN (
        'pendiente', 'procesando', 'completado', 'error_permanente'
    )),
    CONSTRAINT chk_tipo_media_columnas CHECK (
        (tipo_media = 'texto' AND mensaje_raw IS NOT NULL
            AND file_id IS NULL AND storage_path IS NULL AND signed_url IS NULL)
        OR
        (tipo_media = 'voz' AND file_id IS NOT NULL AND storage_path IS NOT NULL
            AND mensaje_raw IS NULL)
    )
);

CREATE INDEX idx_buffer_estado_procesamiento
    ON buffer_ingesta_contingencia (estado_procesamiento, creado_en)
    WHERE estado_procesamiento = 'pendiente';

CREATE INDEX idx_buffer_tomado_en
    ON buffer_ingesta_contingencia (tomado_en)
    WHERE estado_procesamiento = 'procesando';
