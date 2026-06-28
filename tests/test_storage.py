from __future__ import annotations

from datetime import datetime, timezone

from jimini.storage.supabase import signed_url_is_expired


def test_sin_expires():
    assert signed_url_is_expired("https://example.com/file.ogg") is False


def test_url_expirada():
    five_seconds_ago = int(datetime.now(timezone.utc).timestamp()) - 5
    url = f"https://example.com/file.ogg?expires={five_seconds_ago}"
    assert signed_url_is_expired(url) is True


def test_url_vigente():
    far_future = int(datetime.now(timezone.utc).timestamp()) + 86400 * 365
    url = f"https://example.com/file.ogg?expires={far_future}"
    assert signed_url_is_expired(url) is False


def test_url_parse_error():
    assert signed_url_is_expired("https://example.com/file.ogg?expires=notanumber") is False


def test_url_multiple_params():
    far_future = int(datetime.now(timezone.utc).timestamp()) + 86400 * 365
    url = f"https://example.com/file.ogg?token=abc&expires={far_future}&sig=xyz"
    assert signed_url_is_expired(url) is False
