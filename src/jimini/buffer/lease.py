from __future__ import annotations

from dataclasses import dataclass

from jimini.db import get_db


@dataclass
class BufferMessage:
    id: int
    chat_id: int
    telegram_message_id: int
    tipo_media: str
    tipo_mensaje: str = "tarea"
    mensaje_raw: str | None = None
    file_id: str | None = None
    storage_path: str | None = None
    signed_url: str | None = None
    transcripcion: str | None = None
    intentos_fallidos: int = 0
    estado_procesamiento: str = "pendiente"

    @classmethod
    def from_row(cls, row: dict) -> BufferMessage:
        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            telegram_message_id=row["telegram_message_id"],
            tipo_media=row["tipo_media"],
            tipo_mensaje=row.get("tipo_mensaje", "tarea"),
            mensaje_raw=row.get("mensaje_raw"),
            file_id=row.get("file_id"),
            storage_path=row.get("storage_path"),
            signed_url=row.get("signed_url"),
            transcripcion=row.get("transcripcion"),
            intentos_fallidos=row["intentos_fallidos"],
            estado_procesamiento=row["estado_procesamiento"],
        )


def claim_next_message() -> BufferMessage | None:
    db = get_db()
    result = db.rpc("claim_next_buffer_message").execute()
    rows = result.data if result.data else []
    if not rows:
        return None
    return BufferMessage.from_row(rows[0])


def mark_completed(message_id: int) -> None:
    db = get_db()
    db.rpc("mark_buffer_completed", {"p_id": message_id}).execute()


def mark_failed(message_id: int, current_intentos: int) -> str | None:
    db = get_db()
    result = db.rpc(
        "mark_buffer_failed",
        {"p_id": message_id, "p_current_intentos": current_intentos},
    ).execute()
    if result.data and len(result.data) > 0:
        return str(result.data[0])
    return None


def get_idioma_config() -> str | None:
    db = get_db()
    result = db.rpc("get_idioma_config").execute()
    if result.data and len(result.data) > 0:
        val = str(result.data[0])
        return val if val.strip() else None
    return None
