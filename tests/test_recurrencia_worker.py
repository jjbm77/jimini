from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jimini.buffer.lease import BufferMessage
from jimini.buffer.worker import _structure_plantilla, process_message


@pytest.fixture
def recurrencia_msg():
    return BufferMessage(
        id=10,
        chat_id=12345,
        telegram_message_id=200,
        tipo_media="texto",
        tipo_mensaje="recurrencia",
        mensaje_raw="Pagar luz el día 5 de cada mes, personal",
        file_id=None,
        storage_path=None,
        signed_url=None,
        transcripcion=None,
        intentos_fallidos=0,
        estado_procesamiento="procesando",
    )


@pytest.fixture
def tarea_msg():
    return BufferMessage(
        id=11,
        chat_id=12345,
        telegram_message_id=201,
        tipo_media="texto",
        tipo_mensaje="tarea",
        mensaje_raw="Reunión con Juan mañana",
        file_id=None,
        storage_path=None,
        signed_url=None,
        transcripcion=None,
        intentos_fallidos=0,
        estado_procesamiento="procesando",
    )


class TestWorkerBifurcation:
    @patch("jimini.buffer.worker._process_recurrencia", new_callable=AsyncMock)
    @patch("jimini.buffer.worker._process_tarea", new_callable=AsyncMock)
    @patch("jimini.buffer.worker.mark_completed")
    @patch("jimini.buffer.worker._get_text_for_ia", new_callable=AsyncMock)
    async def test_recurrencia_goes_to_recurrencia_branch(
        self, mock_get_text, mock_completed, mock_tarea, mock_rec, recurrencia_msg
    ):
        mock_get_text.return_value = "Pagar luz día 5"
        await process_message(recurrencia_msg)
        mock_rec.assert_called_once()
        mock_tarea.assert_not_called()

    @patch("jimini.buffer.worker._process_recurrencia", new_callable=AsyncMock)
    @patch("jimini.buffer.worker._process_tarea", new_callable=AsyncMock)
    @patch("jimini.buffer.worker.mark_completed")
    @patch("jimini.buffer.worker._get_text_for_ia", new_callable=AsyncMock)
    async def test_tarea_goes_to_tarea_branch(
        self, mock_get_text, mock_completed, mock_tarea, mock_rec, tarea_msg
    ):
        mock_get_text.return_value = "Reunión Juan"
        await process_message(tarea_msg)
        mock_tarea.assert_called_once()
        mock_rec.assert_not_called()


class TestStructurePlantilla:
    @patch("jimini.buffer.worker._call_openrouter", new_callable=AsyncMock)
    async def test_structure_plantilla_returns_fields(self, mock_call):
        mock_call.return_value = {
            "titulo": "Pagar luz",
            "ambito": "personal",
            "tipo_recurrencia": "mensual",
            "intervalo": 1,
            "dia_del_mes": 5,
            "dias_para_vencer": 0,
            "prioridad": "media",
        }
        result = await _structure_plantilla("Pagar luz día 5 cada mes")
        assert result["titulo"] == "Pagar luz"
        assert result["tipo_recurrencia"] == "mensual"
        assert result["dia_del_mes"] == 5

    @patch("jimini.buffer.worker._call_openrouter", new_callable=AsyncMock)
    async def test_structure_plantilla_fin_de_mes(self, mock_call):
        mock_call.return_value = {
            "titulo": "Pagar alquiler",
            "tipo_recurrencia": "mensual",
            "dia_del_mes": 0,
            "dias_para_vencer": 0,
        }
        result = await _structure_plantilla("Pagar alquiler a fin de mes")
        assert result["dia_del_mes"] == 0

    @patch("jimini.buffer.worker._call_openrouter", new_callable=AsyncMock)
    async def test_structure_plantilla_trimestral(self, mock_call):
        mock_call.return_value = {
            "titulo": "Reporte trimestral",
            "tipo_recurrencia": "mensual",
            "intervalo": 3,
            "dia_del_mes": 15,
        }
        result = await _structure_plantilla("Reporte trimestral día 15")
        assert result["intervalo"] == 3
        assert result["tipo_recurrencia"] == "mensual"

    @patch("jimini.buffer.worker._call_openrouter", new_callable=AsyncMock)
    async def test_structure_plantilla_semanal(self, mock_call):
        mock_call.return_value = {
            "titulo": "Revisión proyecto",
            "tipo_recurrencia": "semanal",
            "dia_de_semana": 1,
            "dias_para_vencer": 0,
        }
        result = await _structure_plantilla("Revisión cada lunes")
        assert result["tipo_recurrencia"] == "semanal"
        assert result["dia_de_semana"] == 1
