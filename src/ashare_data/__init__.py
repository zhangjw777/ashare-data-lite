"""轻量证券行情接口，返回可序列化的 dataclass 对象。"""

from ._default import configure, get_client
from .async_client import AsyncMarketClient
from .client import MarketClient
from typing import Sequence

from .models import (
    Bar,
    DateLike,
    ETFComponent,
    ETFHolding,
    ETFPcf,
    FundNav,
    FundShares,
    Instrument,
    Observation,
    Quote,
)
from .stock import get_stock_quote, get_stock_quotes, get_stock_history
from .index import get_index_quote, get_index_quotes, get_index_history
from .etf import (
    get_etf_quote,
    get_etf_quotes,
    get_etf_history,
    get_fund_nav_history,
    get_etf_catalog,
    get_etf_pcf,
    get_etf_holdings,
    get_sse_etf_shares,
)
from .exceptions import (
    MarketDataError,
    InvalidCodeError,
    ConfigurationError,
    RequestError,
    DataFormatError,
    QuoteNotFoundError,
    AllSourcesFailedError,
)
from .models import OrderLevel

__version__ = "0.1.2"


def get_quotes(codes: Sequence[str], *, instrument: Instrument = "auto") -> list[Quote]:
    """批量获取实时行情，按首次出现的代码顺序返回 Quote；缺失项带 error。"""
    return get_client().get_quotes(codes, instrument=instrument)


def get_quote(code: str, *, instrument: Instrument = "auto") -> Quote:
    """获取单只实时行情；缺失时抛出 QuoteNotFoundError。"""
    return get_client().get_quote(code, instrument=instrument)


def get_history(
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
    return get_client().get_history(
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


def get_fred_series(
    series_id: str,
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    api_key: str | None = None,
) -> list[Observation]:
    """获取升序 FRED 观测值；api_key 优先于客户端配置和环境变量。"""
    return get_client().get_fred_series(series_id, start, end, api_key=api_key)


def get_vix_history(
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    api_key: str | None = None,
) -> list[Observation]:
    """获取 VIX 日度收盘序列 VIXCLS，返回 Observation 列表。"""
    return get_client().get_vix_history(start, end, api_key=api_key)


def get_twelve_bars(
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
    return get_client().get_twelve_bars(
        symbol,
        interval=interval,
        outputsize=outputsize,
        start=start,
        end=end,
        adjust=adjust,
        api_key=api_key,
    )


def get_twelve_daily_history(
    symbol: str,
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    adjust: str = "all",
    api_key: str | None = None,
    max_pages: int = 100,
) -> list[Bar]:
    """分页获取指定日期区间的升序海外日线，返回 Bar 列表。"""
    return get_client().get_twelve_daily_history(
        symbol, start, end, adjust=adjust, api_key=api_key, max_pages=max_pages
    )


__all__ = [
    "get_quote",
    "get_quotes",
    "get_history",
    "get_fund_nav_history",
    "get_etf_catalog",
    "get_etf_pcf",
    "get_etf_holdings",
    "get_sse_etf_shares",
    "get_fred_series",
    "get_vix_history",
    "get_twelve_bars",
    "get_twelve_daily_history",
    "get_stock_quote",
    "get_stock_quotes",
    "get_stock_history",
    "get_etf_quote",
    "get_etf_quotes",
    "get_etf_history",
    "get_index_quote",
    "get_index_quotes",
    "get_index_history",
    "configure",
    "MarketClient",
    "AsyncMarketClient",
    "MarketDataError",
    "InvalidCodeError",
    "ConfigurationError",
    "RequestError",
    "DataFormatError",
    "QuoteNotFoundError",
    "AllSourcesFailedError",
    "Quote",
    "OrderLevel",
    "Bar",
    "FundNav",
    "FundShares",
    "ETFComponent",
    "ETFPcf",
    "ETFHolding",
    "Observation",
]
