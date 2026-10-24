"""进程级默认客户端，连续调用复用净值限速与冷却状态。"""

import threading

from .client import MarketClient

_client = None
_lock = threading.Lock()


def get_client():
    global _client
    with _lock:
        if _client is None:
            _client = MarketClient()
        return _client


def configure(
    *,
    timeout: float = 10,
    retries: int = 1,
    fred_api_key: str | None = None,
    twelve_api_key: str | None = None,
) -> MarketClient:
    """设置全局请求超时、重试和账户密钥，返回新的默认客户端。"""
    global _client
    client = MarketClient(
        timeout=timeout,
        retries=retries,
        fred_api_key=fred_api_key,
        twelve_api_key=twelve_api_key,
    )
    with _lock:
        _client = client
    return client
