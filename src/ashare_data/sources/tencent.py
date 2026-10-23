"""腾讯行情文本解析，字段定义沿用原项目 provider。"""

import re
from datetime import date, datetime, timedelta
from typing import Any

from .._utils import date_range, is_index, normalize_symbol, number, sorted_rows
from ..exceptions import ConfigurationError, DataFormatError

QUOTE_URL = "https://qt.gtimg.cn/q="
HISTORY_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
RECORD = re.compile(r'v_([A-Za-z0-9_]+)="(.*?)";', re.DOTALL)


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
        try:
            return float(summary[2])
        except ValueError:
            pass
    amount_10k = _float(fields, 57)
    return amount_10k * 10000 if amount_10k is not None else None


def parse_quote(symbol: str, payload: str, instrument="auto") -> dict[str, Any]:
    fields = [part.strip() for part in payload.split("~")]
    if len(fields) <= 30:
        raise DataFormatError(f"{symbol} 返回字段不足：实际 {len(fields)} 个")
    symbol = normalize_symbol(symbol)
    instrument_type = (
        "index"
        if instrument == "index" or is_index(symbol)
        else _instrument_type(symbol, fields)
    )
    book = _order_book(fields)
    amount_yuan = _amount_yuan(fields)
    volume_lot = _int(fields, 6)
    average_price_calculated = (
        amount_yuan / (volume_lot * 100)
        if amount_yuan is not None and volume_lot
        else None
    )
    bid_volume = sum((level["volume_lot"] or 0 for level in book["bids"]))
    ask_volume = sum((level["volume_lot"] or 0 for level in book["asks"]))
    result: dict[str, Any] = {
        "source": "tencent",
        "symbol": symbol,
        "market": symbol[:2],
        "code": _field(fields, 2),
        "name": _field(fields, 1),
        "instrument_type": instrument_type,
        "type_tag": _field(fields, 61) or None,
        "market_status_code": _field(fields, 60) or None,
        "is_suspended": _field(fields, 40) == "S",
        "quote_time": _quote_time(_field(fields, 30)),
        "quote_time_raw": _field(fields, 30),
        "last": _float(fields, 3),
        "prev_close": _float(fields, 4),
        "open": _float(fields, 5),
        "high": _float(fields, 33),
        "low": _float(fields, 34),
        "change": _float(fields, 31),
        "change_pct": _float(fields, 32),
        "volume_lot": volume_lot,
        "outer_volume_lot": _int(fields, 7),
        "inner_volume_lot": _int(fields, 8),
        "amount_yuan": amount_yuan,
        "amount_10k": _float(fields, 57),
        "turnover_rate": _float(fields, 38),
        "amplitude": _float(fields, 43),
        "circulating_market_cap_100m": _float(fields, 44),
        "total_market_cap_100m": _float(fields, 45),
        "pb": _float(fields, 46),
        "limit_up": _float(fields, 47),
        "limit_down": _float(fields, 48),
        "volume_ratio": _float(fields, 49),
        "order_imbalance_lot": _int(fields, 50),
        "order_imbalance_calculated": bid_volume - ask_volume,
        "average_price": _float(fields, 51),
        "average_price_calculated": average_price_calculated,
        "currency": _field(fields, 82) or None,
        "recent_trades_raw": _field(fields, 29) or None,
        "order_book": book,
        "raw_fields": fields,
    }
    extension = {
        "statistics_candidates": {
            "year_high": _float(fields, 67),
            "year_low": _float(fields, 68),
            "short_return_1": _float(fields, 69),
            "short_return_2": _float(fields, 70),
            "short_return_3": _float(fields, 71),
            "year_return": _float(fields, 79),
        },
        "raw_extension": {
            str(index): _field(fields, index) for index in range(62, len(fields))
        },
    }
    if instrument_type == "etf":
        iopv = _float(fields, 78)
        premium_rate = _float(fields, 77)
        last = _float(fields, 3)
        calculated_premium_rate = (
            (last / iopv - 1) * 100 if last is not None and iopv else None
        )
        result["etf"] = {
            "iopv": iopv,
            "premium_rate": premium_rate,
            "premium_rate_calculated": calculated_premium_rate,
            "circulating_units": _int(fields, 72),
            "total_units": _int(fields, 73),
            "nav_reference_candidate": _float(fields, 81),
            **extension,
        }
    elif instrument_type == "stock":
        result["stock"] = {
            "pe": _float(fields, 39),
            "pe_candidate_1": _float(fields, 52),
            "pe_candidate_2": _float(fields, 53),
            "circulating_shares": _int(fields, 72),
            "total_shares": _int(fields, 73),
            **extension,
        }
    if instrument_type == "index":
        result["index"] = extension
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
                            "raw": row,
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
