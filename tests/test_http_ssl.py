"""TLS helper for Steam Web API requests."""

from __future__ import annotations

import ssl
from unittest.mock import patch

from src.utils.http import build_ssl_context, urlopen


def test_build_ssl_context_uses_certifi():
    ctx = build_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)


def test_urlopen_passes_ssl_context():
    with patch("src.utils.http.urllib.request.urlopen") as mock_urlopen:
        from urllib.request import Request

        req = Request("https://example.com")
        ctx = ssl.create_default_context()
        with patch("src.utils.http.build_ssl_context", return_value=ctx):
            urlopen(req, timeout=5)
        mock_urlopen.assert_called_once_with(req, timeout=5, context=ctx)
