from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jimini.buffer.lease import BufferMessage, claim_next_message, mark_completed, mark_failed


class TestLeaseProtocol:
    @patch("jimini.buffer.lease.get_db")
    def test_claim_no_messages(self, mock_get_db):
        mock_db = AsyncMock()
        mock_db.rpc.return_value.execute.return_value.data = []
        mock_get_db.return_value = mock_db

        result = claim_next_message()
        assert result is None

    @patch("jimini.buffer.lease.get_db")
    def test_claim_with_message(self, mock_get_db):
        mock_db = AsyncMock()
        mock_db.rpc.return_value.execute.return_value.data = [
            {
                "id": 1,
                "chat_id": 12345,
                "telegram_message_id": 100,
                "tipo_media": "texto",
                "mensaje_raw": "test message",
                "file_id": None,
                "storage_path": None,
                "signed_url": None,
                "transcripcion": None,
                "intentos_fallidos": 0,
                "estado_procesamiento": "pendiente",
            }
        ]
        mock_get_db.return_value = mock_db

        msg = claim_next_message()
        assert msg is not None
        assert msg.id == 1
        assert msg.tipo_media == "texto"
        assert msg.mensaje_raw == "test message"

    @patch("jimini.buffer.lease.get_db")
    def test_mark_completed(self, mock_get_db):
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mark_completed(1)
        mock_db.rpc.assert_called_with("mark_buffer_completed", {"p_id": 1})

    @patch("jimini.buffer.lease.get_db")
    def test_mark_failed_below_threshold(self, mock_get_db):
        mock_db = AsyncMock()
        mock_db.rpc.return_value.execute.return_value.data = ["pendiente"]
        mock_get_db.return_value = mock_db

        result = mark_failed(1, 0)
        assert result == "pendiente"

    @patch("jimini.buffer.lease.get_db")
    def test_mark_failed_reaches_dlq(self, mock_get_db):
        mock_db = AsyncMock()
        mock_db.rpc.return_value.execute.return_value.data = ["error_permanente"]
        mock_get_db.return_value = mock_db

        result = mark_failed(1, 2)
        assert result == "error_permanente"
