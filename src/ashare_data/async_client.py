"""异步行情客户端。"""

import asyncio

from .client import MarketClient
from typing import Sequence

from .models import Bar, DateLike, FundNav, FundShares, Instrument, Observation, Quote


class AsyncMarketClient:
    """提供与 MarketClient 相同的 await 方法和返回类型。"""

    def __init__(
        self,
        *,
        timeout: float = 10,
        retries: int = 1,
        fred_api_key: str | None = None,
        twelve_api_key: str | None = None,
        http=None,
    ):
        """创建异步客户端，复用同一请求配置和净值限速状态。"""
        self._client = MarketClient(
            timeout=timeout,
            retries=retries,
            fred_api_key=fred_api_key,
            twelve_api_key=twelve_api_key,
            http=http,
        )

    async def get_quotes(
        self, codes: Sequence[str], *, instrument: Instrument = "auto"
    ) -> list[Quote]:
        """批量获取实时行情，按首次出现的代码顺序返回 Quote；缺失项带 error。"""
        return await asyncio.to_thread(
            self._client.get_quotes, codes, instrument=instrument
        )

    async def get_quote(self, code: str, *, instrument: Instrument = "auto") -> Quote:
        """获取单只实时行情；缺失时抛出 QuoteNotFoundError。"""
        return await asyncio.to_thread(
            self._client.get_quote, code, instrument=instrument
        )

    async def get_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        instrument: Instrument = "auto",
        sources: Sequence[str] | None = None,
        adjust: str = "none",
        scale: int = 240,
        datalen: int = 5049,
        max_pages: int = 100,
    ) -> list[Bar]:
        """获取升序 K 线；sources 按顺序降级，默认日线腾讯→新浪、分钟线新浪。"""
        return await asyncio.to_thread(
            self._client.get_history,
            code,
            start,
            end,
            instrument=instrument,
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )

    async def get_fund_nav_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        sources: Sequence[str] | None = None,
    ) -> list[FundNav]:
        """获取升序基金单位净值，默认东方财富移动端→网页，sources 可调整顺序。"""
        return await asyncio.to_thread(
            self._client.get_fund_nav_history, code, start, end, sources=sources
        )

    async def get_etf_catalog(self) -> dict[str, str]:
        """获取场内 ETF 目录，返回六位代码到名称的映射。"""
        return await asyncio.to_thread(self._client.get_etf_catalog)

    async def get_sse_etf_shares(self, day: DateLike) -> list[FundShares]:
        """获取上交所指定统计日的 ETF 份额，shares 单位为份。"""
        return await asyncio.to_thread(self._client.get_sse_etf_shares, day)

    async def get_fred_series(
        self,
        series_id: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        api_key: str | None = None,
    ) -> list[Observation]:
        """获取升序 FRED 观测值；api_key 优先于客户端配置和环境变量。"""
        return await asyncio.to_thread(
            self._client.get_fred_series, series_id, start, end, api_key=api_key
        )

    async def get_vix_history(
        self,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        api_key: str | None = None,
    ) -> list[Observation]:
        """获取 VIX 日度收盘序列 VIXCLS，返回 Observation 列表。"""
        return await asyncio.to_thread(
            self._client.get_vix_history, start, end, api_key=api_key
        )

    async def get_twelve_bars(
        self,
        symbol: str,
        *,
        interval: str = "1day",
        outputsize: int = 5000,
        start: DateLike | None = None,
        end: DateLike | None = None,
        adjust: str = "all",
        api_key: str | None = None,
    ) -> list[Bar]:
        """获取一页升序海外 K 线，outputsize 为 1～5000，时间使用 UTC。"""
        return await asyncio.to_thread(
            self._client.get_twelve_bars,
            symbol,
            interval=interval,
            outputsize=outputsize,
            start=start,
            end=end,
            adjust=adjust,
            api_key=api_key,
        )

    async def get_twelve_daily_history(
        self,
        symbol: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        adjust: str = "all",
        api_key: str | None = None,
        max_pages: int = 100,
    ) -> list[Bar]:
        """分页获取指定日期区间的升序海外日线，返回 Bar 列表。"""
        return await asyncio.to_thread(
            self._client.get_twelve_daily_history,
            symbol,
            start,
            end,
            adjust=adjust,
            api_key=api_key,
            max_pages=max_pages,
        )

    async def get_stock_quote(self, code: str) -> Quote:
        """获取单只股票实时行情，返回 Quote。"""
        return await asyncio.to_thread(self._client.get_stock_quote, code)

    async def get_stock_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取股票实时行情，按首次输入顺序返回 Quote 列表。"""
        return await asyncio.to_thread(self._client.get_stock_quotes, codes)

    async def get_stock_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        sources: Sequence[str] | None = None,
        adjust: str = "none",
        scale: int = 240,
        datalen: int = 5049,
        max_pages: int = 100,
    ) -> list[Bar]:
        """获取升序股票历史 K 线；sources 按优先顺序降级，默认原始价格。"""
        return await asyncio.to_thread(
            self._client.get_stock_history,
            code,
            start,
            end,
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )

    async def get_etf_quote(self, code: str) -> Quote:
        """获取单只ETF实时行情，返回 Quote。"""
        return await asyncio.to_thread(self._client.get_etf_quote, code)

    async def get_etf_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取ETF实时行情，按首次输入顺序返回 Quote 列表。"""
        return await asyncio.to_thread(self._client.get_etf_quotes, codes)

    async def get_etf_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        sources: Sequence[str] | None = None,
        adjust: str = "none",
        scale: int = 240,
        datalen: int = 5049,
        max_pages: int = 100,
    ) -> list[Bar]:
        """获取升序ETF历史 K 线；sources 按优先顺序降级，默认原始价格。"""
        return await asyncio.to_thread(
            self._client.get_etf_history,
            code,
            start,
            end,
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )

    async def get_index_quote(self, code: str) -> Quote:
        """获取单只指数实时行情，返回 Quote。"""
        return await asyncio.to_thread(self._client.get_index_quote, code)

    async def get_index_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取指数实时行情，按首次输入顺序返回 Quote 列表。"""
        return await asyncio.to_thread(self._client.get_index_quotes, codes)

    async def get_index_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        sources: Sequence[str] | None = None,
        adjust: str = "none",
        scale: int = 240,
        datalen: int = 5049,
        max_pages: int = 100,
    ) -> list[Bar]:
        """获取升序指数历史 K 线；sources 按优先顺序降级，默认原始价格。"""
        return await asyncio.to_thread(
            self._client.get_index_history,
            code,
            start,
            end,
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )
