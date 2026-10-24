"""公开行情函数。"""

from ._default import get_client
from typing import Sequence

from .models import Bar, DateLike, FundNav, FundShares, Quote


def get_etf_quote(code: str) -> Quote:
    """获取单只ETF实时行情，返回 Quote。"""
    return get_client().get_etf_quote(code)


def get_etf_quotes(codes: Sequence[str]) -> list[Quote]:
    """批量获取ETF实时行情，按首次输入顺序返回 Quote 列表。"""
    return get_client().get_etf_quotes(codes)


def get_etf_history(
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
    return get_client().get_etf_history(
        code,
        start,
        end,
        sources=sources,
        adjust=adjust,
        scale=scale,
        datalen=datalen,
        max_pages=max_pages,
    )


def get_fund_nav_history(
    code: str,
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    sources: Sequence[str] | None = None,
) -> list[FundNav]:
    """获取升序基金单位净值，默认东方财富移动端→网页，sources 可调整顺序。"""
    return get_client().get_fund_nav_history(code, start, end, sources=sources)


def get_etf_catalog() -> dict[str, str]:
    """获取场内 ETF 目录，返回六位代码到名称的映射。"""
    return get_client().get_etf_catalog()


def get_sse_etf_shares(day: DateLike) -> list[FundShares]:
    """获取上交所指定统计日的 ETF 份额，shares 单位为份。"""
    return get_client().get_sse_etf_shares(day)
