# **Documento de Requerimientos Funcionales: Sistema Omnicanal de Gestión de Pendientes con IA**

**Autor:** Jaime Jesus Bustamante Marcotti  
**Fecha de Creación:** 27 de junio de 2026  
**Estado:** Línea Base de Requerimientos Ampliada (Resiliencia y Control SRE)  
**Versión:** V3

## **1\. Declaración de la Necesidad de Negocio (Business Need)**

La Jefatura de Área de Proyectos gestiona múltiples iniciativas en paralelo, actuando como receptor central de solicitudes, cambios y requerimientos de diversos stakeholders de la compañía. Actualmente, estas solicitudes ingresan de forma descentralizada a través de múltiples canales (Microsoft Teams, Outlook y minutas verbales de reuniones).  
El usuario cuenta con una solución local robusta: un asistente/agente llamado **Kiro** que procesa la información entrante y la transforma en archivos Markdown (.md), alimentando una **LLM Wiki personal** que se visualiza a través de **Obsidian**. Esta base de conocimiento local está inspirada en la arquitectura compacta de recuperación/búsqueda de Andrej Karpathy (Gist base).  
A pesar de que el procesamiento local y el enlazado de conceptos funcionan de manera óptima para centralizar el conocimiento, el sistema presenta brechas críticas en la gestión activa de compromisos:

* **Pasividad del Backlog:** La información de los pendientes se almacena de forma estática en Obsidian. El sistema no posee capacidad nativa para escanear activamente esas tareas, calcular fechas límite ni generar alertas proactivas ante vencimientos inminentes.  
* **Inaccesibilidad Remota:** Al estar la solución (Kiro \+ Obsidian) confinada estrictamente de manera local en el computador corporativo, el usuario no tiene ninguna vía para consultar su hoja de pendientes actualizados cuando se encuentra en otro dispositivo.  
* **Ausencia de Reportabilidad y Notificaciones:** Falta un módulo de inteligencia temporal y activa que extraiga los metadatos de las tareas y entregue notificaciones de vencimiento, forzando al usuario a responder.  
* **Falta de Gestión de Rutinas Cíclicas:** El sistema carece de un motor nativo para manejar tareas repetitivas (como pagos mensuales de cuentas o revisiones semanales), obligando a la ingesta manual recurrente.  
* **Ausencia de Vista de Línea de Tiempo:** Falta una abstracción visual en formato de calendario para correlacionar tareas sin tener que ingresar directamente a los listados de texto del Bot de Telegram.

**Objetivo de Negocio:** Diseñar un flujo de trabajo y una aplicación web externa (accesible de manera multi-dispositivo) que interactúe con componentes de Inteligencia Artificial (vía la API gratuita de OpenRouter) para transformar los requerimientos capturados en tareas dinámicas, con gestión explícita de fechas de vencimiento, sistema proactivo y agresivo de alertas (Telegram Bot), un motor integrado de tareas recurrentes, sincronización directa con Google Calendar segregado por ámbitos y sincronización bidireccional limpia entre el entorno corporativo y el personal, asegurando alta disponibilidad, control de concurrencia y tolerancia total a fallas en la nube.

## **2\. Definición de Ámbitos (Higiene de Seguridad y Privacidad)**

El sistema operará bajo dos ámbitos estrictamente separados mediante lógica de software para respetar las restricciones de la máquina corporativa y resguardar la privacidad personal:

| Ámbito | Origen de Datos | Direccionalidad del Flujo | Destino / Almacenamiento   |
| :---- | :---- | :---- | :---- |
| **Laboral** | Teams, Outlook, Reuniones (vía Kiro en PC corporativo) | Bidireccional (Sube a la App Web y baja los cambios a Obsidian) | PC Oficina (.md), App Web (DB) y Google Calendar ("Pepe Grillo \- Laboral") |
| **Personal** | Telegram Bot, Interfaz Web (Asuntos propios, AlToque.Shop, etc.) | Unidireccional Estricto (Nace y muere en la App Web/Nube) | Sólo App Web (DB) y Google Calendar ("Pepe Grillo \- Personal"). Invisible para la PC corporativa. |

## **3\. Registro y Estructura de Tareas (Framework Simplicidad \+ Efectividad)**

### **3.1. Requerimiento como Archivo Independiente (.md)**

\---  
id: "req-2026-001"  
ambito: "laboral"  
title: "Migración de lógica Ciclo Ancla a Pay Studio"  
project: "Iron"  
source: "Outlook (Mail de Juan Pérez)"  
created: 2026-06-27  
due: 2026-07-05  
priority: "alta"  
status: "pendiente"  
ultima\_modificacion: 2026-06-27T19:20:00Z  
\---  
\# Detalles del Requerimiento  
\[Contenido extraído de forma local por Kiro\]

### **3.2. Manejo de Desestructura, Subtareas y Relaciones Cruzadas**

* **Relaciones Cruzadas:** Se utilizarán Wikilinks (  
  `[[NombreNota]]`). El script extractor mapeará dependencias entre proyectos dentro de la App Web.  
* **Subtareas:** Se manejarán mediante indentación estándar en Markdown (Tabulación). Las subtareas se reflejarán en la App Web como un árbol anidado.  
* **Tareas Sueltas / Inbox:** El campo  
  `project`y el campo  
  `due`serán opcionales en la base de datos (admiten nulos), permitiendo un volcado rápido de ideas ("Dumping") sin fechas asignadas que se listará mediante el comando de bandeja de entrada.

## **4\. Requerimientos Funcionales de Resiliencia y Control Temporal (A Prueba de Balas)**

### **RF05 \- Motor de Generación de Tareas Recurrentes**

El sistema deberá evaluar diariamente a las 00:01 AM las plantillas de recurrencia registradas. Si una plantilla coincide con los criterios temporales del día actual (ej: día 5 del mes, o día de la semana específico), el backend clonará la plantilla automáticamente generando una tarea activa con estado "pendiente" y su respectiva fecha límite calculada, integrándola de inmediato al flujo de alertas de Pepe Grillo.

### **RF06 \- Sincronización Unidireccional con Google Calendar**

Cada vez que una tarea con fecha de vencimiento sea creada, modificada o completada en el sistema, el backend invocará de forma asíncrona la API de Google Calendar:

* Las tareas del ámbito  
  `laboral`se reflejarán como eventos de todo el día en el calendario secundario privado **"Pepe Grillo \- Laboral"**.  
* Las tareas del ámbito  
  `personal`se registrarán en el calendario secundario privado **"Pepe Grillo \- Personal"**.  
* Al completar una tarea en Telegram, el título del evento correspondiente en el calendario se mutará anteponiendo el string visual "✅ ".

### **RF07 \- Botones de Control de Flujo Avanzados (Snooze Inteligente)**

El bot de Telegram incluirá botones interactivos de control temporal rápidos (

`[⏳ Posponer 2 horas]`

,

`[📅 Mañana]`

) en sus alertas activas de nivel 1 y 2\. Al ser acionados por el usuario, el backend reprogramará automáticamente la hora del próximo escaneo de inacción para esa tarea, deteniendo temporalmente la escalada de hostigamiento sin alterar la fecha límite real del requerimiento.

### **RF08 \- \[NUEVO\] Ingesta Segura Anti-Caídas (Fail-Safe Inbox)**

Para evitar la pérdida de requerimientos ingresados por Telegram ante fallas externas (como indisponibilidad de OpenRouter o Supabase), el webhook de entrada procesará el texto crudo guardándolo de inmediato en una cola temporal de entrada (Buffer) y retornará un HTTP 200 OK de forma instantánea a Telegram. El procesamiento por IA se realizará en un hilo asíncrono desacoplado asegurando que ningún mensaje sea ignorado o perdido.

### **RF09 \- \[NUEVO\] Resolución de Conflictos por Concurrencia (Split-Brain Mitigation)**

El script local (Kiro) y la App Web implementarán una estrategia de resolución de conflictos de tipo "El último cambio gana" (Last-Write-Wins) basada en la estampa de tiempo universal (\`ultima\_modificacion\`). Si un archivo .md de Obsidian posee una modificación más antigua que el registro de la DB central, el script local reescribirá el archivo local absteniéndose de pisar la manguera a los cambios realizados en Telegram.

### **RF10 \- \[NUEVO\] Control de Estado de Descanso (Modo Vacaciones / Fin de Semana)**

El sistema admitirá estados de desconexión global mediante los comandos de Telegram

`/vacaciones`

y

`/finde`

. Al activarse, el motor Pepe Grillo suspenderá automáticamente todas las rutinas de hostigamiento asociadas al ámbito

`laboral`

hasta la fecha de retorno especificada o el día lunes a las 08:30 AM, manteniendo activas únicamente las alertas personales esenciales.  
