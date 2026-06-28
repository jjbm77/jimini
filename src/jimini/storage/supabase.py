from __future__ import annotations

from datetime import datetime, timezone

from jimini.config import settings
from jimini.db import get_db


def signed_url_is_expired(signed_url: str) -> bool:
    if "?expires=" not in signed_url:
        return False
    try:
        expires_str = signed_url.split("?expires=")[1].split("&")[0]
        expires_ts = int(expires_str)
        return datetime.fromtimestamp(expires_ts, tz=timezone.utc) <= datetime.now(
            timezone.utc
        )
    except (ValueError, IndexError):
        return False


def regenerate_signed_url(storage_path: str) -> str | None:
    db = get_db()
    ttl = settings.signed_url_ttl_hours * 3600
    result = (
        db.storage.from_(settings.supabase_bucket_audio)
        .create_signed_url(storage_path, ttl)
    )
    if result:
        return result.get("signedURL") or result.get("signed_url")
    return None
