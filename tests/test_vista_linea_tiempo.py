from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jimini.hostigamiento.comandos import (
    _build_emoji_for_tarea,
    handle_hoy,
    handle_mes,
    handle_semana,
)


class TestEmojiBuilder:
    def test_laboral(self):
        assert _build_emoji_for_tarea({"ambito": "laboral", "id": "t1"}) == "🔵"

    def test_personal(self):
        assert _build_emoji_for_tarea({"ambito": "personal", "id": "t2"}) == "🟠"

    def test_recurrencia(self):
        assert _build_emoji_for_tarea({"ambito": "laboral", "id": "rec-42-2026-07-05"}) == "🟡"


class TestHandleHoy:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_hoy_con_tareas(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {"id": "t1", "titulo": "Pagar luz", "fecha_vence": "2026-07-05", "ambito": "personal", "prioridad": "alta"},
        ]

        result = await handle_hoy(12345)
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "HOY" in mock_send.call_args[0][1] or "Hoy" in mock_send.call_args[0][1]
        assert "Pagar luz" in mock_send.call_args[0][1]

    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_hoy_sin_tareas(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = []

        result = await handle_hoy(12345)
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "No tienes" in mock_send.call_args[0][1]


class TestHandleSemana:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_semana_con_vencidas(self, mock_db, mock_send):
        today = "2026-07-05"
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.order.return_value.execute.return_value.data = [
            {"id": "t1", "titulo": "Vencida", "fecha_vence": "2026-07-03", "ambito": "laboral", "prioridad": "alta"},
        ]

        with patch("jimini.hostigamiento.comandos._get_date_in_tz", return_value=date(2026, 7, 5)):
            from datetime import date
            result = await handle_semana(12345)

        assert result["ok"] is True
        mock_send.assert_called_once()
        sent = mock_send.call_args[0][1]
        assert "Vencidas" in sent or "vencida" in sent


class TestHandleMes:
    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_mes_actual(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value.data = []

        with patch("jimini.hostigamiento.comandos._get_date_in_tz", return_value=date(2026, 7, 5)):
            result = await handle_mes(12345, None)

        assert result["ok"] is True
        mock_send.assert_called_once()
        sent = mock_send.call_args[0][1]
        assert "Julio" in sent or "julio" in sent

    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    async def test_mes_invalido(self, mock_send):
        result = await handle_mes(12345, "13")
        assert result["ok"] is True
        mock_send.assert_called_once()
        assert "inválido" in mock_send.call_args[0][1]

    @patch("jimini.hostigamiento.comandos._send", new_callable=AsyncMock)
    @patch("jimini.hostigamiento.comandos.get_db")
    async def test_mes_agosto(self, mock_db, mock_send):
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value.data = []

        with patch("jimini.hostigamiento.comandos._get_date_in_tz", return_value=date(2026, 7, 5)):
            result = await handle_mes(12345, "8")

        assert result["ok"] is True
        mock_send.assert_called_once()
        sent = mock_send.call_args[0][1]
        assert "Agosto" in sent or "agosto" in sent
