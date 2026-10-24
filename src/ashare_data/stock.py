"""公开行情函数。"""

from ._default import get_client
from typing import Sequence

from .models import Bar, DateLike, Quote


def get_stock_quote(code: str) -> Quote:
    """获取单只股票实时行情，返回 Quote。"""
    return get_client().get_stock_quote(code)


def get_stock_quotes(codes: Sequence[str]) -> list[Quote]:
    """批量获取股票实时行情，按首次输入顺序返回 Quote 列表。"""
    return get_client().get_stock_quotes(codes)


def get_stock_history(
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
    return get_client().get_stock_history(
        code,
        start,
        end,
        sources=sources,
        adjust=adjust,
        scale=scale,
        datalen=datalen,
        max_pages=max_pages,
    )
