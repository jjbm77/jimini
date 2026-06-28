from __future__ import annotations

import logging

import httpx

from jimini.buffer.lease import BufferMessage
from jimini.config import settings
from jimini.db import get_db

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def notify_dlq_telegram(message: BufferMessage) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        if message.tipo_media == "texto":
            text = (
                "⚠️ No pude procesar tu mensaje tras 3 intentos.\n"
                f"Texto: {message.mensaje_raw}\n\n"
                "Revísalo manualmente."
            )
            await _send_message(client, message.chat_id, text)

        elif message.tipo_media == "voz":
            if message.transcripcion:
                text = (
                    "⚠️ No pude procesar tu audio tras 3 intentos.\n"
                    f"Transcripción: {message.transcripcion}\n\n"
                    "Revísalo manualmente."
                )
                await _send_message(client, message.chat_id, text)
            else:
                await _notify_voice_with_fallback(client, message)


async def _notify_voice_with_fallback(
    client: httpx.AsyncClient, message: BufferMessage
) -> None:
    fallback_text = (
        "⚠️ No pude transcribir tu audio tras 3 intentos.\n"
        "Revisa el audio adjunto y vuelve a escribir la tarea manualmente."
    )

    forwarded = await _try_forward_message(client, message.chat_id, message.telegram_message_id)
    if forwarded:
        await _send_message(client, message.chat_id, fallback_text)
        return

    sent = await _try_send_voice(client, message.chat_id, message.file_id)
    if sent:
        await _send_message(client, message.chat_id, fallback_text)
        return

    terminal_text = (
        "⚠️ No pude transcribir tu audio tras 3 intentos y no fue posible reenviarlo.\n"
        "Contacta al administrador para recuperar el audio desde la base de datos.\n"
        f"Ref: {message.storage_path}"
    )
    await _send_message(client, message.chat_id, terminal_text)
    logger.warning(
        "DLQ audio fallback exhausted for msg %s. Storage path: %s",
        message.id,
        message.storage_path,
    )


async def _try_forward_message(
    client: httpx.AsyncClient, chat_id: int, message_id: int
) -> bool:
    try:
        resp = await client.post(
            f"{TELEGRAM_API}/forwardMessage",
            json={
                "chat_id": chat_id,
                "from_chat_id": chat_id,
                "message_id": message_id,
            },
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _try_send_voice(
    client: httpx.AsyncClient, chat_id: int, file_id: str | None
) -> bool:
    if not file_id:
        return False
    try:
        resp = await client.post(
            f"{TELEGRAM_API}/sendVoice",
            json={"chat_id": chat_id, "voice": file_id},
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _send_message(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    try:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
    except Exception as e:
        logger.error("Failed to send DLQ notification to %s: %s", chat_id, e)


async def send_recurrencia_confirmation(chat_id: int, plantilla: dict) -> None:
    plantilla_id = plantilla["id"]
    titulo = plantilla["titulo"]
    ambito = plantilla.get("ambito", "laboral")
    prioridad = plantilla.get("prioridad", "media")
    dias = plantilla.get("dias_para_vencer", 0)
    tipo = plantilla.get("tipo_recurrencia", "")
    intervalo = plantilla.get("intervalo", 1)

    tipo_desc = _describe_tipo(tipo, intervalo)
    dia_desc = _describe_dia(plantilla)

    text = (
        f"✅ Recurrencia creada:\n"
        f"📌 {titulo}\n"
        f"📅 {tipo_desc} — {dia_desc}\n"
        f"🏠 {ambito.capitalize()}\n"
        f"⏰ Vence en {dias} días\n"
        f"⚡ Prioridad: {prioridad}"
    )

    reply_markup = {
        "inline_keyboard": [[
            {
                "text": "↩️ Deshacer",
                "callback_data": f"recurrencia_deshacer:{plantilla_id}",
            }
        ]]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "reply_markup": reply_markup,
                },
            )
        except Exception as e:
            logger.error("Failed to send recurrencia confirmation to %s: %s", chat_id, e)


async def handle_recurrencia_deshacer_callback(callback_query: dict) -> None:
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query.get("data", "")
    callback_query_id = callback_query.get("id", "")

    try:
        plantilla_id = int(data.split(":")[1])
    except (IndexError, ValueError):
        plantilla_id = None

    if plantilla_id is None:
        await _answer_callback(callback_query_id, "Error: callback inválido")
        return

    db = get_db()
    result = (
        db.table("plantillas_recurrencia")
        .select("id")
        .eq("id", plantilla_id)
        .execute()
    )

    if not result.data:
        await _answer_callback(callback_query_id, "Esta recurrencia ya no existe.")
        return

    db.table("plantillas_recurrencia").delete().eq("id", plantilla_id).execute()

    await _answer_callback(callback_query_id, "✅ Recurrencia eliminada")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{TELEGRAM_API}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "~~Recurrencia eliminada~~",
                },
            )
        except Exception:
            pass


async def _answer_callback(callback_query_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{TELEGRAM_API}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
        except Exception as e:
            logger.error("Failed to answer callback: %s", e)


def _describe_tipo(tipo: str, intervalo: int) -> str:
    if intervalo == 1:
        return {"diaria": "Diaria", "semanal": "Semanal",
                "mensual": "Mensual", "anual": "Anual"}.get(tipo, tipo.capitalize())
    if tipo == "mensual":
        if intervalo == 3:
            return "Trimestral"
        if intervalo == 6:
            return "Semestral"
        return f"Cada {intervalo} meses"
    if tipo == "semanal":
        if intervalo == 2:
            return "Quincenal"
        return f"Cada {intervalo} semanas"
    if tipo == "anual":
        return f"Cada {intervalo} años"
    return tipo.capitalize()


def _describe_dia(plantilla: dict) -> str:
    dia_del_mes = plantilla.get("dia_del_mes")
    mes = plantilla.get("mes_del_anio")
    dia_sem = plantilla.get("dia_de_semana")
    tipo = plantilla.get("tipo_recurrencia", "")

    if tipo == "diaria":
        return "todos los días"
    if tipo == "semanal" and dia_sem is not None:
        dias = ["domingo", "lunes", "martes", "miércoles",
                "jueves", "viernes", "sábado"]
        return f"cada {dias[dia_sem]}"
    if tipo == "mensual":
        if dia_del_mes == 0:
            return "último día del mes"
        return f"día {dia_del_mes}"
    if tipo == "anual" and dia_del_mes and mes:
        return f"{dia_del_mes}/{mes}"
    return ""
