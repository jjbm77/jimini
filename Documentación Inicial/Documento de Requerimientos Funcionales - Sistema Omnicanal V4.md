# **Documento de Requerimientos Funcionales: Sistema Omnicanal de Gestión de Pendientes con IA**

**Autor:** Jaime Jesus Bustamante Marcotti  
**Fecha de Creación:** 27 de junio de 2026  
**Estado:** Línea Base de Requerimientos de Producción  
**Versión:** V4 (Producción Confiable)

## **1\. Declaración de la Necesidad de Negocio**

La Jefatura de Área de Proyectos gestiona múltiples iniciativas en paralelo, actuando como receptor central de solicitudes, cambios y requerimientos de diversos stakeholders de la compañía. El sistema actual presenta brechas en la persistencia ante picos de tráfico y fallos volátiles de memoria.

## **2\. Requerimientos Críticos de Resiliencia (V4)**

* **RF01 \- Ingesta Durable (Fail-Safe Buffer):** El sistema debe persistir el mensaje crudo de Telegram inmediatamente en la tabla física de la base de datos (buffer\_ingesta\_contingencia) con estado procesado \= false y retornar un HTTP 200 de inmediato. Queda estrictamente prohibido el uso de colas puras en memoria RAM (como asyncio.Queue sin persistencia) para evitar la pérdida de mensajes ante reinicios del servidor.  
* **RF02 \- Manejo de Mensajes Corruptos (Dead Letter Queue):** Si un mensaje falla en el procesamiento de la IA (OpenRouter), se incrementará un contador de intentos\_fallidos. Al llegar al tercer intento, el mensaje se moverá a estado error\_permanente, saldrá de la cola activa y se enviará una notificación proactiva al usuario por Telegram para revisión manual.  
* **RF03 \- Resolución de Concurrencia Avanzada:** Se implementará la estrategia Last-Write-Wins (LWW) a nivel de campo o registro validando la estampa de tiempo ultima\_modificacion.