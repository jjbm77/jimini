from __future__ import annotations

import asyncio
import json
import logging

from jimini.buffer.lease import (
    BufferMessage,
    claim_next_message,
    get_idioma_config,
    mark_completed,
    mark_failed,
)
from jimini.config import settings
from jimini.db import get_db
from jimini.notifications.dlq import (
    notify_dlq_telegram,
    send_recurrencia_confirmation,
)
from jimini.storage.supabase import regenerate_signed_url, signed_url_is_expired
from jimini.transcription.provider import get_provider

logger = logging.getLogger(__name__)

_openrouter_http = None

_TAREA_SYSTEM_PROMPT = (
    "Extract task information from the user's message. "
    "Return JSON with: titulo (string, required), ambito ('laboral'|'personal'|null), "
    "proyecto (string|null), fecha_vence (YYYY-MM-DD|null), prioridad ('alta'|'media'|'baja'|null). "
    "If unsure about a field, set it to null. For ambito, default to 'laboral' unless clearly personal."
)

_RECURRENCIA_SYSTEM_PROMPT = (
    "Extract recurrence information from the user's message. "
    "Return JSON with: "
    "titulo (string, required), "
    "ambito ('laboral'|'personal'|null, default 'laboral'), "
    "tipo_recurrencia ('diaria'|'semanal'|'mensual'|'anual'), "
    "intervalo (int, default 1), "
    "dia_del_mes (int|null, 0=último día del mes), "
    "mes_del_anio (int|null), "
    "dia_de_semana (int|null, 0=domingo..6=sábado), "
    "dias_para_vencer (int, default 0), "
    "prioridad ('alta'|'media'|'baja'|null, default 'media'), "
    "proyecto (string|null). "
    "Map 'fin de mes' to dia_del_mes=0. "
    "Map 'cada lunes' to dia_de_semana=1, 'martes'=2, 'miércoles'=3, 'jueves'=4, 'viernes'=5, 'sábado'=6, 'domingo'=0. "
    "Map 'trimestral' to tipo_recurrencia='mensual', intervalo=3. "
    "Map 'quincenal' to tipo_recurrencia='semanal', intervalo=2. "
    "Map 'cada 2 meses' to tipo_recurrencia='mensual', intervalo=2. "
    "If unsure about a field, set it to null or its default."
)


async def _get_openrouter_http():
    global _openrouter_http
    if _openrouter_http is None:
        import httpx
        _openrouter_http = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    return _openrouter_http


async def _call_openrouter(system_prompt: str, text: str) -> dict:
    client = await _get_openrouter_http()
    payload = {
        "model": "~openai/gpt-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_object"},
    }
    response = await client.post("/chat/completions", json=payload)
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def _structure_tarea(text: str) -> dict:
    return await _call_openrouter(_TAREA_SYSTEM_PROMPT, text)


async def _structure_plantilla(text: str) -> dict:
    return await _call_openrouter(_RECURRENCIA_SYSTEM_PROMPT, text)


async def process_message(msg: BufferMessage) -> None:
    try:
        text_for_ia = await _get_text_for_ia(msg)

        if not text_for_ia:
            raise ValueError("No text available for IA processing")

        if msg.tipo_mensaje == "recurrencia":
            await _process_recurrencia(msg, text_for_ia)
        else:
            await _process_tarea(msg, text_for_ia)

        mark_completed(msg.id)

    except Exception as e:
        logger.error("Error processing message %s: %s", msg.id, e)
        new_status = mark_failed(msg.id, msg.intentos_fallidos)
        if new_status == "error_permanente":
            await notify_dlq_telegram(msg)


async def _get_text_for_ia(msg: BufferMessage) -> str | None:
    if msg.tipo_media == "voz":
        language = get_idioma_config() or settings.transcripcion_idioma_default

        if msg.signed_url and signed_url_is_expired(msg.signed_url):
            new_url = regenerate_signed_url(msg.storage_path)
            db = get_db()
            db.table("buffer_ingesta_contingencia").update(
                {"signed_url": new_url}
            ).eq("id", msg.id).execute()
            msg.signed_url = new_url

        if msg.transcripcion is None:
            provider = get_provider()
            transcripcion_text = await provider.transcribe(msg.signed_url, language)
            db = get_db()
            db.table("buffer_ingesta_contingencia").update(
                {"transcripcion": transcripcion_text}
            ).eq("id", msg.id).execute()
            text = transcripcion_text
        else:
            text = msg.transcripcion

        if text and text.strip().startswith("/recurrencia"):
            db = get_db()
            db.table("buffer_ingesta_contingencia").update(
                {"tipo_mensaje": "recurrencia"}
            ).eq("id", msg.id).execute()
            msg.tipo_mensaje = "recurrencia"
            stripped = text.strip()
            if stripped.startswith("/recurrencia "):
                text = stripped[len("/recurrencia "):]

        return text

    return msg.mensaje_raw


async def _process_tarea(msg: BufferMessage, text: str) -> None:
    tarea = await _structure_tarea(text)
    db = get_db()
    db.table("tareas").insert({
        "id": f"tg-{msg.chat_id}-{msg.telegram_message_id}",
        "chat_id": msg.chat_id,
        "ambito": tarea.get("ambito", "laboral"),
        "titulo": tarea["titulo"],
        "proyecto": tarea.get("proyecto"),
        "origen": f"telegram-{msg.tipo_media}",
        "fecha_vence": tarea.get("fecha_vence"),
        "prioridad": tarea.get("prioridad", "media"),
        "estado": "pendiente",
    }).execute()


async def _process_recurrencia(msg: BufferMessage, text: str) -> None:
    plantilla = await _structure_plantilla(text)

    if not plantilla.get("titulo"):
        raise ValueError("IA did not return a titulo for the plantilla")

    db = get_db()
    result = db.table("plantillas_recurrencia").insert({
        "titulo": plantilla["titulo"],
        "ambito": plantilla.get("ambito", "laboral"),
        "proyecto": plantilla.get("proyecto"),
        "prioridad": plantilla.get("prioridad", "media"),
        "origen": f"telegram-{msg.tipo_media}",
        "tipo_recurrencia": plantilla["tipo_recurrencia"],
        "intervalo": plantilla.get("intervalo", 1),
        "dia_del_mes": plantilla.get("dia_del_mes"),
        "mes_del_anio": plantilla.get("mes_del_anio"),
        "dia_de_semana": plantilla.get("dia_de_semana"),
        "dias_para_vencer": plantilla.get("dias_para_vencer", 0),
        "activa": True,
        "fecha_inicio": "today()",
    }).execute()

    if result.data and len(result.data) > 0:
        plantilla_id = result.data[0]["id"]
        await send_recurrencia_confirmation(msg.chat_id, result.data[0])


async def worker_loop() -> None:
    logger.info("Worker loop started")
    while True:
        try:
            msg = claim_next_message()
            if msg is None:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue
            await process_message(msg)
        except Exception as e:
            logger.exception("Unhandled error in worker loop: %s", e)
            await asyncio.sleep(5)
