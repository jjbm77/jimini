from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx

from jimini.config import settings
from jimini.db import get_db

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def _send(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
        except Exception:
            pass


async def handle_vacaciones(chat_id: int, text: str) -> dict:
    from jimini.hostigamiento.core import get_modo

    stripped = text.strip()

    if stripped == "/vacaciones" or stripped == "/vacaciones ":
        modo = get_modo("modo_vacaciones")
        if modo and modo.get("fecha_liberacion"):
            await _send(chat_id, f"🏖️ Modo vacaciones activo hasta {modo['fecha_liberacion']}.")
        else:
            await _send(chat_id, "No estás en modo vacaciones.\nUsa: `/vacaciones DD/MM/YYYY`")
        return {"ok": True, "detail": "vacaciones status"}

    fecha_str = stripped[len("/vacaciones "):].strip()
    try:
        try:
            fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
        except ValueError:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        await _send(chat_id, "Formato de fecha inválido. Usa DD/MM/YYYY o YYYY-MM-DD.")
        return {"ok": True, "detail": "invalid date"}

    if fecha <= date.today():
        await _send(chat_id, "La fecha debe ser futura.")
        return {"ok": True, "detail": "past date"}

    db = get_db()
    db.table("configuracion_sistema").upsert({
        "clave": "modo_vacaciones",
        "valor_booleano": True,
        "fecha_liberacion": fecha.isoformat(),
    }).execute()

    await _send(chat_id, f"🏖️ Modo vacaciones activado hasta el {fecha_str}. Las alertas laborales están silenciadas.")
    return {"ok": True, "detail": "vacaciones activated"}


async def handle_finde(chat_id: int) -> dict:
    from dateutil import tz

    db = get_db()
    tz_result = db.table("configuracion_sistema").select("valor_texto").eq("clave", "zona_horaria_default").limit(1).execute()
    tz_name = "America/Lima"
    if tz_result.data and tz_result.data[0].get("valor_texto"):
        tz_name = tz_result.data[0]["valor_texto"]

    zona = tz.gettz(tz_name)
    now = datetime.now(tz=zona)
    dias_hasta_lunes = (7 - now.weekday()) % 7
    if dias_hasta_lunes == 0 and now.hour >= 8:
        dias_hasta_lunes = 7
    lunes = now + timedelta(days=dias_hasta_lunes)
    liberacion = lunes.replace(hour=8, minute=30, second=0, microsecond=0)

    db.table("configuracion_sistema").upsert({
        "clave": "modo_finde",
        "valor_booleano": True,
        "fecha_liberacion": liberacion.isoformat(),
    }).execute()

    await _send(
        chat_id,
        "🗓️ Modo fin de semana activado. Las alertas laborales se reanudarán "
        f"el lunes a las 08:30 ({tz_name})."
    )
    return {"ok": True, "detail": "finde activated"}


async def handle_tareas(chat_id: int) -> dict:
    from dateutil.parser import parse as parse_date

    db = get_db()
    result = (
        db.table("tareas")
        .select("id, titulo, fecha_vence, ambito, prioridad")
        .eq("estado", "pendiente")
        .order("fecha_vence", nulls_last=True)
        .execute()
    )
    rows = result.data if result.data else []

    if not rows:
        await _send(chat_id, "No tienes tareas pendientes. 🎉")
        return {"ok": True, "detail": "no tasks"}

    today = date.today()
    grupos: dict[str, list[str]] = {"vencidas": [], "hoy": [], "proximas": [], "inbox": []}

    for r in rows:
        fv_raw = r.get("fecha_vence")
        titulo = r["titulo"]
        ambito = r.get("ambito", "laboral")
        prio = r.get("prioridad", "media")
        linea = f"{'🔵' if ambito == 'personal' else '🟢'} {titulo} ({prio})"
        if r["id"].startswith("rec"):
            linea += " 🔄"

        if fv_raw is None:
            grupos["inbox"].append(linea)
        else:
            try:
                if isinstance(fv_raw, str):
                    fv = parse_date(fv_raw).date()
                else:
                    fv = fv_raw if hasattr(fv_raw, 'isoformat') else parse_date(str(fv_raw)).date()
            except Exception:
                grupos["inbox"].append(linea)
                continue

            if fv < today:
                grupos["vencidas"].append(linea)
            elif fv == today:
                grupos["hoy"].append(linea)
            else:
                grupos["proximas"].append(f"{linea} ({fv.isoformat()})")

    lines = []
    if grupos["vencidas"]:
        lines.append("🔴 Vencidas:")
        lines.extend(f"  {l}" for l in grupos["vencidas"])
    if grupos["hoy"]:
        lines.append("⚠️ Hoy:")
        lines.extend(f"  {l}" for l in grupos["hoy"])
    if grupos["proximas"]:
        lines.append("📅 Próximas:")
        lines.extend(f"  {l}" for l in grupos["proximas"])
    if grupos["inbox"]:
        lines.append("📥 Inbox:")
        lines.extend(f"  {l}" for l in grupos["inbox"])

    await _send(chat_id, "\n".join(lines))
    return {"ok": True, "detail": "tasks listed"}


def _get_date_in_tz() -> date:
    from dateutil import tz
    db = get_db()
    tz_res = db.table("configuracion_sistema").select("valor_texto").eq("clave", "zona_horaria_default").limit(1).execute()
    tz_name = "America/Lima"
    if tz_res.data and tz_res.data[0].get("valor_texto"):
        tz_name = tz_res.data[0]["valor_texto"]
    zona = tz.gettz(tz_name)
    return datetime.now(tz=zona).date()


def _build_emoji_for_tarea(tarea: dict) -> str:
    ambito = tarea.get("ambito", "laboral")
    emoji = "🔵" if ambito == "laboral" else "🟠"
    if tarea.get("id", "").startswith("rec"):
        emoji = "🟡"
    return emoji


async def handle_hoy(chat_id: int) -> dict:
    today = _get_date_in_tz()
    db = get_db()
    result = (
        db.table("tareas")
        .select("id, titulo, fecha_vence, ambito, prioridad")
        .eq("estado", "pendiente")
        .eq("fecha_vence", today.isoformat())
        .order("prioridad")
        .execute()
    )
    rows = result.data if result.data else []
    if not rows:
        await _send(chat_id, "🎉 No tienes tareas para hoy.")
        return {"ok": True, "detail": "no tasks today"}

    lines = [f"📅 *Hoy — {today.day}/{today.month}*"]
    for r in rows:
        prio = r.get("prioridad", "media")
        emoji = _build_emoji_for_tarea(r)
        rec_mark = " 🔄" if r["id"].startswith("rec") else ""
        lines.append(f"  {emoji} {r['titulo']} ({prio}){rec_mark}")

    await _send(chat_id, "\n".join(lines))
    return {"ok": True, "detail": "today listed"}


async def handle_semana(chat_id: int) -> dict:
    today = _get_date_in_tz()
    week_end = today + timedelta(days=7)
    db = get_db()
    result = (
        db.table("tareas")
        .select("id, titulo, fecha_vence, ambito, prioridad")
        .eq("estado", "pendiente")
        .not_.is_("fecha_vence", "null")
        .order("fecha_vence")
        .execute()
    )
    rows = result.data if result.data else []
    if not rows:
        await _send(chat_id, "🎉 No tienes tareas para esta semana.")
        return {"ok": True, "detail": "no tasks this week"}

    vencidas = [r for r in rows if r.get("fecha_vence") and r["fecha_vence"] < today.isoformat()]
    semana = [r for r in rows if r.get("fecha_vence") and today.isoformat() <= r["fecha_vence"] <= week_end.isoformat()]

    lines = []
    if vencidas:
        lines.append("🔴 Vencidas:")
        for r in vencidas:
            emoji = _build_emoji_for_tarea(r)
            fv = date.fromisoformat(r["fecha_vence"])
            dias_v = (today - fv).days
            lines.append(f"  {emoji} {r['titulo']} (-{dias_v}d)")

    dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    agrupadas: dict[str, list] = {}
    for r in semana:
        agrupadas.setdefault(r["fecha_vence"], []).append(r)

    for fv_str in sorted(agrupadas.keys()):
        fv = date.fromisoformat(fv_str)
        dia_idx = fv.weekday()
        encabezado = f"📅 {dias_semana[dia_idx]} {fv.day}"
        lines.append(encabezado)
        for r in agrupadas[fv_str]:
            emoji = _build_emoji_for_tarea(r)
            prio = r.get("prioridad", "media")
            lines.append(f"  {emoji} {r['titulo']} ({prio})")

    if not vencidas and not semana:
        await _send(chat_id, "🎉 No tienes tareas para esta semana.")
        return {"ok": True, "detail": "no tasks this week"}

    total = len(vencidas) + len(semana)
    lines.append(f"\n📊 {total} tareas esta semana")
    await _send(chat_id, "\n".join(lines))
    return {"ok": True, "detail": "week listed"}


def _format_dia_semana(dia_iso: int) -> str:
    return ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][dia_iso]


def _month_grid(year: int, month: int, tareas_por_dia: dict[str, list]) -> str:
    import calendar
    cal = calendar.monthcalendar(year, month)
    lines = [f"🗓️ {calendar.month_name[month].capitalize()} {year}"]
    header = "│" + "│".join(f" {_format_dia_semana(i)} " for i in range(7)) + "│"
    sep = "├" + "───┼" * 6 + "───┤" if len(lines) < 2 else "├" + "───┼" * 6 + "───┤"

    lines.append(sep if len(lines) == 1 else header)
    lines.append(header)
    lines.append(sep)

    for week in cal:
        cells = []
        emoji_cells = []
        for dia in week:
            if dia == 0:
                cells.append("   ")
                emoji_cells.append("   ")
            else:
                cells.append(f"{dia:2d} ")
                key = f"{year:04d}-{month:02d}-{dia:02d}"
                tasks = tareas_por_dia.get(key, [])
                emojis = set()
                for t in tasks:
                    emojis.add(_build_emoji_for_tarea(t))
                    if t.get("fecha_vence") and t["fecha_vence"] < date.today().isoformat():
                        emojis.add("⚡")
                mostrar = "".join(sorted(emojis))[:3] if emojis else "  "
                emoji_cells.append(f"{mostrar:3s}")

        lines.append("│" + "│".join(cells) + "│")
        lines.append("│" + "│".join(emoji_cells) + "│")

    lines.append("└" + "───┴" * 6 + "───┘")
    lines.append("🔵 laboral  🟠 personal  🟡 recurrencia  ⚡ vencida")
    return "\n".join(lines)


async def handle_mes(chat_id: int, mes_str: str | None = None) -> dict:
    today = _get_date_in_tz()
    year = today.year
    if mes_str:
        try:
            mes_num = int(mes_str)
            if mes_num < 1 or mes_num > 12:
                await _send(chat_id, "Mes inválido. Usa un número entre 1 y 12.")
                return {"ok": True, "detail": "invalid month"}
        except ValueError:
            await _send(chat_id, "Mes inválido. Usa un número entre 1 y 12.")
            return {"ok": True, "detail": "invalid month"}
    else:
        mes_num = today.month

    db = get_db()
    result = (
        db.table("tareas")
        .select("id, titulo, fecha_vence, ambito, prioridad")
        .eq("estado", "pendiente")
        .not_.is_("fecha_vence", "null")
        .execute()
    )
    rows = result.data if result.data else []

    tareas_por_dia: dict[str, list] = {}
    for r in rows:
        if r.get("fecha_vence"):
            try:
                fv = date.fromisoformat(r["fecha_vence"])
                if fv.year == year and fv.month == mes_num:
                    tareas_por_dia.setdefault(r["fecha_vence"], []).append(r)
            except (ValueError, TypeError):
                pass

    grid = _month_grid(year, mes_num, tareas_por_dia)
    await _send(chat_id, grid)
    return {"ok": True, "detail": "month listed"}
