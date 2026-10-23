"""沪深指数统一入口。"""

from ._default import get_client


def get_index_quote(code):
    return get_client().get_index_quote(code)


def get_index_quotes(codes):
    return get_client().get_index_quotes(codes)


def get_index_history(code, start=None, end=None, **kwargs):
    return get_client().get_index_history(code, start, end, **kwargs)
