"""使用 urllib 请求上游数据，异常消息仅显示主机和路径。"""

import gzip
import json
import socket
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .exceptions import ConfigurationError, DataFormatError, RequestError


def retry_seconds(value):
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(
                0,
                (
                    parsedate_to_datetime(value) - datetime.now(timezone.utc)
                ).total_seconds(),
            )
        except (TypeError, ValueError):
            return 0


class HttpClient:
    def __init__(self, timeout=10, retries=1):
        if timeout <= 0 or not isinstance(retries, int) or retries < 0:
            raise ConfigurationError("timeout 应大于 0，retries 应为非负整数")
        self.timeout = timeout
        self.retries = retries

    def get_bytes(self, url, *, params=None, headers=None, timeout=None):
        query = urlencode(
            {key: value for key, value in (params or {}).items() if value is not None}
        )
        request_url = url + ("&" if "?" in url else "?") + query if query else url
        parts = urlsplit(url)
        endpoint = parts.netloc + parts.path
        request = Request(
            request_url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})}
        )
        for attempt in range(self.retries + 1):
            try:
                with urlopen(
                    request, timeout=self.timeout if timeout is None else timeout
                ) as response:
                    data = response.read()
                    return (
                        gzip.decompress(data)
                        if response.headers.get("Content-Encoding") == "gzip"
                        else data
                    )
            except HTTPError as exc:
                status = exc.code
                delay = retry_seconds(exc.headers.get("Retry-After"))
                exc.close()
                error = RequestError(
                    f"{endpoint} HTTP {status}", status_code=status, retry_after=delay
                )
                retryable = status in {502, 503, 504}
            except (URLError, OSError, socket.timeout) as exc:
                error = RequestError(f"{endpoint} 网络请求失败（{type(exc).__name__}）")
                retryable = True
            if attempt == self.retries or not retryable:
                raise error from None
            time.sleep(0.5 * 2**attempt)

    def get_text(self, url, *, encoding="utf-8", **kwargs):
        try:
            return self.get_bytes(url, **kwargs).decode(encoding)
        except UnicodeError as exc:
            raise DataFormatError("响应文本编码异常") from exc

    def get_json(self, url, **kwargs):
        try:
            return json.loads(self.get_text(url, **kwargs))
        except (ValueError, TypeError) as exc:
            raise DataFormatError("响应应为 JSON") from exc
