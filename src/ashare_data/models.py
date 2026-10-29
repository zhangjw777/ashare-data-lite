"""公开数据类型；金额使用标价币种，百分率使用百分数。"""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Literal

Instrument = Literal["auto", "stock", "etf", "index"]
DateLike = str | date


class DataModel:
    """提供可直接用于 JSON 的字典转换。"""

    __slots__ = ()

    def to_dict(self) -> dict:
        """递归转为字典；日期和带时区时间转为 ISO 8601 字符串。"""

        def encode(value):
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [encode(item) for item in value]
            return value

        return encode(asdict(self))


@dataclass(frozen=True, slots=True)
class OrderLevel(DataModel):
    """一档买卖报价；volume 为股数或基金份数。"""

    price: float | None
    volume: float | None


@dataclass(frozen=True, slots=True)
class Quote(DataModel):
    """股票、ETF、指数共用的实时行情；缺失的数值为 None。"""

    symbol: str
    code: str
    instrument: str
    source: str
    name: str | None = None
    timestamp: datetime | None = None
    currency: str | None = None
    last: float | None = None
    prev_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    outer_volume: float | None = None
    inner_volume: float | None = None
    turnover_rate_pct: float | None = None
    amplitude_pct: float | None = None
    market_cap: float | None = None
    circulating_market_cap: float | None = None
    pe: float | None = None
    pb: float | None = None
    limit_up: float | None = None
    limit_down: float | None = None
    volume_ratio: float | None = None
    order_imbalance: float | None = None
    average_price: float | None = None
    is_suspended: bool = False
    bids: tuple[OrderLevel, ...] = ()
    asks: tuple[OrderLevel, ...] = ()
    iopv: float | None = None
    premium_rate_pct: float | None = None
    circulating_shares: float | None = None
    total_shares: float | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Bar(DataModel):
    """各来源共用的 K 线；timestamp 带时区，adjust 标明价格调整方式。"""

    symbol: str
    timestamp: datetime
    interval: str
    source: str
    adjust: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None = None
    volume_unit: str = "share"
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class FundNav(DataModel):
    """基金某一净值所属日的单位净值。"""

    code: str
    date: date
    nav: float
    source: str


@dataclass(frozen=True, slots=True)
class FundShares(DataModel):
    """基金某一统计日的份额，shares 单位为份。"""

    code: str
    date: date
    shares: float | None
    source: str


@dataclass(frozen=True, slots=True)
class ETFComponent(DataModel):
    """一个申赎单位的成分；现金替代金额为人民币，溢折价率为小数。"""

    code: str
    name: str
    market: str
    quantity: float
    substitution_flag: str
    creation_premium_rate: float | None
    redemption_discount_rate: float | None
    creation_cash_substitute: float | None
    redemption_cash_substitute: float | None
    is_cash: bool


@dataclass(frozen=True, slots=True)
class ETFPcf(DataModel):
    """最新申购赎回清单（PCF）；creation_unit 为份数，金额为人民币。"""

    code: str
    source: str
    creation_unit: float
    nav_per_cu: float
    cash_component: float | None
    components: tuple[ETFComponent, ...]


@dataclass(frozen=True, slots=True)
class ETFHolding(DataModel):
    """申赎篮子证券的最新估值；market_value 为人民币，weight_pct 为百分数。"""

    code: str
    name: str
    market: str
    quantity: float
    price: float | None
    currency: str
    exchange_rate: float
    market_value: float
    weight_pct: float
    valuation: str


@dataclass(frozen=True, slots=True)
class Observation(DataModel):
    """经济或市场序列在某一观测日期的数值。"""

    series_id: str
    date: date
    value: float
    source: str
