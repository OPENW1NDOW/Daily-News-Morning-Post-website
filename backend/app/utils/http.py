import httpx
from ..config import settings


def make_client(use_proxy: bool = False, timeout: float = 10.0) -> httpx.Client:
    proxies = {"http://": settings.proxy_url, "https://": settings.proxy_url} if use_proxy else None
    return httpx.Client(proxy=settings.proxy_url if use_proxy else None, timeout=timeout, follow_redirects=True)


def make_async_client(use_proxy: bool = False, timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(proxy=settings.proxy_url if use_proxy else None, timeout=timeout, follow_redirects=True)
