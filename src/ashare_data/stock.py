"""沪深股票统一入口。"""

from ._default import get_client


def get_stock_quote(code):
    return get_client().get_stock_quote(code)


def get_stock_quotes(codes):
    return get_client().get_stock_quotes(codes)


def get_stock_history(code, start=None, end=None, **kwargs):
    return get_client().get_stock_history(code, start, end, **kwargs)
