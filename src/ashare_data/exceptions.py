"""公开异常类型。"""


class MarketDataError(Exception):
    """行情请求及解析错误的共同父类。"""


class InvalidCodeError(MarketDataError, ValueError):
    """证券代码格式错误。"""


class ConfigurationError(MarketDataError, ValueError):
    """请求参数或账户配置错误。"""


class RequestError(MarketDataError):
    """网络或 HTTP 错误，保留状态码及服务端建议等待时间。"""

    def __init__(self, message, *, status_code=None, retry_after=0):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class DataFormatError(MarketDataError):
    """响应字段、业务状态或分页结果异常。"""


class QuoteNotFoundError(MarketDataError):
    """指定证券的行情缺失。"""


class AllSourcesFailedError(MarketDataError):
    """候选数据源依次失败，errors 保存各次异常。"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("；".join(f"{name}: {error}" for name, error in errors))
