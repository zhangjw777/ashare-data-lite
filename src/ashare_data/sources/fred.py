"""FRED 经济与市场时间序列 HTTPS 接口。"""

from datetime import datetime, timezone

from .._utils import date_range, number, sorted_rows
from ..exceptions import ConfigurationError, DataFormatError

URL = "https://api.stlouisfed.org/fred/series/observations"


class FredSource:
    def __init__(self, http, api_key=None):
        self.http, self.api_key = http, api_key

    def series(self, series_id, start=None, end=None, *, api_key=None):
        key = api_key or self.api_key
        if not key:
            raise ConfigurationError("请配置 FRED_API_KEY 或传入 api_key")
        series_id = series_id.strip().upper()
        if not series_id:
            raise ConfigurationError("series_id 应为有效序列标识")
        start, end = date_range(start, end)
        offset, rows = 0, []
        while True:
            body = self.http.get_json(
                URL,
                params={
                    "series_id": series_id,
                    "api_key": key,
                    "file_type": "json",
                    "observation_start": start,
                    "observation_end": end,
                    "sort_order": "asc",
                    "limit": 100000,
                    "offset": offset,
                },
            )
            if not isinstance(body, dict) or "error_code" in body:
                raise DataFormatError("FRED 序列业务状态异常")
            page = body.get("observations")
            if not isinstance(page, list):
                raise DataFormatError("FRED observations 字段异常")
            try:
                total = int(body["count"])
            except (KeyError, ValueError, TypeError) as exc:
                raise DataFormatError("FRED count 字段异常") from exc
            for row in page:
                if not isinstance(row, dict) or "date" not in row:
                    raise DataFormatError("FRED 观测记录字段异常")
                value = number(row.get("value"))
                if value is None:
                    continue
                try:
                    moment = datetime.strptime(row["date"], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError) as exc:
                    raise DataFormatError("FRED 观测日期异常") from exc
                if start <= row["date"] <= end:
                    rows.append(
                        {
                            "date": row["date"],
                            "timestamp": int(moment.timestamp()),
                            "value": value,
                            "series_id": series_id,
                            "source": "fred",
                            "raw": row,
                        }
                    )
            offset += len(page)
            if offset >= total:
                return sorted_rows(rows, "date")
            if not page:
                raise DataFormatError("FRED 分页提前结束")
