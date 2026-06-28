from __future__ import annotations

import asyncio
import uuid

import httpx

from jimini.config import settings
from jimini.db import get_db

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
_MAX_FILE_SIZE = settings.max_audio_file_size_mb * 1024 * 1024

_CMD_RECURRENCIA = "/recurrencia"
_CMD_RECURRENCIAS = "/recurrencias"
_CMD_VACACIONES = "/vacaciones"
_CMD_FINDE = "/finde"
_CMD_TAREAS = "/tareas"
_CMD_HOY = "/hoy"
_CMD_SEMANA = "/semana"
_CMD_MES = "/mes"


async def handle_webhook(update: dict) -> dict:
    message = update.get("message")
    callback_query = update.get("callback_query")

    if callback_query:
        return await _handle_callback(callback_query)

    if not message:
        return {"ok": True, "detail": "no message"}

    chat_id = message["chat"]["id"]
    message_id = message["message_id"]

    if "text" in message:
        return await _handle_text(chat_id, message_id, message["text"])

    if "voice" in message:
        return await _handle_voice(chat_id, message_id, message["voice"])

    return {"ok": True, "detail": "unsupported message type"}


async def _handle_text(chat_id: int, message_id: int, text: str) -> dict:
    stripped = text.strip()

    if stripped == _CMD_RECURRENCIAS or stripped.startswith(_CMD_RECURRENCIAS + " "):
        return await _handle_list_recurrencias(chat_id)

    if stripped == _CMD_RECURRENCIA:
        await _send_telegram_message(
            chat_id,
            "Crea una recurrencia con: `/recurrencia <descripción>`\n"
            "Ej: `/recurrencia Pagar luz el día 5 de cada mes, personal`",
        )
        return {"ok": True, "detail": "usage info sent"}

    if stripped.startswith(_CMD_RECURRENCIA + " "):
        descripcion = stripped[len(_CMD_RECURRENCIA) + 1:]
        db = get_db()
        db.table("buffer_ingesta_contingencia").insert({
            "chat_id": chat_id,
            "telegram_message_id": message_id,
            "tipo_media": "texto",
            "tipo_mensaje": "recurrencia",
            "mensaje_raw": descripcion,
            "estado_procesamiento": "pendiente",
            "procesado": False,
        }).execute()
        return {"ok": True, "detail": "recurrencia queued"}

    if stripped.startswith(_CMD_VACACIONES) or stripped == _CMD_VACACIONES:
        from jimini.hostigamiento.comandos import handle_vacaciones
        return await handle_vacaciones(chat_id, stripped)

    if stripped == _CMD_FINDE or stripped.startswith(_CMD_FINDE + " "):
        from jimini.hostigamiento.comandos import handle_finde
        return await handle_finde(chat_id)

    if stripped == _CMD_TAREAS:
        from jimini.hostigamiento.comandos import handle_tareas
        return await handle_tareas(chat_id)

    if stripped in (_CMD_HOY, _CMD_SEMANA, _CMD_MES) or stripped.startswith(_CMD_MES + " "):
        if stripped == _CMD_HOY:
            from jimini.hostigamiento.comandos import handle_hoy
            return await handle_hoy(chat_id)
        if stripped == _CMD_SEMANA:
            from jimini.hostigamiento.comandos import handle_semana
            return await handle_semana(chat_id)
        if stripped == _CMD_MES:
            from jimini.hostigamiento.comandos import handle_mes
            return await handle_mes(chat_id, None)
        if stripped.startswith(_CMD_MES + " "):
            from jimini.hostigamiento.comandos import handle_mes
            return await handle_mes(chat_id, stripped[len(_CMD_MES) + 1:].strip())

    db = get_db()
    db.table("buffer_ingesta_contingencia").insert({
        "chat_id": chat_id,
        "telegram_message_id": message_id,
        "tipo_media": "texto",
        "tipo_mensaje": "tarea",
        "mensaje_raw": text,
        "estado_procesamiento": "pendiente",
        "procesado": False,
    }).execute()
    return {"ok": True, "detail": "text queued"}


async def _handle_list_recurrencias(chat_id: int) -> dict:
    db = get_db()
    result = (
        db.table("plantillas_recurrencia")
        .select("id, titulo, ambito, tipo_recurrencia, dia_del_mes, mes_del_anio, dia_de_semana, dias_para_vencer, prioridad")
        .eq("activa", True)
        .order("id")
        .execute()
    )
    rows = result.data if result.data else []

    if not rows:
        await _send_telegram_message(chat_id, "No tienes recurrencias activas.")
        return {"ok": True, "detail": "no recurrencias"}

    lines = ["📋 *Recurrencias activas:*\n"]
    for r in rows:
        dia_str = _format_dia(r)
        lines.append(
            f"📌 #{r['id']} \"{r['titulo']}\" — {_format_tipo(r)} — "
            f"{r['ambito'].capitalize()} — Vence en {r['dias_para_vencer']} días"
        )

    await _send_telegram_message(chat_id, "\n".join(lines))
    return {"ok": True, "detail": "recurrencias listed"}


def _format_dia(r: dict) -> str:
    if r.get("dia_del_mes") == 0:
        return "último día del mes"
    if r.get("dia_del_mes"):
        return f"día {r['dia_del_mes']}"
    if r.get("dia_de_semana") is not None:
        dias = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
        return dias[r["dia_de_semana"]]
    if r.get("mes_del_anio") and r.get("dia_del_mes"):
        return f"{r['dia_del_mes']}/{r['mes_del_anio']}"
    return ""


def _format_tipo(r: dict) -> str:
    tipo = r["tipo_recurrencia"]
    if tipo == "diaria":
        return "Diaria"
    if tipo == "semanal":
        return "Semanal"
    if tipo == "mensual":
        return "Mensual"
    if tipo == "anual":
        return "Anual"
    return tipo.capitalize()


async def _handle_voice(chat_id: int, message_id: int, voice: dict) -> dict:
    file_size = voice.get("file_size", 0)
    if file_size > _MAX_FILE_SIZE:
        await _send_telegram_message(
            chat_id,
            "Audio demasiado grande. Máximo 25MB.",
            reply_to=message_id,
        )
        return {"ok": True, "detail": "audio too large"}

    file_id = voice["file_id"]

    ogg_data = await _download_audio(file_id)
    if ogg_data is None:
        return {"ok": False, "detail": "download failed", "status_code": 500}

    storage_path = await _upload_to_storage(ogg_data)
    if storage_path is None:
        return {"ok": False, "detail": "upload failed", "status_code": 500}

    db = get_db()
    signed_url = _create_signed_url_sync(storage_path)
    if signed_url is None:
        return {"ok": False, "detail": "signed URL generation failed", "status_code": 500}

    db.table("buffer_ingesta_contingencia").insert({
        "chat_id": chat_id,
        "telegram_message_id": message_id,
        "tipo_media": "voz",
        "tipo_mensaje": "tarea",
        "file_id": file_id,
        "storage_path": storage_path,
        "signed_url": signed_url,
        "estado_procesamiento": "pendiente",
        "procesado": False,
    }).execute()

    return {"ok": True, "detail": "voice queued"}


async def _handle_callback(callback_query: dict) -> dict:
    from jimini.notifications.dlq import handle_recurrencia_deshacer_callback

    data = callback_query.get("data", "")

    if data.startswith("recurrencia_deshacer:"):
        await handle_recurrencia_deshacer_callback(callback_query)
        return {"ok": True, "detail": "callback handled"}

    from jimini.hostigamiento.callbacks import handle_hostigamiento_callback
    handled = await handle_hostigamiento_callback(callback_query)
    if handled:
        return {"ok": True, "detail": "callback handled"}

    return {"ok": True, "detail": "unknown callback"}


async def _download_audio(file_id: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(3):
            try:
                resp = await client.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id})
                resp.raise_for_status()
                file_path = resp.json()["result"]["file_path"]
                download_url = f"{TELEGRAM_API}/{file_path}"
                audio_resp = await client.get(download_url)
                audio_resp.raise_for_status()
                return audio_resp.content
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    return None
    return None


async def _upload_to_storage(ogg_data: bytes) -> str | None:
    try:
        db = get_db()
        file_uuid = uuid.uuid4().hex
        storage_path = f"{file_uuid}.ogg"
        db.storage.from_(settings.supabase_bucket_audio).upload(
            storage_path, ogg_data, file_options={"content-type": "audio/ogg"}
        )
        return storage_path
    except Exception:
        return None


def _create_signed_url_sync(storage_path: str) -> str | None:
    db = get_db()
    ttl = settings.signed_url_ttl_hours * 3600
    result = db.storage.from_(settings.supabase_bucket_audio).create_signed_url(
        storage_path, ttl
    )
    if result:
        return result.get("signedURL") or result.get("signed_url")
    return None


async def _send_telegram_message(chat_id: int, text: str, reply_to: int | None = None) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {"chat_id": chat_id, "text": text}
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
