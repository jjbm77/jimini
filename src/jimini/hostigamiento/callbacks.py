from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from jimini.config import settings
from jimini.db import get_db

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def _answer(callback_query_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{TELEGRAM_API}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
        except Exception:
            pass


async def _edit_message(chat_id: int, message_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{TELEGRAM_API}/editMessageText",
                json={"chat_id": chat_id, "message_id": message_id, "text": text},
            )
        except Exception:
            pass


async def handle_hostigamiento_callback(callback_query: dict) -> bool:
    data = callback_query.get("data", "")
    cb_id = callback_query.get("id", "")
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]

    parts = data.split(":", 1)
    if len(parts) != 2:
        return False

    action, tarea_id = parts
    db = get_db()

    if action == "snooze_2h":
        hasta = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        result = db.table("tareas").update({"proxima_alerta_bloqueada_hasta": hasta}).eq("id", tarea_id).execute()
        if result.data:
            await _answer(cb_id, "⏳ Pospuesto 2 horas")
        else:
            await _answer(cb_id, "Esta tarea ya no existe.")
        return True

    if action == "snooze_manana":
        from dateutil import tz
        db_config = get_db()
        tz_res = db_config.table("configuracion_sistema").select("valor_texto").eq("clave", "zona_horaria_default").limit(1).execute()
        tz_name = "America/Lima"
        if tz_res.data and tz_res.data[0].get("valor_texto"):
            tz_name = tz_res.data[0]["valor_texto"]
        zona = tz.gettz(tz_name)
        tomorrow = datetime.now(tz=zona).date() + timedelta(days=1)
        manana_9 = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=zona)
        result = db.table("tareas").update({"proxima_alerta_bloqueada_hasta": manana_9.isoformat()}).eq("id", tarea_id).execute()
        if result.data:
            await _answer(cb_id, "📅 Pospuesto para mañana")
        else:
            await _answer(cb_id, "Esta tarea ya no existe.")
        return True

    if action == "completar":
        result = db.table("tareas").update({"estado": "completado"}).eq("id", tarea_id).execute()
        if result.data:
            await _answer(cb_id, "✅ Completada")
            await _edit_message(chat_id, message_id, "✅ Tarea completada.")
        else:
            await _answer(cb_id, "Esta tarea ya no existe.")
        return True

    if action == "descartar":
        result = db.table("tareas").update({"estado": "descartado"}).eq("id", tarea_id).execute()
        if result.data:
            await _answer(cb_id, "🗑️ Descartada")
            await _edit_message(chat_id, message_id, "🗑️ Tarea descartada.")
        else:
            await _answer(cb_id, "Esta tarea ya no existe.")
        return True

    return False
