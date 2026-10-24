"""证券代码、日期及数值的共同约定。"""

import math
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from .exceptions import ConfigurationError, InvalidCodeError


def number(value):
    try:
        result = float(str(value).replace(",", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def china_today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def date_text(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ConfigurationError("日期使用 YYYY-MM-DD 或 date 对象") from exc


def date_range(start=None, end=None):
    start = date_text(start) if start is not None else "1970-01-01"
    end = date_text(end) if end is not None else china_today().isoformat()
    if start > end:
        raise ConfigurationError("起始日期应早于或等于截止日期")
    return start, end


def normalize_symbol(code, instrument="auto"):
    if instrument not in {"auto", "stock", "etf", "index"}:
        raise ConfigurationError("instrument 使用 auto、stock、etf 或 index")
    if not isinstance(code, str):
        raise InvalidCodeError("证券代码使用字符串，以保留前导零")
    value = code.strip().lower()
    if re.fullmatch(r"(sh|sz)\d{6}", value):
        return value
    suffix = re.fullmatch(r"(\d{6})\.(sh|sz)", value)
    if suffix:
        return suffix[2] + suffix[1]
    if not re.fullmatch(r"\d{6}", value):
        raise InvalidCodeError(f"证券代码格式错误：{code!r}")
    if instrument == "index":
        if value.startswith("000"):
            return "sh" + value
        if value.startswith("399"):
            return "sz" + value
        raise InvalidCodeError("该指数请使用明确市场前缀，例如 sh000001")
    return ("sh" if value.startswith(("5", "6", "9")) else "sz") + value


def is_index(symbol):
    return symbol.startswith(("sh000", "sz399"))


def fund_code(code):
    symbol = normalize_symbol(code, "etf")
    return symbol[2:]


def sorted_rows(rows, key="datetime"):
    unique = {row[key]: row for row in rows}
    return [unique[value] for value in sorted(unique)]


def source_order(sources, default, allowed):
    """验证并保留来源优先顺序。"""
    values = default if sources is None else sources
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ConfigurationError("sources 使用按优先级排列的来源列表")
    if not values or any(
        not isinstance(value, str) or value not in allowed for value in values
    ):
        raise ConfigurationError("sources 可用来源：" + ", ".join(allowed))
    return tuple(dict.fromkeys(values))
