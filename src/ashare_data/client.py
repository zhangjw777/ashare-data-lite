"""统一客户端与有序来源降级。"""

import os
from typing import Sequence

from ._convert import (
    bar_models,
    nav_models,
    observation_models,
    quote_model,
    shares_models,
)
from ._http import HttpClient
from ._utils import date_range, is_index, normalize_symbol, source_order
from .exceptions import ConfigurationError, QuoteNotFoundError
from .fallback import first_success
from .models import Bar, DateLike, FundNav, FundShares, Instrument, Observation, Quote
from .sources.eastmoney import EastmoneySource
from .sources.exchanges import ExchangeSource
from .sources.fred import FredSource
from .sources.sina import SinaSource
from .sources.tencent import TencentSource
from .sources.twelvedata import TwelveDataSource


class MarketClient:
    """同步行情客户端；timeout 为每次网络请求的秒数，retries 为重试次数。"""

    def __init__(
        self,
        *,
        timeout: float = 10,
        retries: int = 1,
        fred_api_key: str | None = None,
        twelve_api_key: str | None = None,
        http=None,
    ):
        """创建可复用客户端；账户密钥默认读取对应环境变量。"""
        self.http = http if http is not None else HttpClient(timeout, retries)
        self._tencent = TencentSource(self.http)
        self._sina = SinaSource(self.http)
        self._eastmoney = EastmoneySource(self.http)
        self._exchanges = ExchangeSource(self.http)
        self._fred = FredSource(self.http, fred_api_key or os.getenv("FRED_API_KEY"))
        self._twelve = TwelveDataSource(
            self.http, twelve_api_key or os.getenv("TWELVE_DATA_API_KEY")
        )

    def get_quotes(
        self, codes: Sequence[str], *, instrument: Instrument = "auto"
    ) -> list[Quote]:
        """批量获取实时行情，按首次出现的代码顺序返回 Quote；缺失项带 error。"""
        if isinstance(codes, str):
            raise ConfigurationError("批量 codes 使用字符串列表")
        symbols = [normalize_symbol(code, instrument) for code in codes]
        return [
            quote_model(row, instrument)
            for row in self._tencent.quotes(symbols, instrument=instrument)
        ]

    def get_quote(self, code: str, *, instrument: Instrument = "auto") -> Quote:
        """获取单只实时行情；缺失时抛出 QuoteNotFoundError。"""
        quote = self.get_quotes([code], instrument=instrument)[0]
        if quote.error:
            raise QuoteNotFoundError(f"{quote.symbol} 行情缺失")
        return quote

    def get_history(
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
        symbol = normalize_symbol(code, instrument)
        start, end = date_range(start, end)
        if adjust not in {"none", "qfq", "hfq"}:
            raise ConfigurationError("adjust 使用 none、qfq 或 hfq")
        if scale not in {5, 15, 30, 240}:
            raise ConfigurationError("scale 使用 5、15、30 或 240")
        if not isinstance(datalen, int) or not 1 <= datalen <= 5049:
            raise ConfigurationError("datalen 使用 1～5049 的整数")
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ConfigurationError("max_pages 应为正整数")
        if (instrument == "index" or is_index(symbol)) and adjust != "none":
            raise ConfigurationError("指数历史使用 adjust='none'")
        order = source_order(
            sources,
            ("tencent", "sina") if scale == 240 else ("sina",),
            ("tencent", "sina"),
        )
        # 降级保持周期与复权方式一致，按来源能力选取候选请求。
        fetchers = {}
        if scale == 240:
            fetchers["tencent"] = lambda: self._tencent.history(
                symbol,
                start,
                end,
                adjust="" if adjust == "none" else adjust,
                max_pages=max_pages,
            )
        if adjust == "none":
            fetchers["sina"] = lambda: self._sina.history(
                symbol, start, end, scale=scale, datalen=datalen
            )
        interval = "1day" if scale == 240 else f"{scale}min"
        candidates = [
            (name, lambda fetch=fetchers[name]: bar_models(fetch(), symbol, interval))
            for name in order
            if name in fetchers
        ]
        if not candidates:
            raise ConfigurationError("所选来源需支持请求的周期与复权方式")
        return first_success(candidates)

    def get_fund_nav_history(
        self,
        code: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        sources: Sequence[str] | None = None,
    ) -> list[FundNav]:
        """获取升序基金单位净值，默认东方财富移动端→网页，sources 可调整顺序。"""
        return nav_models(
            self._eastmoney.nav_history(code, start, end, sources=sources)
        )

    def get_etf_catalog(self) -> dict[str, str]:
        """获取场内 ETF 目录，返回六位代码到名称的映射。"""
        return self._sina.etf_catalog()

    def get_sse_etf_shares(self, day: DateLike) -> list[FundShares]:
        """获取上交所指定统计日的 ETF 份额，shares 单位为份。"""
        return shares_models(self._exchanges.sse_shares(day))

    def get_fred_series(
        self,
        series_id: str,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        api_key: str | None = None,
    ) -> list[Observation]:
        """获取升序 FRED 观测值；api_key 优先于客户端配置和环境变量。"""
        return observation_models(
            self._fred.series(series_id, start, end, api_key=api_key)
        )

    def get_vix_history(
        self,
        start: DateLike | None = None,
        end: DateLike | None = None,
        *,
        api_key: str | None = None,
    ) -> list[Observation]:
        """获取 VIX 日度收盘序列 VIXCLS，返回 Observation 列表。"""
        return self.get_fred_series("VIXCLS", start, end, api_key=api_key)

    def get_twelve_bars(
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
        rows = self._twelve.bars(
            symbol,
            interval=interval,
            outputsize=outputsize,
            start=start,
            end=end,
            adjust=adjust,
            api_key=api_key,
        )
        return bar_models(rows, symbol.strip().upper(), interval)

    def get_twelve_daily_history(
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
        rows = self._twelve.daily_history(
            symbol, start, end, adjust=adjust, api_key=api_key, max_pages=max_pages
        )
        return bar_models(rows, symbol.strip().upper(), "1day")

    def get_stock_quote(self, code: str) -> Quote:
        """获取单只股票实时行情，返回 Quote。"""
        return self.get_quote(code, instrument="stock")

    def get_stock_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取股票实时行情，按首次输入顺序返回 Quote 列表。"""
        return self.get_quotes(codes, instrument="stock")

    def get_stock_history(
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
        return self.get_history(
            code,
            start,
            end,
            instrument="stock",
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )

    def get_etf_quote(self, code: str) -> Quote:
        """获取单只ETF实时行情，返回 Quote。"""
        return self.get_quote(code, instrument="etf")

    def get_etf_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取ETF实时行情，按首次输入顺序返回 Quote 列表。"""
        return self.get_quotes(codes, instrument="etf")

    def get_etf_history(
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
        return self.get_history(
            code,
            start,
            end,
            instrument="etf",
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )

    def get_index_quote(self, code: str) -> Quote:
        """获取单只指数实时行情，返回 Quote。"""
        return self.get_quote(code, instrument="index")

    def get_index_quotes(self, codes: Sequence[str]) -> list[Quote]:
        """批量获取指数实时行情，按首次输入顺序返回 Quote 列表。"""
        return self.get_quotes(codes, instrument="index")

    def get_index_history(
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
        return self.get_history(
            code,
            start,
            end,
            instrument="index",
            sources=sources,
            adjust=adjust,
            scale=scale,
            datalen=datalen,
            max_pages=max_pages,
        )
