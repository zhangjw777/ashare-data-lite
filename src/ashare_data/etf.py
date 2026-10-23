"""ETF 行情、基金净值及目录统一入口。"""

from ._default import get_client


def get_etf_quote(code):
    return get_client().get_etf_quote(code)


def get_etf_quotes(codes):
    return get_client().get_etf_quotes(codes)


def get_etf_history(code, start=None, end=None, **kwargs):
    return get_client().get_etf_history(code, start, end, **kwargs)


def get_fund_nav_history(code, start=None, end=None):
    return get_client().get_fund_nav_history(code, start, end)


def get_etf_catalog():
    return get_client().get_etf_catalog()


def get_sse_etf_shares(day):
    return get_client().get_sse_etf_shares(day)
