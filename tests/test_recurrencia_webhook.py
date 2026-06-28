from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jimini.webhook.handler import handle_webhook


class TestWebhookCommands:
    @patch("jimini.webhook.handler.get_db")
    @patch("jimini.webhook.handler._send_telegram_message", new_callable=AsyncMock)
    async def test_recurrencia_with_text_inserts_to_buffer(self, mock_send, mock_db):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_table = MagicMock()
        mock_db_inst.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = MagicMock()

        update = {
            "message": {
                "chat": {"id": 12345},
                "message_id": 100,
                "text": "/recurrencia Pagar luz día 5 cada mes",
            }
        }
        result = await handle_webhook(update)

        assert result["ok"] is True
        mock_table.insert.assert_called_once()
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["tipo_mensaje"] == "recurrencia"
        assert insert_data["mensaje_raw"] == "Pagar luz día 5 cada mes"
        mock_send.assert_not_called()

    @patch("jimini.webhook.handler.get_db")
    @patch("jimini.webhook.handler._send_telegram_message", new_callable=AsyncMock)
    async def test_recurrencias_list_does_not_insert_to_buffer(self, mock_send, mock_db):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_table = MagicMock()
        mock_db_inst.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])

        update = {
            "message": {
                "chat": {"id": 12345},
                "message_id": 101,
                "text": "/recurrencias",
            }
        }
        result = await handle_webhook(update)

        assert result["ok"] is True
        mock_table.insert.assert_not_called()
        mock_send.assert_called_once()

    @patch("jimini.webhook.handler._send_telegram_message", new_callable=AsyncMock)
    async def test_recurrencia_without_arg_shows_usage(self, mock_send):
        update = {
            "message": {
                "chat": {"id": 12345},
                "message_id": 102,
                "text": "/recurrencia",
            }
        }
        result = await handle_webhook(update)

        assert result["ok"] is True
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        assert "/recurrencia" in sent_text

    @patch("jimini.webhook.handler.get_db")
    @patch("jimini.webhook.handler._send_telegram_message", new_callable=AsyncMock)
    async def test_normal_text_inserts_as_tarea(self, mock_send, mock_db):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_table = MagicMock()
        mock_db_inst.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = MagicMock()

        update = {
            "message": {
                "chat": {"id": 12345},
                "message_id": 103,
                "text": "Reunión con Juan mañana",
            }
        }
        result = await handle_webhook(update)

        assert result["ok"] is True
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["tipo_mensaje"] == "tarea"
