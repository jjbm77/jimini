from __future__ import annotations

import asyncio
import logging
from datetime import UTC

import httpx

from jimini.config import settings
from jimini.db import get_db
from jimini.hostigamiento.core import (
    auto_limpiar_modos,
    calcular_nivel,
    debe_alertar,
    dentro_horario_activo,
    frecuencia_nivel,
    get_modo,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def _query_tareas_pendientes() -> list[dict]:
    db = get_db()
    result = (
        db.table("tareas")
        .select("id, chat_id, titulo, fecha_vence, ambito, prioridad, nivel_hostigamiento, proxima_alerta_bloqueada_hasta")
        .eq("estado", "pendiente")
        .not_.is_("fecha_vence", "null")
        .execute()
    )
    return result.data if result.data else []


async def enviar_alerta_telegram(chat_id: int, tarea: dict, nivel: int) -> None:
    titulo = tarea.get("titulo", "sin título")
    dias_vencida = 0
    if tarea.get("fecha_vence"):
        from datetime import date
        fv = tarea["fecha_vence"]
        if isinstance(fv, str):
            fv = date.fromisoformat(fv)
        dias_vencida = (date.today() - fv).days

    mensajes = {
        0: f"📅 Recuerda: '{titulo}' vence mañana.",
        1: f"⚠️ '{titulo}' vence HOY. ¿Lo resolvemos?",
        2: f"🔴 '{titulo}' está vencida ({dias_vencida}d). Hay que resolverlo.",
        3: f"🚨 '{titulo}' lleva {dias_vencida} días vencida. ¿Sigue siendo relevante?",
        4: f"📈 '{titulo}' lleva una semana+ vencida. Necesito que la completes o descartes.",
    }

    text = mensajes.get(nivel, f"📋 '{titulo}' necesita atención.")

    keyboard = _build_keyboard(tarea["id"], nivel)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            payload = {"chat_id": chat_id, "text": text}
            if keyboard:
                payload["reply_markup"] = {"inline_keyboard": keyboard}
            await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
        except Exception as e:
            logger.error("Failed to send alert %s: %s", tarea["id"], e)


def _build_keyboard(tarea_id: str, nivel: int) -> list[list[dict]]:
    completar = [{"text": "✅ Completar", "callback_data": f"completar:{tarea_id}"}]
    descartar = {"text": "🗑️ Descartar", "callback_data": f"descartar:{tarea_id}"}
    snooze_2h = {"text": "⏳ 2h", "callback_data": f"snooze_2h:{tarea_id}"}
    snooze_manana = {"text": "📅 Mañana", "callback_data": f"snooze_manana:{tarea_id}"}

    if nivel == 0:
        return [completar]
    if nivel == 1:
        return [[snooze_2h, snooze_manana], completar]
    if nivel == 2:
        return [[snooze_2h, snooze_manana], completar]
    if nivel == 3:
        return [completar, [descartar]]
    if nivel == 4:
        return [completar, [descartar]]
    return [completar]


async def worker_loop_hostigamiento() -> None:
    logger.info("Hostigamiento worker loop started")
    while True:
        try:
            auto_limpiar_modos()

            modo_vacaciones = get_modo("modo_vacaciones")
            modo_finde = get_modo("modo_finde")

            tareas = _query_tareas_pendientes()

            for tarea in tareas:
                try:
                    nivel = calcular_nivel(tarea.get("fecha_vence"))
                    if nivel < 0:
                        continue

                    if not debe_alertar(
                        tarea.get("ambito", "laboral"),
                        nivel,
                        modo_vacaciones,
                        modo_finde,
                    ):
                        continue

                    if not dentro_horario_activo():
                        continue

                    nivel_actual = tarea.get("nivel_hostigamiento", 0) or 0
                    bloqueado_hasta = tarea.get("proxima_alerta_bloqueada_hasta")
                    debe_enviar = False

                    if nivel > nivel_actual:
                        debe_enviar = True
                    elif nivel == nivel_actual:
                        if bloqueado_hasta is None:
                            debe_enviar = True

                    if debe_enviar:
                        chat_id = tarea.get("chat_id")
                        if not chat_id:
                            continue

                        await enviar_alerta_telegram(chat_id, tarea, nivel)

                        freq = frecuencia_nivel(nivel)
                        update_data = {"nivel_hostigamiento": nivel}
                        if freq is not None:
                            from datetime import datetime
                            hasta = datetime.now(UTC) + freq
                            update_data["proxima_alerta_bloqueada_hasta"] = hasta.isoformat()
                        else:
                            update_data["proxima_alerta_bloqueada_hasta"] = None

                        db = get_db()
                        db.table("tareas").update(update_data).eq("id", tarea["id"]).execute()

                except Exception as e:
                    logger.error("Error evaluando tarea %s: %s", tarea.get("id"), e)

            await asyncio.sleep(60)

        except Exception as e:
            logger.exception("Error en worker hostigamiento: %s", e)
            await asyncio.sleep(10)
