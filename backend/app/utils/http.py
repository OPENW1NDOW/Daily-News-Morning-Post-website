import httpx
from ..config import settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}


def make_client(use_proxy: bool = False, timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(proxy=settings.proxy_url if use_proxy else None, timeout=timeout, follow_redirects=True, headers=_HEADERS)


def make_async_client(use_proxy: bool = False, timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(proxy=settings.proxy_url if use_proxy else None, timeout=timeout, follow_redirects=True, headers=_HEADERS)
