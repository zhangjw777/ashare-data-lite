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


def configure(**kwargs):
    """配置默认客户端，返回创建的 MarketClient。"""
    global _client
    client = MarketClient(**kwargs)
    with _lock:
        _client = client
    return client
