from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jimini.buffer.lease import BufferMessage
from jimini.buffer.worker import _get_text_for_ia


@pytest.fixture
def msg_texto():
    return BufferMessage(id=1, chat_id=123, telegram_message_id=1, tipo_media="texto",
                         tipo_mensaje="tarea", mensaje_raw="Hola mundo")


@pytest.fixture
def msg_voz_cache():
    return BufferMessage(id=2, chat_id=123, telegram_message_id=2, tipo_media="voz",
                         tipo_mensaje="tarea", signed_url="https://example.com/audio.ogg?expires=9999999999",
                         storage_path="audio/uuid.ogg", transcripcion="Texto transcrito",
                         file_id="f123")


@pytest.fixture
def msg_voz_sin_cache():
    return BufferMessage(id=3, chat_id=123, telegram_message_id=3, tipo_media="voz",
                         tipo_mensaje="tarea", signed_url="https://example.com/audio.ogg?expires=9999999999",
                         storage_path="audio/uuid.ogg", transcripcion=None,
                         file_id="f456")


@pytest.fixture
def msg_voz_url_expirada():
    return BufferMessage(id=4, chat_id=123, telegram_message_id=4, tipo_media="voz",
                         tipo_mensaje="tarea",
                         signed_url="https://example.com/audio.ogg?expires=1000000000",
                         storage_path="audio/uuid.ogg", transcripcion=None,
                         file_id="f789")


@pytest.mark.asyncio
async def test_texto_retorna_mensaje_raw(msg_texto):
    result = await _get_text_for_ia(msg_texto)
    assert result == "Hola mundo"


@pytest.mark.asyncio
async def test_voz_cache_retorna_transcripcion(msg_voz_cache):
    with patch("jimini.buffer.worker.get_idioma_config", return_value="es"):
        result = await _get_text_for_ia(msg_voz_cache)
    assert result == "Texto transcrito"


@patch("jimini.buffer.worker.get_provider")
@patch("jimini.buffer.worker.get_idioma_config")
@patch("jimini.buffer.worker.get_db")
async def test_voz_sin_cache_invoca_groq(mock_db, mock_idioma, mock_provider, msg_voz_sin_cache):
    mock_idioma.return_value = "es"
    mock_db_inst = MagicMock()
    mock_db.return_value = mock_db_inst

    mock_prov = AsyncMock()
    mock_prov.transcribe.return_value = "Transcripción de Groq"
    mock_provider.return_value = mock_prov

    result = await _get_text_for_ia(msg_voz_sin_cache)
    assert result == "Transcripción de Groq"
    mock_prov.transcribe.assert_called_once()
    mock_db_inst.table.return_value.update.assert_called()


@patch("jimini.buffer.worker.regenerate_signed_url")
@patch("jimini.buffer.worker.signed_url_is_expired")
@patch("jimini.buffer.worker.get_provider")
@patch("jimini.buffer.worker.get_idioma_config")
@patch("jimini.buffer.worker.get_db")
async def test_voz_url_expirada_regenera(mock_db, mock_idioma, mock_provider, mock_is_expired,
                                          mock_regenerate, msg_voz_url_expirada):
    mock_is_expired.return_value = True
    mock_regenerate.return_value = "https://new.url/audio.ogg?expires=9999999999"
    mock_idioma.return_value = "es"

    mock_db_inst = MagicMock()
    mock_db.return_value = mock_db_inst

    mock_prov = AsyncMock()
    mock_prov.transcribe.return_value = "Nueva transcripción"
    mock_provider.return_value = mock_prov

    result = await _get_text_for_ia(msg_voz_url_expirada)
    assert result == "Nueva transcripción"
    assert msg_voz_url_expirada.signed_url == "https://new.url/audio.ogg?expires=9999999999"
