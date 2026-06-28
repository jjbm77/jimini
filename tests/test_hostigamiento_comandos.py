from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from jimini.hostigamiento.callbacks import handle_hostigamiento_callback
from jimini.hostigamiento.comandos import handle_finde, handle_tareas, handle_vacaciones


class TestComandoVacaciones:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_vacaciones_activa(self, mock_db, mock_send):
        result = await handle_vacaciones(12345, "/vacaciones 15/08/2026")
        assert result["ok"] is True
        assert mock_db.return_value.table.return_value.upsert.called

    @patch("jimini.hostigamiento.core.get_modo")
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    async def test_vacaciones_sin_fecha(self, mock_send, mock_get_modo):
        mock_get_modo.return_value = None
        result = await handle_vacaciones(12345, "/vacaciones")
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "No estás" in mock_send.call_args[0][1]

    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    async def test_vacaciones_fecha_invalida(self, mock_send):
        result = await handle_vacaciones(12345, "/vacaciones 99/99/9999")
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "inválido" in mock_send.call_args[0][1]


class TestComandoFinde:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_finde_activa(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        tz_res = MagicMock()
        tz_res.data = []
        mock_db_inst.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = tz_res

        result = await handle_finde(12345)
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "fin de semana" in mock_send.call_args[0][1]


class TestComandoTareas:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_tareas_sin_tareas(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

        result = await handle_tareas(12345)
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "No tienes" in mock_send.call_args[0][1]


class TestCallbacks:
    @patch("jimini.hostigamiento.callbacks._answer", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.callbacks.get_db")
    async def test_snooze_2h(self, mock_db, mock_answer):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "t1"}]

        cb = {"id": "cb1", "data": "snooze_2h:t1", "message": {"chat": {"id": 12345}, "message_id": 100}}
        result = await handle_hostigamiento_callback(cb)
        assert result is True
        mock_answer.assert_called_once_with("cb1", "⏳ Pospuesto 2 horas")

    @patch("jimini.hostigamiento.callbacks._answer", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.callbacks._edit_message", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.callbacks.get_db")
    async def test_completar(self, mock_db, mock_edit, mock_answer):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "t1"}]

        cb = {"id": "cb2", "data": "completar:t1", "message": {"chat": {"id": 12345}, "message_id": 100}}
        result = await handle_hostigamiento_callback(cb)
        assert result is True
        mock_answer.assert_called_once_with("cb2", "✅ Completada")

    @patch("jimini.hostigamiento.callbacks._answer", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.callbacks.get_db")
    async def test_callback_tarea_inexistente(self, mock_db, mock_answer):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []

        cb = {"id": "cb3", "data": "completar:tarea_inexistente", "message": {"chat": {"id": 12345}, "message_id": 100}}
        result = await handle_hostigamiento_callback(cb)
        assert result is True
        mock_answer.assert_called_once_with("cb3", "Esta tarea ya no existe.")
