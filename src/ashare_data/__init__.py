"""稳定的行情入口；公开数据由同步函数或 AsyncMarketClient 获取。"""

from ._default import configure, get_client
from .async_client import AsyncMarketClient
from .client import MarketClient
from .etf import (
    get_etf_quote,
    get_etf_quotes,
    get_etf_history,
    get_fund_nav_history,
    get_etf_catalog,
    get_sse_etf_shares,
)
from .stock import get_stock_quote, get_stock_quotes, get_stock_history
from .index import get_index_quote, get_index_quotes, get_index_history
from .exceptions import (
    MarketDataError,
    InvalidCodeError,
    ConfigurationError,
    RequestError,
    DataFormatError,
    QuoteNotFoundError,
    AllSourcesFailedError,
)

__version__ = "0.1.0"


def get_quote(code, **kwargs):
    return get_client().get_quote(code, **kwargs)


def get_quotes(codes, **kwargs):
    return get_client().get_quotes(codes, **kwargs)


def get_history(code, start=None, end=None, **kwargs):
    return get_client().get_history(code, start, end, **kwargs)


def get_fred_series(series_id, start=None, end=None, **kwargs):
    return get_client().get_fred_series(series_id, start, end, **kwargs)


def get_vix_history(start=None, end=None, **kwargs):
    return get_client().get_vix_history(start, end, **kwargs)


def get_twelve_bars(symbol, **kwargs):
    return get_client().get_twelve_bars(symbol, **kwargs)


def get_twelve_daily_history(symbol, start=None, end=None, **kwargs):
    return get_client().get_twelve_daily_history(symbol, start, end, **kwargs)


__all__ = [
    "get_quote",
    "get_quotes",
    "get_history",
    "get_fund_nav_history",
    "get_etf_catalog",
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
]
