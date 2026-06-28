from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jimini.config import settings


class TranscriptionError(Exception):
    pass


class RateLimitError(TranscriptionError):
    pass


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_url: str, language: str | None) -> str:
        ...


_provider: TranscriptionProvider | None = None


def get_provider() -> TranscriptionProvider:
    global _provider
    if _provider is None:
        provider_name = getattr(settings, "transcription_provider", "groq")
        if provider_name == "groq":
            from jimini.transcription.groq_provider import GroqTranscriptionProvider
            _provider = GroqTranscriptionProvider()
        else:
            raise ValueError(f"Unknown transcription provider: {provider_name}")
    return _provider


def set_provider(provider: TranscriptionProvider) -> None:
    global _provider
    _provider = provider
