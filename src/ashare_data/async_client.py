"""在线程中执行标准库网络请求，供 asyncio 应用 await 调用。"""

import asyncio

from .client import MarketClient


class AsyncMarketClient:
    """每个实例复用一个同步客户端，多个协程共享净值请求限制。"""

    def __init__(self, **kwargs):
        self._client = MarketClient(**kwargs)

    async def get_quote(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_quote, *args, **kwargs)

    async def get_quotes(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_quotes, *args, **kwargs)

    async def get_history(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_history, *args, **kwargs)

    async def get_fund_nav_history(self, *args, **kwargs):
        return await asyncio.to_thread(
            self._client.get_fund_nav_history, *args, **kwargs
        )

    async def get_etf_catalog(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_etf_catalog, *args, **kwargs)

    async def get_sse_etf_shares(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_sse_etf_shares, *args, **kwargs)

    async def get_fred_series(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_fred_series, *args, **kwargs)

    async def get_vix_history(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_vix_history, *args, **kwargs)

    async def get_twelve_bars(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_twelve_bars, *args, **kwargs)

    async def get_twelve_daily_history(self, *args, **kwargs):
        return await asyncio.to_thread(
            self._client.get_twelve_daily_history, *args, **kwargs
        )

    async def get_stock_quote(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_stock_quote, *args, **kwargs)

    async def get_stock_quotes(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_stock_quotes, *args, **kwargs)

    async def get_stock_history(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_stock_history, *args, **kwargs)

    async def get_etf_quote(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_etf_quote, *args, **kwargs)

    async def get_etf_quotes(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_etf_quotes, *args, **kwargs)

    async def get_etf_history(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_etf_history, *args, **kwargs)

    async def get_index_quote(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_index_quote, *args, **kwargs)

    async def get_index_quotes(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_index_quotes, *args, **kwargs)

    async def get_index_history(self, *args, **kwargs):
        return await asyncio.to_thread(self._client.get_index_history, *args, **kwargs)
