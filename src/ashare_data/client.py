"""统一客户端：数据源选择集中在此，公开返回字段保持稳定。"""

import os

from ._http import HttpClient
from ._utils import normalize_symbol
from .exceptions import ConfigurationError, QuoteNotFoundError
from .sources.eastmoney import EastmoneySource
from .sources.exchanges import ExchangeSource
from .sources.fred import FredSource
from .sources.sina import SinaSource
from .sources.tencent import TencentSource
from .sources.twelvedata import TwelveDataSource


class MarketClient:
    """同步客户端；http 可注入具有 get_json/get_text 方法的传输对象。"""

    def __init__(
        self,
        *,
        timeout=10,
        retries=1,
        fred_api_key=None,
        twelve_api_key=None,
        http=None,
    ):
        self.http = http if http is not None else HttpClient(timeout, retries)
        self._tencent = TencentSource(self.http)
        self._sina = SinaSource(self.http)
        self._eastmoney = EastmoneySource(self.http)
        self._exchanges = ExchangeSource(self.http)
        self._fred = FredSource(self.http, fred_api_key or os.getenv("FRED_API_KEY"))
        self._twelve = TwelveDataSource(
            self.http, twelve_api_key or os.getenv("TWELVE_DATA_API_KEY")
        )

    def get_quotes(self, codes, *, instrument="auto"):
        if isinstance(codes, str):
            raise ConfigurationError("批量 codes 使用字符串列表")
        symbols = [normalize_symbol(code, instrument) for code in codes]
        return self._tencent.quotes(symbols, instrument=instrument)

    def get_quote(self, code, *, instrument="auto"):
        result = self.get_quotes([code], instrument=instrument)[0]
        if "error" in result:
            raise QuoteNotFoundError(f"{result['symbol']} 行情缺失")
        return result

    def get_history(
        self,
        code,
        start=None,
        end=None,
        *,
        instrument="auto",
        source="tencent",
        adjust="qfq",
        scale=240,
        datalen=5049,
        max_pages=100,
    ):
        symbol = normalize_symbol(code, instrument)
        if source == "tencent":
            if scale != 240:
                raise ConfigurationError("腾讯历史接口使用日线 scale=240")
            return self._tencent.history(
                symbol, start, end, adjust=adjust, max_pages=max_pages
            )
        if source == "sina":
            if adjust:
                raise ConfigurationError("新浪历史接口使用 adjust='' 获取原始价格")
            return self._sina.history(symbol, start, end, scale=scale, datalen=datalen)
        raise ConfigurationError("历史 source 使用 tencent 或 sina")

    def get_fund_nav_history(self, code, start=None, end=None):
        return self._eastmoney.nav_history(code, start, end)

    def get_etf_catalog(self):
        return self._sina.etf_catalog()

    def get_sse_etf_shares(self, day):
        return self._exchanges.sse_shares(day)

    def get_fred_series(self, series_id, start=None, end=None, *, api_key=None):
        return self._fred.series(series_id, start, end, api_key=api_key)

    def get_vix_history(self, start=None, end=None, *, api_key=None):
        return self.get_fred_series("VIXCLS", start, end, api_key=api_key)

    def get_twelve_bars(self, symbol, **kwargs):
        return self._twelve.bars(symbol, **kwargs)

    def get_twelve_daily_history(self, symbol, start=None, end=None, **kwargs):
        return self._twelve.daily_history(symbol, start, end, **kwargs)

    def get_stock_quote(self, code):
        return self.get_quote(code, instrument="stock")

    def get_stock_quotes(self, codes):
        return self.get_quotes(codes, instrument="stock")

    def get_stock_history(self, code, start=None, end=None, **kwargs):
        return self.get_history(code, start, end, instrument="stock", **kwargs)

    def get_etf_quote(self, code):
        return self.get_quote(code, instrument="etf")

    def get_etf_quotes(self, codes):
        return self.get_quotes(codes, instrument="etf")

    def get_etf_history(self, code, start=None, end=None, **kwargs):
        return self.get_history(code, start, end, instrument="etf", **kwargs)

    def get_index_quote(self, code):
        return self.get_quote(code, instrument="index")

    def get_index_quotes(self, codes):
        return self.get_quotes(codes, instrument="index")

    def get_index_history(self, code, start=None, end=None, **kwargs):
        kwargs.setdefault("adjust", "")
        return self.get_history(code, start, end, instrument="index", **kwargs)
