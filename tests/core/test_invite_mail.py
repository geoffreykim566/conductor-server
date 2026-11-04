"""Invite email: one recipient per send with the download link, and a failure returns False instead of raising."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core import invite_mail


async def test_send_posts_one_recipient_with_the_link() -> None:
    client = MagicMock()
    client.post = AsyncMock(return_value=httpx.Response(200, request=httpx.Request("POST", "https://x")))
    with patch.object(invite_mail.config, "RESEND_API_KEY", "k"), \
            patch.object(invite_mail.config, "DOWNLOAD_URL", "https://askconductor.ai/download"):
        assert await invite_mail.send(client, "sam@example.com") is True
    kw = client.post.await_args.kwargs
    assert kw["json"]["to"] == ["sam@example.com"], kw
    assert "https://askconductor.ai/download" in kw["json"]["text"], kw
    assert kw["headers"]["Authorization"] == "Bearer k", kw


async def test_a_failed_send_returns_false() -> None:
    client = MagicMock()
    client.post = AsyncMock(return_value=httpx.Response(422, request=httpx.Request("POST", "https://x")))
    assert await invite_mail.send(client, "a@b.co") is False
    client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    assert await invite_mail.send(client, "a@b.co") is False


def test_configured_follows_the_key() -> None:
    with patch.object(invite_mail.config, "RESEND_API_KEY", ""):
        assert not invite_mail.configured()
    with patch.object(invite_mail.config, "RESEND_API_KEY", "k"):
        assert invite_mail.configured()
