# **Documento de Arquitectura Técnica: Sistema de Gestión de Pendientes con IA y Telegram**

**Autor:** Jaime Jesus Bustamante Marcotti  
**Fecha de Creación:** 27 de junio de 2026  
**Estado:** Diseño Técnico de Producción Robustecido  
**Versión:** V4 (Producción Confiable)

## **1\. Diseño de la Base de Datos (Esquema SQL V4)**

`-- Tabla de Tareas Modificada V4`  
`CREATE TABLE tareas (`  
    `id VARCHAR(64) PRIMARY KEY,`  
    `ambito VARCHAR(12) NOT NULL CHECK (ambito IN ('laboral', 'personal')),`  
    `titulo VARCHAR(255) NOT NULL,`  
    `proyecto VARCHAR(100) DEFAULT NULL,`  
    `origen VARCHAR(100) NOT NULL,`  
    `fecha_vence DATE DEFAULT NULL,`  
    `prioridad VARCHAR(10) NOT NULL CHECK (prioridad IN ('alta', 'media', 'baja')),`  
    `estado VARCHAR(15) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'completado')),`  
    `google_calendar_event_id VARCHAR(255) DEFAULT NULL,`  
    `ultima_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- Tabla de Buffer Físico Persistente (Anti-Volatilidad)`  
`CREATE TABLE buffer_ingesta_contingencia (`  
    `id SERIAL PRIMARY KEY,`  
    `chat_id BIGINT NOT NULL,`  
    `mensaje_raw TEXT NOT NULL,`  
    `procesado BOOLEAN DEFAULT FALSE,`  
    `intentos_fallidos INT DEFAULT 0,`  
    `estado_procesamiento VARCHAR(20) DEFAULT 'pendiente' CHECK (estado_procesamiento IN ('pendiente', 'procesando', 'completado', 'error_permanente')),`  
    `creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP`  
`);`

## **2\. Orquestación y Workers Asíncronos**

* **Orquestador de Recurrencias:** Se utilizará la extensión **pg\_cron** nativa de Supabase para disparar de manera confiable la evaluación de las plantillas a las 00:01 AM, evitando depender del estado de la memoria del proceso de FastAPI.  
* **Google Calendar Worker con Backoff Exponencial:** En lugar de delays fijos, el worker procesará las solicitudes de forma continua. Si la API de Google retorna un error HTTP 429 (Rate Limiting), se capturará la excepción aplicando un algoritmo de backoff incremental (10s, 30s, 60s).