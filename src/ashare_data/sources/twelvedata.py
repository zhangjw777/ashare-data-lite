"""Twelve Data 的 HTTPS K 线请求和完整日线分页。"""

from datetime import datetime, timedelta, timezone

from .._utils import date_range, number, sorted_rows
from ..exceptions import ConfigurationError, DataFormatError

URL = "https://api.twelvedata.com/time_series"


class TwelveDataSource:
    def __init__(self, http, api_key=None):
        self.http, self.api_key = http, api_key

    def bars(
        self,
        symbol,
        *,
        interval="1day",
        outputsize=5000,
        start=None,
        end=None,
        adjust="all",
        api_key=None,
    ):
        key = api_key or self.api_key
        if not key:
            raise ConfigurationError("请配置 TWELVE_DATA_API_KEY 或传入 api_key")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ConfigurationError("symbol 应为有效证券代码")
        if not isinstance(outputsize, int) or not 1 <= outputsize <= 5000:
            raise ConfigurationError("outputsize 使用 1～5000 的整数")
        if adjust not in {"none", "splits", "dividends", "all"}:
            raise ConfigurationError("adjust 使用 none、splits、dividends 或 all")
        body = self.http.get_json(
            URL,
            params={
                "apikey": key,
                "symbol": symbol.strip().upper(),
                "interval": interval,
                "outputsize": outputsize,
                "start_date": start,
                "end_date": end,
                "timezone": "UTC",
                "order": "desc",
                "adjust": adjust,
            },
        )
        if not isinstance(body, dict) or body.get("status") == "error":
            raise DataFormatError("Twelve Data K 线业务状态异常")
        if not isinstance(body.get("values"), list):
            raise DataFormatError("Twelve Data values 字段异常")
        rows = []
        for row in body["values"]:
            if not isinstance(row, dict):
                raise DataFormatError("Twelve Data K 线记录应为字典")
            try:
                moment = datetime.fromisoformat(row["datetime"])
            except (KeyError, ValueError, TypeError) as exc:
                raise DataFormatError("Twelve Data K 线时间异常") from exc
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            values = {
                key: number(row.get(key))
                for key in ("open", "high", "low", "close", "volume")
            }
            if values["close"] is None:
                raise DataFormatError("Twelve Data 收盘价字段异常")
            rows.append(
                {
                    "datetime": row["datetime"],
                    "trade_date": row["datetime"][:10],
                    "timestamp": int(moment.timestamp()),
                    **values,
                    "volume_unit": "upstream",
                    "source": "twelvedata",
                    "adjust": adjust,
                    "meta": body.get("meta", {}),
                    "raw": row,
                }
            )
        return sorted_rows(rows)

    def daily_history(
        self, symbol, start=None, end=None, *, adjust="all", api_key=None, max_pages=100
    ):
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ConfigurationError("max_pages 应为正整数")
        start, end = date_range(start, end)
        cursor, rows = end + " 23:59:59", []
        for _ in range(max_pages):
            page = self.bars(
                symbol,
                interval="1day",
                start=start,
                end=cursor,
                outputsize=5000,
                adjust=adjust,
                api_key=api_key,
            )
            rows.extend(row for row in page if start <= row["trade_date"] <= end)
            if not page or len(page) < 5000 or page[0]["trade_date"] <= start:
                break
            next_end = (
                datetime.fromisoformat(page[0]["datetime"]) - timedelta(seconds=1)
            ).strftime("%Y-%m-%d %H:%M:%S")
            if next_end >= cursor:
                raise DataFormatError("Twelve Data 分页时间应持续向前推进")
            cursor = next_end
        else:
            raise DataFormatError(
                "Twelve Data 达到 max_pages，请缩小日期范围或提高页数上限"
            )
        return sorted_rows(rows)
