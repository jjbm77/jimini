from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jimini.notifications.dlq import (
    _describe_dia,
    _describe_tipo,
    handle_recurrencia_deshacer_callback,
    send_recurrencia_confirmation,
)


class TestSendConfirmation:
    @patch("jimini.notifications.dlq.httpx.AsyncClient")
    async def test_send_confirmation_with_deshacer_button(self, mock_httpx):
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client

        plantilla = {
            "id": 42,
            "titulo": "Pagar luz",
            "ambito": "personal",
            "prioridad": "media",
            "dias_para_vencer": 0,
            "tipo_recurrencia": "mensual",
            "intervalo": 1,
            "dia_del_mes": 5,
        }

        await send_recurrencia_confirmation(12345, plantilla)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["chat_id"] == 12345
        assert "Pagar luz" in payload["text"]
        assert "reply_markup" in payload
        keyboard = payload["reply_markup"]["inline_keyboard"]
        assert keyboard[0][0]["callback_data"] == "recurrencia_deshacer:42"


class TestDeshacerCallback:
    @patch("jimini.notifications.dlq.get_db")
    @patch("jimini.notifications.dlq._answer_callback", new_callable=AsyncMock)
    @patch("jimini.notifications.dlq.httpx.AsyncClient")
    async def test_deshacer_deletes_plantilla(self, mock_httpx, mock_answer, mock_db):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_table = MagicMock()
        mock_db_inst.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[{"id": 42}])
        mock_table.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client

        callback_query = {
            "id": "cb123",
            "message": {"chat": {"id": 12345}, "message_id": 500},
            "data": "recurrencia_deshacer:42",
        }

        await handle_recurrencia_deshacer_callback(callback_query)

        mock_table.delete.assert_called_once()
        mock_answer.assert_called_once_with("cb123", "✅ Recurrencia eliminada")

    @patch("jimini.notifications.dlq.get_db")
    @patch("jimini.notifications.dlq._answer_callback", new_callable=AsyncMock)
    async def test_deshacer_plantilla_inexistente(self, mock_answer, mock_db):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_table = MagicMock()
        mock_db_inst.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])

        callback_query = {
            "id": "cb456",
            "message": {"chat": {"id": 12345}, "message_id": 500},
            "data": "recurrencia_deshacer:999",
        }

        await handle_recurrencia_deshacer_callback(callback_query)

        mock_table.delete.assert_not_called()
        mock_answer.assert_called_once_with("cb456", "Esta recurrencia ya no existe.")


class TestDescribeHelpers:
    def test_describe_tipo_mensual(self):
        assert _describe_tipo("mensual", 1) == "Mensual"

    def test_describe_tipo_trimestral(self):
        assert _describe_tipo("mensual", 3) == "Trimestral"

    def test_describe_tipo_semanal(self):
        assert _describe_tipo("semanal", 1) == "Semanal"

    def test_describe_tipo_quincenal(self):
        assert _describe_tipo("semanal", 2) == "Quincenal"

    def test_describe_dia_fin_de_mes(self):
        plantilla = {"tipo_recurrencia": "mensual", "dia_del_mes": 0}
        assert _describe_dia(plantilla) == "último día del mes"

    def test_describe_dia_specific(self):
        plantilla = {"tipo_recurrencia": "mensual", "dia_del_mes": 15}
        assert _describe_dia(plantilla) == "día 15"

    def test_describe_dia_semanal(self):
        plantilla = {"tipo_recurrencia": "semanal", "dia_de_semana": 1}
        assert _describe_dia(plantilla) == "cada lunes"

    def test_describe_dia_anual(self):
        plantilla = {"tipo_recurrencia": "anual", "dia_del_mes": 15, "mes_del_anio": 3}
        assert _describe_dia(plantilla) == "15/3"
