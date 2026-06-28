## 1. Tests para signed_url_is_expired

- [x] 1.1 Crear `tests/test_storage.py` con `test_url_sin_expires` (retorna False)
- [x] 1.2 Test `test_url_expirada` (timestamp pasado → True)
- [x] 1.3 Test `test_url_vigente` (timestamp futuro → False)
- [x] 1.4 Test `test_url_parse_error` (formato inválido → False)

## 2. Tests para _build_keyboard

- [x] 2.1 Test nivel 0: solo [Completar]
- [x] 2.2 Test nivel 1: [Snooze 2h, Mañana] + [Completar]
- [x] 2.3 Test nivel 2: [Snooze 2h, Mañana] + [Completar]
- [x] 2.4 Test nivel 3: [Completar] + [Descartar]
- [x] 2.5 Test nivel 4: [Completar] + [Descartar]
- [x] 2.6 Test nivel default: [Completar]

## 3. Tests para _month_grid

- [x] 3.1 Test mes 31 días (enero): verificar 31 celdas + formato semana
- [x] 3.2 Test mes 28 días (febrero no bisiesto): verificar 28 celdas
- [x] 3.3 Test con tareas en celda: verificar emoji 🔵 en celda correcta

## 4. Tests para _get_text_for_ia

- [x] 4.1 Test entrada de texto: retorna mensaje_raw tal cual
- [x] 4.2 Test voz con transcripción cacheada: retorna transcripcion
- [x] 4.3 Test voz sin transcripción: invoca Groq, guarda resultado, lo retorna
- [x] 4.4 Test signed URL expirada: regenera URL, actualiza DB
- [x] 4.5 Test detección /recurrencia en voz: ajusta tipo_mensaje en buffer

## 5. Tests para worker_loop_hostigamiento

- [x] 5.1 Test tarea sube de nivel (1→2): verifica envío de alerta + update nivel_hostigamiento
- [x] 5.2 Test tarea se repite mismo nivel: verifica update proxima_alerta_bloqueada_hasta
- [x] 5.3 Test tarea bloqueada por modo vacaciones: no envía alerta
- [x] 5.4 Test tarea sin chat_id: skip silencioso