from __future__ import annotations

from supabase import Client, create_client

from jimini.config import settings

_supabase: Client | None = None


def get_db() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase
