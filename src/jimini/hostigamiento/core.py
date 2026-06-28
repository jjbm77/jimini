from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from jimini.db import get_db


def calcular_nivel(fecha_vence: str | None, now: datetime | None = None) -> int:
    if not fecha_vence:
        return -1
    now = now or datetime.now(timezone.utc)
    db = get_db()
    result = db.rpc(
        "calcular_nivel_hostigamiento",
        {"p_fecha_vence": fecha_vence, "p_now": now.isoformat()},
    ).execute()
    if result.data and len(result.data) > 0:
        return int(result.data[0])
    return -1


def frecuencia_nivel(nivel: int) -> timedelta | None:
    mapping = {0: None, 1: timedelta(hours=4), 2: timedelta(hours=3),
               3: timedelta(hours=4), 4: timedelta(days=1)}
    return mapping.get(nivel)


def get_modo(clave: str) -> dict[str, Any] | None:
    db = get_db()
    result = (
        db.table("configuracion_sistema")
        .select("*")
        .eq("clave", clave)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    activo = row.get("valor_booleano", False)
    fecha_lib = row.get("fecha_liberacion")
    if not activo:
        return None
    return {"activo": True, "fecha_liberacion": fecha_lib}


def auto_limpiar_modos() -> None:
    now = datetime.now(timezone.utc)
    db = get_db()
    for clave in ("modo_vacaciones", "modo_finde"):
        modo = get_modo(clave)
        if modo and modo.get("fecha_liberacion"):
            import dateutil.parser as dp
            try:
                lib = dp.parse(modo["fecha_liberacion"])
                if lib.tzinfo is None:
                    lib = lib.replace(tzinfo=timezone.utc)
                if now >= lib:
                    db.table("configuracion_sistema").update(
                        {"valor_booleano": False, "fecha_liberacion": None}
                    ).eq("clave", clave).execute()
            except Exception:
                pass


def debe_alertar(
    ambito: str, nivel: int, modo_vacaciones: dict | None, modo_finde: dict | None
) -> bool:
    modo_activo = modo_vacaciones is not None or modo_finde is not None
    if not modo_activo:
        return True
    if ambito == "laboral":
        return False
    if ambito == "personal":
        return nivel >= 2
    return True


def dentro_horario_activo(tz_name: str = "America/Lima") -> bool:
    from datetime import timezone
    from dateutil import tz
    try:
        zona = tz.gettz(tz_name)
        now = datetime.now(tz=zona)
        return 9 <= now.hour < 21
    except Exception:
        return True
