# **Documento de Arquitectura Técnica: Sistema de Gestión de Pendientes con IA y Telegram**

**Autor:** Jaime Jesus Bustamante Marcotti  
**Fecha de Creación:** 27 de junio de 2026  
**Estado:** Diseño de Arquitectura Técnico Ampliado (Resiliencia Avanzada)  
**Versión:** V3

## **1\. Resumen de la Arquitectura**

El backend basado en **FastAPI (Python)** introduce patrones arquitectónicos de desacoplamiento y resiliencia para mitigar fallas en servicios de terceros (OpenRouter y Google APIs) mediante el uso de colas de ejecución asíncronas en memoria y un sistema estricto de control de concurrencia optimista.

## **2\. Stack Tecnológico Ampliado**

| Componente | Tecnología Seleccionada | Razón de Selección e Integración Técnica   |
| :---- | :---- | :---- |
| **Core & DB** | FastAPI \+ Supabase (PostgreSQL) | Mantiene el núcleo relacional asíncrono básico. Capa gratuita permanente. |
| **Integración Calendario** | Google APIs Client Library ( `google-api-python-client` ) | Conexión asíncrona mediante un Worker que respeta las cuotas de tasa de solicitudes (Rate Limiting) de Google de forma silenciosa. |
| **Buffer Interno** | FastAPI Asyncio Queue / Background Tasks | Cola estructurada no bloqueante en memoria para absorber picos de tráfico en webhooks sin requerir infraestructura externa de mensajería (como Redis o RabbitMQ). |

## **3\. Diseño de la Base de Datos Ampliada (Esquema SQL V3)**

Se inyectan metadatos de control para el estado de las vacaciones, el buffer de contingencia y el control de sincronización de calendarios.

\-- Tabla de Tareas (Modificada V3)  
CREATE TABLE tareas (  
    id VARCHAR(64) PRIMARY KEY,  
    ambito VARCHAR(12) NOT NULL CHECK (ambito IN ('laboral', 'personal')),  
    titulo VARCHAR(255) NOT NULL,  
    proyecto VARCHAR(100) DEFAULT NULL,  
    origen VARCHAR(100) NOT NULL,  
    fecha\_vence DATE DEFAULT NULL,  
    prioridad VARCHAR(10) NOT NULL CHECK (prioridad IN ('alta', 'media', 'baja')),  
    estado VARCHAR(15) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'completado')),  
    nivel\_hostigamiento INT DEFAULT 0,  
    google\_calendar\_event\_id VARCHAR(255) DEFAULT NULL,  
    sincronizado\_calendar BOOLEAN DEFAULT FALSE, \-- NUEVO: Bandera para la cola asíncrona del Worker  
    proxima\_alerta\_bloqueada\_hasta TIMESTAMP DEFAULT NULL,  
    ultima\_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT\_TIMESTAMP \-- NUEVO: Clave para Last-Write-Wins  
);

\-- NUEVO: Tabla de Configuración Global (Modo Vacaciones)  
CREATE TABLE configuracion\_sistema (  
    clave VARCHAR(50) PRIMARY KEY,  
    valor\_booleano BOOLEAN DEFAULT FALSE,  
    fecha\_liberacion TIMESTAMP DEFAULT NULL  
);

\-- NUEVO: Tabla Buffer Fail-Safe para Ingesta Rápida  
CREATE TABLE buffer\_ingesta\_contingencia (  
    id SERIAL PRIMARY KEY,  
    origen VARCHAR(50) NOT NULL,  
    contenido\_crudo TEXT NOT NULL,  
    procesado BOOLEAN DEFAULT FALSE,  
    fecha\_ingreso TIMESTAMP DEFAULT CURRENT\_TIMESTAMP  
);

## **4\. Endpoints y Lógica de Mitigación de Fallas**

### **4.1. Flujo de Ingesta Rápida (Fail-Safe Webhook)**

El webhook responde inmediatamente a la pasarela de Telegram tras persistir el texto crudo en la base de datos o en la cola local de asyncio, delegando el procesamiento costoso por IA a un Worker asíncrono independiente:

@app.post("/api/v1/tg/webhook")  
async def tg\_webhook\_fast\_ingest(update: TelegramUpdate, bg\_tasks: BackgroundTasks):  
    \# Guardar en almacenamiento seguro para mitigar caídas de la IA  
    await db.save\_to\_buffer(update.message.text)  
      
    \# Desacoplar procesamiento de OpenRouter  
    bg\_tasks.add\_task(procesar\_ia\_desde\_buffer, update.message.text, update.chat\_id)  
      
    \# Liberar a Telegram de inmediato (HTTP 200\)  
    return {"status": "queued"}

### **4.2. Mitigación de Rate Limiting con Google Calendar (Worker en Segundo Plano)**

Para evitar el bloqueo de API por ráfagas concurrentes de peticiones (Error HTTP 429), un Worker lee periódicamente los registros pendientes de sincronización procesándolos de manera secuencial controlada:

async def worker\_google\_calendar\_sync():  
    while True:  
        \# Obtener tareas no sincronizadas  
        tareas\_pendientes \= await db.tareas.select().where(sincronizado\_calendar=False).limit(10)  
        for tarea in tareas\_pendientes:  
            try:  
                await ejecutar\_llamada\_google\_calendar(tarea)  
                await db.tareas.update(id=tarea.id, sincronizado\_calendar=True)  
                await asyncio.sleep(2.0) \# Delay de cortesía de 2 segundos para control de cuota  
            except Exception as e:  
                logger.error(f"Falla temporal en Google API: {e}. Reintento en próximo ciclo.")  
        await asyncio.sleep(60) \# Revisión de cola cada minuto

### **4.3. Resolución de Concurrencia en Sincronización Local (Obsidian/Kiro)**

Al realizar una sincronización de tipo Pulling desde Kiro en el entorno corporativo, el endpoint \`/api/v1/sync/pull\` evalúa de forma explícita el campo \`ultima\_modificacion\` antes de autorizar una sobreescritura, evitando el fenómeno de Split-Brain:

@app.post("/api/v1/sync/pull")  
async def resolve\_concurrency\_pull(client\_task: TareaSyncSchema):  
    server\_task \= await db.tareas.get(id=client\_task.id)  
    if server\_task.ultima\_modificacion \> client\_task.ultima\_modificacion:  
        \# Los cambios de la nube (vía Telegram) son más recientes  
        return {"action": "REWRITE\_LOCAL", "data": server\_task}  
    elif client\_task.ultima\_modificacion \> server\_task.ultima\_modificacion:  
        \# Los cambios locales del PC corporativo ganan  
        await db.tareas.update\_from\_client(client\_task)  
        return {"action": "ACCEPTED"}  
    return {"action": "NO\_CHANGES"}  
