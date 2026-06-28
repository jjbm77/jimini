from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jimini.transcription.groq_provider import (
    GroqTranscriptionProvider,
    RateLimitError,
    TranscriptionError,
)


@pytest.fixture
def provider():
    return GroqTranscriptionProvider()


@patch("jimini.transcription.groq_provider.settings")
@patch("jimini.transcription.groq_provider.httpx.AsyncClient")
async def test_transcribe_success(mock_httpx, mock_settings, provider):
    mock_settings.groq_model = "whisper-large-v3-turbo"
    mock_settings.groq_api_key = "test-key"

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Hola, esto es una prueba"}
    mock_client.post = AsyncMock(return_value=mock_response)

    provider._client = mock_client

    result = await provider.transcribe("https://example.com/audio.ogg", "es")
    assert result == "Hola, esto es una prueba"


@patch("jimini.transcription.groq_provider.settings")
@patch("jimini.transcription.groq_provider.httpx.AsyncClient")
async def test_transcribe_rate_limit(mock_httpx, mock_settings, provider):
    mock_settings.groq_model = "whisper-large-v3-turbo"
    mock_settings.groq_api_key = "test-key"

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_client.post = AsyncMock(return_value=mock_response)

    provider._client = mock_client

    with pytest.raises(RateLimitError):
        await provider.transcribe("https://example.com/audio.ogg", "es")


@patch("jimini.transcription.groq_provider.settings")
@patch("jimini.transcription.groq_provider.httpx.AsyncClient")
async def test_transcribe_server_error(mock_httpx, mock_settings, provider):
    mock_settings.groq_model = "whisper-large-v3-turbo"
    mock_settings.groq_api_key = "test-key"

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_client.post = AsyncMock(return_value=mock_response)

    provider._client = mock_client

    with pytest.raises(TranscriptionError):
        await provider.transcribe("https://example.com/audio.ogg", "es")
