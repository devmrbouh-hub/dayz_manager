"""HTTP helpers with a reliable TLS trust store on Windows."""

from __future__ import annotations

import ssl
import urllib.request
from typing import Optional


def build_ssl_context() -> ssl.SSLContext:
    """Build SSL context; prefer certifi bundle when system CA store is missing."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def urlopen(req: urllib.request.Request, timeout: int = 20, context: Optional[ssl.SSLContext] = None):
    """urllib.request.urlopen with explicit CA bundle (fixes Win Errno 2 on HTTPS)."""
    return urllib.request.urlopen(req, timeout=timeout, context=context or build_ssl_context())
