from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", ""))
    supabase_bucket_audio: str = field(default="audio-ingesta")
    signed_url_ttl_hours: int = field(
        default_factory=lambda: int(os.environ.get("SIGNED_URL_TTL_HOURS", "24"))
    )
    openrouter_api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    webhook_secret_token: str = field(
        default_factory=lambda: os.environ.get("WEBHOOK_SECRET_TOKEN", "")
    )
    transcripcion_idioma_default: str = field(
        default_factory=lambda: os.environ.get("TRANSCRIPCION_IDIOMA_DEFAULT", "es")
    )
    groq_model: str = field(
        default_factory=lambda: os.environ.get("GROQ_MODEL", "whisper-large-v3-turbo")
    )
    max_audio_file_size_mb: int = field(
        default_factory=lambda: int(os.environ.get("MAX_AUDIO_FILE_SIZE_MB", "25"))
    )
    worker_poll_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))
    )


settings = Settings()
