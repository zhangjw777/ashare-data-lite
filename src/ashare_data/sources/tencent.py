"""腾讯实时行情与历史日线。"""

import re
from datetime import date, datetime, timedelta
from typing import Any

from .._utils import date_range, is_index, normalize_symbol, number, sorted_rows
from ..exceptions import ConfigurationError, DataFormatError

QUOTE_URL = "https://qt.gtimg.cn/q="
HISTORY_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
RECORD = re.compile(r'v_([A-Za-z0-9_.]+)="(.*?)";', re.DOTALL)


def _field(fields: list[str], index: int) -> str:
    return fields[index].strip() if index < len(fields) else ""


def _float(fields: list[str], index: int) -> float | None:
    return number(_field(fields, index))


def _int(fields: list[str], index: int) -> int | None:
    value = _float(fields, index)
    return int(value) if value is not None else None


def _quote_time(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").isoformat(sep=" ")
    except ValueError:
        return None


def _instrument_type(symbol: str, fields: list[str]) -> str:
    type_tag = _field(fields, 61).upper()
    if "ETF" in type_tag:
        return "etf"
    if type_tag.startswith("GP"):
        return "stock"
    code = _field(fields, 2)
    is_etf = (
        symbol.startswith("sh")
        and code.startswith("5")
        or (symbol.startswith("sz") and code.startswith(("15", "16")))
    )
    return "etf" if is_etf else "stock"


def _order_book(fields: list[str]) -> dict[str, list[dict[str, Any]]]:

    def levels(start: int) -> list[dict[str, Any]]:
        return [
            {
                "level": level,
                "price": _float(fields, start + (level - 1) * 2),
                "volume_lot": _int(fields, start + (level - 1) * 2 + 1),
            }
            for level in range(1, 6)
        ]

    return {"bids": levels(9), "asks": levels(19)}


def _amount_yuan(fields: list[str]) -> float | None:
    summary = _field(fields, 35).split("/")
    if len(summary) >= 3:
        amount = number(summary[2])
        if amount is not None:
            return amount
    amount_10k = _float(fields, 57)
    return amount_10k * 10000 if amount_10k is not None else None


def parse_quote(symbol: str, payload: str, instrument="auto") -> dict[str, Any]:
    """解析实时行情的业务字段，统一中间数据的价格和数量含义。"""
    fields = [part.strip() for part in payload.split("~")]
    if len(fields) <= 30:
        raise DataFormatError(f"{symbol} 行情字段不足")
    symbol = normalize_symbol(symbol)
    kind = (
        "index"
        if instrument == "index" or is_index(symbol)
        else _instrument_type(symbol, fields)
    )
    book = _order_book(fields)
    amount = _amount_yuan(fields)
    volume = _int(fields, 6)
    result = {
        "source": "tencent",
        "symbol": symbol,
        "code": _field(fields, 2),
        "name": _field(fields, 1),
        "instrument_type": kind,
        "quote_time": _quote_time(_field(fields, 30)),
        "currency": _field(fields, 82) or None,
        "is_suspended": _field(fields, 40) == "S",
        "order_book": book,
        "volume_lot": volume,
        "amount_yuan": amount,
        "average_price_calculated": amount / (volume * 100)
        if amount is not None and volume
        else None,
        "order_imbalance_calculated": sum(
            level["volume_lot"] or 0 for level in book["bids"]
        )
        - sum(level["volume_lot"] or 0 for level in book["asks"]),
    }
    indexes = {
        "last": 3,
        "prev_close": 4,
        "open": 5,
        "high": 33,
        "low": 34,
        "change": 31,
        "change_pct": 32,
        "outer_volume_lot": 7,
        "inner_volume_lot": 8,
        "turnover_rate": 38,
        "amplitude": 43,
        "circulating_market_cap_100m": 44,
        "total_market_cap_100m": 45,
        "pb": 46,
        "limit_up": 47,
        "limit_down": 48,
        "volume_ratio": 49,
        "average_price": 51,
    }
    result.update((key, _float(fields, index)) for key, index in indexes.items())
    if kind == "etf":
        iopv, last = _float(fields, 78), result["last"]
        result["etf"] = {
            "iopv": iopv,
            "premium_rate": _float(fields, 77),
            "premium_rate_calculated": (last / iopv - 1) * 100
            if last is not None and iopv
            else None,
            "circulating_units": _int(fields, 72),
            "total_units": _int(fields, 73),
        }
    elif kind == "stock":
        result["stock"] = {
            "pe": _float(fields, 39),
            "circulating_shares": _int(fields, 72),
            "total_shares": _int(fields, 73),
        }
    return result


class TencentSource:
    def __init__(self, http):
        self.http = http

    def quotes(self, symbols, *, instrument="auto"):
        symbols = list(dict.fromkeys(symbols))
        quotes = {}
        for offset in range(0, len(symbols), 50):
            text = self.http.get_text(
                QUOTE_URL + ",".join(symbols[offset : offset + 50]), encoding="gbk"
            )
            matches = RECORD.findall(text)
            if not matches:
                raise DataFormatError("腾讯行情响应缺少证券记录")
            for symbol, payload in matches:
                if payload and symbol in symbols:
                    quotes[symbol] = parse_quote(symbol, payload, instrument)
        return [
            quotes.get(
                symbol, {"symbol": symbol, "source": "tencent", "error": "行情缺失"}
            )
            for symbol in symbols
        ]

    def history(self, symbol, start=None, end=None, *, adjust="qfq", max_pages=100):
        if adjust not in {"", "qfq", "hfq"}:
            raise ConfigurationError("adjust 使用空字符串、qfq 或 hfq")
        if is_index(symbol) and adjust:
            raise ConfigurationError("指数日线使用 adjust='' 获取原始价格")
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ConfigurationError("max_pages 应为正整数")
        start, end = date_range(start, end)
        cursor, rows = end, []
        for _ in range(max_pages):
            body = self.http.get_json(
                HISTORY_URL, params={"param": f"{symbol},day,,{cursor},640,{adjust}"}
            )
            if not isinstance(body, dict) or body.get("code") != 0:
                raise DataFormatError("腾讯历史日线业务状态异常")
            container = body.get("data")
            if not isinstance(container, dict) or not isinstance(
                container.get(symbol), dict
            ):
                raise DataFormatError("腾讯日线证券数据字段异常")
            data = container[symbol]
            page = data.get(f"{adjust}day" if adjust else "day")
            if not isinstance(page, list):
                raise DataFormatError("腾讯日线字段与所选复权方式应一致")
            if not page:
                break
            for row in page:
                if not isinstance(row, list) or len(row) < 6:
                    raise DataFormatError("腾讯日线记录字段异常")
                if not isinstance(row[0], str):
                    raise DataFormatError("腾讯日线日期应为字符串")
                if start <= row[0] <= end:
                    rows.append(
                        {
                            "datetime": row[0],
                            "trade_date": row[0],
                            "open": number(row[1]),
                            "close": number(row[2]),
                            "high": number(row[3]),
                            "low": number(row[4]),
                            "volume": number(row[5]),
                            "volume_unit": "lot",
                            "source": "tencent",
                            "adjust": adjust,
                        }
                    )
            oldest = min(row[0] for row in page)
            if oldest <= start or len(page) < 640:
                break
            try:
                next_end = (date.fromisoformat(oldest) - timedelta(days=1)).isoformat()
            except ValueError as exc:
                raise DataFormatError("腾讯日线日期格式异常") from exc
            if next_end >= cursor:
                raise DataFormatError("腾讯日线分页日期应持续向前推进")
            cursor = next_end
        else:
            raise DataFormatError(
                "腾讯日线达到 max_pages，请缩小日期范围或提高页数上限"
            )
        return sorted_rows(rows)
