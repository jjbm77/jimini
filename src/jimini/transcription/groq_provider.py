from __future__ import annotations

import httpx

from jimini.config import settings
from jimini.transcription.provider import (
    RateLimitError,
    TranscriptionError,
    TranscriptionProvider,
)


class GroqTranscriptionProvider(TranscriptionProvider):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            timeout=120.0,
        )

    async def transcribe(self, audio_url: str, language: str | None) -> str:
        payload: dict = {
            "model": settings.groq_model,
            "url": audio_url,
            "response_format": "json",
        }
        if language:
            payload["language"] = language

        response = await self._client.post("/audio/transcriptions", json=payload)

        if response.status_code == 429:
            raise RateLimitError("Groq rate limit hit")
        if response.status_code >= 500:
            raise TranscriptionError(f"Groq server error: {response.status_code}")
        if response.status_code != 200:
            raise TranscriptionError(
                f"Groq error {response.status_code}: {response.text}"
            )

        data = response.json()
        return data["text"]
