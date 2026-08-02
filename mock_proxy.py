"""
Route all Instagram HTTP traffic through the mockapis proxy.
Rewrites www.instagram.com and i.instagram.com URLs to the configured mock base.
"""

from typing import Callable
import requests
from config import config

INSTAGRAM_HOST_PREFIXES = (
    "https://www.instagram.com/",
    "https://i.instagram.com/",
    "http://www.instagram.com/",
    "http://i.instagram.com/",
)

_original_session_request: Callable = requests.Session.request
_patched = False


def rewrite_instagram_url(url: str) -> str:
    """Map real Instagram URLs to the mockapis demo endpoint."""
    base = config.MOCK_API_BASE_URL.rstrip("/") + "/"
    for prefix in INSTAGRAM_HOST_PREFIXES:
        if url.startswith(prefix):
            return base + url[len(prefix):]
    return url


def install_mock_proxy() -> None:
    """Patch requests.Session so instaloader never hits real instagram.com."""
    global _patched
    if _patched:
        return

    def patched_request(self, method, url, *args, **kwargs):
        if isinstance(url, str):
            url = rewrite_instagram_url(url)
        return _original_session_request(self, method, url, *args, **kwargs)

    requests.Session.request = patched_request  # type: ignore[method-assign]
    _patched = True
