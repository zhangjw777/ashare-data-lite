"""依次尝试数据源，统一保留失败原因。"""

from .exceptions import AllSourcesFailedError, MarketDataError


def first_success(candidates):
    errors = []
    for name, fetch in candidates:
        try:
            return fetch()
        except MarketDataError as exc:
            errors.append((name, exc))
    raise AllSourcesFailedError(errors)
