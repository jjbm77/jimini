from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from jimini.notifications.dlq import notify_dlq_telegram
from jimini.buffer.lease import BufferMessage


@pytest.fixture
def text_message():
    return BufferMessage(
        id=1,
        chat_id=12345,
        telegram_message_id=100,
        tipo_media="texto",
        mensaje_raw="test text",
        file_id=None,
        storage_path=None,
        signed_url=None,
        transcripcion=None,
        intentos_fallidos=3,
        estado_procesamiento="error_permanente",
    )


@pytest.fixture
def voice_message_with_transcription():
    return BufferMessage(
        id=2,
        chat_id=12345,
        telegram_message_id=101,
        tipo_media="voz",
        mensaje_raw=None,
        file_id="file_abc",
        storage_path="audio/uuid.ogg",
        signed_url="https://example.com/signed?expires=9999999999",
        transcripcion="Hola esto es una prueba",
        intentos_fallidos=3,
        estado_procesamiento="error_permanente",
    )


@pytest.fixture
def voice_message_no_transcription():
    return BufferMessage(
        id=3,
        chat_id=12345,
        telegram_message_id=102,
        tipo_media="voz",
        mensaje_raw=None,
        file_id="file_def",
        storage_path="audio/uuid2.ogg",
        signed_url="https://example.com/signed2?expires=9999999999",
        transcripcion=None,
        intentos_fallidos=3,
        estado_procesamiento="error_permanente",
    )


@patch("jimini.notifications.dlq.settings")
@patch("jimini.notifications.dlq.httpx.AsyncClient")
def test_notify_text(mock_httpx, mock_settings, text_message):
    notify_dlq_telegram(text_message)
    # Should call sendMessage for text
    mock_client = mock_httpx.return_value.__aenter__.return_value
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "sendMessage" in args[0]
    assert "test text" in kwargs["json"]["text"]


@patch("jimini.notifications.dlq.settings")
@patch("jimini.notifications.dlq.httpx.AsyncClient")
def test_notify_voice_with_transcription(mock_httpx, mock_settings, voice_message_with_transcription):
    mock_client = mock_httpx.return_value.__aenter__.return_value
    notify_dlq_telegram(voice_message_with_transcription)
    # With transcription, should just send text including transcription
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "sendMessage" in args[0]
    assert "Hola esto es una prueba" in kwargs["json"]["text"]


@patch("jimini.notifications.dlq.settings")
@patch("jimini.notifications.dlq.httpx.AsyncClient")
def test_notify_voice_without_transcription_forward_success(mock_httpx, mock_settings, voice_message_no_transcription):
    mock_client = mock_httpx.return_value.__aenter__.return_value
    # forwardMessage succeeds
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    notify_dlq_telegram(voice_message_no_transcription)

    calls = mock_client.post.call_args_list
    # First call should be forwardMessage
    assert "forwardMessage" in calls[0][0]


@patch("jimini.notifications.dlq.settings")
@patch("jimini.notifications.dlq.httpx.AsyncClient")
def test_notify_voice_without_transcription_forward_fails_send_voice_succeeds(mock_httpx, mock_settings, voice_message_no_transcription):
    mock_client = mock_httpx.return_value.__aenter__.return_value

    def post_side_effect(url, **kwargs):
        mock_resp = AsyncMock()
        if "forwardMessage" in url:
            mock_resp.status_code = 403
        elif "sendVoice" in url:
            mock_resp.status_code = 200
        else:
            mock_resp.status_code = 200
        return mock_resp

    mock_client.post.side_effect = post_side_effect

    notify_dlq_telegram(voice_message_no_transcription)

    calls = mock_client.post.call_args_list
    assert any("forwardMessage" in c[0] for c in calls)
    assert any("sendVoice" in c[0] for c in calls)
