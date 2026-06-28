from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jimini.hostigamiento.worker import worker_loop_hostigamiento


# Stops the while True loop after one iteration
class _BreakLoop(Exception):
    pass


@patch("asyncio.sleep", side_effect=_BreakLoop)
@patch("jimini.hostigamiento.worker.auto_limpiar_modos")
@patch("jimini.hostigamiento.worker.get_modo")
@patch("jimini.hostigamiento.worker._query_tareas_pendientes")
@patch("jimini.hostigamiento.worker.enviar_alerta_telegram", new_callable=AsyncMock)
@patch("jimini.hostigamiento.worker.calcular_nivel")
@patch("jimini.hostigamiento.worker.debe_alertar")
@patch("jimini.hostigamiento.worker.dentro_horario_activo")
@patch("jimini.hostigamiento.worker.get_db")
async def test_subida_de_nivel(
    mock_db, mock_horario, mock_alertar, mock_nivel,
    mock_enviar, mock_query, mock_modo, mock_limpiar, mock_sleep
):
    mock_horario.return_value = True
    mock_alertar.return_value = True
    mock_nivel.return_value = 2
    mock_modo.side_effect = lambda k: None
    mock_query.return_value = [
        {"id": "t1", "chat_id": 12345, "titulo": "Test", "fecha_vence": "2026-07-05",
         "ambito": "laboral", "prioridad": "alta", "nivel_hostigamiento": 1,
         "proxima_alerta_bloqueada_hasta": None}
    ]
    mock_db_inst = MagicMock()
    mock_db.return_value = mock_db_inst

    with pytest.raises(_BreakLoop):
        await worker_loop_hostigamiento()

    mock_enviar.assert_called_once()
    assert mock_enviar.call_args[0][0] == 12345
    mock_db_inst.table.return_value.update.assert_called()
    update_data = mock_db_inst.table.return_value.update.call_args[0][0]
    assert update_data["nivel_hostigamiento"] == 2


@patch("asyncio.sleep", side_effect=_BreakLoop)
@patch("jimini.hostigamiento.worker.auto_limpiar_modos")
@patch("jimini.hostigamiento.worker.get_modo")
@patch("jimini.hostigamiento.worker._query_tareas_pendientes")
@patch("jimini.hostigamiento.worker.enviar_alerta_telegram", new_callable=AsyncMock)
@patch("jimini.hostigamiento.worker.calcular_nivel")
@patch("jimini.hostigamiento.worker.debe_alertar")
@patch("jimini.hostigamiento.worker.dentro_horario_activo")
@patch("jimini.hostigamiento.worker.get_db")
async def test_skip_por_vacaciones(
    mock_db, mock_horario, mock_alertar, mock_nivel,
    mock_enviar, mock_query, mock_modo, mock_limpiar, mock_sleep
):
    mock_horario.return_value = True
    mock_alertar.return_value = False
    mock_nivel.return_value = 2
    mock_modo.side_effect = lambda k: {"activo": True, "fecha_liberacion": "2026-08-01"} if k == "modo_vacaciones" else None
    mock_query.return_value = [
        {"id": "t1", "chat_id": 12345, "titulo": "Test", "fecha_vence": "2026-07-05",
         "ambito": "laboral", "prioridad": "alta", "nivel_hostigamiento": 1,
         "proxima_alerta_bloqueada_hasta": None}
    ]

    with pytest.raises(_BreakLoop):
        await worker_loop_hostigamiento()

    mock_enviar.assert_not_called()


@patch("asyncio.sleep", side_effect=_BreakLoop)
@patch("jimini.hostigamiento.worker.auto_limpiar_modos")
@patch("jimini.hostigamiento.worker.get_modo")
@patch("jimini.hostigamiento.worker._query_tareas_pendientes")
@patch("jimini.hostigamiento.worker.enviar_alerta_telegram", new_callable=AsyncMock)
@patch("jimini.hostigamiento.worker.calcular_nivel")
@patch("jimini.hostigamiento.worker.debe_alertar")
@patch("jimini.hostigamiento.worker.dentro_horario_activo")
@patch("jimini.hostigamiento.worker.get_db")
async def test_skip_sin_chat_id(
    mock_db, mock_horario, mock_alertar, mock_nivel,
    mock_enviar, mock_query, mock_modo, mock_limpiar, mock_sleep
):
    mock_horario.return_value = True
    mock_alertar.return_value = True
    mock_nivel.return_value = 2
    mock_modo.side_effect = lambda k: None
    mock_query.return_value = [
        {"id": "t1", "chat_id": None, "titulo": "Test", "fecha_vence": "2026-07-05",
         "ambito": "laboral", "prioridad": "alta", "nivel_hostigamiento": 1,
         "proxima_alerta_bloqueada_hasta": None}
    ]

    with pytest.raises(_BreakLoop):
        await worker_loop_hostigamiento()

    mock_enviar.assert_not_called()
